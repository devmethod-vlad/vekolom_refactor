"""ModelView-классы для модуля home.

Содержит все представления админ-панели для домашней страницы:
  - MainCarouselView  — управление слайдами карусели (фото + превью)
  - CoreSeoView       — SEO-настройки
  - MainTextView      — основной текстовый блок (RichTextUploadingField → TinyMCE с загрузкой)
  - ActionView        — блоки действий (RichTextField → TinyMCE без загрузки)
  - SloganView        — слоганы
  - PriemView         — блок «Мы принимаем»

Аналог Django admin-классов из core/admin.py + core/models.py:
    admin.site.register(MainCarousel, CarouselAdmin)
    admin.site.register(CoreSeo)
    admin.site.register(MainText)
    admin.site.register(Actions)
    admin.site.register(Priem)
    admin.site.register(Slogan1)
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from app.admin.utils.photo_upload import handle_photo_upload
from app.admin.fields import AdminImageField, LocalTinyMCEEditorField, RichTextUploadField
from app.admin.views.base import BaseAdminView
from app.infrastructure.media.image_processor import save_carousel_photo_sync
from app.infrastructure.celery.tasks import slide_to_webp
from app.modules.home.infrastructure.sa_models import (
    CoreSeo,
    MainCarousel,
    MainText,
    Action,
    Priem,
    Slogan,
)


# ---------------------------------------------------------------------------
# Карусель
# ---------------------------------------------------------------------------


class MainCarouselView(BaseAdminView):
    """Управление слайдами карусели с превью и загрузкой фото.

    Аналог CarouselAdmin из Django core/models.py:
        list_display = ('__str__', 'admin_thumbnail')
        exclude      = ('photo_low', 'photo_webp')
        admin_thumbnail = AdminThumbnail(image_field='avatarimage')

    Дополнительно:
        - При сохранении фото обрабатывается через ResizeToFill(2050×544).
        - После сохранения запускается задача slide_to_webp(slide_id, photo_path).
        - Валидация загрузки: формат, размер, длина имени файла — из .env.

    AdminImageField вместо стандартного ImageField:
        Стандартный ImageField ломается в list-рендерере (new URL() на
        относительном пути). AdminImageField строит абсолютный URL
        через request.base_url — валидный для new URL().
    """

    label = "Карусель"
    name = "Слайд карусели"
    icon = "fa fa-images"

    # Колонки в списке — аналог list_display
    column_list = ["id", "photo", "text"]

    # Поля в форме создания/редактирования
    # AdminImageField — рендерит поле как загрузку файла + абсолютный URL для превью
    # photo_webp, photo_amp, photo_turbo заполняются автоматически (Celery / AMP)
    fields = [
        "id",
        AdminImageField("photo", label="Фото для карусели"),
        LocalTinyMCEEditorField("text", label="Текст слайда"),
        "photo_webp",
        "photo_amp",
        "photo_turbo",
    ]

    # Скрытие автоматически заполняемых полей из форм
    form_include_pk = False
    exclude_fields_from_create = ["photo_webp", "photo_amp", "photo_turbo"]
    exclude_fields_from_edit = ["photo_webp", "photo_amp", "photo_turbo"]
    exclude_fields_from_list = ["photo_webp", "photo_amp", "photo_turbo"]
    exclude_fields_from_detail = []

    column_labels = {
        "id": "ID",
        "photo": "Фото для карусели",
        "text": "Текст слайда",
        "photo_amp": "Фото (AMP)",
        "photo_turbo": "Фото (Турбо)",
        "photo_webp": "Фото (WebP, авто)",
    }

    # ------------------------------------------------------------------
    # Обработка загрузки фото (универсальная функция с валидацией)
    # ------------------------------------------------------------------

    async def before_create(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженный файл фото при создании слайда."""
        await handle_photo_upload(
            data=data,
            field_name="photo",
            save_fn=save_carousel_photo_sync,
            # Можно переопределить ограничения из .env:
            # allowed_formats=["jpeg", "jpg"],
            # max_size_mb=5,
        )

    async def before_edit(self, request: Request, data: dict, obj: Any) -> None:
        """Обрабатывает загруженный файл фото при редактировании слайда."""
        await handle_photo_upload(
            data=data,
            field_name="photo",
            save_fn=save_carousel_photo_sync,
        )

    # ------------------------------------------------------------------
    # Запуск Celery-задачи после сохранения
    # Аналог @receiver(post_save, sender=MainCarousel) из Django
    # ------------------------------------------------------------------

    async def after_create(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после создания слайда."""
        if obj.photo:
            slide_to_webp.delay(obj.id, obj.photo)

    async def after_edit(self, request: Request, obj: Any) -> None:
        """Запускает конвертацию в WebP после редактирования (если фото изменилось)."""
        if obj.photo:
            slide_to_webp.delay(obj.id, obj.photo)


# ---------------------------------------------------------------------------
# SEO
# ---------------------------------------------------------------------------


class CoreSeoView(BaseAdminView):
    """SEO-настройки сайта."""

    label = "SEO настройки"
    name = "SEO"
    icon = "fa fa-search"
    column_labels = {
        "id": "ID",
        "title": "Заголовок",
        "description": "Описание",
        "keywords": "Ключевые слова",
    }


# ---------------------------------------------------------------------------
# Основной текст (с загрузкой изображений в редакторе)
# ---------------------------------------------------------------------------


class MainTextView(BaseAdminView):
    """Основной текстовый блок на главной странице.

    В Django использовался RichTextUploadingField — редактор CKEditor
    с возможностью загрузки изображений внутрь контента.
    Здесь используется RichTextUploadField — TinyMCE с images_upload_url.
    """

    label = "Основной текст"
    name = "Текстовый блок"
    icon = "fa fa-align-left"

    fields = [
        "id",
        "header",
        RichTextUploadField("text", label="Текст"),
    ]

    column_labels = {
        "id": "ID",
        "header": "Заголовок",
        "text": "Текст",
    }


# ---------------------------------------------------------------------------
# Блоки действий (простой rich text)
# ---------------------------------------------------------------------------


class ActionView(BaseAdminView):
    """Блоки действий на главной странице.

    В Django использовался RichTextField — редактор CKEditor без загрузки
    изображений. Здесь используется TinyMCEEditorField.
    """

    label = "Блоки действий"
    name = "Блок действий"
    icon = "fa fa-bolt"

    fields = [
        "id",
        LocalTinyMCEEditorField("text", label="Текст"),
    ]

    column_labels = {
        "id": "ID",
        "text": "Текст",
    }


# ---------------------------------------------------------------------------
# Слоганы (простой rich text)
# ---------------------------------------------------------------------------


class SloganView(BaseAdminView):
    """Слоганы на главной странице.

    В Django использовался RichTextField. Здесь — TinyMCEEditorField.
    """

    label = "Слоганы"
    name = "Слоган"
    icon = "fa fa-quote-left"

    fields = [
        "id",
        LocalTinyMCEEditorField("text", label="Текст"),
    ]

    column_labels = {
        "id": "ID",
        "text": "Текст",
    }


# ---------------------------------------------------------------------------
# Мы принимаем (простой rich text)
# ---------------------------------------------------------------------------


class PriemView(BaseAdminView):
    """Блок «Мы принимаем».

    В Django использовался RichTextField. Здесь — TinyMCEEditorField.
    """

    label = "Мы принимаем"
    name = "Пункт приёма"
    icon = "fa fa-recycle"

    fields = [
        "id",
        "header",
        LocalTinyMCEEditorField("text", label="Текст"),
    ]

    column_labels = {
        "id": "ID",
        "header": "Заголовок",
        "text": "Текст",
    }
