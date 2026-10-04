# Prodapt AI Operations Center

Multi-agent AI platform for telecom customer support. Automates billing dispute resolution, network diagnostics, policy lookups, and SQL analytics using four coordinated frameworks.

---

## Architecture

```
User Query
    │
    ▼
LangGraph Supervisor          ← main orchestrator
    │
    ├── PolicyRAG             ← LlamaIndex Document RAG (policy/SLA documents)
    ├── NetworkAnalytics      ← LlamaIndex Semantic SQL (database metrics)
    ├── NetworkDiagnosticsADK ← Google ADK A2A service (port 8001)
    └── BillingResolutionADK  ← Google ADK A2A service (port 8002)
    │
    ▼
accumulated agent_context
    │
    ▼
CrewAI Communications Layer   ← customer communication only
    ├── Communications Specialist  (drafts customer response from agent_context)
    └── Quality Reviewer           (audits accuracy, returns final text)
    │
    ▼
Final Customer Response
```

**LangGraph** makes all routing decisions. **CrewAI** only handles the final customer-facing communication — it never calls the specialist agents directly.

---

## Components

| Component | Framework | Location | Port |
|---|---|---|---|
| Policy & SLA document Q&A | LlamaIndex Document RAG | `llamaindex_rag/document_rag.py` | — |
| Network metrics & SQL analytics | LlamaIndex Semantic SQL | `llamaindex_rag/sql_semantic_search.py` | — |
| Live cell tower diagnostics | Google ADK (A2A) | `adk-services/network_diagnostics/` | 8001 |
| Live billing account & credits | Google ADK (A2A) | `adk-services/billing_resolution/` | 8002 |
| Supervisor orchestration | LangGraph | `orchestration/graph.py` | — |
| Customer communication | CrewAI | `orchestration/crew_nodes.py` | — |
| Operations dashboard | Streamlit | `ui/app.py` | 8501 |

**Model used throughout:** `anthropic/claude-sonnet-4-5-20250929` via ANTHROPIC_API_KEY.

---

## Project Structure

```
Prodapt_Phase_2/
├── .env                              # API keys — never commit
├── requirements.txt
├── README.md
│
├── adk-services/
│   ├── billing_resolution/           # ADK agent, LiteLLM, SQL tools (port 8002)
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── a2a_server.py
│   └── network_diagnostics/          # ADK agent, LiteLLM, SQL tools (port 8001)
│       ├── agent.py
│       ├── tools.py
│       └── a2a_server.py
│
├── llamaindex_rag/
│   ├── document_rag.py               # Vector RAG over 6 policy .txt files
│   └── sql_semantic_search.py        # Natural language → SQL over telecom_ops.db
│
├── orchestration/
│   ├── state.py                      # LangGraph AgentState (messages, trace, agent_context)
│   ├── graph.py                      # Supervisor node, worker nodes, run_telecom_assistant()
│   ├── adk_remote_client.py          # Async A2A client for ports 8001 & 8002
│   ├── crew_nodes.py                 # CrewAI 2-agent sequential crew
│   ├── test_crew_integration.py      # Unit + live CrewAI tests
│   └── test_langgraph_paths.py       # LangGraph routing tests
│
├── ui/
│   └── app.py                        # Streamlit dashboard
│
├── data/
│   ├── telecom_ops.db                # SQLite database
│   ├── documents/                    # 6 policy .txt files (RAG source)
│   ├── vector_index/                 # LlamaIndex document embeddings (auto-built)
│   └── semantic_sql_index/           # LlamaIndex SQL schema index (auto-built)
│
└── sql/
    ├── 01_schema.sql
    └── 02_seed_data.sql
```

---

## Setup

### 1. Prerequisites

- Python 3.13
- API keys for Anthropic, Google, and NVIDIA

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

> **Dependency note:** `google-api-core` is pinned to `2.34.0` to avoid an OpenTelemetry version conflict with Google ADK `2.10.0`. Do not upgrade it independently.

### 3. Configure environment

Create `.env` in the project root:

```dotenv
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
NVIDIA_API_KEY=your_key_here
```

---

## Running the System

Open **three separate PowerShell terminals**, each from `D:\Prodapt_Phase_2`.

### Terminal 1 — Billing Resolution (port 8002)

```powershell
cd adk-services
uvicorn billing_resolution.a2a_server:app --host 0.0.0.0 --port 8002
```

### Terminal 2 — Network Diagnostics (port 8001)

```powershell
cd adk-services
uvicorn network_diagnostics.a2a_server:app --host 0.0.0.0 --port 8001
```

### Terminal 3 — Streamlit Dashboard

```powershell
streamlit run ui/app.py
```

Opens at **http://localhost:8501**.

> The ADK services are optional for RAG and SQL queries. If offline, those nodes return a graceful unavailability message and CrewAI still produces a response.

---

## Verify ADK Services

```powershell
curl http://localhost:8001/.well-known/agent-card.json   # Network Diagnostics
curl http://localhost:8002/.well-known/agent-card.json   # Billing Resolution
```

Both should return HTTP 200 with the agent skill definitions.

---

## Testing

```powershell
# CrewAI unit + live integration tests
python orchestration/test_crew_integration.py

# LangGraph routing tests (all 4 specialist paths)
python orchestration/test_langgraph_paths.py

# Interactive CLI (alternative to Streamlit)
python orchestration/graph.py
```

---

## Database

SQLite at `data/telecom_ops.db`. Initialized from:
- `sql/01_schema.sql` — schema for towers, outages, billing accounts, charges, credits, disputes
- `sql/02_seed_data.sql` — synthetic customer and network data

**Billing credit policy enforced in code:**
- Credits ≤ $50 → status `APPLIED` immediately
- Credits > $50 → status `PENDING_APPROVAL`, requires manual review