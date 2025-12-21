"""
Data transfer objects for the home module.

The DTO layer defines simple containers used to transfer data out of
the application layer.  DTOs decouple the domain entities from
presentation formats (HTML/JSON) and can be easily serialised or
transformed for different consumers.  ``HomePageDTO`` aggregates all
components of the home page into a single object, while ``SeoDTO``
exposes only the search meta information when needed separately.
"""

from dataclasses import dataclass
from typing import Sequence

from .entities import Seo, CarouselSlide, MainBlock, ActionItem, Slogan, AcceptItem


@dataclass(frozen=True, slots=True)
class HomePageDTO:
    """Aggregate DTO for the home page.

    Each attribute corresponds to a group of records from the database.
    ``positions`` remains a list of dictionaries for now because the
    price list has not yet been extracted into its own module.  Once
    that happens a dedicated DTO should replace the loose dict type.
    """

    seo: Seo | None
    slides: Sequence[CarouselSlide]
    main_blocks: Sequence[MainBlock]
    actions: Sequence[ActionItem]
    slogans: Sequence[Slogan]
    accept_items: Sequence[AcceptItem]
    positions: Sequence[dict]


@dataclass(frozen=True, slots=True)
class SeoDTO:
    """Standalone SEO DTO used when only meta data is needed."""

    title: str = ""
    description: str = ""
    keywords: str = ""