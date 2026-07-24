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
             "hw_type": "unit", "ble_hw_version": "3E", "status": "online",
             "type_gen": "unlock", "created_at": "2026-07-24 10:00:00"}]

def _capturing_exec_activity(sql, params):
    return [{"count": 15, "type_gen": "unlock", "by_user_gen": "user123",
             "created_at": "2026-07-24 10:00:00", "site_id_gen": "2223391"}]

verify_all_last_sql = [""]
dre.execute_query = _capturing_exec
dre.execute_activity_query = _capturing_exec_activity

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
# 10. GATEWAY QUERIES (new entity)
# ════════════════════════════════════════════════════════════════════
run("GW-01  List all gateways",
    ["gateway"], "DATA_RETRIEVAL", [],
    expect_in=["gateways", "t0.site_id IN"])

run("GW-02  Count online gateways",
    ["gateway"], "DATA_AGGREGATION", ["count", "online"],
    expect_in=["COUNT(*)", "status = 'online'"])

run("GW-03  Count offline gateways",
    ["gateway"], "DATA_AGGREGATION", ["count", "offline"],
    expect_in=["COUNT(*)", "status = 'offline'"])

run("GW-04  List disconnected gateways",
    ["gateway"], "DATA_RETRIEVAL", ["disconnected"],
    expect_in=["status = 'offline'"])

run("GW-05  Gateway status breakdown",
    ["gateway"], "DATA_AGGREGATION", ["count"],
    grp=["status"],
    expect_in=["GROUP BY t0.status"])

run("GW-06  Search gateway by name",
    ["gateway"], "DATA_RETRIEVAL", [], search="MainGate",
    expect_in=["LIKE '%MainGate%'", "gateways"])

run("GW-07  Search gateway by MAC",
    ["gateway"], "DATA_RETRIEVAL", [], search="AA:BB:CC",
    expect_in=["LIKE '%AA:BB:CC%'", "gateways"])

# ════════════════════════════════════════════════════════════════════
# 11. COMPANY QUERIES (no site guardrail)
# ════════════════════════════════════════════════════════════════════
run("CO-01  List all companies",
    ["company"], "DATA_RETRIEVAL", [],
    expect_in=["companies"],
    expect_not_in=["site_id"])

run("CO-02  Count companies",
    ["company"], "DATA_AGGREGATION", ["count"],
    expect_in=["COUNT(*)", "companies"],
    expect_not_in=["site_id"])

run("CO-03  Search company by name",
    ["company"], "DATA_RETRIEVAL", [], search="Acme",
    expect_in=["LIKE '%Acme%'", "companies"],
    expect_not_in=["site_id"])

# ════════════════════════════════════════════════════════════════════
# 12. EVENT QUERIES (smartentry-activity DB, site_id_gen scoping)
# ════════════════════════════════════════════════════════════════════
run("EV-01  List all events",
    ["event"], "DATA_RETRIEVAL", [],
    expect_in=["events", "t0.site_id_gen IN"],
    expect_not_in=["site_id IN"])

run("EV-02  Count unlock events",
    ["event"], "DATA_AGGREGATION", ["count", "unlock"],
    expect_in=["COUNT(*)", "type_gen = 'unlock'", "site_id_gen"])

run("EV-03  Count lock events",
    ["event"], "DATA_AGGREGATION", ["count", "lock event"],
    expect_in=["COUNT(*)", "type_gen = 'lock'"])

run("EV-04  List share events",
    ["event"], "DATA_RETRIEVAL", ["share"],
    expect_in=["type_gen = 'share'", "events"])

run("EV-05  List user events",
    ["event"], "DATA_RETRIEVAL", ["user event"],
    expect_in=["type_gen = 'user'"])

run("EV-06  List video events",
    ["event"], "DATA_RETRIEVAL", ["video"],
    expect_in=["type_gen = 'video'"])

run("EV-07  List site events",
    ["event"], "DATA_RETRIEVAL", ["site event"],
    expect_in=["type_gen = 'site'"])

run("EV-08  Count unit access events",
    ["event"], "DATA_AGGREGATION", ["count", "unit event"],
    expect_in=["COUNT(*)", "type_gen = 'unit'"])

run("EV-09  Events by type breakdown",
    ["event"], "DATA_AGGREGATION", ["count"],
    grp=["type_gen"],
    expect_in=["GROUP BY t0.type_gen", "site_id_gen"])

run("EV-10  Search event by user",
    ["event"], "DATA_RETRIEVAL", [], search="user123",
    expect_in=["LIKE '%user123%'", "events"])

# ════════════════════════════════════════════════════════════════════
# 13. BATTERY STATUS QUERIES (voltage_battery from locks)
# ════════════════════════════════════════════════════════════════════
run("BAT-01  Battery status of Fake 3A  [lock search]",
    ["lock"], "DATA_RETRIEVAL", [], search="Fake 3A",
    expect_in=["v2_locks", "LIKE '%Fake 3A%'", "voltage_battery"])

run("BAT-02  Battery status of 3A hardware  [ble_hw_version]",
    ["lock"], "DATA_RETRIEVAL", ["3a"],
    expect_in=["ble_hw_version = '3A'", "voltage_battery"])

run("BAT-03  All locks with battery info  [includes voltage_battery]",
    ["lock"], "DATA_RETRIEVAL", [],
    expect_in=["voltage_battery", "v2_locks"])

run("BAT-04  Unit battery status  [unit+lock join]",
    ["unit", "lock"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["v2_locks_to_units", "voltage_battery", "LIKE '%LA1234%'"])

# ════════════════════════════════════════════════════════════════════
# 14. USER/TENANT SITE SCOPING (uses users_roles, NOT company_id)
# ════════════════════════════════════════════════════════════════════
run("TEN-01  Count tenants (site-scoped)  [uses users_roles join]",
    ["user"], "DATA_AGGREGATION", ["count", "client"],
    expect_in=["COUNT(*)", "type = 'client'", "users_roles"],
    expect_not_in=["company_id IN"])

run("TEN-02  List tenants (site-scoped)",
    ["user"], "DATA_RETRIEVAL", ["tenant"],
    expect_in=["type = 'client'", "users_roles"],
    expect_not_in=["company_id IN"])

run("TEN-03  Count employees (site-scoped)",
    ["user"], "DATA_AGGREGATION", ["count", "employee"],
    expect_in=["COUNT(*)", "type = 'employee'", "users_roles"])

run("TEN-04  Percentage of tenants  [group by type with users_roles]",
    ["user"], "DATA_AGGREGATION", ["count"],
    grp=["type"],
    expect_in=["GROUP BY t0.type", "users_roles"],
    expect_not_in=["company_id IN"])

run("TEN-05  Search user by email (site-scoped)",
    ["user"], "DATA_RETRIEVAL", [], search="john@example.com",
    expect_in=["LIKE '%john@example.com%'", "users_roles"])

# ════════════════════════════════════════════════════════════════════
# 15. LOCK ENTRY/ENTRIES ALIASES (gate/exitgate)
# ════════════════════════════════════════════════════════════════════
run("ENT-01  Count entries (gate type)  [entry → gate]",
    ["lock"], "DATA_AGGREGATION", ["count", "entry"],
    expect_in=["COUNT(*)", "hw_type = 'gate'"])

run("ENT-02  List entries (gate+exitgate)  [entries → gate]",
    ["lock"], "DATA_RETRIEVAL", ["entries"],
    expect_in=["hw_type = 'gate'"])

run("ENT-03  Count exit entries  [exitgate type]",
    ["lock"], "DATA_AGGREGATION", ["count", "exit entry"],
    expect_in=["COUNT(*)", "hw_type = 'exitgate'"])

run("ENT-04  Open entries  [hw_state + hw_type]",
    ["lock"], "DATA_RETRIEVAL", ["open", "entry"],
    expect_in=["hw_state = 'OPEN'", "hw_type = 'gate'"])

run("ENT-05  Hold open entries",
    ["lock"], "DATA_RETRIEVAL", ["hold open", "entry"],
    expect_in=["hw_state = 'HOLDOPEN'", "hw_type = 'gate'"])

run("ENT-06  Locked entrance gates",
    ["lock"], "DATA_RETRIEVAL", ["locked", "entrance"],
    expect_in=["hw_state = 'LOCKED'", "hw_type = 'gate'"])

# ════════════════════════════════════════════════════════════════════
# 16. MULTI-SCENARIO REAL-WORLD QUERIES
# ════════════════════════════════════════════════════════════════════
run("REAL-01  Which unit is occupied by user employee2",
    ["unit", "user"], "DATA_RETRIEVAL", ["inuse", "employee"],
    search="employee2",
    expect_in=["rental_state = 'inuse'", "type = 'employee'", "LIKE '%employee2%'"],
    expect_not_in=["company_id IN"])

run("REAL-02  Which unit is rented by employee2",
    ["unit", "user"], "DATA_RETRIEVAL", ["inuse"], search="employee2",
    expect_in=["rental_state = 'inuse'", "LIKE '%employee2%'"])

run("REAL-03  How many people are onsite  [active users]",
    ["user"], "DATA_AGGREGATION", ["count", "active"],
    expect_in=["COUNT(*)", "state = 'active'", "users_roles"],
    expect_not_in=["company_id IN"])

run("REAL-04  How many tenants in onsite  [site-scoped]",
    ["user"], "DATA_AGGREGATION", ["count", "client"],
    expect_in=["COUNT(*)", "type = 'client'", "users_roles"],
    expect_not_in=["company_id IN"])

run("REAL-05  Percentage of tenants  [group by type]",
    ["user"], "DATA_AGGREGATION", ["count"],
    grp=["type"],
    expect_in=["GROUP BY t0.type", "users_roles"],
    expect_not_in=["type = 'client'"])

run("REAL-06  Show all available units",
    ["unit"], "DATA_RETRIEVAL", ["available"],
    expect_in=["rental_state = 'available'"])

run("REAL-07  Battery status of Fake 3A",
    ["lock"], "DATA_RETRIEVAL", [], search="Fake 3A",
    expect_in=["voltage_battery", "LIKE '%Fake 3A%'"])

run("REAL-08  How many gateways are online",
    ["gateway"], "DATA_AGGREGATION", ["count", "online"],
    expect_in=["COUNT(*)", "status = 'online'"])

run("REAL-09  How many gateways are offline",
    ["gateway"], "DATA_AGGREGATION", ["count", "offline"],
    expect_in=["COUNT(*)", "status = 'offline'"])

run("REAL-10  How many entries are open",
    ["lock"], "DATA_AGGREGATION", ["count", "open", "entry"],
    expect_in=["COUNT(*)", "hw_state = 'OPEN'", "hw_type = 'gate'"])

run("REAL-11  How many entries are hold open",
    ["lock"], "DATA_AGGREGATION", ["count", "hold open", "entry"],
    expect_in=["COUNT(*)", "hw_state = 'HOLDOPEN'", "hw_type = 'gate'"])

run("REAL-12  Last activity for unit LA1234  [events]",
    ["event"], "DATA_RETRIEVAL", [], search="LA1234",
    expect_in=["events", "site_id_gen", "LIKE '%LA1234%'"])

run("REAL-13  Count access events today  [unlock events]",
    ["event"], "DATA_AGGREGATION", ["count", "unlock"],
    expect_in=["COUNT(*)", "type_gen = 'unlock'"])

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
