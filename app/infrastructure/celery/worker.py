"""Celery application instance.

Единственная точка создания Celery-объекта в проекте.
Все задачи импортируются из app.infrastructure.celery.tasks.

Запуск воркера в dev (из docker-compose):
    celery -A app.infrastructure.celery.worker worker --loglevel=info

Конфигурация берётся из CelerySettings (.env: CELERY_BROKER_URL, CELERY_RESULT_BACKEND).
"""

from __future__ import annotations

import logging
import os

from celery import Celery
from celery import signals
from celery.schedules import crontab

from app.infrastructure.set_logging import configure_runtime_logging
from app.settings.config import settings

celery_app = Celery(
    "vekolom",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["app.infrastructure.celery.tasks"],
)

celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Зеркалирует acks_late=True из Django-задач
    task_acks_late=settings.celery.task_acks_late,

    # Повторные попытки подключения к брокеру при старте воркера
    broker_connection_retry_on_startup=settings.celery.broker_connection_retry_on_startup,

    # Часовой пояс (как в Django TIME_ZONE)
    timezone=settings.celery.timezone,
    enable_utc=True,

    # Worker настройки
    worker_prefetch_multiplier=1,  # честная очередь при acks_late
    task_routes={
        "app.infrastructure.celery.tasks.run_files_backup": {"queue": "backups"},
    },
)


def _normalize_celery_logger(logger: logging.Logger) -> None:
    """Ensure Celery loggers propagate to root handlers only once."""
    logger.handlers.clear()
    logger.propagate = True


@signals.setup_logging.connect
def _setup_celery_logging(**_: object) -> None:
    """Use project logging config and disable Celery's default handler setup."""
    configure_runtime_logging(
        service_name=os.getenv("SERVICE_NAME", "celery_vekolom"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_to_file=os.getenv("LOG_TO_FILE", "false"),
        log_file=os.getenv("LOG_FILE", "/vekolom/logs/celery_vekolom.log"),
    )


@signals.after_setup_logger.connect
def _after_setup_logger(logger: logging.Logger, **_: object) -> None:
    _normalize_celery_logger(logger)


@signals.after_setup_task_logger.connect
def _after_setup_task_logger(logger: logging.Logger, **_: object) -> None:
    _normalize_celery_logger(logger)


def _parse_backup_cron(value: str) -> crontab:
    parts = value.split()
    if len(parts) != 5:
        raise ValueError("BACKUP_SCHEDULE_CRON должен быть в формате: m h dom mon dow")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


def _build_backup_schedule() -> dict:
    backup = settings.backup
    if backup.SCHEDULE_CRON and backup.INTERVAL_MINUTES:
        raise ValueError("Заданы и BACKUP_SCHEDULE_CRON, и BACKUP_INTERVAL_MINUTES одновременно")

    if backup.SCHEDULE_CRON:
        return {
            "run-files-backup": {
                "task": "app.infrastructure.celery.tasks.run_files_backup",
                "schedule": _parse_backup_cron(backup.SCHEDULE_CRON),
                "options": {"queue": "backups"},
            }
        }

    if backup.INTERVAL_MINUTES:
        return {
            "run-files-backup": {
                "task": "app.infrastructure.celery.tasks.run_files_backup",
                "schedule": backup.INTERVAL_MINUTES * 60,
                "options": {"queue": "backups"},
            }
        }

    return {}


backup_schedule = _build_backup_schedule()
if backup_schedule:
    celery_app.conf.beat_schedule = {
        **celery_app.conf.get("beat_schedule", {}),
        **backup_schedule,
    }
