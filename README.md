# 🔎 Autonomous Tech & Market Research Agent (Decoupled Microservice Architecture)

A production-grade, **100% asynchronous, decoupled AI agent microservice** built with Python. Instead of blocking client web applications with long-running LLM and web-search loops, this system separates the user-facing client from an event-driven background agent worker using a message broker, persistent state storage, and full LLM observability.

---

## 🏗️ System Architecture

```text
┌─────────────────────────┐       POST /research (202 Accepted)       ┌─────────────────────────┐
│   Client Web App        │ ────────────────────────────────────────► │   Agent Gateway API     │
│   (Streamlit Cloud)     │                                           │   (FastAPI on Render)   │
│                         │ ◄────────── Poll GET /tasks/{id} ──────── │                         │
└─────────────────────────┘                                           └───────────┬─────────────┘
                                                                                  │
                                                                            Push Task ID
                                                                                  │
                                                                                  ▼
┌─────────────────────────┐       Save State & JSON Report            ┌─────────────────────────┐
│   PostgreSQL Database   │ ◄──────────────────────────────────────── │   Background Worker     │
│   (Supabase)            │                                           │   (Celery + Upstash)    │
└─────────────────────────┘                                           └───────────┬─────────────┘
                                                                                  │
                                                                       Execute 3-Node Graph
                                                                                  │
                                                                                  ▼
┌─────────────────────────┐       Trace Latency & Token Usage         ┌─────────────────────────┐
│   Observability         │ ◄──────────────────────────────────────── │   LangGraph Pipeline    │
│   (LangSmith Tracing)   │                                           │   Planner ──► Tavily    │
└─────────────────────────┘                                           │   ──► Groq Analyst      │
                                                                      └─────────────────────────┘
```

### How It Works
1. **Instant Non-Blocking API (`POST /research`):** Validates the `X-API-Key` header, creates a task record (`QUEUED`) in Supabase PostgreSQL, pushes the `task_id` to Upstash Redis, and returns an immediate `202 Accepted` response in milliseconds.
2. **Asynchronous Worker Execution:** A dedicated Celery worker pulls jobs from Redis, transitions state (`QUEUED` → `RUNNING` → `COMPLETED`), and handles automatic retries on transient network or API failures.
3. **Stateful Multi-Step Agent (LangGraph):**
   * **Planner Node:** Generates targeted search queries using Groq (`openai/gpt-oss-120b`) in strict JSON mode.
   * **Researcher Node:** Fetches live web context and verified source URLs via the Tavily Search API.
   * **Analyst Node:** Synthesizes findings into a Pydantic-enforced `ResearchReport` schema.
4. **Zero-Coupling Client:** The Streamlit frontend has zero direct access to LLMs, search tools, or the database—it communicates exclusively over authenticated REST endpoints.
5. **Production Observability:** Every LangGraph node execution, prompt, latency breakdown, and token count is traced end-to-end in LangSmith.

---

## 🛠️ Tech Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Agent Orchestration** | **LangGraph** & **Pydantic** | Stateful multi-node workflow & strict structured output validation |
| **LLM Inference** | **Groq API** | High-speed JSON-mode reasoning and synthesis |
| **Web Search Tool** | **Tavily API** | Real-time web retrieval and source extraction |
| **API Gateway** | **FastAPI** & **Uvicorn** | REST endpoints, API key auth, and OpenAPI docs |
| **Task Queue & Broker** | **Celery** & **Upstash Redis** | Asynchronous job queuing and retry management |
| **Database** | **Supabase (PostgreSQL)** & **SQLAlchemy** | Persistent task lifecycle tracking and report storage |
| **Client UI** | **Streamlit** | Decoupled frontend polling live task states |
| **Observability** | **LangSmith** | End-to-end step tracing, latency, and token monitoring |
| **Container & Hosting** | **Docker**, **Render**, **Streamlit Cloud** | Containerized microservice deployment |

---

## 📁 Project Structure

```text
Production_AI_Agent_Deployment/
├── agent_service/               # Independent Agent Microservice (Dockerized)
│   ├── app/
│   │   ├── main.py              # FastAPI endpoints (/health, /research, /tasks/{id})
│   │   ├── worker.py            # Celery worker & retry logic
│   │   ├── graph.py             # LangGraph nodes (Planner -> Researcher -> Analyst)
│   │   ├── schemas.py           # Pydantic request/response & report schemas
│   │   └── database.py          # SQLAlchemy models & Supabase connection
│   ├── Dockerfile               # Container definition
│   ├── start.sh                 # Entrypoint running Celery worker + Uvicorn
│   └── requirements.txt
│
├── client_app/                  # Decoupled User-Facing Application
│   ├── app.py                   # Streamlit UI (REST API consumer only)
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Live Deployments & API Usage

* **Client Web App:** `https://<your-streamlit-url>.streamlit.app`
* **Agent Microservice API:** `https://<your-render-url>.onrender.com`
* **Interactive API Docs:** `https://<your-render-url>.onrender.com/docs`

### Programmatic API Example (Python)

Any external application can trigger the agent microservice directly via HTTP:

```python
import time
import requests

BASE_URL = "https://<your-render-url>.onrender.com"
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "your-agent-api-key"
}

# 1. Trigger background research task
resp = requests.post(
    f"{BASE_URL}/research",
    json={"topic": "Groq LPU architecture vs NVIDIA H100"},
    headers=HEADERS
)
task_id = resp.json()["task_id"]

# 2. Poll until completion
while True:
    status_data = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=HEADERS).json()
    if status_data["status"] in ("COMPLETED", "FAILED"):
        print(status_data)
        break
    time.sleep(3)
```

---

## 💻 Local Development Setup (Windows PowerShell)

1. **Clone & Create Virtual Environment:**
   ```powershell
   git clone [https://github.com/](https://github.com/)<your-username>/Production_AI_Agent_Deployment.git
   cd Production_AI_Agent_Deployment
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r agent_service\requirements.txt
   pip install -r client_app\requirements.txt
   ```

2. **Configure Environment Variables:**
   Create `agent_service\.env`:
   ```env
   GROQ_API_KEY=your_groq_key
   TAVILY_API_KEY=your_tavily_key
   REDIS_URL=rediss://default:password@endpoint.upstash.io:6379
   DATABASE_URL=postgresql://postgres.user:password@pooler.supabase.com:6543/postgres
   AGENT_API_KEY=super-secret-agent-key-123

   # Observability (LangSmith)
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_ENDPOINT=[https://api.smith.langchain.com](https://api.smith.langchain.com)
   LANGCHAIN_API_KEY=your_langsmith_key
   LANGCHAIN_PROJECT=autonomous-research-agent
   ```

3. **Run All 3 Decoupled Processes (3 Separate Terminals):**
   * **Terminal 1 (Celery Worker):**
     ```powershell
     celery -A agent_service.app.worker.celery_app worker --loglevel=info --pool=solo
     ```
   * **Terminal 2 (FastAPI Gateway):**
     ```powershell
     uvicorn agent_service.app.main:app --port 8000
     ```
   * **Terminal 3 (Streamlit Client):**
     ```powershell
     streamlit run client_app\app.py
     ```