"""Serviço de geração de resumo de notícias via API compatível com OpenAI (NVIDIA NIM)."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import requests
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final[str] = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL: Final[str] = "meta/llama-3.3-70b-instruct"
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY_SECONDS: Final[float] = 5.0
DEFAULT_TIMEOUT_SECONDS: Final[float] = 600.0
DEFAULT_TEMPERATURE: Final[float] = 0.2
DEFAULT_TOP_P: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 6144
DEFAULT_REASONING_BUDGET: Final[int] = 4096


class OpenAIServiceError(Exception):
    """Erro base para falhas na integração com a API de IA."""


class OpenAIService:
    """Encapsula chamadas à API de IA (NVIDIA NIM) com retry e tratamento de erros."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        reasoning_budget: int = DEFAULT_REASONING_BUDGET,
        use_stream: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Inicializa o cliente de IA.

        Args:
            api_key: Chave de API (NVIDIA nvapi-...).
            base_url: URL base da API (NVIDIA NIM).
            model: Nome do modelo a ser utilizado.
            temperature: Temperatura da geração.
            top_p: Parâmetro top_p da geração.
            max_tokens: Limite máximo de tokens na resposta.
            reasoning_budget: Orçamento de raciocínio (modelos Nemotron).
            use_stream: Usar streaming na geração.
            max_retries: Número máximo de tentativas em caso de falha.
            retry_delay_seconds: Intervalo base entre tentativas.
            timeout_seconds: Timeout da requisição em segundos.
        """
        if not api_key:
            raise ValueError("AI_API_KEY não configurada.")

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._reasoning_budget = reasoning_budget
        self._use_stream = use_stream
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    @staticmethod
    def load_prompt(prompt_path: Path) -> str:
        """
        Carrega o conteúdo do arquivo de prompt.

        Args:
            prompt_path: Caminho para o arquivo news_prompt.txt.

        Returns:
            Conteúdo do prompt como string.

        Raises:
            FileNotFoundError: Se o arquivo não existir.
            ValueError: Se o arquivo estiver vazio.
        """
        if not prompt_path.exists():
            raise FileNotFoundError(f"Arquivo de prompt não encontrado: {prompt_path}")

        content = prompt_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Arquivo de prompt vazio: {prompt_path}")

        return content

    def _build_extra_body(self) -> dict[str, Any] | None:
        """Monta parâmetros extras conforme o modelo."""
        model_lower = self._model.lower()

        if "nemotron" in model_lower:
            return {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": self._reasoning_budget,
            }

        if "deepseek" in model_lower:
            return {"chat_template_kwargs": {"thinking": False}}

        return None

    @staticmethod
    def _collect_stream(stream: Iterator[Any]) -> str:
        """
        Agrega chunks de streaming em texto final.

        Ignora reasoning_content e usa apenas o content da resposta.
        """
        content_parts: list[str] = []

        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue

            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)

        return "".join(content_parts).strip()

    def generate_news_summary(self, prompt: str) -> str:
        """
        Gera o resumo de notícias a partir do prompt fornecido.

        Args:
            prompt: Texto do prompt com instruções de geração.

        Returns:
            Resumo gerado pelo modelo de IA.

        Raises:
            OpenAIServiceError: Se todas as tentativas falharem.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "Solicitando resumo à API NVIDIA (modelo=%s, stream=%s, tentativa=%d/%d)",
                    self._model,
                    self._use_stream,
                    attempt,
                    self._max_retries,
                )

                request_kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Você é o editor-chefe do DevBrief News. "
                                "Produza textos CLEAN, bem espaçados e fáceis de ler no celular. "
                                "Cada subseção tem emoji+título numa linha e o texto nas linhas abaixo. "
                                "Nunca amontoe tudo num bloco só. "
                                "Use tom analítico e narrativo. Links reais apenas ao final das subseções. "
                                "Sempre inclua o Bordão do Dia na seção 10. "
                                "Responda em português do Brasil."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self._temperature,
                    "top_p": self._top_p,
                    "max_tokens": self._max_tokens,
                    "stream": self._use_stream,
                }

                extra_body = self._build_extra_body()
                if extra_body:
                    request_kwargs["extra_body"] = extra_body

                if self._use_stream:
                    stream = self._client.chat.completions.create(**request_kwargs)
                    summary = self._collect_stream(stream)
                    if not summary:
                        raise OpenAIServiceError("Resposta streaming vazia ou inválida.")
                else:
                    response = self._client.chat.completions.create(**request_kwargs)
                    summary = self._extract_content(response)

                logger.info("Resumo gerado com sucesso (%d caracteres).", len(summary))
                return summary

            except (APITimeoutError, requests.Timeout) as exc:
                last_error = exc
                logger.warning("Timeout na API (tentativa %d): %s", attempt, exc)
            except RateLimitError as exc:
                last_error = exc
                logger.warning("Rate limit da API (tentativa %d): %s", attempt, exc)
            except APIConnectionError as exc:
                last_error = exc
                logger.warning("Falha de conexão com a API (tentativa %d): %s", attempt, exc)
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 429:
                    raise OpenAIServiceError(
                        f"Erro permanente da API (HTTP {exc.status_code}): {exc}"
                    ) from exc
                logger.warning(
                    "Erro HTTP da API (tentativa %d, status=%s): %s",
                    attempt,
                    exc.status_code,
                    exc,
                )
            except OpenAIServiceError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("Erro inesperado na API (tentativa %d): %s", attempt, exc)

            if attempt < self._max_retries:
                delay = self._retry_delay_seconds * attempt
                logger.info("Aguardando %.1fs antes da próxima tentativa...", delay)
                time.sleep(delay)

        raise OpenAIServiceError(
            f"Falha ao gerar resumo após {self._max_retries} tentativas."
        ) from last_error

    @staticmethod
    def _extract_content(response: object) -> str:
        """
        Extrai e valida o conteúdo textual da resposta da API.

        Args:
            response: Objeto de resposta da API.

        Returns:
            Texto do resumo.

        Raises:
            OpenAIServiceError: Se a resposta for inválida ou vazia.
        """
        choices = getattr(response, "choices", None)
        if not choices:
            raise OpenAIServiceError("Resposta da API sem choices.")

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message else None

        if not content or not str(content).strip():
            raise OpenAIServiceError("Resposta da API vazia ou inválida.")

        return str(content).strip()
