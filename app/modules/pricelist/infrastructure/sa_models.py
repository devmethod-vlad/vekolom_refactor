"""SQLAlchemy ORM models for the pricelist module.

These classes map the legacy Django tables used in the pricelist section
to SQLAlchemy declarative models.

Table names are preserved exactly:
* ``category``              — категории позиций прайс-листа
* ``position``              — позиции прайс-листа (с FK на category)
* ``foto``                  — фотографии к позициям (с FK на position)
* ``pricedate``             — дата прайс-листа
* ``pricelist_pricelistseo``— SEO-метаданные страницы прайс-листа

Trigram (pg_trgm) GIN-индексы добавлены на текстовые поля,
по которым может понадобиться нечёткий поиск — по аналогии с модулем home.
Индексы НЕ добавляются на поля цен (varchar(50)) и пути к файлам,
поскольку нечёткий поиск по ним не имеет смысла.
"""

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


# ---------------------------------------------------------------------------
# Category  (legacy table ``category``)
# ---------------------------------------------------------------------------


class Category(Base):
    """Категория позиций прайс-листа (legacy table ``category``)."""

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Обратная связь: все позиции, принадлежащие этой категории
    positions: Mapped[list["Position"]] = relationship(
        "Position",
        back_populates="category",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_category_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_category_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# Position  (legacy table ``position``)
# ---------------------------------------------------------------------------


class Position(Base):
    """Позиция прайс-листа (legacy table ``position``).

    Поля цен хранятся как varchar, а не числовые типы — так было в Django.
    Поля ``photo2`` / ``foto_app`` / ``foto_rss`` хранят относительные пути
    к изображениям (``media/filename.jpg``), аналогично ``MainCarousel.photo``.
    ``photo2_webp`` / ``avatar_webp`` — URL-пути (``/media/media/name.webp``).
    """

    __tablename__ = "position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SEO-поля позиции
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    seodescrip: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Флаг отображения на главной странице
    check_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Порядок сортировки в прайсе
    order: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Цены: Безналичный расчет (На карту физ.лица) ---
    price_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    price: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price2_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    price_2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price3_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    price_3: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Цены: Безналичный расчет (Лицензия юр.лица) ---
    price_card_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    price_card: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price2_card_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    price2_card: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Изображения ---
    photo2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo2_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)
    avatar_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)
    foto_app: Mapped[str | None] = mapped_column(String(100), nullable=True)
    foto_rss: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- FK на категорию ---
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("category.id"),
        nullable=False,
    )

    # Связи
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="positions",
        lazy="selectin",
    )
    fotos: Mapped[list["Foto"]] = relationship(
        "Foto",
        back_populates="position",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_position_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_position_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index(
            "ix_position_rules_trgm",
            "rules",
            postgresql_using="gin",
            postgresql_ops={"rules": "gin_trgm_ops"},
        ),
        # Индекс на category_id уже есть в legacy-схеме (idx_17449_position_category_id_...),
        # но ORM-определение ForeignKey автоматически не создаёт индекс в SQLAlchemy —
        # при необходимости Alembic добавит его отдельно.
    )


# ---------------------------------------------------------------------------
# Foto  (legacy table ``foto``)
# ---------------------------------------------------------------------------


class Foto(Base):
    """Фотография позиции прайс-листа (legacy table ``foto``).

    ``foto`` — относительный путь к JPEG (``media/filename.jpg``).
    ``foto_webp`` — URL-путь к WebP-версии (``/media/media/name.webp``).
    ``text`` — подпись к фотографии.
    """

    __tablename__ = "foto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    foto: Mapped[str | None] = mapped_column(String(100), nullable=True)
    foto_webp: Mapped[str | None] = mapped_column(String(600), nullable=True)
    text: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # FK на позицию
    position_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("position.id"),
        nullable=False,
    )

    # Связь
    position: Mapped["Position"] = relationship(
        "Position",
        back_populates="fotos",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_foto_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# PriceDate  (legacy table ``pricedate``)
# ---------------------------------------------------------------------------


class PriceDate(Base):
    """Дата актуальности прайс-листа (legacy table ``pricedate``)."""

    __tablename__ = "pricedate"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    date: Mapped[str | None] = mapped_column(String(100), nullable=True)


# ---------------------------------------------------------------------------
# PricelistSeo  (legacy table ``pricelist_pricelistseo``)
# ---------------------------------------------------------------------------


class PricelistSeo(Base):
    """SEO-метаданные для страницы прайс-листа (legacy table ``pricelist_pricelistseo``)."""

    __tablename__ = "pricelist_pricelistseo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_pricelist_pricelistseo_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_pricelist_pricelistseo_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index(
            "ix_pricelist_pricelistseo_keywords_trgm",
            "keywords",
            postgresql_using="gin",
            postgresql_ops={"keywords": "gin_trgm_ops"},
        ),
    )
