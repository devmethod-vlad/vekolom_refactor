"""
Repository protocols for the apikeys module.

Определяют интерфейс доступа к API-ключам:
  get_active_yandex_maps_key()    — активный ключ Яндекс.Карт (или None)
  get_active_smartcaptcha_key()   — активный ключ SmartCaptcha (или None)

Протокол намеренно возвращает Optional: если ключ не настроен,
presentation-слой просто передаёт пустую строку в шаблон,
и соответствующий виджет (карта / капча) не загружается.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .entities import SmartCaptchaKey, YandexMapsApiKey


class ApiKeysReadRepository(Protocol):
    """Protocol describing read operations for API keys."""

    async def get_active_yandex_maps_key(self) -> Optional[YandexMapsApiKey]:
        """Возвращает первый активный ключ Яндекс.Карт или None.

        Если в таблице несколько активных записей, возвращается
        запись с наименьшим id (первая по порядку).
        """

    async def get_active_smartcaptcha_key(self) -> Optional[SmartCaptchaKey]:
        """Возвращает первый активный ключ SmartCaptcha или None.

        Если в таблице несколько активных записей, возвращается
        запись с наименьшим id (первая по порядку).
        """
