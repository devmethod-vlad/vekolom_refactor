"""Нотификатор обновлений контента через Redis Pub/Sub.

Зачем это нужно
---------------
Когда администратор изменяет данные в админке (starlette-admin),
PWA-клиенты должны максимально быстро получить актуальную версию страницы.

Механизм работает так:
  1. Админ сохраняет запись → вызывается ``ContentNotifier.publish()``.
  2. Сообщение публикуется в Redis-канал ``vekolom:content_updated``.
  3. SSE-endpoint (``/api/pwa/events``) подписан на этот канал
     и мгновенно пересылает событие всем подключённым клиентам.
  4. JS на странице клиента получает событие и даёт команду
     Service Worker-у сбросить кеш HTML-страниц.
  5. При следующем запросе SW загружает свежую страницу с сервера.

Redis уже используется в проекте как брокер Celery,
поэтому дополнительная инфраструктура не требуется.

Использование
-------------
Публикация (из admin-хука или Celery-задачи)::

    notifier = ContentNotifier(redis_url="redis://redis-vekolom:6379/0")
    await notifier.publish("home", "update")

Подписка (в SSE-endpoint)::

    async for event in notifier.subscribe():
        yield event  # → SSE-клиенту
"""

from __future__ import annotations

import json
import logging
import time
import typing as tp

from redis import asyncio as aioredis

logger = logging.getLogger(__name__)

# Канал Redis для уведомлений об обновлении контента.
# Все модули публикуют в один канал — фильтрация по module/action
# происходит на стороне клиента (или в subscribe-генераторе).
CONTENT_CHANNEL = "vekolom:content_updated"


class ContentNotifier:
    """Обёртка над Redis Pub/Sub для уведомлений об изменении контента.

    Attributes:
        redis_url: URL подключения к Redis (совпадает с Celery broker_url).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """Ленивое создание Redis-клиента (переиспользуется между вызовами)."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def publish(self, module: str, action: str = "update") -> None:
        """Опубликовать событие обновления контента.

        Args:
            module: Имя модуля, данные которого изменились
                    (например: ``"home"``, ``"pricelist"``, ``"contacts"``).
            action: Тип действия (``"create"``, ``"update"``, ``"delete"``).
        """
        redis = await self._get_redis()
        payload = json.dumps(
            {
                "module": module,
                "action": action,
                "timestamp": time.time(),
            },
            ensure_ascii=False,
        )
        await redis.publish(CONTENT_CHANNEL, payload)
        logger.info("PWA content_updated published: module=%s action=%s", module, action)

    async def subscribe(self) -> tp.AsyncIterator[dict]:
        """Асинхронный генератор событий из Redis-канала.

        Yields:
            dict: Распарсенный JSON-объект вида
                  ``{"module": "home", "action": "update", "timestamp": 1234567890.0}``.

        Note:
            Генератор работает бесконечно (пока не будет отменён/прерван).
            Используется в SSE-endpoint — каждый подключённый клиент
            получает свой экземпляр подписки.
        """
        redis = await self._get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(CONTENT_CHANNEL)
        logger.info("PWA SSE subscriber connected to channel: %s", CONTENT_CHANNEL)
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "PWA: invalid message in channel %s: %s",
                            CONTENT_CHANNEL,
                            message["data"],
                        )
        finally:
            await pubsub.unsubscribe(CONTENT_CHANNEL)
            await pubsub.close()
            logger.info("PWA SSE subscriber disconnected from channel: %s", CONTENT_CHANNEL)

    async def close(self) -> None:
        """Закрыть Redis-соединение (вызывается при shutdown приложения)."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
