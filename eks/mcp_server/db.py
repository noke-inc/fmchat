import pymysql
import pymysql.cursors
from mcp_server.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_SCHEMA


def get_connection() -> pymysql.Connection:
    """Open a new read-only connection to the database."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_SCHEMA,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
    )


def execute_query(sql: str, params: tuple = ()) -> list[dict]:
    """
    Execute a query and return results as a list of dicts.
    Only SELECT, SHOW, and DESCRIBE statements are permitted.
    Raises ValueError for any other statement type.
    """
    first_word = sql.strip().split()[0].upper()
    if first_word not in ("SELECT", "SHOW", "DESCRIBE"):
        raise ValueError(
            f"Statement type '{first_word}' is not allowed. Only SELECT, SHOW, and DESCRIBE are permitted."
        )

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        conn.close()
