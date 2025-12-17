from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings.config import PostgresSettings


@dataclass(frozen=True, slots=True)
class AsyncDatabase:
    """Тонкая обёртка: engine + фабрика AsyncSession.
    - единая точка, где создаётся engine и sessionmaker;
    - удобно отдавать в DI как один объект;
    - легко централизованно настраивать пул, echo, pre_ping и т.д.
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @classmethod
    def from_config(cls, cfg: PostgresSettings) -> "AsyncDatabase":
        engine = create_async_engine(
            str(cfg.dsn),
            echo=cfg.echo,
            pool_pre_ping=True,
            pool_size=cfg.pool_size,
            max_overflow=cfg.pool_overflow_size,
        )
        session_factory = async_sessionmaker(
            bind=engine,
            autoflush=cfg.autoflush,
            expire_on_commit=cfg.expire_on_commit,
        )
        return cls(engine=engine, session_factory=session_factory)
