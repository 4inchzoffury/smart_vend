from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmailApproval(Base):
    __tablename__ = "email_approvals"
    __table_args__ = (
        Index("ix_email_approvals_thread", "gmail_thread_id"),
        UniqueConstraint("gmail_message_id", name="uq_email_approvals_message_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(100), nullable=False)
    gmail_message_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    original_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    original_body: Mapped[str] = mapped_column(Text, nullable=False)
    draft_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # customer | vendor | promotional | internal | spam | other | unclassified
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="unclassified")
    # One-line rationale from the classifier (powers the "why was this filtered" UI).
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | approved | rejected | sent | draft_failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
