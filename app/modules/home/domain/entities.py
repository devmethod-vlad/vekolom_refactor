"""
Domain entities for the home module.

These dataclasses represent the core business objects used on the
project's home page.  They are deliberately simple and free of any
infrastructure‑specific concerns (such as SQLAlchemy, FastAPI, or Jinja2).
Each entity mirrors one of the tables from the legacy Django project but
adds optional ``sort_order`` and ``is_active`` fields to make it easy to
control ordering and visibility of items in the future.  The ``id``
attribute allows admin interfaces to reference the objects without
leaking database details into higher layers of the application.

Adding ``sort_order`` and ``is_active`` does not break migration from
the old database because default values are supplied and existing data
will map cleanly to the new schema.  Should these additional fields not
be required, they can simply remain at their defaults.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class Seo:
    """Search engine optimisation meta information for the home page."""

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CarouselSlide:
    """A single slide in the top carousel on the home page.

    ``image_path`` is the URL or relative path to the original image.
    ``image_webp_path`` stores a WebP version of the same image (if
    available).  ``text_html`` contains any rich HTML caption for the
    slide.  ``sort_order`` defines the order in which slides appear and
    ``is_active`` allows a slide to be hidden without deleting it from
    the database.
    """

    id: int
    image_path: Optional[str]
    image_webp_path: Optional[str]
    text_html: Optional[str]
    sort_order: int = 0
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class MainBlock:
    """The main text block displayed on the home page.

    Multiple instances are permitted; ``sort_order`` controls their
    ordering when more than one record exists.  ``is_active`` can be
    toggled to hide a block from the page without removing it from
    storage.  ``header`` and ``text_html`` correspond to the title and
    rich text body from the old ``MainText`` model.
    """

    id: int
    header: Optional[str]
    text_html: Optional[str]
    sort_order: int = 0
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ActionItem:
    """An action call‑out displayed beneath the main block.

    The legacy project always displayed exactly three actions.  In the
    new architecture we treat the number of actions as flexible; the
    presentation layer can decide how many to show.  ``text_html``
    contains rich text for the action, ``sort_order`` controls the
    display order, and ``is_active`` allows hiding items without
    deletion.
    """

    id: int
    text_html: Optional[str]
    sort_order: int = 0
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Slogan:
    """A short slogan displayed on the home page.

    ``text_html`` may include HTML markup (for example line breaks).
    ``sort_order`` and ``is_active`` have the same semantics as in
    ``CarouselSlide``.
    """

    id: int
    text_html: Optional[str]
    sort_order: int = 0
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class AcceptItem:
    """An item in the 'We accept' list on the home page.

    ``header`` corresponds to the heading of the accept block and
    ``text_html`` contains its description.  Items are ordered via
    ``sort_order`` and can be toggled via ``is_active``.
    """

    id: int
    header: Optional[str]
    text_html: Optional[str]
    sort_order: int = 0
    is_active: bool = True