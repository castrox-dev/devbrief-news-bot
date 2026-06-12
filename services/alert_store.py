"""Armazenamento de alertas já enviados (Upstash Redis REST ou memória local)."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Final

import requests

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS: Final[int] = 72 * 3600  # 72 horas
REQUEST_TIMEOUT: Final[float] = 10.0

_memory_store: dict[str, float] = {}


class AlertStore:
    """Evita reenvio de alertas de breaking news para a mesma notícia."""

    def __init__(
        self,
        redis_url: str = "",
        redis_token: str = "",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis_url = redis_url.rstrip("/")
        self._redis_token = redis_token
        self._ttl_seconds = ttl_seconds
        self._use_redis = bool(self._redis_url and self._redis_token)

        if not self._use_redis:
            logger.warning(
                "UPSTASH_REDIS_REST_URL/TOKEN não configurados — "
                "deduplicação de alertas limitada a esta execução."
            )

    @classmethod
    def from_env(cls) -> AlertStore:
        """Cria instância a partir de variáveis de ambiente."""
        return cls(
            redis_url=os.getenv("UPSTASH_REDIS_REST_URL", "").strip(),
            redis_token=os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip(),
            ttl_seconds=int(os.getenv("ALERT_TTL_SECONDS", str(DEFAULT_TTL_SECONDS))),
        )

    @staticmethod
    def article_key(url: str, title: str) -> str:
        """Gera chave estável para um artigo."""
        raw = f"{url.strip().lower()}|{title.strip().lower()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"breaking:{digest}"

    def was_sent(self, key: str) -> bool:
        """Verifica se o alerta já foi enviado."""
        if self._use_redis:
            return self._redis_get(key) is not None
        return key in _memory_store

    def mark_sent(self, key: str) -> None:
        """Marca alerta como enviado."""
        if self._use_redis:
            self._redis_set(key, "1", self._ttl_seconds)
            return
        import time

        _memory_store[key] = time.time()

    def _redis_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._redis_token}"}

    def _redis_get(self, key: str) -> str | None:
        try:
            response = requests.get(
                f"{self._redis_url}/get/{key}",
                headers=self._redis_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json().get("result")
            return str(result) if result is not None else None
        except Exception as exc:
            logger.warning("Falha ao ler alerta no Redis (%s): %s", key, exc)
            return None

    def _redis_set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            response = requests.post(
                f"{self._redis_url}/setex/{key}/{ttl_seconds}/{value}",
                headers=self._redis_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Falha ao salvar alerta no Redis (%s): %s", key, exc)
