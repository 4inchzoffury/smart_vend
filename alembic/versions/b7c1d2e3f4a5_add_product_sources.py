"""add product_sources (per-supplier price comparison for products)

Revision ID: b7c1d2e3f4a5
Revises: f1a2b3c4d5e6
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One supplier's offer for one product. Per-unit cost (unit_cost, else
    # case_price / case_pack_qty) is the price-comparison key.
    op.create_table(
        "product_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("supplier_url", sa.String(500), nullable=True),
        sa.Column("case_price", sa.Float(), nullable=True),
        sa.Column("case_pack_qty", sa.Integer(), nullable=True),
        sa.Column("unit_cost", sa.Float(), nullable=True),
        sa.Column("unit_size", sa.String(50), nullable=True),
        sa.Column("min_order", sa.String(100), nullable=True),
        sa.Column("price_notes", sa.String(300), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stock_notes", sa.String(200), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("last_verified", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_sources_product_id",
        "product_sources",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_sources_product_id", table_name="product_sources")
    op.drop_table("product_sources")
