"""Cliente RSS leve (stdlib) para endpoints Vercel."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

FEEDS = [
    {"name": "G1", "url": "https://g1.globo.com/rss/g1/", "category": "brasil", "label": "Brasil"},
    {"name": "G1 Tech", "url": "https://g1.globo.com/rss/g1/tecnologia/", "category": "tecnologia", "label": "Tecnologia"},
    {"name": "G1 Economia", "url": "https://g1.globo.com/rss/g1/economia/", "category": "mercado", "label": "Mercado"},
    {"name": "InfoMoney", "url": "https://www.infomoney.com.br/feed/", "category": "mercado", "label": "Mercado"},
    {"name": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "category": "brasil", "label": "Brasil"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tecnologia", "label": "Tecnologia"},
]

FALLBACK_IMAGES = {
    "brasil": "https://images.unsplash.com/photo-1483728642387-6c3bddae7a35?w=800&q=80",
    "tecnologia": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
    "mercado": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
    "mundo": "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=800&q=80",
}

TIMEOUT = 5
USER_AGENT = "DevBriefNewsBot/1.0"


def _fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _format_datetime(raw: str) -> str:
    parsed = _parse_datetime(raw)
    if not parsed:
        return "Agora"
    return parsed.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M")


def _extract_image(html: str, category: str) -> str:
    match = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
    if match:
        return match.group(1)
    return FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["brasil"])


def _parse_feed(xml_text: str, source: str, category: str, label: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return items

    nodes = root.findall(".//item") or root.findall(".//{*}entry")
    for node in nodes[:6]:
        title = ""
        link = ""
        summary = ""
        pub_raw = ""
        for child in node:
            tag = child.tag.split("}")[-1].lower()
            if tag == "title" and child.text:
                title = child.text.strip()
            elif tag == "link":
                link = (child.text or "").strip() or child.get("href", "")
            elif tag in ("description", "summary", "content") and child.text:
                summary = _strip_html(child.text)[:400]
            elif tag in ("pubdate", "published", "updated") and child.text:
                pub_raw = child.text.strip()

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "category": category,
                "category_label": label,
                "summary": summary[:220],
                "published": _format_datetime(pub_raw),
                "published_at": _parse_datetime(pub_raw),
                "image": _extract_image(summary, category),
            }
        )
    return items


def _fetch_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    xml_text = _fetch_url(feed["url"])
    return _parse_feed(xml_text, feed["name"], feed["category"], feed["label"])


def fetch_all_articles(*, max_feeds: int | None = None) -> list[dict[str, Any]]:
    """Coleta artigos dos feeds (paralelo para caber no timeout da Vercel)."""
    feeds = FEEDS[:max_feeds] if max_feeds else FEEDS
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=min(4, len(feeds))) as pool:
        futures = {pool.submit(_fetch_feed, feed): feed for feed in feeds}
        for future in as_completed(futures):
            feed = futures[future]
            try:
                for item in future.result():
                    key = re.sub(r"[^a-z0-9]+", "", item["title"].lower())[:60]
                    if key in seen:
                        continue
                    seen.add(key)
                    articles.append(item)
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                logger.warning("Feed %s falhou: %s", feed["name"], exc)

    return articles


def _public_article(item: dict[str, Any]) -> dict[str, str]:
    """Remove campos internos (ex.: datetime) do payload JSON."""
    return {
        "title": item["title"],
        "url": item["url"],
        "source": item.get("source", ""),
        "category": item.get("category", "brasil"),
        "category_label": item.get("category_label", ""),
        "summary": item.get("summary", ""),
        "published": item.get("published", ""),
        "image": item.get("image", ""),
    }


def build_news_payload() -> dict[str, Any]:
    """Monta JSON da landing page."""
    articles = [_public_article(item) for item in fetch_all_articles()]
    categories: dict[str, list[dict[str, str]]] = {
        "brasil": [],
        "mundo": [],
        "tecnologia": [],
        "mercado": [],
    }
    for item in articles:
        cat = item.get("category", "brasil")
        if cat in categories and len(categories[cat]) < 8:
            categories[cat].append(item)

    return {
        "ok": True,
        "source": "rss_stdlib",
        "featured": articles[0] if articles else None,
        "latest": articles[:12],
        "categories": categories,
        "market": [],
        "updated_at": articles[0]["published"] if articles else "",
        "total": len(articles),
    }
