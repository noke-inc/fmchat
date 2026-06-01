from mcp_server.auth import resolve_user_sites
from mcp_server.db import execute_query
from mcp_server.config import ALLOWED_TABLES


def _build_in_clause(site_ids: list[int]) -> tuple[str, tuple]:
    """Return (placeholders_str, params_tuple) for a WHERE site_id IN (...) clause."""
    placeholders = ", ".join(["%s"] * len(site_ids))
    return placeholders, tuple(site_ids)


def tool_get_units(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return rows from v2_units scoped to the sites assigned to user_id.
    Raises PermissionError if the user is invalid or has no assigned sites.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"SELECT * FROM v2_units WHERE site_id IN ({ph}) LIMIT %s"
    return execute_query(sql, params + (limit,))


def tool_get_locks(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return rows from v2_locks scoped to the sites assigned to user_id.
    NOTE: Assumes v2_locks has a site_id column.
          If it does not, update this query to JOIN through v2_units.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"SELECT * FROM v2_locks WHERE site_id IN ({ph}) LIMIT %s"
    return execute_query(sql, params + (limit,))


def tool_get_locks_to_units(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return rows from v2_locks_to_units scoped to the user's sites.
    Joins through v2_units (site_id) since v2_locks_to_units is a join table.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"""
        SELECT lu.*
        FROM v2_locks_to_units lu
        JOIN v2_units u ON lu.unit_id = u.id
        WHERE u.site_id IN ({ph})
        LIMIT %s
    """
    return execute_query(sql, params + (limit,))


def tool_describe_table(table_name: str) -> list[dict]:
    """
    Return the column schema for a whitelisted table.
    No user_id required — this is a metadata-only call.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError(
            f"Table '{table_name}' is not allowed. Permitted tables: {sorted(ALLOWED_TABLES)}"
        )
    return execute_query(f"DESCRIBE `{table_name}`")
