"""Endpoint — sincroniza RSS → PostgreSQL (cron-job.org a cada 5 min)."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.rss_client import fetch_all_articles
from lib.vercel_utils import is_authorized, send_json, setup_api_logging

logger = logging.getLogger(__name__)

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


def _sync_to_database(articles: list[dict]) -> int:
    """Grava artigos no Neon PostgreSQL."""
    import psycopg

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL ausente nas variáveis de ambiente da Vercel.")

    conn = psycopg.connect(db_url)
    upserted = 0
    try:
        with conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                cur.execute(statement)
            for article in articles:
                cur.execute(
                    """
                    INSERT INTO articles (url, title, summary, source, category, image, published_at, synced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        source = EXCLUDED.source,
                        category = EXCLUDED.category,
                        image = EXCLUDED.image,
                        published_at = EXCLUDED.published_at,
                        synced_at = NOW()
                    """,
                    (
                        article["url"],
                        article["title"],
                        article.get("summary", ""),
                        article.get("source", ""),
                        article.get("category", "brasil"),
                        article.get("image", ""),
                        article.get("published_at"),
                    ),
                )
                upserted += 1

            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            cur.execute("DELETE FROM articles WHERE synced_at < %s", (cutoff,))
        conn.commit()
    finally:
        conn.close()
    return upserted


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "unauthorized"})
            return

        try:
            articles = fetch_all_articles(max_feeds=4)
            upserted = _sync_to_database(articles)
            send_json(
                self,
                200,
                {
                    "ok": True,
                    "job": "sync",
                    "fetched": len(articles),
                    "upserted": upserted,
                },
            )
        except Exception as exc:
            logger.exception("Erro /api/sync: %s", exc)
            send_json(self, 500, {"ok": False, "error": str(exc)})
