"""Endpoint público — notícias RSS (standalone, otimizado para Vercel)."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    "mundo": "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=800&q=80",
}

TIMEOUT = 4


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _extract_image(html: str) -> str:
    match = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
    return match.group(1) if match else ""


def _parse_feed(xml_text: str, source: str, category: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
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

        published = _parse_date(pub_raw)
        pub_label = published.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M") if published else "Agora"
        image = _extract_image(summary) or FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["brasil"])
        label = next((f["label"] for f in FEEDS if f["category"] == category), category)

        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "category": category,
                "category_label": label,
                "summary": summary,
                "published": pub_label,
                "image": image,
            }
        )
    return items


def _fetch_market() -> list[dict[str, Any]]:
    try:
        response = requests.get(
            "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL",
            timeout=5,
            headers={"User-Agent": "DevBriefNewsBot/1.0"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    labels = {"USDBRL": "USD/BRL", "EURBRL": "EUR/BRL", "BTCBRL": "BTC/BRL"}
    quotes: list[dict[str, Any]] = []
    for key, label in labels.items():
        item = data.get(key)
        if not item:
            continue
        try:
            pct = float(str(item.get("pctChange", "0")).replace(",", "."))
        except ValueError:
            pct = 0.0
        quotes.append(
            {
                "label": label,
                "value": str(item.get("bid", "—")),
                "change": f"{pct:+.2f}%",
                "positive": pct >= 0,
            }
        )
    return quotes


def _build_payload() -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()

    for feed in FEEDS:
        try:
            response = requests.get(
                feed["url"],
                timeout=TIMEOUT,
                headers={"User-Agent": "DevBriefNewsBot/1.0"},
            )
            response.raise_for_status()
            for item in _parse_feed(response.text, feed["name"], feed["category"]):
                key = re.sub(r"[^a-z0-9]+", "", item["title"].lower())[:60]
                if key in seen:
                    continue
                seen.add(key)
                articles.append(item)
        except Exception as exc:
            logger.warning("Feed %s falhou: %s", feed["name"], exc)

    categories: dict[str, list[dict[str, Any]]] = {
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
        "source": "rss_standalone",
        "featured": articles[0] if articles else None,
        "latest": articles[:12],
        "categories": categories,
        "market": _fetch_market(),
        "updated_at": articles[0]["published"] if articles else "",
        "total": len(articles),
    }


class handler(BaseHTTPRequestHandler):
    """Handler serverless Vercel."""

    def do_GET(self) -> None:  # noqa: N802
        logging.basicConfig(level=logging.INFO)
        try:
            payload = _build_payload()
            if not payload.get("total"):
                _send_json(self, 200, {**payload, "ok": True, "error": "Nenhum feed disponível agora."})
                return
            _send_json(self, 200, payload)
        except Exception as exc:
            logger.exception("Erro /api/news: %s", exc)
            _send_json(self, 500, {"ok": False, "error": str(exc)})
