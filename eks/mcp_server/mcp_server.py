# mcp_server.py
import json
import os
import re

from db import execute_query

SCHEMA_CATALOG = {}

def load_database_schema_config(file_path: str = "database_schema.json"):
    """Loads all system metadata rules directly from your static configuration file."""
    global SCHEMA_CATALOG
    with open(file_path, "r") as f:
        SCHEMA_CATALOG = json.load(f)
    print("✅ 100% Dynamic Metadata Engine successfully cached into server memory.")

def run_compiled_mcp_query(subjects: list, intent_type: str, session_context: dict, semantic_filter: str = None, search_keyword: str = None) -> list[dict]:
    if not subjects:
        raise ValueError("Critical Fault: target_subjects list parameter cannot be empty.")
        
    root_entity = subjects[0].lower() # e.g., 'user'
    entity_meta = SCHEMA_CATALOG["entities"].get(root_entity)
    if not entity_meta:
        raise ValueError(f"Entity boundary error: '{root_entity}' is not defined inside schema files.")
        
    root_table = entity_meta["physical_table"]
    current_table = root_table
    current_alias = "t0"
    alias_count = 1
    join_clauses = []
    
    # Track the real alias names assigned to each subject dynamically
    # This solves the t1 vs t2 table alias mismatch completely!
    alias_map = {root_entity: "t0"}
    
    select_fields = [
        f"t0.{col}" for col in entity_meta["allowed_columns"] 
        if col not in SCHEMA_CATALOG["safety"]["deny_columns"]
    ]
    current_meta = entity_meta
    
    for next_entity in [s.lower() for s in subjects[1:]]:
        next_meta = SCHEMA_CATALOG["entities"].get(next_entity)
        if not next_meta:
            raise ValueError(f"Relational chain error: Entity '{next_entity}' is unregistered.")
            
        next_table = next_meta["physical_table"]
        parent_entity = subjects[subjects.index(next_entity) - 1].lower()
        lookup_key = f"{parent_entity}.{next_entity}"
        
        junction_meta = SCHEMA_CATALOG["junction_bridges"].get(lookup_key)
        
        if junction_meta:
            via_table = junction_meta["via_table"]
            j_alias = f"t{alias_count}"
            alias_count += 1
            
            # FIXED: We target word boundaries using unique token tags instead of generic .replace()
            # This completely stops 'users' from corrupting 'users_units_parameters'!
            rule_1 = junction_meta["step_1"]
            rule_1 = re.sub(rf'\b{current_table}\b', current_alias, rule_1)
            rule_1 = re.sub(rf'\b{via_table}\b', j_alias, rule_1)
            join_clauses.append(f"LEFT JOIN {via_table} {j_alias} ON {rule_1}")
            
            next_alias = f"t{alias_count}"
            rule_2 = junction_meta["step_2"]
            rule_2 = re.sub(rf'\b{via_table}\b', j_alias, rule_2)
            rule_2 = re.sub(rf'\b{next_table}\b', next_alias, rule_2)
            join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {rule_2}")
            
            # Map the true final operational alias back to this subject name
            alias_map[next_entity] = next_alias
            
            for col in next_meta["allowed_columns"]:
                if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                    select_fields.append(f"{next_alias}.{col} AS {next_entity}_{col}")
                    
            current_table = next_table
            current_alias = next_alias
            current_meta = next_meta
            alias_count += 1
            continue
            
        join_rule_template = current_meta["relationships"].get(next_entity)
        if not join_rule_template:
            raise ValueError(f"Structural network break: No valid connection pathway links {current_table} to {next_table}")
            
        next_alias = f"t{alias_count}"
        alias_map[next_entity] = next_alias
        
        clean_rule = re.sub(rf'\b{current_table}\b', current_alias, join_rule_template)
        clean_rule = re.sub(rf'\b{next_table}\b', next_alias, clean_rule)
        join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {clean_rule}")
        
        for col in next_meta["allowed_columns"]:
            if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                select_fields.append(f"{next_alias}.{col} AS {next_entity}_{col}")
                
        current_table = next_table
        current_alias = next_alias
        current_meta = next_meta
        alias_count += 1

    where_clauses = ["t0.company_id = %(company_id)s"] if "company_id" in entity_meta["allowed_columns"] else ["1=1"]
    query_params = {"company_id": session_context["company_id"]}
    
    if search_keyword and "first_name" in entity_meta["allowed_columns"]:
        where_clauses.append("(t0.first_name LIKE %(search)s OR t0.last_name LIKE %(search)s)")
        query_params["search"] = f"%{search_keyword}%"
        
    if semantic_filter:
        for entity_name in [s.lower() for s in subjects]:
            target_meta = SCHEMA_CATALOG["entities"].get(entity_name)
            if not target_meta or "column_metadata" not in target_meta:
                continue
                
            for real_col_name, col_meta in target_meta["column_metadata"].items():
                enum_rules = col_meta.get("enum_map", {})
                
                for standard_state, raw_database_values in enum_rules.items():
                    if semantic_filter == standard_state or semantic_filter in raw_database_values:
                        # FIXED: We pull the exact runtime alias from our dictionary tracker!
                        # This turns t1 into t2 flawlessly when junction bridges are injected
                        active_alias = alias_map[entity_name]
                        
                        where_clauses.append(f"{active_alias}.{real_col_name} IN %(states)s")
                        query_params["states"] = tuple(raw_database_values)
                        break

    columns_str = ", ".join(select_fields)
    joins_str = " ".join(join_clauses)
    where_str = " AND ".join(where_clauses)
    
    if intent_type == "DATA_AGGREGATION":
        final_sql = f"SELECT COUNT(*) as total_count FROM {root_table} t0 {joins_str} WHERE {where_str};"
    else:
        limit_cap = SCHEMA_CATALOG["safety"]["max_limit_ceiling"]
        final_sql = f"SELECT {columns_str} FROM {root_table} t0 {joins_str} WHERE {where_str} LIMIT {limit_cap};"
        
    # ─── UPDATE: PRETTIFIED TERMINAL PRINT MATRIX DISPLAY ───
    print("\n================ STEP 1: GENERATED PARAMETERIZED SQL ================")
    print(final_sql)
    print("\n================ STEP 2: PASSED ARGUMENTS MAP VALUES ================")
    print(json.dumps(query_params, indent=4, default=str))
    print("=====================================================================\n")
    
    # ─── REMOVE THiS after testing - EXTRACTION VISIBILITY UTILITY: PRETTY PRINT LIVE SQL INTERPOLATION ───
    try:
        formatted_params = {}
        for k, v in query_params.items():
            if isinstance(v, str):
                formatted_params[k] = f"'{v}'"
            elif isinstance(v, tuple):
                # Formats tuple elements cleanly inside standard SQL parentheses
                formatted_params[k] = "(" + ", ".join([f"'{item}'" if isinstance(item, str) else str(item) for item in v]) + ")"
            else:
                formatted_params[k] = str(v)
        
        # String interpolate the values back into the format placeholders
        raw_debug_sql = final_sql % formatted_params
        
        print("\n================ STEP 3: INTERPOLATED QUERY WITH LIVE VALUES ================")
        print(raw_debug_sql)
        print("=============================================================================\n")
    except Exception as log_error:
        print(f"Skipping debug string formatting optimization loop: {log_error}")
    print("=====================END till this remove it================================================\n")

    return execute_query(final_sql, query_params)

# --- LOCAL ISOLATED COMPILER RUN TIME VERIFICATION ---
if __name__ == "__main__":
    # Ensure your static file is named 'database_schema.json' or 'dbschema.json' on your disk
    load_database_schema_config("database_schema.json")
    
    test_subjects = ["user", "unit", "lock"]
    test_intent = "DATA_RETRIEVAL"
    mock_manager_session = {"company_id": 88}
    
    try:
        results = run_compiled_mcp_query(
            subjects=test_subjects,
            intent_type=test_intent,
            session_context=mock_manager_session,
            search_keyword="Alex",
            semantic_filter="vacant"
        )
    except Exception as e:
        # Handles local logging if a direct database socket connection isn't configured yet
        print(f"Error occurred: {e}")