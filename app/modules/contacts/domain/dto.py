"""
Data transfer objects for the contacts module.

``ContactsPageDTO`` mirrors the exact set of variables that the legacy Django
view ``contacts(request)`` passed to its template context:

    debug_flag  ← settings.DEBUG
    seo         ← ContactsSeo.objects.all()
    contacts    ← Contacts.objects.all()
    form        ← dict (данные формы для повторного заполнения при ошибке)
    errors      ← list[str] (список ошибок валидации)
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .entities import ContactInfo, ContactsSeo


@dataclass(frozen=True, slots=True)
class ContactsPageDTO:
    """Aggregate DTO for the contacts page.

    Variable names intentionally match the Django template context so the
    Jinja2 template can use the same ``{{ variable }}`` references.
    """

    # SEO-метаданные — полный queryset (в Django: ContactsSeo.objects.all())
    seo: Sequence[ContactsSeo]

    # Тексты контактной информации (в Django: Contacts.objects.all())
    contacts: Sequence[ContactInfo]

    # Данные формы для повторного заполнения при ошибке валидации
    form: dict = field(default_factory=dict)

    # Список ошибок валидации формы
    errors: Sequence[str] = field(default_factory=list)

    # Флаг дебага из настроек
    debug_flag: bool = False
