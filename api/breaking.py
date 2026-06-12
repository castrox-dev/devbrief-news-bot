"""Endpoint — verificação de breaking news (disparado pelo cron-job.org)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._shared import is_authorized, send_json, setup_api_logging, validate_config
from services.jobs import load_config_from_env, run_breaking_news_job


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_GET(self) -> None:  # noqa: N802
        setup_api_logging()

        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "unauthorized"})
            return

        config = load_config_from_env()
        error = validate_config(config)
        if error:
            send_json(self, 500, {"ok": False, "error": error})
            return

        try:
            result = run_breaking_news_job(config)
            send_json(self, 200, result)
        except Exception as exc:
            send_json(self, 500, {"ok": False, "error": str(exc)})
