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
    print("✅ 100% Dynamic Engine Loaded. Zero hardcoded calculation branches remain.")

def run_compiled_mcp_query(subjects: list, intent_type: str, session_context: dict, semantic_filters: list = None, aggregation_column: str = None, search_keyword: str = None) -> list[dict]:
    if not subjects:
        raise ValueError("Critical Fault: target_subjects list parameter cannot be empty.")
        
    root_entity = subjects[0].lower()
    entity_meta = SCHEMA_CATALOG["entities"].get(root_entity)
    if not entity_meta:
        raise ValueError(f"Entity boundary error: '{root_entity}' is unregistered.")
        
    root_table = entity_meta["physical_table"]
    current_table = root_table
    current_alias = "t0"
    alias_count = 1
    join_clauses = []
    current_meta = entity_meta
    alias_map = {root_entity: "t0"}
    select_fields = []

    # ========================================================
    # 1. RECURSIVE JOIN FACTORY LOOP
    # ========================================================
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
            
            rule_1 = re.sub(rf'\b{current_table}\b', current_alias, junction_meta["step_1"])
            rule_1 = re.sub(rf'\b{via_table}\b', j_alias, rule_1)
            join_clauses.append(f"LEFT JOIN {via_table} {j_alias} ON {rule_1}")
            
            next_alias = f"t{alias_count}"
            rule_2 = re.sub(rf'\b{via_table}\b', j_alias, junction_meta["step_2"])
            rule_2 = re.sub(rf'\b{next_table}\b', next_alias, rule_2)
            join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {rule_2}")
            
            alias_map[next_entity] = next_alias
            current_table = next_table
            current_alias = next_alias
            current_meta = next_meta
            alias_count += 1
            continue
            
        join_rule_template = current_meta["relationships"].get(next_entity)
        if not join_rule_template:
            raise ValueError(f"No valid connection links {current_table} to {next_table}")
            
        next_alias = f"t{alias_count}"
        alias_map[next_entity] = next_alias
        clean_rule = re.sub(rf'\b{current_table}\b', current_alias, join_rule_template)
        clean_rule = re.sub(rf'\b{next_table}\b', next_alias, clean_rule)
        join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {clean_rule}")
        current_table = next_table
        current_alias = next_alias
        current_meta = next_meta
        alias_count += 1

    # ========================================================
    # 2. DYNAMIC SELECT COMPILATION
    # ========================================================
    if intent_type == "DATA_AGGREGATION" and semantic_filters:
        allowed_formulas = entity_meta.get("allowed_aggregations", {})
        for op in [f.lower() for f in semantic_filters]:
            formula_meta = allowed_formulas.get(op)
            if not formula_meta:
                continue
                
            raw_function = formula_meta["sql_function"]
            out_name = formula_meta["output_column"]
            
            if formula_meta.get("requires_column"):
                if aggregation_column in formula_meta["allowed_columns"] and aggregation_column in entity_meta["allowed_columns"]:
                    compiled_func = raw_function.format(column=f"t0.{aggregation_column}")
                    select_fields.append(f"{compiled_func} AS {out_name}_{aggregation_column}")
            else:
                select_fields.append(f"{raw_function} AS {out_name}")
                
        if not select_fields:
            select_fields.append("COUNT(*) AS count")
    else:
        for col in entity_meta["allowed_columns"]:
            if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                select_fields.append(f"t0.{col}")
                
        for entity_name, assigned_alias in alias_map.items():
            if entity_name != root_entity:
                child_meta = SCHEMA_CATALOG["entities"][entity_name]
                for col in child_meta["allowed_columns"]:
                    if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                        select_fields.append(f"{assigned_alias}.{col} AS {entity_name}_{col}")

    # ========================================================
    # 3. 100% DYNAMIC SESSION CONTEXT MAPPING FILTERS
    # ========================================================
    where_clauses = []
    query_params = {}
    security_group_filters = []
    
    for session_key, session_value in session_context.items():
        if session_value is None or session_value == "" or session_value == [] or session_value == ():
            continue
            
        target_column_name = session_key
        resolved_column_alias = None
        
        # Track A: Direct match inside the primary table
        if target_column_name in entity_meta["allowed_columns"]:
            resolved_column_alias = "t0"
        else:
            # Track B: Dynamic Namespace Scan across child entities [🔒]
            for entity_name, assigned_alias in alias_map.items():
                child_meta = SCHEMA_CATALOG["entities"][entity_name]
                
                # Check for direct naming equality matches inside child schemas
                if target_column_name in child_meta["allowed_columns"]:
                    resolved_column_alias = assigned_alias
                    break
                    
                # Adaptive Suffix Translation: Automatically reduces 'site_id' or 'user_id' 
                # to primitive primary keys ('id') matching your physical tables dynamically [🔒]
                clean_suffix_token = target_column_name.replace(f"{entity_name}_", "")
                if clean_suffix_token in child_meta["allowed_columns"] and target_column_name.startswith(entity_name):
                    resolved_column_alias = assigned_alias
                    target_column_name = clean_suffix_token
                    break
                    
        if resolved_column_alias:
            param_token_name = f"ctx_{session_key}"
            if isinstance(session_value, (list, tuple)):
                clause_snippet = f"{resolved_column_alias}.{target_column_name} IN %({param_token_name})s"
                query_params[param_token_name] = tuple(session_value)
            else:
                clause_snippet = f"{resolved_column_alias}.{target_column_name} = %({param_token_name})s"
                query_params[param_token_name] = session_value
            security_group_filters.append(clause_snippet)

    if len(security_group_filters) == 2:
        where_clauses.append(f"({security_group_filters[0]} OR {security_group_filters[1]})")
    elif len(security_group_filters) == 1:
        where_clauses.append(security_group_filters[0])
    elif len(security_group_filters) > 2:
        where_clauses.append(" AND ".join(security_group_filters))
    else:
        where_clauses.append("1=1")

    if search_keyword and "first_name" in entity_meta["allowed_columns"]:
        where_clauses.append("(t0.first_name LIKE %(search)s OR t0.last_name LIKE %(search)s)")
        query_params["search"] = f"%{search_keyword}%"
        
    if semantic_filters:
        math_keywords = list(entity_meta.get("allowed_aggregations", {}).keys())
        for entity_name in [s.lower() for s in subjects]:
            target_meta = SCHEMA_CATALOG["entities"].get(entity_name)
            if not target_meta or "column_metadata" not in target_meta:
                continue
                
            for real_col_name, col_meta in target_meta["column_metadata"].items():
                enum_rules = col_meta.get("enum_map", {})
                filter_found_and_mapped = False
                
                for f_word in [sf.lower() for sf in semantic_filters]:
                    if f_word in math_keywords:
                        continue
                        
                    for standard_state, raw_database_values in enum_rules.items():
                        if f_word == standard_state or f_word in raw_database_values:
                            active_alias = alias_map[entity_name]
                            unique_param_name = f"states_{entity_name}_{real_col_name}"
                            where_clauses.append(f"{active_alias}.{real_col_name} IN %({unique_param_name})s")
                            query_params[unique_param_name] = tuple(raw_database_values)
                            filter_found_and_mapped = True
                            break
                            
                    if filter_found_and_mapped:
                        break
                if filter_found_and_mapped:
                    break

    # ========================================================
    # 4. FINAL STRING CONCATENATION & EMISSION
    # ========================================================
    columns_str = ", ".join(select_fields)
    joins_str = " ".join(join_clauses)
    where_str = " AND ".join(where_clauses)
    if intent_type == "DATA_AGGREGATION":
        final_sql = f"SELECT {columns_str} FROM {root_table} t0 {joins_str} WHERE {where_str};"
    else:
        limit_cap = SCHEMA_CATALOG["safety"]["max_limit_ceiling"]
        final_sql = f"SELECT {columns_str} FROM {root_table} t0 {joins_str} WHERE {where_str} LIMIT {limit_cap};"
    try:
        formatted_params = {}
        for k, v in query_params.items():
            if isinstance(v, str):
                formatted_params[k] = f"'{v}'"
            elif isinstance(v, tuple):
                formatted_params[k] = "(" + ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in v]) + ")"
            else:
                formatted_params[k] = str(v)
        print("\n================ STEP 3: INTERPOLATED QUERY WITH LIVE VALUES ================ ")
        print(final_sql % formatted_params)
        print("=============================================================================\n")
    except Exception as e:
        print("Formatting log notice:", e)
    return execute_query(final_sql, query_params)

    #--- LOCAL DYNAMIC TESTING PIPELINE ENVIRONMENT --- #
if __name__ == "__main__":
    load_database_schema_config("database_schema.json")
    
    mock_filters = ["count", "avg", "sum", "vacant", "active"]
    
    random_session_context = {"company_id": None,
                              "site_id":[1001005, 1001009, 1001050],
                              "user_id":[1032127]}
    try:
        run_compiled_mcp_query(subjects=["unit", "site", "user"],
                               intent_type="DATA_AGGREGATION",
                               session_context=random_session_context,
                               semantic_filters=mock_filters,
                               aggregation_column="details_price")
    except Exception as e:
        print(f"❌ Local Execution Unit Test Failed: {e}")