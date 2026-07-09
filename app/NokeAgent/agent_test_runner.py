# agent_test_runner.py
import sys
import os
from typing import Any

# Ensure both the local NokeAgent directory and core mcp_server modules are visible to paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eks", "mcp_server")))

# Import the native LangChain message constructors
from langchain_core.messages import HumanMessage

# Import your frozen production LangGraph orchestrator state machine app
from agent_graph import agent_brain_app

# =============================================================================
# --- CONVERSATIONAL SYSTEM TEST CASES PROFILE MATRIX ---
# =============================================================================
agent_integration_scenarios = [
    {
        "id": 1,
        "prompt_scenario": "How many active users ?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["count", "active", "user", "found"],
        "forbidden_any": []
    },
    {
        "id": 2,
        "prompt_scenario": "What is the unit status for Service Unit 2256149?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["unit", "status", "service"],
        "forbidden_any": []
    },
    {
        "id": 3,
        "prompt_scenario": "Total number of units across sites Mateo's House and Mateo's Office?",
        "user_id": None,
        "site_id": [1001005, 1001009],
        "company_id": None,
        "expected_any": ["total", "count", "unit", "site"],
        "forbidden_any": []
    },
    {
        "id": 4,
        "prompt_scenario": "Rental state for user John",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["rental", "state", "john", "user"],
        "forbidden_any": []
    },
    {
        "id": 5,
        "prompt_scenario": "How many Noke Volt locks are managed at our site?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["lock", "count", "site", "managed"],
        "forbidden_any": []
    },
    {
        "id": 6,
        "prompt_scenario": "How many open units?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["open", "unit", "count", "found"],
        "forbidden_any": []
    },
    {
        "id": 7,
        "prompt_scenario": "Show me the company manager list.",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["manager", "company", "list", "found"],
        "forbidden_any": []
    },
    {
        "id": 8,
        "prompt_scenario": "what is the tenant email for TEST",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None,
        "expected_any": ["not available", "no matching", "could not", "unable"],
        "forbidden_any": ["test@test.com", "@test.com"]
    }
]


def _to_plain_text(content: Any) -> str:
    """Safely flattens LangChain message content payloads into plain text."""
    if isinstance(content, list):
        chunks = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                chunks.append(str(block["text"]))
            else:
                chunks.append(str(block))
        return " ".join(chunks).strip()
    return str(content).strip()


def _validate_response(response_text: str, expected_any: list[str], forbidden_any: list[str]) -> list[str]:
    """Returns a list of validation errors for a scenario response."""
    failures = []
    normalized = response_text.lower()

    if expected_any and not any(token.lower() in normalized for token in expected_any):
        failures.append(
            f"Missing expected signal words. Expected one of: {expected_any}"
        )

    for token in forbidden_any or []:
        if token.lower() in normalized:
            failures.append(f"Forbidden token detected in response: '{token}'")

    return failures

def execute_agent_matrix_diagnostics():
    print("\n" + "═"*80)
    print(f"🚀 INITIATING {len(agent_integration_scenarios)} CONVERSATIONAL AGENT TEST INTEGRATIONS")
    print("═"*80)

    pass_count = 0
    validation_failure_count = 0
    execution_failure_count = 0

    # Sequential State Graph Execution Engine Loop
    for case in agent_integration_scenarios:
        print(f"\n▶️ [TEST CASE #{case['id']}] USER INPUT: '{case['prompt_scenario']}'")
        print(f"   ↳ Session Privilege: User {case['user_id']} | Sites {case['site_id']} | Company {case['company_id']}")
        
        # Initialize the state dictionary context exactly like your API Gateway
        initial_graph_state = {
            "messages": [HumanMessage(content=case["prompt_scenario"])],
            "user_id": case["user_id"],
            "site_id": case["site_id"],
            "company_id": case["company_id"]
        }
        
        try:
            # Trigger the entire end-to-end AWS Bedrock + Datatype query factory loop
            final_output_state = agent_brain_app.invoke(initial_graph_state)
            
            # Extract cumulative token totals generated inside this unique turn trip
            total_input_tokens = 0
            total_output_tokens = 0
            for msg in final_output_state["messages"]:
                if hasattr(msg, "response_metadata") and msg.response_metadata:
                    usage = msg.response_metadata.get("usage", {})
                    if usage:
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)

            final_response_text = _to_plain_text(final_output_state["messages"][-1].content)
            validation_failures = _validate_response(
                final_response_text,
                case.get("expected_any", []),
                case.get("forbidden_any", [])
            )
            
            print(f"   🤖 AGENT RESPONSE: \"{final_response_text}\"")
            print(f"   📥 Input Tokens: {total_input_tokens} | 📤 Output Tokens: {total_output_tokens}")

            if validation_failures:
                print("   ⚠️ VALIDATION FAILURE: Response completed but semantic guard checks failed.")
                for issue in validation_failures:
                    print(f"      - {issue}")
                validation_failure_count += 1
            else:
                print("   🟢 SUCCESS: Conversational sequence executed and passed semantic checks.")
                pass_count += 1
            
        except Exception as graph_fault:
            print(f"   ❌ FAILURE: Orchestrator thread dropped or AWS connection exception caught.")
            print(f"      Details: {graph_fault}")
            execution_failure_count += 1

    print("\n" + "═"*80)
    print("🏁 CONVERSATIONAL AGENT WORKFLOW STATE SUITE AUDIT REPORT")
    print(f"   📊 Total Prompts Evaluated : {len(agent_integration_scenarios)}")
    print(f"   ✅ Passed (Execution + Validation): {pass_count}")
    print(f"   ⚠️ Validation Failures         : {validation_failure_count}")
    print(f"   💥 Execution Failures          : {execution_failure_count}")
    print("═"*80 + "\n")

if __name__ == "__main__":
    # Apply your environment output encoding patch to prevent codec crashes on Windows
    os.environ["PYTHONIOENCODING"] = "utf-8"
    execute_agent_matrix_diagnostics()
