"""
FastAPI backend for the Multi-Agent Research System.

Exposes the research pipeline (search -> read -> write -> critique) as a REST API
so the Streamlit client (client/app.py) can trigger and consume research runs.

Place this file at: server/main.py
Run from the `server/` directory with: uvicorn main:app --reload --port 8000
"""

import logging
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from pipeline import pipeline

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research_api")

# ------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------
app = FastAPI(
    title="Multi-Agent Research System API",
    description="Backend API orchestrating the search, reader, writer and critic agents.",
    version="1.0.0",
)

# Allow the Streamlit client to call this API from a different port/origin.
# Streamlit's default dev port is 8501 - tighten this list for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------
# UPDATED: matches state.py's State TypedDict, which has these fields:
#   topic, messages, attempt, is_approved, urls, scraped_content, report, feedback
# There is no "search_results" field in State (there never was) - the old
# version of this file read state.get("search_results", ...), which would
# always silently return the empty-string default. Fixed to read "urls" and
# "scraped_content" instead, which are the fields the graph actually fills in.
class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="The research topic to investigate")


class ResearchResponse(BaseModel):
    topic: str
    urls: List[str] = Field(default_factory=list, description="Source URLs found by the Search agent")
    scraped_content: List[str] = Field(
        default_factory=list, description="Research notes extracted by the Scraper agent, one entry per source"
    )
    report: str = Field(default="", description="Final report text produced by the Writer agent")
    feedback: str = Field(default="", description="Critic agent's most recent review of the report")
    is_approved: bool = Field(default=False, description="Whether the Critic approved the final report")
    attempts: int = Field(default=0, description="How many writer/critic revision rounds were used")


class HealthResponse(BaseModel):
    status: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _to_text(value) -> str:
    """
    Coerce a single value to plain text.

    ASSUMPTION: some state fields (e.g. "report", "feedback") are already
    plain strings coming out of nodes.py (extract_draft_node / critic_node),
    but this stays as a safety net in case a LangChain message object
    (e.g. AIMessage) ever ends up in one of these fields instead.
    """
    if hasattr(value, "content"):
        return value.content
    return str(value) if value is not None else ""


def _to_text_list(values) -> List[str]:
    """
    Coerce a list of values (e.g. state["scraped_content"] or state["urls"])
    to a plain list of strings. Handles the case where an entry is a
    LangChain message object instead of a raw string.
    """
    if not values:
        return []
    return [_to_text(v) for v in values]


# ------------------------------------------------------------------
# In-memory store for run history (optional convenience feature).
# Resets on server restart - swap for a DB/Redis if you need persistence.
# ------------------------------------------------------------------
_run_history: Dict[str, ResearchResponse] = {}


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health_check():
    """Simple liveness check for the client to verify the backend is up."""
    return {"status": "ok"}


@app.post("/research", response_model=ResearchResponse, tags=["Research"])
async def run_research(request: ResearchRequest):
    """
    Runs the full multi-agent research pipeline (search -> read -> write -> critique)
    for the given topic and returns the resulting state.

    The pipeline itself is synchronous/blocking (LLM + web calls), so it's offloaded
    to a threadpool to avoid blocking the FastAPI event loop while it runs.
    """
    topic = request.topic.strip()
    logger.info(f"Received research request for topic: {topic!r}")

    try:
        state = await run_in_threadpool(pipeline, topic)
    except Exception as e:
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    response = ResearchResponse(
        topic=topic,
        urls=_to_text_list(state.get("urls", [])),
        scraped_content=_to_text_list(state.get("scraped_content", [])),
        report=_to_text(state.get("report", "")),
        feedback=_to_text(state.get("feedback", "")),
        is_approved=bool(state.get("is_approved", False)),
        attempts=int(state.get("attempt", 0)),
    )

    _run_history[topic] = response
    return response


@app.get("/research/{topic}", response_model=ResearchResponse, tags=["Research"])
async def get_research_by_topic(topic: str):
    """Retrieve a previously run research result for a given topic (in-memory only)."""
    result = _run_history.get(topic)
    if result is None:
        raise HTTPException(status_code=404, detail="No research found for this topic yet.")
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)