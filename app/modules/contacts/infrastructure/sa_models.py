"""SQLAlchemy ORM models for the contacts module.

These classes map the legacy Django tables used on the contacts page to
SQLAlchemy declarative models.

Table names are preserved exactly:
* ``contacts``              — текст контактной информации
* ``contacts_contactsseo``  — SEO-метаданные страницы контактов
* ``mess_messages``         — сообщения из контактной формы

Trigram (pg_trgm) GIN-индексы добавлены на текстовые поля,
по которым может понадобиться нечёткий поиск — по аналогии с модулями home и pricelist.

Индексы НЕ добавляются на короткие поля name/mail/phone (varchar(100)),
поскольку для таких полей обычный B-tree более эффективен.
trgm-индексы применяются к text-полям с потенциально длинным текстовым содержимым.
"""

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


# ---------------------------------------------------------------------------
# Contacts  (legacy table ``contacts``)
# ---------------------------------------------------------------------------


class Contacts(Base):
    """Текст контактной информации (legacy table ``contacts``).

    В Django использовался RichTextField('Текст контактов').
    Поле ``text`` хранит HTML-разметку.

    Legacy Django-схема:
        id   bigserial primary key
        text text
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_contacts_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# ContactsSeo  (legacy table ``contacts_contactsseo``)
# ---------------------------------------------------------------------------


class ContactsSeo(Base):
    """SEO-метаданные для страницы контактов (legacy table ``contacts_contactsseo``).

    Legacy Django-схема:
        id          bigserial primary key
        title       text
        description text
        keywords    text
    """

    __tablename__ = "contacts_contactsseo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_contacts_contactsseo_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_contacts_contactsseo_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index(
            "ix_contacts_contactsseo_keywords_trgm",
            "keywords",
            postgresql_using="gin",
            postgresql_ops={"keywords": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# MessMessages  (legacy table ``mess_messages``)
# ---------------------------------------------------------------------------


class MessMessages(Base):
    """Сообщение из контактной формы (legacy table ``mess_messages``).

    Соответствует модели Messages из Django-приложения mess.
    В Django view contacts() при успешной отправке формы вызывался:
        Messages.objects.create(name=..., phone=..., mail=..., message=...)

    Legacy Django-схема:
        id      bigserial primary key
        name    varchar(100) default NULL
        mail    varchar(100) default NULL
        phone   varchar(100) default NULL
        message text
    """

    __tablename__ = "mess_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_mess_messages_message_trgm",
            "message",
            postgresql_using="gin",
            postgresql_ops={"message": "gin_trgm_ops"},
        ),
    )
