"""add_task_sort_order

Revision ID: c4d8e2f1a9b3
Revises: 71c7a2dcf004
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2f1a9b3"
down_revision: Union[str, Sequence[str], None] = "71c7a2dcf004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_tasks",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill: preserve insertion order within each section using the row id
    op.execute("UPDATE research_tasks SET sort_order = id")


def downgrade() -> None:
    op.drop_column("research_tasks", "sort_order")
