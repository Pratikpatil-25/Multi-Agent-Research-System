"""
FastAPI backend for the Multi-Agent Research System.

Exposes the research pipeline (search -> read -> write -> critique -> human
review) as a REST API so the Streamlit client (client/app.py) can trigger,
review, and resume research runs.

HUMAN-IN-THE-LOOP :
The graph now pauses at human_review_node (see nodes.py / pipeline.py) and
waits for a person to approve or request revisions before finishing. Because
each HTTP request is stateless, a single research run now spans TWO calls:

  1. POST /research           -> starts the run; it runs until either it
                                  finishes or hits the human_review pause
                                  point, and returns either way.
  2. POST /research/{id}/resume -> sends the human's decision back in and
                                  continues the run (which may pause again,
                                  e.g. if the writer needs another revision
                                  round).

`thread_id` is what ties these calls together - it's generated on the first
call and must be echoed back on every /resume call for that run.
"""

import logging
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from langgraph.types import Command

from graph import app as graph
from pipeline import build_initial_state


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research_api")


app = FastAPI(
    title="Multi-Agent Research System API",
    description="Backend API orchestrating the search, reader, writer, critic and human-review agents.",
    version="1.1.0",
)


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



class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="The research topic to investigate")


class ResumeRequest(BaseModel):
    action: str = Field(..., description='"approve" or "revise"')
    comments: Optional[str] = Field(
        default=None, description="Human's notes for the writer, used when action='revise'"
    )
    edited_report: Optional[str] = Field(
        default=None, description="Optional human-edited report text, used when action='approve'"
    )


class ReportResult(BaseModel):
    topic: str
    urls: List[str] = Field(default_factory=list, description="Source URLs found by the Search agent")
    scraped_content: List[str] = Field(
        default_factory=list, description="Research notes extracted by the Scraper agent, one entry per source"
    )
    report: str = Field(default="", description="Final report text produced by the Writer agent")
    feedback: str = Field(default="", description="Critic agent's most recent review of the report")
    is_approved: bool = Field(default=False, description="Whether a human approved the final report")
    attempts: int = Field(default=0, description="How many writer/critic/human revision rounds were used")


class PendingReview(BaseModel):
    """What the human reviewer needs to see and decide on."""
    message: str
    topic: str
    report: str
    critic_feedback: str
    attempt: int


class RunResponse(BaseModel):
    """
    Returned by both /research and /research/{thread_id}/resume.

    status="interrupted" -> the graph is paused, waiting on `pending_review`.
                             Call /research/{thread_id}/resume next.
    status="completed"    -> the graph finished; `result` has the final data.
    """
    thread_id: str
    status: str  # "interrupted" | "completed"
    pending_review: Optional[PendingReview] = None
    result: Optional[ReportResult] = None


class HealthResponse(BaseModel):
    status: str



# Helpers

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
    """Coerce a list of values to a plain list of strings."""
    if not values:
        return []
    return [_to_text(v) for v in values]


def _build_run_response(thread_id: str, graph_result: dict) -> RunResponse:
    """
    Inspect the dict returned by graph.invoke() and figure out whether the
    run paused at a human_review interrupt or actually finished.
    """
    interrupts = graph_result.get("__interrupt__")

    if interrupts:
        # graph.invoke() returns a tuple/list of Interrupt objects when
        # paused; .value is whatever payload we passed to interrupt(...)
        # inside human_review_node.
        payload = interrupts[0].value
        return RunResponse(
            thread_id=thread_id,
            status="interrupted",
            pending_review=PendingReview(**payload),
        )

    result = ReportResult(
        topic=graph_result.get("topic", ""),
        urls=_to_text_list(graph_result.get("urls", [])),
        scraped_content=_to_text_list(graph_result.get("scraped_content", [])),
        report=_to_text(graph_result.get("report", "")),
        feedback=_to_text(graph_result.get("feedback", "")),
        is_approved=bool(graph_result.get("is_approved", False)),
        attempts=int(graph_result.get("attempt", 0)),
    )
    response = RunResponse(thread_id=thread_id, status="completed", result=result)
    _run_history[thread_id] = response
    return response



# In-memory store for run history (optional convenience feature).
# Resets on server restart - swap for a DB/Redis if you need persistence.
# Note: paused (interrupted) runs are tracked by the graph's own
# checkpointer, not this dict - this only stores completed results.
_run_history: Dict[str, RunResponse] = {}


@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health_check():
    """Simple liveness check for the client to verify the backend is up."""
    return {"status": "ok"}


@app.post("/research", response_model=RunResponse, tags=["Research"])
async def start_research(request: ResearchRequest):
    """
    Starts a new research run. Runs the graph until it either finishes or
    pauses for human review, and returns either way.
    """
    topic = request.topic.strip()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = build_initial_state(topic)

    logger.info(f"Starting research run {thread_id} for topic: {topic!r}")

    try:
        result = await run_in_threadpool(graph.invoke, initial_state, config)
    except Exception as e:
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    return _build_run_response(thread_id, result)


@app.post("/research/{thread_id}/resume", response_model=RunResponse, tags=["Research"])
async def resume_research(thread_id: str, resume: ResumeRequest):
    """
    Resumes a paused research run with a human's decision.

    action="approve" finalizes the report (optionally replacing it with
    edited_report). action="revise" sends `comments` back to the Writer
    agent as feedback and runs another writer -> critic -> human_review pass.
    """
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"Resuming research run {thread_id} with action={resume.action!r}")

    try:
        result = await run_in_threadpool(
            graph.invoke, Command(resume=resume.model_dump()), config
        )
    except Exception as e:
        logger.exception("Pipeline resume failed")
        raise HTTPException(status_code=500, detail=f"Resume failed: {str(e)}")

    return _build_run_response(thread_id, result)


@app.get("/research/{thread_id}", response_model=RunResponse, tags=["Research"])
async def get_research_by_thread(thread_id: str):
    """Retrieve a previously completed research result (in-memory only)."""
    result = _run_history.get(thread_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No completed research found for this thread_id (it may still be pending review).",
        )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)