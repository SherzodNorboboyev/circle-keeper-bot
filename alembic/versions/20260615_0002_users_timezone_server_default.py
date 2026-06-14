"""users timezone server default

Revision ID: 20260615_0002
Revises: 1ebf3d0e7ee4
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260615_0002"
down_revision = "1ebf3d0e7ee4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "timezone",
                existing_type=sa.String(length=64),
                nullable=False,
                server_default="Asia/Tashkent",
            )
        return

    op.alter_column(
        "users",
        "timezone",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default="Asia/Tashkent",
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "timezone",
                existing_type=sa.String(length=64),
                nullable=False,
                server_default=None,
            )
        return

    op.alter_column(
        "users",
        "timezone",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default=None,
    )
