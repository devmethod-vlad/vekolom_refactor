"""
Application layer use cases for the apikeys module.

``GetYandexMapsApiKey``   — получение активного ключа Яндекс.Карт.
``GetSmartCaptchaKeys``   — получение активных ключей SmartCaptcha.

Use cases используются presentation-слоем страниц home и contacts
для передачи ключей в шаблоны.
"""

from __future__ import annotations

from typing import Optional

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.apikeys.domain.entities import SmartCaptchaKey, YandexMapsApiKey


class GetYandexMapsApiKey:
    """Use case для получения активного ключа Яндекс.Карт.

    Возвращает строку ключа или пустую строку, если ключ не настроен.
    Пустая строка безопаснее None для шаблонов: скрипт карты просто
    не загрузится с пустым apikey, без ошибок Jinja2 UndefinedError.
    """

    async def execute(self, uow: AsyncUnitOfWork) -> str:
        """Получить значение активного API-ключа Яндекс.Карт."""
        key: Optional[YandexMapsApiKey] = (
            await uow.apikeys.get_active_yandex_maps_key()
        )
        return key.api_key if key else ""


class GetSmartCaptchaKeys:
    """Use case для получения активных ключей SmartCaptcha.

    Возвращает кортеж (client_key, server_key).
    Если ключи не настроены, возвращает ("", "").
    """

    async def execute(self, uow: AsyncUnitOfWork) -> tuple[str, str]:
        """Получить пару (client_key, server_key) активной SmartCaptcha."""
        key: Optional[SmartCaptchaKey] = (
            await uow.apikeys.get_active_smartcaptcha_key()
        )
        if key:
            return key.client_key, key.server_key
        return "", ""
