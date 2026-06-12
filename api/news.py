"""Endpoint público — notícias e cotações para a landing page."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from lib.vercel_utils import send_json, setup_api_logging
from services.market_data import fetch_market_quotes
from services.news_fetcher import articles_to_web_payload, fetch_news_articles


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        try:
            articles = fetch_news_articles(max_age_hours=24)
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

            send_json(
                self,
                200,
                {
                    "ok": True,
                    "featured": web_articles[0] if web_articles else None,
                    "latest": web_articles[:12],
                    "categories": by_category,
                    "market": fetch_market_quotes(),
                    "updated_at": web_articles[0]["published"] if web_articles else "",
                },
            )
        except Exception as exc:
            send_json(self, 500, {"ok": False, "error": str(exc)})
