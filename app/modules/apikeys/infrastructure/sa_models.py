"""SQLAlchemy ORM models for the apikeys module.

Таблицы для хранения API-ключей внешних сервисов:
  ``apikeys_yandex_maps``   — ключ API Яндекс.Карт
  ``apikeys_smartcaptcha``  — ключи Yandex SmartCaptcha (client + server)

Имена таблиц используют префикс ``apikeys_`` для логической группировки
и предотвращения коллизий с таблицами других модулей.

Обе таблицы содержат поле ``is_active``, позволяющее хранить
несколько ключей и переключаться между ними без удаления записей.
"""

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


# ---------------------------------------------------------------------------
# YandexMapsApiKey  (таблица ``apikeys_yandex_maps``)
# ---------------------------------------------------------------------------


class YandexMapsApiKeyModel(Base):
    """Ключ API Яндекс.Карт (таблица ``apikeys_yandex_maps``).

    Схема:
        id          bigserial primary key
        api_key     varchar(255) not null   — ключ API
        description text                    — описание / комментарий
        is_active   boolean default true    — флаг активности
    """

    __tablename__ = "apikeys_yandex_maps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __str__(self) -> str:
        status = "активен" if self.is_active else "неактивен"
        return f"Яндекс.Карты [{status}]: {self.api_key[:12]}..."


# ---------------------------------------------------------------------------
# SmartCaptchaKeyModel  (таблица ``apikeys_smartcaptcha``)
# ---------------------------------------------------------------------------


class SmartCaptchaKeyModel(Base):
    """Ключи Yandex SmartCaptcha (таблица ``apikeys_smartcaptcha``).

    Схема:
        id          bigserial primary key
        client_key  varchar(255) not null   — публичный ключ (для фронтенда)
        server_key  varchar(255) not null   — секретный ключ (для валидации)
        description text                    — описание / комментарий
        is_active   boolean default true    — флаг активности
    """

    __tablename__ = "apikeys_smartcaptcha"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_key: Mapped[str] = mapped_column(String(255), nullable=False)
    server_key: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __str__(self) -> str:
        status = "активен" if self.is_active else "неактивен"
        return f"SmartCaptcha [{status}]: {self.client_key[:12]}..."
