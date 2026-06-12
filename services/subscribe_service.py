"""Serviço de inscrição na newsletter via Resend."""

from __future__ import annotations

import logging
import re
import time
from typing import Final

import requests

from lib.email_templates import render_team_notification_email, render_welcome_email

logger = logging.getLogger(__name__)

RESEND_CONTACTS_URL: Final[str] = "https://api.resend.com/audiences/{audience_id}/contacts"
RESEND_EMAIL_URL: Final[str] = "https://api.resend.com/emails"
DEFAULT_FROM: Final[str] = "DevBrief News <noreply@rmsys.com.br>"
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
) -> dict[str, bool | str | None]:
    """Inscreve e-mail na newsletter."""
    if not api_key:
        return {"email_sent": False, "warning": "newsletter_email_disabled"}

    normalized = validate_email(email)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if audience_id:
        _add_to_audience(normalized, audience_id, headers)

    email_sent = _send_welcome_email(normalized, from_address, headers)

    if notify_addresses:
        _notify_team(normalized, from_address, notify_addresses, headers)

    return {
        "email_sent": email_sent,
        "warning": None if email_sent else "welcome_email_failed",
    }


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


def _send_resend(from_address: str, headers: dict[str, str], *, to: list[str], subject: str, html: str) -> bool:
    sender = from_address.strip() or DEFAULT_FROM
    response = requests.post(
        RESEND_EMAIL_URL,
        headers=headers,
        json={"from": sender, "to": to, "subject": subject, "html": html},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code in (200, 201):
        time.sleep(0.2)
        return True
    logger.warning(
        "Resend falhou (%s) remetente=%s: %s",
        response.status_code,
        sender,
        response.text[:300],
    )
    return False


def _send_welcome_email(email: str, from_address: str, headers: dict[str, str]) -> bool:
    subject, html_body = render_welcome_email(email)
    return _send_resend(from_address, headers, to=[email], subject=subject, html=html_body)


def _notify_team(
    email: str,
    from_address: str,
    notify_addresses: list[str],
    headers: dict[str, str],
) -> None:
    try:
        subject, html_body = render_team_notification_email(email)
        _send_resend(from_address, headers, to=notify_addresses, subject=subject, html=html_body)
    except Exception as exc:
        logger.warning("Falha ao notificar equipe: %s", exc)
