"""supplier onboarding fields: account_status, priority, address

Revision ID: g2h3i4j5k6l7
Revises: e8d2c4b6a1f9
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, Sequence[str], None] = "e8d2c4b6a1f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Three new columns on suppliers to support the "open these accounts"
    # workflow on the Inventory → Suppliers tab.
    # `server_default` covers existing rows; the model defaults handle new ones.
    with op.batch_alter_table("suppliers") as batch:
        batch.add_column(sa.Column("address", sa.String(300), nullable=True))
        batch.add_column(
            sa.Column(
                "account_status",
                sa.String(20),
                nullable=False,
                server_default="not_started",
            )
        )
        batch.add_column(
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default="100",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("suppliers") as batch:
        batch.drop_column("priority")
        batch.drop_column("account_status")
        batch.drop_column("address")
