"""Persistência de notícias e assinantes no PostgreSQL."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from services.db import get_connection
from services.news_fetcher import (
    NewsArticle,
    articles_to_web_payload,
    fetch_news_articles,
    get_article_image,
)

logger = logging.getLogger(__name__)

RETENTION_DAYS = 7
WEB_MAX_AGE_HOURS = 72


def sync_articles_from_rss(max_age_hours: int = 24) -> dict[str, int]:
    """
    Busca RSS e sincroniza artigos no banco.

    Returns:
        Contadores fetched, upserted, pruned.
    """
    articles = fetch_news_articles(max_age_hours=max_age_hours)
    upserted = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
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
                        article.url,
                        article.title,
                        article.summary,
                        article.source,
                        article.category,
                        get_article_image(article),
                        article.published,
                    ),
                )
                upserted += 1

            cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            cur.execute("DELETE FROM articles WHERE synced_at < %s", (cutoff,))
            pruned = cur.rowcount

        conn.commit()

    logger.info(
        "Sync concluído: %d coletados, %d upserted, %d removidos (> %d dias).",
        len(articles),
        upserted,
        pruned,
        RETENTION_DAYS,
    )
    return {"fetched": len(articles), "upserted": upserted, "pruned": pruned}


def _rows_to_articles(rows: list[dict]) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    for row in rows:
        articles.append(
            NewsArticle(
                title=row["title"],
                url=row["url"],
                source=row["source"] or "",
                category=row["category"] or "brasil",
                summary=row["summary"] or "",
                published=row["published_at"],
                image=row["image"] or "",
            )
        )
    return articles


def fetch_articles_from_db(max_age_hours: int = WEB_MAX_AGE_HOURS, limit: int = 60) -> list[NewsArticle]:
    """Carrega artigos recentes do banco para a landing page."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT url, title, summary, source, category, image, published_at
                FROM articles
                WHERE published_at IS NULL OR published_at >= %s
                ORDER BY published_at DESC NULLS LAST, synced_at DESC
                LIMIT %s
                """,
                (cutoff, limit),
            )
            rows = cur.fetchall()

    return _rows_to_articles(rows)


def build_web_payload_from_db() -> dict[str, object]:
    """Monta payload JSON da landing page a partir do banco."""
    articles = fetch_articles_from_db()
    web_articles = articles_to_web_payload(articles)

    by_category: dict[str, list[dict[str, str]]] = {
        "brasil": [],
        "mundo": [],
        "tecnologia": [],
        "mercado": [],
    }
    for item in web_articles:
        category = item.get("category", "brasil")
        if category in by_category and len(by_category[category]) < 8:
            by_category[category].append(item)

    last_sync = ""
    if web_articles:
        last_sync = web_articles[0].get("published", "")

    return {
        "ok": True,
        "source": "database",
        "featured": web_articles[0] if web_articles else None,
        "latest": web_articles[:12],
        "categories": by_category,
        "updated_at": last_sync,
        "total": len(web_articles),
    }


def add_subscriber(email: str) -> bool:
    """
    Salva assinante no banco.

    Returns:
        True se inseriu, False se já existia.
    """
    normalized = email.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscribers (email)
                VALUES (%s)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (normalized,),
            )
            inserted = cur.fetchone() is not None
        conn.commit()
    return inserted


def count_subscribers() -> int:
    """Retorna total de assinantes."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM subscribers")
            row = cur.fetchone()
    return int(row["total"]) if row else 0
