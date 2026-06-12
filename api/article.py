"""Endpoint — detalhe de uma notícia para leitura no site."""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from lib.rss_client import find_article_by_url
from lib.vercel_utils import send_json, setup_api_logging

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()
        try:
            query = parse_qs(urlparse(self.path).query)
            article_url = (query.get("u") or query.get("url") or [""])[0].strip()
            if not article_url:
                send_json(self, 400, {"ok": False, "error": "Parâmetro u (URL) é obrigatório."})
                return

            article = find_article_by_url(article_url)
            if not article:
                send_json(self, 404, {"ok": False, "error": "Notícia não encontrada."})
                return

            send_json(self, 200, {"ok": True, "article": article})
        except Exception as exc:
            logger.exception("Erro /api/article: %s", exc)
            send_json(self, 500, {"ok": False, "error": str(exc)})
