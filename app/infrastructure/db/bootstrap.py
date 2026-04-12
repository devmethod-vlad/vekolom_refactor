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
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from app.settings.config import PostgresSettings

logger = logging.getLogger("app.db.bootstrap")

_DB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# SQLSTATE для duplicate_database в PostgreSQL
_DUPLICATE_DATABASE_SQLSTATE = "42P04"

# фиксированный ключ advisory lock (одинаковый для всех инстансов приложения)
MIGRATION_LOCK_KEY = 914_000_123

# расширения, которые должны быть включены в целевой БД
REQUIRED_EXTENSIONS: tuple[str, ...] = ("pg_trgm",)

# служебные таблицы, которые не должны влиять на проверку "схема пустая / не пустая"
INTERNAL_TABLES: frozenset[str] = frozenset({"alembic_version"})

# Таблицы, по которым можно с высокой вероятностью опознать старую Django-схему проекта.
#
# Логика здесь специально консервативная:
# - django_migrations — сильный маркер того, что БД пришла из Django-проекта;
# - auth_user / django_content_type — стандартные Django-таблицы;
# - core_coreseo / maincarousel / maintext / actions / priem / slogan1 —
#   прикладные таблицы именно этого проекта, которые уже описаны в новой Alembic-миграции.
#
# Если база непустая, но под такой профиль не подходит, мы не будем автоматически
# выполнять миграции. Это защищает от сценария, когда приложение случайно подключили
# к "чужой" непустой БД.
LEGACY_DJANGO_MARKER_TABLES: frozenset[str] = frozenset(
    {
        "django_migrations",
        "django_content_type",
        "auth_user",
    }
)

LEGACY_PROJECT_TABLES: frozenset[str] = frozenset(
    {
        "core_coreseo",
        "maincarousel",
        "maintext",
        "actions",
        "priem",
        "slogan1",
        # pricelist module tables
        "category",
        "position",
        "foto",
        "pricedate",
        "pricelist_pricelistseo",
        # contacts module tables
        "contacts",
        "contacts_contactsseo",
        "mess_messages"
    }
)


@dataclass(frozen=True)
class BootstrapOptions:
    """Параметры ретраев на старте, когда Postgres ещё поднимается."""

    retries: int = 30
    delay_seconds: float = 1.0


@dataclass(frozen=True)
class DatabaseEnsureResult:
    """Результат шага ensure_database_exists."""

    database_existed: bool
    database_created: bool


@dataclass(frozen=True)
class DatabaseState:
    """Краткое описание состояния целевой БД перед запуском миграций."""

    has_alembic_version_table: bool
    current_revision: str | None
    user_tables: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        """Возвращает True, если в схеме public нет пользовательских таблиц."""
        return not self.user_tables

    @property
    def is_alembic_managed(self) -> bool:
        """Возвращает True, если база уже была инициализирована Alembic."""
        return self.has_alembic_version_table

    @property
    def looks_like_legacy_django_database(self) -> bool:
        """
        Возвращает True, если база похожа на старую Django-БД проекта.

        Критерий намеренно прагматичный, а не академически-идеальный:
        - в базе должны быть Django-маркеры;
        - в базе должна быть хотя бы часть прикладных таблиц проекта.

        Нам не нужно доказывать математическую истину; нам нужно безопасно решить,
        можно ли допускать автоматическое выполнение нашей "адаптационной"
        init-миграции поверх существующей схемы.
        """
        tables = set(self.user_tables)
        has_django_markers = LEGACY_DJANGO_MARKER_TABLES.issubset(tables)
        has_project_tables = bool(LEGACY_PROJECT_TABLES & tables)
        return has_django_markers and has_project_tables


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


def _quote_ident(conn: Connection, identifier: str) -> str:
    """
    Безопасно экранируем identifier средствами dialect/preparer.

    Да, имя БД у нас уже проходит regex-проверку, но quoting через dialect всё равно
    делает код аккуратнее и менее хрупким к будущим изменениям.
    """
    return conn.dialect.identifier_preparer.quote(identifier)


def _is_duplicate_database_error(exc: BaseException) -> bool:
    """
    Проверяем, что ошибка от PostgreSQL соответствует duplicate_database (SQLSTATE 42P04).

    Используем это для benign-гонки:
    два инстанса одновременно увидели, что БД отсутствует, и оба попытались её создать.
    Один успеет, второй получит duplicate_database — это нормальная ситуация, не авария.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    pgcode = getattr(orig, "pgcode", None)
    sqlstate = getattr(orig, "sqlstate", None)
    return pgcode == _DUPLICATE_DATABASE_SQLSTATE or sqlstate == _DUPLICATE_DATABASE_SQLSTATE


def _get_database_encoding(conn: Connection, db_name: str) -> str | None:
    """
    Возвращает encoding существующей БД, например 'UTF8', либо None, если БД не найдена.
    """
    return conn.execute(
        text(
            """
            SELECT pg_encoding_to_char(encoding)
            FROM pg_database
            WHERE datname = :dbname
            """
        ),
        {"dbname": db_name},
    ).scalar_one_or_none()


def _ensure_database_encoding_utf8(conn: Connection, db_name: str) -> None:
    """
    Проверяем, что целевая БД использует UTF8.

    Для русского текста в PostgreSQL критично именно UTF8. Если кто-то руками создал БД
    с другой кодировкой, лучше упасть сразу на старте с понятной ошибкой, чем потом
    разбираться с "кракозябрами" и странным поведением текстовых данных.
    """
    encoding = _get_database_encoding(conn, db_name)
    if encoding is None:
        raise RuntimeError(f"DB bootstrap: database metadata not found after ensure step: {db_name}")

    if encoding.upper() != "UTF8":
        raise RuntimeError(
            f"DB bootstrap: database '{db_name}' has unsupported encoding '{encoding}'. "
            "Expected UTF8."
        )


def ensure_database_exists(
    pg: PostgresSettings,
    *,
    opts: BootstrapOptions = BootstrapOptions(),
) -> DatabaseEnsureResult:
    """
    Подключается к maintenance DB (обычно 'postgres') и создаёт pg.db, если её нет.

    Возвращает признак, существовала ли база заранее, чтобы bootstrap-логика могла
    корректно логировать ветку выполнения.

    Важно:
    - нужен sync драйвер (psycopg2) и права CREATE DATABASE для пользователя;
    - CREATE DATABASE в Postgres нельзя выполнять внутри транзакции,
      поэтому используем AUTOCOMMIT.

    Дополнительно:
    - обрабатываем benign-гонку duplicate_database;
    - явно требуем UTF8 для целевой БД;
    - гарантированно освобождаем engine в finally.
    """
    _require_safe_db_name(pg.db)

    logger.info("DB bootstrap: ensure database exists: %s", pg.db)

    last_err: Exception | None = None

    for attempt in range(1, opts.retries + 1):
        engine = None
        try:
            t0 = time.monotonic()
            database_existed = False
            database_created = False

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
                    database_existed = True
                    logger.info("DB bootstrap: database already exists: %s", pg.db)
                else:
                    quoted_db_name = _quote_ident(conn, pg.db)

                    logger.warning("DB bootstrap: database not found, creating: %s", pg.db)
                    try:
                        conn.execute(
                            text(
                                f"CREATE DATABASE {quoted_db_name} "
                                "WITH ENCODING = 'UTF8' "
                                "TEMPLATE = template0"
                            )
                        )
                        database_created = True
                        logger.info("DB bootstrap: database created: %s", pg.db)

                    except DBAPIError as e:
                        if _is_duplicate_database_error(e):
                            database_existed = True
                            logger.info(
                                "DB bootstrap: database was created concurrently by another instance: %s",
                                pg.db,
                            )
                        else:
                            raise

                # Проверяем кодировку и для "уже существующей", и для "только что созданной" БД.
                _ensure_database_encoding_utf8(conn, pg.db)

            logger.info("DB bootstrap: ensure database step done in %.2fs", time.monotonic() - t0)
            return DatabaseEnsureResult(
                database_existed=database_existed,
                database_created=database_created,
            )

        except Exception as e:
            last_err = e
            logger.warning(
                "DB bootstrap: attempt %d/%d failed to ensure database exists: %s",
                attempt,
                opts.retries,
                e,
            )
            if attempt < opts.retries:
                time.sleep(opts.delay_seconds)

        finally:
            if engine is not None:
                engine.dispose()

    raise RuntimeError(
        f"DB bootstrap: unable to connect to Postgres or create database '{pg.db}'. "
        f"Last error: {last_err}"
    ) from last_err


def _list_public_tables(conn: Connection) -> tuple[str, ...]:
    """
    Возвращает список пользовательских таблиц в схеме public.

    Почему information_schema, а не sqlalchemy inspector:
    - меньше зависимостей от отражения;
    - query короткий и предсказуемый;
    - для bootstrap-проверки нам нужны только имена таблиц.
    """
    rows = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
    ).scalars()
    return tuple(rows)


def inspect_database_state(pg: PostgresSettings) -> DatabaseState:
    """
    Анализирует состояние целевой БД перед запуском миграций.

    Ключевая идея:
    наличие существующей БД — это ещё не полный ответ. Нам важно различать:
      - пустую БД;
      - БД, уже управляемую Alembic;
      - старую Django-БД проекта без alembic_version;
      - подозрительную непустую БД непонятного происхождения.

    Это позволяет держать bootstrap простым для корректных сценариев и строгим там,
    где автоматизация уже становится рискованной.
    """
    engine = None
    try:
        engine = create_engine(
            str(pg.sync_dsn),
            pool_pre_ping=True,
            future=True,
        )
        with engine.connect() as conn:
            all_tables = _list_public_tables(conn)
            has_alembic_version_table = "alembic_version" in all_tables
            user_tables = tuple(name for name in all_tables if name not in INTERNAL_TABLES)

            current_revision: str | None = None
            if has_alembic_version_table:
                current_revision = conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar_one_or_none()

            state = DatabaseState(
                has_alembic_version_table=has_alembic_version_table,
                current_revision=current_revision,
                user_tables=user_tables,
            )
            logger.info(
                "DB bootstrap: database state inspected: empty=%s, alembic_managed=%s, "
                "legacy_django=%s, current_revision=%s, user_tables=%s",
                state.is_empty,
                state.is_alembic_managed,
                state.looks_like_legacy_django_database,
                state.current_revision,
                ", ".join(state.user_tables) if state.user_tables else "<none>",
            )
            return state
    finally:
        if engine is not None:
            engine.dispose()


def _validate_database_state_before_upgrade(state: DatabaseState, db_name: str) -> None:
    """
    Решает, можно ли безопасно выполнять автоматический `alembic upgrade head`.

    Разрешённые сценарии:
      1) БД пустая;
      2) БД уже управляется Alembic;
      3) БД похожа на legacy Django-схему этого проекта.

    Сценарий №3 стал возможен потому, что init-миграция в проекте сделана
    адаптационной и идемпотентной:
    - существующие таблицы не пересоздаются;
    - отсутствующие таблицы при необходимости создаются;
    - trigram-индексы добавляются только если их ещё нет.

    Если же база непустая, но на legacy Django-схему не похожа, мы намеренно падаем.
    Автоматика не должна быть настолько смелой, чтобы радостно пометить своим
    `alembic_version` чужую или случайную БД.
    """
    if state.is_empty or state.is_alembic_managed or state.looks_like_legacy_django_database:
        return

    raise RuntimeError(
        "DB bootstrap: existing database is not empty and is not recognized as a compatible "
        "legacy Django database for this project. "
        f"Database: '{db_name}'. Detected tables: {', '.join(state.user_tables)}. "
        "Automatic migration is blocked to avoid taking ownership of an unknown schema. "
        "If this is really the old project database, verify table names and migration set; "
        "otherwise point the application to the correct database."
    )


def _ensure_required_extensions(conn: Connection) -> None:
    """
    Включаем нужные расширения в целевой БД.

    Важно:
    - расширения включаются *внутри конкретной БД*, поэтому используем соединение
      именно к pg.sync_dsn (целевой базе);
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

    Что важно для legacy-сценария:
    - под lock выполняется не только Alembic, но и включение расширений;
    - если старая Django-БД ещё не содержит alembic_version, первый успешный запуск
      аккуратно создаст её через обычный механизм Alembic.
    """
    alembic_ini = _resolve_alembic_ini()
    logger.info("DB bootstrap: alembic.ini resolved: %s", alembic_ini)

    t0 = time.monotonic()
    engine = None

    try:
        engine = create_engine(
            str(pg.sync_dsn),
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
            future=True,
        )

        with engine.connect() as conn:
            logger.info("DB bootstrap: acquiring advisory lock %s ...", MIGRATION_LOCK_KEY)
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATION_LOCK_KEY})
            logger.info("DB bootstrap: advisory lock acquired")

            main_error: Exception | None = None
            try:
                # 1) Включаем расширения ДО миграций (под тем же lock)
                _ensure_required_extensions(conn)

                # 2) Запускаем миграции Alembic
                alembic_cfg = Config(str(alembic_ini))
                alembic_cfg.set_main_option("sqlalchemy.url", str(pg.sync_dsn))

                logger.info("DB bootstrap: running alembic upgrade head ...")
                command.upgrade(alembic_cfg, "head")
                logger.info("DB bootstrap: alembic upgrade head finished")

            except Exception as exc:
                main_error = exc
                raise

            finally:
                try:
                    conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK_KEY})
                    logger.info("DB bootstrap: advisory lock released")
                except Exception:
                    if main_error is None:
                        raise
                    logger.exception(
                        "DB bootstrap: failed to release advisory lock after previous error"
                    )

    finally:
        if engine is not None:
            engine.dispose()

    logger.info("DB bootstrap: migrations step done in %.2fs", time.monotonic() - t0)


def bootstrap_database(pg: PostgresSettings) -> None:
    """
    Полный bootstrap базы данных на старте приложения.

    Итоговая логика:
      1) если БД отсутствует -> создаём её;
      2) анализируем состояние схемы;
      3) если схема пустая -> накатываем все миграции до head;
      4) если схема уже под Alembic -> обновляем до head;
      5) если это распознанная legacy Django-БД проекта -> также выполняем upgrade head,
         потому что init-миграция написана как безопасная адаптационная миграция;
      6) если это непустая неизвестная БД -> аварийно завершаем старт.

    Такой подход сохраняет понятный пользовательский сценарий:
    - новой БД достаточно "создать и накатить всё";
    - старую БД проекта можно безопасно "подхватить" без ручного stamp;
    - случайную чужую БД приложение себе не присвоит.
    """
    logger.info("DB bootstrap: start")

    ensure_result = ensure_database_exists(pg)
    state = inspect_database_state(pg)
    _validate_database_state_before_upgrade(state, pg.db)

    if ensure_result.database_created:
        logger.info(
            "DB bootstrap: database '%s' was created during startup; applying all migrations",
            pg.db,
        )
    elif state.is_empty:
        logger.info(
            "DB bootstrap: database '%s' already exists but schema is empty; applying all migrations",
            pg.db,
        )
    elif state.is_alembic_managed:
        logger.info(
            "DB bootstrap: database '%s' already exists and is managed by Alembic; upgrading from revision %s to head",
            pg.db,
            state.current_revision,
        )
    else:
        logger.info(
            "DB bootstrap: database '%s' looks like the legacy Django schema of this project; "
            "running idempotent init migration and upgrading to head",
            pg.db,
        )

    run_alembic_upgrade(pg)
    logger.info("DB bootstrap: done")