"""
Repository protocol for the pricelist module.

Method names mirror the Django ORM calls used in the legacy view so it is
easy to verify that every queryset has a counterpart here:

    list_seo()                ← PricelistSeo.objects.all()
    list_dates()              ← PriceDate.objects.all()
    list_fotos()              ← Foto.objects.all()
    list_categories()         ← Category.objects.order_by('-name')
    list_positions()          ← Position.objects.order_by('order')
    list_checked_positions()  ← Position.objects.filter(check_flag=True)
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .entities import (
    Category,
    Foto,
    PositionEntity,
    PriceDate,
    PricelistSeo,
)


class PricelistReadRepository(Protocol):
    """Protocol describing all read operations needed by the pricelist use cases."""

    async def list_seo(self) -> Sequence[PricelistSeo]:
        """Return all PricelistSeo records.

        Corresponds to ``PricelistSeo.objects.all()``.
        """

    async def list_dates(self) -> Sequence[PriceDate]:
        """Return all PriceDate records.

        Corresponds to ``PriceDate.objects.all()``.
        """

    async def list_fotos(self) -> Sequence[Foto]:
        """Return all Foto records.

        Corresponds to ``Foto.objects.all()``.
        """

    async def list_categories(self) -> Sequence[Category]:
        """Return all categories ordered by name descending.

        Corresponds to ``Category.objects.order_by('-name')``.
        """

    async def list_positions(self) -> Sequence[PositionEntity]:
        """Return all positions ordered by ``order`` ascending.

        Corresponds to ``Position.objects.order_by('order')``.
        """

    async def list_checked_positions(self) -> Sequence[PositionEntity]:
        """Return positions where ``check_flag = True``, ordered by ``order``.

        Corresponds to ``Position.objects.filter(check_flag=True).order_by('order')``.
        Used on the home page.
        """
