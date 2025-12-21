"""
SQLAlchemy ORM models for the home module.

These classes map the legacy Django tables used on the home page to
SQLAlchemy declarative models.  The table names are preserved exactly
(``maincarousel``, ``maintext``, ``actions``, ``priem``, ``slogan1``,
and ``core_coreseo``) to simplify migrating data from the old
PostgreSQL database.  Additional columns ``sort_order`` and
``is_active`` have been added to most tables to support ordering and
soft deletion.  They default to sensible values so existing rows can
be migrated without modification.

If further performance optimisations are required you can add
SQLAlchemy indexes (``index=True``) or create raw SQL indices/triggers
in your migrations.  The models are defined here without such
optimisations to keep the ORM portable across database backends.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all declarative models in this module."""

    pass


class CoreSeo(Base):
    """
    SEO metadata for the home page.

    The legacy table ``core_coreseo`` typically holds a single row.
    There is no slug or page identifier column in the old schema.  If
    you wish to support multiple SEO records in the future consider
    adding such a column via a migration and updating the repository
    accordingly.
    """

    __tablename__ = "core_coreseo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)


class MainCarousel(Base):
    """
    A slide in the home page carousel.

    ``photo`` stores the original image path.  ``photo_webp`` stores
    the path to a WebP version of the image.  ``photo_amp`` and
    ``photo_turbo`` are reserved for alternative page versions (AMP and
    Yandex Turbo).  ``text`` contains rich text associated with the
    slide.  ``sort_order`` and ``is_active`` have been added in the
    refactored schema to control ordering and visibility.
    """

    __tablename__ = "maincarousel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    photo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_amp: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_turbo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MainText(Base):
    """
    A main text block on the home page.

    ``header`` and ``text`` map to the legacy ``header`` and ``text``
    fields.  ``sort_order`` and ``is_active`` provide additional
    control over ordering and visibility.
    """

    __tablename__ = "maintext"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Action(Base):
    """An action item displayed on the home page."""

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Accept(Base):
    """An item in the 'we accept' section of the home page."""

    __tablename__ = "priem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Slogan(Base):
    """A slogan associated with the home page."""

    __tablename__ = "slogan1"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)