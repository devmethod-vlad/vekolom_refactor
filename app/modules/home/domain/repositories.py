"""
Repository protocol for the home module.

Method names mirror the Django ORM calls used in the legacy view so it is
easy to verify that every queryset has a counterpart here:

    get_seo()         ← CoreSeo.objects.all()
    list_slides()     ← MainCarousel.objects.all()
    list_main()       ← MainText.objects.all()
    list_actions()    ← Actions.objects.all()
    list_slogan1()    ← Slogan1.objects.all()
    list_priem()      ← Priem.objects.all()
    list_positions()  ← Position.objects.filter(check_flag=True)
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .entities import (
    Seo,
    CarouselSlide,
    MainBlock,
    ActionItem,
    Slogan,
    PriemItem,
)


class HomeReadRepository(Protocol):
    """Protocol describing all read operations needed by the home use cases."""

    async def get_seo(self) -> Seo | None:
        """Return the first SEO record or ``None`` if none exist."""

    async def list_slides(self) -> Sequence[CarouselSlide]:
        """Return all carousel slides ordered by ``id`` ascending.

        Corresponds to ``MainCarousel.objects.all()``.
        """

    async def list_main(self) -> Sequence[MainBlock]:
        """Return all main text blocks ordered by ``id`` ascending.

        Corresponds to ``MainText.objects.all()``.
        """

    async def list_actions(self) -> Sequence[ActionItem]:
        """Return all action items ordered by ``id`` ascending.

        Corresponds to ``Actions.objects.all()``.
        The use case picks the first three items as ``action1/2/3``.
        """

    async def list_slogan1(self) -> Sequence[Slogan]:
        """Return all slogans ordered by ``id`` ascending.

        Corresponds to ``Slogan1.objects.all()``.
        """

    async def list_priem(self) -> Sequence[PriemItem]:
        """Return all 'we accept' items ordered by ``id`` ascending.

        Corresponds to ``Priem.objects.all()``.
        """

    async def list_positions(self) -> Sequence[dict]:
        """Return price list positions where ``check_flag = True``.

        Corresponds to ``Position.objects.filter(check_flag=True)``.
        Returns an empty list until the pricelist module is migrated.
        """