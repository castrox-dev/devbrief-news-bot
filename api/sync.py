"""Endpoint — sincroniza RSS → PostgreSQL (cron-job.org a cada 5 min)."""

from __future__ import annotations

import logging
import os
from http.server import BaseHTTPRequestHandler

from lib.db_client import sync_articles
from lib.rss_client import fetch_all_articles
from lib.vercel_utils import is_authorized, send_json, setup_api_logging

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "unauthorized"})
            return

        try:
            articles = fetch_all_articles(max_feeds=4)
            db_url = os.getenv("DATABASE_URL", "").strip()
            if not db_url:
                send_json(
                    self,
                    200,
                    {
                        "ok": True,
                        "job": "sync",
                        "fetched": len(articles),
                        "upserted": 0,
                        "warning": "DATABASE_URL ausente na Vercel",
                    },
                )
                return

            upserted = sync_articles(articles)
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
        except ImportError as exc:
            logger.exception("Driver DB ausente: %s", exc)
            send_json(self, 500, {"ok": False, "error": f"driver_db: {exc}"})
        except Exception as exc:
            logger.exception("Erro /api/sync: %s", exc)
            send_json(self, 500, {"ok": False, "error": str(exc)})
