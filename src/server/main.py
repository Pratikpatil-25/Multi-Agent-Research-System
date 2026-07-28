"""
FastAPI backend for the Multi-Agent Research System.

Exposes the research pipeline (search -> read -> write -> critique) as a REST API
so the Streamlit client (client/app.py) can trigger and consume research runs.

Place this file at: server/main.py
Run from the `server/` directory with: uvicorn main:app --reload --port 8000
"""

import logging
from typing import Dict, Optional

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
class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="The research topic to investigate")


class ResearchResponse(BaseModel):
    topic: str
    search_results: str
    scraped_content: str
    report: str
    feedback: str


class HealthResponse(BaseModel):
    status: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _to_text(value) -> str:
    """
    Coerce chain/agent outputs to plain text.

    ASSUMPTION: writer_chain / critic_chain may return LangChain message
    objects (e.g. AIMessage) rather than raw strings, depending on how
    they're built in components/agents.py. This safely unwraps `.content`
    if present, otherwise falls back to str(). Remove this if your chains
    already return plain strings.
    """
    if hasattr(value, "content"):
        return value.content
    return str(value) if value is not None else ""


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
        search_results=_to_text(state.get("search_results", "")),
        scraped_content=_to_text(state.get("scraped_content", "")),
        report=_to_text(state.get("report", "")),
        feedback=_to_text(state.get("feedback", "")),
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