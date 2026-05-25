from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EquipmentUnit(Base):
    __tablename__ = "equipment_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    reseller: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # smart_cooler | freezer | combo | drink | snack | glass_cooler | kiosk | micro_market

    # Lifecycle — archived units stay in the DB (reversible) but drop off the catalog.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # active | archived

    # Pricing — null means contact required. With multi-distributor sourcing these denormalize
    # the *best* (lowest) price across the unit's sources; recompute_best_price() keeps them
    # in sync. price_is_starting drives a "Starting at $X" label (micro markets / kiosks).
    price_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_is_starting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    monthly_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_fee_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # When True, the AI spec-refresh job leaves this unit untouched. Set on curated/verified
    # rows so an auto-refresh can't clobber hand-checked pricing (the cause of past drift).
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    sources: Mapped[list[EquipmentSource]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="EquipmentSource.price_low",
    )

    # ── derived sourcing helpers ──────────────────────────────────────────────
    @property
    def priced_sources(self) -> list[EquipmentSource]:
        """Sources that carry a usable low price, cheapest first."""
        return sorted(
            (s for s in self.sources if s.price_low is not None),
            key=lambda s: s.price_low,  # type: ignore[arg-type,return-value]
        )

    @property
    def best_source(self) -> EquipmentSource | None:
        """The cheapest distributor offering, used for the catalog 'best buy' badge."""
        priced = self.priced_sources
        return priced[0] if priced else None

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def recompute_best_price(self) -> None:
        """Sync denormalized price_low/price_high from the cheapest source.

        Catalog cards and filters read the unit-level price columns, so they must mirror
        the best (lowest) distributor offering. Units with no priced source keep whatever
        price they were curated with (e.g. a sourced 'Starting at' figure for markets).
        """
        priced = self.priced_sources
        if not priced:
            return
        self.price_low = priced[0].price_low
        # High end = the largest high (or low, when high is unset) across priced sources.
        self.price_high = max(s.price_high or s.price_low or 0 for s in priced) or None


class Distributor(Base):
    """A supplier the team can buy equipment from (distributor, reseller, or manufacturer)."""

    __tablename__ = "distributors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    distributor_type: Mapped[str] = mapped_column(String(20), default="distributor", nullable=False)
    # distributor | reseller | manufacturer
    financing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fast_ship: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    sources: Mapped[list[EquipmentSource]] = relationship(back_populates="distributor")


class EquipmentSource(Base):
    """One distributor's offer for one equipment unit — the basis for price comparison."""

    __tablename__ = "equipment_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_unit_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_units.id"), nullable=False, index=True
    )
    distributor_id: Mapped[int] = mapped_column(ForeignKey("distributors.id"), nullable=False)
    distributor_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    price_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    lead_time_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stock_notes: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Team can pin a preferred supplier even when it isn't the absolute cheapest.
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    unit: Mapped[EquipmentUnit] = relationship(back_populates="sources")
    distributor: Mapped[Distributor] = relationship(back_populates="sources")
