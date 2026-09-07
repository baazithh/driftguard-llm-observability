"""Auto-apply schema.sql on startup."""
from __future__ import annotations

import logging
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PGConn

from backend.config import get_settings

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_connection() -> PGConn:
    cfg = get_settings()
    return psycopg2.connect(cfg.database_url)


def apply_schema() -> None:
    """Execute schema.sql against the configured database."""
    sql = SCHEMA_FILE.read_text()
    logger.info("Applying schema from %s …", SCHEMA_FILE)
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        logger.info("Schema applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_schema()
