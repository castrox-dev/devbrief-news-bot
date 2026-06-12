"""Montagem do payload JSON da landing page (sem dependência de banco)."""

from __future__ import annotations

from services.news_fetcher import articles_to_web_payload, fetch_news_articles


def _group_by_category(web_articles: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
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
    return by_category


def build_web_payload_from_rss(*, lite: bool = True) -> dict[str, object]:
    """Busca RSS e monta JSON para o site (sempre funciona sem PostgreSQL)."""
    articles = fetch_news_articles(max_age_hours=24, lite=lite)
    web_articles = articles_to_web_payload(articles)
    return {
        "ok": True,
        "source": "rss_lite" if lite else "rss",
        "featured": web_articles[0] if web_articles else None,
        "latest": web_articles[:12],
        "categories": _group_by_category(web_articles),
        "updated_at": web_articles[0]["published"] if web_articles else "",
        "total": len(web_articles),
    }
