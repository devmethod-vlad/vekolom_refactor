"""
Domain entities for the contacts module.

Field names deliberately mirror the legacy Django model fields so that
Jinja2 templates can be ported from Django templates with minimal changes.

Сущности повторяют структуру Django-моделей из contacts/models.py:
    ContactInfo  — текст контактной информации (legacy table ``contacts``)
    ContactsSeo  — SEO-метаданные страницы контактов (legacy table ``contacts_contactsseo``)
    Message      — сообщение из контактной формы (legacy table ``mess_messages``)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class ContactsSeo:
    """SEO-метаданные для страницы контактов (legacy table ``contacts_contactsseo``)."""

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ContactInfo:
    """Текст контактной информации (legacy table ``contacts``).

    В Django использовался RichTextField('Текст контактов').
    ``text`` содержит HTML-разметку контактных данных.
    """

    id: int
    text: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Message:
    """Сообщение из контактной формы (legacy table ``mess_messages``).

    Соответствует модели Messages из Django-приложения mess.
    В Django view contacts() при успешной отправке формы создавалась
    запись: Messages.objects.create(name=..., phone=..., mail=..., message=...).
    """

    id: int
    name: Optional[str] = None
    mail: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
