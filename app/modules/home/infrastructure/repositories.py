"""
SQLAlchemy implementation of the home read repository.

This module provides a concrete ``HomeReadRepository`` that uses
SQLAlchemy's asynchronous session to query PostgreSQL.  Each method
filters inactive rows and orders the results by ``sort_order`` then by
``id`` to provide deterministic ordering.

Note: this repository is intentionally read‑only.  Write operations
(create, update, delete) should be implemented in separate write
repositories to preserve the clear responsibilities of a CQRS setup.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.home.domain.entities import (
    Seo,
    CarouselSlide,
    MainBlock,
    ActionItem,
    Slogan,
    AcceptItem,
)
from app.modules.home.domain.repositories import HomeReadRepository
from .sa_models import CoreSeo, MainCarousel, MainText, Action, Accept, Slogan as SloganORM


class SAHomeReadRepository(HomeReadRepository):
    """SQLAlchemy‑based implementation of ``HomeReadRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_seo(self) -> Seo | None:
        """Return the first SEO record or ``None`` if none exist."""
        result = await self._session.execute(select(CoreSeo).order_by(CoreSeo.id.asc()).limit(1))
        row: CoreSeo | None = result.scalar_one_or_none()
        if row is None:
            return None
        return Seo(id=row.id, title=row.title, description=row.description, keywords=row.keywords)

    async def list_slides(self) -> Sequence[CarouselSlide]:
        stmt = (
            select(MainCarousel)
            .where(MainCarousel.is_active.is_(True))
            .order_by(MainCarousel.sort_order.asc(), MainCarousel.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[MainCarousel] = result.scalars().all()
        return [
            CarouselSlide(
                id=row.id,
                image_path=row.photo,
                image_webp_path=row.photo_webp,
                text_html=row.text,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ]

    async def list_main_blocks(self) -> Sequence[MainBlock]:
        stmt = (
            select(MainText)
            .where(MainText.is_active.is_(True))
            .order_by(MainText.sort_order.asc(), MainText.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[MainText] = result.scalars().all()
        return [
            MainBlock(
                id=row.id,
                header=row.header,
                text_html=row.text,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ]

    async def list_actions(self) -> Sequence[ActionItem]:
        stmt = (
            select(Action)
            .where(Action.is_active.is_(True))
            .order_by(Action.sort_order.asc(), Action.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[Action] = result.scalars().all()
        return [
            ActionItem(
                id=row.id,
                text_html=row.text,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ]

    async def list_slogans(self) -> Sequence[Slogan]:
        stmt = (
            select(SloganORM)
            .where(SloganORM.is_active.is_(True))
            .order_by(SloganORM.sort_order.asc(), SloganORM.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[SloganORM] = result.scalars().all()
        return [
            Slogan(
                id=row.id,
                text_html=row.text,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ]

    async def list_accept_items(self) -> Sequence[AcceptItem]:
        stmt = (
            select(Accept)
            .where(Accept.is_active.is_(True))
            .order_by(Accept.sort_order.asc(), Accept.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[Accept] = result.scalars().all()
        return [
            AcceptItem(
                id=row.id,
                header=row.header,
                text_html=row.text,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ]

    async def list_positions(self) -> Sequence[dict]:
        """Return price list positions if integrated, else an empty list.

        For now we return an empty list because the price list module has
        not yet been migrated.  In a future refactoring this method
        should delegate to a repository from the price list module to
        fetch the positions and map them into an appropriate DTO.
        """

        return []