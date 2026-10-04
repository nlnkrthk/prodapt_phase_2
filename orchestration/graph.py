"""
orchestration/graph.py

Main LangGraph orchestration module for the Prodapt AI Operations Center.
Implements the Supervisor architecture with conditional routing to four specialist workers:
  1. PolicyRAG (LlamaIndex Document RAG)
  2. NetworkAnalytics (LlamaIndex Semantic SQL)
  3. NetworkDiagnosticsADK (Google ADK A2A service on port 8001)
  4. BillingResolutionADK (Google ADK A2A service on port 8002)
  5. CustomerCommsCrew (Customer Communications Crew integration point)
  6. FINISH (Completion)

Routes back to the Supervisor after each worker, allowing multi-worker coordination
and context accumulation.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of execution directory
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from typing import Literal
import truststore

# Inject system/enterprise certificates for secure outbound API calls
truststore.inject_into_ssl()

from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END

# Import shared state
from orchestration.state import AgentState

# Import synchronous worker modules
from llamaindex_rag.document_rag import answer_policy_question
from llamaindex_rag.sql_semantic_search import answer_sql_question
from orchestration.adk_remote_client import (
    call_network_diagnostics,
    call_billing_resolution,
)
from orchestration.crew_nodes import customer_comms_crew_node


# ============================================================================
# Supervisor LLM & Structured Decision Schema
# ============================================================================

class SupervisorDecision(BaseModel):
    """Structured decision output produced by the Supervisor LLM."""

    next_worker: Literal[
        "PolicyRAG",
        "NetworkAnalytics",
        "NetworkDiagnosticsADK",
        "BillingResolutionADK",
        "CustomerCommsCrew",
        "FINISH",
    ] = Field(
        description="The next specialist worker to route to, or FINISH if all tasks are complete."
    )
    reasoning: str = Field(
        description="Clear, concise rationale explaining why this worker was selected or why we are done."
    )


def _get_supervisor_llm():
    """Initializes the Anthropic Claude model configured for structured output."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY was not found in the .env file.")

    base_llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        api_key=api_key,
        temperature=0.0,
    )
    return base_llm.with_structured_output(SupervisorDecision)


# ============================================================================
# Supervisor Node
# ============================================================================

def supervisor_node(state: AgentState) -> dict:
    """
    Evaluates the user inquiry, checks accumulated context and prior execution trace,
    and decides which specialist worker should execute next, or FINISH.
    """
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()
    executed_workers = [t.get("worker") for t in state.get("trace", [])]

    # Formulate supervisor system prompt with specialist domain responsibilities
    prompt = f"""You are the Operations Supervisor for the Prodapt AI Operations Center.
Your role is to orchestrate specialist workers to resolve telecom customer inquiries accurately.

SPECIALIST WORKER RESPONSIBILITIES:
1. PolicyRAG:
   - Use for company policies, SLAs, refund windows, roaming rates/zones, outage credit calculation rules, 5G device troubleshooting, or equipment upgrade terms.
   - Grounded in documents: sla_policy.txt, roaming_policy.txt, billing_disputes_policy.txt, network_outage_procedures.txt, 5g_faq.txt, device_upgrade_policy.txt.

2. NetworkAnalytics:
   - Use for aggregated historical network metrics, regional outage statistics, tower health counts, and customer subscription counts across the database.
   - Grounded in tables: network_outages, network_towers, customer_subscriptions, tower_performance.

3. NetworkDiagnosticsADK:
   - Use for LIVE technical diagnostics on specific cell towers (e.g. TX-512, NY-301, IL-104), active incident inspection, and real-time subscriber connectivity tests (port 8001).

4. BillingResolutionADK:
   - Use for LIVE customer billing accounts, investigating duplicate charges, checking balances, and processing billing credits under the $50 auto-approval limit (port 8002).

5. CustomerCommsCrew:
   - Formats customer-facing responses after specialist workers have gathered information.
   - Always route to CustomerCommsCrew once specialist findings have been collected so that the communication is properly synthesized and quality-reviewed before finishing.

6. FINISH:
   - Select FINISH only after CustomerCommsCrew has executed, or if all required work is completely finished.

ROUTING RULES:
- Read the original user inquiry carefully.
- Review what workers have ALREADY executed: {executed_workers}
- Review the accumulated findings so far:
{current_context if current_context else "(No specialist workers have executed yet)"}

- IMPORTANT: DO NOT select a specialist worker that has already been executed for this inquiry unless new specific information is strictly needed.
- For multi-domain questions (e.g. "Outage lasted 6 hours - do I get a credit?"), first call the outage/analytics or diagnostics worker, and then call the policy worker.
- Once the necessary specialist workers have executed and their findings are recorded, route to CustomerCommsCrew.
- Once CustomerCommsCrew has executed, choose FINISH.

CURRENT USER INQUIRY:
"{user_query}"
"""

    supervisor_llm = _get_supervisor_llm()
    decision: SupervisorDecision = supervisor_llm.invoke(prompt)

    next_worker = decision.next_worker

    # Safety guard: prevent infinite loops and ensure CustomerCommsCrew runs before FINISH
    if next_worker in executed_workers and next_worker not in ["FINISH"]:
        if "CustomerCommsCrew" not in executed_workers and current_context:
            next_worker = "CustomerCommsCrew"
        else:
            next_worker = "FINISH"
    elif next_worker == "FINISH" and current_context and "CustomerCommsCrew" not in executed_workers:
        # Route to CustomerCommsCrew before finishing whenever specialist findings exist
        next_worker = "CustomerCommsCrew"

    return {
        "next": next_worker,
    }


# ============================================================================
# Specialist Worker Nodes
# ============================================================================

def policy_rag_node(state: AgentState) -> dict:
    """Invokes the LlamaIndex Document RAG engine to answer policy/SLA inquiries."""
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    try:
        answer = answer_policy_question(user_query)
    except Exception as exc:
        answer = f"Policy RAG encountered an error: {str(exc)}"

    block = f"[PolicyRAG]\n{answer}"
    updated_context = f"{current_context}\n\n{block}" if current_context else block

    output_preview = answer[:500] + ("..." if len(answer) > 500 else "")
    trace_entry = {
        "worker": "PolicyRAG",
        "summary": output_preview,
        "output": output_preview,
    }

    return {
        "messages": [AIMessage(content=answer)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }


def network_analytics_node(state: AgentState) -> dict:
    """Invokes the LlamaIndex Semantic SQL engine to run analytics on the SQLite database."""
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    try:
        answer = answer_sql_question(user_query)
    except Exception as exc:
        answer = f"Network Analytics encountered an error: {str(exc)}"

    block = f"[NetworkAnalytics]\n{answer}"
    updated_context = f"{current_context}\n\n{block}" if current_context else block

    output_preview = answer[:500] + ("..." if len(answer) > 500 else "")
    trace_entry = {
        "worker": "NetworkAnalytics",
        "summary": output_preview,
        "output": output_preview,
    }

    return {
        "messages": [AIMessage(content=answer)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }


def network_diagnostics_adk_node(state: AgentState) -> dict:
    """Invokes the Google ADK Network Diagnostics service via A2A protocol on port 8001."""
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    try:
        answer = call_network_diagnostics(user_query)
    except Exception as exc:
        answer = f"Network Diagnostics service error: {str(exc)}"

    block = f"[NetworkDiagnosticsADK]\n{answer}"
    updated_context = f"{current_context}\n\n{block}" if current_context else block

    output_preview = answer[:500] + ("..." if len(answer) > 500 else "")
    trace_entry = {
        "worker": "NetworkDiagnosticsADK",
        "summary": output_preview,
        "output": output_preview,
    }

    return {
        "messages": [AIMessage(content=answer)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }


def billing_resolution_adk_node(state: AgentState) -> dict:
    """Invokes the Google ADK Billing Resolution service via A2A protocol on port 8002."""
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    try:
        answer = call_billing_resolution(user_query)
    except Exception as exc:
        answer = f"Billing Resolution service error: {str(exc)}"

    block = f"[BillingResolutionADK]\n{answer}"
    updated_context = f"{current_context}\n\n{block}" if current_context else block

    output_preview = answer[:500] + ("..." if len(answer) > 500 else "")
    trace_entry = {
        "worker": "BillingResolutionADK",
        "summary": output_preview,
        "output": output_preview,
    }

    return {
        "messages": [AIMessage(content=answer)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }


# ============================================================================
# Conditional Routing Logic
# ============================================================================

def route_supervisor(state: AgentState) -> str:
    """Maps the supervisor's decision in state['next'] to the appropriate node or END."""
    decision = state.get("next", "FINISH")

    mapping = {
        "PolicyRAG": "policy_rag",
        "NetworkAnalytics": "network_analytics",
        "NetworkDiagnosticsADK": "network_diagnostics_adk",
        "BillingResolutionADK": "billing_resolution_adk",
        "CustomerCommsCrew": "customer_comms_crew",
        "FINISH": END,
    }

    return mapping.get(decision, END)


# ============================================================================
# Graph Construction & Compilation
# ============================================================================

def build_telecom_graph():
    """Constructs and compiles the StateGraph for the Telecom Operations Assistant."""
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("policy_rag", policy_rag_node)
    workflow.add_node("network_analytics", network_analytics_node)
    workflow.add_node("network_diagnostics_adk", network_diagnostics_adk_node)
    workflow.add_node("billing_resolution_adk", billing_resolution_adk_node)
    workflow.add_node("customer_comms_crew", customer_comms_crew_node)

    # Start directs directly to the Supervisor
    workflow.add_edge(START, "supervisor")

    # Conditional routing out of the Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "policy_rag": "policy_rag",
            "network_analytics": "network_analytics",
            "network_diagnostics_adk": "network_diagnostics_adk",
            "billing_resolution_adk": "billing_resolution_adk",
            "customer_comms_crew": "customer_comms_crew",
            END: END,
        },
    )

    # Every specialist worker returns control back to the Supervisor
    workflow.add_edge("policy_rag", "supervisor")
    workflow.add_edge("network_analytics", "supervisor")
    workflow.add_edge("network_diagnostics_adk", "supervisor")
    workflow.add_edge("billing_resolution_adk", "supervisor")
    workflow.add_edge("customer_comms_crew", "supervisor")

    return workflow.compile()


# Compile global graph instance
graph = build_telecom_graph()


# ============================================================================
# Public Entry Point
# ============================================================================

def run_telecom_assistant(user_query: str) -> dict:
    """
    Primary execution function for the Telecom Operations Center.
    Invoked by UI (Streamlit), integration tests, or API scripts.

    Returns the complete final AgentState dictionary augmented with
    convenience fields: 'final_response' and 'execution_trace'.
    """
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_query)],
        "next": "supervisor",
        "user_query": user_query,
        "agent_context": "",
        "trace": [],
    }

    # Execute graph with a safe recursion limit to prevent runaway loops
    final_state = graph.invoke(initial_state, config={"recursion_limit": 15})

    # Extract clean final_response from CustomerCommsCrew or last AIMessage
    final_response = ""
    for msg in reversed(final_state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            final_response = msg.content
            break
    if not final_response:
        final_response = final_state.get("agent_context", "")

    # Format execution_trace conforming to Streamlit data contract
    raw_trace = final_state.get("trace", [])
    execution_trace = []
    for step in raw_trace:
        text = step.get("output") or step.get("summary") or ""
        execution_trace.append({
            "worker": step.get("worker", "Unknown"),
            "summary": text,
            "output": text,
        })

    final_state["final_response"] = final_response
    final_state["execution_trace"] = execution_trace
    return final_state


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("\n" + "=" * 70)
    print(" Prodapt AI Operations Center - LangGraph Supervisor CLI")
    print("=" * 70)
    print("Type your telecom inquiry below (or 'exit' to quit).\n")

    while True:
        try:
            query = input("Inquiry > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting.")
                break

            print("\n[Running LangGraph Supervisor...]")
            result = run_telecom_assistant(query)

            print("\n" + "-" * 70)
            print("EXECUTION TRACE:")
            trace = result.get("trace", [])
            if trace:
                for idx, step in enumerate(trace, 1):
                    worker = step.get("worker", "Unknown")
                    summary = step.get("summary", "")[:140]
                    print(f"  Step {idx}: [{worker}] -> {summary}...")
            else:
                print("  No specialist worker executed.")

            print("\nFINAL RESPONSE / AGENT CONTEXT:")
            print("-" * 70)
            print(result.get("agent_context", "(No context generated)"))
            print("=" * 70 + "\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\n[Error executing query]: {e}\n")

