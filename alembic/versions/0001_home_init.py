"""home: initial schema

Revision ID: 0001_home_init
Revises:
Create Date: 2025-12-21

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_home_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions must be enabled inside the target DB.
    # IF NOT EXISTS makes it safe to run multiple times.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # core_coreseo
    op.create_table(
        "core_coreseo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_core_coreseo_title_trgm",
        "core_coreseo",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_core_coreseo_description_trgm",
        "core_coreseo",
        ["description"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_core_coreseo_keywords_trgm",
        "core_coreseo",
        ["keywords"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"keywords": "gin_trgm_ops"},
    )

    # maincarousel
    op.create_table(
        "maincarousel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("photo", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("photo_amp", sa.String(length=300), nullable=True),
        sa.Column("photo_turbo", sa.String(length=300), nullable=True),
        sa.Column("photo_webp", sa.String(length=300), nullable=True),
    )
    op.create_index(
        "ix_maincarousel_text_trgm",
        "maincarousel",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    # maintext
    op.create_table(
        "maintext",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_maintext_header_trgm",
        "maintext",
        ["header"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"header": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_maintext_text_trgm",
        "maintext",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    # actions
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_actions_text_trgm",
        "actions",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    # priem
    op.create_table(
        "priem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_priem_header_trgm",
        "priem",
        ["header"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"header": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_priem_text_trgm",
        "priem",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    # slogan1
    op.create_table(
        "slogan1",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_slogan1_text_trgm",
        "slogan1",
        ["text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_slogan1_text_trgm", table_name="slogan1")
    op.drop_table("slogan1")

    op.drop_index("ix_priem_header_trgm", table_name="priem")
    op.drop_index("ix_priem_text_trgm", table_name="priem")
    op.drop_table("priem")

    op.drop_index("ix_actions_text_trgm", table_name="actions")
    op.drop_table("actions")

    op.drop_index("ix_maintext_header_trgm", table_name="maintext")
    op.drop_index("ix_maintext_text_trgm", table_name="maintext")
    op.drop_table("maintext")

    op.drop_index("ix_maincarousel_text_trgm", table_name="maincarousel")
    op.drop_table("maincarousel")

    op.drop_index("ix_core_coreseo_keywords_trgm", table_name="core_coreseo")
    op.drop_index("ix_core_coreseo_description_trgm", table_name="core_coreseo")
    op.drop_index("ix_core_coreseo_title_trgm", table_name="core_coreseo")
    op.drop_table("core_coreseo")

    # Обычно расширения на downgrade не трогают:
    # op.execute('DROP EXTENSION IF EXISTS "pg_trgm";')
