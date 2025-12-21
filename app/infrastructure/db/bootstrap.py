from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.settings.config import PostgresSettings

logger = logging.getLogger("app.db.bootstrap")

_DB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# фиксированный ключ advisory lock (одинаковый для всех инстансов приложения)
MIGRATION_LOCK_KEY = 914_000_123

# расширения, которые должны быть включены в целевой БД
REQUIRED_EXTENSIONS: tuple[str, ...] = ("pg_trgm",)


@dataclass(frozen=True)
class BootstrapOptions:
    """Параметры ретраев на старте, когда Postgres ещё поднимается."""
    retries: int = 30
    delay_seconds: float = 1.0


def _require_safe_db_name(db_name: str) -> None:
    """
    Проверяем имя БД, потому что CREATE DATABASE нельзя безопасно параметризовать,
    и нам придётся вставить имя в SQL строку. Regex защищает от SQL-инъекций.
    """
    if not _DB_NAME_RE.match(db_name):
        raise ValueError(
            f"Некорректное имя БД: {db_name!r}. Разрешены буквы/цифры/подчёркивание, "
            f"не должно начинаться с цифры."
        )


def _find_upwards(start: Path, filename: str) -> Path | None:
    """
    Поднимаемся вверх по дереву каталогов от start и ищем filename.
    Возвращаем полный путь или None.
    """
    cur = start.resolve()
    for parent in (cur, *cur.parents):
        candidate = parent / filename
        if candidate.exists():
            return candidate
    return None


def _resolve_alembic_ini() -> Path:
    """
    Надёжно находим alembic.ini.

    Стратегия:
      1) ALEMBIC_INI (если задан в env) — абсолютный или относительный путь
      2) поиск alembic.ini вверх от текущей рабочей директории (cwd)
      3) поиск alembic.ini вверх от расположения этого файла (bootstrap.py)
      4) как fallback: ищем pyproject.toml и предполагаем, что alembic.ini рядом
    """
    env_path = os.getenv("ALEMBIC_INI")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"ALEMBIC_INI задан, но файл не найден: {p}")

    found = _find_upwards(Path.cwd(), "alembic.ini")
    if found:
        return found

    here = Path(__file__).resolve().parent
    found = _find_upwards(here, "alembic.ini")
    if found:
        return found

    pyproject = _find_upwards(Path.cwd(), "pyproject.toml") or _find_upwards(here, "pyproject.toml")
    if pyproject:
        candidate = pyproject.parent / "alembic.ini"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Не удалось найти alembic.ini. "
        "Либо положи его в корень проекта, либо задай переменную окружения ALEMBIC_INI."
    )


def ensure_database_exists(pg: PostgresSettings, *, opts: BootstrapOptions = BootstrapOptions()) -> None:
    """
    Подключается к maintenance DB (обычно 'postgres') и создаёт pg.db, если её нет.

    Важно:
    - нужен sync драйвер (psycopg2) и права CREATE DATABASE для пользователя.
    - CREATE DATABASE в Postgres нельзя выполнять внутри транзакции,
      поэтому используем AUTOCOMMIT.
    """
    _require_safe_db_name(pg.db)

    logger.info("DB bootstrap: ensure database exists: %s", pg.db)

    last_err: Exception | None = None

    for attempt in range(1, opts.retries + 1):
        try:
            t0 = time.time()

            engine = create_engine(
                str(pg.maintenance_dsn),
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True,
                future=True,
            )
            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                    {"dbname": pg.db},
                ).scalar()

                if exists:
                    logger.info("DB bootstrap: database already exists: %s", pg.db)
                else:
                    logger.warning("DB bootstrap: database not found, creating: %s", pg.db)
                    conn.execute(text(f'CREATE DATABASE "{pg.db}"'))
                    logger.info("DB bootstrap: database created: %s", pg.db)

            engine.dispose()
            logger.info("DB bootstrap: ensure database step done in %.2fs", time.time() - t0)
            return

        except Exception as e:
            last_err = e
            logger.warning(
                "DB bootstrap: attempt %d/%d failed to ensure database exists: %s",
                attempt,
                opts.retries,
                e,
            )
            time.sleep(opts.delay_seconds)

    raise RuntimeError(
        f"DB bootstrap: unable to connect to Postgres or create database '{pg.db}'. "
        f"Last error: {last_err}"
    ) from last_err


def _ensure_required_extensions(conn) -> None:
    """
    Включаем нужные расширения в целевой БД.

    Важно:
    - расширения включаются *внутри конкретной БД*, поэтому используем соединение
      именно к pg.sync_dsn (целевой базе).
    - IF NOT EXISTS делает операцию идемпотентной.
    """
    for ext in REQUIRED_EXTENSIONS:
        logger.info("DB bootstrap: ensuring extension enabled: %s", ext)
        conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}";'))


def run_alembic_upgrade(pg: PostgresSettings) -> None:
    """
    Прогоняет `alembic upgrade head` под advisory lock, чтобы миграции
    не выполнялись параллельно в нескольких процессах/репликах.

    Lock берём в целевой БД (pg.sync_dsn), чтобы все инстансы “видели” один и тот же замок.
    """
    alembic_ini = _resolve_alembic_ini()
    logger.info("DB bootstrap: alembic.ini resolved: %s", alembic_ini)

    t0 = time.time()

    engine = create_engine(str(pg.sync_dsn), pool_pre_ping=True, future=True)

    with engine.connect() as conn:
        logger.info("DB bootstrap: acquiring advisory lock %s ...", MIGRATION_LOCK_KEY)
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATION_LOCK_KEY})
        logger.info("DB bootstrap: advisory lock acquired")

        try:
            # 1) Включаем расширения ДО миграций (под тем же lock)
            _ensure_required_extensions(conn)

            # Важно: Alembic будет работать через другое соединение.
            # Поэтому фиксируем изменения, чтобы миграции "увидели" extension.
            conn.commit()

            # 2) Запускаем миграции Alembic
            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", str(pg.sync_dsn))

            logger.info("DB bootstrap: running alembic upgrade head ...")
            command.upgrade(alembic_cfg, "head")
            logger.info("DB bootstrap: alembic upgrade head finished")

        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK_KEY})
            logger.info("DB bootstrap: advisory lock released")

    engine.dispose()
    logger.info("DB bootstrap: migrations step done in %.2fs", time.time() - t0)


def bootstrap_database(pg: PostgresSettings) -> None:
    """
    Точка входа:
      1) создаём БД, если её нет
      2) включаем расширения (pg_trgm) и применяем миграции Alembic до head

    Вызывается на старте приложения (обычно из FastAPI lifespan),
    чтобы приложение принимало запросы только с валидной БД-структурой.
    """
    logger.info("DB bootstrap: start")
    ensure_database_exists(pg)
    run_alembic_upgrade(pg)
    logger.info("DB bootstrap: done")
