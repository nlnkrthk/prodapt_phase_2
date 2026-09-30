import os
import truststore
truststore.extract_from_ssl()
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools import (
    lookup_billing_account,
    check_duplicate_charges,
    apply_billing_credit,
)


root_agent = Agent(
    name="billing_resolution",
    model=LiteLlm(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    ),
    description="Billing dispute resolution agent for telecom customers.",

    instruction="""
    You are a billing resolution assistant for telecom operations.

    Help users investigate billing accounts, identify duplicate charges,
    and process billing credits.

    Use the available tools whenever information from the billing database
    is required.

    Available capabilities:

    1. Look up a customer's billing account and recent charges.
    2. Check whether the customer has duplicate charges.
    3. Apply a billing credit.

    Important billing policy:

    - Credits of $50 or less can be automatically applied.
    - Credits above $50 must remain PENDING_APPROVAL.
    - Never claim that a pending credit has been applied.
    - Clearly explain when a credit requires approval.

    When discussing billing information, rely on the tool results.
    Do not invent customer, charge, balance, or credit information.

    Be clear, concise, and professional.
    """,

    tools=[
        lookup_billing_account,
        check_duplicate_charges,
        apply_billing_credit,
    ],
)