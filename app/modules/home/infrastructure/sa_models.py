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

"""

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class CoreSeo(Base):
    """SEO metadata for the home page (legacy table `core_coreseo`)."""

    __tablename__ = "core_coreseo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_core_coreseo_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_core_coreseo_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index(
            "ix_core_coreseo_keywords_trgm",
            "keywords",
            postgresql_using="gin",
            postgresql_ops={"keywords": "gin_trgm_ops"},
        ),
    )


class MainCarousel(Base):
    """A slide in the home page carousel (legacy table `maincarousel`)."""

    __tablename__ = "maincarousel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    photo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_amp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_turbo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)

    __table_args__ = (
        Index(
            "ix_maincarousel_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


class MainText(Base):
    """A main text block on the home page (legacy table `maintext`)."""

    __tablename__ = "maintext"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_maintext_header_trgm",
            "header",
            postgresql_using="gin",
            postgresql_ops={"header": "gin_trgm_ops"},
        ),
        Index(
            "ix_maintext_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


class Action(Base):
    """An action item displayed on the home page (legacy table `actions`)."""

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_actions_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


class Priem(Base):
    """An item in the 'we accept' section (legacy table `priem`)."""

    __tablename__ = "priem"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    header: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_priem_header_trgm",
            "header",
            postgresql_using="gin",
            postgresql_ops={"header": "gin_trgm_ops"},
        ),
        Index(
            "ix_priem_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


class Slogan(Base):
    """A slogan associated with the home page (legacy table `slogan1`)."""

    __tablename__ = "slogan1"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_slogan1_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )
