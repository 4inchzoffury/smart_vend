"""add crm tables

Revision ID: a1b2c3d4e5f6
Revises: 10f8a8a74f0c
Create Date: 2026-05-12 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "10f8a8a74f0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(150), nullable=True),
        sa.Column("contact_title", sa.String(100), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("account_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("prospect_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_number"),
    )

    op.create_table(
        "crm_client_billing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("billing_email", sa.String(200), nullable=True),
        sa.Column("billing_phone", sa.String(30), nullable=True),
        sa.Column("billing_address", sa.String(300), nullable=True),
        sa.Column("billing_city", sa.String(100), nullable=True),
        sa.Column("billing_state", sa.String(2), nullable=True),
        sa.Column("billing_zip", sa.String(10), nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("payment_terms", sa.String(10), nullable=True),
        sa.Column("auto_pay", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("tax_id", sa.String(20), nullable=True),
        sa.Column("tax_exempt", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["crm_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )

    op.create_table(
        "crm_client_sites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("site_name", sa.String(150), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=False, server_default="Panama City"),
        sa.Column("state", sa.String(2), nullable=False, server_default="FL"),
        sa.Column("zip_code", sa.String(10), nullable=True),
        sa.Column("contact_name", sa.String(150), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("commission_pct", sa.Float(), nullable=True),
        sa.Column("contract_start", sa.Date(), nullable=True),
        sa.Column("contract_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["crm_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "crm_client_equipment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("equipment_type", sa.String(30), nullable=True),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(150), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("placement_description", sa.String(300), nullable=True),
        sa.Column("install_date", sa.Date(), nullable=True),
        sa.Column("last_service_date", sa.Date(), nullable=True),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("monthly_fee", sa.Float(), nullable=True),
        sa.Column("commission_pct", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["crm_clients.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["crm_client_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "crm_client_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("note_type", sa.String(20), nullable=False, server_default="general"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["crm_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "crm_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("invoice_number", sa.String(30), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("paid_amount", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["crm_clients.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["crm_client_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )


def downgrade() -> None:
    op.drop_table("crm_invoices")
    op.drop_table("crm_client_notes")
    op.drop_table("crm_client_equipment")
    op.drop_table("crm_client_sites")
    op.drop_table("crm_client_billing")
    op.drop_table("crm_clients")
