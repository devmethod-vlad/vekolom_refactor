"""Сборка и конфигурация экземпляра Starlette-Admin.

Этот модуль:
  - создаёт Admin с авторизацией, i18n и middleware;
  - регистрирует ModelView-классы из модулей home / pricelist / contacts;
  - монтирует API-эндпоинты для загрузки изображений из TinyMCE;
  - раздаёт кастомный JS для sidebar/dropdown/иконок/preview;
  - публикует self-hosted TinyMCE-ассеты из локальной папки проекта.

Важно: служебные API-эндпоинты админки монтируются вне `/admin`
(на `/api/admin/*`), потому что admin sub-app (mount на `/admin`)
иначе перехватывает все запросы к `/admin/*`.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from PIL import Image
from sqlalchemy import create_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette_admin import DropDown
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin
from starlette_admin.exceptions import LoginFailed
from starlette_admin.i18n import I18nConfig

from app.admin.views.apikeys import (
    SmartCaptchaKeyView,
    YandexMapsApiKeyView,
)
from app.admin.views.contacts import (
    ContactsSeoView,
    ContactsView,
    MessagesView,
)
from app.admin.views.home import (
    ActionView,
    CoreSeoView,
    MainCarouselView,
    MainTextView,
    PriemView,
    SloganView,
)
from app.admin.views.pricelist import (
    CategoryView,
    FotoView,
    PositionView,
    PriceDateView,
    PricelistSeoView,
)
from app.modules.apikeys.infrastructure.sa_models import (
    SmartCaptchaKeyModel,
    YandexMapsApiKeyModel,
)
from app.modules.contacts.infrastructure.sa_models import (
    Contacts,
    ContactsSeo,
    MessMessages,
)
from app.modules.home.infrastructure.sa_models import (
    Action,
    CoreSeo,
    MainCarousel,
    MainText,
    Priem,
    Slogan,
)
from app.modules.pricelist.infrastructure.sa_models import (
    Category,
    Foto,
    Position,
    PriceDate,
    PricelistSeo,
)
from app.settings.config import Settings

logger = logging.getLogger("app.admin.setup")

# Карта `identity -> icon` для внутренних пунктов dropdown-меню.
# Наполняется в build_admin() и используется в _admin_custom_js().
ADMIN_SUBMENU_ICON_MAP: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginThrottle:
    """Ограничивает количество неудачных попыток входа по IP.

    Защита от brute-force атак на форму логина.
    Хранит историю неудачных попыток в памяти процесса.
    При перезапуске приложения счётчики сбрасываются — это приемлемо,
    т.к. цель — затруднить онлайн-перебор, а не хранить историю навечно.

    Параметры:
        max_attempts    — максимум неудачных попыток в окне.
        window_seconds  — длительность окна в секундах (по умолчанию 5 минут).
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, ip: str) -> None:
        """Удаляет записи старше window_seconds."""
        cutoff = time.monotonic() - self.window
        self._attempts[ip] = [t for t in self._attempts[ip] if t > cutoff]
        # Удаляем ключ, если пуст — не даём dict расти бесконечно
        if not self._attempts[ip]:
            self._attempts.pop(ip, None)

    def is_blocked(self, ip: str) -> bool:
        """Проверяет, заблокирован ли IP из-за превышения лимита попыток."""
        self._cleanup(ip)
        return len(self._attempts.get(ip, [])) >= self.max_attempts

    def record_failure(self, ip: str) -> None:
        """Фиксирует неудачную попытку входа."""
        self._attempts[ip].append(time.monotonic())

    def reset(self, ip: str) -> None:
        """Сбрасывает счётчик при успешном входе."""
        self._attempts.pop(ip, None)


# Глобальный экземпляр throttle — один на весь процесс.
# 5 неудачных попыток за 5 минут → блокировка IP на оставшееся время окна.
_login_throttle = LoginThrottle(max_attempts=5, window_seconds=300)


class SimpleAdminAuthProvider(AuthProvider):
    """Аутентификация по username/password с защитой от timing attack и brute-force.

    Безопасность:
      - Пароль хранится как SHA-256 хеш (не plaintext в памяти).
      - Сравнение через secrets.compare_digest (constant-time, защита от timing attack).
      - LoginThrottle блокирует IP после 5 неудачных попыток за 5 минут.
      - Сессия содержит timestamp входа для автоматического logout (SESSION_MAX_AGE).
      - Все попытки входа (успешные и неудачные) логируются с IP-адресом.
    """

    # Время жизни admin-сессии (секунды). После этого is_authenticated вернёт False.
    SESSION_MAX_AGE: int = 7200  # 2 часа

    def __init__(
        self,
        username: str,
        password: str,
        login_path: str = "/login",
        logout_path: str = "/logout",
    ) -> None:
        super().__init__(login_path=login_path, logout_path=logout_path)
        self._username = username
        # Храним хеш пароля — plaintext не остаётся в памяти процесса.
        self._password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _verify_credentials(self, username: str, password: str) -> bool:
        """Проверяет учётные данные через constant-time сравнение.

        secrets.compare_digest сравнивает строки за фиксированное время,
        независимо от позиции первого различия. Это исключает timing attack,
        при котором атакующий измеряет время ответа и побуквенно подбирает пароль.
        """
        input_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        username_ok = secrets.compare_digest(username, self._username)
        password_ok = secrets.compare_digest(input_hash, self._password_hash)
        # Оба сравнения выполняются ВСЕГДА (short-circuit не используется),
        # чтобы время ответа не зависело от того, что именно неверно.
        return username_ok and password_ok

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Извлекает IP клиента из запроса.

        X-Real-IP устанавливается nginx (snippets/proxy_params.conf).
        Если nginx нет (dev-режим) — используем request.client.host.
        """
        return (
            request.headers.get("x-real-ip")
            or (request.client.host if request.client else "unknown")
        )

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        ip = self._get_client_ip(request)

        # --- Brute-force protection ---
        if _login_throttle.is_blocked(ip):
            logger.warning(
                "Admin login BLOCKED (rate limit): user=%s ip=%s", username, ip,
            )
            raise LoginFailed(
                "Слишком много неудачных попыток. Подождите 5 минут."
            )

        # --- Constant-time credential verification ---
        if self._verify_credentials(username, password):
            _login_throttle.reset(ip)
            request.session["admin_user"] = {
                "username": username,
                "login_at": time.time(),
            }
            logger.info("Admin login OK: user=%s ip=%s", username, ip)
            return response

        # --- Failed attempt ---
        _login_throttle.record_failure(ip)
        logger.warning("Admin login FAILED: user=%s ip=%s", username, ip)
        raise LoginFailed("Неверное имя пользователя или пароль")

    async def is_authenticated(self, request: Request) -> bool:
        user = request.session.get("admin_user")
        if not user:
            return False

        # --- Session expiry ---
        # Автоматический logout после SESSION_MAX_AGE секунд бездействия.
        login_at = user.get("login_at", 0)
        if time.time() - login_at > self.SESSION_MAX_AGE:
            request.session.clear()
            return False

        return True

    def get_admin_user(self, request: Request) -> AdminUser | None:
        data = request.session.get("admin_user") or {}
        username = data.get("username")
        if not username:
            return None
        return AdminUser(username=username)

    async def logout(self, request: Request, response: Response) -> Response:
        ip = self._get_client_ip(request)
        user = request.session.get("admin_user", {})
        logger.info(
            "Admin logout: user=%s ip=%s", user.get("username", "?"), ip,
        )
        request.session.clear()
        return response


# ---------------------------------------------------------------------------
# Admin API auth guard
# ---------------------------------------------------------------------------


def _check_admin_session(request: Request) -> bool:
    """Проверяет наличие валидной admin-сессии в запросе.

    Используется для защиты API-эндпоинтов админки (/api/admin/*),
    которые монтируются вне starlette-admin sub-app и потому
    НЕ проходят через AuthProvider автоматически.

    Без этой проверки /api/admin/tinymce-upload доступен ЛЮБОМУ —
    это критическая уязвимость, позволяющая загрузить файл на сервер.
    """
    admin_user = request.session.get("admin_user")
    if not admin_user:
        return False
    # Проверяем expiry (аналогично SimpleAdminAuthProvider.is_authenticated)
    login_at = admin_user.get("login_at", 0)
    if time.time() - login_at > SimpleAdminAuthProvider.SESSION_MAX_AGE:
        return False
    return True


# ---------------------------------------------------------------------------
# TinyMCE image upload endpoint
# ---------------------------------------------------------------------------


async def _tinymce_upload(request: Request) -> JSONResponse:
    """Эндпоинт для загрузки изображений из TinyMCE-редактора.

    TinyMCE отправляет файл в поле ``file`` через multipart/form-data.
    В ответ ждёт JSON вида: ``{"location": "/media/media/uploads/file.jpg"}``.

    Это функциональный аналог Django CKEditor upload-endpoint.

    БЕЗОПАСНОСТЬ: endpoint защищён проверкой admin-сессии.
    Без валидной сессии возвращает 403 Forbidden.
    """
    # --- Auth guard: только авторизованные admin-пользователи ---
    if not _check_admin_session(request):
        return JSONResponse(
            {"error": "Требуется авторизация в админ-панели."},
            status_code=403,
        )
    from app.admin.utils.photo_upload import PhotoUploadError, _validate_upload
    from app.infrastructure.media.storage import ensure_dir
    from app.settings.config import settings

    form = await request.form()
    upload = form.get("file")

    if upload is None or not hasattr(upload, "read"):
        return JSONResponse(
            {"error": "Файл не найден в запросе."},
            status_code=400,
        )

    filename = getattr(upload, "filename", None) or "image.jpg"
    content = await upload.read()

    if not content:
        return JSONResponse(
            {"error": "Загружен пустой файл."},
            status_code=400,
        )

    try:
        _validate_upload(filename=filename, content=content)
    except PhotoUploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    subdir = os.path.join(settings.media.MEDIA_ROOT, "media", "uploads")
    ensure_dir(subdir)
    dest = os.path.join(subdir, unique_name)

    def _save_image() -> str:
        img = Image.open(io.BytesIO(content))
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        img.save(dest, quality=90)
        return f"/media/media/uploads/{unique_name}"

    location = await asyncio.to_thread(_save_image)
    return JSONResponse({"location": location})


# ---------------------------------------------------------------------------
# Custom JS — sidebar state + submenu icons + edit photo preview
# ---------------------------------------------------------------------------


async def _admin_custom_js(request: Request) -> Response:
    """Кастомный JS для админ-панели.

    Решает четыре практические задачи:
    1. Не даёт sidebar dropdown закрываться по клику вне меню.
    2. Автоматически раскрывает dropdown с активным пунктом.
    3. Возвращает иконки внутренним пунктам меню.
    4. Показывает имя текущего файла на edit-формах с ImageField/FileField.

    Пункт №3 нужен потому, что шаблон dropdown в starlette-admin рендерит иконку
    только у самой dropdown-группы, а вложенные item'ы выводит просто текстом.
    Поэтому иконки view у внутренних пунктов формально есть, но в HTML не попадают.

    Важный нюанс:
    на /admin/ dashboard DOM бокового меню может отличаться от DOM list/edit-страниц
    и может дорисовываться/перестраиваться позже. Поэтому:
    - добавление иконок не завязано на "один правильный sidebar-root";
    - каждая операция выполняется отдельно, чтобы ошибка в одной не ломала остальные;
    - применяется повторная инициализация с ограниченным числом повторов.

    БЕЗОПАСНОСТЬ: endpoint защищён проверкой admin-сессии.
    Без валидной сессии возвращает 403 Forbidden.
    """
    # --- Auth guard: только авторизованные admin-пользователи ---
    if not _check_admin_session(request):
        return Response("// unauthorized", status_code=403, media_type="application/javascript")

    submenu_icon_map_json = json.dumps(ADMIN_SUBMENU_ICON_MAP, ensure_ascii=False)
    js = rf"""
    (function() {{
        var submenuIconMap = {submenu_icon_map_json};

        function onReady(fn) {{
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', fn, {{ once: true }});
            }} else {{
                fn();
            }}
        }}

        function safeRun(fn) {{
            try {{
                fn();
            }} catch (error) {{
                console.warn('[admin-custom-js] function failed:', error);
            }}
        }}

        function uniqueElements(nodeListArray) {{
            var seen = new Set();
            var result = [];

            nodeListArray.forEach(function(nodeList) {{
                Array.prototype.forEach.call(nodeList || [], function(node) {{
                    if (!node || seen.has(node)) return;
                    seen.add(node);
                    result.push(node);
                }});
            }});

            return result;
        }}

        function pathnameOf(href) {{
            try {{
                return new URL(href, window.location.href).pathname;
            }} catch (error) {{
                return '';
            }}
        }}

        function pathnameOfLink(link) {{
            try {{
                return new URL(link.href, window.location.href).pathname;
            }} catch (error) {{
                return pathnameOf(link.getAttribute('href') || '');
            }}
        }}

        function isAdminPath(pathname) {{
            return /^\/admin(?:\/|$)/.test(pathname || '');
        }}

        function extractIdentityFromPath(pathname) {{
            var match = (pathname || '').match(/^\/admin\/([^\/]+)(?:\/|$)/);
            return match ? match[1] : null;
        }}

        function getSidebarRoots() {{
            var roots = uniqueElements([
                document.querySelectorAll('.navbar-vertical'),
                document.querySelectorAll('aside'),
                document.querySelectorAll('[class*="sidebar"]'),
                document.querySelectorAll('.offcanvas'),
                document.querySelectorAll('.navbar-nav')
            ]).filter(function(node) {{
                return !!node.querySelector('a[href*="/admin/"], a[href^="/admin/"]');
            }});

            return roots;
        }}

        function getSidebarDropdownItems() {{
            var roots = getSidebarRoots();
            var lists = roots.map(function(root) {{
                return root.querySelectorAll('.nav-item.dropdown');
            }});

            var result = uniqueElements(lists);
            if (result.length) {{
                return result;
            }}

            return uniqueElements([
                document.querySelectorAll('.nav-item.dropdown')
            ]);
        }}

        function getSidebarLinks() {{
            var roots = getSidebarRoots();
            var lists = roots.map(function(root) {{
                return root.querySelectorAll('a[href]');
            }});

            var result = uniqueElements(lists).filter(function(link) {{
                var href = link.getAttribute('href') || '';
                if (!href || href == '#' || href.startsWith('#')) return false;
                return isAdminPath(pathnameOfLink(link));
            }});

            if (result.length) {{
                return result;
            }}

            return uniqueElements([
                document.querySelectorAll('a[href]')
            ]).filter(function(link) {{
                var href = link.getAttribute('href') || '';
                if (!href || href == '#' || href.startsWith('#')) return false;
                return isAdminPath(pathnameOfLink(link));
            }});
        }}

        function getSubmenuLinks() {{
            var result = uniqueElements([
                document.querySelectorAll('.dropdown-menu a[href]'),
                document.querySelectorAll('.collapse a[href]')
            ]).filter(function(link) {{
                var href = link.getAttribute('href') || '';
                if (!href || href == '#' || href.startsWith('#')) return false;
                return isAdminPath(pathnameOfLink(link));
            }});

            return result;
        }}

        /* ================================================================
         * 1. SIDEBAR — не закрываем dropdown от клика мимо меню
         * ================================================================ */
        function pinSidebarDropdowns() {{
            var dropdownItems = getSidebarDropdownItems();

            dropdownItems.forEach(function(item) {{
                var toggle = item.querySelector(':scope > .dropdown-toggle');
                var menu = item.querySelector(':scope > .dropdown-menu');
                if (!toggle || !menu) return;

                toggle.setAttribute('data-bs-auto-close', 'false');

                if (window.bootstrap && window.bootstrap.Dropdown) {{
                    var current = window.bootstrap.Dropdown.getInstance(toggle);
                    if (current) {{
                        current.dispose();
                    }}
                    window.bootstrap.Dropdown.getOrCreateInstance(toggle, {{
                        autoClose: false,
                    }});
                }}

                if (!item.dataset.keepOpenBound) {{
                    item.dataset.keepOpenBound = 'true';
                    item.addEventListener('hide.bs.dropdown', function(event) {{
                        var clickEvent = event.clickEvent;
                        var target = clickEvent && clickEvent.target;
                        if (!target) return;

                        if (toggle === target || toggle.contains(target)) {{
                            return;
                        }}

                        if (!item.contains(target)) {{
                            event.preventDefault();
                        }}
                    }});
                }}
            }});
        }}

        /* ================================================================
         * 2. SIDEBAR — раскрываем dropdown, содержащий активную ссылку
         * ================================================================ */
        function openActiveSidebarDropdown() {{
            var currentPath = window.location.pathname;
            var links = getSidebarLinks();

            var bestMatch = null;
            var bestLen = 0;

            links.forEach(function(link) {{
                var linkPath = pathnameOfLink(link);
                if (!linkPath) return;

                if (
                    currentPath === linkPath ||
                    currentPath.startsWith(linkPath + '/') ||
                    (linkPath !== '/admin' && linkPath !== '/admin/' && currentPath.startsWith(linkPath))
                ) {{
                    if (linkPath.length > bestLen) {{
                        bestLen = linkPath.length;
                        bestMatch = link;
                    }}
                }}
            }});

            if (!bestMatch) return;

            var el = bestMatch;
            while (el && el !== document.body) {{
                if (el.classList && el.classList.contains('dropdown-menu')) {{
                    el.classList.add('show');

                    var dropdownToggle = el.previousElementSibling;
                    if (dropdownToggle && dropdownToggle.classList.contains('dropdown-toggle')) {{
                        dropdownToggle.classList.add('show');
                        dropdownToggle.classList.remove('collapsed');
                        dropdownToggle.setAttribute('aria-expanded', 'true');

                        if (window.bootstrap && window.bootstrap.Dropdown) {{
                            window.bootstrap.Dropdown.getOrCreateInstance(dropdownToggle, {{
                                autoClose: false,
                            }});
                        }}
                    }}
                }}

                if (el.classList && el.classList.contains('collapse')) {{
                    el.classList.add('show');
                    var collapseId = el.id;
                    if (collapseId) {{
                        var triggers = document.querySelectorAll(
                            '[data-bs-target="#' + collapseId + '"],' +
                            '[href="#' + collapseId + '"]'
                        );
                        triggers.forEach(function(t) {{
                            t.setAttribute('aria-expanded', 'true');
                            t.classList.remove('collapsed');
                        }});
                    }}
                }}

                if (
                    el.classList &&
                    el.classList.contains('nav-item') &&
                    el.classList.contains('dropdown')
                ) {{
                    el.classList.add('active');
                }}

                el = el.parentElement;
            }}

            bestMatch.classList.add('active');
            var li = bestMatch.closest('li') || bestMatch.closest('.nav-item');
            if (li) li.classList.add('active');
        }}

        /* ================================================================
         * 3. SUBMENU ICONS — возвращаем иконки вложенным пунктам меню
         * ================================================================ */
        function addSubmenuIcons() {{
            var submenuLinks = getSubmenuLinks();

            submenuLinks.forEach(function(link) {{
                if (link.querySelector('.vekolom-submenu-icon')) return;

                var identity = extractIdentityFromPath(pathnameOfLink(link));
                if (!identity) return;

                var iconClass = submenuIconMap[identity];
                if (!iconClass) return;

                var icon = document.createElement('i');
                icon.className = iconClass + ' vekolom-submenu-icon me-2';
                icon.style.width = '1.1rem';
                icon.style.textAlign = 'center';
                icon.style.display = 'inline-block';
                icon.setAttribute('aria-hidden', 'true');

                var firstElement = link.firstElementChild;
                if (firstElement && firstElement.classList && firstElement.classList.contains('vekolom-submenu-icon')) {{
                    return;
                }}

                link.insertBefore(icon, link.firstChild);
            }});
        }}

        /* ================================================================
         * 4. SHOW CURRENT FILENAME ON EDIT FORM (for ImageField / FileField)
         * ================================================================ */
        function addPhotoHints() {{
            document.querySelectorAll('input[type="file"]').forEach(function(input) {{
                if (input.dataset.hintAdded) return;
                input.dataset.hintAdded = 'true';

                var wrapper = input.closest('.mb-3')
                    || input.closest('.form-group')
                    || input.parentElement;
                if (!wrapper) return;

                var existingImg = wrapper.querySelector('img[src]:not([src=""])');
                if (existingImg && existingImg.src && !existingImg.src.endsWith('/')) {{
                    var url = existingImg.src;
                    var filename = url.split('/').pop().split('?')[0];
                    if (filename) {{
                        var hint = document.createElement('div');
                        hint.className = 'text-muted small mt-1 mb-2';
                        hint.innerHTML = '&#128247; Текущий файл: <code>' + filename + '</code>';

                        var insertTarget = input.closest('.input-group') || input;
                        if (insertTarget.parentNode) {{
                            insertTarget.parentNode.insertBefore(hint, insertTarget);
                        }}
                    }}
                    return;
                }}

                var hiddenVal = wrapper.querySelector('input[type="hidden"]');
                if (hiddenVal && hiddenVal.value && hiddenVal.value !== '' && hiddenVal.value !== 'null') {{
                    var fname = hiddenVal.value.split('/').pop();
                    if (fname) {{
                        var hint2 = document.createElement('div');
                        hint2.className = 'text-muted small mt-1 mb-2';
                        hint2.innerHTML = '&#128247; Текущий файл: <code>' + fname + '</code>';

                        if (input.parentElement) {{
                            input.parentElement.insertBefore(hint2, input);
                        }}
                    }}
                }}
            }});
        }}

        /* ================================================================
         * 5. RE-RUN / OBSERVER
         * ================================================================ */
        function applySidebarEnhancements() {{
            safeRun(pinSidebarDropdowns);
            safeRun(openActiveSidebarDropdown);
            safeRun(addSubmenuIcons);
        }}

        function bindDocumentObserver() {{
            if (!document.body) {{
                return false;
            }}

            if (document.body.dataset.vekolomObserverBound === 'true') {{
                return true;
            }}

            document.body.dataset.vekolomObserverBound = 'true';

            var scheduled = false;
            var observer = new MutationObserver(function() {{
                if (scheduled) return;
                scheduled = true;

                setTimeout(function() {{
                    scheduled = false;
                    applySidebarEnhancements();
                    safeRun(addPhotoHints);
                }}, 50);
            }});

            observer.observe(document.body, {{
                childList: true,
                subtree: true,
            }});

            return true;
        }}

        function scheduleRetries() {{
            var attempts = 0;
            var maxAttempts = 12;
            var delayMs = 250;

            var timer = setInterval(function() {{
                attempts += 1;
                applySidebarEnhancements();

                if (attempts >= maxAttempts) {{
                    clearInterval(timer);
                }}
            }}, delayMs);
        }}

        onReady(function() {{
            applySidebarEnhancements();

            setTimeout(applySidebarEnhancements, 50);
            setTimeout(applySidebarEnhancements, 250);
            setTimeout(applySidebarEnhancements, 800);
            setTimeout(applySidebarEnhancements, 1500);

            bindDocumentObserver();
            scheduleRetries();

            setTimeout(function() {{
                safeRun(addPhotoHints);
            }}, 300);
        }});

        window.addEventListener('load', function() {{
            applySidebarEnhancements();
            safeRun(addPhotoHints);
        }});
    }})();
    """
    return Response(content=js, media_type="application/javascript")


# ---------------------------------------------------------------------------
# Admin builder helpers
# ---------------------------------------------------------------------------


def _iter_views(views: Iterable[Any]) -> Iterable[Any]:
    """Рекурсивно проходит по views и dropdown-вложенностям."""
    for view in views:
        yield view
        nested = getattr(view, "views", None)
        if nested:
            yield from _iter_views(nested)


def _build_admin_views() -> list[DropDown]:
    """Создаёт все root-level views для регистрации в Admin."""
    return [
        DropDown(
            "Главная страница",
            icon="fa fa-home",
            views=[
                MainCarouselView(MainCarousel),
                MainTextView(MainText),
                ActionView(Action),
                SloganView(Slogan),
                PriemView(Priem),
            ],
        ),
        DropDown(
            "Прайс-лист",
            icon="fa fa-list-alt",
            views=[
                CategoryView(Category),
                PositionView(Position),
                FotoView(Foto),
                PriceDateView(PriceDate),
            ],
        ),
        DropDown(
            "Контакты",
            icon="fa fa-address-book",
            views=[
                ContactsView(Contacts),
                MessagesView(MessMessages),
            ],
        ),
        DropDown(
            "SEO",
            icon="fa fa-search",
            views=[
                CoreSeoView(CoreSeo),
                PricelistSeoView(PricelistSeo),
                ContactsSeoView(ContactsSeo),
            ],
        ),
        DropDown(
            "API-ключи",
            icon="fa fa-key",
            views=[
                YandexMapsApiKeyView(YandexMapsApiKeyModel),
                SmartCaptchaKeyView(SmartCaptchaKeyModel),
            ],
        ),
    ]


def _collect_submenu_icon_map(views: Iterable[Any]) -> dict[str, str]:
    """Собирает карту `identity -> icon` для вложенных ModelView пунктов меню."""
    mapping: dict[str, str] = {}
    for view in _iter_views(views):
        identity = getattr(view, "identity", None)
        icon = getattr(view, "icon", None)
        if identity and icon:
            mapping[str(identity)] = str(icon)
    return mapping


# ---------------------------------------------------------------------------
# Admin builder
# ---------------------------------------------------------------------------


def build_admin(s: Settings) -> Admin:
    """Создаёт и конфигурирует экземпляр Starlette-Admin."""
    global ADMIN_SUBMENU_ICON_MAP

    engine = create_engine(str(s.database.sync_dsn), pool_pre_ping=True)

    # Каталог с переопределёнными шаблонами Starlette-Admin.
    # Нужен, чтобы dashboard (/admin/) тоже загружал кастомный JS,
    # а не только страницы конкретных ModelView.
    admin_templates_dir = str(Path(__file__).resolve().parent / "templates")

    admin = Admin(
        engine,
        title=s.app.ADMIN_TITLE,
        templates_dir=admin_templates_dir,
        i18n_config=I18nConfig(default_locale="ru"),
        auth_provider=SimpleAdminAuthProvider(
            username=s.app.ADMIN_USERNAME,
            password=s.app.ADMIN_PASSWORD,
        ),
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=s.app.SECRET_KEY,
                # Имя cookie — менее предсказуемое, чем дефолтный "session".
                session_cookie="vekolom_admin_sid",
                # max_age в секундах. Совпадает с SESSION_MAX_AGE в AuthProvider.
                # Cookie удаляется браузером через 2 часа, даже если вкладка открыта.
                max_age=SimpleAdminAuthProvider.SESSION_MAX_AGE,
                # same_site="lax" — cookie не отправляется при cross-site POST-запросах.
                # Это базовая защита от CSRF: злоумышленник не сможет отправить
                # POST-запрос к /admin/ со своего сайта и получить cookie.
                same_site="lax",
                # https_only=True в production — cookie передаётся только по HTTPS.
                # Без этого cookie перехватывается на открытых Wi-Fi (HTTP sniffing).
                # В dev (DEBUG=True) отключаем — localhost обычно без SSL.
                https_only=not s.app.DEBUG,
            ),
        ],
    )

    root_views = _build_admin_views()
    ADMIN_SUBMENU_ICON_MAP = _collect_submenu_icon_map(root_views)

    for view in root_views:
        admin.add_view(view)

    return admin


# ---------------------------------------------------------------------------
# Public mounting helpers
# ---------------------------------------------------------------------------


def mount_admin_support_routes(app: Any, s: Settings) -> None:
    """Монтирует служебные admin-route'ы и локальные TinyMCE-ассеты.

    Вызывается из `main.py` до `admin.mount_to(app)`.

    Добавляет:
      - POST /api/admin/tinymce-upload — загрузка изображений из TinyMCE
      - GET  /api/admin/custom.js      — sidebar/dropdown/icons/file-preview
      - Static mount `ADMIN_TINYMCE_ASSETS_URL` -> `ADMIN_TINYMCE_ASSETS_DIR`
    """
    from starlette.routing import Route

    assets_dir = s.admin_tinymce.ASSETS_DIR
    assets_url = s.admin_tinymce.ASSETS_URL

    if not os.path.isdir(assets_dir):
        logger.warning(
            "Admin TinyMCE assets directory does not exist yet: %s. "
            "Place TinyMCE files there or override ADMIN_TINYMCE_ASSETS_DIR.",
            assets_dir,
        )

    app.mount(
        assets_url,
        StaticFiles(directory=assets_dir, check_dir=False),
        name="admin-tinymce-assets",
    )

    admin_api_routes = [
        Route("/api/admin/tinymce-upload", _tinymce_upload, methods=["POST"]),
        Route("/api/admin/custom.js", _admin_custom_js, methods=["GET"]),
    ]
    app.routes[0:0] = admin_api_routes