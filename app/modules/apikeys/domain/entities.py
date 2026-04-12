"""
Domain entities for the apikeys module.

Хранят API-ключи внешних сервисов, используемых на страницах сайта:
  YandexMapsApiKey   — ключ API Яндекс.Карт (таблица ``apikeys_yandex_maps``)
  SmartCaptchaKey    — ключи Yandex SmartCaptcha (таблица ``apikeys_smartcaptcha``)

SmartCaptcha требует два ключа:
  - ``client_key`` — публичный, передаётся в шаблон (data-sitekey);
  - ``server_key`` — секретный, используется на сервере для валидации токена.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class YandexMapsApiKey:
    """Ключ API Яндекс.Карт (таблица ``apikeys_yandex_maps``).

    Используется на страницах home и contacts для загрузки
    скрипта Яндекс.Карт:
        https://api-maps.yandex.ru/2.1/?apikey={{ yandex_maps_api_key }}

    ``is_active`` позволяет хранить несколько ключей и переключаться
    без удаления записей (например, при ротации ключей).
    """

    id: int
    api_key: str
    description: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class SmartCaptchaKey:
    """Ключи Yandex SmartCaptcha (таблица ``apikeys_smartcaptcha``).

    ``client_key`` — публичный ключ для фронтенда (data-sitekey).
    ``server_key`` — секретный ключ для серверной валидации токена
                     через https://smartcaptcha.yandexcloud.net/validate.

    Используется на странице contacts для защиты формы обратной связи.
    """

    id: int
    client_key: str
    server_key: str
    description: Optional[str] = None
    is_active: bool = True
