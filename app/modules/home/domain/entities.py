from dataclasses import dataclass


@dataclass(frozen=True)
class Seo:
    title: str | None
    description: str | None
    keywords: str | None


@dataclass(frozen=True)
class CarouselSlide:
    id: int
    image_path: str | None
    image_webp_path: str | None
    text_html: str | None
    sort_order: int
    is_active: bool


@dataclass(frozen=True)
class MainBlock:
    header: str | None
    text_html: str | None
    is_active: bool


@dataclass(frozen=True)
class ActionItem:
    text_html: str | None
    sort_order: int
    is_active: bool


@dataclass(frozen=True)
class Slogan:
    text_html: str | None
    is_active: bool


@dataclass(frozen=True)
class AcceptItem:
    header: str | None
    text_html: str | None
    sort_order: int
    is_active: bool
