"""
Repository protocol for the home module.

This module defines a protocol that specifies the read operations
required by the home page use cases.  It encapsulates the various
queries into a cohesive interface so that the application layer can
remain agnostic of how data is fetched.  Implementations may use
SQLAlchemy, an external API, a cache, or any other backing store.
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
        """Return the SEO meta information for the home page.

        Should return ``None`` if no SEO record exists.
        """

    async def list_slides(self) -> Sequence[CarouselSlide]:
        """Return all carousel slides in ascending order.

        Implementations should filter out inactive slides and order by
        ``sort_order`` then by ``id`` to provide a stable ordering.
        """

    async def list_main_blocks(self) -> Sequence[MainBlock]:
        """Return all main text blocks in ascending order.

        Inactive records should be excluded; ordering should follow
        ``sort_order`` then ``id``.
        """

    async def list_actions(self) -> Sequence[ActionItem]:
        """Return all action items in ascending order.

        Inactive records should be excluded; ordering should follow
        ``sort_order`` then ``id``.
        """

    async def list_slogans(self) -> Sequence[Slogan]:
        """Return all slogans in ascending order.

        Inactive records should be excluded; ordering should follow
        ``sort_order`` then ``id``.
        """

    async def list_priem_items(self) -> Sequence[PriemItem]:
        """Return all 'we accept' items in ascending order.

        Inactive records should be excluded; ordering should follow
        ``sort_order`` then ``id``.
        """

    async def list_positions(self) -> Sequence[dict]:
        """Return the list of positions from the price list.

        Until the price list is refactored into a separate module this
        method should return a list of dicts containing the raw
        information (for example as produced by a SQLAlchemy result or
        Pydantic model).  If price list integration is not yet
        implemented, this method may return an empty list.
        """