import typing as tp

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="app_")

    DEBUG: bool = False

    # Нужен для cookie-сессий starlette-admin (SessionMiddleware)
    SECRET_KEY: str = "CHANGE_ME_PLEASE"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    ADMIN_TITLE: str = "Vekolom Admin"


class PostgresSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_prefix="postgres_"
    )

    host: str
    port: int = 5432
    user: str
    password: str
    db: str

    # В приложении мы работаем асинхронно, но для starlette-admin нужен sync engine
    use_async: bool = True
    async_driver: str = "asyncpg"
    sync_driver: str = "psycopg2"  # psycopg3; можно заменить на "psycopg2"

    echo: bool = False

    # Пулы/сессии (то, что у тебя уже используется в Database.from_config)
    pool_size: int = 5
    pool_overflow_size: int = 10
    autoflush: bool = False
    expire_on_commit: bool = False

    # DSN’ы
    dsn: str | None = None
    sync_dsn: str | None = None

    # На будущее (реплики)
    slave_hosts: list[str] = Field(default_factory=list)
    slave_dsns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def assemble_db_connection(self) -> tp.Self:
        # 1) DSN для основного приложения
        if self.dsn is None:
            driver = self.async_driver if self.use_async else self.sync_driver
            self.dsn = (
                f"postgresql+{driver}://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.db}"
            )

        # 2) DSN для sync-инструментов (starlette-admin, alembic offline и т.п.)
        if self.sync_dsn is None:
            self.sync_dsn = (
                f"postgresql+{self.sync_driver}://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.db}"
            )

        return self


class Settings(EnvBaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: PostgresSettings = Field(default_factory=PostgresSettings)


settings = Settings()
