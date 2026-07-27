"""
tests/test_engine_scenarios.py

Comprehensive SQL-generation tests for data_retrieval_engine.py.

Covers every scenario from the requirements document + reported bugs:
  - Companies, gateways, events (new entities)
  - Users scoped by site_id (not company_id)
  - Gateway queries use gateways table (not v2_locks / v2_units)
  - Battery status queries use v2_locks (not v2_units)
  - "last N activities" → DATA_RETRIEVAL + ORDER BY created_at DESC + LIMIT N
  - "rented by / occupied by" → user+unit join
  - "people / person / client" → user entity
  - Follow-up question on zero-row result
  - Entity conflict resolution (gateway vs lock, unit vs lock for battery)

Run from repo root:
    python -m pytest tests/test_engine_scenarios.py -v
  OR directly:
    python tests/test_engine_scenarios.py
"""

import sys
import os
import re
import json

# ── Path setup ────────────────────────────────────────────────────────────────
MCP_DIR = os.path.join(os.path.dirname(__file__), "..", "eks", "mcp_server")
sys.path.insert(0, os.path.abspath(MCP_DIR))
os.chdir(os.path.abspath(MCP_DIR))

import data_retrieval_engine as dre

# Load schema once
dre.load_database_schema_config("database_schema.json")

# ── DB mocking ────────────────────────────────────────────────────────────────
_calls: list[tuple] = []

def _mock_main(sql, params):
    _calls.append(("main", sql.strip(), params))
    return []

def _mock_activity(sql, params):
    _calls.append(("activity", sql.strip(), params))
    return []

dre.execute_query = _mock_main
dre.execute_activity_query = _mock_activity

SESSION = {"site_id": [2223391], "company_id": [1000241]}


def run(subjects, intent, filters=None, search=None, group_by=None,
        having=None, order_by=None, limit=None, session=None):
    """Helper: run query and return (db_label, raw_sql, compiled_sql, params)."""
    _calls.clear()
    dre.LAST_COMPILED_SQL = ""
    try:
        dre.run_compiled_mcp_query(
            subjects=subjects,
            intent_type=intent,
            session_context=session or SESSION,
            semantic_filters=filters or [],
            search_keyword=search,
            group_by_columns=group_by or [],
            having_conditions=having or [],
            order_by=order_by,
            limit=limit,
        )
    except Exception:
        pass
    compiled = getattr(dre, "LAST_COMPILED_SQL", "")
    if not _calls:
        return None, "", compiled, {}
    db, raw_sql, params = _calls[-1]
    # Use compiled SQL (with values substituted) when available; fall back to raw
    effective_sql = compiled if compiled else raw_sql
    return db, effective_sql, raw_sql, params


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════
PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(name: str, condition: bool, detail: str = ""):
    label = PASS if condition else FAIL
    results.append((label, name, detail))
    if not condition:
        print(f"{FAIL}  {name}")
        if detail:
            print(f"      → {detail}")
    return condition


def sql_contains(sql: str, *fragments: str) -> bool:
    return all(f.lower() in sql.lower() for f in fragments)


def sql_not_contains(sql: str, *fragments: str) -> bool:
    return all(f.lower() not in sql.lower() for f in fragments)


# ══════════════════════════════════════════════════════════════════════════════
# 1. COMPANIES – new entity, no site guard-rail, uuid + id present
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 1. Companies ─────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["company"], "DATA_RETRIEVAL", session={})
check("company uses companies table", sql_contains(sql, "FROM companies"), sql)
check("company does NOT filter by site_id", sql_not_contains(sql, "site_id"), sql)
check("company selects uuid column", sql_contains(sql, "uuid"), sql)
check("company selects name column", sql_contains(sql, "name"), sql)
check("company excludes frontend_host", sql_not_contains(sql, "frontend_host"), sql)
check("company excludes email_template_path", sql_not_contains(sql, "email_template_path"), sql)

db, sql, _raw, _params = run(["company"], "DATA_AGGREGATION", filters=["count"], session={})
check("company count aggregation", sql_contains(sql, "COUNT(*) AS count"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 2. GATEWAYS – new entity, scoped by site_id, specific columns only
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 2. Gateways ──────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count"])
check("gateway uses gateways table (not v2_locks)", sql_contains(sql, "FROM gateways"), sql)
check("gateway does NOT use v2_locks", sql_not_contains(sql, "v2_locks"), sql)
check("gateway does NOT use v2_units", sql_not_contains(sql, "v2_units"), sql)
check("gateway scoped by site_id", sql_contains(sql, "site_id"), sql)
check("gateway uses main DB", db == "main", f"db={db}")

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count", "online"])
check("gateway online filter uses status column", sql_contains(sql, "status"), sql)
check("gateway online filter = 'online'", sql_contains(sql, "'online'"), sql)
check("gateway online does NOT use hw_state", sql_not_contains(sql, "hw_state"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count", "offline"])
check("gateway offline filter = 'offline'", sql_contains(sql, "'offline'"), sql)
check("gateway offline does NOT use hw_state", sql_not_contains(sql, "hw_state"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_RETRIEVAL")
check("gateway retrieval includes name", sql_contains(sql, "name"), sql)
check("gateway retrieval includes status", sql_contains(sql, "status"), sql)
check("gateway retrieval excludes image_url", sql_not_contains(sql, "image_url"), sql)
check("gateway retrieval excludes pagekitename", sql_not_contains(sql, "pagekitename"), sql)
check("gateway retrieval excludes sw_version", sql_not_contains(sql, "sw_version"), sql)
check("gateway retrieval excludes diag_expiration", sql_not_contains(sql, "diag_expiration"), sql)
check("gateway retrieval excludes fw_update_version", sql_not_contains(sql, "fw_update_version"), sql)
check("gateway retrieval excludes notified_delinquent", sql_not_contains(sql, "notified_delinquent"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_RETRIEVAL",
                  order_by={"column": "status", "direction": "DESC"})
check("gateway order by status", sql_contains(sql, "ORDER BY"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION",
                  filters=["count"], group_by=["status"])
check("gateway group by status", sql_contains(sql, "GROUP BY"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 3. EVENTS – smartentry-activity database, site_id_gen scoping
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 3. Events (activity DB) ──────────────────────────────────────────")

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL")
check("event uses activity DB", db == "activity", f"db={db}")
check("event uses events table", sql_contains(sql, "FROM events"), sql)
check("event scoped by site_id_gen", sql_contains(sql, "site_id_gen"), sql)
check("event does NOT scope by company_id", sql_not_contains(sql, "company_id"), sql)

db, sql, _raw, _params = run(["event"], "DATA_AGGREGATION", filters=["count", "unlock"])
check("event unlock filter uses type_gen", sql_contains(sql, "type_gen"), sql)
check("event unlock value is 'unlock'", sql_contains(sql, "'unlock'"), sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  order_by={"column": "created_at", "direction": "DESC"}, limit=5)
check("event last 5 uses LIMIT 5", sql_contains(sql, "LIMIT 5"), sql)
check("event last 5 ORDER BY created_at DESC",
      sql_contains(sql, "created_at") and "DESC" in sql.upper(), sql)
check("event last 5 is NOT COUNT(*)", sql_not_contains(sql, "COUNT(*) AS count"), sql)

db, sql, _raw, _params = run(["event"], "DATA_AGGREGATION",
                  filters=["count"], group_by=["type_gen"])
check("event group by type_gen", sql_contains(sql, "GROUP BY") and "type_gen" in sql, sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL", filters=["lock"])
check("event type lock filter correct", sql_contains(sql, "'lock'") or sql_contains(sql, "type_gen"), sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL", search="employee2")
check("event search keyword propagates", sql_contains(sql, "employee2"), sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  filters=["share"],
                  order_by={"column": "created_at", "direction": "DESC"}, limit=10)
check("event share type with limit 10", sql_contains(sql, "LIMIT 10"), sql)

# Event excluded columns
db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL")
check("event excludes sensor_type_gen", sql_not_contains(sql, "sensor_type_gen"), sql)
check("event excludes by_user_type_gen", sql_not_contains(sql, "by_user_type_gen"), sql)
check("event excludes platform_gen", sql_not_contains(sql, "platform_gen"), sql)
check("event excludes access_type_gen", sql_not_contains(sql, "access_type_gen"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 4. USERS – site scoping via users_roles (not company_id)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 4. Users / Tenants – site scoping ────────────────────────────────")

db, sql, _raw, _params = run(["user"], "DATA_AGGREGATION", filters=["count"])
check("tenant count uses users_roles join", sql_contains(sql, "users_roles"), sql)
check("tenant count scoped by site_id via join", "site_id" in sql, sql)
check("tenant count does NOT filter by company_id", sql_not_contains(sql, "company_id"), sql)
check("tenant count uses main DB", db == "main", f"db={db}")

db, sql, _raw, _params = run(["user"], "DATA_AGGREGATION", filters=["count", "client"])
check("tenant (client) count uses users_roles", sql_contains(sql, "users_roles"), sql)
check("tenant (client) no type filter on users", sql_not_contains(sql, "t0.type"), sql)

db, sql, _raw, _params = run(["user"], "DATA_RETRIEVAL", filters=["active"])
check("active users scoped by site (users_roles)", sql_contains(sql, "users_roles"), sql)
check("active users filter = 'active'", sql_contains(sql, "'active'"), sql)

# employee state scoping
db, sql, _raw, _params = run(["user"], "DATA_AGGREGATION", filters=["count", "employee"])
check("employee count uses users_roles", sql_contains(sql, "users_roles"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 5. LOCKS – battery status queries target v2_locks (not v2_units)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 5. Locks – battery status ─────────────────────────────────────────")

db, sql, _raw, _params = run(["lock"], "DATA_RETRIEVAL", search="Fake 3A")
check("lock battery query uses v2_locks", sql_contains(sql, "FROM v2_locks"), sql)
check("lock battery does NOT use v2_units as root", not sql.lower().startswith("select") or
      sql.lower().split("from")[1].strip().startswith("v2_locks"), sql)
check("lock battery search for Fake 3A", sql_contains(sql, "Fake 3A"), sql)
check("lock battery includes voltage_battery", sql_contains(sql, "voltage_battery"), sql)
check("lock battery includes battery_state", sql_contains(sql, "battery_state"), sql)

db, sql, _raw, _params = run(["lock"], "DATA_AGGREGATION", filters=["count", "offline"])
check("lock offline uses hw_state (not gateway status)", sql_contains(sql, "hw_state"), sql)
check("lock offline value = 'offline'", sql_contains(sql, "'offline'"), sql)

db, sql, _raw, _params = run(["lock"], "DATA_AGGREGATION", filters=["count", "open"])
check("lock open uses hw_state OPEN", sql_contains(sql, "hw_state") and "'OPEN'" in sql, sql)

db, sql, _raw, _params = run(["lock"], "DATA_AGGREGATION", filters=["count", "hold open"])
check("lock holdopen filter", sql_contains(sql, "HOLDOPEN") or sql_contains(sql, "holdopen"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 6. LOCK HW_TYPE – gate/exitgate = entries alias
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 6. Lock hw_type – entries aliases ────────────────────────────────")

catalog = dre.SCHEMA_CATALOG
gate_aliases = catalog["entities"]["lock"]["column_metadata"]["hw_type"]["enum_map"]["gate"]
exitgate_aliases = catalog["entities"]["lock"]["column_metadata"]["hw_type"]["enum_map"]["exitgate"]

check("gate alias includes 'entry'", "entry" in gate_aliases, str(gate_aliases))
check("gate alias includes 'entries'", "entries" in gate_aliases, str(gate_aliases))
check("gate alias includes 'entrance'", "entrance" in gate_aliases, str(gate_aliases))
check("exitgate alias includes 'exit entry'", "exit entry" in exitgate_aliases, str(exitgate_aliases))
check("exitgate alias includes 'exit entries'", "exit entries" in exitgate_aliases, str(exitgate_aliases))

db, sql, _raw, _params = run(["lock"], "DATA_RETRIEVAL", filters=["entries"])
check("lock 'entries' filter resolves to hw_type = gate",
      sql_contains(sql, "hw_type") and ("'gate'" in sql or "gate" in sql), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 7. ENTITY CONFLICT RESOLUTION (gateway vs lock for offline/status queries)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 7. Entity conflict – gateway not confused with lock ───────────────")

# Simulate what the engine does when subjects = ["gateway"] (after agent filtering)
db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count", "offline"])
check("gateway offline uses gateways table (not v2_locks)", sql_contains(sql, "FROM gateways"), sql)
check("gateway offline uses status column", sql_contains(sql, "status"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count", "online"])
check("gateway online uses gateways table", sql_contains(sql, "FROM gateways"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_RETRIEVAL")
check("gateway retrieval root is gateways (not v2_units)", sql_contains(sql, "FROM gateways"), sql)

# When subjects correctly has gateway first, root must be gateway
db, sql, _raw, _params = run(["gateway", "lock"], "DATA_AGGREGATION", filters=["count", "offline"])
check("gateway+lock subjects: gateway is root (first-subject wins)",
      sql_contains(sql, "FROM gateways"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 8. UNITS
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 8. Units ─────────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION", filters=["count"])
check("unit count uses v2_units", sql_contains(sql, "FROM v2_units"), sql)
check("unit count scoped by site_id", sql_contains(sql, "site_id"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION", filters=["count", "available"])
check("unit available count", sql_contains(sql, "'available'"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION", filters=["count", "inuse"])
check("unit occupied count", sql_contains(sql, "'inuse'"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION", filters=["count", "rented"])
check("unit rented→inuse normalized", sql_contains(sql, "'inuse'"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_RETRIEVAL", search="Fake 3A")
check("unit search uses LIKE", sql_contains(sql, "LIKE"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION",
                  filters=["count"], group_by=["rental_state"])
check("unit group by rental_state", sql_contains(sql, "GROUP BY") and "rental_state" in sql, sql)

db, sql, _raw, _params = run(["unit", "user"], "DATA_RETRIEVAL", filters=["inuse"])
check("unit+user join uses users table", sql_contains(sql, "users"), sql)
check("unit+user rental_state filter", sql_contains(sql, "'inuse'"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 9. RENTED BY / OCCUPIED BY – unit+user join with search keyword
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 9. Rented-by / occupied-by queries ───────────────────────────────")

db, sql, _raw, _params = run(["unit", "user"], "DATA_RETRIEVAL",
                  filters=["inuse"], search="employee2")
check("rented-by uses unit+user join", sql_contains(sql, "users"), sql)
check("rented-by search for employee2", sql_contains(sql, "employee2"), sql)
check("rented-by inuse filter applied", sql_contains(sql, "'inuse'"), sql)
check("rented-by root is unit (first subject)", sql_contains(sql, "FROM v2_units"), sql)

db, sql, _raw, _params = run(["unit", "user"], "DATA_RETRIEVAL",
                  filters=["occupied"], search="John")
check("occupied-by search for John", sql_contains(sql, "John"), sql)

# With user as first subject
db, sql, _raw, _params = run(["user", "unit"], "DATA_RETRIEVAL", search="employee2")
check("user-first: root is users table", sql_contains(sql, "FROM users"), sql)
check("user-first: joins units", sql_contains(sql, "v2_units") or sql_contains(sql, "v2_locks_to_units"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 10. LAST N ACTIVITIES – DATA_RETRIEVAL + ORDER BY created_at DESC + LIMIT N
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 10. Last N activities ─────────────────────────────────────────────")

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  order_by={"column": "created_at", "direction": "DESC"}, limit=5)
check("last 5: uses LIMIT 5", "LIMIT 5" in sql, sql)
check("last 5: ORDER BY created_at DESC", "created_at" in sql and "DESC" in sql.upper(), sql)
check("last 5: is NOT aggregation (no COUNT(*))", "COUNT(*)" not in sql, sql)
check("last 5: uses events table", sql_contains(sql, "FROM events"), sql)
check("last 5: uses activity DB", db == "activity", f"db={db}")

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  order_by={"column": "created_at", "direction": "DESC"}, limit=10)
check("last 10 uses LIMIT 10", "LIMIT 10" in sql, sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  order_by={"column": "created_at", "direction": "DESC"}, limit=1)
check("last 1 uses LIMIT 1", "LIMIT 1" in sql, sql)

# Limit respects max_limit_ceiling (50)
db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL",
                  order_by={"column": "created_at", "direction": "DESC"}, limit=100)
check("limit capped at 50", "LIMIT 50" in sql, sql)

# No limit = default 50
db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL")
check("default limit is 50", "LIMIT 50" in sql, sql)


# ══════════════════════════════════════════════════════════════════════════════
# 11. PEOPLE / PERSON / CLIENT / RESIDENTS alias → user entity
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 11. User entity aliases (people, person, client) ─────────────────")

user_aliases = dre.SCHEMA_CATALOG["entities"]["user"]["aliases"]
check("user aliases include 'people'", "people" in user_aliases, str(user_aliases))
check("user aliases include 'person'", "person" in user_aliases, str(user_aliases))
check("user aliases include 'client'", "client" in user_aliases, str(user_aliases))
check("user aliases include 'clients'", "clients" in user_aliases, str(user_aliases))
check("user aliases include 'resident'", "resident" in user_aliases, str(user_aliases))
check("user aliases include 'residents'", "residents" in user_aliases, str(user_aliases))
check("user aliases include 'member'", "member" in user_aliases, str(user_aliases))
check("user aliases include 'rented by'", "rented by" in user_aliases, str(user_aliases))
check("user aliases include 'occupied by'", "occupied by" in user_aliases, str(user_aliases))


# ══════════════════════════════════════════════════════════════════════════════
# 12. UNIT rental_state – generic aliases removed
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 12. Unit rental_state aliases (no generic 'status') ──────────────")

rs_aliases = dre.SCHEMA_CATALOG["entities"]["unit"]["column_metadata"]["rental_state"]["aliases"]
check("rental_state does NOT have generic 'status'", "status" not in rs_aliases, str(rs_aliases))
check("rental_state does NOT have generic 'state'", "state" not in rs_aliases, str(rs_aliases))
check("rental_state keeps 'rental status'", "rental status" in rs_aliases, str(rs_aliases))
check("rental_state keeps 'availability'", "availability" in rs_aliases, str(rs_aliases))
check("rental_state keeps 'occupancy'", "occupancy" in rs_aliases, str(rs_aliases))


# ══════════════════════════════════════════════════════════════════════════════
# 13. ROOT ENTITY SELECTION – first-subject wins
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 13. Root entity selection (first-subject wins) ───────────────────")

db, sql, _raw, _params = run(["gateway"], "DATA_RETRIEVAL")
check("gateway alone: root is gateways", sql_contains(sql, "FROM gateways"), sql)

db, sql, _raw, _params = run(["event"], "DATA_RETRIEVAL")
check("event alone: root is events", sql_contains(sql, "FROM events"), sql)

db, sql, _raw, _params = run(["lock"], "DATA_RETRIEVAL")
check("lock alone: root is v2_locks", sql_contains(sql, "FROM v2_locks"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_RETRIEVAL")
check("unit alone: root is v2_units", sql_contains(sql, "FROM v2_units"), sql)

db, sql, _raw, _params = run(["user"], "DATA_RETRIEVAL")
check("user alone: root is users", sql_contains(sql, "FROM users"), sql)

db, sql, _raw, _params = run(["company"], "DATA_RETRIEVAL", session={})
check("company alone: root is companies", sql_contains(sql, "FROM companies"), sql)

# First-subject wins over relationship-density
db, sql, _raw, _params = run(["lock", "unit"], "DATA_RETRIEVAL")
check("lock,unit: lock is root (first-subject wins)", sql_contains(sql, "FROM v2_locks"), sql)

db, sql, _raw, _params = run(["unit", "lock"], "DATA_RETRIEVAL")
check("unit,lock: unit is root (first-subject wins)", sql_contains(sql, "FROM v2_units"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 14. UUID + ID CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 14. UUID + ID columns ─────────────────────────────────────────────")

gateway_cols = dre.SCHEMA_CATALOG["entities"]["gateway"]["allowed_columns"]
check("gateway has 'id' column", "id" in gateway_cols, str(list(gateway_cols.keys())))
check("gateway has 'uuid' column", "uuid" in gateway_cols, str(list(gateway_cols.keys())))

company_cols = dre.SCHEMA_CATALOG["entities"]["company"]["allowed_columns"]
check("company has 'id' column", "id" in company_cols, str(list(company_cols.keys())))
check("company has 'uuid' column", "uuid" in company_cols, str(list(company_cols.keys())))


# ══════════════════════════════════════════════════════════════════════════════
# 15. SITE HOURS, ROLES, SITES – existing entities still work
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 15. Existing entities unbroken ───────────────────────────────────")

db, sql, _raw, _params = run(["site"], "DATA_RETRIEVAL")
check("site query works", sql_contains(sql, "FROM sites"), sql)

db, sql, _raw, _params = run(["site_hours"], "DATA_RETRIEVAL")
check("site_hours query works", sql_contains(sql, "FROM site_hours_suite"), sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION",
                  filters=["count"], group_by=["access_type"])
check("unit group by access_type", "access_type" in sql and "GROUP BY" in sql, sql)

db, sql, _raw, _params = run(["unit"], "DATA_AGGREGATION", filters=["count", "overlock"])
check("unit overlock filter", "'overlock'" in sql, sql)

db, sql, _raw, _params = run(["unit", "lock"], "DATA_RETRIEVAL", search="3E")
check("unit+lock join search", sql_contains(sql, "v2_locks"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 16. AGENT-LEVEL ENTITY DISCOVERY (agent_graph.py logic tests)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 16. Agent entity discovery (mock) ─────────────────────────────────")

import re as _re

catalog = dre.SCHEMA_CATALOG

def discover_entities(query_text: str) -> tuple[list, list]:
    """Reproduce agent_graph.py entity discovery logic."""
    clean = _re.sub(r'[^\w\s]', ' ', query_text.lower())
    clean = ' '.join(clean.split())
    found = []
    direct = []
    for ename, emeta in catalog.get("entities", {}).items():
        is_active = False
        is_direct = False
        aliases = emeta.get("aliases", []) + [ename]
        for alias in aliases:
            if _re.search(rf'\b{_re.escape(alias.lower())}\b', clean):
                is_active = True
                is_direct = True
                break
        for col, cmeta in emeta.get("column_metadata", {}).items():
            pool = {a.lower() for a in cmeta.get("aliases", [])}
            for cano, syns in cmeta.get("enum_map", {}).items():
                for s in syns:
                    pool.add(s.lower())
            if any(_re.search(rf'\b{_re.escape(t)}\b', clean) for t in pool if t):
                is_active = True
        if is_active:
            found.append(ename)
            if is_direct:
                direct.append(ename)
    return found, direct

def apply_conflict_resolution(discovered, directly_matched):
    """Reproduce agent_graph.py conflict resolution."""
    if not directly_matched or len(discovered) <= len(directly_matched):
        return discovered
    jb = catalog.get("junction_bridges", {})
    filtered = list(directly_matched)
    for ie in discovered:
        if ie in directly_matched:
            continue
        needed = False
        for de in directly_matched:
            if f"{de}.{ie}" in jb or f"{ie}.{de}" in jb:
                needed = True
                break
            if ie in catalog["entities"].get(de, {}).get("relationships", {}):
                needed = True
                break
            if de in catalog["entities"].get(ie, {}).get("relationships", {}):
                needed = True
                break
        if needed:
            filtered.append(ie)
    return filtered

def check_discovery(query, expected_contains=None, expected_not_contains=None,
                     after_resolution_contains=None, after_resolution_not_contains=None):
    found, direct = discover_entities(query)
    resolved = apply_conflict_resolution(found, direct)
    ok = True
    for e in (expected_contains or []):
        if e not in found:
            check(f"'{query}' → discovers {e}", False, f"found={found}")
            ok = False
    for e in (expected_not_contains or []):
        if e in found:
            check(f"'{query}' → raw discovery does NOT include {e}", False, f"found={found}")
            ok = False
    for e in (after_resolution_contains or []):
        if e not in resolved:
            check(f"'{query}' [after resolution] → keeps {e}", False, f"resolved={resolved}")
            ok = False
    for e in (after_resolution_not_contains or []):
        if e in resolved:
            check(f"'{query}' [after resolution] → removes {e}", False, f"resolved={resolved}")
            ok = False
    if ok:
        all_labels = (expected_contains or []) + (after_resolution_contains or [])
        removed_labels = (after_resolution_not_contains or [])
        check(
            f"discovery: '{query}'",
            True,
            f"raw={found}, resolved={resolved}"
        )

# "how many people are in onsite" → user entity
check_discovery("how many people are in onsite",
                after_resolution_contains=["user"])

# "how many people are online" → user entity (not confused with gateway)
check_discovery("how many clients are active",
                after_resolution_contains=["user"])

# "how many gateways are offline" → gateway only (lock filtered out)
check_discovery("how many gateways are offline",
                expected_contains=["gateway"],
                after_resolution_contains=["gateway"],
                after_resolution_not_contains=["lock"])

# "how many gateways and what are those status" → gateway, unit filtered out
check_discovery("how many gateways and what are those status",
                expected_contains=["gateway"],
                after_resolution_not_contains=["unit"])

# "what are the battery status of Fake 3A" → both unit+lock raw, lock comes from direct column match
check_discovery("what are the battery status of Fake 3A",
                expected_contains=["lock"])

# "which unit is rented by employee2" → unit only (user needs 'rented by' pattern)
check_discovery("which unit is rented by employee2",
                expected_contains=["unit"])

# "how many tenants are in onsite" → user discovered
check_discovery("how many tenants are in onsite",
                expected_contains=["user"])

# "show me the last 5 activities" → event discovered
check_discovery("show me the last 5 activities",
                expected_contains=["event"])

# "how many gateways are online and offline" → gateway only
check_discovery("how many gateways are online and offline",
                after_resolution_contains=["gateway"],
                after_resolution_not_contains=["lock"])


# ══════════════════════════════════════════════════════════════════════════════
# 17. DB ROUTING VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 17. DB routing ────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["unit"],    "DATA_AGGREGATION", filters=["count"])
check("unit → main DB",    db == "main",     f"db={db}")
db, sql, _raw, _params = run(["user"],    "DATA_AGGREGATION", filters=["count"])
check("user → main DB",    db == "main",     f"db={db}")
db, sql, _raw, _params = run(["lock"],    "DATA_AGGREGATION", filters=["count"])
check("lock → main DB",    db == "main",     f"db={db}")
db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count"])
check("gateway → main DB", db == "main",     f"db={db}")
db, sql, _raw, _params = run(["company"], "DATA_AGGREGATION", filters=["count"], session={})
check("company → main DB", db == "main",     f"db={db}")
db, sql, _raw, _params = run(["event"],   "DATA_AGGREGATION", filters=["count"])
check("event → activity DB", db == "activity", f"db={db}")


# ══════════════════════════════════════════════════════════════════════════════
# 18. FOLLOW-UP QUESTION GENERATION (agent_graph.py)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 18. Follow-up questions ───────────────────────────────────════════")

# Add app path to import agent_graph helpers
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "NokeAgent")
sys.path.insert(0, os.path.abspath(APP_DIR))

# Patch heavy imports so we can import the helper functions
import types, unittest.mock as _mock

for mod_name in ["langchain_aws", "langchain_core", "langchain_core.messages",
                  "langchain_core.tools", "langgraph", "langgraph.graph",
                  "langgraph.graph.message", "langchain_core.messages",
                  "dotenv", "boto3", "botocore"]:
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

# Stub specific symbols
import langchain_core.messages as _lcm
for attr in ["BaseMessage", "SystemMessage", "HumanMessage", "AIMessage", "ToolMessage"]:
    if not hasattr(_lcm, attr):
        setattr(_lcm, attr, type(attr, (), {}))

_dotenv_mod = sys.modules.get("dotenv") or types.ModuleType("dotenv")
setattr(_dotenv_mod, "load_dotenv", lambda *a, **kw: None)
sys.modules["dotenv"] = _dotenv_mod

sys.modules["langchain_aws"] = types.ModuleType("langchain_aws")
sys.modules["langchain_aws"].ChatBedrock = type("ChatBedrock", (), {})
sys.modules.setdefault("langchain_core.tools", types.ModuleType("langchain_core.tools"))
setattr(sys.modules["langchain_core.tools"], "tool", lambda f: f)
sys.modules.setdefault("langgraph.graph", types.ModuleType("langgraph.graph"))
setattr(sys.modules["langgraph.graph"], "StateGraph", type("StateGraph", (), {}))
setattr(sys.modules["langgraph.graph"], "END", "END")
setattr(sys.modules["langgraph.graph"], "START", "START")
sys.modules.setdefault("langgraph.graph.message", types.ModuleType("langgraph.graph.message"))
setattr(sys.modules["langgraph.graph.message"], "add_messages", lambda x: x)

# Import just the helpers we want to test
import importlib, importlib.util
spec = importlib.util.spec_from_file_location(
    "agent_graph_helpers",
    os.path.join(os.path.abspath(APP_DIR), "agent_graph.py")
)
# We can't load it fully due to LangGraph; extract helpers via exec
_src = open(os.path.join(os.path.abspath(APP_DIR), "agent_graph.py"), encoding="utf-8").read()
_ns = {"__name__": "__fake__", "sys": sys, "os": os, "re": re, "json": json,
       "__file__": os.path.join(os.path.abspath(APP_DIR), "agent_graph.py"),
       # Pre-stub symbols that may be stripped by the import-filter below
       "load_dotenv": lambda *a, **kw: None,
       "ChatBedrock": type("ChatBedrock", (), {}),
       "tool": lambda f: f,
       "StateGraph": type("StateGraph", (), {
           "__init__": lambda self, *a, **kw: None,
           "add_node": lambda self, *a, **kw: None,
           "add_edge": lambda self, *a, **kw: None,
           "add_conditional_edges": lambda self, *a, **kw: None,
           "set_entry_point": lambda self, *a, **kw: None,
           "compile": lambda self, *a, **kw: type("App", (), {"invoke": lambda self, *a, **kw: {}})(),
       }),
       "END": "END", "START": "START",
       "add_messages": lambda x: x,
       "Optional": __import__("typing").Optional,
       "List": __import__("typing").List,
       "Annotated": __import__("typing").Annotated,
       "TypedDict": __import__("typing").TypedDict,
       "Literal": __import__("typing").Literal,
       "Sequence": __import__("typing").Sequence,
       "Enum": __import__("enum").Enum,
       "BaseModel": type("BaseModel", (), {}),
       "Field": lambda *a, **kw: None,
       "data_retrieval_engine": dre,
       "dre": dre,
       # langchain message stubs
       "BaseMessage": type("BaseMessage", (), {}),
       "SystemMessage": type("SystemMessage", (), {"content": ""}),
       "HumanMessage": type("HumanMessage", (), {"content": ""}),
       "AIMessage": type("AIMessage", (), {"content": "", "tool_calls": []}),
       "ToolMessage": type("ToolMessage", (), {"content": "", "tool_call_id": ""}),
       # stdlib
       "logging": __import__("logging"),
       "datetime": __import__("datetime"),
       "traceback": __import__("traceback"),
       "collections": __import__("collections"),
       }
# Extract just _build_followup_question and _CONTENT_FILTER_PATTERNS
_helper_src = "\n".join(
    line for line in _src.split("\n")
    if not line.strip().startswith(("from ", "import ")) or
       any(kw in line for kw in ["import re", "import json", "import os", "import sys"])
)
try:
    exec(_helper_src, _ns)
    _build_followup = _ns.get("_build_followup_question")
    _cf_patterns = _ns.get("_CONTENT_FILTER_PATTERNS", ())
    if _build_followup:
        fq = _build_followup("which unit is rented by employee2")
        check("followup for rented-by includes tip about 'tenant'",
              "tenant" in fq.lower() or "user" in fq.lower(), fq)
        fq = _build_followup("what are the battery status of Fake 3A")
        check("followup for battery includes battery hint",
              "battery" in fq.lower() or "voltage" in fq.lower() or "status" in fq.lower(), fq)
        fq = _build_followup("show me the last 5 activities")
        check("followup for activities references time/date",
              "time" in fq.lower() or "range" in fq.lower() or "user" in fq.lower(), fq)
        fq = _build_followup("how many people are in onsite")
        check("followup for unknown query is non-empty", len(fq) > 10, fq)
        check("content filter patterns defined", len(_cf_patterns) > 0, str(_cf_patterns))
    else:
        check("_build_followup_question importable", False, "function not found in exec namespace")
except Exception as e:
    check("followup helpers load", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 19. ZONES – v2_zones + v2_zones_to_units junction
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 19. Zones ─────────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["zone"], "DATA_RETRIEVAL")
check("zone uses v2_zones table", sql_contains(sql, "FROM v2_zones"), sql)
check("zone scoped by site_id", sql_contains(sql, "site_id"), sql)
check("zone selects name", sql_contains(sql, "name"), sql)
check("zone excludes relays_in_binary", sql_not_contains(sql, "relays_in_binary"), sql)

db, sql, _raw, _params = run(["zone"], "DATA_AGGREGATION", filters=["count"])
check("zone count uses COUNT(*)", sql_contains(sql, "COUNT(*)"), sql)
check("zone count FROM v2_zones", sql_contains(sql, "FROM v2_zones"), sql)

# Zone → Unit join via junction table
db, sql, _raw, _params = run(["zone", "unit"], "DATA_RETRIEVAL", search="Zone A")
check("zone+unit joins v2_zones_to_units", sql_contains(sql, "v2_zones_to_units"), sql)
check("zone+unit also joins v2_units", sql_contains(sql, "v2_units"), sql)
check("zone+unit search propagates", sql_contains(sql, "Zone A"), sql)

# Unit → Zone reverse join
db, sql, _raw, _params = run(["unit", "zone"], "DATA_RETRIEVAL", search="unit-123")
check("unit+zone joins v2_zones_to_units", sql_contains(sql, "v2_zones_to_units"), sql)
check("unit+zone root table is v2_units", sql_contains(sql, "FROM v2_units"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 20. CHANGE_LOG – hermes_change_logs entity
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 20. Change Log ────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL")
check("change_log uses hermes_change_logs table", sql_contains(sql, "FROM hermes_change_logs"), sql)
check("change_log scoped by site_id", sql_contains(sql, "site_id"), sql)
check("change_log selects status_change", sql_contains(sql, "status_change"), sql)
check("change_log selects created_date", sql_contains(sql, "created_date"), sql)

db, sql, _raw, _params = run(["change_log"], "DATA_AGGREGATION", filters=["count"])
check("change_log count uses COUNT(*)", sql_contains(sql, "COUNT(*)"), sql)

# status_change enum_map: "moved in" → 'Moved In'
db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL", filters=["moved in"])
check("change_log 'moved in' resolves to Moved In", sql_contains(sql, "'Moved In'"), sql)

db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL", filters=["moved out"])
check("change_log 'moved out' resolves to Moved Out", sql_contains(sql, "'Moved Out'"), sql)

db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL", filters=["overlocked"])
check("change_log 'overlocked' resolves to Overlocked", sql_contains(sql, "'Overlocked'"), sql)

# Search by unit name
db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL", search="unit-A1")
check("change_log search propagates", sql_contains(sql, "unit-A1"), sql)

# Change_log → Unit join
db, sql, _raw, _params = run(["change_log", "unit"], "DATA_RETRIEVAL")
check("change_log+unit joins v2_units", sql_contains(sql, "v2_units"), sql)
check("change_log+unit root is hermes_change_logs", sql_contains(sql, "FROM hermes_change_logs"), sql)

# Order by created_date for last N events
db, sql, _raw, _params = run(["change_log"], "DATA_RETRIEVAL",
                               order_by={"column": "created_date", "direction": "DESC"}, limit=10)
check("change_log ORDER BY created_date DESC", sql_contains(sql, "ORDER BY t0.created_date DESC"), sql)
check("change_log LIMIT 10", sql_contains(sql, "LIMIT 10"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 21. GATEWAY – no company_id in WHERE clause
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 21. Gateway – no company_id filter ────────────────────────────────")

db, sql, _raw, _params = run(["gateway"], "DATA_AGGREGATION", filters=["count", "offline"])
check("gateway offline count uses gateways table", sql_contains(sql, "FROM gateways"), sql)
check("gateway offline no company_id filter", sql_not_contains(sql, "company_id"), sql)
check("gateway offline has site_id filter", sql_contains(sql, "site_id"), sql)
check("gateway offline filters status='offline'", sql_contains(sql, "'offline'"), sql)

db, sql, _raw, _params = run(["gateway"], "DATA_RETRIEVAL")
check("gateway retrieval no company_id", sql_not_contains(sql, "company_id"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 22. COMPANY – scoped by company_id (maps session company_id → companies.id)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 22. Company – scoped by company id ────────────────────────────────")

db, sql, _raw, _params = run(["company"], "DATA_RETRIEVAL")
check("company query uses companies table", sql_contains(sql, "FROM companies"), sql)
check("company scoped by id from session company_id", sql_contains(sql, "WHERE t0.id IN"), sql)
check("company does NOT use WHERE 1=1 (unscoped)", sql_not_contains(sql, "WHERE 1=1"), sql)
check("company selects name", sql_contains(sql, "name"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 23. ROLES – roles table with site scoping via users_roles
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 23. Roles ─────────────────────────────────────────────────────────")

db, sql, _raw, _params = run(["role"], "DATA_RETRIEVAL")
check("role uses roles table", sql_contains(sql, "FROM roles"), sql)
check("role has INNER JOIN users_roles for site scoping", sql_contains(sql, "INNER JOIN users_roles"), sql)
check("role scoped by site_id via users_roles", sql_contains(sql, "site_id"), sql)
check("role selects name", sql_contains(sql, "name"), sql)
check("role selects tier", sql_contains(sql, "tier"), sql)

db, sql, _raw, _params = run(["role"], "DATA_AGGREGATION", filters=["count"])
check("role count uses COUNT(*)", sql_contains(sql, "COUNT(*)"), sql)
check("role count has users_roles join", sql_contains(sql, "users_roles"), sql)

# User + Role join (via users_roles junction)
db, sql, _raw, _params = run(["user", "role"], "DATA_RETRIEVAL", search="employee2")
check("user+role joins users_roles", sql_contains(sql, "users_roles"), sql)
check("user+role also joins roles", sql_contains(sql, "roles"), sql)
check("user+role search propagates", sql_contains(sql, "employee2"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 24. ROLE_PERMISSION – roles_permissions with role-based site scoping
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 24. Role Permissions ──────────────────────────────────────────────")

db, sql, _raw, _params = run(["role_permission"], "DATA_RETRIEVAL")
check("role_permission uses roles_permissions table", sql_contains(sql, "FROM roles_permissions"), sql)
check("role_permission selects permission column", sql_contains(sql, "permission"), sql)

# Permission queries as root entity must be site-scoped via role + users_roles
# "what all permissions do we have" should ONLY show permissions for roles at THIS site
db, sql, _raw, _params = run(["role_permission"], "DATA_RETRIEVAL")
check("role_permission as root joins to roles table", sql_contains(sql, "roles t_role") or sql_contains(sql, "JOIN roles"), sql)
check("role_permission as root has INNER JOIN users_roles for site scoping", sql_contains(sql, "INNER JOIN users_roles ur_rp_scope"), sql)
check("role_permission as root scoped by site_id", "_rp_site_0" in _params or "_rp_site" in str(_params), sql)

# Permission search with partial match
db, sql, _raw, _params = run(["role_permission"], "DATA_RETRIEVAL", search="move out")
check("role_permission search propagates", sql_contains(sql, "move out"), sql)
check("role_permission uses LIKE for search", sql_contains(sql, "LIKE"), sql)

# Role + Permission with site scoping (role as root triggers users_roles join)
db, sql, _raw, _params = run(["role", "role_permission"], "DATA_RETRIEVAL", search="move out")
check("role+permission joins roles_permissions", sql_contains(sql, "roles_permissions"), sql)
check("role+permission has INNER JOIN users_roles for site scoping", sql_contains(sql, "INNER JOIN users_roles"), sql)
check("role+permission search propagates", sql_contains(sql, "move out"), sql)

# Role + Permission (checking specific permission existence)
db, sql, _raw, _params = run(["role", "role_permission"], "DATA_RETRIEVAL", search="move_out")
check("role+permission search for move_out", sql_contains(sql, "move_out"), sql)
check("role+permission site scoped via users_roles", sql_contains(sql, "users_roles"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# 25. FEATUREFLAG – featureflags with site scoping via featureflags_assignments
# ══════════════════════════════════════════════════════════════════════════════
print("\n── 25. Feature Flags ─────────────────────────────────────────────────")

db, sql, _raw, _params = run(["featureflag"], "DATA_RETRIEVAL")
check("featureflag uses featureflags table", sql_contains(sql, "FROM featureflags"), sql)
check("featureflag has INNER JOIN featureflags_assignments for site scoping", sql_contains(sql, "INNER JOIN featureflags_assignments"), sql)
check("featureflag scoped by site_id via assignments", sql_contains(sql, "site_id"), sql)
check("featureflag selects name", sql_contains(sql, "name"), sql)
check("featureflag selects description", sql_contains(sql, "description"), sql)
check("featureflag selects is_default", sql_contains(sql, "is_default"), sql)

# Feature flag retrieval should NOT use COUNT aggregation
db, sql, _raw, _params = run(["featureflag"], "DATA_RETRIEVAL", search="mobile")
check("featureflag search by name uses DATA_RETRIEVAL", sql_contains(sql, "SELECT"), sql)
check("featureflag search NOT aggregation", sql_not_contains(sql, "COUNT(*)"), sql)
check("featureflag search has featureflags_assignments join", sql_contains(sql, "featureflags_assignments"), sql)
check("featureflag search propagates", sql_contains(sql, "mobile"), sql)

# Feature flag enabled check
db, sql, _raw, _params = run(["featureflag"], "DATA_RETRIEVAL", filters=["enabled"])
check("featureflag enabled filter uses is_default", sql_contains(sql, "is_default"), sql)
check("featureflag enabled has site scoping", sql_contains(sql, "featureflags_assignments"), sql)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
print("\n" + "═" * 70)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total  = len(results)
print(f"RESULTS: {passed}/{total} passed  |  {failed} failed")
print("═" * 70)
if failed:
    print("\nFailed tests:")
    for label, name, detail in results:
        if label == FAIL:
            print(f"  {label}  {name}")
            if detail:
                print(f"         {detail[:120]}")

if failed > 0:
    sys.exit(1)
