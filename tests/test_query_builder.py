"""
tests/test_query_builder.py

Unit tests for the deterministic query builder.
Tests cover:
  - Aggregation: count, count with group_by, count with filters
  - Search: default columns, explicit columns, filter with auto-correction
  - Auto-correction: enum normalization (free→available), column alias resolution
  - Safety: denied column, unknown entity, unknown column, disallowed operator, bad limit
  - Determinism: identical inputs produce identical SQL
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'eks'))

import pytest
from mcp_server.query_builder import (
    build_aggregate_query,
    build_search_query,
    QueryValidationError,
    PolicyDeniedError,
)

SITE_IDS = [1001009]


# ── Aggregation tests ──────────────────────────────────────────────────────────

class TestAggregateQuery:

    def test_count_units_no_filters(self):
        qr = build_aggregate_query("unit", "count", None, None, None, SITE_IDS)
        assert "COUNT(*)" in qr.sql
        assert "v2_units" in qr.sql
        assert "%s" in qr.sql          # parameterized
        assert not qr.corrections

    def test_count_units_grouped_by_rental_state(self):
        qr = build_aggregate_query("unit", "count", None, ["rental_state"], None, SITE_IDS)
        assert "GROUP BY" in qr.sql
        assert "rental_state" in qr.sql
        assert "ORDER BY" in qr.sql    # deterministic ordering

    def test_count_units_with_filter(self):
        filters = [{"column": "rental_state", "operator": "=", "value": "available"}]
        qr = build_aggregate_query("unit", "count", None, None, filters, SITE_IDS)
        assert "WHERE" in qr.sql
        assert "available" not in qr.sql   # value is parameterized, not inline
        assert "available" in str(qr.params)

    def test_count_units_alias_entity(self):
        # "units" is an alias for "unit"
        qr = build_aggregate_query("units", "count", None, None, None, SITE_IDS)
        assert "v2_units" in qr.sql

    def test_invalid_aggregation_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_aggregate_query("unit", "median", None, None, None, SITE_IDS)
        assert exc.value.code == "invalid_aggregation"

    def test_sum_requires_agg_column(self):
        with pytest.raises(QueryValidationError) as exc:
            build_aggregate_query("unit", "sum", None, None, None, SITE_IDS)
        assert exc.value.code == "missing_agg_column"

    def test_sum_price(self):
        qr = build_aggregate_query("unit", "sum", "details_price", None, None, SITE_IDS)
        assert "SUM(" in qr.sql
        assert "details_price" in qr.sql

    def test_unknown_entity_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_aggregate_query("invoice", "count", None, None, None, SITE_IDS)
        assert exc.value.code == "unknown_entity"

    def test_determinism_same_inputs_same_sql(self):
        qr1 = build_aggregate_query("unit", "count", None, ["rental_state"], None, SITE_IDS)
        qr2 = build_aggregate_query("unit", "count", None, ["rental_state"], None, SITE_IDS)
        assert qr1.sql == qr2.sql
        assert qr1.params == qr2.params


# ── Search tests ───────────────────────────────────────────────────────────────

class TestSearchQuery:

    def test_search_units_defaults(self):
        qr = build_search_query("unit", None, None, None, None, 50, SITE_IDS)
        assert "v2_units" in qr.sql
        assert "LIMIT" in qr.sql
        assert "ORDER BY" in qr.sql

    def test_search_units_explicit_columns(self):
        qr = build_search_query("unit", ["name", "rental_state"], None, None, None, 10, SITE_IDS)
        assert "`v`.`name`" in qr.sql
        assert "`v`.`rental_state`" in qr.sql

    def test_search_with_filter(self):
        filters = [{"column": "rental_state", "operator": "=", "value": "available"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        assert "WHERE" in qr.sql
        assert "available" in str(qr.params)

    def test_search_sort_direction_desc(self):
        qr = build_search_query("unit", None, None, "name", "DESC", 50, SITE_IDS)
        assert "DESC" in qr.sql

    def test_invalid_sort_direction_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_search_query("unit", None, None, "name", "RANDOM", 50, SITE_IDS)
        assert exc.value.code == "invalid_sort_direction"

    def test_limit_too_high_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_search_query("unit", None, None, None, None, 9999, SITE_IDS)
        assert exc.value.code == "invalid_limit"

    def test_limit_too_low_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_search_query("unit", None, None, None, None, 0, SITE_IDS)
        assert exc.value.code == "invalid_limit"

    def test_determinism_same_inputs_same_sql(self):
        qr1 = build_search_query("unit", ["name"], None, "name", "ASC", 50, SITE_IDS)
        qr2 = build_search_query("unit", ["name"], None, "name", "ASC", 50, SITE_IDS)
        assert qr1.sql == qr2.sql
        assert qr1.params == qr2.params


# ── Auto-correction tests ──────────────────────────────────────────────────────

class TestAutoCorrection:

    def test_enum_normalization_free_to_available(self):
        filters = [{"column": "rental_state", "operator": "=", "value": "free"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        # "free" should be normalized to "available" in params
        assert "available" in str(qr.params)
        assert any(c["type"] == "enum_normalization" for c in qr.corrections)

    def test_enum_normalization_rented_to_in_use(self):
        filters = [{"column": "rental_state", "operator": "=", "value": "rented"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        assert "in use" in str(qr.params)

    def test_column_alias_status_resolves_to_rental_state(self):
        filters = [{"column": "status", "operator": "=", "value": "available"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        assert "rental_state" in qr.sql
        assert any(c["type"] == "column_alias" for c in qr.corrections)

    def test_correction_trace_contains_required_fields(self):
        filters = [{"column": "status", "operator": "=", "value": "free"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        for correction in qr.corrections:
            assert "type" in correction
            assert "original" in correction
            assert "resolved" in correction
            assert "reason" in correction


# ── Safety tests ───────────────────────────────────────────────────────────────

class TestSafety:

    def test_denied_column_password_raises(self):
        with pytest.raises(PolicyDeniedError) as exc:
            build_search_query("user", ["password"], None, None, None, 10, SITE_IDS)
        assert exc.value.code == "denied_column"

    def test_denied_column_pin_raises(self):
        with pytest.raises(PolicyDeniedError) as exc:
            build_search_query("user", ["pin"], None, None, None, 10, SITE_IDS)
        assert exc.value.code == "denied_column"

    def test_unknown_column_raises(self):
        with pytest.raises(QueryValidationError) as exc:
            build_search_query("unit", ["nonexistent_col"], None, None, None, 10, SITE_IDS)
        assert exc.value.code == "unknown_column"

    def test_disallowed_operator_raises(self):
        filters = [{"column": "rental_state", "operator": "DROP", "value": "x"}]
        with pytest.raises(PolicyDeniedError) as exc:
            build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        assert exc.value.code == "disallowed_operator"

    def test_sql_injection_in_value_is_parameterized(self):
        # Value is always parameterized; injection payload should never reach SQL text
        filters = [{"column": "name", "operator": "=", "value": "'; DROP TABLE users; --"}]
        qr = build_search_query("unit", None, filters, None, None, 50, SITE_IDS)
        assert "DROP" not in qr.sql
        assert "DROP" in str(qr.params)   # safely in params only

    def test_no_raw_id_columns_in_select(self):
        qr = build_search_query("unit", ["name", "rental_state"], None, None, None, 10, SITE_IDS)
        assert "`v`.`id`" not in qr.sql
        assert "`v`.`uuid`" not in qr.sql

    def test_no_write_statement_allowed(self):
        from mcp_server.db import execute_query
        with pytest.raises(ValueError):
            execute_query("DELETE FROM v2_units WHERE 1=1", ())
