"""
orchestration/crew_nodes.py

Integration placeholder for the Customer Communications CrewAI worker.
Will later orchestrate:
  1. Communications Specialist: Drafts response from user_query + accumulated agent_context
  2. Quality Reviewer: Reviews response for tone, accuracy, and SLA compliance

Keeps the LangGraph integration point ready without inventing dummy CrewAI code.
"""

from langchain_core.messages import AIMessage
from orchestration.state import AgentState


def customer_comms_crew_node(state: AgentState) -> dict:
    """
    LangGraph node for Customer Communications Crew.
    Acts as the final customer-facing polish worker before FINISH.
    Receives user_query and accumulated agent_context from prior specialist workers.
    """
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    # Note: Full sequential CrewAI crew (Communications Specialist + Quality Reviewer)
    # will be plugged in here in the subsequent Phase.
    crew_header = (
        "[CustomerCommsCrew]\n"
        "(Customer Communications CrewAI integration placeholder - CrewAI implementation pending)\n"
    )

    if current_context:
        formatted_response = (
            f"{crew_header}"
            f"Synthesizing response for customer inquiry: '{user_query}'\n"
            f"Based on gathered specialist findings:\n{current_context}"
        )
    else:
        formatted_response = (
            f"{crew_header}"
            f"Acknowledging customer inquiry: '{user_query}'"
        )

    # Accumulate into agent_context
    updated_context = (
        f"{current_context}\n\n{formatted_response}"
        if current_context
        else formatted_response
    )

    trace_entry = {
        "worker": "CustomerCommsCrew",
        "summary": "Customer Communications Crew placeholder executed.",
    }

    return {
        "messages": [AIMessage(content=formatted_response)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }
