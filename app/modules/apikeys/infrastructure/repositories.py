"""
SQLAlchemy implementation of the apikeys read repository.

Маппинг SA-модель → domain entity:
  YandexMapsApiKeyModel  → YandexMapsApiKey
  SmartCaptchaKeyModel   → SmartCaptchaKey
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.apikeys.domain.entities import (
    SmartCaptchaKey,
    YandexMapsApiKey,
)
from app.modules.apikeys.domain.repositories import ApiKeysReadRepository
from .sa_models import SmartCaptchaKeyModel, YandexMapsApiKeyModel


class SAApiKeysReadRepository(ApiKeysReadRepository):
    """SQLAlchemy-based implementation of ``ApiKeysReadRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Яндекс.Карты
    # ------------------------------------------------------------------

    async def get_active_yandex_maps_key(self) -> Optional[YandexMapsApiKey]:
        """Возвращает первый активный ключ Яндекс.Карт или None."""
        result = await self._session.execute(
            select(YandexMapsApiKeyModel)
            .where(YandexMapsApiKeyModel.is_active.is_(True))
            .order_by(YandexMapsApiKeyModel.id.asc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return None

        return YandexMapsApiKey(
            id=row.id,
            api_key=row.api_key,
            description=row.description,
            is_active=row.is_active,
        )

    # ------------------------------------------------------------------
    # SmartCaptcha
    # ------------------------------------------------------------------

    async def get_active_smartcaptcha_key(self) -> Optional[SmartCaptchaKey]:
        """Возвращает первый активный ключ SmartCaptcha или None."""
        result = await self._session.execute(
            select(SmartCaptchaKeyModel)
            .where(SmartCaptchaKeyModel.is_active.is_(True))
            .order_by(SmartCaptchaKeyModel.id.asc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return None

        return SmartCaptchaKey(
            id=row.id,
            client_key=row.client_key,
            server_key=row.server_key,
            description=row.description,
            is_active=row.is_active,
        )
