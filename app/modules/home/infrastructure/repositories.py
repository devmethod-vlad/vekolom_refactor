from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.home.domain.dto import HomePageDTO, SeoDTO
from app.modules.home.domain.repositories import HomeReadRepository
from app.modules.home.infrastructure.sa_models import HomeBlock, HomeSEO


class SAHomeReadRepository(HomeReadRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_seo(self, slug: str) -> SeoDTO | None:
        res = await self._session.execute(select(HomeSEO).where(HomeSEO.slug == slug))
        row = res.scalar_one_or_none()
        if not row:
            return None
        return SeoDTO(title=row.title, description=row.description, keywords=row.keywords)

    async def list_blocks(self) -> list[HomePageDTO]:
        res = await self._session.execute(
            select(HomeBlock).where(HomeBlock.is_active.is_(True)).order_by(HomeBlock.position.asc())
        )
        rows = res.scalars().all()
        return [
            HomeBlockDTO(
                key=r.key,
                title=r.title,
                body=r.body,
                position=r.position,
            )
            for r in rows
        ]
