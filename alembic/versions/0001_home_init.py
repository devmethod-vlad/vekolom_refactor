"""home: initial schema / legacy adoption migration

Revision ID: 0001_home_init
Revises:
Create Date: 2025-12-21

Эта миграция выполняет сразу две роли:

1) Для новой пустой базы данных:
   - создаёт таблицы модуля `home`;
   - включает нужные PostgreSQL extensions;
   - создаёт trigram-индексы.

2) Для уже существующей legacy Django-БД:
   - не пытается пересоздать уже имеющиеся таблицы;
   - не удаляет и не ломает существующую схему;
   - добавляет только отсутствующие таблицы и отсутствующие trigram-индексы.

Почему миграция написана так, а не через "обычный лобовой create_table":
- bootstrap проекта должен уметь безопасно стартовать поверх старой БД Django;
- при первом запуске Alembic на legacy-БД ревизия `0001_home_init` будет выполнена
  как первая миграция;
- если здесь безусловно вызывать `create_table(...)`, то старт упадёт на
  "table already exists".

Важно:
- миграция сознательно НЕ пытается автоматически "выправлять" все возможные
  расхождения legacy-схемы с новой ORM-моделью;
- здесь реализована безопасная адаптация стартового состояния, а не тотальная
  реконструкция всей исторической схемы.
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.engine.reflection import Inspector


revision = "0001_home_init"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Вспомогательные функции инспекции схемы
# ---------------------------------------------------------------------------


def _inspector(bind: Connection) -> Inspector:
    """Создаёт Inspector для текущего bind."""
    return sa.inspect(bind)


def _table_exists(bind: Connection, table_name: str) -> bool:
    """
    Проверяет существование таблицы в схеме public.

    Используем inspector вместо предположений:
    миграция должна корректно работать и на новой БД, и на legacy Django-БД.
    """
    insp = _inspector(bind)
    return table_name in insp.get_table_names(schema="public")


def _column_exists(bind: Connection, table_name: str, column_name: str) -> bool:
    """
    Проверяет существование колонки в таблице.

    Это дополнительная защита на случай ручных изменений legacy-схемы.
    """
    if not _table_exists(bind, table_name):
        return False

    insp = _inspector(bind)
    columns = insp.get_columns(table_name, schema="public")
    return any(col["name"] == column_name for col in columns)


def _index_exists(bind: Connection, table_name: str, index_name: str) -> bool:
    """
    Проверяет существование индекса по имени.

    Почему не используем if_not_exists в create_index:
    - так меньше зависимости от конкретной версии Alembic;
    - логика остаётся прозрачной и предсказуемой;
    - совместимость получается чуть менее хрупкой.
    """
    if not _table_exists(bind, table_name):
        return False

    insp = _inspector(bind)
    indexes = insp.get_indexes(table_name, schema="public")
    return any(idx["name"] == index_name for idx in indexes)


def _create_table_if_missing(
    bind: Connection,
    table_name: str,
    *columns: sa.Column,
) -> None:
    """
    Создаёт таблицу только если её ещё нет.

    Для legacy-сценария это критично: существующие Django-таблицы не должны
    пересоздаваться Alembic-миграцией.
    """
    if _table_exists(bind, table_name):
        return

    op.create_table(table_name, *columns)


def _create_trgm_index_if_missing(
    bind: Connection,
    *,
    index_name: str,
    table_name: str,
    column_name: str,
) -> None:
    """
    Создаёт trigram GIN-индекс только если:
    - таблица существует;
    - колонка существует;
    - индекс с таким именем ещё не существует.

    Это делает миграцию идемпотентной и безопасной для legacy-БД.
    """
    if not _table_exists(bind, table_name):
        return

    if not _column_exists(bind, table_name, column_name):
        return

    if _index_exists(bind, table_name, index_name):
        return

    op.create_index(
        index_name,
        table_name,
        [column_name],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={column_name: "gin_trgm_ops"},
    )


# ---------------------------------------------------------------------------
# Описание стартовых таблиц модуля home
# ---------------------------------------------------------------------------


def _create_core_coreseo(bind: Connection) -> None:
    """
    Таблица SEO для главной страницы.

    Legacy Django-схема:
        id          bigserial primary key
        title       text
        description text
        keywords    text
    """
    _create_table_if_missing(
        bind,
        "core_coreseo",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
    )


def _create_maincarousel(bind: Connection) -> None:
    """
    Таблица карусели главной страницы.

    Важно: размеры строк приведены к legacy Django-схеме:
        photo       varchar(100)
        photo_amp   varchar(100)
        photo_turbo varchar(100)
        photo_webp  varchar(600)

    Это отличается от предыдущей Alembic-версии, где длины были завышены до 300.
    Для "усыновления" старой БД лучше ориентироваться именно на реальную legacy-схему.
    """
    _create_table_if_missing(
        bind,
        "maincarousel",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("photo", sa.String(length=100), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("photo_amp", sa.String(length=100), nullable=True),
        sa.Column("photo_turbo", sa.String(length=100), nullable=True),
        sa.Column("photo_webp", sa.String(length=600), nullable=True),
    )


def _create_maintext(bind: Connection) -> None:
    """Таблица основного текста главной страницы."""
    _create_table_if_missing(
        bind,
        "maintext",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
    )


def _create_actions(bind: Connection) -> None:
    """Таблица блока actions."""
    _create_table_if_missing(
        bind,
        "actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=True),
    )


def _create_priem(bind: Connection) -> None:
    """Таблица блока priem."""
    _create_table_if_missing(
        bind,
        "priem",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
    )


def _create_slogan1(bind: Connection) -> None:
    """Таблица блока slogan1."""
    _create_table_if_missing(
        bind,
        "slogan1",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=True),
    )


def _create_home_tables(bind: Connection) -> None:
    """
    Создаёт стартовый набор таблиц home, если каких-то из них ещё нет.

    Порядок здесь не критичен, потому что внешних ключей между этими таблицами нет.
    """
    _create_core_coreseo(bind)
    _create_maincarousel(bind)
    _create_maintext(bind)
    _create_actions(bind)
    _create_priem(bind)
    _create_slogan1(bind)


def _create_home_indexes(bind: Connection) -> None:
    """
    Создаёт trigram-индексы для текстовых полей.

    Индексы создаются после таблиц и только при их отсутствии.
    """
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_core_coreseo_title_trgm",
        table_name="core_coreseo",
        column_name="title",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_core_coreseo_description_trgm",
        table_name="core_coreseo",
        column_name="description",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_core_coreseo_keywords_trgm",
        table_name="core_coreseo",
        column_name="keywords",
    )

    _create_trgm_index_if_missing(
        bind,
        index_name="ix_maincarousel_text_trgm",
        table_name="maincarousel",
        column_name="text",
    )

    _create_trgm_index_if_missing(
        bind,
        index_name="ix_maintext_header_trgm",
        table_name="maintext",
        column_name="header",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_maintext_text_trgm",
        table_name="maintext",
        column_name="text",
    )

    _create_trgm_index_if_missing(
        bind,
        index_name="ix_actions_text_trgm",
        table_name="actions",
        column_name="text",
    )

    _create_trgm_index_if_missing(
        bind,
        index_name="ix_priem_header_trgm",
        table_name="priem",
        column_name="header",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_priem_text_trgm",
        table_name="priem",
        column_name="text",
    )

    _create_trgm_index_if_missing(
        bind,
        index_name="ix_slogan1_text_trgm",
        table_name="slogan1",
        column_name="text",
    )


# ---------------------------------------------------------------------------
# Alembic entrypoints
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """
    Применяет стартовую схему модуля home.

    Логика intentionally idempotent:
    - extension включается через IF NOT EXISTS;
    - таблицы создаются только если их нет;
    - индексы создаются только если их нет.

    Благодаря этому миграция подходит и для:
    - полностью новой БД;
    - уже существующей legacy Django-БД.
    """
    bind = op.get_bind()

    # Расширения PostgreSQL должны включаться внутри целевой БД.
    # IF NOT EXISTS делает операцию безопасной для повторных запусков.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    _create_home_tables(bind)
    _create_home_indexes(bind)


def downgrade() -> None:
    """
    Откат этой миграции намеренно запрещён.

    Причина:
    данная ревизия может быть применена не только к новой БД, но и к уже существующей
    legacy Django-БД. Автоматический downgrade в таком случае становится опасным:
    Alembic не может надёжно отличить:
    - таблицы/индексы, созданные именно этой ревизией;
    - таблицы/индексы, которые существовали в legacy-схеме заранее.

    Поэтому лучше явно запретить downgrade, чем молча снести кусок живой базы.
    """
    raise RuntimeError(
        "Downgrade for revision '0001_home_init' is intentionally disabled. "
        "This migration can adopt an existing legacy Django database, so automatic "
        "rollback is unsafe."
    )