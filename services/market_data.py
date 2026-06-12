"""Cotações e indicadores de mercado para enriquecer o briefing diário."""

from __future__ import annotations

import logging
from typing import Final

import requests

logger = logging.getLogger(__name__)

AWESOME_API_URL: Final[str] = (
    "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL"
)
REQUEST_TIMEOUT: Final[int] = 10

LABELS: Final[dict[str, str]] = {
    "USDBRL": "Dólar (USD/BRL)",
    "EURBRL": "Euro (EUR/BRL)",
    "BTCBRL": "Bitcoin (BTC/BRL)",
}


def fetch_market_snapshot() -> str:
    """
    Busca cotações recentes de ativos-chave.

    Returns:
        Texto formatado para injeção no prompt da IA, ou string vazia em caso de falha.
    """
    try:
        response = requests.get(
            AWESOME_API_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "DevBriefNewsBot/1.0"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("Falha ao buscar cotações de mercado: %s", exc)
        return ""

    lines = ["=== MERCADO FINANCEIRO (cotações recentes) ==="]

    for key, label in LABELS.items():
        item = data.get(key)
        if not item:
            continue
        bid = item.get("bid", "—")
        pct = item.get("pctChange", "—")
        lines.append(f"- {label}: R$ {bid} (variação: {pct}%)")

    if len(lines) == 1:
        return ""

    lines.append("")
    lines.append(
        "Use estes números na seção 'Mercado e Investimentos' quando relevante. "
        "Não invente cotações além destes dados."
    )
    return "\n".join(lines)
