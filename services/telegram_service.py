"""Serviço de envio de mensagens via Telegram Bot API."""

from __future__ import annotations

import logging
import time
from typing import Final

import requests

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH: Final[int] = 4096
TELEGRAM_API_BASE_URL: Final[str] = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY_SECONDS: Final[float] = 3.0
REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0


class TelegramServiceError(Exception):
    """Erro base para falhas na integração com o Telegram."""


class TelegramService:
    """Encapsula envio de mensagens ao Telegram com divisão automática."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        """
        Inicializa o serviço do Telegram.

        Args:
            bot_token: Token do bot obtido via @BotFather.
            chat_id: ID do chat ou grupo de destino.
            max_retries: Número máximo de tentativas por mensagem.
            retry_delay_seconds: Intervalo base entre tentativas.
        """
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID não configurado.")

        self._bot_token = bot_token
        self._chat_id = chat_id
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    def send_message(self, text: str, title: str | None = None) -> None:
        """
        Envia uma ou mais mensagens ao chat configurado.

        Mensagens longas são divididas automaticamente em partes
        respeitando o limite de 4096 caracteres do Telegram.

        Args:
            text: Conteúdo a ser enviado.
            title: Título exibido no cabeçalho da primeira parte.

        Raises:
            TelegramServiceError: Se o envio falhar após todas as tentativas.
        """
        if not text or not text.strip():
            raise TelegramServiceError("Texto da mensagem vazio.")

        chunks = self._split_message(text)
        logger.info("Enviando %d mensagem(ns) para o chat %s.", len(chunks), self._chat_id)

        for index, chunk in enumerate(chunks, start=1):
            self._send_chunk(chunk, part=index, total=len(chunks), title=title)

        logger.info("Mensagem(ns) enviada(s) com sucesso ao Telegram.")

    def _send_chunk(
        self,
        text: str,
        part: int,
        total: int,
        title: str | None = None,
    ) -> None:
        """
        Envia um único fragmento de mensagem com retry.

        Args:
            text: Fragmento de texto.
            part: Número da parte atual.
            total: Total de partes.
            title: Título exibido no cabeçalho.
        """
        header_title = title or "📰 DevBrief News — Resumo das Principais Notícias (Últimas 24h)"
        header = f"{header_title} ({part}/{total})\n\n" if total > 1 else f"{header_title}\n\n"
        payload_text = f"{header}{text}"

        if len(payload_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            payload_text = text[: TELEGRAM_MAX_MESSAGE_LENGTH - 50] + "\n\n...(continua)"

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = requests.post(
                    TELEGRAM_API_BASE_URL.format(token=self._bot_token, method="sendMessage"),
                    json={
                        "chat_id": self._chat_id,
                        "text": payload_text,
                        "disable_web_page_preview": True,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return

                    description = data.get("description", "Erro desconhecido")
                    raise TelegramServiceError(f"Telegram retornou erro: {description}")

                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                    logger.warning(
                        "Rate limit do Telegram. Aguardando %ss (tentativa %d).",
                        retry_after,
                        attempt,
                    )
                    time.sleep(retry_after)
                    continue

                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise TelegramServiceError(
                        f"Erro permanente do Telegram (HTTP {response.status_code}): "
                        f"{response.text}"
                    )

                raise TelegramServiceError(
                    f"Erro temporário do Telegram (HTTP {response.status_code}): {response.text}"
                )

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                logger.warning(
                    "Falha de conexão com o Telegram (parte %d, tentativa %d): %s",
                    part,
                    attempt,
                    exc,
                )
            except TelegramServiceError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Erro inesperado no Telegram (parte %d, tentativa %d): %s",
                    part,
                    attempt,
                    exc,
                )

            if attempt < self._max_retries:
                delay = self._retry_delay_seconds * attempt
                time.sleep(delay)

        raise TelegramServiceError(
            f"Falha ao enviar parte {part}/{total} após {self._max_retries} tentativas."
        ) from last_error

    @staticmethod
    def _split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
        """
        Divide o texto em partes respeitando o limite do Telegram.

        A divisão prioriza quebras em parágrafos e linhas para manter legibilidade.

        Args:
            text: Texto completo.
            max_length: Tamanho máximo por parte (reservando espaço para cabeçalho).

        Returns:
            Lista de fragmentos de texto.
        """
        reserved = 80
        effective_max = max_length - reserved

        if len(text) <= effective_max:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= effective_max:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n\n", 0, effective_max)
            if split_at == -1:
                split_at = remaining.rfind("\n", 0, effective_max)
            if split_at == -1:
                split_at = remaining.rfind(" ", 0, effective_max)
            if split_at == -1:
                split_at = effective_max

            chunk = remaining[:split_at].rstrip()
            if not chunk:
                chunk = remaining[:effective_max]
                split_at = effective_max

            chunks.append(chunk)
            remaining = remaining[split_at:].lstrip()

        return chunks
