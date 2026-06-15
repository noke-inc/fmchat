"""
test_connection.py — Run this FIRST before starting the MCP server.

What it does:
  1. Verifies DB connectivity
  2. Prints DESCRIBE output for all 5 relevant tables (so you can confirm
     column names in config.py / .env match your actual DB schema)
  3. Prints row counts for v2_units, v2_locks scoped to TEST_USER_ID's sites
  4. Validates TEST_USER_ID through the same auth flow the MCP server uses

Usage (from repo root):
  cd eks && python ../tests/test_connection.py
  # or from repo root with PYTHONPATH:
  PYTHONPATH=eks python tests/test_connection.py
"""

import sys
import os

# Resolve eks/mcp_server — run from eks/ directory or set PYTHONPATH=eks
eks_dir = os.path.join(os.path.dirname(__file__), "..", "eks")
sys.path.insert(0, os.path.abspath(eks_dir))

import pymysql
import pymysql.cursors

# Load env vars before importing mcp_server modules
from dotenv import load_dotenv
load_dotenv()

from mcp_server.config import (
    DB_HOST, DB_PORT, DB_USER, DB_SCHEMA, TEST_USER_ID,
    USERS_TABLE, USERS_ID_COL, USERS_ACTIVE_COL,
    USERS_ROLES_TABLE, USERS_ROLES_USER_COL, USERS_ROLES_SITE_COL,
)
from mcp_server.db import get_connection


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main():
    # ── 1. Basic connectivity ─────────────────────────────────────
    section("1. Database connectivity")
    print(f"Host   : {DB_HOST}:{DB_PORT}")
    print(f"Schema : {DB_SCHEMA}")
    print(f"User   : {DB_USER}")

    try:
        conn = get_connection()
        print("✓  Connection successful")
    except Exception as e:
        print(f"✗  Connection FAILED: {e}")
        sys.exit(1)

    with conn.cursor() as cursor:

        # ── 2. Schema discovery ───────────────────────────────────
        section("2. Table schema (DESCRIBE)")
        tables = [USERS_TABLE, USERS_ROLES_TABLE, "v2_units", "v2_locks", "v2_locks_to_units"]
        for table in tables:
            print(f"\n--- {table} ---")
            try:
                cursor.execute(f"DESCRIBE `{table}`")
                for col in cursor.fetchall():
                    print(f"  {col['Field']:<30} {col['Type']:<25} Null={col['Null']}  Key={col['Key']}")
            except Exception as e:
                print(f"  ✗  Could not describe '{table}': {e}")

        # ── 3. Validate TEST_USER_ID ──────────────────────────────
        section(f"3. Validate TEST_USER_ID = {TEST_USER_ID}")
        try:
            cursor.execute(
                f"SELECT * FROM `{USERS_TABLE}` WHERE `{USERS_ID_COL}` = %s LIMIT 1",
                (TEST_USER_ID,),
            )
            user = cursor.fetchone()
            if not user:
                print(f"✗  User ID {TEST_USER_ID} NOT FOUND in '{USERS_TABLE}'.")
                print("   → Update TEST_USER_ID in .env to a valid user ID.")
            else:
                print(f"✓  User found: {user}")
                active_val = user.get(USERS_ACTIVE_COL)
                print(f"   '{USERS_ACTIVE_COL}' value = {repr(active_val)}")
                if str(active_val).lower() in ("0", "false", "inactive", "no", "none"):
                    print(f"   ✗  User is INACTIVE — queries will be rejected.")
                else:
                    print(f"   ✓  User is active")
        except Exception as e:
            print(f"✗  User query failed: {e}")
            print(f"   → Check USERS_ACTIVE_COL in .env (current: '{USERS_ACTIVE_COL}')")

        # ── 4. Resolve user sites ─────────────────────────────────
        section(f"4. Sites assigned to user {TEST_USER_ID}")
        try:
            cursor.execute(
                f"SELECT `{USERS_ROLES_SITE_COL}` FROM `{USERS_ROLES_TABLE}` WHERE `{USERS_ROLES_USER_COL}` = %s",
                (TEST_USER_ID,),
            )
            rows = cursor.fetchall()
            site_ids = [r[USERS_ROLES_SITE_COL] for r in rows]
            if not site_ids:
                print(f"✗  No sites found for user {TEST_USER_ID} in '{USERS_ROLES_TABLE}'.")
                print("   → Check USERS_ROLES_SITE_COL / USERS_ROLES_USER_COL in .env")
            else:
                print(f"✓  Assigned site_ids: {site_ids}")
        except Exception as e:
            print(f"✗  Site query failed: {e}")
            print(f"   → Check USERS_ROLES_SITE_COL in .env (current: '{USERS_ROLES_SITE_COL}')")
            site_ids = []

        # ── 5. Row counts per table ───────────────────────────────
        if site_ids:
            section("5. Row counts scoped to user's sites")
            ph = ", ".join(["%s"] * len(site_ids))
            checks = [
                ("v2_units", f"SELECT COUNT(*) AS cnt FROM v2_units WHERE site_id IN ({ph})"),
                ("v2_locks", f"SELECT COUNT(*) AS cnt FROM v2_locks WHERE site_id IN ({ph})"),
                (
                    "v2_locks_to_units (via join)",
                    f"""
                    SELECT COUNT(*) AS cnt
                    FROM v2_locks_to_units lu
                    JOIN v2_units u ON lu.unit_id = u.id
                    WHERE u.site_id IN ({ph})
                    """,
                ),
            ]
            for label, sql in checks:
                try:
                    cursor.execute(sql, tuple(site_ids))
                    count = cursor.fetchone()["cnt"]
                    print(f"  {label:<35} → {count:,} rows")
                except Exception as e:
                    print(f"  {label:<35} → ✗ {e}")

    conn.close()
    section("Done")
    print("If all checks passed, start the server with:")
    print("  python -m mcp_server.main")
    print()


if __name__ == "__main__":
    main()
