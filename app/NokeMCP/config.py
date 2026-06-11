"""
app/NokeMCP/config.py

Environment variable configuration for the AgentCore MCP runtime.
Reads from environment (AgentCore injects these at runtime) with local .env fallback.
"""
import os

from dotenv import load_dotenv

load_dotenv()   # no-op in production; loads .env for local dev

# ── Database ──────────────────────────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USER: str = os.getenv("DB_USER", "")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_SCHEMA: str = os.getenv("DB_SCHEMA", "")

# ── User / role table column names ────────────────────────────────────────────
USERS_TABLE: str = "users"
USERS_ID_COL: str = "id"
USERS_ACTIVE_COL: str = os.getenv("USERS_ACTIVE_COL", "state")
USERS_ACTIVE_VALUE: str = os.getenv("USERS_ACTIVE_VALUE", "active")

USERS_ROLES_TABLE: str = "users_roles"
USERS_ROLES_USER_COL: str = "user_id"
USERS_ROLES_SITE_COL: str = os.getenv("USERS_ROLES_SITE_COL", "site_id")

# ── Allowed query tables (whitelist) ──────────────────────────────────────────
ALLOWED_TABLES: set[str] = {
    "v2_units",
    "v2_locks",
    "v2_locks_to_units",
    "users",
    "users_roles",
}
