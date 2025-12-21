"""SQLAlchemy ORM models for the home module.

These classes map the legacy Django tables used on the home page to
SQLAlchemy declarative models.

Table names are preserved exactly:
* `maincarousel`
* `maintext`
* `actions`
* `priem`
* `slogan1`
* `core_coreseo`

This greatly simplifies migration from the old database, because you can copy
data table-to-table with minimal transformations.

Extra columns
-------------
We added two generic columns to most tables:

* `sort_order` — explicit ordering for UI lists (default: 0)
* `is_active`  — soft-disable row without deleting it (default: true)

Indexes
-------
For list screens and home page rendering we almost always query:
    WHERE is_active = true
    ORDER BY sort_order, id

So we add a composite index `(is_active, sort_order, id)` for those tables.
"""

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class CoreSeo(Base):
    """SEO metadata for the home page (legacy table `core_coreseo`)."""

    __tablename__ = "core_coreseo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)


class MainCarousel(Base):
    """A slide in the home page carousel (legacy table `maincarousel`)."""

    __tablename__ = "maincarousel"

    __table_args__ = (
        Index("ix_maincarousel_active_order", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    photo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_amp: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_turbo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MainText(Base):
    """A main text block on the home page (legacy table `maintext`)."""

    __tablename__ = "maintext"

    __table_args__ = (
        Index("ix_maintext_active_order", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Action(Base):
    """An action item displayed on the home page (legacy table `actions`)."""

    __tablename__ = "actions"

    __table_args__ = (
        Index("ix_actions_active_order", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Accept(Base):
    """An item in the 'we accept' section (legacy table `priem`)."""

    __tablename__ = "priem"

    __table_args__ = (
        Index("ix_priem_active_order", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Slogan(Base):
    """A slogan associated with the home page (legacy table `slogan1`)."""

    __tablename__ = "slogan1"

    __table_args__ = (
        Index("ix_slogan1_active_order", "is_active", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
