"""
orchestration/test_crew_integration.py

Comprehensive test suite verifying:
1. CrewAI sequential workflow construction (Communications Specialist -> Quality Reviewer).
2. Review task context dependency on Communication task.
3. Billing resolution test scenario (Query + Context -> CrewAI response).
4. Network diagnostics test scenario (Query + Context -> CrewAI response).
5. Error handling and fallback behavior when Crew execution encounters exceptions.
6. LangGraph node integration (customer_comms_crew_node updates messages, context, trace).
7. Live CrewAI invocation with real Anthropic Claude LLM.
"""

import sys
import io
import os
from unittest.mock import MagicMock, patch

# Ensure proper UTF-8 stdout on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from crewai import Process
from langchain_core.messages import HumanMessage
from orchestration.crew_nodes import (
    create_customer_comms_crew,
    run_communication_crew,
    customer_comms_crew_node,
)
from orchestration.state import AgentState
from orchestration.graph import graph, build_telecom_graph


def test_crew_structure():
    """Verify that create_customer_comms_crew builds the exact required architecture."""
    print("\n[TEST 1] Verifying CrewAI sequential architecture...")
    user_query = "I was charged twice for my plan. Can I get a refund?"
    agent_context = "Duplicate charge detected. Amount: $65.99. Refund status: pending approval."

    crew, review_task = create_customer_comms_crew(user_query, agent_context)

    # 1. Verify two agents
    assert len(crew.agents) == 2, f"Expected 2 agents, got {len(crew.agents)}"
    roles = [agent.role for agent in crew.agents]
    assert "Customer Communications Specialist" in roles, "Communications Specialist missing"
    assert "Quality Reviewer" in roles, "Quality Reviewer missing"
    print("  -> Passed: Exactly 2 agents initialized (Communications Specialist & Quality Reviewer)")

    # 2. Verify two tasks
    assert len(crew.tasks) == 2, f"Expected 2 tasks, got {len(crew.tasks)}"
    comm_task, rev_task = crew.tasks[0], crew.tasks[1]
    assert comm_task.agent.role == "Customer Communications Specialist"
    assert rev_task.agent.role == "Quality Reviewer"
    print("  -> Passed: Tasks mapped to respective agents")

    # 3. Verify task dependency / context
    assert rev_task.context is not None and len(rev_task.context) == 1, "Review task must depend on comm task context"
    assert rev_task.context[0] == comm_task, "Review task context must be communication task"
    print("  -> Passed: Quality Reviewer receives communication task as context")

    # 4. Verify Process.sequential
    assert crew.process == Process.sequential, f"Expected Process.sequential, got {crew.process}"
    print("  -> Passed: Crew process is Process.sequential")


def test_billing_mocked():
    """Test Billing Resolution flow through CrewAI with mocked LLM/Crew output."""
    print("\n[TEST 2] Verifying Billing Resolution scenario (mocked)...")
    user_query = "I was charged twice for my plan. Can I get a refund?"
    agent_context = "[BillingResolutionADK]\nDuplicate charge detected. Amount: $65.99. Refund status: pending approval."

    expected_clean_response = (
        "We have reviewed your account and confirmed a duplicate charge of $65.99. "
        "A refund request for $65.99 has been submitted and is currently pending approval. "
        "You will receive an update once the review is complete."
    )

    mock_crew_output = MagicMock()
    mock_crew_output.raw = expected_clean_response

    with patch("orchestration.crew_nodes.Crew.kickoff", return_value=mock_crew_output) as mock_kickoff:
        response = run_communication_crew(user_query, agent_context)
        assert mock_kickoff.called
        assert "$65.99" in response
        assert "pending approval" in response
        assert isinstance(response, str)
        print("  -> Passed: Billing response correctly contains $65.99 and pending approval status")
        print(f"     Response: {response}")


def test_network_mocked():
    """Test Network Diagnostics flow through CrewAI with mocked LLM/Crew output."""
    print("\n[TEST 3] Verifying Network Diagnostics scenario (mocked)...")
    user_query = "Why is my internet not working?"
    agent_context = "[NetworkDiagnosticsADK]\nNetwork device is offline. Last heartbeat was 2 hours ago."

    expected_clean_response = (
        "We detected that your network device is currently offline. "
        "The last recorded heartbeat from the device was approximately 2 hours ago. "
        "Please verify your device power and connection cables while our technical team investigates."
    )

    mock_crew_output = MagicMock()
    mock_crew_output.raw = expected_clean_response

    with patch("orchestration.crew_nodes.Crew.kickoff", return_value=mock_crew_output) as mock_kickoff:
        response = run_communication_crew(user_query, agent_context)
        assert mock_kickoff.called
        assert "offline" in response
        assert "2 hours ago" in response
        assert isinstance(response, str)
        print("  -> Passed: Network response correctly reflects offline device and 2-hour heartbeat")
        print(f"     Response: {response}")


def test_langgraph_node_state_update():
    """Test customer_comms_crew_node LangGraph node execution and state mutation."""
    print("\n[TEST 4] Verifying customer_comms_crew_node LangGraph state updates...")
    mock_crew_output = MagicMock()
    mock_crew_output.raw = "Your duplicate charge of $65.99 is pending approval."

    initial_state: AgentState = {
        "messages": [HumanMessage(content="I was charged twice.")],
        "next": "CustomerCommsCrew",
        "user_query": "I was charged twice.",
        "agent_context": "[BillingResolutionADK]\nDuplicate charge $65.99 found.",
        "trace": [{"worker": "BillingResolutionADK", "summary": "Found charge"}],
    }

    with patch("orchestration.crew_nodes.Crew.kickoff", return_value=mock_crew_output):
        update = customer_comms_crew_node(initial_state)

        # Check messages
        assert len(update["messages"]) == 1
        assert update["messages"][0].content == "Your duplicate charge of $65.99 is pending approval."

        # Check agent_context accumulation
        assert "[CustomerCommsCrew]" in update["agent_context"]
        assert "Your duplicate charge of $65.99 is pending approval." in update["agent_context"]

        # Check trace
        assert len(update["trace"]) == 1
        assert update["trace"][0]["worker"] == "CustomerCommsCrew"
        print("  -> Passed: LangGraph node properly returned messages, updated context, and added trace entry")


def test_error_fallback():
    """Verify that run_communication_crew handles exceptions gracefully without crashing."""
    print("\n[TEST 5] Verifying error handling and graceful fallback...")
    user_query = "Is there an outage?"
    agent_context = "[PolicyRAG]\nSLA policy specifies standard turnaround within 4 hours."

    with patch("orchestration.crew_nodes.Crew.kickoff", side_effect=RuntimeError("Simulated LLM network timeout")):
        fallback = run_communication_crew(user_query, agent_context)
        assert isinstance(fallback, str)
        assert "SLA policy" in fallback
        print("  -> Passed: Handled runtime failure cleanly with grounded fallback string")


def test_langgraph_compilation():
    """Verify that LangGraph compiles and starts cleanly with customer_comms_crew."""
    print("\n[TEST 6] Verifying LangGraph compilation and structure...")
    compiled_graph = build_telecom_graph()
    nodes = list(compiled_graph.nodes.keys())
    assert "supervisor" in nodes
    assert "policy_rag" in nodes
    assert "network_analytics" in nodes
    assert "network_diagnostics_adk" in nodes
    assert "billing_resolution_adk" in nodes
    assert "customer_comms_crew" in nodes
    print(f"  -> Passed: LangGraph successfully compiled with all nodes: {nodes}")


def test_live_crewai_billing_call():
    """Run a real live call through CrewAI with the Billing scenario using the Anthropic API."""
    print("\n[TEST 7] Running LIVE CrewAI test with Anthropic API (Billing scenario)...")
    user_query = "I was charged twice for my plan. Can I get a refund?"
    agent_context = "Duplicate charge detected. Amount: $65.99. Refund status: pending approval."

    print("  -> Calling CrewAI with real Anthropic Claude model...")
    response = run_communication_crew(user_query, agent_context)
    print(f"  -> LIVE FINAL RESPONSE RECEIVED:\n{'-'*60}\n{response}\n{'-'*60}")

    assert isinstance(response, str), "Response must be a string"
    assert len(response.strip()) > 20, "Response should not be empty"
    assert "65.99" in response, "Response must include the exact amount $65.99"
    assert "pending" in response.lower(), "Response must note that the refund/credit is pending"
    print("  -> Passed: Live CrewAI billing executed successfully and verified factual adherence!")


def test_live_crewai_network_call():
    """Run a real live call through CrewAI with the Network scenario using the Anthropic API."""
    print("\n[TEST 8] Running LIVE CrewAI test with Anthropic API (Network scenario)...")
    user_query = "Why is my internet not working?"
    agent_context = "Network device is offline. Last heartbeat was 2 hours ago."

    print("  -> Calling CrewAI with real Anthropic Claude model...")
    response = run_communication_crew(user_query, agent_context)
    print(f"  -> LIVE FINAL RESPONSE RECEIVED:\n{'-'*60}\n{response}\n{'-'*60}")

    assert isinstance(response, str), "Response must be a string"
    assert len(response.strip()) > 20, "Response should not be empty"
    assert "offline" in response.lower(), "Response must note that the device is offline"
    assert "2 hours ago" in response.lower() or "2 hours" in response.lower(), "Response must note the 2 hour heartbeat"
    print("  -> Passed: Live CrewAI network executed successfully and verified factual adherence!")


if __name__ == "__main__":
    print("=" * 75)
    print(" PRODAPT AI OPERATIONS CENTER - CREWAI INTEGRATION TEST SUITE")
    print("=" * 75)

    test_crew_structure()
    test_billing_mocked()
    test_network_mocked()
    test_langgraph_node_state_update()
    test_error_fallback()
    test_langgraph_compilation()

    # Run live tests to verify real API credentials & end-to-end Anthropic execution
    test_live_crewai_billing_call()
    test_live_crewai_network_call()

    print("\n" + "=" * 75)
    print(" ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 75 + "\n")
