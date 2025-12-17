from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.home.domain.repositories import HomeReadRepository


class AsyncUnitOfWork:
    """
    UnitOfWork для одной бизнес-операции.

    Важно: UoW не создаёт сессию сам.
    Сессию и репозитории ему отдаёт DI-контейнер (Dishka) на Scope.REQUEST.
    """

    def __init__(self, session: AsyncSession, home_repo: HomeReadRepository):
        self.session = session
        self.home = home_repo

    async def __aenter__(self) -> "AsyncUnitOfWork":
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.session.rollback()
        else:
            await self.session.commit()
