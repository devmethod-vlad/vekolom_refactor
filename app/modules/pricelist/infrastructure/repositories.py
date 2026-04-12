"""
SQLAlchemy implementation of the pricelist read repository.

Read-only. Write operations should live in separate write repositories.

Field mapping from SA model columns to domain entity fields:
  Category.name          → Category.name
  Category.description   → Category.description
  Position.*             → PositionEntity.*  (все поля — 1:1)
  Foto.foto              → Foto.foto
  Foto.foto_webp         → Foto.foto_webp
  Foto.text              → Foto.text
  PriceDate.date         → PriceDate.date
  PricelistSeo.*         → PricelistSeo.*
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pricelist.domain.entities import (
    Category as CategoryEntity,
    Foto as FotoEntity,
    PositionEntity,
    PriceDate as PriceDateEntity,
    PricelistSeo as PricelistSeoEntity,
)
from app.modules.pricelist.domain.repositories import PricelistReadRepository
from .sa_models import (
    Category,
    Foto,
    Position,
    PriceDate,
    PricelistSeo,
)


class SAPricelistReadRepository(PricelistReadRepository):
    """SQLAlchemy-based implementation of ``PricelistReadRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # SEO  (PricelistSeo.objects.all())
    # ------------------------------------------------------------------

    async def list_seo(self) -> Sequence[PricelistSeoEntity]:
        """Return all PricelistSeo records ordered by id ascending."""
        result = await self._session.execute(
            select(PricelistSeo).order_by(PricelistSeo.id.asc())
        )
        rows: list[PricelistSeo] = list(result.scalars().all())
        return [
            PricelistSeoEntity(
                id=row.id,
                title=row.title,
                description=row.description,
                keywords=row.keywords,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # PriceDate  (PriceDate.objects.all())
    # ------------------------------------------------------------------

    async def list_dates(self) -> Sequence[PriceDateEntity]:
        """Return all PriceDate records ordered by id ascending."""
        result = await self._session.execute(
            select(PriceDate).order_by(PriceDate.id.asc())
        )
        rows: list[PriceDate] = list(result.scalars().all())
        return [
            PriceDateEntity(
                id=row.id,
                date=row.date,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Foto  (Foto.objects.all())
    # ------------------------------------------------------------------

    async def list_fotos(self) -> Sequence[FotoEntity]:
        """Return all Foto records ordered by id ascending."""
        result = await self._session.execute(
            select(Foto).order_by(Foto.id.asc())
        )
        rows: list[Foto] = list(result.scalars().all())
        return [
            FotoEntity(
                id=row.id,
                foto=row.foto,
                foto_webp=row.foto_webp,
                text=row.text,
                position_id=row.position_id,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Category  (Category.objects.order_by('-name'))
    # ------------------------------------------------------------------

    async def list_categories(self) -> Sequence[CategoryEntity]:
        """Return all categories ordered by name descending."""
        result = await self._session.execute(
            select(Category).order_by(Category.name.desc())
        )
        rows: list[Category] = list(result.scalars().all())
        return [
            CategoryEntity(
                id=row.id,
                name=row.name,
                description=row.description,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Position  (Position.objects.order_by('order'))
    # ------------------------------------------------------------------

    def _map_position(self, row: Position) -> PositionEntity:
        """Преобразует SA-модель Position в доменную сущность PositionEntity."""
        return PositionEntity(
            id=row.id,
            name=row.name,
            description=row.description,
            rules=row.rules,
            title=row.title,
            seodescrip=row.seodescrip,
            keywords=row.keywords,
            check_flag=row.check_flag,
            order=row.order,
            price_title=row.price_title,
            price=row.price,
            price2_title=row.price2_title,
            price_2=row.price_2,
            price3_title=row.price3_title,
            price_3=row.price_3,
            price_card_title=row.price_card_title,
            price_card=row.price_card,
            price2_card_title=row.price2_card_title,
            price2_card=row.price2_card,
            photo2=row.photo2,
            photo2_webp=row.photo2_webp,
            avatar_webp=row.avatar_webp,
            foto_app=row.foto_app,
            foto_rss=row.foto_rss,
            category_id=row.category_id,
            # category и fotos — заполняются на уровне use case при необходимости
            category=CategoryEntity(
                id=row.category.id,
                name=row.category.name,
                description=row.category.description,
            ) if row.category else None,
        )

    async def list_positions(self) -> Sequence[PositionEntity]:
        """Return all positions ordered by order ascending."""
        result = await self._session.execute(
            select(Position).order_by(Position.order.asc())
        )
        rows: list[Position] = list(result.scalars().all())
        return [self._map_position(row) for row in rows]

    async def list_checked_positions(self) -> Sequence[PositionEntity]:
        """Return positions with check_flag=True, ordered by order ascending.

        Используется на главной странице для блока позиций прайс-листа.
        """
        result = await self._session.execute(
            select(Position)
            .where(Position.check_flag.is_(True))
            .order_by(Position.order.asc())
        )
        rows: list[Position] = list(result.scalars().all())
        return [self._map_position(row) for row in rows]
