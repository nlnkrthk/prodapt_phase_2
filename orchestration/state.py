"""
orchestration/state.py

Defines the AgentState used across the LangGraph orchestration layer.
Maintains the conversation history, routing decision, original inquiry,
accumulated specialist outputs, and execution trace.
"""

from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def append_trace(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Helper reducer to append new trace entries across worker nodes."""
    if existing is None:
        existing = []
    if new_items is None:
        new_items = []
    return existing + new_items


class AgentState(TypedDict):
    """
    Central state object passed between the LangGraph supervisor and specialist workers.
    """

    # 1. messages: Stores conversation history.
    #    Annotated with add_messages so new messages from workers are appended, not overwritten.
    messages: Annotated[list[BaseMessage], add_messages]

    # 2. next: Stores the supervisor's routing decision.
    #    Possible values:
    #    - "PolicyRAG"
    #    - "NetworkAnalytics"
    #    - "NetworkDiagnosticsADK"
    #    - "BillingResolutionADK"
    #    - "CustomerCommsCrew"
    #    - "FINISH"
    next: str

    # 3. user_query: The original question or customer inquiry submitted by the user.
    user_query: str

    # 4. agent_context: Accumulated textual output from all specialist workers.
    #    Formatted clearly (e.g., "[PolicyRAG]\n<output>") so downstream workers
    #    (like CustomerCommsCrew) have complete context of prior findings.
    agent_context: str

    # 5. trace: Structured execution log recording which workers executed and their snippets.
    #    Annotated with append_trace so each worker adds its trace entry for the UI.
    trace: Annotated[list[dict], append_trace]
