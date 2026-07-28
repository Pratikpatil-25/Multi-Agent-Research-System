"""
Streamlit client for the Multi-Agent Research System.

Connects to the FastAPI backend (server/main.py) using the API_URL
defined in client/config.py.

Place this file at: client/app.py
(and .streamlit/config.toml alongside it, for the theme colors)
Run with: streamlit run app.py
"""

import html
from urllib.parse import quote

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
# Fraunces (display serif, characterful) for headings,
# IBM Plex Sans for body copy, IBM Plex Mono for stage tags / labels
# — a "field dossier" register that matches a pipeline of agents
# building a file step by step.
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


def run_research(topic: str) -> dict:
    """
    Calls the backend's POST /research endpoint and returns the parsed JSON response.
    Raises requests.exceptions.RequestException on network errors,
    or ValueError with the backend's error detail on a non-200 response.
    """
    resp = requests.post(
        f"{API_URL}/research",
        json={"topic": topic},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ValueError(detail)
    return resp.json()


def fetch_past_research(topic: str) -> dict:
    """Calls GET /research/{topic}. Raises ValueError with a friendly message on failure."""
    resp = requests.get(f"{API_URL}/research/{quote(topic, safe='')}", timeout=15)
    if resp.status_code == 404:
        raise ValueError("No file exists yet for that topic.")
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ValueError(detail)
    return resp.json()


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
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
    st.caption("Pulls a previously completed file without re-running the pipeline.")
    lookup_topic = st.text_input("Topic to retrieve", key="lookup_topic")
    if st.button("Fetch", use_container_width=True, key="fetch_btn"):
        if not lookup_topic.strip():
            st.warning("Enter a topic to look up.")
        else:
            try:
                with st.spinner("Searching the archive..."):
                    result = fetch_past_research(lookup_topic.strip())
                st.session_state.result = result
                st.session_state.last_topic = lookup_topic.strip()
                st.success("File loaded from the archive.")
            except ValueError as e:
                st.warning(str(e))
            except requests.exceptions.RequestException as e:
                st.error(f"Could not reach backend: {e}")

    st.divider()
    st.caption(
        "Every case runs through four agents in order: **Search** finds sources, "
        "**Read** extracts the most relevant one, **Write** drafts the report, "
        "**Critique** reviews it for gaps."
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
        Dispatch a topic below. Four agents build the file in sequence, start to finish.
    </div>
    <div class="stage-line">01 Search &nbsp;→&nbsp; 02 Read &nbsp;→&nbsp; 03 Write &nbsp;→&nbsp; 04 Critique</div>
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
                result = run_research(topic.strip())
                st.session_state.result = result
                st.session_state.last_topic = topic.strip()
            except ValueError as e:
                st.error(f"The pipeline failed: {e}")
            except requests.exceptions.RequestException as e:
                st.error(
                    f"Could not reach the backend at `{API_URL}`. "
                    f"Start the FastAPI server and try again.\n\nDetails: {e}"
                )

# ------------------------------------------------------------------
# Results display
# ------------------------------------------------------------------
if st.session_state.result:
    result = st.session_state.result
    display_topic = html.escape(result.get("topic", st.session_state.last_topic))

    st.divider()
    st.markdown(
        f"""
        <div class="case-eyebrow">Case File</div>
        <div class="case-title" style="font-size: 1.9rem;">{display_topic}</div>
        """,
        unsafe_allow_html=True,
    )

    tab_report, tab_feedback, tab_search, tab_scraped = st.tabs(
        ["📄 Report", "🧐 Critic's Notes", "🔍 Search Log", "📚 Source Extract"]
    )

    with tab_report:
        with st.container(border=True):
            st.markdown('<span class="section-label">Final Report</span>', unsafe_allow_html=True)
            st.markdown(result.get("report", "_No report generated._"))
            st.download_button(
                "Download as Markdown",
                data=result.get("report", ""),
                file_name=f"{st.session_state.last_topic.replace(' ', '_')}_report.md",
                mime="text/markdown",
            )

    with tab_feedback:
        with st.container(border=True):
            st.markdown('<span class="section-label">Critic Review</span>', unsafe_allow_html=True)
            st.markdown(result.get("feedback", "_No feedback generated._"))

    with tab_search:
        with st.container(border=True):
            st.markdown('<span class="section-label">Raw Search Results</span>', unsafe_allow_html=True)
            st.text(result.get("search_results", "_No search results._"))

    with tab_scraped:
        with st.container(border=True):
            st.markdown('<span class="section-label">Scraped Source Content</span>', unsafe_allow_html=True)
            st.text(result.get("scraped_content", "_No scraped content._"))

else:
    st.divider()
    with st.container(border=True):
        st.markdown('<span class="section-label">No Active Case</span>', unsafe_allow_html=True)
        st.write("Enter a topic above and open a case to start the pipeline.")