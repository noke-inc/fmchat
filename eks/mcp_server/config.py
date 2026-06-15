import os
from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USER: str = os.getenv("DB_USER", "")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_SCHEMA: str = os.getenv("DB_SCHEMA", "")

# --- Local dev test user (set in .env) ---
# In production, user identity comes from the request; this is only for test_connection.py
TEST_USER_ID: int = int(os.getenv("TEST_USER_ID", "1"))

# --- Table / column names ---
# Update these in .env if the actual DB columns differ (run test_connection.py to discover).
# Future: these will be read from AWS Secrets Manager alongside DB credentials.
USERS_TABLE: str = "users"
USERS_ID_COL: str = "id"
USERS_ACTIVE_COL: str = os.getenv("USERS_ACTIVE_COL", "state")
USERS_ACTIVE_VALUE: str = os.getenv("USERS_ACTIVE_VALUE", "active")

USERS_ROLES_TABLE: str = "users_roles"
USERS_ROLES_USER_COL: str = "user_id"
USERS_ROLES_SITE_COL: str = os.getenv("USERS_ROLES_SITE_COL", "site_id")

# --- Allowed query tables (whitelist) ---
ALLOWED_TABLES: set[str] = {"v2_units", "v2_locks", "v2_locks_to_units", "users", "users_roles"}

# --- Allowed query tables (whitelist) ---
ALLOWED_TABLES: set[str] = {"v2_units", "v2_locks", "v2_locks_to_units", "users", "users_roles", "sites"}

# --- NOKE JWT (must match Go backend helpers/auth/auth.go CreateDigest secret) ---
NOKE_JWT_SECRET: str = os.getenv("NOKE_JWT_SECRET", "")

# --- MCP server ---
MCP_API_KEY: str     = os.getenv("MCP_API_KEY", "")
MCP_BASE_URL: str    = os.getenv("MCP_BASE_URL", "https://mcp.smartentry.noke.dev")


