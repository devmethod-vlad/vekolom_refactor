"""Кастомные поля для starlette-admin.

AdminImageField         — ImageField с корректным абсолютным URL для отображения
                          превью. Решает проблему «Failed to construct URL» в списке
                          и пустого src на странице деталей.
LocalTinyMCEEditorField — TinyMCE с локальными JS-ассетами и конфигурацией из .env.
RichTextUploadField     — TinyMCE с локальными ассетами + загрузкой изображений
                          в контент.

Сравнение с Django:
    ProcessedImageField      → AdminImageField (загрузка + превью)
    RichTextField            → LocalTinyMCEEditorField (без загрузки изображений)
    RichTextUploadingField   → RichTextUploadField (с загрузкой изображений)
"""

from __future__ import annotations

import mimetypes
import os
from typing import Any

from starlette_admin import ImageField, TinyMCEEditorField

from app.settings.config import settings


# ---------------------------------------------------------------------------
# URL-ы для служебных admin-эндпоинтов.
# Роуты монтируются ВОВНЕ /admin, чтобы не конфликтовать с admin sub-app mount.
# ---------------------------------------------------------------------------
TINYMCE_UPLOAD_URL = "/api/admin/tinymce-upload"

# URL для кастомного JS (сайдбар, превью при редактировании, иконки в submenu)
ADMIN_CUSTOM_JS_URL = "/api/admin/custom.js"


# ---------------------------------------------------------------------------
# TinyMCE helpers
# ---------------------------------------------------------------------------


def _join_url(base: str, *parts: str) -> str:
    """Аккуратно склеивает URL-фрагменты без двойных слэшей."""
    normalized = [base.rstrip("/")]
    normalized.extend(part.strip("/") for part in parts if part)
    return "/".join(normalized)


class LocalTinyMCEEditorField(TinyMCEEditorField):
    """TinyMCE-редактор с локальными JS-ассетами и конфигурацией из .env.

    Почему отдельное поле
    ---------------------
    Базовый `starlette_admin.TinyMCEEditorField` по умолчанию подтягивает
    `tinymce.min.js` и `tinymce-jquery.min.js` с CDN. Для проекта удобнее
    self-hosted вариант:
      - админка не зависит от внешнего CDN;
      - можно фиксировать конкретную сборку TinyMCE у себя в репозитории;
      - набор toolbar/plugins можно централизованно регулировать через .env.

    По умолчанию поле использует настройки из `settings.admin_tinymce`, но при
    необходимости отдельный view может передать свои overrides прямо в конструктор.
    """

    def __init__(
        self,
        name: str,
        *,
        label: str = "",
        enable_image_upload: bool = False,
        toolbar: str | None = None,
        plugins: str | None = None,
        menubar: bool | str | None = None,
        statusbar: bool | None = None,
        height: int | None = None,
        extra_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tinymce_settings = settings.admin_tinymce

        resolved_plugins = plugins or tinymce_settings.PLUGINS
        if enable_image_upload and "image" not in resolved_plugins.split():
            resolved_plugins = f"{resolved_plugins} image".strip()

        resolved_extra_options = {
            "plugins": resolved_plugins,
            **tinymce_settings.extra_options,
            **(extra_options or {}),
        }

        if enable_image_upload:
            resolved_extra_options = {
                **resolved_extra_options,
                "images_upload_url": TINYMCE_UPLOAD_URL,
                "automatic_uploads": True,
                "images_reuse_filename": False,
                "file_picker_types": "image",
                "image_title": True,
            }

        super().__init__(
            name,
            label=label,
            height=height if height is not None else tinymce_settings.HEIGHT,
            menubar=menubar if menubar is not None else tinymce_settings.MENUBAR,
            statusbar=statusbar if statusbar is not None else tinymce_settings.STATUSBAR,
            toolbar=toolbar if toolbar is not None else tinymce_settings.TOOLBAR,
            content_style=tinymce_settings.CONTENT_STYLE,
            extra_options=resolved_extra_options,
            **kwargs,
        )
        self._enable_image_upload = enable_image_upload

    def additional_js_links(self, request: Any, action: Any = None) -> list[str]:
        """Подключает локальные TinyMCE-скрипты вместо CDN."""
        if action is not None and hasattr(action, "is_form") and not action.is_form():
            return []

        assets_url = settings.admin_tinymce.ASSETS_URL.rstrip("/")
        return [
            _join_url(assets_url, settings.admin_tinymce.TINYMCE_JS_PATH),
            _join_url(assets_url, settings.admin_tinymce.TINYMCE_JQUERY_JS_PATH),
        ]


# ---------------------------------------------------------------------------
# AdminImageField — ImageField с абсолютным URL
# ---------------------------------------------------------------------------


class AdminImageField(ImageField):
    """ImageField, совместимый с форматом данных starlette-admin.

    Почему понадобилось своё поле
    ------------------------------
    В legacy-базе Django в поле ``photo`` хранится обычная строка:
        ``media/<filename>.jpg``

    Но starlette-admin для ``ImageField`` ожидает уже не строку, а объект вида:
        ``{"url": "https://...", "filename": "file.jpg", "content_type": "image/jpeg"}``

    Его фронтенд (`render.js`) при рендере списка делает вызов ``new URL(d.url)``.
    Если вернуть строку вместо объекта, ``d.url`` становится ``undefined`` и
    браузер падает с ошибкой ``Failed to construct 'URL': Invalid URL``.

    Поэтому здесь мы:
      1. Преобразуем строковый путь из БД в абсолютный URL.
      2. Возвращаем словарь в формате, который ожидает starlette-admin.

    Дополнительный бонус: тот же формат используется и на странице редактирования,
    поэтому встроенное превью текущего изображения начинает работать без костылей.

    Параметры:
        media_prefix — URL-префикс медиафайлов (по умолчанию '/media/').
    """

    def __init__(
        self,
        *args: Any,
        media_prefix: str = "/media/",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._media_prefix = media_prefix.rstrip("/")

    def _build_absolute_url(self, request: Any, value: str) -> str:
        """Строит абсолютный URL к медиафайлу.

        Примеры преобразований (при base_url=http://127.0.0.1:8001):
            'media/slide.jpg'   → 'http://127.0.0.1:8001/media/media/slide.jpg'
            '/media/slide.jpg'  → 'http://127.0.0.1:8001/media/slide.jpg'
            'https://cdn/1.jpg' → 'https://cdn/1.jpg'
        """
        base_url = str(request.base_url).rstrip("/")

        if value.startswith(("http://", "https://")):
            return value
        if value.startswith("/"):
            return f"{base_url}{value}"
        return f"{base_url}{self._media_prefix}/{value.lstrip('/')}"

    def _build_file_payload(self, request: Any, value: str) -> dict[str, str]:
        """Преобразует строковый путь из БД в payload формата FileField/ImageField."""
        filename = os.path.basename(value.lstrip("/")) or "image"
        content_type = mimetypes.guess_type(filename)[0] or "image/*"
        return {
            "url": self._build_absolute_url(request, value),
            "filename": filename,
            "content_type": content_type,
        }

    async def serialize_value(
        self,
        request: Any,
        value: Any,
        action: Any,
    ) -> Any:
        """Сериализует значение для list/detail/edit/create API starlette-admin.

        Поддерживаем несколько вариантов входных данных:
          - строка из legacy-БД;
          - словарь формата FileField/ImageField;
          - объект с атрибутом ``url`` (на случай будущих расширений).
        """
        if not value:
            return await super().serialize_value(request, value, action)

        if isinstance(value, str):
            value = self._build_file_payload(request, value)
        elif isinstance(value, dict) and value.get("url"):
            if isinstance(value["url"], str):
                value = {
                    **value,
                    "url": self._build_absolute_url(request, value["url"]),
                    "filename": value.get("filename") or os.path.basename(value["url"]),
                    "content_type": value.get("content_type")
                    or (mimetypes.guess_type(value.get("filename") or value["url"])[0] or "image/*"),
                }
        elif hasattr(value, "url"):
            raw_url = getattr(value, "url")
            raw_name = getattr(value, "filename", None) or getattr(value, "name", None) or raw_url
            value = {
                "url": self._build_absolute_url(request, str(raw_url)),
                "filename": os.path.basename(str(raw_name)),
                "content_type": getattr(value, "content_type", None)
                or (mimetypes.guess_type(str(raw_name))[0] or "image/*"),
            }

        return await super().serialize_value(request, value, action)


# ---------------------------------------------------------------------------
# RichTextUploadField — TinyMCE с загрузкой изображений
# ---------------------------------------------------------------------------


class RichTextUploadField(LocalTinyMCEEditorField):
    """TinyMCE-редактор с поддержкой загрузки изображений в контент.

    Аналог Django CKEditor RichTextUploadingField. Позволяет вставлять
    изображения прямо в текст через диалог TinyMCE «Insert/edit image»,
    при этом файл загружается на сервер через TINYMCE_UPLOAD_URL.

    Для полей, где загрузка изображений НЕ нужна (аналог RichTextField),
    используйте LocalTinyMCEEditorField.
    """

    def __init__(self, name: str, *, label: str = "", **kwargs: Any) -> None:
        super().__init__(
            name,
            label=label,
            enable_image_upload=True,
            **kwargs,
        )
