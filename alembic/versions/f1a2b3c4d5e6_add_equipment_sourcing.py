"""add distributors + equipment sources, equipment lifecycle/pricing columns

Revision ID: f1a2b3c4d5e6
Revises: d5e9f1a2b7c4
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d5e9f1a2b7c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── new equipment_units columns (server_default backfills existing rows) ──
    op.add_column(
        "equipment_units",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.add_column(
        "equipment_units",
        sa.Column("price_is_starting", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "equipment_units",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # ── distributors (supplier directory) ──
    op.create_table(
        "distributors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("website", sa.String(300), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column(
            "distributor_type", sa.String(20), nullable=False, server_default="distributor"
        ),
        sa.Column("financing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fast_ship", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── equipment_sources (one distributor's offer for one unit) ──
    op.create_table(
        "equipment_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipment_unit_id", sa.Integer(), nullable=False),
        sa.Column("distributor_id", sa.Integer(), nullable=False),
        sa.Column("distributor_url", sa.String(500), nullable=True),
        sa.Column("price_low", sa.Integer(), nullable=True),
        sa.Column("price_high", sa.Integer(), nullable=True),
        sa.Column("price_notes", sa.String(300), nullable=True),
        sa.Column("lead_time_days_min", sa.Integer(), nullable=True),
        sa.Column("lead_time_days_max", sa.Integer(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stock_notes", sa.String(200), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_verified", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["equipment_unit_id"], ["equipment_units.id"]),
        sa.ForeignKeyConstraint(["distributor_id"], ["distributors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_equipment_sources_equipment_unit_id",
        "equipment_sources",
        ["equipment_unit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_equipment_sources_equipment_unit_id", table_name="equipment_sources")
    op.drop_table("equipment_sources")
    op.drop_table("distributors")
    op.drop_column("equipment_units", "is_locked")
    op.drop_column("equipment_units", "price_is_starting")
    op.drop_column("equipment_units", "status")
