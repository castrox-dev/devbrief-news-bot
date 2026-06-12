"""Jobs reutilizáveis para execução local, Vercel Cron e testes."""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from services.alert_store import AlertStore
from services.breaking_detector import ScoredArticle, detect_breaking_candidates
from services.email_service import EmailService, EmailServiceError
from services.market_data import fetch_market_snapshot
from services.news_fetcher import (
    fetch_news_articles,
    format_articles_for_prompt,
    select_articles_for_ai,
)
from services.openai_service import OpenAIService, OpenAIServiceError
from services.summary_formatter import normalize_summary
from services.telegram_service import TelegramService, TelegramServiceError

logger = logging.getLogger("daily_news_bot")


def get_base_dir() -> Path:
    """Retorna o diretório base (compatível com PyInstaller e Vercel)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_prompt_path(filename: str = "news_prompt.txt") -> Path:
    """Retorna caminho de arquivo de prompt."""
    base = get_base_dir()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / filename
        if bundled.exists():
            return bundled
    return base / filename


def _parse_email_recipients(raw: str) -> list[str]:
    return [address.strip() for address in raw.split(",") if address.strip()]


def _is_email_enabled(config: dict[str, str]) -> bool:
    return bool(
        config.get("resend_api_key")
        and config.get("email_from")
        and config.get("email_to")
    )


def _build_openai_service(config: dict[str, str]) -> OpenAIService:
    return OpenAIService(
        api_key=config["ai_api_key"],
        base_url=config["ai_base_url"],
        model=config["ai_model"],
        temperature=float(config["ai_temperature"]),
        top_p=float(config["ai_top_p"]),
        max_tokens=int(config["ai_max_tokens"]),
        reasoning_budget=int(config["ai_reasoning_budget"]),
        use_stream=config["ai_stream"],
    )


def _build_telegram_service(config: dict[str, str]) -> TelegramService:
    return TelegramService(
        bot_token=config["telegram_bot_token"],
        chat_id=config["telegram_chat_id"],
    )


def run_daily_news_job(config: dict[str, str]) -> dict[str, object]:
    """
    Executa o briefing diário completo.

    Returns:
        Resumo com status da execução.
    """
    start_time = time.perf_counter()
    logger.info("=" * 60)
    logger.info("Início do briefing diário")
    logger.info("Data/hora: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        base_prompt = OpenAIService.load_prompt(get_prompt_path("news_prompt.txt"))
        today = datetime.now().strftime("%d/%m/%Y")

        logger.info("Coletando notícias de feeds RSS...")
        articles = fetch_news_articles()
        ai_articles = select_articles_for_ai(articles)
        logger.info(
            "%d artigos coletados (%d selecionados para a IA).",
            len(articles),
            len(ai_articles),
        )

        news_context = format_articles_for_prompt(ai_articles)
        market_context = fetch_market_snapshot()

        prompt_parts = [
            f"Data de referência: {today}. Considere notícias das últimas 24 horas.\n",
        ]
        if market_context:
            prompt_parts.append(market_context)
            prompt_parts.append("")
        prompt_parts.extend([news_context, "", base_prompt])
        prompt = "\n".join(prompt_parts)

        openai_service = _build_openai_service(config)
        telegram_service = _build_telegram_service(config)

        summary = normalize_summary(openai_service.generate_news_summary(prompt))
        telegram_service.send_message(
            summary,
            title="📰 DevBrief News — Resumo das Principais Notícias (Últimas 24h)",
        )

        email_sent = False
        if _is_email_enabled(config):
            email_service = EmailService(
                api_key=config["resend_api_key"],
                from_address=config["email_from"],
                to_addresses=_parse_email_recipients(config["email_to"]),
                logo_url=config.get("email_logo_url", ""),
            )
            email_service.send_news_summary(summary, reference_date=datetime.now())
            email_sent = True
            logger.info("E-mail enviado com sucesso.")
        else:
            logger.info("E-mail não configurado — pulando envio.")

        elapsed = time.perf_counter() - start_time
        logger.info("Briefing diário concluído em %.2f segundos.", elapsed)
        return {
            "ok": True,
            "job": "daily",
            "articles": len(articles),
            "email_sent": email_sent,
            "elapsed_seconds": round(elapsed, 2),
        }

    except (OpenAIServiceError, TelegramServiceError, EmailServiceError) as exc:
        elapsed = time.perf_counter() - start_time
        logger.error("Falha no briefing diário após %.2f segundos: %s", elapsed, exc)
        raise
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.exception("Erro inesperado no briefing diário após %.2f segundos: %s", elapsed, exc)
        raise
    finally:
        logger.info("=" * 60)


def _format_candidates_for_ai(candidates: list[ScoredArticle]) -> str:
    lines = ["=== CANDIDATOS A ALERTA ==="]
    for index, item in enumerate(candidates, 1):
        article = item.article
        summary = article.summary[:200] if article.summary else ""
        lines.append(
            f"{index}. [{article.title}]({article.url}) — {article.source} "
            f"(score={item.score}, categoria={article.category})"
        )
        if summary:
            lines.append(f"   Resumo: {summary}")
    return "\n".join(lines)


def run_breaking_news_job(config: dict[str, str]) -> dict[str, object]:
    """
    Verifica notícias recentes e dispara alertas de alto impacto.

    Returns:
        Resumo com status da execução.
    """
    start_time = time.perf_counter()
    logger.info("=" * 60)
    logger.info("Início da verificação de breaking news")
    logger.info("Data/hora: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        max_age_hours = int(config.get("breaking_max_age_hours", "3"))
        min_score = int(config.get("breaking_min_score", "5"))
        max_candidates = int(config.get("breaking_max_candidates", "5"))

        articles = fetch_news_articles(max_age_hours=max_age_hours)
        if not articles:
            logger.info("Nenhuma notícia recente encontrada.")
            return {"ok": True, "job": "breaking", "alerts_sent": 0, "reason": "no_articles"}

        store = AlertStore.from_env()
        fresh_articles = [
            article
            for article in articles
            if not store.was_sent(AlertStore.article_key(article.url, article.title))
        ]

        candidates = detect_breaking_candidates(
            fresh_articles,
            min_score=min_score,
            max_candidates=max_candidates,
        )

        if not candidates:
            logger.info("Nenhum candidato a breaking news (score >= %d).", min_score)
            return {
                "ok": True,
                "job": "breaking",
                "alerts_sent": 0,
                "reason": "no_candidates",
                "articles_checked": len(fresh_articles),
            }

        breaking_prompt = OpenAIService.load_prompt(get_prompt_path("breaking_prompt.txt"))
        market_context = fetch_market_snapshot()
        prompt_parts = []
        if market_context:
            prompt_parts.extend([market_context, ""])
        prompt_parts.extend([
            _format_candidates_for_ai(candidates),
            "",
            breaking_prompt,
        ])
        prompt = "\n".join(prompt_parts)

        openai_service = OpenAIService(
            api_key=config["ai_api_key"],
            base_url=config["ai_base_url"],
            model=config["ai_model"],
            temperature=0.1,
            top_p=float(config["ai_top_p"]),
            max_tokens=min(1024, int(config["ai_max_tokens"])),
            reasoning_budget=int(config["ai_reasoning_budget"]),
            use_stream=False,
        )

        alert_text = openai_service.generate_news_summary(prompt).strip()
        if not alert_text or "NENHUM_ALERTA" in alert_text.upper():
            logger.info("IA não confirmou alertas de breaking news.")
            return {
                "ok": True,
                "job": "breaking",
                "alerts_sent": 0,
                "reason": "ai_declined",
                "candidates": len(candidates),
            }

        alert_text = normalize_summary(alert_text)
        telegram_service = _build_telegram_service(config)
        telegram_service.send_message(
            alert_text,
            title="🚨 DevBrief News — Alerta Urgente",
        )

        if _is_email_enabled(config):
            email_service = EmailService(
                api_key=config["resend_api_key"],
                from_address=config["email_from"],
                to_addresses=_parse_email_recipients(config["email_to"]),
                logo_url=config.get("email_logo_url", ""),
            )
            email_service.send_news_summary(
                alert_text,
                reference_date=datetime.now(),
                subject_prefix="🚨 Alerta Urgente",
            )

        for item in candidates:
            store.mark_sent(AlertStore.article_key(item.article.url, item.article.title))

        elapsed = time.perf_counter() - start_time
        logger.info("Breaking news enviado em %.2f segundos.", elapsed)
        return {
            "ok": True,
            "job": "breaking",
            "alerts_sent": 1,
            "candidates": len(candidates),
            "elapsed_seconds": round(elapsed, 2),
        }

    except (OpenAIServiceError, TelegramServiceError, EmailServiceError) as exc:
        elapsed = time.perf_counter() - start_time
        logger.error("Falha em breaking news após %.2f segundos: %s", elapsed, exc)
        raise
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.exception("Erro inesperado em breaking news após %.2f segundos: %s", elapsed, exc)
        raise
    finally:
        logger.info("=" * 60)


def load_config_from_env() -> dict[str, str]:
    """Carrega configuração a partir de variáveis de ambiente."""
    return {
        "ai_api_key": os.getenv("AI_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip(),
        "ai_base_url": os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1").strip(),
        "ai_model": os.getenv("AI_MODEL", "meta/llama-3.3-70b-instruct").strip(),
        "ai_temperature": os.getenv("AI_TEMPERATURE", "0.2").strip(),
        "ai_top_p": os.getenv("AI_TOP_P", "0.7").strip(),
        "ai_max_tokens": os.getenv("AI_MAX_TOKENS", "6144").strip(),
        "ai_reasoning_budget": os.getenv("AI_REASONING_BUDGET", "4096").strip(),
        "ai_stream": os.getenv("AI_STREAM", "false").strip().lower() in ("1", "true", "yes"),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        "resend_api_key": os.getenv("RESEND_API_KEY", "").strip(),
        "email_from": os.getenv("EMAIL_FROM", "").strip(),
        "email_to": os.getenv("EMAIL_TO", "").strip(),
        "email_logo_url": os.getenv("EMAIL_LOGO_URL", "").strip(),
        "timezone": os.getenv("TIMEZONE", "America/Sao_Paulo").strip(),
        "schedule_time": os.getenv("SCHEDULE_TIME", "07:00").strip(),
        "breaking_max_age_hours": os.getenv("BREAKING_MAX_AGE_HOURS", "3").strip(),
        "breaking_min_score": os.getenv("BREAKING_MIN_SCORE", "5").strip(),
        "breaking_max_candidates": os.getenv("BREAKING_MAX_CANDIDATES", "5").strip(),
        "cron_secret": os.getenv("CRON_SECRET", "").strip(),
    }
