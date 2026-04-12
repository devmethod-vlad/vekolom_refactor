"""
Domain entities for the home module.

Field names deliberately mirror the legacy Django model fields so that
Jinja2 templates can be ported from Django templates with minimal changes.
For example, ``CarouselSlide.photo`` corresponds to ``MainCarousel.photo``
and all rich-text bodies are named ``text`` (not ``text_html``) to match
the original ``RichTextField`` column names.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class Seo:
    """SEO meta information for the home page (legacy table ``core_coreseo``)."""

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CarouselSlide:
    """A single slide in the top carousel (legacy table ``maincarousel``).

    ``photo`` is the relative path to the JPEG image (e.g. ``media/foo.jpg``).
    ``photo_webp`` is the path to the WebP version generated asynchronously by
    the legacy Celery task; may be ``None`` if conversion has not finished.
    ``photo_amp`` and ``photo_turbo`` are variants used by AMP / Turbo pages.
    ``text`` contains the rich HTML caption for the slide.
    """

    id: int
    photo: Optional[str]
    photo_webp: Optional[str]
    photo_amp: Optional[str]
    photo_turbo: Optional[str]
    text: Optional[str]


@dataclass(frozen=True, slots=True)
class MainBlock:
    """A main text block on the home page (legacy table ``maintext``).

    ``header`` is the block heading; ``text`` is the rich-text body.
    """

    id: int
    header: Optional[str]
    text: Optional[str]


@dataclass(frozen=True, slots=True)
class ActionItem:
    """An action call-out (legacy table ``actions``).

    The legacy project always stored exactly three rows and accessed them
    as ``action1``, ``action2``, ``action3``.  The use case unpacks the
    list into those three separate variables before passing them to the
    template context.
    ``text`` contains the rich-text body of the action block.
    """

    id: int
    text: Optional[str]


@dataclass(frozen=True, slots=True)
class Slogan:
    """A slogan displayed on the home page (legacy table ``slogan1``).

    ``text`` may contain HTML markup.
    """

    id: int
    text: Optional[str]


@dataclass(frozen=True, slots=True)
class PriemItem:
    """An item in the 'We accept' section (legacy table ``priem``).

    ``header`` is the block heading; ``text`` is the rich-text body.
    """

    id: int
    header: Optional[str]
    text: Optional[str]