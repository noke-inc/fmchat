# agent_test_runner.py
import sys
import os

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
        "company_id": None
    },
    {
        "id": 2,
        "prompt_scenario": "What is the unit status for Service Unit 2256149?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None
    },
    {
        "id": 3,
        "prompt_scenario": "Total number of units across sites Mateo's House and Mateo's Office?",
        "user_id": None,
        "site_id": [1001005, 1001009],
        "company_id": None
    },
    {
        "id": 4,
        "prompt_scenario": "Rental state for user John",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None
    },
    {
        "id": 5,
        "prompt_scenario": "How many Noke Volt locks are managed at our site?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None
    },
    {
        "id": 6,
        "prompt_scenario": "How many open units?",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None
    },
    {
        "id": 7,
        "prompt_scenario": "Show me the company manager list.",
        "user_id": None,
        "site_id": [1001005],
        "company_id": None
    }
]

def execute_agent_matrix_diagnostics():
    print("\n" + "═"*80)
    print(f"🚀 INITIATING {len(agent_integration_scenarios)} CONVERSATIONAL AGENT TEST INTEGRATIONS")
    print("═"*80)

    success_count = 0
    failure_count = 0

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
            
            print(f"   🤖 AGENT RESPONSE: \"{final_output_state['messages'][-1].content}\"")
            print(f"   📥 Input Tokens: {total_input_tokens} | 📤 Output Tokens: {total_output_tokens}")
            print(f"   🟢 SUCCESS: Conversational sequence executed and synthesized flawlessly.")
            success_count += 1
            
        except Exception as graph_fault:
            print(f"   ❌ FAILURE: Orchestrator thread dropped or AWS connection exception caught.")
            print(f"      Details: {graph_fault}")
            failure_count += 1

    print("\n" + "═"*80)
    print("🏁 CONVERSATIONAL AGENT WORKFLOW STATE SUITE AUDIT REPORT")
    print(f"   📊 Total Prompts Evaluated : {len(agent_integration_scenarios)}")
    print(f"   ✅ Successful Responses    : {success_count}")
    print(f"   💥 Trapped Pipeline Drops   : {failure_count}")
    print("═"*80 + "\n")

if __name__ == "__main__":
    # Apply your environment output encoding patch to prevent codec crashes on Windows
    os.environ["PYTHONIOENCODING"] = "utf-8"
    execute_agent_matrix_diagnostics()
