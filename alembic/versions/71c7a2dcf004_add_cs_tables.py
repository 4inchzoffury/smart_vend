"""add_cs_tables

Revision ID: 71c7a2dcf004
Revises: 57a3fd95c05c
Create Date: 2026-05-09 13:50:26.126668

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "71c7a2dcf004"
down_revision: Union[str, Sequence[str], None] = "57a3fd95c05c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen app_settings.value from String(200) to Text to support Gmail OAuth tokens
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(200),
            type_=sa.Text(),
            existing_nullable=False,
        )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(80), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.create_table(
        "email_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gmail_thread_id", sa.String(100), nullable=False),
        sa.Column("gmail_message_id", sa.String(100), nullable=False, unique=True),
        sa.Column("sender_email", sa.String(200), nullable=False),
        sa.Column("sender_name", sa.String(150), nullable=True),
        sa.Column("original_subject", sa.String(500), nullable=False),
        sa.Column("original_body", sa.Text(), nullable=False),
        sa.Column("draft_subject", sa.String(500), nullable=True),
        sa.Column("draft_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(150), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("gmail_message_id", name="uq_email_approvals_message_id"),
    )
    op.create_index("ix_email_approvals_thread", "email_approvals", ["gmail_thread_id"])

    op.create_table(
        "cs_governance_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cs_governance_rules")
    op.drop_index("ix_email_approvals_thread", table_name="email_approvals")
    op.drop_table("email_approvals")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(200),
            existing_nullable=False,
        )
