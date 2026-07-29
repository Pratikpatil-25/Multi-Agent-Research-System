"""
Streamlit client for the Multi-Agent Research System.

Connects to the FastAPI backend (server/main.py) using the API_URL
defined in client/config.py.

Place this file at: client/app.py
(and .streamlit/config.toml alongside it, for the theme colors)
Run with: streamlit run app.py

UPDATED for the iterative + human-in-the-loop pipeline:
A research run is no longer "one request, one final answer." It now goes:

  1. POST /research               -> runs until it either finishes or pauses
                                      for human review.
  2. (if paused) show the draft + critic feedback, let a human approve or
     request revisions.
  3. POST /research/{id}/resume   -> sends the human's decision back in;
                                      may pause again (another revision
                                      round) or finish.

Everything needed to keep this going lives in st.session_state - the
thread_id ties the start call and every resume call together.
"""

import html

import requests
import streamlit as st

from config import API_URL

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Research Desk",
    page_icon="🗂️",
    layout="wide",
)

# Requests can take a while since the pipeline runs multiple
# LLM + web calls in sequence (search -> read -> write -> critique).
REQUEST_TIMEOUT = 300  # seconds


# ------------------------------------------------------------------
# Visual identity
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="st-"], [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    h1, h2, h3 {
        font-family: 'Fraunces', serif;
    }

    .case-eyebrow {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #4C9DA3;
    }

    .case-stamp {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border: 1.5px solid #D9A63D;
        color: #D9A63D;
        padding: 3px 12px;
        border-radius: 4px;
        display: inline-block;
        transform: rotate(-2deg);
    }

    .case-stamp.pending {
        border-color: #D9A63D;
        color: #D9A63D;
    }

    .case-stamp.approved {
        border-color: #4C9DA3;
        color: #4C9DA3;
    }

    .case-title {
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 2.6rem;
        margin: 0.35rem 0 0.25rem 0;
        color: #E7E9E4;
        line-height: 1.1;
    }

    .case-sub {
        color: #9AA3A8;
        font-size: 1.02rem;
        max-width: 640px;
        margin-bottom: 0.4rem;
    }

    .stage-line {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #4C9DA3;
        border-top: 1px dashed rgba(76, 157, 163, 0.35);
        border-bottom: 1px dashed rgba(76, 157, 163, 0.35);
        padding: 0.5rem 0;
        margin: 0.9rem 0 1.6rem 0;
    }

    .section-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #4C9DA3;
        margin-bottom: 0.5rem;
        display: block;
    }

    .sidebar-eyebrow {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #9AA3A8;
        margin-bottom: -0.4rem;
    }

    .thread-tag {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        color: #9AA3A8;
    }

    .stButton > button, .stDownloadButton > button {
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-size: 0.8rem;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def check_backend_health() -> bool:
    """Pings the backend's /health route. Returns True if reachable and healthy."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") == "ok"
    except requests.exceptions.RequestException:
        return False


def _raise_for_bad_response(resp: requests.Response):
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ValueError(detail)


def start_research(topic: str) -> dict:
    """
    Calls POST /research. Returns the RunResponse dict:
    {"thread_id", "status", "pending_review"?, "result"?}
    """
    resp = requests.post(
        f"{API_URL}/research",
        json={"topic": topic},
        timeout=REQUEST_TIMEOUT,
    )
    _raise_for_bad_response(resp)
    return resp.json()


def resume_research(thread_id: str, action: str, comments: str = None, edited_report: str = None) -> dict:
    """
    Calls POST /research/{thread_id}/resume with the human's decision.
    Returns the same RunResponse shape as start_research.
    """
    payload = {"action": action}
    if comments:
        payload["comments"] = comments
    if edited_report:
        payload["edited_report"] = edited_report

    resp = requests.post(
        f"{API_URL}/research/{thread_id}/resume",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    _raise_for_bad_response(resp)
    return resp.json()


def fetch_completed_case(thread_id: str) -> dict:
    """
    Calls GET /research/{thread_id}. Only works for runs that finished
    (approved or hit max attempts) - the backend only stores completed
    results, not runs still waiting on human review.
    """
    resp = requests.get(f"{API_URL}/research/{thread_id.strip()}", timeout=15)
    if resp.status_code == 404:
        raise ValueError("No completed case found for that Case ID (it may still be pending review, or doesn't exist).")
    _raise_for_bad_response(resp)
    return resp.json()


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------
# "run" holds the most recent RunResponse from the backend:
#   {"thread_id": ..., "status": "interrupted" | "completed",
#    "pending_review": {...} or None, "result": {...} or None}
if "run" not in st.session_state:
    st.session_state.run = None
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-eyebrow">Station Status</div>', unsafe_allow_html=True)
    st.header("🛰️ Backend")
    st.caption(f"API URL: `{API_URL}`")

    if st.button("Check connection", use_container_width=True):
        with st.spinner("Pinging backend..."):
            healthy = check_backend_health()
        if healthy:
            st.success("Backend is reachable.")
        else:
            st.error("Backend unreachable — start the FastAPI server and try again.")

    st.divider()
    st.markdown('<div class="sidebar-eyebrow">Retrieve a Prior Case</div>', unsafe_allow_html=True)
    st.header("🗃️ Archive Lookup")
    st.caption(
        "Pulls a previously *completed* case by its Case ID (shown at the top "
        "of the case file once a run finishes). Cases still awaiting human "
        "review aren't retrievable this way — keep this tab open instead."
    )
    lookup_id = st.text_input("Case ID (thread_id)", key="lookup_id")
    if st.button("Fetch", use_container_width=True, key="fetch_btn"):
        if not lookup_id.strip():
            st.warning("Enter a Case ID to look up.")
        else:
            try:
                with st.spinner("Searching the archive..."):
                    run = fetch_completed_case(lookup_id.strip())
                st.session_state.run = run
                st.session_state.last_topic = run.get("result", {}).get("topic", "")
                st.success("File loaded from the archive.")
            except ValueError as e:
                st.warning(str(e))
            except requests.exceptions.RequestException as e:
                st.error(f"Could not reach backend: {e}")

    st.divider()
    st.caption(
        "Every case runs through **Search**, **Read**, **Write**, and **Critique** "
        "agents, then pauses for **Human Review** before it's finalized — "
        "approving may loop back through Write/Critique again if you request changes."
    )


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="case-eyebrow">Field Dossier · Multi-Agent Ops</span>
        <span class="case-stamp">Open Case</span>
    </div>
    <div class="case-title">Research Desk</div>
    <div class="case-sub">
        Dispatch a topic below. Agents build the file in sequence, then hand it to you for sign-off.
    </div>
    <div class="stage-line">01 Search &nbsp;→&nbsp; 02 Read &nbsp;→&nbsp; 03 Write &nbsp;→&nbsp; 04 Critique &nbsp;→&nbsp; 05 Your Review</div>
    """,
    unsafe_allow_html=True,
)

with st.form("research_form"):
    topic = st.text_input(
        "Research topic",
        placeholder="e.g. Recent advances in small modular nuclear reactors",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Open case →", use_container_width=True, type="primary")

if submitted:
    if not topic or len(topic.strip()) < 3:
        st.warning("Enter a topic with at least 3 characters.")
    else:
        with st.spinner("Agents are working the case... this can take a minute or two."):
            try:
                run = start_research(topic.strip())
                st.session_state.run = run
                st.session_state.last_topic = topic.strip()
            except ValueError as e:
                st.error(f"The pipeline failed: {e}")
            except requests.exceptions.RequestException as e:
                st.error(
                    f"Could not reach the backend at `{API_URL}`. "
                    f"Start the FastAPI server and try again.\n\nDetails: {e}"
                )


# ------------------------------------------------------------------
# Results / review display
# ------------------------------------------------------------------
run = st.session_state.run

if run:
    thread_id = run.get("thread_id", "")
    status = run.get("status")
    display_topic = html.escape(st.session_state.last_topic or "Untitled case")

    st.divider()

    stamp_class = "pending" if status == "interrupted" else "approved"
    stamp_text = "Awaiting Review" if status == "interrupted" else "Closed"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div class="case-eyebrow">Case File</div>
                <div class="case-title" style="font-size: 1.9rem;">{display_topic}</div>
            </div>
            <span class="case-stamp {stamp_class}">{stamp_text}</span>
        </div>
        <div class="thread-tag">Case ID: <code>{thread_id}</code> — save this to retrieve the case later</div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # PAUSED: human review needed
    # ------------------------------------------------------------------
    if status == "interrupted":
        pending = run.get("pending_review", {})
        st.write("")

        with st.container(border=True):
            st.markdown('<span class="section-label">Human Review Needed</span>', unsafe_allow_html=True)
            st.caption(f"Revision round {pending.get('attempt', 1)} of 3")

            st.markdown("**Critic's feedback:**")
            st.markdown(pending.get("critic_feedback", "_No critic feedback available._"))

            st.markdown("**Draft report** (edit below if you want to tweak it before approving):")
            edited_text = st.text_area(
                "Draft report",
                value=pending.get("report", ""),
                height=350,
                label_visibility="collapsed",
                key=f"draft_edit_{thread_id}_{pending.get('attempt', 0)}",
            )

            revision_notes = st.text_area(
                "Notes for the writer (only used if you request a revision)",
                placeholder="e.g. Add more recent statistics on adoption rates, and tighten the conclusion.",
                key=f"revision_notes_{thread_id}_{pending.get('attempt', 0)}",
            )

            col_approve, col_revise = st.columns(2)

            with col_approve:
                if st.button("✅ Approve & Finalize", use_container_width=True, type="primary"):
                    with st.spinner("Finalizing the report..."):
                        try:
                            # Only send edited_report if the human actually changed it.
                            edited_report = edited_text if edited_text != pending.get("report", "") else None
                            new_run = resume_research(thread_id, action="approve", edited_report=edited_report)
                            st.session_state.run = new_run
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Resume failed: {e}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not reach backend: {e}")

            with col_revise:
                if st.button("🔁 Send Back for Revision", use_container_width=True):
                    with st.spinner("Sending back to the writer..."):
                        try:
                            new_run = resume_research(
                                thread_id,
                                action="revise",
                                comments=revision_notes or "Human reviewer requested changes, no specific notes given.",
                            )
                            st.session_state.run = new_run
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Resume failed: {e}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not reach backend: {e}")

    # ------------------------------------------------------------------
    # COMPLETED: final result
    # ------------------------------------------------------------------
    elif status == "completed":
        result = run.get("result", {}) or {}

        badge = "✅ Approved" if result.get("is_approved") else "⚠️ Ended without approval (max revisions reached)"
        st.caption(f"{badge} · {result.get('attempts', 0)} revision round(s)")

        tab_report, tab_feedback, tab_search, tab_scraped = st.tabs(
            ["📄 Report", "🧐 Critic's Notes", "🔍 Search Log", "📚 Source Extract"]
        )

        with tab_report:
            with st.container(border=True):
                st.markdown('<span class="section-label">Final Report</span>', unsafe_allow_html=True)
                st.markdown(result.get("report") or "_No report generated._")
                st.download_button(
                    "Download as Markdown",
                    data=result.get("report", ""),
                    file_name=f"{st.session_state.last_topic.replace(' ', '_') or 'report'}_report.md",
                    mime="text/markdown",
                )

        with tab_feedback:
            with st.container(border=True):
                st.markdown('<span class="section-label">Critic Review</span>', unsafe_allow_html=True)
                st.markdown(result.get("feedback") or "_No feedback generated._")

        with tab_search:
            with st.container(border=True):
                st.markdown('<span class="section-label">Source URLs</span>', unsafe_allow_html=True)
                urls = result.get("urls") or []
                if urls:
                    for url in urls:
                        st.markdown(f"- {url}")
                else:
                    st.text("No search results.")

        with tab_scraped:
            with st.container(border=True):
                st.markdown('<span class="section-label">Scraped Source Content</span>', unsafe_allow_html=True)
                scraped = result.get("scraped_content") or []
                if scraped:
                    for i, chunk in enumerate(scraped, start=1):
                        st.markdown(f"**Source {i}**")
                        st.text(chunk)
                        st.markdown("---")
                else:
                    st.text("No scraped content.")

else:
    st.divider()
    with st.container(border=True):
        st.markdown('<span class="section-label">No Active Case</span>', unsafe_allow_html=True)
        st.write("Enter a topic above and open a case to start the pipeline.")