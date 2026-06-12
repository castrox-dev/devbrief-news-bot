"""Endpoint público — notícias RSS (stdlib only, compatível com Vercel)."""

from __future__ import annotations

import json
import logging
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

FEEDS = [
    {"name": "G1", "url": "https://g1.globo.com/rss/g1/", "category": "brasil", "label": "Brasil"},
    {"name": "G1 Tech", "url": "https://g1.globo.com/rss/g1/tecnologia/", "category": "tecnologia", "label": "Tecnologia"},
    {"name": "G1 Economia", "url": "https://g1.globo.com/rss/g1/economia/", "category": "mercado", "label": "Mercado"},
]

FALLBACK_IMAGES = {
    "brasil": "https://images.unsplash.com/photo-1483728642387-6c3bddae7a35?w=800&q=80",
    "tecnologia": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
    "mercado": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
}

TIMEOUT = 4
USER_AGENT = "DevBriefNewsBot/1.0"


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _parse_date(raw: str) -> str:
    if not raw:
        return "Agora"
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "Agora"


def _extract_image(html: str, category: str) -> str:
    match = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
    if match:
        return match.group(1)
    return FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["brasil"])


def _parse_feed(xml_text: str, source: str, category: str, label: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return items

    nodes = root.findall(".//item") or root.findall(".//{*}entry")
    for node in nodes[:5]:
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
                summary = _strip_html(child.text)[:220]
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
                "summary": summary,
                "published": _parse_date(pub_raw),
                "image": _extract_image(summary, category),
            }
        )
    return items


def _build_payload() -> dict[str, Any]:
    articles: list[dict[str, str]] = []
    seen: set[str] = set()

    for feed in FEEDS:
        try:
            xml_text = _fetch_url(feed["url"])
            for item in _parse_feed(xml_text, feed["name"], feed["category"], feed["label"]):
                key = re.sub(r"[^a-z0-9]+", "", item["title"].lower())[:60]
                if key in seen:
                    continue
                seen.add(key)
                articles.append(item)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("Feed %s falhou: %s", feed["name"], exc)

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


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        logging.basicConfig(level=logging.INFO)
        try:
            payload = _build_payload()
            _send_json(self, 200, payload)
        except Exception as exc:
            logger.exception("Erro /api/news: %s", exc)
            _send_json(self, 500, {"ok": False, "error": str(exc)})
