"""Endpoint — inscrição na newsletter."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

from lib.vercel_utils import send_json, setup_api_logging
from services.news_store import add_subscriber
from services.subscribe_service import SubscribeError, subscribe_email


class handler(BaseHTTPRequestHandler):
    """Handler serverless da Vercel (runtime Python)."""

    def do_POST(self) -> None:  # noqa: N802
        setup_api_logging()

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw)
            email = str(payload.get("email", "")).strip()

            api_key = os.getenv("RESEND_API_KEY", "").strip()
            from_address = os.getenv("EMAIL_FROM", "").strip()
            audience_id = os.getenv("RESEND_AUDIENCE_ID", "").strip()
            notify_raw = os.getenv("EMAIL_TO", "").strip()
            notify_addresses = [item.strip() for item in notify_raw.split(",") if item.strip()]

            if not from_address:
                from_address = "DevBrief News <onboarding@resend.dev>"

            try:
                add_subscriber(email)
            except Exception as db_exc:
                send_json(
                    self,
                    500,
                    {"ok": False, "error": f"Banco indisponível: {db_exc}"},
                )
                return

            subscribe_email(
                email,
                api_key=api_key,
                from_address=from_address,
                audience_id=audience_id,
                notify_addresses=notify_addresses,
            )
            send_json(self, 200, {"ok": True, "message": "Inscrição confirmada! Verifique seu e-mail."})
        except SubscribeError as exc:
            send_json(self, 400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            send_json(self, 500, {"ok": False, "error": str(exc)})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
