"""Cliente PostgreSQL leve (pg8000) para endpoints Vercel."""

from __future__ import annotations

import os
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

SCHEMA_STATEMENTS = [
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles (published_at DESC NULLS LAST)",
    """
    CREATE TABLE IF NOT EXISTS subscribers (
        id BIGSERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]


def connect_db():
    """Abre conexão PostgreSQL (pg8000 — pure Python, ok na Vercel)."""
    import pg8000.native

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL ausente nas variáveis de ambiente da Vercel.")

    parsed = urlparse(db_url)
    query = parse_qs(parsed.query)
    ssl_mode = (query.get("sslmode") or [""])[0]
    use_ssl = ssl_mode in {"require", "verify-ca", "verify-full"}

    kwargs = {
        "user": parsed.username or "",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/").lstrip("/"),
    }
    if use_ssl:
        kwargs["ssl_context"] = ssl.create_default_context()

    return pg8000.native.Connection(**kwargs)


def ensure_schema(conn) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.run(statement)


def add_subscriber(email: str) -> bool:
    """Salva assinante. Retorna True se inseriu, False se já existia."""
    normalized = email.strip().lower()
    conn = connect_db()
    try:
        ensure_schema(conn)
        rows = conn.run(
            """
            INSERT INTO subscribers (email)
            VALUES (:email)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
            """,
            email=normalized,
        )
        return bool(rows)
    finally:
        conn.close()


def sync_articles(articles: list[dict]) -> int:
    """Upsert de artigos RSS no banco."""
    conn = connect_db()
    upserted = 0
    try:
        ensure_schema(conn)
        for article in articles:
            conn.run(
                """
                INSERT INTO articles (url, title, summary, source, category, image, published_at, synced_at)
                VALUES (:url, :title, :summary, :source, :category, :image, :published_at, NOW())
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    source = EXCLUDED.source,
                    category = EXCLUDED.category,
                    image = EXCLUDED.image,
                    published_at = EXCLUDED.published_at,
                    synced_at = NOW()
                """,
                url=article["url"],
                title=article["title"],
                summary=article.get("summary", ""),
                source=article.get("source", ""),
                category=article.get("category", "brasil"),
                image=article.get("image", ""),
                published_at=article.get("published_at"),
            )
            upserted += 1

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        conn.run("DELETE FROM articles WHERE synced_at < :cutoff", cutoff=cutoff)
    finally:
        conn.close()
    return upserted
