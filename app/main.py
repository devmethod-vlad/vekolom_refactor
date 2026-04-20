"""FastAPI application factory for the Vekolom project.

Статика и медиа в dev vs prod
------------------------------
В DEBUG-режиме FastAPI сам отдаёт и статику, и медиа через StaticFiles —
удобно для локальной разработки без Nginx.

В prod оба маунта убираются: Nginx отдаёт файлы напрямую с диска,
минуя Python-процесс полностью. Пример конфига Nginx:

    location /static/ { alias /vekolom/static/; expires 30d; add_header Cache-Control "public"; }
    location /media/  { alias /vekolom/media/;  expires 30d; add_header Cache-Control "public"; }
    location /        { proxy_pass http://fastapi:8000; }

Зачем убирать StaticFiles в prod?
  - StaticFiles использует синхронный I/O через threadpool — это медленнее Nginx.
  - Nginx умеет sendfile(), кешировать, ставить правильные Cache-Control/ETag.
  - Запросы на /static/ и /media/ вообще не доходят до Python — меньше нагрузка.
  - Аналогичная логика была в Django: DEBUG=True включал static/media через urlpatterns,
    в prod Django вообще не участвовал в отдаче файлов.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from app.admin.setup import build_admin, mount_admin_support_routes
from app.infrastructure.db.bootstrap import bootstrap_database
from app.infrastructure.set_logging import setup_logging
from app.infrastructure.web.bundler import build_assets
from app.infrastructure.web.csrf import CSRFMiddleware
from app.ioc.container import build_container
from app.modules.home.presentation.router import router as home_router
from app.modules.pricelist.presentation.router import router as pricelist_router
from app.modules.contacts.presentation.router import router as contacts_router
from app.modules.amp.presentation.router import router as amp_router
from app.modules.pwa.presentation.router import router as pwa_router
from app.modules.seo.presentation.router import router as seo_router
from app.settings.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""

    # 1) Ensure target DB exists and schema is up-to-date.
    await asyncio.to_thread(bootstrap_database, settings.database)

    # 2) В prod-режиме собираем production-бандлы legacy JS и custom CSS.
    #    Сборка выполняется в отдельном потоке, чтобы не блокировать event loop.
    #    Флаги BUNDLE_LEGACY_JS и BUNDLE_CUSTOM_CSS контролируют, какие бандлы
    #    собирать. В dev-режиме build_assets() ничего не делает.
    await asyncio.to_thread(build_assets, settings)

    yield

    # 3) Dispose resources (DB engines, etc.) managed by Dishka.
    await app.state.dishka_container.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(debug=settings.app.DEBUG)
    app = FastAPI(lifespan=lifespan, debug=settings.app.DEBUG)

    # --- Security: TrustedHostMiddleware ---
    # Отклоняет запросы с подменённым Host-заголовком (Host header injection).
    # Без этого middleware атакующий может подставить свой домен в Host,
    # и request.url_for() / canonical URL будут генерировать ссылки
    # на вредоносный домен. Также защищает от cache poisoning.
    #
    # В dev разрешаем localhost и 127.0.0.1 для удобства разработки.
    # В prod — только production-домен.
    allowed_hosts = ["vekolom.com", "www.vekolom.com"]
    if settings.app.DEBUG:
        allowed_hosts += ["localhost", "127.0.0.1", "testserver"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # --- Security: CSRF Protection ---
    # Double Submit Cookie паттерн для защиты форм от CSRF-атак.
    # Проверяет POST/PUT/PATCH/DELETE запросы (кроме /admin/ и /api/).
    # Admin-панель защищена отдельно через SameSite=Lax session cookie.
    # Подробнее: app/infrastructure/web/csrf.py
    app.add_middleware(
        CSRFMiddleware,
        secret_key=settings.app.SECRET_KEY,
        secure=not settings.app.DEBUG,
    )

    # Initialise dependency injection container.
    container = build_container()
    setup_dishka(container=container, app=app)

    if settings.app.DEBUG:
        # В dev FastAPI отдаёт статику и медиа сам.
        # В prod оба location обслуживает Nginx — маунты здесь не нужны.
        app.mount(
            settings.static.mount_path,
            StaticFiles(directory=settings.static.STATIC_ROOT),
            name="static",
        )
        app.mount(
            settings.media.mount_path,
            StaticFiles(directory=settings.media.MEDIA_ROOT),
            name="media",
        )

    # Routers.
    app.include_router(home_router)
    app.include_router(pricelist_router)
    app.include_router(contacts_router)

    # AMP: Accelerated Mobile Pages — облегчённые версии публичных страниц.
    # Маршруты: /amp/, /amp/pricelist/, /amp/contacts/, /amp/contacts/submit/
    app.include_router(amp_router)

    # PWA: SSE-стрим обновлений, notify endpoint, version endpoint.
    app.include_router(pwa_router)

    # SEO: robots.txt и sitemap.xml — доступны с корня сайта.
    app.include_router(seo_router)

    # PWA: Service Worker должен отдаваться с корневого пути (/sw.js),
    # чтобы его scope охватывал весь сайт. Файл лежит в static/pwa/sw.js,
    # но браузер ограничивает scope SW путём, откуда он загружен.
    # Поэтому проксируем через route на /.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        """Минимальный health endpoint для container healthcheck'ов."""
        return {"status": "ok"}

    @app.get("/sw.js", include_in_schema=False)
    async def service_worker():
        """Отдаёт Service Worker с корневого пути для максимального scope."""
        return FileResponse(
            f"{settings.static.STATIC_ROOT}/pwa/sw.js",
            media_type="application/javascript",
            headers={
                # SW не должен кешироваться браузером надолго —
                # иначе обновления SW будут приходить с задержкой.
                "Cache-Control": "no-cache, no-store, must-revalidate",
                # Service-Worker-Allowed расширяет допустимый scope
                # (на случай, если путь файла не совпадает со scope).
                "Service-Worker-Allowed": "/",
            },
        )

    # PWA: Offline-страница, кешируется SW при установке.
    from fastapi.templating import Jinja2Templates as _Templates

    @app.get("/offline/", include_in_schema=False)
    async def offline_page(request: Request):
        """Offline-страница для PWA (показывается SW при отсутствии сети)."""
        _tpl = _Templates(directory="app/templates")
        return _tpl.TemplateResponse("pwa/offline.html", {"request": request})

    # Служебные admin-route'ы (TinyMCE upload, custom JS, self-hosted assets).
    # Монтируем их ДО admin sub-app, чтобы /api/admin/* не перехватывался /admin mount.
    mount_admin_support_routes(app, settings)

    # Admin interface.
    admin = build_admin(settings)
    admin.mount_to(app)

    return app


app = create_app()
