from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    supplier_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    products: Mapped[list[Product]] = relationship(back_populates="primary_supplier")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    case_pack_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_seasonal: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    primary_supplier: Mapped[Supplier | None] = relationship(back_populates="products")
    restock_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    par_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    on_hand_qty: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    inventory_logs: Mapped[list[InventoryLog]] = relationship(back_populates="product")


class InventoryLog(Base):
    __tablename__ = "inventory_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped[Product] = relationship(back_populates="inventory_logs")
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id"), nullable=True)
    log_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty_change: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_cost_at_log: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    logged_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
