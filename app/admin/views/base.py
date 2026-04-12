"""Общие базовые классы и helpers для админских ModelView.

Зачем файл нужен
----------------
Ранее в каждом модуле админки (`home.py`, `pricelist.py`, `contacts.py`)
дублировался собственный `BaseAdminView`. Это неудобно по двум причинам:

1. Любое изменение общего поведения приходилось копировать в несколько файлов.
2. Было легко пропустить мелкую, но неприятную ошибку в одном из модулей.

Этот модуль собирает общую логику в одном месте.
"""

from __future__ import annotations

from typing import Any, Iterable

from starlette_admin.contrib.sqla import ModelView
from starlette_admin.fields import BaseField

from app.admin.fields import ADMIN_CUSTOM_JS_URL


class BaseAdminView(ModelView):
    """Общий базовый класс для всех SQLAlchemy ModelView проекта.

    Что делает:
      - Подключает общий кастомный JS для админки.
      - Сохраняет `icon`, заданный как атрибут класса view.
      - Применяет `column_labels` не только в списке, но и к form/detail fields.

    Почему понадобилось отдельное сохранение `icon`
    -----------------------------------------------
    В `starlette-admin` конструктор `ModelView(..., icon=...)` в конце просто делает
    `self.icon = icon`. Если view создаётся как `MyView(MyModel)` без явного аргумента
    `icon=...`, то значение class-attribute (`icon = "fa ..."`) перетирается на `None`.
    Из-за этого иконки у внутренних пунктов меню тихо исчезают.
    """

    additional_js_links = [ADMIN_CUSTOM_JS_URL]
    column_labels: dict[str, str] = {}

    def __init__(
        self,
        model: Any,
        icon: str | None = None,
        name: str | None = None,
        label: str | None = None,
        identity: str | None = None,
        converter: Any | None = None,
    ) -> None:
        resolved_icon = icon if icon is not None else getattr(type(self), "icon", None)
        super().__init__(
            model,
            icon=resolved_icon,
            name=name,
            label=label,
            identity=identity,
            converter=converter,
        )
        self._apply_column_labels()

    def _apply_column_labels(self) -> None:
        """Применяет `column_labels` к уже сконвертированным starlette-admin field'ам.

        В `starlette-admin` рендер списков/форм/деталей опирается на `field.label`.
        Поэтому одного словаря `column_labels` недостаточно, если поля были построены
        из строковых имён модели. Здесь мы централизованно переносим подписи из
        `column_labels` в реальные Field-объекты.
        """
        if not self.column_labels:
            return

        for field in self._iter_fields(self.fields):
            label = self.column_labels.get(field.name)
            if label:
                field.label = label

    def _iter_fields(self, fields: Iterable[Any]) -> Iterable[BaseField]:
        """Рекурсивно проходит по плоскому и вложенному списку field-объектов."""
        for field in fields:
            if isinstance(field, BaseField):
                yield field
                nested = getattr(field, "fields", None)
                if nested:
                    yield from self._iter_fields(nested)
