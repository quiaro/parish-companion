"""create parishioners and comfort_sent_passages tables

Revision ID: 0001
Revises:
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parishioners",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("comfort_intro_shown", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("comfort_last_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "comfort_sent_passages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "telegram_user_id",
            sa.BigInteger(),
            sa.ForeignKey("parishioners.telegram_user_id"),
            nullable=False,
        ),
        sa.Column("passage_reference", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_sent_passages_user_time",
        "comfort_sent_passages",
        ["telegram_user_id", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_sent_passages_user_time", table_name="comfort_sent_passages")
    op.drop_table("comfort_sent_passages")
    op.drop_table("parishioners")
