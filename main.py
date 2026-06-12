"""Ponto de entrada do Daily News Bot."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from scheduler.scheduler import create_scheduler, start_scheduler
from services.email_renderer import render_email_html
from services.jobs import get_base_dir, run_daily_news_job, run_sync_news_job
from services.summary_formatter import normalize_summary

LOG_DIR = get_base_dir() / "logs"
LOG_FILE = LOG_DIR / "bot.log"


def setup_logging() -> None:
    """Configura logging em arquivo e console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def load_config() -> dict[str, str]:
    """
    Carrega variáveis de ambiente necessárias.

    Returns:
        Dicionário com configurações validadas.

    Raises:
        SystemExit: Se variáveis obrigatórias estiverem ausentes.
    """
    load_dotenv(get_base_dir() / ".env")

    config = {
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
        "sync_max_age_hours": os.getenv("SYNC_MAX_AGE_HOURS", "24").strip(),
        "database_url": os.getenv("DATABASE_URL", "").strip(),
        "cron_secret": os.getenv("CRON_SECRET", "").strip(),
    }

    missing = [
        key
        for key, value in {
            "AI_API_KEY": config["ai_api_key"],
            "TELEGRAM_BOT_TOKEN": config["telegram_bot_token"],
            "TELEGRAM_CHAT_ID": config["telegram_chat_id"],
        }.items()
        if not value
    ]

    if missing:
        logging.error("Variáveis de ambiente ausentes: %s", ", ".join(missing))
        logging.error("Copie .env.example para .env e preencha os valores.")
        raise SystemExit(1)

    return config


def parse_args() -> argparse.Namespace:
    """Define e processa argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Daily News Bot — resumo diário via NVIDIA NIM + Telegram + E-mail.",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Executa o briefing diário imediatamente e encerra.",
    )
    parser.add_argument(
        "--sync-now",
        action="store_true",
        help="Sincroniza notícias RSS → PostgreSQL imediatamente (atualiza o site).",
    )
    parser.add_argument(
        "--breaking-now",
        action="store_true",
        help="[Legado] Executa verificação de breaking news imediatamente.",
    )
    parser.add_argument(
        "--preview-email",
        action="store_true",
        help="Gera preview HTML do e-mail em logs/email_preview.html (sem enviar).",
    )
    return parser.parse_args()


def generate_email_preview() -> Path:
    """Gera arquivo HTML de preview do template de e-mail."""
    sample_summary = """📰 DevBrief News — Resumo das Principais Notícias (Últimas 24h)

1. Resumo Executivo

O tema dominante continua sendo a corrida global pela Inteligência Artificial...

5. Mercado e Investimentos

📈 Cenário do dia
Dólar em R$ 5,42 (+0,3%). Bitcoin em R$ 520 mil. Ibovespa abre em alta de 0,8%...

10. 💬 Bordão do Dia

"Quem dominar a infraestrutura de IA hoje, domina o mercado de amanhã." """

    html_content = render_email_html(normalize_summary(sample_summary), for_preview=True)
    preview_path = LOG_DIR / "email_preview.html"
    preview_path.write_text(html_content, encoding="utf-8")
    return preview_path


def main() -> None:
    """Inicializa logging, carrega configuração e inicia o bot."""
    setup_logging()
    logger = logging.getLogger("daily_news_bot")
    args = parse_args()

    try:
        config = load_config()
    except SystemExit:
        raise

    if args.preview_email:
        preview_path = generate_email_preview()
        logger.info("Preview do e-mail salvo em: %s", preview_path)
        return

    if args.run_now:
        logger.info("Modo --run-now: executando briefing diário.")
        run_daily_news_job(config)
        return

    if args.sync_now:
        logger.info("Modo --sync-now: sincronizando notícias para o banco.")
        run_sync_news_job(config)
        return

    if args.breaking_now:
        from services.jobs import run_breaking_news_job

        logger.info("Modo --breaking-now: verificando breaking news.")
        run_breaking_news_job(config)
        return

    def scheduled_daily_job() -> None:
        try:
            run_daily_news_job(config)
        except Exception:
            logger.error("Briefing diário falhou. Próxima tentativa no horário configurado.")

    def scheduled_sync_job() -> None:
        try:
            run_sync_news_job(config)
        except Exception:
            logger.error("Sync de notícias falhou. Próxima tentativa em 5 min.")

    daily_scheduler = create_scheduler(
        job=scheduled_daily_job,
        timezone=config["timezone"],
        schedule_time=config["schedule_time"],
    )
    daily_scheduler.add_job(
        scheduled_sync_job,
        trigger=CronTrigger(
            minute="*/5",
            timezone=config["timezone"],
        ),
        id="news_sync_job",
        name="News Sync (site)",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Sync do site: a cada 5 minutos. Telegram/e-mail: só às %s.", config["schedule_time"])

    logger.info("Executando busca inicial de notícias ao iniciar...")
    try:
        run_sync_news_job(config)
    except Exception:
        logger.error("Sync inicial falhou — próxima tentativa em 5 min.")

    start_scheduler(daily_scheduler)


if __name__ == "__main__":
    main()
