"""create comfort_aggregate_stats table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comfort_aggregate_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("is_crisis", sa.Boolean(), nullable=False),
        sa.Column("emotional_tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("situational_tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("time_bucket", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("comfort_aggregate_stats")
