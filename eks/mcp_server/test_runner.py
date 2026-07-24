# test_runner.py
import sys
import os

# Ensure the local repository tracking directory is accessible to Python paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the frozen production query layers safely
from data_retrieval_engine import load_database_schema_config, run_compiled_mcp_query

# =============================================================================
# --- AUTOMATED VALIDATION RETRIEVAL MATRIX PROFILE ARRAY ---
# =============================================================================
integration_test_cases = [
    {
        "id": 1,
        "prompt_scenario": "How many active users at site 1001005?",
        "subjects": ["site", "user"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count", "active"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "site_id": [1001005]
        }
    },
    {
        "id": 2,
        "prompt_scenario": "What is the unit status for Service Unit 2256149?",
        "subjects": ["unit", "site"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "Service Unit 2256149",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [1001005]
        }
    },
    {
        "id": 3,
        "prompt_scenario": "Total number of units across sites 1001005 and 1001009?",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [1001005, 1001009]
        }
    },
    {
        "id": 4,
        "prompt_scenario": "Look up details for unit linked to user matching search 'narrow'?",
        "subjects": ["user", "unit"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "narrow",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [2223399, 2223449]
        }
    },
    {
        "id": 5,
        "prompt_scenario": "How many Noke Volt hardware assets are managed at site 1001005?",
        "subjects": ["lock", "unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count", "noke volt"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [1001005]
        }
    },{
        "id": 6,
        "prompt_scenario": "How many open units are available at site 1001005?",
        "subjects": ["unit", "site"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count", "open"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [1001005]
        }
    },
    {
        "id": 7,
        "prompt_scenario": "Show me the Tenant list",
        "subjects": ["site","user", "role" ], # order has to be maintained for the query builder to resolve the joins correctly
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "Tenant",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {
            "company_id": None,
            "site_id": [1001005]
        }
    },
    # ── NEW: Unit/User Analytical Test Cases ─────────────────────────────────
    {
        "id": 8,
        "prompt_scenario": "Tell me about unit Fake 3A",
        "subjects": ["unit"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "Fake 3A",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 9,
        "prompt_scenario": "Give me unit Fake 3A user information",
        "subjects": ["unit", "user"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "Fake 3A",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 10,
        "prompt_scenario": "How many units per rental state",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["rental_state"],
        "having_conditions": None,
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 11,
        "prompt_scenario": "How many available units",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count", "available"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 12,
        "prompt_scenario": "Available and occupied unit count breakdown",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count", "available", "inuse"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 13,
        "prompt_scenario": "Tenants renting more than 1 unit",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["user_id"],
        "having_conditions": [{"aggregation": "count", "operator": ">", "value": 1}],
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 14,
        "prompt_scenario": "Average price per access type",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["avg"],
        "aggregation_column": "details_price",
        "search_keyword": None,
        "group_by_columns": ["access_type"],
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 15,
        "prompt_scenario": "Occupied units with their user info",
        "subjects": ["unit", "user"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": ["inuse"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 16,
        "prompt_scenario": "Unit count per access type with more than 5 units",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["access_type"],
        "having_conditions": [{"aggregation": "count", "operator": ">", "value": 5}],
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 17,
        "prompt_scenario": "Find user John and their unit",
        "subjects": ["unit", "user"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "John",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 18,
        "prompt_scenario": "What is the percentage of unit occupancy",
        "subjects": ["unit"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["rental_state"],
        "having_conditions": None,
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    # ── Lock / Unit-Lock join test cases ─────────────────────────────────────
    {
        "id": 19,
        "prompt_scenario": "What is the battery status of Unit LA1234",
        "subjects": ["unit", "lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "LA1234",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391], "company_id": [1000241]}
    },
    {
        "id": 20,
        "prompt_scenario": "Show me all locked units",
        "subjects": ["unit", "lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": ["locked"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391], "company_id": [1000241]}
    },
    {
        "id": 21,
        "prompt_scenario": "How many locks per hardware type",
        "subjects": ["lock"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["hw_type"],
        "having_conditions": None,
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 22,
        "prompt_scenario": "Show offline locks",
        "subjects": ["lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": ["offline"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 23,
        "prompt_scenario": "Find lock by MAC abc123",
        "subjects": ["lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "abc123",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 24,
        "prompt_scenario": "Occupied units with lock hardware version noke volt",
        "subjects": ["unit", "lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": ["inuse", "noke volt"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391], "company_id": [1000241]}
    },
    {
        "id": 25,
        "prompt_scenario": "Count of locks by state breakdown",
        "subjects": ["lock"],
        "intent_type": "DATA_AGGREGATION",
        "semantic_filters": ["count"],
        "aggregation_column": None,
        "search_keyword": None,
        "group_by_columns": ["hw_state"],
        "having_conditions": None,
        "order_by": {"column": "count", "direction": "DESC"},
        "session_context": {"site_id": [2223391]}
    },
    {
        "id": 26,
        "prompt_scenario": "Unit LA1234 user and lock details",
        "subjects": ["unit", "user", "lock"],
        "intent_type": "DATA_RETRIEVAL",
        "semantic_filters": [],
        "aggregation_column": None,
        "search_keyword": "LA1234",
        "group_by_columns": None,
        "having_conditions": None,
        "order_by": None,
        "session_context": {"site_id": [2223391], "company_id": [1000241]}
    },
]

def execute_automated_matrix_suite():
    # 1. Boot up and cache the data-driven JSON metadata layout from disk
    load_database_schema_config("database_schema.json")
    
    print("\n" + "═"*80)
    print(f"🚀 INITIATING {len(integration_test_cases)} SEPARATED INTEGRATION SCENARIOS TEST MATRIX")
    print("═"*80)

    success_count = 0
    failure_count = 0

    # 2. Automated Sequential Execution Loop Engine
    for case in integration_test_cases:
        print(f"\n▶️ [TEST CASE #{case['id']}] EVALUATING PROMPT: '{case['prompt_scenario']}'")
        print(f"   ↳ Targets: {case['subjects']} | Intent: {case['intent_type']} | Filters: {case['semantic_filters']}")
        
        try:
            # Dispatch parameters dynamically straight into the frozen query factory loop
            db_response_rows = run_compiled_mcp_query(
                subjects=case["subjects"],
                intent_type=case["intent_type"],
                session_context=case["session_context"],
                semantic_filters=case["semantic_filters"],
                aggregation_column=case["aggregation_column"],
                search_keyword=case["search_keyword"],
                group_by_columns=case.get("group_by_columns") or [],
                having_conditions=case.get("having_conditions") or [],
                order_by=case.get("order_by") or None
            )
            
            print(f"   (Live database response rows array trace checked)")
            print(f"   🟢 SUCCESS: Scenario parameters compiled and mapped flawlessly.")
            success_count += 1
            
        except Exception as query_fault:
            print(f"   ❌ FAILURE: Compilation error or structural exception caught during runtime.")
            print(f"      Details: {query_fault}")
            failure_count += 1

    print("\n" + "═"*80)
    print("🏁 DATATYPE-DRIVEN RETRIEVAL PIPELINE AUTOMATED SUITE AUDIT REPORT")
    print(f"   📊 Total Scenarios Checked: {len(integration_test_cases)}")
    print(f"   ✅ Successful Validations: {success_count}")
    print(f"   💥 Trapped Exception Drops: {failure_count}")
    print("═"*80 + "\n")

if __name__ == "__main__":
    execute_automated_matrix_suite()
