"""Shared SQLAlchemy Declarative Base.

We keep a single Declarative Base for the whole application so that Alembic can
discover ALL models across modules via one `Base.metadata`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models in the project."""

    pass
