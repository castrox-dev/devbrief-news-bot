"""Endpoint — sincroniza RSS → PostgreSQL (cron a cada 5 min)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from lib.vercel_utils import is_authorized, send_json, setup_api_logging
from services.jobs import load_config_from_env, run_sync_news_job


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "unauthorized"})
            return

        error = _validate_database_config()
        if error:
            send_json(self, 500, {"ok": False, "error": error})
            return

        try:
            config = load_config_from_env()
            result = run_sync_news_job(config)
            send_json(self, 200, result)
        except Exception as exc:
            send_json(self, 500, {"ok": False, "error": str(exc)})


def _validate_database_config() -> str | None:
    import os

    if not os.getenv("DATABASE_URL", "").strip():
        return "DATABASE_URL ausente nas variáveis de ambiente."
    return None
