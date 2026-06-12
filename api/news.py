"""Endpoint público — notícias RSS (stdlib, compatível com Vercel)."""

from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.rss_client import build_news_payload

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
            _send_json(self, 200, build_news_payload())
        except Exception as exc:
            logger.exception("Erro /api/news: %s", exc)
            _send_json(self, 500, {"ok": False, "error": str(exc)})
