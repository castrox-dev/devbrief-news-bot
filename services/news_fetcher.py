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
    {"name": "Money Times", "url": "https://www.moneytimes.com.br/feed/", "category": "mercado"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tecnologia"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tecnologia"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "tecnologia"},
    {"name": "BBC Mundo", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "mundo"},
    {"name": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "category": "brasil"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tecnologia"},
]

RSS_FEEDS_LITE: Final[list[dict[str, str]]] = [
    {"name": "G1", "url": "https://g1.globo.com/rss/g1/", "category": "brasil"},
    {"name": "G1 Economia", "url": "https://g1.globo.com/rss/g1/economia/", "category": "mercado"},
    {"name": "G1 Tecnologia", "url": "https://g1.globo.com/rss/g1/tecnologia/", "category": "tecnologia"},
    {"name": "InfoMoney", "url": "https://www.infomoney.com.br/feed/", "category": "mercado"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tecnologia"},
    {"name": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "category": "brasil"},
]


CATEGORY_IMAGES: Final[dict[str, str]] = {
    "brasil": "https://images.unsplash.com/photo-1483728642387-6c3bddae7a35?w=800&q=80",
    "mundo": "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=800&q=80",
    "tecnologia": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
    "mercado": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
}

CATEGORY_LABELS: Final[dict[str, str]] = {
    "brasil": "Brasil",
    "mundo": "Mundo",
    "tecnologia": "Tecnologia",
    "mercado": "Mercado",
}


@dataclass
class NewsArticle:
    """Representa um artigo coletado de feed RSS."""

    title: str
    url: str
    source: str
    category: str
    summary: str
    published: datetime | None = None
    image: str = ""


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


def _extract_image(item: ElementTree.Element, raw_html: str) -> str:
    """Extrai URL de imagem de item RSS (media, enclosure ou HTML)."""
    for child in item:
        local = child.tag.split("}")[-1].lower()
        url = child.get("url") or child.get("href") or ""
        media_type = (child.get("type") or child.get("medium") or "").lower()
        if url and ("image" in media_type or local in ("thumbnail", "content")):
            if local == "content" and child.get("medium") == "image":
                return url
            if "image" in media_type or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                return url

    enclosure = item.find("enclosure")
    if enclosure is not None:
        enc_url = enclosure.get("url", "")
        enc_type = (enclosure.get("type") or "").lower()
        if enc_url and "image" in enc_type:
            return enc_url

    match = re.search(
        r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']',
        raw_html,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


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

        raw_description = _extract_text(item, "description") or _extract_text(item, "summary") or _extract_text(item, "content")
        summary = _strip_html(raw_description)
        image = _extract_image(item, raw_description)

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
                    image=image,
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


def _fetch_single_feed(
    feed: dict[str, str],
    cutoff: datetime,
    timeout: int,
    max_per_feed: int,
) -> list[NewsArticle]:
    """Coleta artigos de um único feed RSS."""
    articles: list[NewsArticle] = []
    try:
        logger.info("Coletando RSS: %s", feed["name"])
        response = requests.get(
            feed["url"],
            timeout=timeout,
            headers={"User-Agent": "DevBriefNewsBot/1.0"},
        )
        response.raise_for_status()
        items = _parse_rss_items(response.text, feed["name"], feed["category"])

        for article in items[:max_per_feed]:
            if not _is_recent(article, cutoff):
                continue
            articles.append(article)
    except Exception as exc:
        logger.warning("Falha ao coletar %s: %s", feed["name"], exc)
    return articles


def fetch_news_articles(
    max_age_hours: int = MAX_AGE_HOURS,
    *,
    lite: bool = False,
) -> list[NewsArticle]:
    """
    Coleta artigos de múltiplos feeds RSS.

    Args:
        max_age_hours: Janela máxima de horas para considerar notícias.
        lite: Usa subset reduzido de feeds (rápido, para fallback web).

    Returns:
        Lista de artigos únicos ordenados por data (mais recentes primeiro).
    """
    feeds = RSS_FEEDS_LITE if lite else RSS_FEEDS
    timeout = 8 if lite else REQUEST_TIMEOUT
    max_total = 30 if lite else MAX_TOTAL
    max_per_feed = 5 if lite else MAX_PER_FEED

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_articles: list[NewsArticle] = []
    seen_titles: set[str] = set()

    for feed in feeds:
        for article in _fetch_single_feed(feed, cutoff, timeout, max_per_feed):
            key = _normalize_title(article.title)
            if key in seen_titles:
                continue
            seen_titles.add(key)
            all_articles.append(article)

    all_articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return all_articles[:max_total]


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


def get_article_image(article: NewsArticle) -> str:
    """Retorna imagem do artigo ou fallback por categoria."""
    if article.image:
        return article.image
    return CATEGORY_IMAGES.get(article.category, CATEGORY_IMAGES["brasil"])


def format_published_label(published: datetime | None) -> str:
    """Formata data para exibição na web."""
    if published is None:
        return "Agora"
    pub = published
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    local = pub.astimezone(timezone(timedelta(hours=-3)))
    return local.strftime("%d/%m/%Y %H:%M")


def articles_to_web_payload(articles: list[NewsArticle]) -> list[dict[str, str]]:
    """Serializa artigos para consumo pela landing page."""
    payload: list[dict[str, str]] = []
    for article in articles:
        payload.append(
            {
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "category": article.category,
                "category_label": CATEGORY_LABELS.get(article.category, article.category),
                "summary": article.summary[:220] if article.summary else "",
                "published": format_published_label(article.published),
                "image": get_article_image(article),
            }
        )
    return payload
