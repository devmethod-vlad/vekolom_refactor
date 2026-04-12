from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.apikeys.domain.repositories import ApiKeysReadRepository
from app.modules.home.domain.repositories import HomeReadRepository
from app.modules.pricelist.domain.repositories import PricelistReadRepository
from app.modules.contacts.domain.repositories import (
    ContactsReadRepository,
    ContactsWriteRepository,
)


class AsyncUnitOfWork:
    """
    UnitOfWork для одной бизнес-операции.

    Важно: UoW не создаёт сессию сам.
    Сессию и репозитории ему отдаёт DI-контейнер (Dishka) на Scope.REQUEST.
    """

    def __init__(
        self,
        session: AsyncSession,
        home_repo: HomeReadRepository,
        pricelist_repo: PricelistReadRepository,
        contacts_repo: ContactsReadRepository,
        contacts_write_repo: ContactsWriteRepository,
        apikeys_repo: ApiKeysReadRepository,
    ):
        self.session = session
        self.home = home_repo
        self.pricelist = pricelist_repo
        self.contacts = contacts_repo
        self.contacts_write = contacts_write_repo
        self.apikeys = apikeys_repo

    async def __aenter__(self) -> "AsyncUnitOfWork":
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc:
            await self.session.rollback()
        else:
            await self.session.commit()
