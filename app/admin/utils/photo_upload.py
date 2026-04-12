"""Универсальная обработка загрузки изображений для админ-панели.

Обеспечивает:
  - Валидацию формата файла (допустимые расширения).
  - Ограничение размера файла в мегабайтах.
  - Ограничение длины имени файла.
  - Человекочитаемые ошибки, отображаемые в интерфейсе админки.

Все ограничения читаются из .env (через UploadPhotoSettings) и могут быть
переопределены непосредственно при вызове функции.

Пример использования в ModelView:

    from app.admin.utils.photo_upload import handle_photo_upload

    class MyView(ModelView):
        async def before_create(self, request, data, obj):
            await handle_photo_upload(
                data=data,
                field_name="photo",
                save_fn=save_carousel_photo_sync,
                # Опционально — переопределить настройки из .env:
                # allowed_formats=["jpeg", "jpg"],
                # max_size_mb=5,
                # max_filename_length=80,
            )
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

from starlette_admin.exceptions import FormValidationError

from app.settings.config import settings


class PhotoUploadError(Exception):
    """Ошибка валидации загружаемого файла."""

    pass


def _validate_upload(
    filename: str,
    content: bytes,
    allowed_formats: list[str] | None = None,
    max_size_mb: float | None = None,
    max_filename_length: int | None = None,
) -> None:
    """Проверяет загруженный файл на соответствие ограничениям.

    Все параметры None означают «использовать значение из .env (UploadPhotoSettings)».

    Проверки (в порядке выполнения):
      1. Расширение файла — быстрая проверка по имени.
      2. Magic bytes — реальный формат файла, независимо от расширения.
         Защищает от загрузки exploit.php, переименованного в exploit.jpg.
      3. Размер файла — лимит в мегабайтах.
      4. Длина имени — лимит в символах.

    Args:
        filename:            оригинальное имя загруженного файла.
        content:             содержимое файла в байтах.
        allowed_formats:     список допустимых расширений (без точки), например ['jpeg', 'jpg', 'png'].
        max_size_mb:         максимальный размер файла в мегабайтах.
        max_filename_length: максимальная длина имени файла в символах.

    Raises:
        PhotoUploadError: с человекочитаемым описанием нарушенного ограничения.
    """
    upload_cfg = settings.upload

    # --- Допустимые форматы (по расширению) ---
    formats = allowed_formats if allowed_formats is not None else upload_cfg.ALLOWED_IMAGE_FORMATS
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext not in formats:
        allowed = ", ".join(formats)
        raise PhotoUploadError(
            f"Недопустимый формат файла «.{ext}». Разрешены: {allowed}."
        )

    # --- Magic bytes (реальный формат файла) ---
    # Проверяем сигнатуру файла (первые байты), а не только расширение.
    # Это предотвращает загрузку вредоносных файлов с поддельным расширением.
    # imghdr deprecated в Python 3.11+ и удалён в 3.13, поэтому проверяем вручную.
    detected_format = _detect_image_format(content)
    if detected_format is None:
        raise PhotoUploadError(
            "Содержимое файла не является допустимым изображением. "
            "Проверьте, что файл не повреждён."
        )

    # --- Размер файла ---
    limit_mb = max_size_mb if max_size_mb is not None else upload_cfg.MAX_FILE_SIZE_MB
    size_mb = len(content) / (1024 * 1024)
    if size_mb > limit_mb:
        raise PhotoUploadError(
            f"Размер файла ({size_mb:.1f} МБ) превышает допустимый лимит ({limit_mb} МБ)."
        )

    # --- Длина имени файла ---
    name_limit = (
        max_filename_length
        if max_filename_length is not None
        else upload_cfg.MAX_FILENAME_LENGTH
    )
    if len(filename) > name_limit:
        raise PhotoUploadError(
            f"Имя файла слишком длинное ({len(filename)} симв.). "
            f"Максимальная длина — {name_limit} символов."
        )


def _detect_image_format(content: bytes) -> str | None:
    """Определяет формат изображения по magic bytes (сигнатуре файла).

    Возвращает строку формата ('jpeg', 'png', 'gif', 'webp')
    или None, если формат не распознан.

    Magic bytes — первые несколько байт файла, уникальные для каждого формата.
    Эта проверка невозможна для обхода простым переименованием файла.
    """
    if len(content) < 8:
        return None

    # JPEG: начинается с FF D8 FF
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"

    # PNG: начинается с 8-байтной сигнатуры
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    # GIF: начинается с GIF87a или GIF89a
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"

    # WebP: начинается с RIFF....WEBP
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"

    return None


async def handle_photo_upload(
    data: dict[str, Any],
    field_name: str,
    save_fn: Callable[[bytes, str], str],
    allowed_formats: list[str] | None = None,
    max_size_mb: float | None = None,
    max_filename_length: int | None = None,
) -> None:
    """Обрабатывает загрузку фото из формы starlette-admin.

    Извлекает файл из ``data[field_name]``, валидирует, обрабатывает через
    ``save_fn`` (sync-функция, будет запущена в threadpool) и записывает
    результирующий путь обратно в ``data[field_name]``.

    Если файл не был загружен (поле пустое, None или строка-путь при
    редактировании без смены фото) — ничего не делает.

    Args:
        data:               словарь данных формы starlette-admin.
        field_name:         имя поля в data, содержащего загруженный файл.
        save_fn:            синхронная функция ``(content: bytes, filename: str) -> str``,
                            выполняющая обработку и сохранение файла на диск.
                            Возвращает относительный путь для записи в БД.
        allowed_formats:    переопределение допустимых форматов (None = из .env).
        max_size_mb:        переопределение лимита размера (None = из .env).
        max_filename_length: переопределение лимита длины имени (None = из .env).

    Raises:
        FormValidationError: при нарушении ограничений — starlette-admin
                             покажет сообщение об ошибке в интерфейсе.
    """
    upload = data.get(field_name)

    # upload может быть: UploadFile, str (уже путь), None, или пустой UploadFile
    if upload is None:
        return
    if isinstance(upload, str):
        # Редактирование без смены фото — поле пришло как строка-путь
        return
    if not hasattr(upload, "read"):
        return

    filename = getattr(upload, "filename", None) or "upload.jpg"
    content = await upload.read()

    if not content:
        # Пустой файл — пользователь не выбрал новый файл при редактировании
        data.pop(field_name, None)
        return

    # Валидация с человекочитаемыми ошибками
    try:
        _validate_upload(
            filename=filename,
            content=content,
            allowed_formats=allowed_formats,
            max_size_mb=max_size_mb,
            max_filename_length=max_filename_length,
        )
    except PhotoUploadError as exc:
        # FormValidationError отображается в интерфейсе starlette-admin
        raise FormValidationError({field_name: str(exc)})

    # Обработка и сохранение через sync-функцию в threadpool
    rel_path = await asyncio.to_thread(save_fn, content, filename)
    data[field_name] = rel_path
