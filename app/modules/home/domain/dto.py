from dataclasses import dataclass
from typing import Sequence

from app.modules.home.domain.entities import Seo, CarouselSlide, MainBlock, ActionItem, Slogan, AcceptItem


@dataclass(frozen=True)
class HomePageDTO:
    seo: Seo
    slides: Sequence[CarouselSlide]
    main_blocks: Sequence[MainBlock]
    actions: Sequence[ActionItem]      # первые 3
    slogans: Sequence[Slogan]
    accept_items: Sequence[AcceptItem]
    positions: Sequence[dict]          # пока dict, пока прайс не вынесен нормально


@dataclass(frozen=True, slots=True)
class SeoDTO:
    title: str = ""
    description: str = ""
    keywords: str = ""
