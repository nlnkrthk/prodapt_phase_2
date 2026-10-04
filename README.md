# Telecom Agentic AI Operations Center (Phase 2)

An intelligent, multi-agent operations platform for telecommunications providers. This platform automates customer support, billing dispute resolution, network diagnostics, and policy exploration using **Google Agent Development Kit (ADK)**, the **Agent-to-Agent (A2A) protocol**, and **LlamaIndex RAG**.


## Core Components

### 1. Billing Resolution Service (Port 8002)
- **Framework:** Google ADK `2.10.0` exposed via `to_a2a` on `http://localhost:8002`.
- **Model:** Claude Sonnet (`anthropic/claude-sonnet-4-5-20250929`) orchestrated via `LiteLLM`.
- **Location:** `adk-services/billing_resolution/`
- **Capabilities:**
  - `lookup_billing_account(customer_id)`: Fetches account details, balance, and recent charges.
  - `check_duplicate_charges(customer_id)`: Identifies duplicate transactions flagged with `is_duplicate_flag = 1`.
  - `apply_billing_credit(customer_id, amount, reason)`:
    - **Policy Rule:** Credits **≤ $50.00** are automatically marked as `APPLIED` and immediately deducted from the customer's balance.
    - **Policy Rule:** Credits **> $50.00** are saved with status `PENDING_APPROVAL` and require manual review.

### 2. Network Diagnostics Service (Port 8001)
- **Framework:** Google ADK `2.10.0` exposed via `to_a2a` on `http://localhost:8001`.
- **Model:** Claude Sonnet (`anthropic/claude-sonnet-4-5-20250929`) orchestrated via `LiteLLM`.
- **Location:** `adk-services/network_diagnostics/`
- **Capabilities:**
  - `check_tower_status(tower_id)`: Inspects operational health, congestion, and alerts for a cell tower.
  - `run_connectivity_diagnostics(customer_id)`: Correlates user connection issues with connected towers.
  - `get_regional_network_summary(region)`: Reports uptime, throughput, and active incidents across regions.

### 3. LlamaIndex Document RAG
- **Script:** `llamaindex_rag/document_rag.py`
- **Purpose:** Answers questions on refund limits, customer dispute workflows, roaming terms, and SLA response times from ingested telecom policy documents using vector embeddings.

### 4. LlamaIndex Semantic SQL
- **Script:** `llamaindex_rag/sql_semantic_search.py`
- **Purpose:** Translates high-level natural language analytics questions into SQL queries across the network metrics and tower performance logs.

### 5. LangGraph Supervisor & Orchestrator
- **Script:** `orchestration/graph.py` & `orchestration/state.py`
- **Purpose:** Acts as the primary supervisor/orchestrator coordinating all specialist worker nodes (`PolicyRAG`, `NetworkAnalytics`, `NetworkDiagnosticsADK`, `BillingResolutionADK`), accumulating findings into `agent_context`, and routing to the customer communications layer before completion.

### 6. CrewAI Customer Communications Layer
- **Script:** `orchestration/crew_nodes.py`
- **Model:** Anthropic Claude (`anthropic/claude-sonnet-4-5-20250929`) configured via the existing `ANTHROPIC_API_KEY` in `.env`.
- **Purpose:** Sequential two-agent crew responsible solely for professional, customer-ready communication:
  1. **Customer Communications Specialist:** Converts technical findings and `agent_context` into an empathetic, factual customer response draft.
  2. **Quality Reviewer:** Cross-checks the draft against `agent_context` to guarantee 100% factual accuracy (verifying amounts and pending vs applied statuses) and returns ONLY the finalized customer response.

```
USER QUERY
    │
    ▼
LANGGRAPH SUPERVISOR (orchestration/graph.py)
    │
    ├──► PolicyRAG (LlamaIndex Document RAG)
    ├──► NetworkAnalytics (LlamaIndex Semantic SQL)
    ├──► NetworkDiagnosticsADK (Google ADK Port 8001)
    └──► BillingResolutionADK (Google ADK Port 8002)
    │
    ▼
accumulated agent_context
    │
    ▼
CREWAI COMMUNICATIONS LAYER (orchestration/crew_nodes.py)
    │
    ▼
Communications Specialist (Drafts customer-facing reply)
    │
    ▼
Quality Reviewer (Audits against context & outputs final text)
    │
    ▼
FINAL CUSTOMER-READY RESPONSE
```

---

## Database Design

The relational backend is SQLite, stored at:
```
data/telecom_ops.db
```

Initialized with scripts located in `sql/`:
- `sql/01_schema.sql`: Table definitions and constraints.
- `sql/02_seed_data.sql`: Realistic synthetic data for customers, accounts, charges, and cell towers.

### Key Billing Tables
| Table | Description |
|---|---|
| `billing_accounts` | Customer account IDs, status, balance, and currency. |
| `billing_charges` | Historical and current charges, invoice status, and duplicate flags. |
| `billing_credits` | Credits issued, amount, reason, and approval status (`APPLIED` / `PENDING_APPROVAL`). |
| `billing_disputes` | Formal dispute cases filed by customers. |

---

## Prerequisites & Environment Configuration

### Python & System Requirements
- **Python Version:** Python 3.13
- **Network / SSL:** Corporate proxy environments are supported out of the box via `truststore`.

### Critical Dependency Alignment

Google ADK `2.10.0` imposes specific constraints on OpenTelemetry:
- Requires `opentelemetry-api >= 1.39, <= 1.42.1` and `opentelemetry-sdk >= 1.39, <= 1.42.1`.
- Newer versions of `google-api-core` (≥ 2.36) require `opentelemetry-api >= 1.44.0`, which creates a version conflict with ADK.
- **Solution:** We pin `google-api-core==2.34.0`, which does not impose the higher OpenTelemetry constraint and is fully supported by `a2a-sdk >= 1.26.0`.

### Environment Variables (`.env`)
Create a `.env` file in the root project folder:
```dotenv
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key
NVIDIA_API_KEY=your_nvidia_api_key
```

---

## How to Run the Services

### Starting the Services

Open PowerShell in `D:\Prodapt_Phase_2\adk-services`:

#### 1. Start the Billing Resolution Service (Port 8002)
```powershell
cd D:\Prodapt_Phase_2\adk-services
uvicorn billing_resolution.a2a_server:app --host 0.0.0.0 --port 8002
```

#### 2. Start the Network Diagnostics Service (Port 8001)
```powershell
cd D:\Prodapt_Phase_2\adk-services
uvicorn network_diagnostics.a2a_server:app --host 0.0.0.0 --port 8001
```

---

### Verifying Agent Cards

Once the services are running, verify their discovery cards via browser or curl:

- **Billing Resolution Agent Card:**
  ```powershell
  curl http://localhost:8002/.well-known/agent-card.json
  ```
  Expected: **HTTP 200** with skills for `lookup_billing_account`, `check_duplicate_charges`, and `apply_billing_credit`.

- **Network Diagnostics Agent Card:**
  ```powershell
  curl http://localhost:8001/.well-known/agent-card.json
  ```
  Expected: **HTTP 200** with skills for `check_tower_status`, `run_connectivity_diagnostics`, and `get_regional_network_summary`.

---

### 3. Launch the Streamlit Operations Dashboard

Once the ADK services are running (or even without them for RAG/SQL-only flows), open a new terminal in the project root:

```powershell
cd D:\Prodapt_Phase_2
streamlit run ui/app.py
```

The app will open at **http://localhost:8501** and provides:
- Live system status (database, vector index, ADK services)
- Customer inquiry text area and Submit button
- Customer-facing final response (CrewAI-polished)
- Agent Execution Trace (which workers ran, in order, with their output snippets)
- Accumulated context debug panel

---

## Directory Structure

```text
D:\Prodapt_Phase_2\
├── .env                              # API keys (Anthropic, Google, Nvidia)
├── requirements.txt                  # Pinned compatible dependencies
├── README.md                         # Project documentation
│
├── adk-services/                     # Google ADK microservices
│   ├── billing_resolution/           # Billing dispute resolution service
│   │   ├── __init__.py
│   │   ├── a2a_server.py             # A2A entrypoint (port 8002)
│   │   ├── agent.py                  # Agent definition & LiteLLM config
│   │   └── tools.py                  # SQL-backed async tools
│   ├── network_diagnostics/          # Network diagnostics service
│   │   ├── __init__.py
│   │   ├── a2a_server.py             # A2A entrypoint (port 8001)
│   │   ├── agent.py                  # Agent definition & LiteLLM config
│   │   └── tools.py                  # SQL-backed async tools
│   ├── test_billing_tool.py          # Standalone test for lookup_billing_account
│   ├── test_duplicate_tool.py        # Standalone test for check_duplicate_charges
│   └── test_credit_tool.py           # Standalone test for apply_billing_credit
│
├── data/
│   └── telecom_ops.db                # SQLite database with telecom data
│
├── llamaindex_rag/
│   ├── document_rag.py               # Document RAG over telecom policies/SLAs
│   └── sql_semantic_search.py        # Semantic natural language SQL queries
│
├── orchestration/                    # Orchestration & Customer Communications
│   ├── __init__.py
│   ├── state.py                      # LangGraph AgentState definition & trace reducer
│   ├── graph.py                      # LangGraph Supervisor & conditional routing
│   ├── adk_remote_client.py          # A2A client for external ADK services
│   ├── crew_nodes.py                 # CrewAI Customer Communications layer
│   ├── test_crew_integration.py      # Unit & live integration test suite for CrewAI
│   └── test_langgraph_paths.py       # LangGraph multi-worker path tests
│
├── ui/                               # Streamlit front-end
│   └── app.py                        # Operations dashboard (streamlit run ui/app.py)
│
└── sql/
    ├── 01_schema.sql                 # Database table DDL
    └── 02_seed_data.sql              # Database initial records & sample data
```