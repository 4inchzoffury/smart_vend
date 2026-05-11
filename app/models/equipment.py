from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EquipmentUnit(Base):
    __tablename__ = "equipment_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    reseller: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # smart_cooler | freezer | ambient | kiosk | micro_market

    # Pricing — null means contact required
    price_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    monthly_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_fee_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Warranty
    warranty_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    extended_warranty_available: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    extended_warranty_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Dimensions
    height_in: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_in: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_in: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_lbs: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Capacity & technology
    capacity_cu_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operating_temp_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_temp_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    connectivity: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_types: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_features: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    certifications: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Delivery
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Reference & metadata
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_confidence: Mapped[str] = mapped_column(String(20), default="seeded", nullable=False)
    # seeded | ai_refreshed | verified
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
