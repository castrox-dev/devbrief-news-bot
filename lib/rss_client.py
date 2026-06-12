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
    {"name": "G1", "url": "https://g1.globo.com/rss/g1/", "category": "brasil", "label": "Brasil", "lang": "pt"},
    {"name": "G1 Tech", "url": "https://g1.globo.com/rss/g1/tecnologia/", "category": "tecnologia", "label": "Tecnologia", "lang": "pt"},
    {"name": "G1 Economia", "url": "https://g1.globo.com/rss/g1/economia/", "category": "mercado", "label": "Mercado", "lang": "pt"},
    {"name": "InfoMoney", "url": "https://www.infomoney.com.br/feed/", "category": "mercado", "label": "Mercado", "lang": "pt"},
    {"name": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "category": "brasil", "label": "Brasil", "lang": "pt"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tecnologia", "label": "Tecnologia", "lang": "en"},
]

FALLBACK_IMAGES: dict[str, list[str]] = {
    "brasil": [
        "https://images.unsplash.com/photo-1483728642387-6c3bddae7a35?w=900&q=80",
        "https://images.unsplash.com/photo-1541872703-74c5ccc27177?w=900&q=80",
        "https://images.unsplash.com/photo-1511578314322-379afb476865?w=900&q=80",
    ],
    "tecnologia": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=900&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=900&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=900&q=80",
    ],
    "mercado": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=900&q=80",
        "https://images.unsplash.com/photo-1642790106117-e829e14a795f?w=900&q=80",
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=900&q=80",
    ],
    "mundo": [
        "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=900&q=80",
        "https://images.unsplash.com/photo-1504711434967-e33886168f1c?w=900&q=80",
        "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=900&q=80",
    ],
}

IMAGE_URL_PATTERN = re.compile(
    r"(https?://[^\s\"'<>]+(?:\.(?:jpg|jpeg|png|webp|gif)|"
    r"wp-content/uploads/[^\s\"'<>]+|"
    r"i\.s\.globo\.com/[^\s\"'<>]+|"
    r"infomoney\.com\.br/uploads/[^\s\"'<>]+))",
    re.I,
)

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


def _fallback_image(category: str, seed: str) -> str:
    options = FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["brasil"])
    idx = sum(ord(char) for char in seed) % len(options)
    return options[idx]


def _normalize_image_url(url: str) -> str:
    clean = url.strip().split("?")[0] if "?" in url and ".jpg" not in url.lower() else url.strip()
    if clean.startswith("//"):
        return "https:" + clean
    return clean


def _extract_image(html: str, category: str, seed: str = "") -> str:
    if not html:
        return _fallback_image(category, seed or category)

    for pattern in (
        r'(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',
        r'(?:url|href)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
        r"property=[\"']og:image[\"']\s+content=[\"']([^\"']+)[\"']",
        r"content=[\"']([^\"']+)[\"']\s+property=[\"']og:image[\"']",
    ):
        for match in re.finditer(pattern, html, re.I):
            candidate = _normalize_image_url(match.group(1))
            if candidate.startswith("http") and "emoji" not in candidate.lower():
                return candidate

    match = IMAGE_URL_PATTERN.search(html)
    if match:
        return _normalize_image_url(match.group(1))

    return _fallback_image(category, seed or html[:40])


def _parse_item_node(node) -> tuple[str, str, str, str, str]:
    """Extrai título, link, data, HTML bruto e imagem direta do item RSS."""
    title = ""
    link = ""
    pub_raw = ""
    html_parts: list[str] = []
    direct_image = ""

    for child in node:
        tag = child.tag.split("}")[-1].lower()
        if tag == "title" and child.text:
            title = child.text.strip()
        elif tag == "link":
            link = (child.text or "").strip() or child.get("href", "")
        elif tag in ("pubdate", "published", "updated") and child.text:
            pub_raw = child.text.strip()
        elif tag == "enclosure":
            enc_url = child.get("url", "")
            enc_type = (child.get("type") or "").lower()
            if enc_url and ("image" in enc_type or re.search(r"\.(jpg|jpeg|png|webp)", enc_url, re.I)):
                direct_image = enc_url
        elif tag in ("content", "thumbnail"):
            media_url = child.get("url") or child.get("href") or ""
            medium = (child.get("medium") or child.get("type") or "").lower()
            if media_url and ("image" in medium or "image" in tag or re.search(r"\.(jpg|jpeg|png|webp)", media_url, re.I)):
                direct_image = direct_image or media_url
        elif tag in ("description", "summary", "content", "encoded") and child.text:
            html_parts.append(child.text)

    combined_html = " ".join(html_parts)
    return title, link, pub_raw, combined_html, direct_image


def _parse_feed(
    xml_text: str, source: str, category: str, label: str, lang: str = "pt"
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return items

    nodes = root.findall(".//item") or root.findall(".//{*}entry")
    for node in nodes[:6]:
        title, link, pub_raw, html_raw, direct_image = _parse_item_node(node)

        if not title or not link:
            continue

        image = direct_image or _extract_image(html_raw, category, seed=title)
        body = _strip_html(html_raw)
        summary = body[:220] if body else ""

        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "category": category,
                "category_label": label,
                "lang": lang,
                "summary": summary,
                "body": body[:1500],
                "published": _format_datetime(pub_raw),
                "published_at": _parse_datetime(pub_raw),
                "image": image,
            }
        )
    return items


def _fetch_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    xml_text = _fetch_url(feed["url"])
    return _parse_feed(
        xml_text,
        feed["name"],
        feed["category"],
        feed["label"],
        feed.get("lang", "pt"),
    )


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
        "lang": item.get("lang", "pt"),
        "summary": item.get("summary", ""),
        "body": item.get("body", item.get("summary", "")),
        "published": item.get("published", ""),
        "image": item.get("image", ""),
    }


def find_article_by_url(url: str) -> dict[str, str] | None:
    """Busca artigo pelo URL original (para página interna)."""
    target = url.strip()
    if not target:
        return None
    for item in fetch_all_articles():
        if item.get("url") == target:
            return _public_article(item)
    return None


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
