"""Cotações e indicadores de mercado para enriquecer o briefing diário."""

from __future__ import annotations

import json
import logging
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

AWESOME_API_URL: Final[str] = (
    "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL"
)
FRANKFURTER_URL: Final[str] = "https://api.frankfurter.app/latest?from={code}&to=BRL"
COINGECKO_BTC_URL: Final[str] = (
    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
)
REQUEST_TIMEOUT: Final[int] = 8
USER_AGENT: Final[str] = "DevBriefNewsBot/1.0"
MAX_RETRIES: Final[int] = 2

LABELS: Final[dict[str, str]] = {
    "USDBRL": "Dólar (USD/BRL)",
    "EURBRL": "Euro (EUR/BRL)",
    "BTCBRL": "Bitcoin (BTC/BRL)",
}


def _fetch_json(url: str) -> dict[str, Any]:
    """Busca JSON via stdlib (compatível com Vercel serverless)."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_awesome_quotes(data: dict[str, Any]) -> list[dict[str, str | bool]]:
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


def _fetch_awesome_quotes() -> list[dict[str, str | bool]]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = _fetch_json(AWESOME_API_URL)
            quotes = _parse_awesome_quotes(data)
            if quotes:
                return quotes
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("AwesomeAPI tentativa %s/%s: %s", attempt, MAX_RETRIES, exc)
    if last_error:
        raise last_error
    return []


def _fetch_fallback_quotes() -> list[dict[str, str | bool]]:
    """Fallback quando AwesomeAPI falha (comum em IPs de datacenter/Vercel)."""
    quotes: list[dict[str, str | bool]] = []

    for code, label in (("USD", "USD/BRL"), ("EUR", "EUR/BRL")):
        try:
            data = _fetch_json(FRANKFURTER_URL.format(code=code))
            rate = data.get("rates", {}).get("BRL")
            if rate is not None:
                quotes.append(
                    {
                        "label": label,
                        "value": f"{float(rate):.4f}",
                        "change": "—",
                        "positive": True,
                    }
                )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Frankfurter %s falhou: %s", code, exc)

    try:
        data = _fetch_json(COINGECKO_BTC_URL)
        brl = data.get("bitcoin", {}).get("brl")
        if brl is not None:
            quotes.append(
                {
                    "label": "BTC/BRL",
                    "value": str(int(float(brl))),
                    "change": "—",
                    "positive": True,
                }
            )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("CoinGecko BTC falhou: %s", exc)

    return quotes


def fetch_market_snapshot() -> str:
    """
    Busca cotações recentes de ativos-chave.

    Returns:
        Texto formatado para injeção no prompt da IA, ou string vazia em caso de falha.
    """
    try:
        data = _fetch_json(AWESOME_API_URL)
    except Exception as exc:
        logger.warning("Falha ao buscar cotações de mercado: %s", exc)
        quotes = _fetch_fallback_quotes()
        if not quotes:
            return ""
        lines = ["=== MERCADO FINANCEIRO (cotações recentes) ==="]
        for quote in quotes:
            lines.append(f"- {quote['label']}: R$ {quote['value']}")
        lines.append("")
        return "\n".join(lines)

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
        quotes = _fetch_awesome_quotes()
        if quotes:
            return quotes
    except Exception as exc:
        logger.warning("AwesomeAPI indisponível: %s", exc)

    quotes = _fetch_fallback_quotes()
    if quotes:
        logger.info("Cotações via fallback (%s itens)", len(quotes))
    return quotes
