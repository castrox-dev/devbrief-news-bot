"""Normalização do texto do briefing para layout clean e legível."""

from __future__ import annotations

import re

HEADER: str = "📰 DevBrief News — Resumo das Principais Notícias (Últimas 24h)"


def normalize_summary(text: str) -> str:
    """
    Limpa e padroniza o briefing gerado pela IA.

    Args:
        text: Texto bruto da IA.

    Returns:
        Texto formatado com espaçamento consistente.
    """
    cleaned = text.strip()

    if not cleaned.startswith("📰"):
        cleaned = f"{HEADER}\n\n{cleaned}"

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)

    cleaned = _ensure_section_spacing(cleaned)
    cleaned = _ensure_bordao(cleaned)

    return cleaned.strip() + "\n"


def _ensure_section_spacing(text: str) -> str:
    """Garante linha em branco antes de seções numeradas."""
    return re.sub(
        r"(?<!\n)\n(\d+\.\s)",
        r"\n\n\1",
        text,
    )


def _ensure_bordao(text: str) -> str:
    """Garante que o bordão do dia exista ao final."""
    if re.search(r"bord[aã]o\s+do\s+dia", text, re.IGNORECASE):
        return text

    return (
        f"{text}\n\n"
        "10. 💬 Bordão do Dia\n\n"
        "\"Quem lê hoje, decide amanhã — e o DevBrief te mantém na frente.\""
    )
