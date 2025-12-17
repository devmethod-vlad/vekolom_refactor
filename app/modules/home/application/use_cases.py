from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.home.domain.dto import HomePageDTO


class GetHomePage:
    async def execute(self, uow: AsyncUnitOfWork) -> HomePageDTO:
        async with uow:
            seo = await uow.home.get_seo(slug="main")
            blocks = await uow.home.list_blocks()

        return HomePageDTO(seo=seo, blocks=blocks)
