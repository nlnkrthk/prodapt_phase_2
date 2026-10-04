"""
orchestration/crew_nodes.py

CrewAI Customer Communications Layer for the Prodapt AI Operations Center.
Implements a two-agent sequential crew:
  1. Communications Specialist: Converts technical/internal specialist findings
     into a clear, empathetic, and professional customer-friendly response draft.
  2. Quality Reviewer: Audits the draft against the original query and accumulated
     agent_context to verify factual accuracy, policy adherence, tone, and clarity,
     returning ONLY the final customer-ready response.

Process: Process.sequential
Review task depends on the communication task output via task context.
Exposes:
  - run_communication_crew(user_query: str, agent_context: str) -> str
  - customer_comms_crew_node(state: AgentState) -> dict
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of execution directory
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import logging
import truststore

# Enable corporate / system SSL certificates
truststore.inject_into_ssl()

from dotenv import load_dotenv

load_dotenv()

from crewai import Agent, Task, Crew, Process, LLM
from langchain_core.messages import AIMessage
from orchestration.state import AgentState

# Configure dedicated logger for CrewAI communications
logger = logging.getLogger("orchestration.crew_nodes")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [CrewAI] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def _get_crewai_llm() -> LLM:
    """
    Initializes the Anthropic Claude model for CrewAI using the existing
    ANTHROPIC_API_KEY from .env and the project's standard Claude model.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment. Please configure it in .env"
        )

    # Reuse the same Anthropic Claude model used across ADK services and LangGraph
    return LLM(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=api_key,
    )


def create_customer_comms_crew(user_query: str, agent_context: str) -> tuple[Crew, Task]:
    """
    Constructs the two-agent sequential CrewAI workflow:
      Agent 1: Communications Specialist (drafts customer response)
      Agent 2: Quality Reviewer (verifies facts against agent_context, outputs final text)
    """
    llm = _get_crewai_llm()

    # Agent 1: Customer Communications Specialist
    comms_specialist = Agent(
        role="Customer Communications Specialist",
        goal="Convert technical and internal telecom specialist results into a clear, "
             "professional, concise, and customer-friendly response.",
        backstory=(
            "You are a Customer Communications Specialist at the Prodapt AI Operations Center. "
            "Your role is to receive the original customer query and the verified technical findings "
            "gathered by specialist agents (RAG policy documents, SQL analytics, network diagnostics, "
            "and billing resolution). You transform these internal findings into an empathetic, "
            "reassuring, and clear customer-facing communication. "
            "CRITICAL RULES: "
            "1. Rely ONLY on the provided verified findings in agent_context. "
            "2. NEVER invent facts, ticket IDs, tower statuses, or refund amounts. "
            "3. NEVER state or imply an action was completed unless confirmed by agent_context. "
            "   If a credit or refund is pending approval, state clearly that it is pending approval. "
            "4. NEVER attempt to call tools or redo the underlying investigation. "
            "5. Keep the explanation concise, professional, and accessible."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    # Agent 2: Quality Reviewer
    quality_reviewer = Agent(
        role="Quality Reviewer",
        goal="Review the drafted communication against the original query and verified specialist "
             "findings for factual fidelity, policy compliance, clarity, and customer-ready tone.",
        backstory=(
            "You are a Quality Reviewer at the Prodapt AI Operations Center. "
            "Your job is to inspect customer-facing communication drafts before they are sent out. "
            "You meticulously cross-reference the draft against the original inquiry and the "
            "underlying agent_context. "
            "CRITICAL RULES: "
            "1. Verify that all monetary amounts, dates, and technical details match agent_context exactly. "
            "2. Confirm that pending actions are accurately described as pending, not completed. "
            "3. Reject and eliminate any hallucinated claims, unauthorized promises, or assumptions. "
            "4. Ensure the tone is polite, professional, and reassuring. "
            "5. Output ONLY the final customer-ready response text. Do NOT include greetings to staff, "
            "   preambles, approval notes, or markdown commentary."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    # Task 1: Draft customer response
    context_str = agent_context.strip() if agent_context else "(No prior specialist context available.)"

    communication_task = Task(
        description=(
            f"Review the original customer inquiry and the accumulated specialist findings below.\n\n"
            f"CUSTOMER INQUIRY:\n{user_query}\n\n"
            f"VERIFIED SPECIALIST FINDINGS:\n{context_str}\n\n"
            f"Task: Draft a professional, empathetic, and customer-friendly response explaining the situation "
            f"and next steps based STRICTLY on the specialist findings. Never invent facts or assume actions "
            f"that are not explicitly verified in the findings."
        ),
        expected_output="A complete, professional, and factually grounded customer response draft.",
        agent=comms_specialist,
    )

    # Task 2: Review and finalize customer response (receives Task 1 output as context)
    review_task = Task(
        description=(
            f"Review the customer response draft produced by the Communications Specialist.\n\n"
            f"ORIGINAL CUSTOMER INQUIRY:\n{user_query}\n\n"
            f"VERIFIED SPECIALIST FINDINGS (GROUND TRUTH):\n{context_str}\n\n"
            f"Task Instructions:\n"
            f"1. Cross-check all facts, amounts, and statuses against the specialist findings.\n"
            f"2. Ensure no hallucinated information or unauthorized promises exist.\n"
            f"3. Polish for professional, clear, and reassuring customer tone.\n"
            f"4. Return ONLY the final customer-facing response text. Do NOT include 'Reviewed and Approved', "
            f"   'Draft Response:', or internal reviewer commentary."
        ),
        expected_output="The finalized, customer-ready text only, with no reviewer commentary or meta-text.",
        agent=quality_reviewer,
        context=[communication_task],
    )

    # Build sequential Crew
    crew = Crew(
        agents=[comms_specialist, quality_reviewer],
        tasks=[communication_task, review_task],
        process=Process.sequential,
        verbose=False,
    )

    return crew, review_task


def run_communication_crew(user_query: str, agent_context: str) -> str:
    """
    Executes the two-agent sequential CrewAI communications layer.
    Accepts:
      - user_query: Original customer query
      - agent_context: Accumulated context string from prior LangGraph workers
    Returns:
      - A clean, customer-ready plain string response.
    """
    logger.info("CrewAI communication workflow started.")
    try:
        crew, _ = create_customer_comms_crew(
            user_query=user_query,
            agent_context=agent_context,
        )

        logger.info("Executing sequential Crew: Communications Specialist -> Quality Reviewer...")
        raw_result = crew.kickoff(
            inputs={
                "user_query": user_query,
                "agent_context": agent_context,
            }
        )

        # Extract plain string from CrewOutput
        if hasattr(raw_result, "raw") and isinstance(raw_result.raw, str):
            final_text = raw_result.raw.strip()
        else:
            final_text = str(raw_result).strip()

        logger.info("Quality Reviewer completed. Final customer response ready.")
        logger.info("CrewAI workflow completed successfully.")
        return final_text

    except Exception as exc:
        logger.error("CrewAI workflow encountered an error: %s", str(exc), exc_info=False)
        # Safe fallback without exposing stack traces or API keys
        if agent_context and agent_context.strip():
            return (
                "Thank you for contacting customer support. We investigated your inquiry with the following findings:\n\n"
                f"{agent_context.strip()}\n\n"
                "If you have further questions or require additional assistance, our support team is here to help."
            )
        return (
            "Thank you for contacting customer support. We have received your inquiry "
            "and are currently reviewing your account details. A support specialist will follow up shortly."
        )


def customer_comms_crew_node(state: AgentState) -> dict:
    """
    LangGraph node for Customer Communications Crew.
    Acts as the final customer-facing polish worker before FINISH.
    Receives user_query and accumulated agent_context from prior specialist workers.
    """
    user_query = state.get("user_query", "")
    current_context = state.get("agent_context", "").strip()

    logger.info("CustomerCommsCrew node invoked for query: %s", user_query[:80])

    final_response = run_communication_crew(
        user_query=user_query,
        agent_context=current_context,
    )

    crew_block = f"[CustomerCommsCrew]\n{final_response}"
    updated_context = (
        f"{current_context}\n\n{crew_block}" if current_context else crew_block
    )

    output_preview = final_response[:500] + ("..." if len(final_response) > 500 else "")
    trace_entry = {
        "worker": "CustomerCommsCrew",
        "summary": output_preview,
        "output": output_preview,
    }

    return {
        "messages": [AIMessage(content=final_response)],
        "agent_context": updated_context,
        "trace": [trace_entry],
    }
