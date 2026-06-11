import datetime
import decimal

import pymysql
import pymysql.cursors

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_SCHEMA


def _serialize_row(row: dict) -> dict:
    """Convert non-JSON-serializable MySQL types (datetime, Decimal, bytes) to strings."""
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            out[k] = v.isoformat()
        elif isinstance(v, decimal.Decimal):
            out[k] = float(v)
        elif isinstance(v, bytes):
            out[k] = v.decode("utf-8", errors="replace")
        else:
            out[k] = v
    return out


def get_connection() -> pymysql.Connection:
    """Open a new connection to the database."""
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
    Execute a SELECT/SHOW/DESCRIBE query and return results as a list of dicts.
    Raises ValueError for any non-read statement.
    """
    first_word = sql.strip().split()[0].upper()
    if first_word not in ("SELECT", "SHOW", "DESCRIBE"):
        raise ValueError(
            f"Statement type '{first_word}' is not allowed. "
            "Only SELECT, SHOW, and DESCRIBE are permitted."
        )

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return [_serialize_row(row) for row in cursor.fetchall()]
    finally:
        conn.close()
