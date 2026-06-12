"""Coleta de notícias reais via RSS para enriquecer o resumo com links verificáveis."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Final
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT: Final[int] = 15
MAX_AGE_HOURS: Final[int] = 24
MAX_PER_FEED: Final[int] = 8
MAX_TOTAL: Final[int] = 60
MAX_FOR_AI: Final[int] = 36
MAX_SUMMARY_CHARS: Final[int] = 120

# Limite por categoria enviado à IA (tecnologia tem prioridade)
AI_CATEGORY_LIMITS: Final[dict[str, int]] = {
    "tecnologia": 10,
    "brasil": 8,
    "mundo": 6,
    "mercado": 12,
}

RSS_FEEDS: Final[list[dict[str, str]]] = [
    {"name": "G1", "url": "https://g1.globo.com/rss/g1/", "category": "brasil"},
    {"name": "G1 Economia", "url": "https://g1.globo.com/rss/g1/economia/", "category": "mercado"},
    {"name": "G1 Tecnologia", "url": "https://g1.globo.com/rss/g1/tecnologia/", "category": "tecnologia"},
    {"name": "InfoMoney", "url": "https://www.infomoney.com.br/feed/", "category": "mercado"},
    {"name": "Valor Econômico", "url": "https://valor.globo.com/rss/", "category": "mercado"},
    {"name": "Estadão Economia", "url": "https://www.estadao.com.br/rss/economia", "category": "mercado"},
    {"name": "Money Times", "url": "https://www.moneytimes.com.br/feed/", "category": "mercado"},
    {"name": "UOL Economia", "url": "https://economia.uol.com.br/ultimas/index.xml", "category": "mercado"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tecnologia"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tecnologia"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "tecnologia"},
    {"name": "BBC Mundo", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "mundo"},
    {"name": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "category": "brasil"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tecnologia"},
]


@dataclass
class NewsArticle:
    """Representa um artigo coletado de feed RSS."""

    title: str
    url: str
    source: str
    category: str
    summary: str
    published: datetime | None = None


def _strip_html(text: str) -> str:
    """Remove tags HTML básicas do texto."""
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _parse_rss_date(raw: str) -> datetime | None:
    """Converte data RSS para datetime com timezone."""
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _extract_text(element: ElementTree.Element | None, tag: str) -> str:
    """Extrai texto de tag filha ou namespace RSS/Atom."""
    if element is None:
        return ""
    for child in element:
        local = child.tag.split("}")[-1].lower()
        if local == tag.lower():
            return (child.text or "").strip()
    return ""


def _parse_rss_items(xml_content: str, source: str, category: str) -> list[NewsArticle]:
    """Faz parse de um feed RSS/Atom."""
    articles: list[NewsArticle] = []
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as exc:
        logger.warning("Erro ao parsear RSS de %s: %s", source, exc)
        return articles

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{*}entry")

    for item in items[:MAX_PER_FEED]:
        title = _extract_text(item, "title")
        link = _extract_text(item, "link")
        if not link:
            link_el = item.find("link")
            if link_el is not None and link_el.get("href"):
                link = link_el.get("href", "")

        summary = _strip_html(_extract_text(item, "description"))
        if not summary:
            summary = _strip_html(_extract_text(item, "summary"))
        if not summary:
            summary = _strip_html(_extract_text(item, "content"))

        pub_raw = _extract_text(item, "pubDate") or _extract_text(item, "published") or _extract_text(item, "updated")
        published = _parse_rss_date(pub_raw)

        if title and link:
            articles.append(
                NewsArticle(
                    title=title,
                    url=link,
                    source=source,
                    category=category,
                    summary=summary[:400] if summary else "",
                    published=published,
                )
            )

    return articles


def _is_recent(article: NewsArticle, cutoff: datetime) -> bool:
    """Verifica se o artigo está dentro da janela de tempo."""
    if article.published is None:
        return True
    pub = article.published
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    return pub >= cutoff


def _normalize_title(title: str) -> str:
    """Normaliza título para deduplicação."""
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def fetch_news_articles(max_age_hours: int = MAX_AGE_HOURS) -> list[NewsArticle]:
    """
    Coleta artigos de múltiplos feeds RSS.

    Args:
        max_age_hours: Janela máxima de horas para considerar notícias.

    Returns:
        Lista de artigos únicos ordenados por data (mais recentes primeiro).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_articles: list[NewsArticle] = []
    seen_titles: set[str] = set()

    for feed in RSS_FEEDS:
        try:
            logger.info("Coletando RSS: %s", feed["name"])
            response = requests.get(
                feed["url"],
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "DevBriefNewsBot/1.0"},
            )
            response.raise_for_status()
            items = _parse_rss_items(response.text, feed["name"], feed["category"])

            for article in items:
                if not _is_recent(article, cutoff):
                    continue
                key = _normalize_title(article.title)
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                all_articles.append(article)

        except Exception as exc:
            logger.warning("Falha ao coletar %s: %s", feed["name"], exc)

    all_articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return all_articles[:MAX_TOTAL]


def select_articles_for_ai(articles: list[NewsArticle]) -> list[NewsArticle]:
    """
    Seleciona subconjunto de artigos para o prompt da IA, evitando payload excessivo.

    Prioriza tecnologia e mantém equilíbrio entre categorias.
    """
    by_category: dict[str, list[NewsArticle]] = {}
    for article in articles:
        by_category.setdefault(article.category, []).append(article)

    selected: list[NewsArticle] = []
    for category, limit in AI_CATEGORY_LIMITS.items():
        selected.extend(by_category.get(category, [])[:limit])

    if len(selected) < MAX_FOR_AI:
        remaining = [a for a in articles if a not in selected]
        selected.extend(remaining[: MAX_FOR_AI - len(selected)])

    return selected[:MAX_FOR_AI]


def format_articles_for_prompt(articles: list[NewsArticle]) -> str:
    """
    Formata artigos coletados para injeção no prompt da IA.

    Args:
        articles: Lista de artigos RSS.

    Returns:
        Texto estruturado com títulos, resumos e URLs reais.
    """
    if not articles:
        return "Nenhuma notícia RSS coletada. Use conhecimento recente, mas indique quando não houver link verificável."

    by_category: dict[str, list[NewsArticle]] = {}
    for article in articles:
        by_category.setdefault(article.category, []).append(article)

    lines = [
        "=== NOTÍCIAS REAIS COLETADAS (últimas 24h) ===",
        "Use APENAS estas URLs como referência. NÃO invente links.",
        "",
    ]

    category_labels = {
        "brasil": "🇧🇷 BRASIL",
        "mundo": "🌍 MUNDO",
        "tecnologia": "💻 TECNOLOGIA",
        "mercado": "📈 MERCADO",
    }

    for category, label in category_labels.items():
        items = by_category.get(category, [])
        if not items:
            continue
        lines.append(f"--- {label} ---")
        for i, article in enumerate(items, 1):
            summary = article.summary[:MAX_SUMMARY_CHARS] if article.summary else ""
            summary_part = f" | {summary}" if summary else ""
            lines.append(
                f"{i}. [{article.title}]({article.url}) — {article.source}{summary_part}"
            )
        lines.append("")

    lines.append(f"Total de fontes disponíveis: {len(articles)}")
    return "\n".join(lines)
