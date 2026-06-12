"""Configuração do agendamento diário com APScheduler."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE: Final[str] = "America/Sao_Paulo"
DEFAULT_HOUR: Final[int] = 7
DEFAULT_MINUTE: Final[int] = 0


def parse_schedule_time(schedule_time: str) -> tuple[int, int]:
    """
    Converte horário no formato HH:MM em hora e minuto.

    Args:
        schedule_time: Horário no formato HH:MM.

    Returns:
        Tupla (hora, minuto).

    Raises:
        ValueError: Se o formato for inválido.
    """
    parts = schedule_time.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Formato de horário inválido: {schedule_time}. Use HH:MM.")

    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Horário fora do intervalo válido: {schedule_time}")

    return hour, minute


def create_scheduler(
    job: Callable[[], None],
    timezone: str = DEFAULT_TIMEZONE,
    schedule_time: str = "07:00",
) -> BlockingScheduler:
    """
    Cria e configura o scheduler com execução diária.

    Args:
        job: Função a ser executada no horário agendado.
        timezone: Fuso horário IANA (ex.: America/Sao_Paulo).
        schedule_time: Horário diário no formato HH:MM.

    Returns:
        Instância configurada de BlockingScheduler.
    """
    hour, minute = parse_schedule_time(schedule_time)

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="daily_news_job",
        name="Daily News Bot",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    logger.info(
        "Agendamento configurado: todos os dias às %02d:%02d (%s).",
        hour,
        minute,
        timezone,
    )

    return scheduler


def start_scheduler(scheduler: BlockingScheduler) -> None:
    """
    Inicia o scheduler bloqueante.

    Args:
        scheduler: Instância do BlockingScheduler.
    """
    logger.info("Scheduler iniciado. Aguardando próxima execução...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler encerrado pelo usuário.")
        scheduler.shutdown(wait=False)
