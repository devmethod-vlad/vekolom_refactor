"""ModelView-классы для модуля apikeys.

Содержит представления админ-панели для управления API-ключами:
  - YandexMapsApiKeyView  — ключи Яндекс.Карт
  - SmartCaptchaKeyView   — ключи Yandex SmartCaptcha

Ключи хранятся в базе данных и используются на страницах home и contacts
для загрузки Яндекс.Карт и виджета SmartCaptcha.
"""

from __future__ import annotations

from app.admin.views.base import BaseAdminView
from app.modules.apikeys.infrastructure.sa_models import (
    SmartCaptchaKeyModel,
    YandexMapsApiKeyModel,
)


# ---------------------------------------------------------------------------
# Ключи Яндекс.Карт
# ---------------------------------------------------------------------------


class YandexMapsApiKeyView(BaseAdminView):
    """Управление ключами API Яндекс.Карт.

    Позволяет добавлять, редактировать и деактивировать ключи.
    На сайте используется первый активный ключ.
    """

    label = "Яндекс.Карты"
    name = "Ключ Яндекс.Карт"
    icon = "fa fa-map"

    column_list = ["id", "description", "is_active"]

    exclude_fields_from_list=["api_key"]

    column_labels = {
        "id": "ID",
        "api_key": "API-ключ",
        "description": "Описание",
        "is_active": "Активен",
    }


# ---------------------------------------------------------------------------
# Ключи SmartCaptcha
# ---------------------------------------------------------------------------


class SmartCaptchaKeyView(BaseAdminView):
    """Управление ключами Yandex SmartCaptcha.

    Хранит пару ключей:
      - client_key — публичный, передаётся в HTML-шаблон (data-sitekey).
      - server_key — секретный, используется на сервере для валидации.

    На сайте используется первая активная пара ключей.
    """

    label = "SmartCaptcha"
    name = "Ключ SmartCaptcha"
    icon = "fa fa-shield"

    column_list = ["id", "description", "is_active"]

    exclude_fields_from_list = ["client_key", "server_key",]

    column_labels = {
        "id": "ID",
        "client_key": "Клиентский ключ",
        "server_key": "Серверный ключ",
        "description": "Описание",
        "is_active": "Активен",
    }
