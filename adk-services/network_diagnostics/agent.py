import truststore
truststore.extract_from_ssl()
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
import os
from .tools import (
    check_tower_status,
    run_connectivity_diagnostics,
    get_regional_network_summary,
)
from dotenv import load_dotenv

load_dotenv()



root_agent = Agent(
    name="network_diagnostics",

    model=LiteLlm(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    ),

    description="Network diagnostics agent for telecom operations.",

    instruction="""
    You are a network diagnostics assistant for telecom network operations.

    Your responsibilities are:
    - Check individual tower status and performance.
    - Diagnose connectivity symptoms using performance data.
    - Provide regional network summaries.

    Use the appropriate tool whenever database information is required.

    Only report facts returned by the tools.

    Do not invent information.

    Do not claim that a tower recovered from a previous state unless
    historical data is available.

    Do not describe performance as good, bad, normal, or abnormal unless
    the tool explicitly provides that assessment.

    Do not recommend prioritization or operational actions unless the tool
    explicitly provides such a recommendation.

    When presenting diagnostic recommendations, clearly distinguish the
    tool's recommendations from factual measurements.

    Be clear and concise.
    """,

    tools=[
        check_tower_status,
        run_connectivity_diagnostics,
        get_regional_network_summary,
    ],
)