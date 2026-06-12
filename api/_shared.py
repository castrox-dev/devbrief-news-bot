"""Utilitários compartilhados pelos endpoints serverless da Vercel."""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def setup_api_logging() -> None:
    """Configura logging para funções serverless (stdout)."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def is_authorized(handler: BaseHTTPRequestHandler) -> bool:
    """Valida chamada de cron via CRON_SECRET."""
    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret:
        return True

    auth_header = handler.headers.get("Authorization", "")
    return auth_header == f"Bearer {secret}"


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    """Envia resposta JSON."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def validate_config(config: dict[str, str]) -> str | None:
    """Retorna mensagem de erro se config obrigatória estiver ausente."""
    missing = []
    if not config.get("ai_api_key"):
        missing.append("AI_API_KEY")
    if not config.get("telegram_bot_token"):
        missing.append("TELEGRAM_BOT_TOKEN")
    if not config.get("telegram_chat_id"):
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        return f"Variáveis ausentes: {', '.join(missing)}"
    return None
