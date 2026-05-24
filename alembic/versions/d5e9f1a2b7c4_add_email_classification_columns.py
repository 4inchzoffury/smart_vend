"""add_email_classification_columns

Revision ID: d5e9f1a2b7c4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e9f1a2b7c4"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # category buckets inbound mail: customer | vendor | promotional | internal
    # | spam | other | unclassified. server_default backfills existing rows.
    op.add_column(
        "email_approvals",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="unclassified",
        ),
    )
    op.add_column(
        "email_approvals",
        sa.Column("classification_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_approvals", "classification_reason")
    op.drop_column("email_approvals", "category")
