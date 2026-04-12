"""add apikeys module tables

Revision ID: 0004_add_apikeys
Revises: <PREVIOUS_REVISION>
Create Date: 2026-03-22

Создаёт таблицы для модуля apikeys:
  - apikeys_yandex_maps   — хранение ключей API Яндекс.Карт
  - apikeys_smartcaptcha   — хранение ключей Yandex SmartCaptcha

Миграция идемпотентна: использует IF NOT EXISTS для таблиц.
Совместима с legacy-adoption паттерном, принятым в проекте.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_add_apikeys"
down_revision = "0003_contacts_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- apikeys_yandex_maps ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS apikeys_yandex_maps (
            id          BIGSERIAL PRIMARY KEY,
            api_key     VARCHAR(255) NOT NULL,
            description TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE
        );
        """
    )

    # --- apikeys_smartcaptcha ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS apikeys_smartcaptcha (
            id          BIGSERIAL PRIMARY KEY,
            client_key  VARCHAR(255) NOT NULL,
            server_key  VARCHAR(255) NOT NULL,
            description TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS apikeys_smartcaptcha;")
    op.execute("DROP TABLE IF EXISTS apikeys_yandex_maps;")
