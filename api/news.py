"""Endpoint público — notícias RSS (stdlib, compatível com Vercel)."""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.rss_client import build_news_payload
from services.market_data import fetch_market_quotes
from services.translate import apply_locale_to_news_payload, normalize_locale

logger = logging.getLogger(__name__)


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        logging.basicConfig(level=logging.INFO)
        try:
            query = parse_qs(urlparse(self.path).query)
            lang = normalize_locale((query.get("lang") or ["pt"])[0])

            with ThreadPoolExecutor(max_workers=2) as pool:
                news_future = pool.submit(build_news_payload)
                market_future = pool.submit(fetch_market_quotes)
                payload = news_future.result()
                payload["market"] = market_future.result()

            payload = apply_locale_to_news_payload(payload, lang)
            _send_json(self, 200, payload)
        except Exception as exc:
            logger.exception("Erro /api/news: %s", exc)
            _send_json(self, 500, {"ok": False, "error": str(exc)})
