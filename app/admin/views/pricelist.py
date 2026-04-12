"""ModelView-классы для модуля pricelist.

Содержит все представления админ-панели для прайс-листа:
  - CategoryView     — управление категориями
  - PositionView     — управление позициями (фото + цены)
  - FotoView         — фотографии к позициям (фото + превью)
  - PriceDateView    — дата прайс-листа
  - PricelistSeoView — SEO-настройки страницы прайс-листа

Аналог Django admin-классов из pricelist/admin.py + pricelist/models.py:
    admin.site.register(Position, PositionAdmin)
    admin.site.register(Category)
    admin.site.register(PricelistSeo)
    admin.site.register(Foto, FotoAdmin)
    admin.site.register(PriceDate)
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from app.admin.utils.photo_upload import handle_photo_upload
from app.admin.fields import AdminImageField, LocalTinyMCEEditorField, RichTextUploadField
from app.admin.views.base import BaseAdminView
from app.infrastructure.media.image_processor import save_position_photo_sync
from app.infrastructure.celery.tasks import position_photo_to_webp, foto_to_webp
from app.modules.pricelist.infrastructure.sa_models import (
    Category,
    Foto,
    Position,
    PriceDate,
    PricelistSeo,
)


# ---------------------------------------------------------------------------
# Категории
# ---------------------------------------------------------------------------


class CategoryView(BaseAdminView):
    """Управление категориями прайс-листа.

    Аналог Django: admin.site.register(Category) — без кастомизации,
    стандартное отображение всех полей.
    description использует RichTextUploadingField → RichTextUploadField.
    """

    label = "Категории"
    name = "Категория"
    icon = "fa fa-folder-open"

    fields = [
        "id",
        "name",
        RichTextUploadField("description", label="Описание категории"),
    ]

    column_labels = {
        "id": "ID",
        "name": "Название категории",
        "description": "Описание категории",
    }

    # Скрываем связь positions из формы — она управляется через PositionView
    exclude_fields_from_create = ["positions"]
    exclude_fields_from_edit = ["positions"]
    exclude_fields_from_list = ["positions"]


# ---------------------------------------------------------------------------
# Позиции
# ---------------------------------------------------------------------------


class PositionView(BaseAdminView):
    """Управление позициями прайс-листа с фото и ценами.

    Аналог Django PositionAdmin из pricelist/models.py:
        list_display = ('name', 'price', 'check_flag')
        list_per_page = 20
        exclude = ('photo2_low', 'photo2_webp', 'avatar_webp')
        ordering = ['order']
        fieldsets = [
            (None, {'fields': [
                'name', 'price_title', 'price', 'price_card_title', 'price_card',
                'price2_card_title', 'price2_card', 'price2_title', 'price_2',
                'price3_title', 'price_3', 'description', 'rules', 'check_flag',
                'photo2', 'category', 'order', 'foto_app', 'foto_rss',
            ]}),
        ]

    Дополнительно:
        - При сохранении фото (photo2) запускается Celery-задача position_photo_to_webp.
        - photo2_webp / avatar_webp заполняются автоматически.
    """

    label = "Позиции"
    name = "Позиция"
    icon = "fa fa-list-alt"

    page_size = 20

    # Колонки в списке — аналог list_display
    column_list = ["id", "name", "price", "check_flag"]

    # Поля формы — порядок как в Django fieldsets
    fields = [
        "id",
        "name",
        "price_title",
        "price",
        "price_card_title",
        "price_card",
        "price2_card_title",
        "price2_card",
        "price2_title",
        "price_2",
        "price3_title",
        "price_3",
        RichTextUploadField("description", label="Описание позиции"),
        LocalTinyMCEEditorField("rules", label="Требования к приемке"),
        "check_flag",
        AdminImageField("photo2", label="Фото для главной"),
        "category",
        "order",
        AdminImageField("foto_app", label="Фото для мобильного приложения"),
        AdminImageField("foto_rss", label="Фото yandexturbo"),
        # Автоматические поля (read-only)
        "photo2_webp",
        "avatar_webp",
    ]

    # Скрытие автоматически заполняемых полей из форм — аналог exclude
    form_include_pk = False
    exclude_fields_from_create = ["photo2_webp", "avatar_webp", "fotos"]
    exclude_fields_from_edit = ["photo2_webp", "avatar_webp", "fotos"]
    exclude_fields_from_list = [
        "photo2_webp", "avatar_webp", "description", "rules",
        "price_title", "price_card_title", "price2_card_title",
        "price2_title", "price3_title", "price_2", "price_3",
        "price_card", "price2_card", "title", "seodescrip", "keywords",
        "photo2", "foto_app", "foto_rss", "order", "category",
        "category_id", "fotos",
    ]
    exclude_fields_from_detail = []

    # SEO-поля позиции скрыты из форм создания/редактирования,
    # т.к. в Django fieldsets их не было (они из PositionAdmin exclude)
    # Но мы их оставим доступными — могут пригодиться.

    column_labels = {
        "id": "ID",
        "name": "Наименование позиции",
        "description": "Описание позиции",
        "rules": "Требования к приемке",
        "title": "SEO-title",
        "seodescrip": "SEO-description",
        "keywords": "SEO-keywords",
        "check_flag": "Показывать на главной",
        "order": "Порядок следования в прайсе",
        "price_title": "Лейбл цены (На карту физ.лица)",
        "price": "Цена (На карту физ.лица)",
        "price2_title": "Лейбл второй цены (На карту физ.лица)",
        "price_2": "Вторая цена (На карту физ.лица)",
        "price3_title": "Лейбл третьей цены (На карту физ.лица)",
        "price_3": "Третья цена (На карту физ.лица)",
        "price_card_title": "Лейбл цены (Лицензия юр.лица)",
        "price_card": "Цена (Лицензия юр.лица)",
        "price2_card_title": "Лейбл второй цены (Лицензия юр.лица)",
        "price2_card": "Вторая цена (Лицензия юр.лица)",
        "photo2": "Фото для главной",
        "photo2_webp": "Фото (WebP, авто)",
        "avatar_webp": "Аватар (WebP, авто)",
        "foto_app": "Фото для мобильного приложения",
        "foto_rss": "Фото yandexturbo",
        "category": "Категория",
        "category_id": "Категория",
    }

    # ------------------------------------------------------------------
    # Обработка загрузки фото
    # ------------------------------------------------------------------

    async def before_create(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженные файлы фото при создании позиции."""
        await handle_photo_upload(
            data=data,
            field_name="photo2",
            save_fn=save_position_photo_sync,
        )
        await handle_photo_upload(
            data=data,
            field_name="foto_app",
            save_fn=save_position_photo_sync,
        )
        await handle_photo_upload(
            data=data,
            field_name="foto_rss",
            save_fn=save_position_photo_sync,
        )

    async def before_edit(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженные файлы фото при редактировании позиции."""
        await handle_photo_upload(
            data=data,
            field_name="photo2",
            save_fn=save_position_photo_sync,
        )
        await handle_photo_upload(
            data=data,
            field_name="foto_app",
            save_fn=save_position_photo_sync,
        )
        await handle_photo_upload(
            data=data,
            field_name="foto_rss",
            save_fn=save_position_photo_sync,
        )

    # ------------------------------------------------------------------
    # Запуск Celery-задачи после сохранения
    # Аналог @receiver(post_save, sender=Position) из Django
    # ------------------------------------------------------------------

    async def after_create(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после создания позиции."""
        if obj.photo2:
            position_photo_to_webp.delay(obj.id, obj.photo2)

    async def after_edit(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после редактирования (если фото изменилось)."""
        if obj.photo2:
            position_photo_to_webp.delay(obj.id, obj.photo2)


# ---------------------------------------------------------------------------
# Фотографии к позициям
# ---------------------------------------------------------------------------


class FotoView(BaseAdminView):
    """Управление фотографиями к позициям прайс-листа.

    Аналог Django FotoAdmin из pricelist/models.py:
        list_display = ('__str__', 'admin_thumbnail')
        exclude = ('foto_low', 'foto_webp')
        list_per_page = 20
        admin_thumbnail = AdminThumbnail(image_field='avatarfoto')
    """

    label = "Фото прайса"
    name = "Фото"
    icon = "fa fa-camera"

    page_size = 20

    # Колонки в списке
    column_list = ["id", "foto", "text", "position"]

    # Поля формы
    fields = [
        "id",
        AdminImageField("foto", label="Фото для прайса"),
        "text",
        "position",
        "foto_webp",
    ]

    # Скрытие автоматически заполняемых полей
    form_include_pk = False
    exclude_fields_from_create = ["foto_webp"]
    exclude_fields_from_edit = ["foto_webp"]
    exclude_fields_from_list = ["foto_webp"]
    exclude_fields_from_detail = []

    column_labels = {
        "id": "ID",
        "foto": "Фото для прайса",
        "foto_webp": "Фото (WebP, авто)",
        "text": "Подпись к фото",
        "position": "Позиция",
        "position_id": "Позиция",
    }

    # ------------------------------------------------------------------
    # Обработка загрузки фото
    # ------------------------------------------------------------------

    async def before_create(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженный файл фото при создании."""
        await handle_photo_upload(
            data=data,
            field_name="foto",
            save_fn=save_position_photo_sync,
        )

    async def before_edit(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженный файл фото при редактировании."""
        await handle_photo_upload(
            data=data,
            field_name="foto",
            save_fn=save_position_photo_sync,
        )

    # ------------------------------------------------------------------
    # Запуск Celery-задачи после сохранения
    # Аналог @receiver(post_save, sender=Foto) из Django
    # ------------------------------------------------------------------

    async def after_create(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после создания фото."""
        if obj.foto:
            foto_to_webp.delay(obj.id, obj.foto)

    async def after_edit(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после редактирования (если фото изменилось)."""
        if obj.foto:
            foto_to_webp.delay(obj.id, obj.foto)


# ---------------------------------------------------------------------------
# Дата прайс-листа
# ---------------------------------------------------------------------------


class PriceDateView(BaseAdminView):
    """Управление датой прайс-листа.

    Аналог Django: admin.site.register(PriceDate) — без кастомизации.
    """

    label = "Дата прайса"
    name = "Дата прайса"
    icon = "fa fa-calendar"

    column_labels = {
        "id": "ID",
        "date": "Дата прайса",
    }


# ---------------------------------------------------------------------------
# SEO настройки прайс-листа
# ---------------------------------------------------------------------------


class PricelistSeoView(BaseAdminView):
    """SEO-настройки страницы прайс-листа.

    Аналог Django: admin.site.register(PricelistSeo) — без кастомизации.
    """

    label = "SEO прайс-листа"
    name = "SEO прайс-листа"
    icon = "fa fa-search-plus"

    column_labels = {
        "id": "ID",
        "title": "Заголовок",
        "description": "Описание",
        "keywords": "Ключевые слова",
    }
