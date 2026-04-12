"""
Domain entities for the pricelist module.

Field names deliberately mirror the legacy Django model fields so that
Jinja2 templates can be ported from Django templates with minimal changes.

Сущности повторяют структуру Django-моделей из pricelist/models.py:
    Position    — позиция прайс-листа
    Category    — категория позиций
    Foto        — фотография к позиции
    PriceDate   — дата актуальности прайса
    PricelistSeo — SEO-метаданные страницы прайс-листа
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class PricelistSeo:
    """SEO-метаданные для страницы прайс-листа (legacy table ``pricelist_pricelistseo``)."""

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PriceDate:
    """Дата актуальности прайс-листа (legacy table ``pricedate``).

    В Django-шаблоне использовалось: ``{{ d.date }}``.
    """

    id: int
    date: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Foto:
    """Фотография к позиции прайс-листа (legacy table ``foto``).

    ``foto`` — относительный путь к JPEG (напр. ``media/filename.jpg``).
    ``foto_webp`` — URL-путь к WebP-версии (``/media/media/name.webp``).
    ``text`` — подпись к фотографии.
    ``position_id`` — FK на позицию.

    В Django-шаблоне:
        {{ foto.foto.url }}          → /media/{{ foto.foto }}
        {{ foto.avatarfoto.url }}    → генерировалось ImageSpecField (150×150),
                                       пока используем оригинал foto.
    """

    id: int
    foto: Optional[str] = None
    foto_webp: Optional[str] = None
    text: Optional[str] = None
    position_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class Category:
    """Категория позиций прайс-листа (legacy table ``category``).

    ``description`` — rich-text описание (RichTextUploadingField в Django).
    """

    id: int
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass(slots=True)
class PositionEntity:
    """Позиция прайс-листа (legacy table ``position``).

    Содержит все поля оригинальной Django-модели Position.
    Имена полей сохранены один-в-один для совместимости с шаблонами.

    ``category`` — связанный объект Category (в Django: ForeignKey).
    ``fotos`` — список связанных Foto (в Django: reverse FK, related_name='positions').
    """

    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    title: Optional[str] = None
    seodescrip: Optional[str] = None
    keywords: Optional[str] = None
    check_flag: bool = False
    order: Optional[float] = None

    # Цены: Безналичный расчет (На карту физ.лица)
    price_title: Optional[str] = None
    price: Optional[str] = None
    price2_title: Optional[str] = None
    price_2: Optional[str] = None
    price3_title: Optional[str] = None
    price_3: Optional[str] = None

    # Цены: Безналичный расчет (Лицензия юр.лица)
    price_card_title: Optional[str] = None
    price_card: Optional[str] = None
    price2_card_title: Optional[str] = None
    price2_card: Optional[str] = None

    # Изображения
    photo2: Optional[str] = None
    photo2_webp: Optional[str] = None
    avatar_webp: Optional[str] = None
    foto_app: Optional[str] = None
    foto_rss: Optional[str] = None

    # FK
    category_id: Optional[int] = None

    # Связанные объекты (заполняются на уровне use case / repository)
    category: Optional[Category] = None
    fotos: list[Foto] = field(default_factory=list)
