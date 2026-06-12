"""Serviço de envio de e-mail via Resend API."""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime
from typing import Any, Final

import requests

from services.email_renderer import LOGO_CID, get_logo_bytes, render_email_html

logger = logging.getLogger(__name__)

RESEND_API_URL: Final[str] = "https://api.resend.com/emails"
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY_SECONDS: Final[float] = 3.0
REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0


class EmailServiceError(Exception):
    """Erro base para falhas no envio de e-mail."""


class EmailService:
    """Encapsula envio de e-mails HTML via Resend com retry automático."""

    def __init__(
        self,
        api_key: str,
        from_address: str,
        to_addresses: list[str],
        logo_url: str = "",
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        """
        Inicializa o serviço de e-mail.

        Args:
            api_key: Chave de API do Resend (re_...).
            from_address: Remetente (ex.: DevBrief News <news@seudominio.com>).
            to_addresses: Lista de destinatários.
            logo_url: URL pública da logo (fallback se CID indisponível).
            max_retries: Número máximo de tentativas.
            retry_delay_seconds: Intervalo base entre tentativas.
        """
        if not api_key:
            raise ValueError("RESEND_API_KEY não configurada.")
        if not from_address:
            raise ValueError("EMAIL_FROM não configurado.")
        if not to_addresses:
            raise ValueError("EMAIL_TO não configurado.")

        self._api_key = api_key
        self._from_address = from_address
        self._to_addresses = to_addresses
        self._logo_url = logo_url
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    def send_news_summary(
        self,
        summary: str,
        reference_date: datetime | None = None,
        subject_prefix: str = "📰 DevBrief News",
    ) -> None:
        """
        Envia o resumo de notícias como e-mail HTML.

        Args:
            summary: Texto do resumo gerado pela IA.
            reference_date: Data exibida no template.
            subject_prefix: Prefixo do assunto do e-mail.

        Raises:
            EmailServiceError: Se o envio falhar após todas as tentativas.
        """
        reference_date = reference_date or datetime.now()
        has_logo = get_logo_bytes() is not None
        html_content = render_email_html(
            summary,
            reference_date,
            logo_url=self._logo_url,
            use_inline_logo=has_logo,
        )
        date_str = reference_date.strftime("%d/%m/%Y")
        subject = f"{subject_prefix} — Briefing de {date_str}"

        self._send_email(subject=subject, html_content=html_content, attach_logo=has_logo)

    @staticmethod
    def _build_logo_attachment() -> dict[str, Any] | None:
        """Monta anexo inline da logo para uso com cid: no HTML."""
        logo_bytes = get_logo_bytes()
        if not logo_bytes:
            return None

        return {
            "filename": "devbrief-logo.png",
            "content": base64.b64encode(logo_bytes).decode("ascii"),
            "content_id": LOGO_CID,
        }

    def _send_email(self, subject: str, html_content: str, attach_logo: bool = True) -> None:
        """
        Envia o e-mail via API Resend com retry.

        Args:
            subject: Assunto do e-mail.
            html_content: Corpo HTML.
            attach_logo: Se True, anexa logo como imagem inline (CID).

        Raises:
            EmailServiceError: Se todas as tentativas falharem.
        """
        last_error: Exception | None = None

        payload: dict[str, Any] = {
            "from": self._from_address,
            "to": self._to_addresses,
            "subject": subject,
            "html": html_content,
        }

        if attach_logo:
            logo_attachment = self._build_logo_attachment()
            if logo_attachment:
                payload["attachments"] = [logo_attachment]
                logger.info("Logo anexada como imagem inline (cid:%s).", LOGO_CID)

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "Enviando e-mail via Resend para %s (tentativa %d/%d)",
                    ", ".join(self._to_addresses),
                    attempt,
                    self._max_retries,
                )

                response = requests.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    email_id = data.get("id", "N/A")
                    logger.info("E-mail enviado com sucesso (id=%s).", email_id)
                    return

                if response.status_code == 429:
                    logger.warning("Rate limit do Resend (tentativa %d).", attempt)
                    time.sleep(5)
                    continue

                if 400 <= response.status_code < 500:
                    raise EmailServiceError(
                        f"Erro permanente do Resend (HTTP {response.status_code}): "
                        f"{response.text}"
                    )

                raise EmailServiceError(
                    f"Erro temporário do Resend (HTTP {response.status_code}): {response.text}"
                )

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                logger.warning("Falha de conexão com Resend (tentativa %d): %s", attempt, exc)
            except EmailServiceError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("Erro inesperado no Resend (tentativa %d): %s", attempt, exc)

            if attempt < self._max_retries:
                delay = self._retry_delay_seconds * attempt
                time.sleep(delay)

        raise EmailServiceError(
            f"Falha ao enviar e-mail após {self._max_retries} tentativas."
        ) from last_error
