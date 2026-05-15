from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.sales import Prospect


class Client(Base):
    __tablename__ = "crm_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    prospect_id: Mapped[int | None] = mapped_column(ForeignKey("prospects.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    prospect: Mapped[Prospect | None] = relationship()
    billing: Mapped[ClientBilling | None] = relationship(back_populates="client", uselist=False)
    sites: Mapped[list[ClientSite]] = relationship(
        back_populates="client", order_by="ClientSite.site_name"
    )
    notes_list: Mapped[list[ClientNote]] = relationship(
        back_populates="client", order_by="ClientNote.created_at.desc()"
    )
    invoices: Mapped[list[ClientInvoice]] = relationship(
        back_populates="client", order_by="ClientInvoice.invoice_date.desc()"
    )


class ClientBilling(Base):
    __tablename__ = "crm_client_billing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("crm_clients.id"), nullable=False, unique=True
    )
    billing_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    billing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    billing_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(10), nullable=True)
    auto_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    client: Mapped[Client] = relationship(back_populates="billing")


class ClientSite(Base):
    __tablename__ = "crm_client_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("crm_clients.id"), nullable=False)
    site_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Panama City")
    state: Mapped[str] = mapped_column(String(2), default="FL")
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    client: Mapped[Client] = relationship(back_populates="sites")
    equipment: Mapped[list[ClientEquipment]] = relationship(
        back_populates="site", order_by="ClientEquipment.placement_description"
    )
    invoices: Mapped[list[ClientInvoice]] = relationship(back_populates="site")


class ClientEquipment(Base):
    __tablename__ = "crm_client_equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("crm_clients.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("crm_client_sites.id"), nullable=False)
    equipment_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    placement_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    install_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    client: Mapped[Client] = relationship()
    site: Mapped[ClientSite] = relationship(back_populates="equipment")


class ClientNote(Base):
    __tablename__ = "crm_client_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("crm_clients.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(20), default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    client: Mapped[Client] = relationship(back_populates="notes_list")


class ClientInvoice(Base):
    __tablename__ = "crm_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("crm_clients.id"), nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("crm_client_sites.id"), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    client: Mapped[Client] = relationship(back_populates="invoices")
    site: Mapped[ClientSite | None] = relationship(back_populates="invoices")
