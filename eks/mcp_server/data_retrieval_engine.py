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
   # print("✅ 100% Dynamic Datatype-Driven Engine Loaded. Zero hardcoded knowledge remains.")

# data_retrieval_engine.py (Fully Synchronized Fact-Table Centric Engine)
import re
import sys
import json

def run_compiled_mcp_query(subjects: list, intent_type: str, session_context: dict, semantic_filters: list = None, aggregation_column: str = None, search_keyword: str = None) -> list[dict]:
    if not subjects:
        raise ValueError("Critical Fault: target_subjects list parameter cannot be empty.")
        
    # Standardize all incoming entity array strings to lowercase tokens cleanly
    target_entities = {s.lower().strip() for s in subjects}
    
    # Automatically add session isolation tables to the targets list if keys match active contexts [🔒]
    for session_key, session_value in session_context.items():
        if session_value is not None and session_value != "" and session_value != [] and session_value != ():
            for ent_name, ent_meta in SCHEMA_CATALOG.get("entities", {}).items():
                if session_key in ent_meta.get("allowed_columns", {}):
                    target_entities.add(ent_name)

    # =============================================================================
    # ─── 1. DETERMINISTIC DYNAMIC FACT TABLE DENSITY MATRIX SELECTION ───
    # =============================================================================
    # We calculate which active concept holds the highest density of directional connection pathways.
    # That table mathematically wins and is crowned our master driving Fact Table anchor t0! [🔒]
    root_entity = None
    max_relationship_density = -1
    
    for candidate in target_entities:
        relationship_count = len(SCHEMA_CATALOG["entities"].get(candidate, {}).get("relationships", {}))
        if relationship_count > max_relationship_density:
            max_relationship_density = relationship_count
            root_entity = candidate
            
    if not root_entity:
        root_entity = list(target_entities)[0] # Safety boundary fallback
        
    entity_meta = SCHEMA_CATALOG["entities"][root_entity]
    root_table = entity_meta["physical_table"]
    
    # Establish your topological path tracking maps
    alias_map = {root_entity: "t0"}
    join_clauses = []
    alias_count = 1
    select_fields = []

    # =============================================================================
    # ─── 2. MINIMUM SPANNING TREE GRAPH MOUNT PATHFINDER (BFS) ───
    # =============================================================================
    # To prevent your joins from breaking due to array string order anomalies, we trace 
    # paths radiating outward from our root t0 Fact Table anchor systematically [🔒]
    traversal_sequence = [root_entity]
    remaining_targets = list(target_entities - {root_entity})
    
    # Simple Breadth-First Search to order connections topologically relative to graph keys [🔒]
    all_graph_nodes = list(SCHEMA_CATALOG["entities"].keys())
    graph_edges = {node: list(SCHEMA_CATALOG["entities"][node].get("relationships", {}).keys()) for node in all_graph_nodes}
    
    def find_shortest_path(start, end):
        queue = [[start]]
        visited = {start}
        while queue:
            current_path = queue.pop(0)
            current_node = current_path[-1]
            if current_node == end:
                return current_path
            for neighbor in graph_edges.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(current_path + [neighbor])
        return []

    # Build an orderly sequence trace path mapping [🔒]
    while remaining_targets:
        best_segment_path = None
        for active_node in traversal_sequence:
            for target_node in remaining_targets:
                candidate_route = find_shortest_path(active_node, target_node)
                if candidate_route and (not best_segment_path or len(candidate_route) < len(best_segment_path)):
                    best_segment_path = candidate_route
                    
        if not best_segment_path:
            # Drop unconnected orphan nodes if configuration metadata bridges are missing
            break
            
        for segment_node in best_segment_path:
            if segment_node not in traversal_sequence:
                traversal_sequence.append(segment_node)
            if segment_node in remaining_targets:
                remaining_targets.remove(segment_node)

    # =============================================================================
    # ─── 3. TOPOLOGICAL LEFT JOIN TREE COMPILATION FACTORY ───
    # =============================================================================
    # We walk our sorted topological path array and output index-optimized left-join fragments [🔒]
    for next_entity in traversal_sequence[1:]:
        next_meta = SCHEMA_CATALOG["entities"].get(next_entity)
        next_table = next_meta["physical_table"]
        
        # Discover which previously registered node functions as the parent link for this child branch
        parent_entity = None
        for pre_node in traversal_sequence[:traversal_sequence.index(next_entity)]:
            if next_entity in SCHEMA_CATALOG["entities"][pre_node].get("relationships", {}):
                parent_entity = pre_node
                break
                
        if not parent_entity:
            parent_entity = traversal_sequence[traversal_sequence.index(next_entity) - 1]
            
        parent_alias = alias_map[parent_entity]
        parent_table = SCHEMA_CATALOG["entities"][parent_entity]["physical_table"]
        
        # Check for many-to-many junction bridges first
        lookup_key = f"{parent_entity}.{next_entity}"
        junction_meta = SCHEMA_CATALOG["junction_bridges"].get(lookup_key)
        
        if junction_meta:
            via_table = junction_meta["via_table"]
            j_alias = f"t{alias_count}"
            alias_count += 1
            
            # Substitute explicit text labels inside step 1
            rule_1 = re.sub(rf'\b{parent_table}\b', parent_alias, junction_meta["step_1"])
            rule_1 = re.sub(rf'\b{via_table}\b', j_alias, rule_1)
            join_clauses.append(f"LEFT JOIN {via_table} {j_alias} ON {rule_1}")
            
            # Substitute explicit text labels inside step 2
            next_alias = f"t{alias_count}"
            rule_2 = re.sub(rf'\b{via_table}\b', j_alias, junction_meta["step_2"])
            rule_2 = re.sub(rf'\b{next_table}\b', next_alias, rule_2)
            join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {rule_2}")
            
            alias_map[next_entity] = next_alias
            alias_count += 1
            continue
            
        # Standard direct relationship left-join matching path [🔒]
        join_rule_template = SCHEMA_CATALOG["entities"][parent_entity]["relationships"].get(next_entity)
        if not join_rule_template:
            raise ValueError(f"No valid connection links table concept key '{parent_entity}' to '{next_entity}'")
            
        next_alias = f"t{alias_count}"
        alias_map[next_entity] = next_alias
        
        # Clean rule template fields text smoothly
        clean_rule = re.sub(rf'\b{parent_table}\b', parent_alias, join_rule_template)
        clean_rule = re.sub(rf'\b{next_table}\b', next_alias, clean_rule)
        join_clauses.append(f"LEFT JOIN {next_table} {next_alias} ON {clean_rule}")
        alias_count += 1

    # =============================================================================
    # ─── 4. DYNAMIC SELECT COMPILATION ───
    # =============================================================================
    allowed_cols_dict = entity_meta.get("allowed_columns", {})
    if intent_type == "DATA_AGGREGATION" and semantic_filters:
        allowed_formulas = entity_meta.get("allowed_aggregations", {})
        for op in [f.lower() for f in semantic_filters]:
            formula_meta = allowed_formulas.get(op)
            if not formula_meta:
                continue
            raw_function = formula_meta["sql_function"]
            out_name = formula_meta["output_column"]
            
            if formula_meta.get("requires_column"):
                if aggregation_column in formula_meta.get("allowed_columns", []) and aggregation_column in allowed_cols_dict:
                    compiled_func = raw_function.format(column=f"t0.{aggregation_column}")
                    select_fields.append(f"{compiled_func} AS {out_name}_{aggregation_column}")
            else:
                select_fields.append(f"{raw_function} AS {out_name}")
                
        if not select_fields:
            select_fields.append("COUNT(*) AS count")
    else:
        # Standard data retrieval field selections [🔒]
        for col in allowed_cols_dict.keys():
            if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                select_fields.append(f"t0.{col}")
                
        for entity_name, assigned_alias in alias_map.items():
            if entity_name != root_entity:
                child_meta = SCHEMA_CATALOG["entities"][entity_name]
                child_cols = child_meta.get("allowed_columns", {})
                for col in child_cols.keys():
                    if col not in SCHEMA_CATALOG["safety"]["deny_columns"]:
                        select_fields.append(f"{assigned_alias}.{col} AS {entity_name}_{col}")

    # =============================================================================
    # ─── 5. MULTI-TENANT SESSION CONTEXT GUARD RAIL FILTERS ───
    # =============================================================================
    where_clauses = []
    query_params = {}
    security_group_filters = []
    
    for session_key, session_value in session_context.items():
        if session_value is None or session_value == "" or session_value == [] or session_value == ():
            continue
            
        target_column_name = session_key
        resolved_column_alias = None
        if target_column_name in allowed_cols_dict:
            resolved_column_alias = "t0"
        else:
            for entity_name, assigned_alias in alias_map.items():
                child_meta = SCHEMA_CATALOG["entities"][entity_name]
                child_cols = child_meta.get("allowed_columns", {})
                if target_column_name in child_cols:
                    resolved_column_alias = assigned_alias
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
    if security_group_filters:
        where_clauses.append(" AND ".join(security_group_filters))
    else:
        where_clauses.append("1=1")
    # ================================# 
    # ─── 6. STRICT TYPE-DRIVEN TEXT SEARCH BUILDER ───#
    #  =====================================
    if search_keyword:
        search_clauses = []
        approved_text_types = ["varchar", "text", "char", "string", "timestamp", "datetime"]
        for entity_name, assigned_alias in alias_map.items():
            target_table_meta = SCHEMA_CATALOG["entities"].get(entity_name)
            if not target_table_meta:
                continue
            cols_map = target_table_meta.get("allowed_columns", {})
            for col_name, col_props in cols_map.items():
                column_datatype = str(col_props.get("type", "")).lower()
                if column_datatype in approved_text_types:
                    search_clauses.append(f"{assigned_alias}.{col_name} LIKE %(search)s")
        if search_clauses:
            where_clauses.append(f"({' OR '.join(search_clauses)})")
        query_params["search"] = f"%{search_keyword}%"

    # =============================================================================#
    #  ─── 7. FINAL SQL CONCATENATION & INTERPOLATION LOGGING ───#
    #  =============================================================================
    columns_str = ", ".join(select_fields)
    joins_str = " ".join(join_clauses)
    where_str = " AND ".join(where_clauses)
    if intent_type == "DATA_AGGREGATION":
        final_sql = f"SELECT {columns_str} FROM {root_table} t0 {joins_str} WHERE {where_str};"
    else:
        limit_cap = SCHEMA_CATALOG["safety"]["max_limit_ceiling"]
        final_sql = f"SELECT {columns_str} FROM {root_table} t0 {joins_str} WHERE {where_str} LIMIT {limit_cap};"
    # Interpolate logging view safely using global parameter strings [🔒]
    try:
        formatted_params = {}
        for k, v in query_params.items():
            if isinstance(v, str):
                formatted_params[k] = f"'{v}'"
            elif isinstance(v, tuple):
                formatted_params[k] = "(" + ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in v]) + ")"
            else:
                formatted_params[k] = str(v)
        # Cache text inside a global module variable so execute_graph_tools node can grab it natively!
        global LAST_COMPILED_SQL
        LAST_COMPILED_SQL = final_sql % formatted_params
         # ─── FIXED PERMANENTLY: FORCE THE EXPLICIT INTERPOLATED PRINT OUTPUT LINE NATIVELY ───
        print("\n================ STEP 3: INTERPOLATED QUERY WITH LIVE VALUES ================ ", file=sys.stderr)
        print(LAST_COMPILED_SQL, file=sys.stderr)
        print("=============================================================================\n", file=sys.stderr)
        
    except Exception as parse_err:
        pass
    # Return execution packets back up to LangGraph database connection loops natively [🔒]
    return execute_query(final_sql, query_params)

# --- LOCAL DYNAMIC TESTING HARNESS (100% SELF-CONTAINED) ---
if __name__ == "__main__":
    # 1. FIXED: Inject a safe, local driver placeholder so the test can print with no database connected! [🔒]
    def execute_query(sql_statement: str, params: dict):
        print("🚀 MCP BASE STATUS: Standalone text compilation successful! Ready for replica dispatch.")
        return [{"status": "Success", "rows_staged": 0}]

    # Load your local JSON catalog map directly into memory namespace [CP6]
    load_database_schema_config("database_schema.json")
    
    # Your exact diagnostic scenario test parameters [🔒]
    mock_subjects = ["unit", "site", "site_hours"]
    mock_filters = None
    mock_intent = "DATA_RETRIEVAL"
    test_search_keyword = "Mateo"
    random_session_context = {
        "company_id": None,
        "site_id": [1001005],
    }
    
    print("\n" + "═"*80)
    print("🔬 RUNNING LIVE DYNAMIC METADATA COMPILER HARNESS TEST")
    print("═"*80)
    print(f"📋 Targets Sequence Ingest: {mock_subjects}")
    print(f"🎛️ Operational Modifiers  : {mock_filters}\n")
    
    try:
        # Trigger your multi-intent dynamic factory compilation run [🔒]
        run_compiled_mcp_query(
            subjects=mock_subjects,
            intent_type=mock_intent,
            session_context=random_session_context,
            semantic_filters=mock_filters,
            aggregation_column="details_price",
            search_keyword=test_search_keyword,
        )
        print("🎉 LIVE LOCAL HARNESS EXECUTION COMPLETED WITH 100% SUCCESS!")
    except Exception as e:
        print(f"❌ Local Execution Unit Test Failed: {e}")
        import traceback
        traceback.print_exc()
    print("═"*80 + "\n")
    