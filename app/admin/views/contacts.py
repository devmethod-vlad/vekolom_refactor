"""ModelView-классы для модуля contacts.

Содержит все представления админ-панели для страницы контактов:
  - ContactsView     — управление текстом контактов (RichTextField → TinyMCE)
  - ContactsSeoView  — SEO-настройки страницы контактов
  - MessagesView     — просмотр сообщений из контактной формы

Аналог Django admin-классов из contacts/admin.py:
    admin.site.register(Contacts)
    admin.site.register(ContactsSeo)

Дополнительно добавлен MessagesView для просмотра полученных сообщений
(в Django модель Messages была зарегистрирована в отдельном приложении mess).
"""

from __future__ import annotations


from app.admin.fields import LocalTinyMCEEditorField
from app.admin.views.base import BaseAdminView
from app.modules.contacts.infrastructure.sa_models import (
    Contacts,
    ContactsSeo,
    MessMessages,
)


# ---------------------------------------------------------------------------
# Контакты (текст)
# ---------------------------------------------------------------------------


class ContactsView(BaseAdminView):
    """Управление текстом контактной информации.

    Аналог Django: admin.site.register(Contacts) — без кастомизации.
    В Django использовался RichTextField → здесь TinyMCEEditorField.

    Django verbose_name = 'Контакты'.
    """

    label = "Контакты"
    name = "Контакт"
    icon = "fa fa-address-card"

    fields = [
        "id",
        LocalTinyMCEEditorField("text", label="Текст контактов"),
    ]

    column_labels = {
        "id": "ID",
        "text": "Текст контактов",
    }


# ---------------------------------------------------------------------------
# SEO настройки контактов
# ---------------------------------------------------------------------------


class ContactsSeoView(BaseAdminView):
    """SEO-настройки страницы контактов.

    Аналог Django: admin.site.register(ContactsSeo) — без кастомизации.
    Django verbose_name = 'SEO'.
    """

    label = "SEO контактов"
    name = "SEO контактов"
    icon = "fa fa-search-plus"

    column_labels = {
        "id": "ID",
        "title": "Заголовок",
        "description": "Описание",
        "keywords": "Ключевые слова",
    }


# ---------------------------------------------------------------------------
# Сообщения из контактной формы
# ---------------------------------------------------------------------------


class MessagesView(BaseAdminView):
    """Просмотр сообщений, полученных через контактную форму.

    В Django модель Messages была в отдельном приложении mess.
    Здесь она включена в модуль contacts, т.к. логически связана
    с обработкой контактной формы.

    Только просмотр — удаление и создание через админку не предполагается,
    но оставлены доступными на случай необходимости.
    """

    label = "Сообщения"
    name = "Сообщение"
    icon = "fa fa-envelope"

    # В списке показываем все информативные колонки
    column_list = ["id", "name", "phone", "mail", "message"]

    column_labels = {
        "id": "ID",
        "name": "Имя",
        "phone": "Телефон",
        "mail": "Email",
        "message": "Сообщение",
    }
