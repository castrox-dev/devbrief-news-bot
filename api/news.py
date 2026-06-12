"""Endpoint público — notícias para a landing page."""

from __future__ import annotations

import logging
import traceback

from http.server import BaseHTTPRequestHandler

from lib.vercel_utils import send_json, setup_api_logging
from services.market_data import fetch_market_quotes
from services.news_store import build_web_payload_for_site

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        try:
            payload = build_web_payload_for_site()
            payload["market"] = fetch_market_quotes()
            send_json(self, 200, payload)
        except Exception as exc:
            logger.error("Erro em /api/news: %s\n%s", exc, traceback.format_exc())
            send_json(
                self,
                500,
                {"ok": False, "error": "Não foi possível carregar notícias. Tente em instantes."},
            )
