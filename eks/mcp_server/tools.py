from __future__ import annotations

from mcp_server.auth import resolve_user_sites
from mcp_server.db import execute_query
from mcp_server.query_builder import (
    build_aggregate_query,
    build_search_query,
    QueryValidationError,
    PolicyDeniedError,
)


# ── Generic tools (aggregate_query + search_records) ─────────────────────────

def tool_aggregate_query(
    user_id: int,
    entity: str,
    aggregation: str,
    agg_column: str | None = None,
    group_by: list[str] | None = None,
    filters: list[dict] | None = None,
) -> dict:
    """
    Run a deterministic aggregation (count/sum/avg) over an entity scoped to the
    calling user's sites.

    Returns a dict with keys:
      - results      : list of row dicts
      - corrections  : list of auto-correction records applied
      - metadata     : entity, aggregation, physical_table info
      - error        : present only on validation/policy failure
    """
    try:
        site_ids = resolve_user_sites(user_id)
        qr = build_aggregate_query(
            entity=entity,
            aggregation=aggregation,
            agg_column=agg_column,
            group_by=group_by,
            filters=filters,
            site_ids=site_ids,
        )
        rows = execute_query(qr.sql, qr.params)
        return {
            "results": rows,
            "corrections": qr.corrections,
            "metadata": qr.metadata,
        }
    except (QueryValidationError, PolicyDeniedError) as exc:
        return {"error": str(exc), "code": exc.code, "results": [], "corrections": []}
    except PermissionError as exc:
        return {"error": str(exc), "code": "permission_denied", "results": [], "corrections": []}


def tool_search_records(
    user_id: int,
    entity: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    sort_column: str | None = None,
    sort_direction: str | None = None,
    limit: int = 50,
) -> dict:
    """
    Retrieve records for an entity scoped to the calling user's sites.

    Returns a dict with keys:
      - results      : list of row dicts
      - corrections  : list of auto-correction records applied
      - metadata     : entity, columns, limit info
      - error        : present only on validation/policy failure
    """
    try:
        site_ids = resolve_user_sites(user_id)
        qr = build_search_query(
            entity=entity,
            columns=columns,
            filters=filters,
            sort_column=sort_column,
            sort_direction=sort_direction,
            limit=limit,
            site_ids=site_ids,
        )
        rows = execute_query(qr.sql, qr.params)
        return {
            "results": rows,
            "corrections": qr.corrections,
            "metadata": qr.metadata,
        }
    except (QueryValidationError, PolicyDeniedError) as exc:
        return {"error": str(exc), "code": exc.code, "results": [], "corrections": []}
    except PermissionError as exc:
        return {"error": str(exc), "code": "permission_denied", "results": [], "corrections": []}
