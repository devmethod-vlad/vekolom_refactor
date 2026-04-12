"""
Data transfer objects for the pricelist module.

``PricelistPageDTO`` mirrors the exact set of variables that the legacy Django
view ``pricelist(request)`` passed to its template context:

    debug_flag  ← settings.DEBUG
    date        ← PriceDate.objects.all()
    fotos       ← Foto.objects.all()
    seo         ← PricelistSeo.objects.all()
    categories  ← Category.objects.order_by('-name')
    positions   ← Position.objects.order_by('order')
"""

from dataclasses import dataclass
from typing import Optional, Sequence

from .entities import Category, Foto, PositionEntity, PriceDate, PricelistSeo


@dataclass(frozen=True, slots=True)
class PricelistPageDTO:
    """Aggregate DTO for the pricelist page.

    Variable names intentionally match the Django template context so the
    Jinja2 template can use the same ``{{ variable }}`` references.
    """

    # SEO-метаданные — полный queryset (в Django: PricelistSeo.objects.all())
    seo: Sequence[PricelistSeo]

    # Дата прайс-листа (в Django: PriceDate.objects.all())
    date: Sequence[PriceDate]

    # Все фотографии (в Django: Foto.objects.all())
    fotos: Sequence[Foto]

    # Категории, отсортированные по имени в обратном порядке
    # (в Django: Category.objects.order_by('-name'))
    categories: Sequence[Category]

    # Позиции, отсортированные по полю order
    # (в Django: Position.objects.order_by('order'))
    positions: Sequence[PositionEntity]

    # Флаг дебага из настроек
    debug_flag: bool = False
