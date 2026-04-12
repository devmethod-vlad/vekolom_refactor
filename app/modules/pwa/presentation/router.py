"""HTTP-роутинг PWA-модуля.

Эндпоинты
----------
GET  /api/pwa/events
    SSE (Server-Sent Events) — стрим обновлений контента в реальном времени.
    Клиентский JS (``pwa-register.js``) подключается к этому endpoint'у
    через ``EventSource`` и получает события при любом изменении данных
    в админке. Используется для мгновенной инвалидации кеша Service Worker.

POST /api/pwa/notify
    Триггер уведомления — вызывается из admin-хуков (starlette-admin)
    при сохранении/удалении записи. Публикует событие в Redis-канал,
    откуда его получают все SSE-подписчики.

GET  /api/pwa/version
    Возвращает текущую версию контента (timestamp последнего изменения).
    Используется Service Worker-ом для быстрой проверки актуальности кеша
    без установки SSE-соединения (fallback для случаев, когда SSE недоступен).

Почему эндпоинты на ``/api/pwa/*``
-----------------------------------
Маршруты ``/admin/*`` перехватываются starlette-admin sub-app.
Размещение на ``/api/pwa/*`` следует паттерну проекта (аналогично
``/api/admin/*`` для TinyMCE upload — см. ``mount_admin_support_routes``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.pwa.infrastructure.notifier import ContentNotifier
from app.settings.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pwa", tags=["pwa"])

# ---------------------------------------------------------------------------
# Singleton-нотификатор: один экземпляр на процесс.
# Инициализируется лениво при первом обращении.
# В идеале стоит вынести в Dishka-провайдер (Scope.APP),
# но для минимальной интеграции — singleton на уровне модуля.
# ---------------------------------------------------------------------------
_notifier: ContentNotifier | None = None


def _get_notifier() -> ContentNotifier:
    """Ленивый singleton ContentNotifier."""
    global _notifier
    if _notifier is None:
        _notifier = ContentNotifier(redis_url=settings.celery.broker_url)
    return _notifier


# ---------------------------------------------------------------------------
# SSE endpoint — стрим событий обновления контента
# ---------------------------------------------------------------------------


@router.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """SSE-стрим обновлений контента.

    Клиент подключается через ``new EventSource('/api/pwa/events')``
    и получает события вида::

        event: content_updated
        data: {"module": "home", "action": "update", "timestamp": 1234567890.0}

    При разрыве соединения клиент автоматически переподключается
    (стандартное поведение ``EventSource``).

    Heartbeat (комментарий ``: heartbeat``) отправляется каждые 30 секунд,
    чтобы соединение не разрывалось прокси/балансировщиками.
    """

    async def event_stream():
        """Асинхронный генератор SSE-событий."""
        notifier = _get_notifier()

        # Параллельно слушаем Redis и отправляем heartbeat.
        # asyncio.Queue используется как буфер между подпиской и генератором.
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def redis_listener():
            """Слушает Redis pub/sub и кладёт форматированные SSE-события в очередь."""
            try:
                async for event_data in notifier.subscribe():
                    sse_line = (
                        f"event: content_updated\n"
                        f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    )
                    await queue.put(sse_line)
            except asyncio.CancelledError:
                pass
            finally:
                await queue.put(None)  # Сигнал завершения

        async def heartbeat():
            """Периодический heartbeat, чтобы прокси не закрывал соединение."""
            try:
                while True:
                    await asyncio.sleep(30)
                    await queue.put(": heartbeat\n\n")
            except asyncio.CancelledError:
                pass

        listener_task = asyncio.create_task(redis_listener())
        heartbeat_task = asyncio.create_task(heartbeat())

        try:
            while True:
                # Проверяем, не отключился ли клиент
                if await request.is_disconnected():
                    break

                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if item is None:
                    break
                yield item
        finally:
            listener_task.cancel()
            heartbeat_task.cancel()
            # Ожидаем завершения задач, подавляя CancelledError
            for task in (listener_task, heartbeat_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # Отключаем буферизацию на прокси (Nginx, CloudFlare и т.д.)
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "none",
        },
    )


# ---------------------------------------------------------------------------
# Notify endpoint — триггер из админки
# ---------------------------------------------------------------------------


@router.post("/notify")
async def notify_content_update(request: Request) -> JSONResponse:
    """Публикует событие обновления контента в Redis.

    Ожидает JSON-тело::

        {"module": "home", "action": "update"}

    Вызывается из admin-хуков (``after_model_change`` / ``after_delete``
    в starlette-admin ModelView) или из Celery-задач после обработки
    изображений.

    Аутентификация: endpoint доступен только из внутренней сети
    (admin-панель работает в том же контейнере). При необходимости
    можно добавить проверку сессии/токена.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    module = body.get("module", "unknown")
    action = body.get("action", "update")

    notifier = _get_notifier()
    await notifier.publish(module=module, action=action)

    return JSONResponse({"status": "ok", "module": module, "action": action})


# ---------------------------------------------------------------------------
# Version endpoint — fallback для проверки актуальности кеша
# ---------------------------------------------------------------------------

# Глобальная метка последнего обновления (обновляется при каждом notify).
_last_update_ts: float = time.time()


@router.get("/version")
async def content_version() -> JSONResponse:
    """Возвращает timestamp последнего обновления контента.

    Service Worker использует этот endpoint как fallback:
    периодически (раз в минуту) проверяет версию и сбрасывает
    кеш страниц, если версия изменилась.

    Это дополнение к SSE — на случай, если SSE-соединение
    было потеряно и ещё не восстановлено.
    """
    return JSONResponse(
        {"version": _last_update_ts},
        headers={"Cache-Control": "no-cache, no-store"},
    )


# ---------------------------------------------------------------------------
# Утилита для вызова из admin-хуков (синхронный контекст)
# ---------------------------------------------------------------------------


async def publish_content_update(module: str, action: str = "update") -> None:
    """Вспомогательная функция для вызова из admin-хуков.

    Обновляет глобальный timestamp и публикует событие в Redis.

    Пример использования в admin view::

        from app.modules.pwa.presentation.router import publish_content_update

        class MyModelView(BaseAdminView):
            async def after_model_change(self, data, model, is_created, request):
                await publish_content_update("home", "create" if is_created else "update")

            async def after_delete(self, model, request):
                await publish_content_update("home", "delete")
    """
    global _last_update_ts
    _last_update_ts = time.time()

    notifier = _get_notifier()
    await notifier.publish(module=module, action=action)
