from __future__ import annotations

import typing as tp

from dishka import Provider, Scope, provide
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.async_database import AsyncDatabase
from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.home.application.use_cases import GetHomePage
from app.modules.home.domain.repositories import HomeReadRepository
from app.modules.home.infrastructure.repositories import SAHomeReadRepository
from app.settings.config import PostgresSettings, Settings, settings


class SettingsProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return settings

    @provide(scope=Scope.APP)
    def get_postgres(self, s: Settings) -> PostgresSettings:
        return s.database


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_async_db(self, pg: PostgresSettings) -> tp.AsyncIterator[AsyncDatabase]:
        db = AsyncDatabase.from_config(pg)
        try:
            yield db
        finally:
            await db.engine.dispose()

    @provide(scope=Scope.REQUEST)
    async def get_session(self, db: AsyncDatabase) -> tp.AsyncIterator[AsyncSession]:
        async with db.session_factory() as session:
            yield session


class TemplatesProvider(Provider):
    @provide(scope=Scope.APP)
    def get_templates(self) -> Jinja2Templates:
        # путь поправь под свою структуру, если шаблоны лежат иначе
        return Jinja2Templates(directory="app/templates")


class HomeProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_home_repo(self, session: AsyncSession) -> HomeReadRepository:
        return SAHomeReadRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_uow(self, session: AsyncSession, home_repo: HomeReadRepository) -> AsyncUnitOfWork:
        return AsyncUnitOfWork(session=session, home_repo=home_repo)

    @provide(scope=Scope.APP)
    def get_home_use_case(self) -> GetHomePage:
        return GetHomePage()
