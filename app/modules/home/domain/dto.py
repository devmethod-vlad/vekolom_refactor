"""
Data transfer objects for the home module.

``HomePageDTO`` mirrors the exact set of variables that the legacy Django
view passed to its template context, so that Jinja2 templates can be
ported from Django templates with the fewest possible changes:

    seo       ← CoreSeo.objects.all()[0]  (single record or None)
    slides    ← MainCarousel.objects.all()
    main      ← MainText.objects.all()
    action1   ← Actions.objects.all()[0]
    action2   ← Actions.objects.all()[1]
    action3   ← Actions.objects.all()[2]
    slogan1   ← Slogan1.objects.all()
    priem     ← Priem.objects.all()
    positions ← Position.objects.filter(check_flag=True)
"""

from dataclasses import dataclass
from typing import Optional, Sequence

from .entities import Seo, CarouselSlide, MainBlock, ActionItem, Slogan, PriemItem


@dataclass(frozen=True, slots=True)
class HomePageDTO:
    """Aggregate DTO for the home page.

    Variable names intentionally match the Django template context so the
    Jinja2 template can use the same ``{{ variable }}`` references.
    ``action1 / action2 / action3`` replace the single ``actions`` list
    that was used in an earlier version of this DTO.
    ``positions`` is kept as a list of dicts until the pricelist module is
    fully migrated; until then it will be an empty list.
    """

    seo: Optional[Seo]

    # carousel
    slides: Sequence[CarouselSlide]

    # main text blocks  (Django context key: ``main``)
    main: Sequence[MainBlock]

    # three action blocks (Django context keys: ``action1``, ``action2``, ``action3``)
    action1: Optional[ActionItem]
    action2: Optional[ActionItem]
    action3: Optional[ActionItem]

    # slogans  (Django context key: ``slogan1``)
    slogan1: Sequence[Slogan]

    # "we accept" items  (Django context key: ``priem``)
    priem: Sequence[PriemItem]

    # price list positions filtered by check_flag=True
    positions: Sequence[dict]


@dataclass(frozen=True, slots=True)
class SeoDTO:
    """Standalone SEO DTO used when only meta data is needed."""

    title: str = ""
    description: str = ""
    keywords: str = ""