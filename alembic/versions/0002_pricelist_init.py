"""pricelist: initial schema / legacy adoption migration

Revision ID: 0002_pricelist_init
Revises: 0001_home_init
Create Date: 2025-12-22

Эта миграция выполняет те же две роли, что и 0001_home_init:

1) Для новой пустой базы данных:
   - создаёт таблицы модуля `pricelist`;
   - создаёт trigram-индексы.

2) Для уже существующей legacy Django-БД:
   - не пытается пересоздать уже имеющиеся таблицы;
   - не удаляет и не ломает существующую схему;
   - добавляет только отсутствующие таблицы и отсутствующие trigram-индексы.

Таблицы модуля pricelist:
  - category              — категории позиций
  - position              — позиции прайс-листа (FK → category)
  - foto                  — фотографии к позициям (FK → position)
  - pricedate             — дата прайс-листа
  - pricelist_pricelistseo — SEO-метаданные страницы прайс-листа

Порядок создания таблиц важен из-за FK:
  category → position → foto
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.engine.reflection import Inspector


revision = "0002_pricelist_init"
down_revision = "0001_home_init"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Вспомогательные функции инспекции схемы (повторяют 0001_home_init)
# ---------------------------------------------------------------------------


def _inspector(bind: Connection) -> Inspector:
    """Создаёт Inspector для текущего bind."""
    return sa.inspect(bind)


def _table_exists(bind: Connection, table_name: str) -> bool:
    """Проверяет существование таблицы в схеме public."""
    insp = _inspector(bind)
    return table_name in insp.get_table_names(schema="public")


def _column_exists(bind: Connection, table_name: str, column_name: str) -> bool:
    """Проверяет существование колонки в таблице."""
    if not _table_exists(bind, table_name):
        return False
    insp = _inspector(bind)
    columns = insp.get_columns(table_name, schema="public")
    return any(col["name"] == column_name for col in columns)


def _index_exists(bind: Connection, table_name: str, index_name: str) -> bool:
    """Проверяет существование индекса по имени."""
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
    """Создаёт таблицу только если её ещё нет."""
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
    """Создаёт trigram GIN-индекс только если таблица, колонка и индекс ещё не существуют."""
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
# Описание стартовых таблиц модуля pricelist
# ---------------------------------------------------------------------------


def _create_category(bind: Connection) -> None:
    """
    Таблица категорий прайс-листа.

    Legacy Django-схема:
        id          bigserial primary key
        name        varchar(100)
        description text
    """
    _create_table_if_missing(
        bind,
        "category",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )


def _create_position(bind: Connection) -> None:
    """
    Таблица позиций прайс-листа.

    Legacy Django-схема: см. django_database.txt, таблица position.
    FK: category_id → category(id)
    """
    _create_table_if_missing(
        bind,
        "position",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("seodescrip", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("check_flag", sa.Boolean(), nullable=False),
        sa.Column("order", sa.Float(), nullable=True),
        sa.Column("price_title", sa.String(length=400), nullable=True),
        sa.Column("price", sa.String(length=50), nullable=True),
        sa.Column("price2_title", sa.String(length=400), nullable=True),
        sa.Column("price_2", sa.String(length=50), nullable=True),
        sa.Column("price3_title", sa.String(length=400), nullable=True),
        sa.Column("price_3", sa.String(length=50), nullable=True),
        sa.Column("price_card_title", sa.String(length=400), nullable=True),
        sa.Column("price_card", sa.String(length=50), nullable=True),
        sa.Column("price2_card_title", sa.String(length=400), nullable=True),
        sa.Column("price2_card", sa.String(length=50), nullable=True),
        sa.Column("photo2", sa.String(length=100), nullable=True),
        sa.Column("photo2_webp", sa.String(length=600), nullable=True),
        sa.Column("avatar_webp", sa.String(length=600), nullable=True),
        sa.Column("foto_app", sa.String(length=100), nullable=True),
        sa.Column("foto_rss", sa.String(length=100), nullable=True),
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("category.id"),
            nullable=False,
        ),
    )


def _create_foto(bind: Connection) -> None:
    """
    Таблица фотографий к позициям прайс-листа.

    Legacy Django-схема:
        id          bigserial primary key
        foto        varchar(100)
        text        varchar(400)
        position_id bigint not null → FK position(id)
        foto_webp   varchar(600)
    """
    _create_table_if_missing(
        bind,
        "foto",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("foto", sa.String(length=100), nullable=True),
        sa.Column("foto_webp", sa.String(length=600), nullable=True),
        sa.Column("text", sa.String(length=400), nullable=True),
        sa.Column(
            "position_id",
            sa.BigInteger(),
            sa.ForeignKey("position.id"),
            nullable=False,
        ),
    )


def _create_pricedate(bind: Connection) -> None:
    """
    Таблица даты прайс-листа.

    Legacy Django-схема:
        id   bigserial primary key
        date varchar(100)
    """
    _create_table_if_missing(
        bind,
        "pricedate",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.String(length=100), nullable=True),
    )


def _create_pricelist_pricelistseo(bind: Connection) -> None:
    """
    Таблица SEO-метаданных страницы прайс-листа.

    Legacy Django-схема:
        id          bigserial primary key
        title       text
        description text
        keywords    text
    """
    _create_table_if_missing(
        bind,
        "pricelist_pricelistseo",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
    )


def _create_pricelist_tables(bind: Connection) -> None:
    """
    Создаёт стартовый набор таблиц pricelist, если каких-то из них ещё нет.

    Порядок важен из-за FK: category → position → foto.
    """
    _create_category(bind)
    _create_position(bind)
    _create_foto(bind)
    _create_pricedate(bind)
    _create_pricelist_pricelistseo(bind)


def _create_pricelist_indexes(bind: Connection) -> None:
    """
    Создаёт trigram-индексы для текстовых полей модуля pricelist.

    Индексы создаются после таблиц и только при их отсутствии.
    """
    # -- category --
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_category_name_trgm",
        table_name="category",
        column_name="name",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_category_description_trgm",
        table_name="category",
        column_name="description",
    )

    # -- position --
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_position_name_trgm",
        table_name="position",
        column_name="name",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_position_description_trgm",
        table_name="position",
        column_name="description",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_position_rules_trgm",
        table_name="position",
        column_name="rules",
    )

    # -- foto --
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_foto_text_trgm",
        table_name="foto",
        column_name="text",
    )

    # -- pricelist_pricelistseo --
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_pricelist_pricelistseo_title_trgm",
        table_name="pricelist_pricelistseo",
        column_name="title",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_pricelist_pricelistseo_description_trgm",
        table_name="pricelist_pricelistseo",
        column_name="description",
    )
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_pricelist_pricelistseo_keywords_trgm",
        table_name="pricelist_pricelistseo",
        column_name="keywords",
    )


# ---------------------------------------------------------------------------
# Alembic entrypoints
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """
    Применяет стартовую схему модуля pricelist.

    Логика intentionally idempotent:
    - таблицы создаются только если их нет;
    - индексы создаются только если их нет.

    Благодаря этому миграция подходит и для:
    - полностью новой БД;
    - уже существующей legacy Django-БД.
    """
    bind = op.get_bind()

    _create_pricelist_tables(bind)
    _create_pricelist_indexes(bind)


def downgrade() -> None:
    """
    Откат этой миграции намеренно запрещён.

    Причина аналогична 0001_home_init:
    данная ревизия может быть применена к legacy Django-БД, и автоматический
    downgrade рискует снести таблицы, которые существовали до Alembic.
    """
    raise RuntimeError(
        "Downgrade for revision '0002_pricelist_init' is intentionally disabled. "
        "This migration can adopt an existing legacy Django database, so automatic "
        "rollback is unsafe."
    )
