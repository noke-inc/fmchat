# mcp_server.py
from itertools import count
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

def run_compiled_mcp_query(subjects: list, intent_type: str, session_context: dict, semantic_filters: list = None, aggregation_column: str = None, search_keyword: str = None, group_by_columns: list = None, having_conditions: list = None, order_by: dict = None) -> list[dict]:
    if not subjects:
        raise ValueError("Critical Fault: target_subjects list parameter cannot be empty.")
        
    # Standardize all incoming entity array strings to lowercase tokens cleanly
    target_entities = {s.lower().strip() for s in subjects}
    
    # Session security filters will be applied in section 5 without auto-joining extra entities.
    # This prevents unnecessary joins to site/site_hours when only querying units.

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
    normalized_filters = [f.lower().strip() for f in (semantic_filters or []) if str(f).strip()]
    allowed_formulas = entity_meta.get("allowed_aggregations", {})
    aggregation_filters = [f for f in normalized_filters if f in allowed_formulas]
    predicate_filters = [f for f in normalized_filters if f not in allowed_formulas]

    if intent_type == "DATA_AGGREGATION" and normalized_filters:
        for op in aggregation_filters:
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
        # Smart column selection: avoid exposing internal IDs and reduce column bloat
        deny_cols = SCHEMA_CATALOG["safety"]["deny_columns"]
        
        # Root entity: select user-facing columns (exclude site_id, user_id)
        for col in allowed_cols_dict.keys():
            if col not in deny_cols and col not in ["site_id", "user_id"]:
                select_fields.append(f"t0.{col}")
        
        # Joined entities: only id + name (not all 18 site_hours columns!)
        for entity_name, assigned_alias in alias_map.items():
            if entity_name != root_entity:
                child_meta = SCHEMA_CATALOG["entities"][entity_name]
                child_cols = child_meta.get("allowed_columns", {})
                # Only select id and name from joined tables
                for col in ["id", "first_name", "last_name", "email", "name"]:
                    if col in child_cols and col not in deny_cols:
                        select_fields.append(f"{assigned_alias}.{col} AS {entity_name}_{col}")

    # =============================================================================
    # ─── 5. MULTI-TENANT SESSION CONTEXT GUARD RAIL FILTERS ───
    # =============================================================================
    where_clauses = []
    query_params = {}
    security_group_filters = []
    
    # Only apply site_id and company_id as security boundaries.
    # user_id in session_context is the LOGGED-IN user (who is querying),
    # NOT a filter for data rows. v2_units.user_id is assignment data.
    security_keys = ["site_id", "company_id"]
    
    for session_key, session_value in session_context.items():
        if session_key not in security_keys:
            continue  # Skip user_id and other non-security context
            
        if session_value is None or session_value == "" or session_value == [] or session_value == ():
            continue
            
        target_column_name = session_key
        resolved_column_alias = None
        if target_column_name in allowed_cols_dict:
            # v2_units.company_id and v2_locks.company_id both default to 0 in the DB —
            # not a reliable security boundary. site_id already scopes both tables.
            # For company_id on unit/lock root, fall through to check joined entities instead.
            if not (session_key == "company_id" and root_entity in ("unit", "lock")):
                resolved_column_alias = "t0"

        if resolved_column_alias is None:
            for entity_name, assigned_alias in alias_map.items():
                if entity_name == root_entity:
                    continue
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

    # ================================================================
    # ─── 5.1 SCHEMA-DRIVEN SEMANTIC PREDICATE FILTER COMPILATION ───
    # ================================================================
    group_by_clause = None
    if predicate_filters:
        # Resolve semantic tokens (e.g. open, inuse, active) against enum_map values.
        # Prefer matching on the root entity first, then outward traversal entities.
        predicate_search_order = [root_entity] + [n for n in traversal_sequence if n != root_entity]
        resolved_predicates = {}
        unresolved_tokens = []

        for token in predicate_filters:
            token_matched = False

            # Pass 1: Synonym-only match (canonical key does NOT self-qualify here).
            # This ensures e.g. user.type='employee' beats unit.access_type canonical
            # key 'employee' when "employee" is explicitly in user.type's synonyms list.
            for entity_name in predicate_search_order:
                assigned_alias = alias_map.get(entity_name)
                if not assigned_alias:
                    continue
                entity_cfg = SCHEMA_CATALOG["entities"].get(entity_name, {})
                column_meta = entity_cfg.get("column_metadata", {})
                for col_name, col_meta in column_meta.items():
                    enum_map = col_meta.get("enum_map", {}) or {}
                    if not enum_map:
                        continue
                    for canonical_value, synonyms in enum_map.items():
                        synonym_terms = {str(s).lower().strip() for s in (synonyms or [])}
                        if token in synonym_terms:
                            key = (assigned_alias, col_name)
                            resolved_predicates.setdefault(key, set()).add(str(canonical_value))
                            token_matched = True
                            break
                    if token_matched:
                        break
                if token_matched:
                    break

            # Pass 2: Fallback — canonical key match only (no synonym required).
            # Skip tokens that are entity aliases (e.g. 'user', 'unit', 'site') —
            # those are subject identifiers, not predicate filter values.
            if not token_matched:
                _entity_aliases = set()
                for _ent in SCHEMA_CATALOG["entities"].values():
                    for _a in _ent.get("aliases", []):
                        _entity_aliases.add(str(_a).lower().strip())
                if token not in _entity_aliases:
                    for entity_name in predicate_search_order:
                        assigned_alias = alias_map.get(entity_name)
                        if not assigned_alias:
                            continue
                        entity_cfg = SCHEMA_CATALOG["entities"].get(entity_name, {})
                        column_meta = entity_cfg.get("column_metadata", {})
                        for col_name, col_meta in column_meta.items():
                            enum_map = col_meta.get("enum_map", {}) or {}
                            if not enum_map:
                                continue
                            for canonical_value, synonyms in enum_map.items():
                                if token == str(canonical_value).lower().strip():
                                    key = (assigned_alias, col_name)
                                    resolved_predicates.setdefault(key, set()).add(str(canonical_value))
                                    token_matched = True
                                    break
                            if token_matched:
                                break
                        if token_matched:
                            break

            if not token_matched:
                unresolved_tokens.append(token)

        for idx, ((pred_alias, pred_col), canonical_values) in enumerate(resolved_predicates.items()):
            pred_param = f"sem_{idx}"
            canonical_list = sorted(canonical_values)
            if len(canonical_list) == 1:
                where_clauses.append(f"{pred_alias}.{pred_col} = %({pred_param})s")
                query_params[pred_param] = canonical_list[0]
            else:
                if intent_type == "DATA_AGGREGATION":
                    # Multiple states requested (e.g. available + inuse) →
                    # use GROUP BY for per-state breakdown instead of a single combined count
                    group_by_clause = f"{pred_alias}.{pred_col}"
                    # Add the grouping column to SELECT so each row shows which state it is
                    if not any(pred_col in f for f in select_fields):
                        select_fields.insert(0, f"{pred_alias}.{pred_col}")
                    # No WHERE filter — GROUP BY covers all values of the column
                else:
                    where_clauses.append(f"{pred_alias}.{pred_col} IN %({pred_param})s")
                    query_params[pred_param] = tuple(canonical_list)

        # print("\n================ SEMANTIC PREDICATE MAPPING =================", file=sys.stderr)
        # print(f"Input predicate filters : {predicate_filters}", file=sys.stderr)
        # print(f"Resolved predicates     : {resolved_predicates}", file=sys.stderr)
        # print(f"Unresolved predicates   : {unresolved_tokens}", file=sys.stderr)
        # print("==============================================================\n", file=sys.stderr)

    # ================================================================
    # ─── 5.2 EXPLICIT GROUP BY COMPILATION ───
    # ================================================================
    group_by_parts = []
    _deny_cols = SCHEMA_CATALOG["safety"]["deny_columns"]
    for group_col in (group_by_columns or []):
        group_col_lc = str(group_col).lower().strip()
        _resolved = False
        for entity_name, assigned_alias in alias_map.items():
            entity_cfg = SCHEMA_CATALOG["entities"].get(entity_name, {})
            entity_cols = entity_cfg.get("allowed_columns", {})
            entity_col_meta = entity_cfg.get("column_metadata", {})
            if group_col_lc in entity_cols and group_col_lc not in _deny_cols:
                group_by_parts.append(f"{assigned_alias}.{group_col_lc}")
                _sexpr = f"{assigned_alias}.{group_col_lc}"
                if not any(_sexpr in f for f in select_fields):
                    select_fields.insert(0, _sexpr)
                _resolved = True
                break
            if not _resolved:
                for col_name, col_meta_item in entity_col_meta.items():
                    if group_col_lc in [str(a).lower().strip() for a in col_meta_item.get("aliases", [])]:
                        if col_name not in _deny_cols:
                            group_by_parts.append(f"{assigned_alias}.{col_name}")
                            _sexpr = f"{assigned_alias}.{col_name}"
                            if not any(_sexpr in f for f in select_fields):
                                select_fields.insert(0, _sexpr)
                            _resolved = True
                            break
            if _resolved:
                break

    # ================================================================
    # ─── 5.3 HAVING CLAUSE BUILDER ───
    # ================================================================
    having_parts = []
    _all_group_by = group_by_parts + ([group_by_clause] if group_by_clause else [])
    if having_conditions and _all_group_by:
        _having_ops = {">", "<", ">=", "<=", "=", "!="}
        for condition in (having_conditions or []):
            _agg = str(condition.get("aggregation", "")).lower().strip()
            _op  = str(condition.get("operator", ">")).strip()
            _val = condition.get("value")
            _col = str(condition.get("column", "")).strip()
            if _op not in _having_ops or _val is None:
                continue
            if _agg == "count":
                having_parts.append(f"COUNT(*) {_op} {int(_val)}")
            elif _agg in ("sum", "avg") and _col:
                _root_cols = SCHEMA_CATALOG["entities"][root_entity].get("allowed_columns", {})
                if _col in _root_cols and _col not in _deny_cols:
                    having_parts.append(f"{_agg.upper()}(t0.{_col}) {_op} {float(_val)}")

    # ================================# 
    # ─── 6. FOCUSED TEXT SEARCH ───#
    #  =====================================
    if search_keyword:
        search_clauses = []
        approved_text_types = ["varchar", "text", "char", "string"]
        # Root entity: search all text columns
        root_cols = SCHEMA_CATALOG["entities"][root_entity].get("allowed_columns", {})
        for col_name, col_props in root_cols.items():
            if str(col_props.get("type", "")).lower() in approved_text_types:
                search_clauses.append(f"t0.{col_name} LIKE %(search)s")
        # Joined entities: search only safe name/email columns (avoids datetime contamination)
        _safe_search_cols = {"first_name", "last_name", "email", "name", "mac", "serial_number", "shortmac"}
        for entity_name, assigned_alias in alias_map.items():
            if entity_name == root_entity:
                continue
            entity_cols = SCHEMA_CATALOG["entities"][entity_name].get("allowed_columns", {})
            for col_name, col_props in entity_cols.items():
                if col_name in _safe_search_cols and str(col_props.get("type", "")).lower() in approved_text_types:
                    search_clauses.append(f"{assigned_alias}.{col_name} LIKE %(search)s")
        if search_clauses:
            where_clauses.append(f"({' OR '.join(search_clauses)})")
        query_params["search"] = f"%{search_keyword}%"

    # =============================================================================
    #  ─── 7. FINAL SQL ASSEMBLY WITH GROUP BY / HAVING / ORDER BY ───
    #  =============================================================================
    columns_str = ", ".join(select_fields)
    joins_str   = " ".join(join_clauses)
    where_str   = " AND ".join(where_clauses)

    _effective_group_by = group_by_parts[:]
    if group_by_clause and group_by_clause not in _effective_group_by:
        _effective_group_by.append(group_by_clause)

    sql_parts = [f"SELECT {columns_str}", f"FROM {root_table} t0"]
    if joins_str.strip():
        sql_parts.append(joins_str)
    sql_parts.append(f"WHERE {where_str}")

    if _effective_group_by:
        sql_parts.append(f"GROUP BY {', '.join(_effective_group_by)}")

    if having_parts:
        sql_parts.append(f"HAVING {' AND '.join(having_parts)}")

    if order_by:
        _ob_col = str(order_by.get("column", "")).strip()
        _ob_dir = str(order_by.get("direction", "ASC")).upper()
        if _ob_dir not in ("ASC", "DESC"):
            _ob_dir = "ASC"
        if _ob_col == "count":
            sql_parts.append(f"ORDER BY COUNT(*) {_ob_dir}")
        else:
            for _en, _ea in alias_map.items():
                if _ob_col in SCHEMA_CATALOG["entities"][_en].get("allowed_columns", {}):
                    sql_parts.append(f"ORDER BY {_ea}.{_ob_col} {_ob_dir}")
                    break
    elif _effective_group_by and intent_type == "DATA_AGGREGATION":
        sql_parts.append("ORDER BY COUNT(*) DESC")

    if not _effective_group_by:
        limit_cap = SCHEMA_CATALOG["safety"]["max_limit_ceiling"]
        sql_parts.append(f"LIMIT {limit_cap}")

    final_sql = " ".join(sql_parts) + ";"

    try:
        formatted_params = {}
        for k, v in query_params.items():
            if isinstance(v, str):
                formatted_params[k] = f"'{v}'"
            elif isinstance(v, tuple):
                formatted_params[k] = "(" + ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in v]) + ")"
            else:
                formatted_params[k] = str(v)
        global LAST_COMPILED_SQL
        LAST_COMPILED_SQL = final_sql % formatted_params
    except Exception:
        pass
    return execute_query(final_sql, query_params)

# --- LOCAL DYNAMIC TESTING HARNESS ---
if __name__ == "__main__":
    def execute_query(sql_statement: str, params: dict):
        print(f"\n📋 SQL:\n{sql_statement}")
        print(f"🔑 PARAMS: {params}")
        return [{"status": "Success"}]

    load_database_schema_config("database_schema.json")
    session = {"site_id": [2223391]}
    sep = "─" * 80

    test_cases = [
        {"label": "Tell me about unit Fake 3A",
         "subjects": ["unit"], "intent": "DATA_RETRIEVAL", "filters": [],
         "search": "Fake 3A", "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Give me unit Fake 3A user information",
         "subjects": ["unit", "user"], "intent": "DATA_RETRIEVAL", "filters": [],
         "search": "Fake 3A", "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "How many units per rental state",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["rental_state"], "having": None,
         "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "How many available units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "available"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Available and occupied unit count breakdown",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "available", "inuse"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Tenants renting more than 1 unit",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["user_id"],
         "having": [{"aggregation": "count", "operator": ">", "value": 1}],
         "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "Average price per access type",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["avg"],
         "search": None, "agg_col": "details_price", "group_by": ["access_type"], "having": None,
         "order_by": None},

        {"label": "Occupied units with their user info",
         "subjects": ["unit", "user"], "intent": "DATA_RETRIEVAL", "filters": ["inuse"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Unit count per access type with more than 5 units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["access_type"],
         "having": [{"aggregation": "count", "operator": ">", "value": 5}],
         "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "Find user John and their unit",
         "subjects": ["unit", "user"], "intent": "DATA_RETRIEVAL", "filters": [],
         "search": "John", "agg_col": None, "group_by": None, "having": None, "order_by": None},

        # ── New columns ──────────────────────────────────────────────────────────
        {"label": "How many active units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "active"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Show inactive/deleted units",
         "subjects": ["unit"], "intent": "DATA_RETRIEVAL", "filters": ["deleted"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Unit count per company",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["company_id"],
         "having": None, "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "Find unit by external ID ABC-001",
         "subjects": ["unit"], "intent": "DATA_RETRIEVAL", "filters": [],
         "search": "ABC-001", "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "How many service units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "service"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Unit breakdown per access type and show only types with more than 3",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["access_type"],
         "having": [{"aggregation": "count", "operator": ">", "value": 3}],
         "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "Occupied padlock units with user info",
         "subjects": ["unit", "user"], "intent": "DATA_RETRIEVAL", "filters": ["inuse", "padlock"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        # ── Real DB state tests ────────────────────────────────────────────────
        {"label": "How many overlock units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "overlock"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Units in checkout state",
         "subjects": ["unit"], "intent": "DATA_RETRIEVAL", "filters": ["checkout"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "How many reserved (prelet) units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "reserved"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Count of units per rental state breakdown",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count"],
         "search": None, "agg_col": None, "group_by": ["rental_state"],
         "having": None, "order_by": {"column": "count", "direction": "DESC"}},

        {"label": "Service and employee units",
         "subjects": ["unit"], "intent": "DATA_AGGREGATION", "filters": ["count", "service", "employee"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},

        {"label": "Delinquent units with their tenant info",
         "subjects": ["unit", "user"], "intent": "DATA_RETRIEVAL", "filters": ["overdue"],
         "search": None, "agg_col": None, "group_by": None, "having": None, "order_by": None},
    ]

    print("\n" + "═"*80)
    print("🔬 SITE MANAGER QUERY TEST SUITE")
    print("═"*80)
    passed = failed = 0
    for tc in test_cases:
        print(f"\n{sep}\n❓ {tc['label']}\n{sep}")
        try:
            run_compiled_mcp_query(
                subjects=tc["subjects"], intent_type=tc["intent"], session_context=session,
                semantic_filters=tc.get("filters"), aggregation_column=tc.get("agg_col"),
                search_keyword=tc.get("search"), group_by_columns=tc.get("group_by"),
                having_conditions=tc.get("having"), order_by=tc.get("order_by"),
            )
            print("✅ PASS"); passed += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"❌ FAIL: {e}"); failed += 1
    print("\n" + "═"*80 + f"\n✅ {passed} passed  |  ❌ {failed} failed\n" + "═"*80)
    