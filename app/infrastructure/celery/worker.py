"""Celery application instance.

Единственная точка создания Celery-объекта в проекте.
Все задачи импортируются из app.infrastructure.celery.tasks.

Запуск воркера в dev (из docker-compose):
    celery -A app.infrastructure.celery.worker worker --loglevel=info

Конфигурация берётся из CelerySettings (.env: CELERY_BROKER_URL, CELERY_RESULT_BACKEND).
"""

from celery import Celery

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
)
