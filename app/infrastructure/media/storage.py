"""Media file storage helpers.

Единственная точка, где формируются пути к медиафайлам на диске
и URL для шаблонов. Все остальные части приложения (image_processor,
Celery-задачи, admin) используют функции отсюда, а не строят пути самостоятельно.

Соглашение о хранении путей в БД
----------------------------------
Поле ``MainCarousel.photo`` хранит **относительный** путь от MEDIA_ROOT,
например ``media/filename.jpg``  (ровно так же, как хранил Django ImageField).

Поле ``MainCarousel.photo_webp`` хранит **URL-путь**,
например ``/media/media/filename.webp`` (как Django Celery-задача slide_to_webp).
Это отличие от photo намеренно сохранено для совместимости с legacy-данными.

В шаблонах:
    {{ slide.photo }}     → нужен prefix /media/:  /media/{{ slide.photo }}
    {{ slide.photo_webp }} → уже полный URL: {{ slide.photo_webp }}
"""

import os
from app.settings.config import settings


def abs_path(relative: str) -> str:
    """Возвращает абсолютный путь к медиафайлу на диске.

    Аналог os.path.join(MEDIA_ROOT, relative) из Django.

    Example:
        abs_path("media/foo.jpg") -> "/usr/src/vekolom/media/media/foo.jpg"
    """
    return os.path.join(settings.media.MEDIA_ROOT, relative)


def url_path(relative: str) -> str:
    """Строит URL для браузера из относительного пути к файлу.

    Example:
        url_path("media/foo.jpg") -> "/media/media/foo.jpg"
    """
    base = settings.media.MEDIA_URL.rstrip("/")
    rel = relative.lstrip("/")
    return f"{base}/{rel}"


def webp_url_path(abs_webp_path: str) -> str:
    """Строит URL для webp-файла из абсолютного пути — для записи в photo_webp.

    Зеркалирует Django-задачу:
        slide.photo_webp = '/media/media/' + webp_name

    Example:
        webp_url_path("/usr/src/media/media/foo.webp") -> "/media/media/foo.webp"
    """
    # Получаем путь относительно MEDIA_ROOT
    media_root = os.path.abspath(settings.media.MEDIA_ROOT)
    abs_normalized = os.path.abspath(abs_webp_path)
    try:
        rel = os.path.relpath(abs_normalized, media_root)
    except ValueError:
        # На Windows relpath может не работать между дисками — fallback
        rel = os.path.basename(abs_webp_path)
    return url_path(rel)


def ensure_dir(path: str) -> None:
    """Создаёт директорию включая промежуточные, если её нет."""
    os.makedirs(path, exist_ok=True)
