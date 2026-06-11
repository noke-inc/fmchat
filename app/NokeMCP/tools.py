from auth.db_user import resolve_user_sites
from config import ALLOWED_TABLES
from db import execute_query


def _build_in_clause(site_ids: list[int]) -> tuple[str, tuple]:
    """Return (placeholders_str, params_tuple) for a WHERE site_id IN (...) clause."""
    placeholders = ", ".join(["%s"] * len(site_ids))
    return placeholders, tuple(site_ids)


def tool_get_units(user_id: int, limit: int = 100) -> list[dict]:
    """Return storage units scoped to the sites assigned to this user."""
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"SELECT * FROM v2_units WHERE site_id IN ({ph}) LIMIT %s"
    return execute_query(sql, params + (limit,))


def tool_get_locks(user_id: int, limit: int = 100) -> list[dict]:
    """Return locks scoped to the sites assigned to this user."""
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"SELECT * FROM v2_locks WHERE site_id IN ({ph}) LIMIT %s"
    return execute_query(sql, params + (limit,))


def tool_get_locks_to_units(user_id: int, limit: int = 100) -> list[dict]:
    """Return lock-to-unit assignments scoped to the user's sites."""
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
    """Return the column schema for a whitelisted table."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(
            f"Table '{table_name}' is not allowed. "
            f"Permitted tables: {sorted(ALLOWED_TABLES)}"
        )
    return execute_query(f"DESCRIBE `{table_name}`")
