"""add_proforma_processing_and_equipment_fields

Adds per-transaction SaaS/processing cost fields and a soft equipment link to
machine_proformas. server_default backfills existing rows (0 fees, no link), so
old scenarios calculate identically to before.

Revision ID: e8d2c4b6a1f9
Revises: b7c1d2e3f4a5
Create Date: 2026-05-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8d2c4b6a1f9"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Named so downgrade can drop it on every dialect. Adding a column WITH a foreign
# key needs batch mode on SQLite (copy-and-move); Postgres runs plain ALTERs.
_FK_NAME = "fk_machine_proformas_equipment_unit"


def upgrade() -> None:
    with op.batch_alter_table("machine_proformas") as batch:
        batch.add_column(
            sa.Column("processing_fee_pct", sa.Float(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("processing_fee_per_txn", sa.Float(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("equipment_unit_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            _FK_NAME, "equipment_units", ["equipment_unit_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("machine_proformas") as batch:
        batch.drop_constraint(_FK_NAME, type_="foreignkey")
        batch.drop_column("equipment_unit_id")
        batch.drop_column("processing_fee_per_txn")
        batch.drop_column("processing_fee_pct")
