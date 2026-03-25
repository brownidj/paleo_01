from psycopg import connect
from psycopg.rows import dict_row

from app.config import get_settings


def check_database() -> None:
    settings = get_settings()
    with connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            if not row or row.get("ok") != 1:
                raise RuntimeError("Database health check returned unexpected response.")
