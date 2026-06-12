"""Serviço de inscrição na newsletter via Resend."""

from __future__ import annotations

import logging
import re
import time
from typing import Final

import requests

logger = logging.getLogger(__name__)

RESEND_CONTACTS_URL: Final[str] = "https://api.resend.com/audiences/{audience_id}/contacts"
RESEND_EMAIL_URL: Final[str] = "https://api.resend.com/emails"
EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUEST_TIMEOUT: Final[float] = 20.0


class SubscribeError(Exception):
    """Erro na inscrição da newsletter."""


def validate_email(email: str) -> str:
    """Valida e normaliza e-mail."""
    normalized = email.strip().lower()
    if not normalized or not EMAIL_PATTERN.match(normalized):
        raise SubscribeError("Informe um e-mail válido.")
    return normalized


def subscribe_email(
    email: str,
    *,
    api_key: str,
    from_address: str,
    audience_id: str = "",
    notify_addresses: list[str] | None = None,
) -> None:
    """
    Inscreve e-mail na newsletter.

    Args:
        email: E-mail do assinante.
        api_key: Chave Resend.
        from_address: Remetente verificado.
        audience_id: ID da audience Resend (opcional).
        notify_addresses: Lista interna para aviso de nova inscrição.
    """
    if not api_key:
        raise SubscribeError("Newsletter indisponível no momento.")

    normalized = validate_email(email)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if audience_id:
        _add_to_audience(normalized, audience_id, headers)

    _send_welcome_email(normalized, from_address, headers)

    if notify_addresses:
        _notify_team(normalized, from_address, notify_addresses, headers)


def _add_to_audience(email: str, audience_id: str, headers: dict[str, str]) -> None:
    try:
        response = requests.post(
            RESEND_CONTACTS_URL.format(audience_id=audience_id),
            headers=headers,
            json={"email": email, "unsubscribed": False},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code in (200, 201):
            logger.info("Contato adicionado à audience Resend: %s", email)
            return
        if response.status_code == 409:
            logger.info("E-mail já inscrito: %s", email)
            return
        logger.warning("Audience Resend retornou %s: %s", response.status_code, response.text)
    except Exception as exc:
        logger.warning("Falha ao adicionar à audience: %s", exc)


def _send_welcome_email(email: str, from_address: str, headers: dict[str, str]) -> None:
    html = """
    <div style="font-family:Segoe UI,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
      <h1 style="color:#E91E63;">DevBrief News</h1>
      <p>Obrigado por assinar a newsletter!</p>
      <p>Você passará a receber:</p>
      <ul>
        <li>Briefing diário às 07:00 (Brasília)</li>
        <li>Alertas urgentes de mercado e tecnologia</li>
        <li>Resumo para empreendedores e investidores</li>
      </ul>
      <p style="color:#666;font-size:14px;">Equipe DevBrief News</p>
    </div>
    """
    response = requests.post(
        RESEND_EMAIL_URL,
        headers=headers,
        json={
            "from": from_address,
            "to": [email],
            "subject": "✅ Bem-vindo ao DevBrief News",
            "html": html,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code not in (200, 201):
        raise SubscribeError("Não foi possível confirmar sua inscrição. Tente novamente.")
    time.sleep(0.2)


def _notify_team(
    email: str,
    from_address: str,
    notify_addresses: list[str],
    headers: dict[str, str],
) -> None:
    try:
        requests.post(
            RESEND_EMAIL_URL,
            headers=headers,
            json={
                "from": from_address,
                "to": notify_addresses,
                "subject": f"📬 Nova inscrição DevBrief: {email}",
                "html": f"<p>Novo assinante: <strong>{email}</strong></p>",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Falha ao notificar equipe: %s", exc)
