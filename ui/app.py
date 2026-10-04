"""
ui/app.py

Prodapt AI Operations Center - Streamlit User Interface
Provides an operations dashboard for customer support and NOC engineers.
Coordinates LangGraph supervisory orchestration, LlamaIndex RAG,
Google ADK microservices, and CrewAI customer communications.

Design Guidelines:
- Clean, minimal, and professional corporate design
- No emojis or saturated palette
- Strict adherence to Agentic AI Project specification (Section 6.8)
"""

import os
import sys
from pathlib import Path
import urllib.request
import urllib.error

# Ensure project root is in sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
from orchestration.graph import run_telecom_assistant


# ============================================================================
# Page Configuration & Minimal Professional Styling
# ============================================================================
st.set_page_config(
    page_title="Prodapt AI Operations Center",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Minimal Corporate Styling */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Header typography */
    .app-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .app-subtitle {
        font-size: 0.9rem;
        color: #4b5563;
        margin-bottom: 1.5rem;
    }

    /* Sidebar minimal styles */
    .sidebar-heading {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #374151;
        margin-top: 1.2rem;
        margin-bottom: 0.5rem;
        padding-bottom: 0.25rem;
        border-bottom: 1px solid #e5e7eb;
    }
    .status-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.85rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid #f3f4f6;
    }
    .status-name {
        color: #4b5563;
    }
    .status-ok {
        color: #047857;
        font-weight: 600;
    }
    .status-alert {
        color: #b91c1c;
        font-weight: 600;
    }

    /* Response container */
    .response-card {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-left: 4px solid #374151;
        border-radius: 4px;
        padding: 1.25rem 1.5rem;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
        color: #1f2937;
        line-height: 1.65;
        font-size: 0.95rem;
    }

    /* Trace items */
    .trace-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }
    .trace-step-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 0.35rem;
    }
    .trace-content {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.8rem;
        color: #374151;
        white-space: pre-wrap;
        background-color: #f9fafb;
        padding: 0.6rem 0.8rem;
        border-radius: 3px;
        border: 1px solid #e5e7eb;
        max-height: 320px;
        overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# Service Health Checks
# ============================================================================
def check_http_service(url: str, timeout: float = 0.5) -> bool:
    """Performs a non-blocking HTTP GET to verify microservice availability."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StreamlitHealthCheck"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def get_system_status() -> dict:
    """Collects current readiness of backend databases, indices, and ADK services."""
    base_dir = Path(_project_root)
    db_file = base_dir / "data" / "telecom_ops.db"
    vector_dir = base_dir / "data" / "vector_index"

    db_ready = db_file.is_file()
    vector_ready = vector_dir.is_dir()
    net_diag_running = check_http_service("http://localhost:8001/.well-known/agent-card.json")
    billing_running = check_http_service("http://localhost:8002/.well-known/agent-card.json")

    return {
        "db": db_ready,
        "vector": vector_ready,
        "net_diag": net_diag_running,
        "billing": billing_running,
    }


# ============================================================================
# Sidebar - System Status & Framework Map
# ============================================================================
with st.sidebar:
    st.markdown('<div class="sidebar-heading">System Status</div>', unsafe_allow_html=True)
    status = get_system_status()

    # Database
    db_class = "status-ok" if status["db"] else "status-alert"
    db_text = "Ready" if status["db"] else "Not found"
    st.markdown(
        f'<div class="status-row"><span class="status-name">Database (SQLite)</span>'
        f'<span class="{db_class}">{db_text}</span></div>',
        unsafe_allow_html=True,
    )

    # Vector Index
    vec_class = "status-ok" if status["vector"] else "status-name"
    vec_text = "Ready" if status["vector"] else "Builds on first query"
    st.markdown(
        f'<div class="status-row"><span class="status-name">Vector Index</span>'
        f'<span class="{vec_class}">{vec_text}</span></div>',
        unsafe_allow_html=True,
    )

    # Network Diagnostics ADK (Port 8001)
    net_class = "status-ok" if status["net_diag"] else "status-alert"
    net_text = "Running" if status["net_diag"] else "Not running"
    st.markdown(
        f'<div class="status-row"><span class="status-name">Network ADK (8001)</span>'
        f'<span class="{net_class}">{net_text}</span></div>',
        unsafe_allow_html=True,
    )

    # Billing Resolution ADK (Port 8002)
    bill_class = "status-ok" if status["billing"] else "status-alert"
    bill_text = "Running" if status["billing"] else "Not running"
    st.markdown(
        f'<div class="status-row"><span class="status-name">Billing ADK (8002)</span>'
        f'<span class="{bill_class}">{bill_text}</span></div>',
        unsafe_allow_html=True,
    )

    # Microservice startup notice if offline
    if not status["net_diag"] or not status["billing"]:
        st.markdown(
            """
            <div style="font-size:0.75rem; color:#6b7280; background-color:#f9fafb; border:1px solid #e5e7eb; border-radius:4px; padding:0.6rem; margin-top:0.75rem;">
            <strong>ADK Service Notice:</strong><br>
            To enable live diagnostics and billing actions, start the A2A services in separate terminals:
            <pre style="margin-top:0.4rem; margin-bottom:0; font-size:0.7rem; color:#374151;">uvicorn network_diagnostics.a2a_server:app --port 8001
uvicorn billing_resolution.a2a_server:app --port 8002</pre>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Framework Map
    st.markdown('<div class="sidebar-heading">Framework Map</div>', unsafe_allow_html=True)
    st.markdown(
        """
        | Capability | Framework |
        |---|---|
        | Policy & SLA Documents | LlamaIndex Document RAG |
        | Database Metrics & SQL | LlamaIndex Semantic SQL |
        | Live Cell Tower Diagnostics | Google ADK (Port 8001) |
        | Live Billing & Credits | Google ADK (Port 8002) |
        | Supervisory Orchestration | LangGraph |
        | Customer Communication | CrewAI |
        """
    )


# ============================================================================
# Main Content Area
# ============================================================================
st.markdown('<div class="app-title">Prodapt AI Operations Center</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Multi-Framework Agentic Architecture: '
    'LangGraph | LlamaIndex | Google ADK | CrewAI</div>',
    unsafe_allow_html=True,
)

# Customer Inquiry Input
customer_inquiry = st.text_area(
    label="Customer Inquiry",
    placeholder="Enter customer inquiry (e.g. 'Customer CUST-10002 was charged twice for Unlimited Plus. Investigate and apply credit.')",
    height=110,
    key="customer_inquiry_input",
)

col_submit, _ = st.columns([1, 5])
with col_submit:
    submit_clicked = st.button("Submit Inquiry", type="primary", use_container_width=True)

# Process Inquiry
if submit_clicked:
    trimmed_query = customer_inquiry.strip()
    if not trimmed_query:
        st.warning("Please enter a customer inquiry before submitting.")
    else:
        with st.spinner("Processing inquiry across multi-agent operations center..."):
            try:
                result = run_telecom_assistant(trimmed_query)
                st.session_state["active_result"] = result
                st.session_state["active_query"] = trimmed_query
            except Exception as exc:
                st.error(f"Error processing inquiry: {str(exc)}")
                st.session_state["active_result"] = None

# Display Output
active_result = st.session_state.get("active_result")

if active_result:
    final_response = active_result.get("final_response") or active_result.get("agent_context", "")
    execution_trace = active_result.get("execution_trace", [])

    st.markdown("### Customer-Facing Response")
    st.markdown(f'<div class="response-card">{final_response}</div>', unsafe_allow_html=True)

    # Agent Execution Trace panel (expanded by default per specification 6.8.3)
    with st.expander("Agent Execution Trace", expanded=True):
        if execution_trace:
            st.markdown(
                f"<div style='font-size:0.85rem; color:#4b5563; margin-bottom:0.75rem;'>"
                f"Total workers executed: <strong>{len(execution_trace)}</strong></div>",
                unsafe_allow_html=True,
            )
            for idx, step in enumerate(execution_trace, 1):
                worker_name = step.get("worker", "Unknown Worker")
                worker_output = step.get("output") or step.get("summary") or "(No output provided)"
                
                # Truncate output preview to 500 characters for clean readability
                truncated_output = worker_output[:500] + ("..." if len(worker_output) > 500 else "")

                st.markdown(
                    f"""
                    <div class="trace-card">
                        <div class="trace-step-title">Step {idx}: {worker_name}</div>
                        <div class="trace-content">{truncated_output}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No specialist workers executed for this inquiry.")

    # Accumulated Context (Secondary debug inspect panel)
    accumulated_context = active_result.get("agent_context", "").strip()
    if accumulated_context:
        with st.expander("Accumulated Agent Context (Internal Specialist Findings)", expanded=False):
            st.text(accumulated_context)
