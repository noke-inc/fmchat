"""
mcp_server/query_builder.py

Deterministic query builder for the Noke MCP server.

Responsibilities
────────────────
1. Load and cache schema.json (physical + semantic + aggregation metadata).
2. Resolve semantic entity/column aliases → physical table/column names.
3. Apply auto-correction rules (enum normalization, synonym mapping).
4. Build parameterized SQL for aggregate_query and search_records.
5. Enforce all safety constraints from the schema (operators, limits, joins).
6. Return a QueryResult with the SQL, params, corrections applied, and metadata.

Design goals
────────────
- Identical inputs ALWAYS produce identical SQL (deterministic).
- All corrections are recorded in QueryResult.corrections for observability.
- Rejects anything not explicitly allowed; never silently broadens scope.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import params

# ── Schema loading ─────────────────────────────────────────────────────────────

_SCHEMA_PATH = Path(__file__).parent / "schema.json"
_SCHEMA: dict | None = None


def _get_schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        with _SCHEMA_PATH.open() as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


# ── Error taxonomy ─────────────────────────────────────────────────────────────

class QueryValidationError(ValueError):
    """Input failed schema/safety validation.  code is machine-readable."""
    def __init__(self, message: str, code: str = "validation_error"):
        super().__init__(message)
        self.code = code


class PolicyDeniedError(PermissionError):
    """Request violates a safety policy (e.g. denied column, disallowed operator)."""
    def __init__(self, message: str, code: str = "policy_denied"):
        super().__init__(message)
        self.code = code


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class QueryResult:
    sql: str
    params: tuple
    corrections: list[dict] = field(default_factory=list)   # auto-correction trace
    metadata: dict = field(default_factory=dict)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_entity(raw: str) -> str:
    """Map a semantic entity name/alias → physical table name. Raises on unknown."""
    schema = _get_schema()
    raw_lower = raw.strip().lower()
    for entity_key, entity_def in schema["semantic_layer"]["entities"].items():
        aliases = [a.lower() for a in entity_def.get("aliases", [])]
        if raw_lower in aliases or raw_lower == entity_key:
            return entity_def["physical_table"]
    raise QueryValidationError(
        f"Unknown entity '{raw}'. Allowed: {list(schema['semantic_layer']['entities'].keys())}",
        code="unknown_entity",
    )


def _resolve_column(raw: str, physical_table: str) -> tuple[str, list[dict]]:
    """
    Map a semantic column alias → physical column name on physical_table.
    Returns (physical_column, corrections_list).
    """
    schema = _get_schema()
    raw_lower = raw.strip().lower()
    corrections: list[dict] = []

    # Check direct match first
    phys_cols = schema["physical_schema"].get(physical_table, {}).get("columns", {})
    if raw_lower in phys_cols:
        _assert_column_exposed(raw_lower, physical_table, phys_cols)
        return raw_lower, corrections

    # Try semantic alias map
    for col_key, col_def in schema["semantic_layer"]["columns"].items():
        aliases = [a.lower() for a in col_def.get("aliases", [])]
        if raw_lower in aliases:
            # Verify physical col exists on this table
            if col_key in phys_cols:
                _assert_column_exposed(col_key, physical_table, phys_cols)
                if raw_lower != col_key:
                    corrections.append({
                        "type": "column_alias",
                        "original": raw,
                        "resolved": col_key,
                        "reason": f"'{raw}' is an alias for column '{col_key}'",
                    })
                return col_key, corrections

    raise QueryValidationError(
        f"Column '{raw}' not found on entity '{physical_table}'. "
        f"Exposed columns: {[c for c, d in phys_cols.items() if d.get('expose')]}",
        code="unknown_column",
    )


def _assert_column_exposed(col: str, table: str, phys_cols: dict) -> None:
    schema = _get_schema()
    denied = schema["safety"]["deny_columns"]
    if col in denied:
        raise PolicyDeniedError(f"Column '{col}' is not permitted.", code="denied_column")
    if not phys_cols.get(col, {}).get("expose", True):
        raise PolicyDeniedError(f"Column '{col}' is not exposed.", code="denied_column")


def _normalize_filter_value(column: str, value: Any) -> tuple[Any, list[dict]]:
    """Apply enum normalization for known columns. Returns (normalized_value, corrections)."""
    schema = _get_schema()
    corrections: list[dict] = []
    col_meta = schema["semantic_layer"]["columns"].get(column, {})
    enum_map = col_meta.get("enum_map", {})
    if isinstance(value, str) and value.lower() in enum_map:
        normalized = enum_map[value.lower()]
        corrections.append({
            "type": "enum_normalization",
            "column": column,
            "original": value,
            "resolved": normalized,
            "reason": f"'{value}' normalized to '{normalized}' per semantic layer",
        })
        return normalized, corrections
    return value, corrections


def _validate_operator(op: str) -> str:
    schema = _get_schema()
    allowed = schema["safety"]["allowed_operators"]
    if op.upper() not in [a.upper() for a in allowed]:
        raise PolicyDeniedError(
            f"Operator '{op}' is not allowed. Allowed: {allowed}",
            code="disallowed_operator",
        )
    return op.upper()


def _validate_limit(limit: int) -> int:
    schema = _get_schema()
    agg_meta = schema["aggregation_metadata"]["pagination"]
    min_l = agg_meta["min_limit"]
    max_l = agg_meta["max_limit"]
    if not (min_l <= limit <= max_l):
        raise QueryValidationError(
            f"limit must be between {min_l} and {max_l}, got {limit}.",
            code="invalid_limit",
        )
    return limit


def _build_where(
    filters: list[dict],
    physical_table: str,
    table_alias: str,
) -> tuple[str, tuple, list[dict]]:
    """
    Build a parameterized WHERE clause from a list of filter dicts.

    Each filter: {"column": str, "operator": str, "value": Any}
    Returns (where_clause_str, params_tuple, corrections).
    """
    if not filters:
        return "", (), []

    parts: list[str] = []
    params: list[Any] = []
    all_corrections: list[dict] = []

    for f in filters:
        raw_col = f.get("column", "")
        op = f.get("operator", "=")
        value = f.get("value")

        physical_col, col_corrections = _resolve_column(raw_col, physical_table)
        all_corrections.extend(col_corrections)
        op = _validate_operator(op)
        value, val_corrections = _normalize_filter_value(physical_col, value)
        all_corrections.extend(val_corrections)

        qualified = f"`{table_alias}`.`{physical_col}`"

        if op in ("IN", "NOT IN"):
            if not isinstance(value, list):
                value = [value]
            ph = ", ".join(["%s"] * len(value))
            parts.append(f"{qualified} {op} ({ph})")
            params.extend(value)
        elif op == "BETWEEN":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise QueryValidationError(
                    f"BETWEEN requires a list of exactly 2 values, got: {value}",
                    code="invalid_filter_value",
                )
            parts.append(f"{qualified} BETWEEN %s AND %s")
            params.extend(value)
        elif op == "LIKE":
            parts.append(f"{qualified} LIKE %s")
            params.append(value)
        else:
            parts.append(f"{qualified} {op} %s")
            params.append(value)

    return "WHERE " + " AND ".join(parts), tuple(params), all_corrections


def _site_scope_join(physical_table: str, table_alias: str, site_ids: list[int]) -> tuple[str, str, tuple]:
    """
    Return (join_clause, scope_where_clause, scope_params) that constrains
    rows to those accessible by the calling user's site_ids.
    """
    if not site_ids:
        return "", "", ()
    
    schema = _get_schema()
    phys = schema["physical_schema"].get(physical_table, {})
    scope_col = phys.get("scope_column")
       

    if scope_col:
        ph = ", ".join(["%s"] * len(site_ids))
        return (
            "",                                                    # no extra join needed
            f"AND `{table_alias}`.`{scope_col}` IN ({ph})",
            tuple(site_ids),
        )

    # users table — no direct site_id; scope via users_roles
    if physical_table == "users":
        ph = ", ".join(["%s"] * len(site_ids))
        join_clause = (
            f"INNER JOIN `users_roles` ur ON ur.`user_id` = `{table_alias}`.`id` "
            f"AND ur.`site_id` IN ({ph})"
        )
        return join_clause, "", tuple(site_ids)

    return "", "", ()


# ── Public API ─────────────────────────────────────────────────────────────────

def build_aggregate_query(
    entity: str,
    aggregation: str,
    agg_column: str | None = None,
    group_by: list[str] | None = None,
    filters: list[dict] | None = None,
    site_ids: list[int] = None,
) -> QueryResult:
    """
    Build a deterministic parameterized aggregation query.

    Parameters
    ──────────
    entity       : semantic entity name (e.g. "unit", "user")
    aggregation  : "count" | "sum" | "avg"
    agg_column   : required for sum/avg; ignored for count
    group_by     : list of semantic column names to group by
    filters      : list of {"column", "operator", "value"} dicts
    site_ids     : resolved site IDs for scoping (from resolve_user_sites)
    """
    schema = _get_schema()
    
   # ✅ ADD THIS BLOCK (critical fix)
    group_by = group_by or []
    filters = filters or []
    site_ids = site_ids or []

    corrections: list[dict] = []

    # --- resolve entity
    physical_table = _resolve_entity(entity)
    table_alias = physical_table[0]   # single-letter alias e.g. "v" for v2_units

    # --- validate aggregation
    agg_meta = schema["aggregation_metadata"]["allowed_aggregations"]
    agg_lower = aggregation.strip().lower()
    if agg_lower not in agg_meta:
        raise QueryValidationError(
            f"Aggregation '{aggregation}' not allowed. Allowed: {list(agg_meta.keys())}",
            code="invalid_aggregation",
        )
    agg_def = agg_meta[agg_lower]

    # --- build SELECT expression
    if agg_lower == "count":
        select_expr = f"COUNT(*) AS `count`"
    else:
        if not agg_column:
            raise QueryValidationError(
                f"'{agg_lower}' requires 'agg_column'.", code="missing_agg_column"
            )
        phys_col, col_corr = _resolve_column(agg_column, physical_table)
        corrections.extend(col_corr)
        allowed_cols = agg_def.get("allowed_columns", [])
        if allowed_cols and phys_col not in allowed_cols:
            raise PolicyDeniedError(
                f"Column '{phys_col}' not allowed for {agg_lower}. Allowed: {allowed_cols}",
                code="policy_denied",
            )
        func = agg_def["sql_function"].format(column=f"`{table_alias}`.`{phys_col}`")
        out_col = agg_def["output_column"]
        select_expr = f"{func} AS `{out_col}`"

    # --- group_by
    group_by = group_by or []
    resolved_groups: list[str] = []
    for g in group_by:
        if g == "site_name":
            # site_name comes from joined sites table
            resolved_groups.append("`s`.`name`")
            select_expr = f"`s`.`name` AS `site_name`, {select_expr}"
        else:
            phys_g, g_corr = _resolve_column(g, physical_table)
            corrections.extend(g_corr)
            allowed_groups = schema["aggregation_metadata"]["allowed_group_by"].get(physical_table, [])
            if phys_g not in allowed_groups and "site_name" not in allowed_groups:
                raise QueryValidationError(
                    f"group_by column '{g}' not allowed for {physical_table}. Allowed: {allowed_groups}",
                    code="invalid_group_by",
                )
            resolved_groups.append(f"`{table_alias}`.`{phys_g}`")
            if f"`{table_alias}`.`{phys_g}`" not in select_expr:
                select_expr = f"`{table_alias}`.`{phys_g}`, {select_expr}"

    # --- site scope join
    scope_join, scope_where, scope_params = _site_scope_join(physical_table, table_alias, site_ids)

    # --- sites join (for site_name in group_by or select)
    sites_join = ""
    if "site_name" in (group_by or []) or physical_table == "v2_units":
        sites_join = f"LEFT JOIN `sites` s ON `{table_alias}`.`site_id` = s.`id`"

    # --- filter WHERE
    where_clause, filter_params, filter_corrections = _build_where(
        filters or [], physical_table, table_alias
    )
    corrections.extend(filter_corrections)

    # --- combine WHERE + scope
    if where_clause and scope_where:
        combined_where = where_clause + " " + scope_where
    elif scope_where:
        combined_where = "WHERE 1=1 " + scope_where
    else:
        combined_where = where_clause

    # --- GROUP BY / ORDER BY (deterministic)
    group_clause = f"GROUP BY {', '.join(resolved_groups)}" if resolved_groups else ""
    sort_defaults = schema["aggregation_metadata"]["default_sort"]["aggregation"]
    order_col = sort_defaults["column"]
    order_dir = sort_defaults["direction"]
    tiebreak = sort_defaults["tiebreak"]
    order_clause = f"ORDER BY `{order_col}` {order_dir}"
    if tiebreak and resolved_groups:
        order_clause += f", {tiebreak}"

    # --- assemble
    sql_parts = [
        f"SELECT {select_expr}",
        f"FROM `{physical_table}` {table_alias}",
    ]
    if scope_join:
        sql_parts.append(scope_join)
    if sites_join:
        sql_parts.append(sites_join)
    if combined_where:
        sql_parts.append(combined_where)
    if group_clause:
        sql_parts.append(group_clause)
    sql_parts.append(order_clause)

    sql = "\n".join(sql_parts)
    # params = scope_params + filter_params
    params = filter_params + scope_params if scope_where else scope_params + filter_params
    print(sql, "aggregate params", params)

    return QueryResult(
        sql=sql,
        params=params,
        corrections=corrections,
        metadata={"entity": entity, "physical_table": physical_table, "aggregation": agg_lower},
    )


def build_search_query(
    entity: str,
    columns: list[str] | None,
    filters: list[dict] | None,
    sort_column: str | None,
    sort_direction: str | None,
    limit: int,
    site_ids: list[int],
) -> QueryResult:
    """
    Build a deterministic parameterized SELECT query for record retrieval.

    Parameters
    ──────────
    entity         : semantic entity name
    columns        : list of semantic column names to return (None = defaults)
    filters        : list of {"column", "operator", "value"} dicts
    sort_column    : semantic column name to sort by (None = schema default)
    sort_direction : "ASC" | "DESC" (None = schema default)
    limit          : number of rows (validated against schema bounds)
    site_ids       : resolved site IDs for scoping
    """
    schema = _get_schema()
    corrections: list[dict] = []

    # --- resolve entity
    physical_table = _resolve_entity(entity)
    table_alias = physical_table[0]

    # --- validate limit
    limit = _validate_limit(limit)
    print(limit)
    # --- resolve columns
    entity_key = next(
        k for k, v in schema["semantic_layer"]["entities"].items()
        if v["physical_table"] == physical_table
    )
    default_cols = schema["semantic_layer"]["entities"][entity_key]["default_exposed_columns"]
    raw_columns = columns if columns else default_cols

    select_parts: list[str] = []
    for raw_col in raw_columns:
        if raw_col == "site_name":
            select_parts.append("`s`.`name` AS `site_name`")
        else:
            phys_col, col_corr = _resolve_column(raw_col, physical_table)
            corrections.extend(col_corr)
            select_parts.append(f"`{table_alias}`.`{phys_col}`")

    select_expr = ", ".join(select_parts) if select_parts else f"`{table_alias}`.*"

    # --- site scope join
    scope_join, scope_where, scope_params = _site_scope_join(physical_table, table_alias, site_ids)

    # --- sites join when site_name is requested
    sites_join = ""
    if "site_name" in (raw_columns or []) or physical_table == "v2_units":
        sites_join = f"LEFT JOIN `sites` s ON `{table_alias}`.`site_id` = s.`id`"

    # --- filter WHERE
    where_clause, filter_params, filter_corrections = _build_where(
        filters or [], physical_table, table_alias
    )
    corrections.extend(filter_corrections)

    if where_clause and scope_where:
        combined_where = where_clause + " " + scope_where
    elif scope_where:
        combined_where = "WHERE 1=1 " + scope_where
    else:
        combined_where = where_clause

    # --- ORDER BY (deterministic default)
    sort_defaults = schema["aggregation_metadata"]["default_sort"]["search"]
    resolved_sort_col = sort_defaults["column"]
    if sort_column:
        if sort_column == "site_name":
            resolved_sort_col = "s`.`name"   # will be wrapped below
        else:
            resolved_sort_col, sort_corr = _resolve_column(sort_column, physical_table)
            corrections.extend(sort_corr)

    direction = "ASC"
    if sort_direction:
        direction = sort_direction.upper()
        if direction not in ("ASC", "DESC"):
            raise QueryValidationError(
                f"sort_direction must be 'ASC' or 'DESC', got '{sort_direction}'.",
                code="invalid_sort_direction",
            )

    if sort_column == "site_name":
        order_clause = f"ORDER BY `s`.`name` {direction}"
    else:
        order_clause = f"ORDER BY `{table_alias}`.`{resolved_sort_col}` {direction}"

    # --- assemble
    sql_parts = [
        f"SELECT {select_expr}",
        f"FROM `{physical_table}` {table_alias}",
    ]
    if scope_join:
        sql_parts.append(scope_join)
    if sites_join:
        sql_parts.append(sites_join)
    if combined_where:
        sql_parts.append(combined_where)
    sql_parts.append(order_clause)
    sql_parts.append(f"LIMIT %s")

    sql = "\n".join(sql_parts)
   # params = scope_params + filter_params + (limit,)
    params = filter_params + scope_params + (limit,) if scope_where else scope_params + filter_params + (limit,)
    print(sql, "params", params)
    return QueryResult(
        sql=sql,
        params=params,
        corrections=corrections,
        metadata={
            "entity": entity,
            "physical_table": physical_table,
            "limit": limit,
            "columns": raw_columns,
        },
    )
