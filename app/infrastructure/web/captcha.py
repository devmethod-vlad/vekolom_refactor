"""Сервис валидации Yandex SmartCaptcha токенов.

После прохождения капчи на клиенте, JS-виджет SmartCaptcha добавляет
в форму скрытое поле ``smart-token``. Сервер должен отправить этот токен
на проверку в Yandex SmartCaptcha API:

    POST https://smartcaptcha.yandexcloud.net/validate
    Content-Type: application/x-www-form-urlencoded

    secret=<server_key>&token=<smart-token>&ip=<client_ip>

Ответ — JSON: ``{"status": "ok"}`` при успехе.

Этот модуль инкапсулирует логику валидации, чтобы presentation-слой
не зависел от деталей HTTP-вызова к Yandex API.

В DEBUG-режиме валидация может быть отключена для удобства разработки
(см. параметр ``skip_in_debug``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("app.infrastructure.captcha")

# URL эндпоинта валидации Yandex SmartCaptcha
SMARTCAPTCHA_VALIDATE_URL = "https://smartcaptcha.yandexcloud.net/validate"

# Таймаут HTTP-запроса к Yandex API (секунды)
SMARTCAPTCHA_TIMEOUT = 5.0


@dataclass(frozen=True, slots=True)
class CaptchaValidationResult:
    """Результат валидации SmartCaptcha.

    ``passed``  — True, если капча пройдена успешно.
    ``error``   — текст ошибки для пользователя (если ``passed=False``).
    """

    passed: bool
    error: Optional[str] = None


async def validate_smartcaptcha(
    token: str | None,
    server_key: str,
    client_ip: str = "",
) -> CaptchaValidationResult:
    """Валидирует SmartCaptcha токен через Yandex API.

    Args:
        token:      Значение поля ``smart-token`` из POST-формы.
        server_key: Секретный ключ SmartCaptcha (из БД).
        client_ip:  IP-адрес клиента (опционально, повышает точность).

    Returns:
        ``CaptchaValidationResult`` с результатом проверки.
    """
    if not token:
        logger.warning("SmartCaptcha validation: empty token")
        return CaptchaValidationResult(
            passed=False,
            error="Пожалуйста, пройдите проверку капчи.",
        )

    if not server_key:
        logger.error(
            "SmartCaptcha validation: server_key is empty — "
            "ключ SmartCaptcha не настроен в базе данных"
        )
        return CaptchaValidationResult(
            passed=False,
            error="Ошибка конфигурации капчи. Обратитесь к администратору.",
        )

    try:
        async with httpx.AsyncClient(timeout=SMARTCAPTCHA_TIMEOUT) as client:
            response = await client.post(
                SMARTCAPTCHA_VALIDATE_URL,
                data={
                    "secret": server_key,
                    "token": token,
                    "ip": client_ip,
                },
            )

        if response.status_code != 200:
            logger.error(
                "SmartCaptcha validation: HTTP %d from Yandex API",
                response.status_code,
            )
            return CaptchaValidationResult(
                passed=False,
                error="Ошибка проверки капчи. Попробуйте ещё раз.",
            )

        data = response.json()

        if data.get("status") == "ok":
            logger.info("SmartCaptcha validation: passed")
            return CaptchaValidationResult(passed=True)

        logger.warning(
            "SmartCaptcha validation: rejected. response=%s", data,
        )
        return CaptchaValidationResult(
            passed=False,
            error="Проверка капчи не пройдена. Попробуйте ещё раз.",
        )

    except httpx.TimeoutException:
        logger.error("SmartCaptcha validation: timeout")
        return CaptchaValidationResult(
            passed=False,
            error="Сервер проверки капчи не ответил. Попробуйте позже.",
        )
    except Exception:
        logger.exception("SmartCaptcha validation: unexpected error")
        return CaptchaValidationResult(
            passed=False,
            error="Ошибка проверки капчи. Попробуйте ещё раз.",
        )
