"""Универсальный рендер превью изображений для админ-панели.

Используется в любом ModelView, где нужно показать превью загруженного
изображения — как в списке записей, так и на странице детального просмотра.

Аналог AdminThumbnail из django-imagekit.

Пример использования в ModelView:
    from app.admin.utils.thumbnail import make_thumbnail_formatter

    class MyView(ModelView):
        column_formatters = {
            "photo": make_thumbnail_formatter("photo", height=60),
        }
        column_formatters_detail = {
            "photo": make_thumbnail_formatter("photo", height=200),
        }
"""

from __future__ import annotations

from typing import Any, Callable

from markupsafe import Markup


def render_thumbnail(
    photo_path: str | None,
    height: int = 60,
    media_prefix: str = "/media/",
) -> Markup:
    """Рендерит HTML-тег <img> для превью медиафайла.

    Args:
        photo_path: относительный путь к файлу (напр. 'media/foo.jpg').
                    Если None или пустая строка — возвращает заглушку «—».
        height:     высота превью в пикселях.
        media_prefix: URL-префикс для формирования полного пути к изображению.

    Returns:
        Markup с HTML-тегом <img> или заглушкой.
    """
    if not photo_path:
        return Markup("<span>—</span>")

    # Убираем лишние слэши при склейке
    prefix = media_prefix.rstrip("/")
    path = photo_path.lstrip("/")
    url = f"{prefix}/{path}"

    return Markup(
        f'<img src="{url}" height="{height}" '
        f'style="object-fit:cover;border-radius:4px;" '
        f'onerror="this.style.display=\'none\'">'
    )


def make_thumbnail_formatter(
    field_name: str = "photo",
    height: int = 60,
    media_prefix: str = "/media/",
) -> Callable[[Any, str], Markup]:
    """Фабрика column_formatter для starlette-admin.

    Возвращает callable, совместимый с ``column_formatters`` starlette-admin:
    ``(obj, attr_name) -> Markup``.

    Args:
        field_name:   имя поля модели, содержащего путь к изображению.
        height:       высота превью в пикселях.
        media_prefix: URL-префикс для медиафайлов.

    Пример:
        column_formatters = {
            "photo": make_thumbnail_formatter("photo", height=60),
        }
    """

    def _formatter(obj: Any, attr: str) -> Markup:
        value = getattr(obj, field_name, None)
        return render_thumbnail(value, height=height, media_prefix=media_prefix)

    return _formatter
