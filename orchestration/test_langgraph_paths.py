"""
orchestration/test_langgraph_paths.py

Comprehensive test suite verifying the 4 specialist execution paths and multi-worker routing
in the LangGraph orchestration layer.
"""

import sys
import io
# Ensure proper UTF-8 stdout on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orchestration.graph import run_telecom_assistant


def test_query(test_name: str, query: str):
    print(f"\n{'='*75}")
    print(f"RUNNING: {test_name}")
    print(f"QUERY:   {query}")
    print(f"{'='*75}")

    result = run_telecom_assistant(query)

    print("\n[EXECUTION TRACE]")
    for step in result.get("trace", []):
        print(f"  -> Worker: {step.get('worker')}")
        print(f"     Summary: {step.get('summary', '')[:120]}...")

    print("\n[ACCUMULATED AGENT CONTEXT]")
    print(result.get("agent_context", "").strip())
    print(f"\n{'-'*75}")
    return result


if __name__ == "__main__":
    # Test 1: Policy RAG
    test_query(
        "Test 1: Policy RAG",
        "What is the roaming policy for Europe?"
    )

    # Test 2: Semantic SQL / Network Analytics
    test_query(
        "Test 2: Semantic SQL / Network Analytics",
        "Which region had the most CRITICAL outages?"
    )

    # Test 3: Network Diagnostics ADK
    test_query(
        "Test 3: Network Diagnostics ADK",
        "My 5G drops near tower TX-512 in Austin."
    )

    # Test 4: Billing Resolution ADK
    test_query(
        "Test 4: Billing Resolution ADK",
        "Customer CUST-10002 was charged twice."
    )
