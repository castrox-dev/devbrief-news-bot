"""Tradução de notícias para o portal (PT ↔ EN)."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

TRANSLATE_TIMEOUT = 6
MAX_CHUNK = 4500
USER_AGENT = "DevBriefNewsBot/1.0"


def normalize_locale(lang: str) -> str:
    """Normaliza locale do cliente para 'pt' ou 'en'."""
    value = (lang or "pt").strip().lower()
    if value.startswith("en"):
        return "en"
    return "pt"


def needs_translation(article: dict[str, Any], target_lang: str) -> bool:
    source = article.get("lang", "pt")
    return source != target_lang


def _translate_chunk(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text
    if source == target:
        return text

    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={source}&tl={target}&dt=t&q={quote(text)}"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TRANSLATE_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Falha ao traduzir (%s→%s): %s", source, target, exc)
        return text

    try:
        parts = [segment[0] for segment in payload[0] if segment and segment[0]]
        return "".join(parts) if parts else text
    except (IndexError, TypeError):
        return text


def translate_text(text: str, source: str, target: str) -> str:
    """Traduz texto, dividindo em blocos se necessário."""
    if not text or source == target:
        return text

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= MAX_CHUNK:
            chunks.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, MAX_CHUNK)
        if split_at < MAX_CHUNK // 2:
            split_at = MAX_CHUNK
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    translated = [_translate_chunk(chunk, source, target) for chunk in chunks]
    return " ".join(translated)


def translate_article(article: dict[str, Any], target_lang: str) -> dict[str, Any]:
    """Traduz campos textuais de um artigo quando o idioma da fonte difere."""
    if not article or not needs_translation(article, target_lang):
        return article

    source_lang = article.get("lang", "pt")
    result = dict(article)

    for field in ("title", "summary", "body"):
        value = result.get(field, "")
        if value:
            result[field] = translate_text(str(value), source_lang, target_lang)

    result["translated"] = True
    result["locale"] = target_lang
    return result


def _translate_many(articles: list[dict[str, Any]], target_lang: str) -> list[dict[str, Any]]:
    if not articles:
        return articles

    indexed = list(enumerate(articles))
    results: dict[int, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(translate_article, article, target_lang): idx
            for idx, article in indexed
            if needs_translation(article, target_lang)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.warning("Erro ao traduzir artigo #%s: %s", idx, exc)
                results[idx] = articles[idx]

    output: list[dict[str, Any]] = []
    for idx, article in indexed:
        output.append(results.get(idx, article))
    return output


def apply_locale_to_news_payload(payload: dict[str, Any], lang: str) -> dict[str, Any]:
    """Aplica tradução ao payload completo da landing page."""
    target = normalize_locale(lang)
    result = dict(payload)
    result["locale"] = target

    if result.get("featured"):
        result["featured"] = translate_article(result["featured"], target)

    if result.get("latest"):
        result["latest"] = _translate_many(result["latest"], target)

    categories = result.get("categories") or {}
    translated_categories: dict[str, list[dict[str, Any]]] = {}
    for key, items in categories.items():
        translated_categories[key] = _translate_many(items, target)
    result["categories"] = translated_categories

    return result
