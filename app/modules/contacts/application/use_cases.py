"""
Application layer use cases for the contacts module.

``GetContactsPage`` replicates the data-fetching logic of the legacy
Django view ``contacts(request)`` from contacts/views.py:

    seo      = ContactsSeo.objects.all()
    contacts = Contacts.objects.all()

``SubmitContactForm`` handles the form POST logic:

    if not form['phone'] or not form['mail']:
        errors.append('Оставьте свой телефон или email')
    if not form['message']:
        errors.append('С каким вопросом вы к нам обратились?')
    if not errors:
        Messages.objects.create(name=..., phone=..., mail=..., message=...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.contacts.domain.dto import ContactsPageDTO
from app.settings.config import settings


class GetContactsPage:
    """Use case for assembling the contacts page data (GET request)."""

    async def execute(self, uow: AsyncUnitOfWork) -> ContactsPageDTO:
        """Fetch all data for the contacts page within a single unit of work.

        The returned ``ContactsPageDTO`` uses the same field names as the
        Django template context so that the Jinja2 template can be ported
        with minimal changes.
        """
        async with uow:
            seo = await uow.contacts.list_seo()
            contacts = await uow.contacts.list_contacts()

        return ContactsPageDTO(
            seo=seo,
            contacts=contacts,
            debug_flag=settings.app.DEBUG,
        )


@dataclass(frozen=True, slots=True)
class ContactFormData:
    """Данные контактной формы, извлечённые из POST-запроса."""

    name: Optional[str] = None
    phone: Optional[str] = None
    mail: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SubmitFormResult:
    """Результат обработки контактной формы.

    ``success`` — True, если сообщение успешно сохранено.
    ``errors``  — список ошибок валидации (пустой при успехе).
    ``form``    — данные формы для повторного заполнения при ошибке.
    """

    success: bool
    errors: list[str]
    form: dict


class SubmitContactForm:
    """Use case for processing the contact form submission (POST request).

    Повторяет логику валидации из legacy Django view:
      - Телефон или email обязательны.
      - Текст сообщения обязателен.

    Проверка SmartCaptcha выполняется в presentation-слое (router.py)
    ДО вызова этого use case. Это разделение ответственности:
    капча — инфраструктурная HTTP-проверка, а не бизнес-правило.
    """

    async def execute(
        self,
        uow: AsyncUnitOfWork,
        form_data: ContactFormData,
    ) -> SubmitFormResult:
        """Validate and save the contact form message.

        Returns ``SubmitFormResult`` with ``success=True`` if message was saved,
        or ``success=False`` with validation errors and form data for re-display.
        """
        form = {
            "name": form_data.name or "",
            "phone": form_data.phone or "",
            "mail": form_data.mail or "",
            "message": form_data.message or "",
        }

        errors: list[str] = []

        # Валидация — аналог Django view:
        # if not form['phone'] or not form['mail']:
        #     errors.append('Оставьте свой телефон или email')
        if not form_data.phone and not form_data.mail:
            errors.append("Оставьте свой телефон или email")

        # if not form['message']:
        #     errors.append('С каким вопросом вы к нам обратились?')
        if not form_data.message:
            errors.append("С каким вопросом вы к нам обратились?")

        if errors:
            return SubmitFormResult(success=False, errors=errors, form=form)

        # Сохранение сообщения — аналог Django view:
        # Messages.objects.create(name=..., phone=..., mail=..., message=...)
        async with uow:
            await uow.contacts_write.create_message(
                name=form_data.name,
                phone=form_data.phone,
                mail=form_data.mail,
                message=form_data.message,
            )

        return SubmitFormResult(success=True, errors=[], form=form)
