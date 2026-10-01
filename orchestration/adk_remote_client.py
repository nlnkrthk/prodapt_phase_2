"""
orchestration/adk_remote_client.py

Synchronous client module for communicating with external Google ADK microservices
via the Agent-to-Agent (A2A) protocol.

Exposes two simple synchronous functions for the LangGraph workers:
  - call_network_diagnostics(user_query: str) -> str
  - call_billing_resolution(user_query: str) -> str

All async event streaming, RemoteA2aAgent creation, proxy agent configuration,
Runner execution, and connection error handling are encapsulated here.
"""

import os
import asyncio
import concurrent.futures
import truststore

# Enable corporate/system SSL certificates
truststore.inject_into_ssl()

from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.agent import RemoteA2aAgent
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part


# ============================================================================
# Service Discovery URLs (read from environment or default to local ports)
# ============================================================================
NETWORK_DIAGNOSTICS_URL = os.getenv(
    "NETWORK_DIAGNOSTICS_URL",
    "http://localhost:8001/.well-known/agent-card.json"
)

BILLING_RESOLUTION_URL = os.getenv(
    "BILLING_RESOLUTION_URL",
    "http://localhost:8002/.well-known/agent-card.json"
)


# ============================================================================
# Asynchronous Remote Execution Engine
# ============================================================================
async def _async_call_remote_adk(
    agent_name: str,
    card_url: str,
    port: int,
    user_query: str
) -> str:
    """
    Connects to the specified A2A service, sends the user query, and retrieves the response.
    Catches connection failures and returns a user-friendly message rather than crashing.
    """
    service_label = (
        "Network Diagnostics" if port == 8001 else "Billing Resolution"
    )

    try:
        # Step 1: Create the RemoteA2aAgent pointing to the discovery agent-card endpoint
        remote_agent = RemoteA2aAgent(
            name=f"{agent_name}_remote",
            agent_card=card_url,
        )

        # Step 2: Wrap the remote agent in a lightweight proxy ADK Agent with the remote as sub_agent
        proxy_agent = Agent(
            name=f"{agent_name}_proxy",
            sub_agents=[remote_agent],
        )

        # Step 3: Initialize the ADK InMemoryRunner to manage the conversation session
        runner = InMemoryRunner(agent=remote_agent)

        # Step 4: Create a new session for this query using runner.app_name
        session = await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id="telecom_operations_user",
        )

        # Step 5: Format the user input into a Google GenAI Content object
        message = Content(
            role="user",
            parts=[Part.from_text(text=user_query)],
        )

        # Step 6: Stream the events from the remote agent and capture the final response text
        final_response_text = ""
        async for event in runner.run_async(
            session_id=session.id,
            user_id="telecom_operations_user",
            new_message=message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    text_content = getattr(part, "text", None)
                    if text_content:
                        final_response_text = text_content

        # Return captured response or a fallback message if no text was emitted
        if not final_response_text.strip():
            return f"{service_label} service on port {port} responded, but did not return any text."

        return final_response_text.strip()

    except Exception:
        # Graceful error handling: if service is unreachable, return a clear message
        return (
            f"{service_label} service is unavailable. "
            f"Please make sure the ADK service is running on port {port}."
        )


def _run_sync(coro):
    """
    Helper to execute an async coroutine synchronously.
    Handles environments where an event loop is already running (e.g. Streamlit).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# ============================================================================
# Public Synchronous Functions for LangGraph Nodes
# ============================================================================
def call_network_diagnostics(user_query: str) -> str:
    """
    Synchronous function called by the LangGraph Network Diagnostics worker node.
    Routes to the Google ADK service running on port 8001.
    """
    return _run_sync(
        _async_call_remote_adk(
            agent_name="network_diagnostics",
            card_url=NETWORK_DIAGNOSTICS_URL,
            port=8001,
            user_query=user_query,
        )
    )


def call_billing_resolution(user_query: str) -> str:
    """
    Synchronous function called by the LangGraph Billing Resolution worker node.
    Routes to the Google ADK service running on port 8002.
    """
    return _run_sync(
        _async_call_remote_adk(
            agent_name="billing_resolution",
            card_url=BILLING_RESOLUTION_URL,
            port=8002,
            user_query=user_query,
        )
    )
