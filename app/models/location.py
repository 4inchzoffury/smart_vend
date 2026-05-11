from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.financial import MachineProForma
    from app.models.sales import Prospect


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Panama City")
    state: Mapped[str] = mapped_column(String(2), default="FL")
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    venue_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    foot_traffic_estimate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    foot_traffic_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_status: Mapped[str] = mapped_column(String(20), default="none")
    commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="prospect")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    machines: Mapped[list[Machine]] = relationship(back_populates="location")
    proformas: Mapped[list[MachineProForma]] = relationship(back_populates="location")
    prospects: Mapped[list[Prospect]] = relationship(back_populates="location")


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    machine_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    financing_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_storage")
    deployment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    location: Mapped[Location | None] = relationship(back_populates="machines")
