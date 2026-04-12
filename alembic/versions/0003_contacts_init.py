"""contacts: initial schema / legacy adoption migration

Revision ID: 0003_contacts_init
Revises: 0002_pricelist_init
Create Date: 2025-12-23

Эта миграция выполняет те же две роли, что и 0001_home_init / 0002_pricelist_init:

1) Для новой пустой базы данных:
   - создаёт таблицы модуля `contacts`;
   - создаёт trigram-индексы.

2) Для уже существующей legacy Django-БД:
   - не пытается пересоздать уже имеющиеся таблицы;
   - не удаляет и не ломает существующую схему;
   - добавляет только отсутствующие таблицы и отсутствующие trigram-индексы.

Таблицы модуля contacts:
  - contacts              — текст контактной информации
  - contacts_contactsseo  — SEO-метаданные страницы контактов
  - mess_messages         — сообщения из контактной формы

Между таблицами нет внешних ключей, порядок создания не критичен.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.engine.reflection import Inspector


revision = "0003_contacts_init"
down_revision = "0002_pricelist_init"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Вспомогательные функции инспекции схемы (повторяют 0001_home_init)
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
# Описание стартовых таблиц модуля contacts
# ---------------------------------------------------------------------------


def _create_contacts(bind: Connection) -> None:
    """
    Таблица текста контактов.

    Legacy Django-схема:
        id   bigserial primary key
        text text
    """
    _create_table_if_missing(
        bind,
        "contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=True),
    )


def _create_contacts_contactsseo(bind: Connection) -> None:
    """
    Таблица SEO для страницы контактов.

    Legacy Django-схема:
        id          bigserial primary key
        title       text
        description text
        keywords    text
    """
    _create_table_if_missing(
        bind,
        "contacts_contactsseo",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
    )


def _create_mess_messages(bind: Connection) -> None:
    """
    Таблица сообщений из контактной формы.

    Legacy Django-схема:
        id      bigserial primary key
        name    varchar(100) default NULL
        mail    varchar(100) default NULL
        phone   varchar(100) default NULL
        message text
    """
    _create_table_if_missing(
        bind,
        "mess_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("mail", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
    )


def _create_contacts_tables(bind: Connection) -> None:
    """
    Создаёт стартовый набор таблиц contacts, если каких-то из них ещё нет.

    Между таблицами нет внешних ключей, порядок не критичен.
    """
    _create_contacts(bind)
    _create_contacts_contactsseo(bind)
    _create_mess_messages(bind)


def _create_contacts_indexes(bind: Connection) -> None:
    """
    Создаёт trigram-индексы для текстовых полей.

    Индексы создаются после таблиц и только при их отсутствии.
    """
    # contacts.text
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_contacts_text_trgm",
        table_name="contacts",
        column_name="text",
    )

    # contacts_contactsseo.title
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_contacts_contactsseo_title_trgm",
        table_name="contacts_contactsseo",
        column_name="title",
    )
    # contacts_contactsseo.description
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_contacts_contactsseo_description_trgm",
        table_name="contacts_contactsseo",
        column_name="description",
    )
    # contacts_contactsseo.keywords
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_contacts_contactsseo_keywords_trgm",
        table_name="contacts_contactsseo",
        column_name="keywords",
    )

    # mess_messages.message
    _create_trgm_index_if_missing(
        bind,
        index_name="ix_mess_messages_message_trgm",
        table_name="mess_messages",
        column_name="message",
    )


# ---------------------------------------------------------------------------
# Alembic entrypoints
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """
    Применяет стартовую схему модуля contacts.

    Логика intentionally idempotent:
    - таблицы создаются только если их нет;
    - индексы создаются только если их нет.

    Благодаря этому миграция подходит и для:
    - полностью новой БД;
    - уже существующей legacy Django-БД.
    """
    bind = op.get_bind()

    _create_contacts_tables(bind)
    _create_contacts_indexes(bind)


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
        "Downgrade for revision '0003_contacts_init' is intentionally disabled. "
        "This migration can adopt an existing legacy Django database, so automatic "
        "rollback is unsafe."
    )
