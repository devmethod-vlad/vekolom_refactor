"""Image processing utilities.

Реализует логику обработки изображений, которая в Django была разбита между:
  - imagekit.processors.ResizeToFill             → _resize_to_fill()
  - imagekit.models.ProcessedImageField           → save_carousel_photo()
  - imagekit.models.ImageSpecField                → (read-only превью, делается на лету)
  - Celery-задача slide_to_webp в core/models.py → make_webp_sync() / make_webp_async()

Все блокирующие операции Pillow выполняются через asyncio.to_thread(),
чтобы не блокировать event loop FastAPI.

Синхронные версии (_sync) используются в Celery-воркере, где event loop не нужен.
"""

import asyncio
import io
import os
import uuid

from PIL import Image

from app.infrastructure.media.storage import abs_path, ensure_dir, webp_url_path
from app.settings.config import settings


# ---------------------------------------------------------------------------
# ResizeToFill — аналог imagekit.processors.ResizeToFill
# ---------------------------------------------------------------------------


def _resize_to_fill(img: Image.Image, width: int, height: int) -> Image.Image:
    """Кроп изображения по центру до точного размера width × height.

    Аналог imagekit ResizeToFill(width, height):
    1. Масштабируем так, чтобы оба измерения перекрыли целевой размер.
    2. Обрезаем по центру до точного размера.

    Это поведение идентично Django ProcessedImageField(processors=[ResizeToFill(2050, 544)]).
    """
    src_w, src_h = img.size
    ratio = max(width / src_w, height / src_h)
    new_w = int(src_w * ratio)
    new_h = int(src_h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return img.crop((left, top, left + width, top + height))


# ---------------------------------------------------------------------------
# Сохранение и обработка файлов (sync, для Celery и тестов)
# ---------------------------------------------------------------------------


def _unique_filename(original: str) -> str:
    """Генерирует уникальное имя файла с сохранением расширения.

    Зеркалирует поведение Django upload_to='media/', где Django сам
    добавляет суффикс при коллизии имён.
    """
    ext = os.path.splitext(original)[1].lower() or ".jpg"
    return f"{uuid.uuid4().hex}{ext}"


def save_carousel_photo_sync(content: bytes, original_filename: str) -> str:
    """Обрабатывает и сохраняет фото для карусели. Возвращает rel. путь для БД.

    Аналог Django ProcessedImageField(
        upload_to='media/',
        processors=[ResizeToFill(2050, 544)],
        format='JPEG',
        options={'quality': 90},
    )

    Возвращаемое значение — путь относительно MEDIA_ROOT, например 'media/abc123.jpg'.
    Именно это значение записывается в MainCarousel.photo.
    """
    filename = _unique_filename(original_filename)
    subdir = os.path.join(settings.media.MEDIA_ROOT, "media")
    ensure_dir(subdir)
    dest = os.path.join(subdir, filename)

    img = Image.open(io.BytesIO(content))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    img = _resize_to_fill(img, settings.media.CAROUSEL_WIDTH, settings.media.CAROUSEL_HEIGHT)
    img.save(dest, "JPEG", quality=settings.media.CAROUSEL_QUALITY)

    # Относительный путь от MEDIA_ROOT — именно он хранится в БД
    return os.path.join("media", filename)


def make_webp_sync(photo_relative_path: str, quality: int | None = None) -> str:
    """Конвертирует JPEG в WebP. Возвращает URL-путь для записи в photo_webp.

    Аналог Celery-задачи slide_to_webp из core/models.py Django:
        im = Image.open(photo_path)
        im.save(media_path + webp_name, 'webp', quality='20')
        slide.photo_webp = '/media/media/' + webp_name

    photo_relative_path — значение из MainCarousel.photo, напр. 'media/abc123.jpg'.
    Возвращает URL вида '/media/media/abc123.webp' для записи в MainCarousel.photo_webp.
    """
    q = quality if quality is not None else settings.media.WEBP_QUALITY
    abs_src = abs_path(photo_relative_path)

    if not os.path.isfile(abs_src):
        raise FileNotFoundError(f"Source photo not found: {abs_src}")

    base_name = os.path.splitext(os.path.basename(abs_src))[0]
    webp_name = base_name + ".webp"
    dest_dir = os.path.dirname(abs_src)
    abs_dest = os.path.join(dest_dir, webp_name)

    img = Image.open(abs_src)
    img.save(abs_dest, "webp", quality=q)

    return webp_url_path(abs_dest)


# ---------------------------------------------------------------------------
# Async-обёртки (для использования в FastAPI endpoint/admin)
# ---------------------------------------------------------------------------


async def save_carousel_photo(content: bytes, original_filename: str) -> str:
    """Async-обёртка над save_carousel_photo_sync для использования в FastAPI.

    Запускает блокирующий Pillow в threadpool через asyncio.to_thread(),
    чтобы не блокировать event loop.
    """
    return await asyncio.to_thread(save_carousel_photo_sync, content, original_filename)


async def make_webp(photo_relative_path: str, quality: int | None = None) -> str:
    """Async-обёртка над make_webp_sync."""
    return await asyncio.to_thread(make_webp_sync, photo_relative_path, quality)


# ---------------------------------------------------------------------------
# Сохранение фото для позиций прайс-листа (pricelist module)
# ---------------------------------------------------------------------------


def save_position_photo_sync(content: bytes, original_filename: str) -> str:
    """Обрабатывает и сохраняет фото для позиции прайс-листа. Возвращает rel. путь для БД.

    Аналог Django ProcessedImageField(
        upload_to='media/',
        format='JPEG',
        options={'quality': 90},
    )

    В отличие от save_carousel_photo_sync, здесь НЕ применяется ResizeToFill —
    Django-модель Position.photo2 / foto_app / foto_rss сохранялись без ресайза
    (кроме foto_rss с ResizeToFill(70, 70), но это мелкий частный случай).

    Возвращаемое значение — путь относительно MEDIA_ROOT, например 'media/abc123.jpg'.
    """
    filename = _unique_filename(original_filename)
    subdir = os.path.join(settings.media.MEDIA_ROOT, "media")
    ensure_dir(subdir)
    dest = os.path.join(subdir, filename)

    img = Image.open(io.BytesIO(content))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    img.save(dest, "JPEG", quality=90)

    # Относительный путь от MEDIA_ROOT — именно он хранится в БД
    return os.path.join("media", filename)


async def save_position_photo(content: bytes, original_filename: str) -> str:
    """Async-обёртка над save_position_photo_sync для использования в FastAPI."""
    return await asyncio.to_thread(save_position_photo_sync, content, original_filename)
