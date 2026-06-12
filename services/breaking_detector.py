"""Detecção heurística de notícias de alto impacto para alertas imediatos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from services.news_fetcher import NewsArticle

IMPACT_KEYWORDS: Final[dict[str, int]] = {
    # Mercado financeiro
    r"\bselic\b": 4,
    r"\bcopom\b": 4,
    r"\bipca\b": 3,
    r"\binfla[cç][aã]o\b": 3,
    r"\bibovespa\b": 4,
    r"\bb3\b": 3,
    r"\bd[oó]lar\b": 3,
    r"\bfed\b": 4,
    r"\bjuros\b": 3,
    r"\bpetr[oó]leo\b": 3,
    r"\bbitcoin\b": 3,
    r"\bcripto": 2,
    r"\brecess[aã]o\b": 4,
    r"\bdefault\b": 4,
    r"\bipo\b": 2,
    r"\bwall street\b": 3,
  # Impacto geral
    r"\burgente\b": 5,
    r"\bbreaking\b": 5,
    r"\bexplos[aã]o\b": 4,
    r"\bataque\b": 4,
    r"\bguerra\b": 4,
    r"\bterremoto\b": 4,
    r"\bapag[aã]o\b": 4,
    r"\bqueda de \d+%": 5,
    r"\balta de \d+%": 4,
    r"\brecorde\b": 3,
    r"\bcrash\b": 5,
    r"\bhack\b": 3,
    r"\bvazamento\b": 3,
    r"\bopenai\b": 2,
    r"\bnvidia\b": 2,
}

CATEGORY_BOOST: Final[dict[str, int]] = {
    "mercado": 2,
    "brasil": 1,
    "mundo": 1,
    "tecnologia": 1,
}

RECENCY_BOOST_HOURS: Final[tuple[tuple[int, int], ...]] = (
    (1, 3),
    (3, 2),
    (6, 1),
)

DEFAULT_MIN_SCORE: Final[int] = 5


@dataclass
class ScoredArticle:
    """Artigo com pontuação de impacto."""

    article: NewsArticle
    score: int
    matched_terms: list[str]


def _hours_ago(published: datetime | None) -> float | None:
    if published is None:
        return None
    pub = published
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - pub
    return delta.total_seconds() / 3600


def _recency_boost(hours_ago: float | None) -> int:
    if hours_ago is None:
        return 0
    for limit, boost in RECENCY_BOOST_HOURS:
        if hours_ago <= limit:
            return boost
    return 0


def score_article(article: NewsArticle) -> ScoredArticle:
    """Calcula pontuação de impacto de um artigo."""
    text = f"{article.title} {article.summary}".lower()
    score = 0
    matched: list[str] = []

    for pattern, points in IMPACT_KEYWORDS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            score += points
            matched.append(pattern.replace("\\b", "").replace("\\", ""))

    score += CATEGORY_BOOST.get(article.category, 0)
    score += _recency_boost(_hours_ago(article.published))

    return ScoredArticle(article=article, score=score, matched_terms=matched)


def detect_breaking_candidates(
    articles: list[NewsArticle],
    min_score: int = DEFAULT_MIN_SCORE,
    max_candidates: int = 5,
) -> list[ScoredArticle]:
    """
    Retorna artigos candidatos a alerta de breaking news.

    Args:
        articles: Artigos recentes coletados.
        min_score: Pontuação mínima para considerar.
        max_candidates: Máximo de candidatos enviados à IA.

    Returns:
        Lista ordenada por score decrescente.
    """
    scored = [score_article(article) for article in articles]
    candidates = [item for item in scored if item.score >= min_score]
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:max_candidates]
