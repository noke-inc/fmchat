"""
app/NokeMCP/auth/db_user.py

Database-backed user validation and site-scope resolution.
Used at the top of every MCP tool to enforce per-user data scoping.
"""

from db import execute_query
from config import (
    USERS_TABLE,
    USERS_ID_COL,
    USERS_ACTIVE_COL,
    USERS_ACTIVE_VALUE,
    USERS_ROLES_TABLE,
    USERS_ROLES_USER_COL,
    USERS_ROLES_SITE_COL,
)


def validate_user(user_id: int) -> dict:
    """
    Confirm the user exists and is active.
    Returns the user row on success.
    Raises PermissionError if the user is not found or inactive.
    """
    rows = execute_query(
        f"SELECT * FROM `{USERS_TABLE}` WHERE `{USERS_ID_COL}` = %s LIMIT 1",
        (user_id,),
    )
    if not rows:
        raise PermissionError(f"User ID {user_id} not found.")

    user = rows[0]
    active_val = user.get(USERS_ACTIVE_COL)
    is_active = (
        str(active_val).lower() == USERS_ACTIVE_VALUE.lower()
        if active_val is not None
        else False
    )
    if not is_active:
        raise PermissionError(
            f"User ID {user_id} is not active (state='{active_val}')."
        )

    return user


def get_user_sites(user_id: int) -> list[int]:
    """
    Return the list of site_ids assigned to this user via the users_roles table.
    Raises PermissionError if no sites are assigned.
    """
    rows = execute_query(
        f"SELECT `{USERS_ROLES_SITE_COL}` FROM `{USERS_ROLES_TABLE}` "
        f"WHERE `{USERS_ROLES_USER_COL}` = %s",
        (user_id,),
    )
    if not rows:
        raise PermissionError(f"User ID {user_id} has no assigned sites.")

    return [
        int(r[USERS_ROLES_SITE_COL])
        for r in rows
        if r.get(USERS_ROLES_SITE_COL) is not None
    ]


def resolve_user_sites(user_id: int) -> list[int]:
    """Validate user then return their site list in one call."""
    validate_user(user_id)
    return get_user_sites(user_id)
