"""CSRF-защита для FastAPI-форм и admin-панели.

Реализация на основе Double Submit Cookie паттерна:
  1. При каждом запросе генерируется (или переиспользуется) CSRF-токен.
  2. Токен записывается в cookie (``vekolom_csrf``) и передаётся в шаблон.
  3. Форма включает ``<input type="hidden" name="csrf_token" value="...">``
     (через Jinja2-функцию ``csrf_input()``).
  4. При POST-запросе middleware сверяет токен из cookie с токеном из формы.

Почему Double Submit Cookie, а не Synchronizer Token:
  - Не требует серверного хранилища (сессии, Redis);
  - Простота интеграции с FastAPI (нет встроенного CSRF, как в Django);
  - Подходит для server-rendered форм (Jinja2).

Безопасность:
  - Cookie с ``SameSite=Lax`` — браузер не отправит cookie при cross-site POST.
  - ``HttpOnly=False`` — cookie читается JS только если нужно (для AJAX),
    но основная защита — сравнение cookie и form field.
  - Токен — 32 байта из ``secrets.token_urlsafe`` (256 бит энтропии).
  - HMAC-подпись токена через SECRET_KEY предотвращает подделку.

Интеграция:
  - ``CSRFMiddleware`` добавляется в FastAPI app.
  - ``csrf_input()`` регистрируется как Jinja2-глобал.
  - Формы добавляют ``{{ csrf_input() }}`` внутри ``<form>``.
  - Admin-панель защищена через ``SameSite=Lax`` на session cookie
    (см. admin/setup.py) — дополнительный CSRF-токен в админке не нужен,
    т.к. starlette-admin использует session-based auth с Lax cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Callable

from markupsafe import Markup
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.infrastructure.csrf")

# Имя cookie и поля формы
CSRF_COOKIE_NAME = "vekolom_csrf"
CSRF_FORM_FIELD = "csrf_token"

# Пути, которые НЕ проверяются на CSRF (API, SSE, webhooks и т.д.)
# Admin защищён через SameSite=Lax session cookie.
# Пути, которые НЕ проверяются на CSRF (API, SSE, webhooks и т.д.)
# Admin защищён через SameSite=Lax session cookie.
# AMP-формы отправляются через XHR с AMP cache origin (cdn.ampproject.org),
# поэтому Double Submit Cookie невозможен — CSRF проверка обходится.
# Защита AMP-форм от спама обеспечивается серверной валидацией.
CSRF_EXEMPT_PREFIXES = (
    "/admin/",
    "/api/admin/",
    "/api/pwa/",
    "/amp/",
)

# Безопасные HTTP-методы, не требующие проверки
CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _generate_csrf_token() -> str:
    """Генерирует криптографически стойкий CSRF-токен (256 бит)."""
    return secrets.token_urlsafe(32)


def _sign_token(token: str, secret_key: str) -> str:
    """Создаёт HMAC-подпись токена.

    Подпись не позволяет злоумышленнику сгенерировать валидный токен
    без знания SECRET_KEY, даже если он может установить cookie
    (например, через субдомен).
    """
    return hmac.new(
        secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _make_signed_token(secret_key: str) -> str:
    """Генерирует токен и возвращает ``token:signature``."""
    token = _generate_csrf_token()
    signature = _sign_token(token, secret_key)
    return f"{token}:{signature}"


def _verify_signed_token(signed_token: str, secret_key: str) -> bool:
    """Проверяет подпись CSRF-токена.

    Возвращает True, если подпись корректна.
    Использует ``hmac.compare_digest`` для защиты от timing attack.
    """
    if not signed_token or ":" not in signed_token:
        return False

    token, signature = signed_token.rsplit(":", 1)
    expected_signature = _sign_token(token, secret_key)
    return hmac.compare_digest(signature, expected_signature)


def _is_csrf_exempt(path: str) -> bool:
    """Проверяет, освобождён ли путь от CSRF-проверки."""
    return any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES)


class CSRFMiddleware:
    """ASGI-middleware для CSRF-защиты по паттерну Double Submit Cookie.

    Логика:
      - GET/HEAD/OPTIONS/TRACE: устанавливает CSRF-cookie, если его нет.
      - POST/PUT/PATCH/DELETE: сверяет токен из cookie и из тела формы.
      - Пути из ``CSRF_EXEMPT_PREFIXES`` не проверяются.

    Параметры:
        app        — ASGI-приложение.
        secret_key — секретный ключ приложения (для HMAC-подписи токенов).
        secure     — передавать cookie только по HTTPS (True в prod).
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        secure: bool = True,
    ) -> None:
        self.app = app
        self.secret_key = secret_key
        self.secure = secure

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path
        method = request.method

        # --- Пути, освобождённые от CSRF ---
        if _is_csrf_exempt(path):
            await self.app(scope, receive, send)
            return

        # --- Безопасные методы: только установка cookie ---
        if method in CSRF_SAFE_METHODS:
            csrf_token = request.cookies.get(CSRF_COOKIE_NAME)

            # Если cookie нет или подпись невалидна — генерируем новый
            if not csrf_token or not _verify_signed_token(csrf_token, self.secret_key):
                csrf_token = _make_signed_token(self.secret_key)

            # Сохраняем токен в scope.state для доступа из Jinja2-глобала
            scope.setdefault("state", {})
            scope["state"]["csrf_token"] = csrf_token

            # Оборачиваем send, чтобы добавить Set-Cookie к ответу
            send = self._make_send_with_cookie(send, csrf_token)
            await self.app(scope, receive, send)
            return

        # --- Мутирующие методы: проверка CSRF ---
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        if not cookie_token:
            logger.warning(
                "CSRF check failed: no cookie. path=%s method=%s",
                path, method,
            )
            response = Response(
                "CSRF-проверка не пройдена: отсутствует cookie.",
                status_code=403,
            )
            await response(scope, receive, send)
            return

        if not _verify_signed_token(cookie_token, self.secret_key):
            logger.warning(
                "CSRF check failed: invalid cookie signature. path=%s method=%s",
                path, method,
            )
            response = Response(
                "CSRF-проверка не пройдена: невалидная подпись токена.",
                status_code=403,
            )
            await response(scope, receive, send)
            return

        # Получаем токен из формы
        form_token = await self._extract_form_token(request)

        if not form_token:
            logger.warning(
                "CSRF check failed: no form token. path=%s method=%s",
                path, method,
            )
            response = Response(
                "CSRF-проверка не пройдена: отсутствует токен в форме.",
                status_code=403,
            )
            await response(scope, receive, send)
            return

        # Сравниваем cookie-токен с form-токеном (constant-time)
        if not hmac.compare_digest(cookie_token, form_token):
            logger.warning(
                "CSRF check failed: token mismatch. path=%s method=%s",
                path, method,
            )
            response = Response(
                "CSRF-проверка не пройдена: токены не совпадают.",
                status_code=403,
            )
            await response(scope, receive, send)
            return

        # CSRF-проверка пройдена — пробрасываем токен в state для ответа
        scope.setdefault("state", {})
        scope["state"]["csrf_token"] = cookie_token
        send = self._make_send_with_cookie(send, cookie_token)
        await self.app(scope, receive, send)

    async def _extract_form_token(self, request: Request) -> str | None:
        """Извлекает CSRF-токен из тела POST-запроса (form data).

        Поддерживает ``application/x-www-form-urlencoded``
        и ``multipart/form-data``.
        """
        content_type = request.headers.get("content-type", "")

        if (
            "application/x-www-form-urlencoded" in content_type
            or "multipart/form-data" in content_type
        ):
            form = await request.form()
            return form.get(CSRF_FORM_FIELD)

        return None

    def _make_send_with_cookie(
        self, send: Send, csrf_token: str
    ) -> Callable:
        """Оборачивает send для добавления Set-Cookie заголовка."""

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                cookie_parts = [
                    f"{CSRF_COOKIE_NAME}={csrf_token}",
                    "Path=/",
                    "SameSite=Lax",
                ]
                if self.secure:
                    cookie_parts.append("Secure")
                # HttpOnly=False — токен должен быть доступен для вставки в форму
                # (но основная защита — сравнение двух значений)
                headers.append("Set-Cookie", "; ".join(cookie_parts))
            await send(message)

        return send_with_cookie


def csrf_input_callable(request: Request) -> Markup:
    """Jinja2-глобал: генерирует ``<input type="hidden">`` с CSRF-токеном.

    Использование в шаблоне:
        <form method="post">
            {{ csrf_input() }}
            ...
        </form>

    Возвращает Markup (не экранируется Jinja2).
    """
    csrf_token = getattr(request.state, "csrf_token", "")
    return Markup(
        f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{csrf_token}">'
    )
