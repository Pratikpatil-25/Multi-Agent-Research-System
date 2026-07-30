# 🔍 Multi-Agent Research Assistant

---

## 🧠 Project Overview

**Multi-Agent Research Assistant** is an AI-powered research automation system that performs end-to-end web research using a multi-agent architecture.

The system accepts a research topic from the user, searches the web for relevant sources, extracts content from multiple websites, generates a structured research report, critiques the report for gaps or inaccuracies, and — before anything is finalized — pauses for a **human reviewer** to approve the report or send it back for another revision round.

The application combines **Agentic AI**, **LangGraph**, **Mistral AI**, **FastAPI**, and **Streamlit** to create an automated, human-supervised research workflow.

Website : https://airesearchsys.streamlit.app/

---

<p align="center">
  <img src="assets/ui.png" width="1000">
</p>

---

<p align="center">
  <img src="assets/report.png" width="1000">
</p>

---

<p align="center">
  <img src="assets/critic.png" width="1000">
</p>

---

## 🚀 Problem Statement

Conducting research manually often involves:

- Searching multiple sources
- Reading numerous articles
- Extracting relevant information
- Writing summaries
- Verifying report quality
- Deciding whether the result is actually good enough to use

This project automates the search, reading, writing, and critique steps using multiple AI agents that collaborate to produce a research report — while keeping a human in charge of the final sign-off, since fully-automated research pipelines can still confidently produce incomplete or subtly wrong reports.

---

## 🤖 Multi-Agent Workflow

The system is built as a **LangGraph** state machine rather than a single linear chain. The Writer and Critic can loop through multiple revision rounds, and the graph pauses for human input before anything is considered final:

```text
User Research Query
          │
          ▼
 ┌─────────────────┐
 │ Search Agent    │
 │ (Tavily Search) │
 └─────────────────┘
          │
          ▼
 ┌─────────────────┐
 │ Scraping Agent  │   (runs once per URL, in parallel)
 │ (BeautifulSoup) │
 └─────────────────┘
          │
          ▼
 ┌─────────────────┐
 │  Writer Agent   │◄────────────────┐
 │ (LLM + tools)   │                 │
 └─────────────────┘                 │
          │                          │
          ▼                          │
 ┌─────────────────┐                 │
 │  Critic Agent   │                 │
 │ (scores report) │                 │
 └─────────────────┘                 │
          │                          │
          ▼                          │
 ┌─────────────────────┐             │
 │   Human Review      │             │
 │ approve / revise     │────────────┘
 └─────────────────────┘   (revise -> back to Writer,
          │                 up to 3 rounds total)
          ▼
   Final Research Report
```

Key behavior:

- The **Critic** no longer has the final say — its score and notes are shown to the human as advisory input.
- The **human reviewer** decides: approve the report as-is, approve an edited version, or send it back with notes for another Writer/Critic pass.
- The loop is capped at **3 attempts** — if no approval happens by then, the graph ends anyway and returns the best available draft, flagged as not approved.

---

## ⚙️ Architecture

```text
                    ┌────────────────────┐
                    │    User Query      │
                    └─────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │    FastAPI Server   │
                   └─────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       Search Agent           │
              │     Tavily Search Tool       │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │      Scraping Agent          │
              │     BeautifulSoup Tool       │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       Writer Agent           │
              │   LLM + optional re-search    │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       Critic Agent           │
              │      Scores the draft        │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   Human-in-the-Loop Review   │
              │  approve / edit / send back  │
              └──────────────┬───────────────┘
                     approve │  revise (loops to Writer, max 3x)
                             ▼
                    Final Research Report
```

The graph is compiled with a **LangGraph checkpointer**, which is what makes the pause-and-resume behavior possible — each research run is tied to a `thread_id`, and the graph's exact execution state is persisted at the human-review pause point until a decision comes back through the API.

---

## 🧩 Agents

### 1️⃣ Search Agent

Responsible for:

- Understanding the research topic
- Searching relevant web sources via the `web_search` tool
- Returning a list of candidate source URLs

**Tool Used:** Tavily Search API

---

### 2️⃣ Scraping Agent

Responsible for:

- Visiting each retrieved URL (one parallel branch per URL)
- Extracting and cleaning article content
- Producing structured research notes for the Writer

**Tool Used:** BeautifulSoup

---

### 3️⃣ Writer Agent

Responsible for:

- Synthesizing the search results and scraped notes into a structured report (Introduction, Key Findings, Conclusion, Sources)
- Optionally calling the search tool again mid-draft if it decides it needs more information
- Rewriting the report using reviewer feedback (from the Critic and/or the human) on subsequent rounds

---

### 4️⃣ Critic Agent

Responsible for:

- Scoring the draft on accuracy, completeness, clarity, and source usage
- Producing structured, actionable feedback (strengths / issues / recommendations)
- Passing that review on to the human reviewer rather than approving/rejecting on its own

---

### 5️⃣ Human Reviewer (Human-in-the-Loop)

Responsible for:

- Reading the draft report and the Critic's notes
- Either **approving** the report (optionally editing the text first) or **requesting a revision** with specific comments
- Having the final word — the pipeline will not mark a report "approved" without this step

This is implemented with LangGraph's `interrupt()` / `Command(resume=...)` mechanism: the graph genuinely pauses mid-execution and waits, across separate API calls, for the human's decision.

---

## 🛠 Features

- Multi-Agent Architecture (LangGraph state machine, not a linear chain)
- Tavily-powered Web Search
- Website Scraping with BeautifulSoup (parallel, one branch per URL)
- Automated Research Workflow
- Structured Report Generation
- AI-based Report Critiquing
- **Human-in-the-Loop approval step** before any report is finalized
- **Iterative revision loop** (Writer ↔ Critic ↔ Human, up to 3 rounds)
- FastAPI Backend with pause/resume endpoints
- Streamlit Frontend with an in-app review panel (approve / edit / send back)
- Cloud Deployment
- Configurable Parameters via YAML

---

## 🌐 Tech Stack

| Component | Technology |
|------------|------------|
| LLM | Mistral Small Latest |
| Agent Framework | LangChain |
| Workflow / Orchestration | LangGraph (StateGraph + checkpointing) |
| Human-in-the-Loop | LangGraph `interrupt()` / `Command(resume=...)` |
| Search Tool | Tavily |
| Web Scraping | BeautifulSoup |
| Backend | FastAPI |
| Frontend | Streamlit |
| Deployment | Render |
| Deployment | Streamlit Cloud |
| Configuration | YAML |
| Environment Management | Python Dotenv |

---

## 📁 Project Structure

```text
Multi-Agent-Research-Assistant
│
├── src
│   │
│   ├── client
│   │   ├── .streamlit
│   │   │   └── config.toml
│   │   │
│   │   ├── app.py
│   │   └── config.py
│   │
│   └── server
│       │
│       ├── components
│       │   ├── nodes.py        # LangGraph node functions (search, scrape,
│       │   │                   # writer, critic, human_review, routers)
│       │   ├── tools.py        # web_search / scrape_url tool implementations
│       │   └── agents.py       # legacy create_agent/LCEL-chain approach,
│       │                       # kept for reference - not used by graph.py
│       │
│       ├── logger
│       │   └── __init__.py
│       │
│       ├── utils
│       │   ├── common.py
│       │   └── __init__.py
│       │
│       ├── state.py            # shared graph State (TypedDict)
│       ├── graph.py            # builds & compiles the StateGraph + checkpointer
│       ├── config.py
│       ├── params.yaml
│       ├── main.py             # FastAPI app: /research + /research/{id}/resume
│       └── requirements.txt
│
├── .gitignore
├── LICENSE
├── README.md
└── template.py
```

---

## 🔧 Environment Variables

Create a `.env` file inside the server directory.

```env
MISTRAL_API_KEY=your_mistral_api_key

TAVILY_API_KEY=your_tavily_api_key
```

---

## ⚡ Quick Setup

### Clone Repository

```bash
git clone https://github.com/your-username/Multi-Agent-Research-Assistant.git

cd Multi-Agent-Research-Assistant
```

---

### Create Virtual Environment

```bash
uv venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

---

### Install Backend Dependencies

```bash
cd src/server

uv pip install -r requirements.txt
```

---

### Run FastAPI Backend

```bash
uvicorn main:app --reload --port 8000
```

Backend will run at:

```text
http://localhost:8000
```

Swagger Documentation:

```text
http://localhost:8000/docs
```

---

### Run Streamlit Frontend

```bash
cd src/client

streamlit run app.py
```

Frontend will run at:

```text
http://localhost:8501
```

---

## 📡 API Endpoints

A research run now spans two calls: one to start it, and one (or more) to
resume it after a human reviews the draft. Every response carries a
`thread_id` that ties these calls together.

### 1. Start a research run

```http
POST /research
```

Request Body:

```json
{
  "topic": "Future of Artificial Intelligence in Healthcare"
}
```

Response (paused for review):

```json
{
  "thread_id": "b3f1c2...",
  "status": "interrupted",
  "pending_review": {
    "message": "Please review this report before it's finalized.",
    "topic": "Future of Artificial Intelligence in Healthcare",
    "report": "Generated draft report...",
    "critic_feedback": "Status: REJECTED\nScore: 68\n...",
    "attempt": 1
  }
}
```

Response (finished immediately, no further review needed):

```json
{
  "thread_id": "b3f1c2...",
  "status": "completed",
  "result": {
    "topic": "Future of Artificial Intelligence in Healthcare",
    "urls": ["https://...", "https://..."],
    "scraped_content": ["Source: https://...\n..."],
    "report": "Final approved report...",
    "feedback": "Status: APPROVED\nScore: 91\n...",
    "is_approved": true,
    "attempts": 1
  }
}
```

---

### 2. Resume after human review

```http
POST /research/{thread_id}/resume
```

Request Body (approve):

```json
{
  "action": "approve",
  "edited_report": "optional - only send this if you changed the text"
}
```

Request Body (request a revision):

```json
{
  "action": "revise",
  "comments": "Add more recent statistics and expand the conclusion."
}
```

Response shape is identical to `POST /research` — either `status: "interrupted"` (another revision round is needed) or `status: "completed"`.

---

### 3. Retrieve a completed case

```http
GET /research/{thread_id}
```

Only works once a case has finished (`status: "completed"`) — the backend stores completed results in memory, keyed by `thread_id`. Cases still awaiting human review aren't retrievable this way; keep the browser tab open until you approve or the run completes.

---

## ⚙️ Configuration

Project parameters can be modified from:

```text
src/server/params.yaml
```

Example:

```yaml
llm:
  temperature: 0.7

search:
  max_results: 5

scraping:
  max_pages: 10
```

This allows experimentation without modifying source code. The maximum number of Writer/Critic/Human revision rounds (currently 3) is set in `nodes.py`'s `should_stop_looping` router, not in `params.yaml`.

---

## ⚠️ Known Limitations

- **Checkpointer is in-memory (`MemorySaver`)** — paused runs live only in the running server process's memory. A server restart, or running with multiple uvicorn workers, will lose in-progress reviews. Swap in a persistent checkpointer (e.g. `SqliteSaver` or a Postgres-backed one) before relying on this in production.
- **Pending reviews aren't independently retrievable** — only completed runs can be fetched via `GET /research/{thread_id}`. If a reviewer closes the browser mid-review, that run currently has to be handled by keeping the original session/tab open rather than reloading.

---

## 📚 Learning Outcomes

This project demonstrates:

- Agentic AI Systems
- Multi-Agent Collaboration
- LangGraph state machines (nodes, conditional edges, `Send` for parallel branches)
- Human-in-the-Loop workflows (`interrupt()` / `Command(resume=...)`, checkpointing)
- Tool Calling
- ReAct Agents
- Web Search Integration
- Web Scraping Pipelines
- FastAPI Development (stateful, multi-step API design)
- Streamlit Applications (multi-step UI state)
- Cloud Deployment

---

## 👨‍💻 Author

**Pratik Patil**

---

## 📄 License

This project is licensed under the MIT License.

---

## ⭐ If you found this project useful

Consider giving the repository a **star ⭐** to support the project and future improvements.
