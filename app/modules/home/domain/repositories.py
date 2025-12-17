from __future__ import annotations

from typing import Protocol

from app.modules.home.domain.dto import HomePageDTO, SeoDTO


class HomeReadRepository(Protocol):
    async def get_seo(self, slug: str) -> SeoDTO | None: ...
    async def list_blocks(self) -> list[HomePageDTO]: ...
