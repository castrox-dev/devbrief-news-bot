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


def fetch_market_quotes() -> list[dict[str, str | bool]]:
    """
    Busca cotações formatadas para a landing page.

    Returns:
        Lista de cotações com label, valor e variação.
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
        return []

    quotes: list[dict[str, str | bool]] = []
    short_labels = {
        "USDBRL": "USD/BRL",
        "EURBRL": "EUR/BRL",
        "BTCBRL": "BTC/BRL",
    }

    for key, label in short_labels.items():
        item = data.get(key)
        if not item:
            continue
        pct_raw = str(item.get("pctChange", "0")).replace(",", ".")
        try:
            pct_value = float(pct_raw)
        except ValueError:
            pct_value = 0.0
        quotes.append(
            {
                "label": label,
                "value": str(item.get("bid", "—")),
                "change": f"{pct_value:+.2f}%",
                "positive": pct_value >= 0,
            }
        )
    return quotes
