"""
SQLAlchemy implementation of the home read repository.

Read-only.  Write operations should live in separate write repositories.

Field mapping from SA model columns to domain entity fields:
  MainCarousel.photo       → CarouselSlide.photo
  MainCarousel.photo_webp  → CarouselSlide.photo_webp
  MainCarousel.photo_amp   → CarouselSlide.photo_amp
  MainCarousel.photo_turbo → CarouselSlide.photo_turbo
  MainCarousel.text        → CarouselSlide.text
  MainText.header          → MainBlock.header
  MainText.text            → MainBlock.text
  Action.text              → ActionItem.text
  Slogan.text              → Slogan.text          (ORM class aliased as SloganORM)
  Priem.header             → PriemItem.header
  Priem.text               → PriemItem.text
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
    PriemItem,
)
from app.modules.home.domain.repositories import HomeReadRepository
from .sa_models import (
    CoreSeo,
    MainCarousel,
    MainText,
    Action,
    Priem,
    Slogan as SloganORM,
)


class SAHomeReadRepository(HomeReadRepository):
    """SQLAlchemy-based implementation of ``HomeReadRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # SEO
    # ------------------------------------------------------------------

    async def get_seo(self) -> Seo | None:
        """Return the first SEO record or ``None``.

        Corresponds to ``CoreSeo.objects.all()`` — the legacy view passed the
        full queryset but templates only ever used the first element.
        """
        result = await self._session.execute(
            select(CoreSeo).order_by(CoreSeo.id.asc()).limit(1)
        )
        row: CoreSeo | None = result.scalar_one_or_none()
        if row is None:
            return None
        return Seo(
            id=row.id,
            title=row.title,
            description=row.description,
            keywords=row.keywords,
        )

    # ------------------------------------------------------------------
    # Carousel  (MainCarousel.objects.all())
    # ------------------------------------------------------------------

    async def list_slides(self) -> Sequence[CarouselSlide]:
        stmt = select(MainCarousel).order_by(MainCarousel.id.asc())
        result = await self._session.execute(stmt)
        rows: list[MainCarousel] = result.scalars().all()
        return [
            CarouselSlide(
                id=row.id,
                photo=row.photo,
                photo_webp=row.photo_webp,
                photo_amp=row.photo_amp,
                photo_turbo=row.photo_turbo,
                text=row.text,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Main text blocks  (MainText.objects.all())
    # ------------------------------------------------------------------

    async def list_main(self) -> Sequence[MainBlock]:
        stmt = select(MainText).order_by(MainText.id.asc())
        result = await self._session.execute(stmt)
        rows: list[MainText] = result.scalars().all()
        return [
            MainBlock(
                id=row.id,
                header=row.header,
                text=row.text,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Actions  (Actions.objects.all())
    # ------------------------------------------------------------------

    async def list_actions(self) -> Sequence[ActionItem]:
        stmt = select(Action).order_by(Action.id.asc())
        result = await self._session.execute(stmt)
        rows: list[Action] = result.scalars().all()
        return [
            ActionItem(
                id=row.id,
                text=row.text,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Slogans  (Slogan1.objects.all())
    # ------------------------------------------------------------------

    async def list_slogan1(self) -> Sequence[Slogan]:
        stmt = select(SloganORM).order_by(SloganORM.id.asc())
        result = await self._session.execute(stmt)
        rows: list[SloganORM] = result.scalars().all()
        return [
            Slogan(
                id=row.id,
                text=row.text,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # "We accept" items  (Priem.objects.all())
    # ------------------------------------------------------------------

    async def list_priem(self) -> Sequence[PriemItem]:
        stmt = select(Priem).order_by(Priem.id.asc())
        result = await self._session.execute(stmt)
        rows: list[Priem] = result.scalars().all()
        return [
            PriemItem(
                id=row.id,
                header=row.header,
                text=row.text,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Price list positions  (Position.objects.filter(check_flag=True))
    # ------------------------------------------------------------------

    async def list_positions(self) -> Sequence[dict]:
        """Return positions with ``check_flag = True``.

        The pricelist module has not yet been migrated, so this method
        returns an empty list for now.  Once the ``pricelist`` module is
        available, replace the body with a delegating call to its
        repository and map the results to dicts with at minimum the keys:
        ``name``, ``price``, ``photo2``, ``avatar``
        (matching the template's ``{{ position.name }}``, etc.).
        """
        return []