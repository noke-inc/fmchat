"""
verify_all.py — Comprehensive SQL compilation verification across all entity combinations.
Run: python verify_all.py
"""
import re
import data_retrieval_engine as dre

dre.load_database_schema_config("database_schema.json")

_captured_sqls = {}
_orig_exec = None

def _capturing_exec(sql, params):
    return [{"count": 42, "rental_state": "available", "hw_state": "LOCKED",
             "name": "TestUnit", "first_name": "John", "last_name": "Doe",
             "email": "john@test.com", "type": "client", "voltage_battery": 3.8,
             "hw_type": "unit", "ble_hw_version": "3E"}]

verify_all_last_sql = [""]
dre.execute_query = _capturing_exec

SESSION = {"site_id": [2223391], "company_id": [1000241]}

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = []

def run(label, subjects, intent, filters, search=None, grp=None, hav=None, order=None, session=None,
        expect_in=None, expect_not_in=None):
    sess = session or SESSION
    try:
        dre.run_compiled_mcp_query(
            subjects=subjects, intent_type=intent, session_context=sess,
            semantic_filters=filters or [], aggregation_column=None,
            search_keyword=search, group_by_columns=grp or [],
            having_conditions=hav or [], order_by=order
        )
        sql = getattr(dre, "LAST_COMPILED_SQL", "")
        ok = True
        failures = []
        for chk in (expect_in or []):
            if chk.lower() not in sql.lower():
                ok = False
                failures.append(f"MISSING: {chk!r}")
        for chk in (expect_not_in or []):
            if chk.lower() in sql.lower():
                ok = False
                failures.append(f"UNEXPECTED: {chk!r}")
        status = PASS if ok else FAIL
        results.append((status, label, sql, failures))
    except Exception as e:
        results.append((FAIL, label, "", [str(e)]))

# ════════════════════════════════════════════════════════════════════
# 1. UNIT QUERIES
# ════════════════════════════════════════════════════════════════════
run("U-01  List all units",
    ["unit"], "DATA_RETRIEVAL", [],
    expect_in=["v2_units", "t0.site_id IN"])

run("U-02  Count all units",
    ["unit"], "DATA_AGGREGATION", ["count"],
    expect_in=["COUNT(*)", "v2_units", "site_id"])

run("U-03  Count available units",
    ["unit"], "DATA_AGGREGATION", ["count", "available"],
    expect_in=["COUNT(*)", "rental_state = 'available'"],
    expect_not_in=["GROUP BY t0.rental_state"])

run("U-04  Count inuse units",
    ["unit"], "DATA_AGGREGATION", ["count", "inuse"],
    expect_in=["COUNT(*)", "rental_state = 'inuse'"])

run("U-05  Count overlock units",
    ["unit"], "DATA_AGGREGATION", ["count", "overlock"],
    expect_in=["rental_state = 'overlock'"])

run("U-06  Count checkout units",
    ["unit"], "DATA_AGGREGATION", ["count", "checkout"],
    expect_in=["rental_state = 'checkout'"])

run("U-07  List employee access_type units",
    ["unit"], "DATA_RETRIEVAL", ["employee"],
    expect_in=["access_type = 'employee'"])

run("U-08  List service units",
    ["unit"], "DATA_RETRIEVAL", ["service unit"],
    expect_in=["access_type = 'service'"])

run("U-09  Search unit by name",
    ["unit"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["LIKE '%LA1234%'", "v2_units"])

run("U-10  Units per rental_state breakdown",
    ["unit"], "DATA_AGGREGATION", ["count"],
    grp=["rental_state"], order={"column": "count", "direction": "DESC"},
    expect_in=["GROUP BY t0.rental_state", "ORDER BY COUNT(*)"])

run("U-11  Units per access_type",
    ["unit"], "DATA_AGGREGATION", ["count"],
    grp=["access_type"],
    expect_in=["GROUP BY t0.access_type"])

run("U-12  Avg price per access_type",
    ["unit"], "DATA_AGGREGATION", ["avg"], grp=["access_type"],
    expect_in=["AVG", "access_type"],
    **{"session": SESSION, "hav": [], "order": None, "search": None})

# Override aggregation_column via direct call below — verify AVG is compiled
try:
    dre.run_compiled_mcp_query(subjects=["unit"], intent_type="DATA_AGGREGATION",
        session_context=SESSION, semantic_filters=["avg"], aggregation_column="details_price",
        search_keyword=None, group_by_columns=["access_type"], having_conditions=[], order_by=None)
    _sql = getattr(dre, "LAST_COMPILED_SQL", "")
    _ok = "AVG" in _sql and "access_type" in _sql
    results[-1] = (PASS if _ok else FAIL, results[-1][1], _sql, [] if _ok else ["AVG not in SQL"])
except Exception as e:
    results[-1] = (FAIL, results[-1][1], "", [str(e)])

# ════════════════════════════════════════════════════════════════════
# 2. PERCENTAGE QUERIES (GROUP BY same column — state filter suppressed)
# ════════════════════════════════════════════════════════════════════
run("P-01  % inuse units  [state must NOT appear in WHERE]",
    ["unit"], "DATA_AGGREGATION", ["count", "inuse"],
    grp=["rental_state"],
    expect_in=["GROUP BY t0.rental_state"],
    expect_not_in=["rental_state = 'inuse'"])

run("P-02  % available units  [state suppressed]",
    ["unit"], "DATA_AGGREGATION", ["count", "available"],
    grp=["rental_state"],
    expect_in=["GROUP BY t0.rental_state"],
    expect_not_in=["rental_state = 'available'"])

run("P-03  % open units   [open suppressed when grouped]",
    ["unit"], "DATA_AGGREGATION", ["count", "open"],
    grp=["rental_state"],
    expect_in=["GROUP BY t0.rental_state"],
    expect_not_in=["rental_state = 'available'"])

run("P-04  Count inuse WITH group by access_type [inuse stays in WHERE]",
    ["unit"], "DATA_AGGREGATION", ["count", "inuse"],
    grp=["access_type"],
    expect_in=["rental_state = 'inuse'", "GROUP BY t0.access_type"])

# ════════════════════════════════════════════════════════════════════
# 3. USER QUERIES
# ════════════════════════════════════════════════════════════════════
run("US-01  List clients",
    ["user"], "DATA_RETRIEVAL", ["client"],
    expect_in=["users", "type = 'client'", "company_id"])

run("US-02  Count active users",
    ["user"], "DATA_AGGREGATION", ["count", "active"],
    expect_in=["COUNT(*)", "state = 'active'"])

run("US-03  Site managers",
    ["user"], "DATA_RETRIEVAL", ["site manager"],
    expect_in=["type = 'site_manager'"])

run("US-04  Employee users",
    ["user"], "DATA_RETRIEVAL", ["employee"],
    expect_in=["type = 'employee'"])

run("US-05  Noke admin users",
    ["user"], "DATA_RETRIEVAL", ["noke admin"],
    expect_in=["type = 'noke_admin'"])

run("US-06  Users by type breakdown",
    ["user"], "DATA_AGGREGATION", ["count"],
    grp=["type"],
    expect_in=["GROUP BY t0.type"])

run("US-07  Okta SSO users",
    ["user"], "DATA_RETRIEVAL", ["okta"],
    expect_in=["login_type = 'okta'"])

run("US-08  Search user by name",
    ["user"], "DATA_RETRIEVAL", [], search="John",
    expect_in=["LIKE '%John%'"])

# ════════════════════════════════════════════════════════════════════
# 4. LOCK QUERIES
# ════════════════════════════════════════════════════════════════════
run("L-01  List all locks",
    ["lock"], "DATA_RETRIEVAL", [],
    expect_in=["v2_locks", "t0.site_id"])

run("L-02  Offline locks",
    ["lock"], "DATA_RETRIEVAL", ["offline"],
    expect_in=["hw_state = 'offline'"])

run("L-03  LOCKED state locks",
    ["lock"], "DATA_RETRIEVAL", ["locked"],
    expect_in=["hw_state = 'LOCKED'"])

run("L-04  OPEN state locks  [lock first → hw_state]",
    ["lock", "unit"], "DATA_RETRIEVAL", ["open"],
    expect_in=["hw_state = 'OPEN'"],
    expect_not_in=["rental_state = 'available'"])

run("L-05  HOLDOPEN locks",
    ["lock"], "DATA_RETRIEVAL", ["hold open"],
    expect_in=["hw_state = 'HOLDOPEN'"])

run("L-06  UGLY fault locks",
    ["lock"], "DATA_RETRIEVAL", ["ugly"],
    expect_in=["hw_state = 'UGLY'"])

run("L-07  Gate type locks",
    ["lock"], "DATA_RETRIEVAL", ["gate"],
    expect_in=["hw_type = 'gate'"])

run("L-08  Noke Volt hardware version",
    ["lock"], "DATA_RETRIEVAL", ["noke volt"],
    expect_in=["ble_hw_version = '3E'"])

run("L-09  Noke Pad (3K)",
    ["lock"], "DATA_RETRIEVAL", ["noke pad"],
    expect_in=["ble_hw_version = '3K'"])

run("L-10  Count locks per hw_type",
    ["lock"], "DATA_AGGREGATION", ["count"],
    grp=["hw_type"],
    expect_in=["GROUP BY t0.hw_type"])

run("L-11  Count locks per hw_state",
    ["lock"], "DATA_AGGREGATION", ["count"],
    grp=["hw_state"],
    expect_in=["GROUP BY t0.hw_state"])

run("L-12  Search lock by MAC",
    ["lock"], "DATA_RETRIEVAL", [], search="abc123",
    expect_in=["LIKE '%abc123%'", "v2_locks"])

run("L-13  Locks in setup sync_flag",
    ["lock"], "DATA_RETRIEVAL", ["setup"],
    expect_in=["sync_flag = 'setup'"])

# ════════════════════════════════════════════════════════════════════
# 5. UNIT + USER (2-table JOIN)
# ════════════════════════════════════════════════════════════════════
run("UU-01  Occupied units with user info",
    ["unit", "user"], "DATA_RETRIEVAL", ["inuse"],
    expect_in=["LEFT JOIN users", "rental_state = 'inuse'"],
    expect_not_in=["company_id IN"])

run("UU-02  Employee users in occupied units",
    ["unit", "user"], "DATA_RETRIEVAL", ["inuse", "employee"],
    expect_in=["rental_state = 'inuse'", "type = 'employee'"])

run("UU-03  Search unit+user by name",
    ["unit", "user"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["v2_units", "users", "LIKE '%LA1234%'"])

run("UU-04  Tenants with more than 1 unit",
    ["unit"], "DATA_AGGREGATION", ["count"],
    grp=["user_id"],
    hav=[{"aggregation": "count", "operator": ">", "value": 1}],
    expect_in=["GROUP BY t0.user_id", "HAVING COUNT(*) > 1"])

run("UU-05  Open units  [unit first → rental_state available]",
    ["unit", "user"], "DATA_RETRIEVAL", ["open"],
    expect_in=["rental_state = 'available'"],
    expect_not_in=["hw_state"])

# ════════════════════════════════════════════════════════════════════
# 6. UNIT + LOCK (2-table via junction bridge)
# ════════════════════════════════════════════════════════════════════
run("UL-01  Battery of a unit (search by name)",
    ["unit", "lock"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["v2_locks_to_units", "v2_locks", "LIKE '%LA1234%'"],
    expect_not_in=["company_id IN"])

run("UL-02  Locked units",
    ["unit", "lock"], "DATA_RETRIEVAL", ["locked"],
    expect_in=["v2_locks_to_units", "hw_state = 'LOCKED'"])

run("UL-03  Noke Volt on occupied units",
    ["unit", "lock"], "DATA_RETRIEVAL", ["inuse", "noke volt"],
    expect_in=["rental_state = 'inuse'", "ble_hw_version = '3E'"])

run("UL-04  Overlock units with lock state",
    ["unit", "lock"], "DATA_RETRIEVAL", ["overlock"],
    expect_in=["rental_state = 'overlock'", "v2_locks"])

# ════════════════════════════════════════════════════════════════════
# 7. LOCK + UNIT (lock-first: lock is disambiguation priority)
# ════════════════════════════════════════════════════════════════════
run("LU-01  Open locks with unit info  [lock first]",
    ["lock", "unit"], "DATA_RETRIEVAL", ["open"],
    expect_in=["hw_state = 'OPEN'"],
    expect_not_in=["rental_state = 'available'"])

run("LU-02  Count open locks  [lock first]",
    ["lock", "unit"], "DATA_AGGREGATION", ["count", "open"],
    expect_in=["COUNT(*)", "hw_state = 'OPEN'"],
    expect_not_in=["rental_state"])

run("LU-03  LOCKED gate locks with unit info",
    ["lock", "unit"], "DATA_RETRIEVAL", ["locked", "gate"],
    expect_in=["hw_state = 'LOCKED'", "hw_type = 'gate'"])

# ════════════════════════════════════════════════════════════════════
# 8. LOCK + UNIT + USER (3-table)
# ════════════════════════════════════════════════════════════════════
run("LUU-01  Open locks with user info  [lock first]",
    ["lock", "unit", "user"], "DATA_RETRIEVAL", ["open"],
    expect_in=["v2_locks_to_units", "users", "hw_state = 'OPEN'"],
    expect_not_in=["rental_state = 'available'"])

run("LUU-02  Offline locks and their occupants",
    ["lock", "unit", "user"], "DATA_RETRIEVAL", ["offline"],
    expect_in=["hw_state = 'offline'", "users", "v2_locks"])

# ════════════════════════════════════════════════════════════════════
# 9. UNIT + USER + LOCK (unit-first: 3-table, unit drives)
# ════════════════════════════════════════════════════════════════════
run("UUL-01  Occupied unit with user and lock details",
    ["unit", "user", "lock"], "DATA_RETRIEVAL", ["inuse"],
    expect_in=["rental_state = 'inuse'", "users", "v2_locks"])

run("UUL-02  Search unit+user+lock by unit name",
    ["unit", "user", "lock"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["v2_units", "users", "v2_locks", "LIKE '%LA1234%'"])

# ════════════════════════════════════════════════════════════════════
# PRINT REPORT
# ════════════════════════════════════════════════════════════════════
print("\n" + "═" * 90)
print("  COMPREHENSIVE QUERY COMPILATION VERIFICATION REPORT")
print("═" * 90)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)

for status, label, sql, failures in results:
    where = sql[sql.find("WHERE"):].split(";")[0].strip() if "WHERE" in sql else sql[-80:]
    grpby = sql[sql.find("GROUP BY"):].split(";")[0].strip() if "GROUP BY" in sql else ""
    print(f"\n{status}  {label}")
    print(f"     SQL→  {where[:110]}" + (f"  |  {grpby}" if grpby else ""))
    for f in failures:
        print(f"     ⚠️   {f}")

print("\n" + "═" * 90)
print(f"  RESULT: {passed} passed  |  {failed} failed  out of {len(results)} tests")
print("═" * 90 + "\n")
