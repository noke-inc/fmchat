from mcp_server.auth import resolve_user_sites
from mcp_server.db import execute_query
from mcp_server.config import ALLOWED_TABLES


SENSITIVE_COLUMN_NAMES = {
    "id",
    "uuid",
    "user_id",
    "site_id",
    "company_uuid",
}


def _is_sensitive_column_name(name: str) -> bool:
    lowered = (name or "").strip().lower()
    if lowered in SENSITIVE_COLUMN_NAMES:
        return True
    return lowered.endswith("_id") or lowered.endswith("_uuid")


def _build_in_clause(site_ids: list[int]) -> tuple[str, tuple]:
    """Return (placeholders_str, params_tuple) for a WHERE site_id IN (...) clause."""
    placeholders = ", ".join(["%s"] * len(site_ids))
    return placeholders, tuple(site_ids)


def tool_get_units(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return units from v2_units scoped to the sites assigned to user_id.
    Includes site name and excludes all IDs/UUIDs from the returned fields.
    Raises PermissionError if the user is invalid or has no assigned sites.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"""
        SELECT
            u.name,
            u.rental_state,
            s.name AS site_name
        FROM v2_units u
        LEFT JOIN sites s ON u.site_id = s.id
        WHERE u.site_id IN ({ph})
        LIMIT %s
    """
    return execute_query(sql, params + (limit,))


def tool_get_locks(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return locks scoped to the sites assigned to user_id.
    Includes site name and excludes all IDs/UUIDs from the returned fields.
    NOTE: Assumes v2_locks has a site_id column.
          If it does not, update this query to JOIN through v2_units.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"""
        SELECT
            l.name,
            s.name AS site_name
        FROM v2_locks l
        LEFT JOIN sites s ON l.site_id = s.id
        WHERE l.site_id IN ({ph})
        LIMIT %s
    """
    return execute_query(sql, params + (limit,))


def tool_get_locks_to_units(user_id: int, limit: int = 100) -> list[dict]:
    """
    Return lock-to-unit mappings scoped to the user's sites.
    Joins through v2_units (site_id) since v2_locks_to_units is a join table.
    Excludes all IDs/UUIDs from the returned fields.
    """
    site_ids = resolve_user_sites(user_id)
    ph, params = _build_in_clause(site_ids)
    sql = f"""
        SELECT
            l.name AS lock_name,
            u.name AS unit_name,
            u.rental_state,
            s.name AS site_name
        FROM v2_locks_to_units lu
        JOIN v2_locks l ON lu.lock_id = l.id
        JOIN v2_units u ON lu.unit_id = u.id
        LEFT JOIN sites s ON u.site_id = s.id
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
    rows = execute_query(f"DESCRIBE `{table_name}`")
    return [r for r in rows if not _is_sensitive_column_name(str(r.get("Field", "")))]


def tool_get_sites_by_company(company_uuid: str) -> list[dict]:
    """
    Return all site names for the given company_uuid.
    No user_id required — site list is public for company members.
    """
    sql = "SELECT name FROM sites WHERE company_uuid = %s ORDER BY name"
    return execute_query(sql, (company_uuid,))
