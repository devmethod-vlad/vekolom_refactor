"""home: initial schema

Revision ID: 0001_home_init
Revises: 
Create Date: 2025-12-21

This migration creates the legacy home-page tables from the old Django project,
but with two extra generic columns on list-like tables:
* sort_order (int, default 0)
* is_active (bool, default true)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_home_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # core_coreseo
    op.create_table(
        "core_coreseo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
    )

    # maincarousel
    op.create_table(
        "maincarousel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("photo", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("photo_amp", sa.String(length=300), nullable=True),
        sa.Column("photo_turbo", sa.String(length=300), nullable=True),
        sa.Column("photo_webp", sa.String(length=600), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_maincarousel_active_order",
        "maincarousel",
        ["is_active", "sort_order", "id"],
        unique=False,
    )

    # maintext
    op.create_table(
        "maintext",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_maintext_active_order",
        "maintext",
        ["is_active", "sort_order", "id"],
        unique=False,
    )

    # actions
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_actions_active_order",
        "actions",
        ["is_active", "sort_order", "id"],
        unique=False,
    )

    # priem
    op.create_table(
        "priem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("header", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_priem_active_order",
        "priem",
        ["is_active", "sort_order", "id"],
        unique=False,
    )

    # slogan1
    op.create_table(
        "slogan1",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_slogan1_active_order",
        "slogan1",
        ["is_active", "sort_order", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_slogan1_active_order", table_name="slogan1")
    op.drop_table("slogan1")

    op.drop_index("ix_priem_active_order", table_name="priem")
    op.drop_table("priem")

    op.drop_index("ix_actions_active_order", table_name="actions")
    op.drop_table("actions")

    op.drop_index("ix_maintext_active_order", table_name="maintext")
    op.drop_table("maintext")

    op.drop_index("ix_maincarousel_active_order", table_name="maincarousel")
    op.drop_table("maincarousel")

    op.drop_table("core_coreseo")
