"""Conexão PostgreSQL (Neon) e schema inicial."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    import psycopg

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    source TEXT DEFAULT '',
    category TEXT DEFAULT 'brasil',
    image TEXT DEFAULT '',
    published_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_published
    ON articles (published_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_articles_category
    ON articles (category);

CREATE TABLE IF NOT EXISTS subscribers (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def get_database_url() -> str:
    """Retorna URL do banco ou lança erro."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise ValueError("DATABASE_URL não configurada.")
    return url


@contextmanager
def get_connection() -> Generator["psycopg.Connection", None, None]:
    """Context manager de conexão com o PostgreSQL."""
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(get_database_url(), row_factory=dict_row)
    try:
        ensure_schema(conn)
        yield conn
    finally:
        conn.close()


def ensure_schema(conn: "psycopg.Connection") -> None:
    """Cria tabelas se ainda não existirem."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()
    logger.info("Schema PostgreSQL verificado.")
