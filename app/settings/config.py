"""Application settings.

This project uses Pydantic Settings v2.

Why we add a maintenance DSN
----------------------------
`POSTGRES_DB` (-> `PostgresSettings.db`) points to the target application
database. If that database does not exist yet, we cannot connect to it to run
Alembic migrations.

So we keep a second DSN (`maintenance_dsn`) that connects to a known-existing
database (by default: `postgres`) and can execute `CREATE DATABASE ...`.
"""

import typing as tp

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvBaseSettings(BaseSettings):
    """Base settings with .env support."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="app_")

    DEBUG: bool = False

    # Needed for cookie-based sessions in Starlette-Admin (SessionMiddleware).
    SECRET_KEY: str = "CHANGE_ME_PLEASE"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    ADMIN_TITLE: str = "Vekolom Admin"


class PostgresSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="postgres_")

    host: str
    port: int = 5432
    user: str
    password: str
    db: str  # POSTGRES_DB

    # App works asynchronously, but Starlette-Admin and Alembic use sync engine.
    use_async: bool = True
    async_driver: str = "asyncpg"
    sync_driver: str = "psycopg2"  # psycopg3; can be changed later

    echo: bool = False

    # Pools/sessions (used in Database.from_config)
    pool_size: int = 5
    pool_overflow_size: int = 10
    autoflush: bool = False
    expire_on_commit: bool = False

    # Where to connect to create DB if it doesn't exist (usually `postgres`)
    maintenance_db: str = "postgres"

    # DSNs
    dsn: str | None = None
    sync_dsn: str | None = None
    maintenance_dsn: str | None = None

    # Future: replicas
    slave_hosts: list[str] = Field(default_factory=list)
    slave_dsns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def assemble_db_connection(self) -> tp.Self:
        # 1) DSN for main async application
        if self.dsn is None:
            driver = self.async_driver if self.use_async else self.sync_driver
            self.dsn = (
                f"postgresql+{driver}://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.db}"
            )

        # 2) DSN for sync tools (Starlette-Admin, Alembic, bootstrap checks)
        if self.sync_dsn is None:
            self.sync_dsn = (
                f"postgresql+{self.sync_driver}://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.db}"
            )

        # 3) DSN for maintenance DB (to run CREATE DATABASE)
        if self.maintenance_dsn is None:
            self.maintenance_dsn = (
                f"postgresql+{self.sync_driver}://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.maintenance_db}"
            )

        return self


class Settings(EnvBaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: PostgresSettings = Field(default_factory=PostgresSettings)


settings = Settings()
