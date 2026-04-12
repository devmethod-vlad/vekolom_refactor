"""
SQLAlchemy implementation of the contacts read and write repositories.

Field mapping from SA model columns to domain entity fields:
  Contacts.text             → ContactInfo.text
  ContactsSeo.title         → ContactsSeo.title
  ContactsSeo.description   → ContactsSeo.description
  ContactsSeo.keywords      → ContactsSeo.keywords
  MessMessages.*            → Message.*
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.domain.entities import (
    ContactInfo,
    ContactsSeo as ContactsSeoEntity,
    Message,
)
from app.modules.contacts.domain.repositories import (
    ContactsReadRepository,
    ContactsWriteRepository,
)
from .sa_models import (
    Contacts,
    ContactsSeo,
    MessMessages,
)


class SAContactsReadRepository(ContactsReadRepository):
    """SQLAlchemy-based implementation of ``ContactsReadRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # SEO  (ContactsSeo.objects.all())
    # ------------------------------------------------------------------

    async def list_seo(self) -> Sequence[ContactsSeoEntity]:
        """Return all ContactsSeo records ordered by id ascending."""
        result = await self._session.execute(
            select(ContactsSeo).order_by(ContactsSeo.id.asc())
        )
        rows: list[ContactsSeo] = list(result.scalars().all())
        return [
            ContactsSeoEntity(
                id=row.id,
                title=row.title,
                description=row.description,
                keywords=row.keywords,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Contacts  (Contacts.objects.all())
    # ------------------------------------------------------------------

    async def list_contacts(self) -> Sequence[ContactInfo]:
        """Return all contact info records ordered by id ascending."""
        result = await self._session.execute(
            select(Contacts).order_by(Contacts.id.asc())
        )
        rows: list[Contacts] = list(result.scalars().all())
        return [
            ContactInfo(
                id=row.id,
                text=row.text,
            )
            for row in rows
        ]


class SAContactsWriteRepository(ContactsWriteRepository):
    """SQLAlchemy-based implementation of ``ContactsWriteRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Messages  (Messages.objects.create(...))
    # ------------------------------------------------------------------

    async def create_message(
        self,
        *,
        name: str | None,
        phone: str | None,
        mail: str | None,
        message: str | None,
    ) -> Message:
        """Create a new contact form message and return the domain entity.

        Corresponds to ``Messages.objects.create(name=..., phone=..., mail=..., message=...)``.
        """
        obj = MessMessages(
            name=name,
            phone=phone,
            mail=mail,
            message=message,
        )
        self._session.add(obj)
        await self._session.flush()
        return Message(
            id=obj.id,
            name=obj.name,
            mail=obj.mail,
            phone=obj.phone,
            message=obj.message,
        )
