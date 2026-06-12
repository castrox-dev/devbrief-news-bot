"""Endpoint de health check."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from lib.vercel_utils import send_json, setup_api_logging


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()
        send_json(
            self,
            200,
            {
                "ok": True,
                "service": "devbrief-news-bot",
                "jobs": ["daily", "breaking"],
            },
        )
