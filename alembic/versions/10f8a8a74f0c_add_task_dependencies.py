"""add task_dependencies

Revision ID: 10f8a8a74f0c
Revises: c4d8e2f1a9b3
Create Date: 2026-05-12 19:17:42.042676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10f8a8a74f0c'
down_revision: Union[str, Sequence[str], None] = 'c4d8e2f1a9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("depends_on_task_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
    )


def downgrade() -> None:
    op.drop_table("task_dependencies")
