"""
Repository protocols for the contacts module.

Method names mirror the Django ORM calls used in the legacy view so it is
easy to verify that every queryset has a counterpart here:

    list_seo()       ← ContactsSeo.objects.all()
    list_contacts()  ← Contacts.objects.all()
    create_message() ← Messages.objects.create(name=..., phone=..., mail=..., message=...)
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .entities import ContactInfo, ContactsSeo, Message


class ContactsReadRepository(Protocol):
    """Protocol describing all read operations needed by the contacts use cases."""

    async def list_seo(self) -> Sequence[ContactsSeo]:
        """Return all ContactsSeo records.

        Corresponds to ``ContactsSeo.objects.all()``.
        """

    async def list_contacts(self) -> Sequence[ContactInfo]:
        """Return all contact info records ordered by ``id`` ascending.

        Corresponds to ``Contacts.objects.all()``.
        """


class ContactsWriteRepository(Protocol):
    """Protocol describing write operations for the contacts module."""

    async def create_message(
        self,
        *,
        name: str | None,
        phone: str | None,
        mail: str | None,
        message: str | None,
    ) -> Message:
        """Create a new contact form message.

        Corresponds to ``Messages.objects.create(name=..., phone=..., mail=..., message=...)``.
        """
