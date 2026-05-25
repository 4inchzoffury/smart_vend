"""Curate the equipment catalog: fix accuracy, attach distributor sources, expand lineup.

Run:  python scripts/curate_equipment.py

Idempotent — safe to re-run. It:
  1. Archives units that have no verifiable price (and the AI-corrupted brand market/kiosk
     rows). Archiving keeps the row (reversible) but drops it off the live catalog.
  2. Locks + re-sources the good coolers (HAHA / WEIMI / Micromart / Cantaloupe SmartStore)
     so the AI refresh can't clobber them again, and adds A&M as a second source where it
     carries the same model (best price wins on the card).
  3. Adds a curated set of traditional vending machines + glass-door coolers (real A&M
     pricing) and "Starting at" micro-market kiosk/packages.

Sources are matched idempotently per (unit, distributor); prices are recomputed onto the
unit afterward so catalog cards show the best (lowest) available price.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.seed_distributors import ensure_distributors
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.equipment import Distributor, EquipmentSource, EquipmentUnit

Base.metadata.create_all(bind=engine)

# ── 1. Archive: no verifiable price, or AI-corrupted identity/pricing ──────────
ARCHIVE: list[tuple[str, str]] = [
    ("365 Retail Markets", "PicoCooler Vision"),  # contact-only, no public price
    ("SandStar", "SandStar ARK"),  # demo-only pricing
    (
        "Crane Merchandising Systems",
        "Merchant Combo 5591",
    ),  # AI grabbed EU pricing; unverifiable US price
    ("AMS", "Sensit Touch 39"),  # ambiguous identity/price — replaced by clean AMS units
    ("Jofemar", "Vision ES Plus"),  # no US price
    ("365 Retail Markets", "NanoMarket"),  # no public price → see kiosk/market packages
    ("Cantaloupe", "Cantaloupe Kiosk"),  # AI showed $995 (bad match)
    ("Avanti Markets", "Avanti Self-Checkout Kiosk"),  # no public price
    ("365 Retail Markets", "365 Micro Market"),  # custom-quote only
    ("Cantaloupe", "Cantaloupe Micro Market"),  # AI showed cooler price range (bad)
    ("Avanti Markets", "Avanti Micro Market"),  # custom-quote only
]

# ── 2. Keep + curate the good coolers; attach distributor sources ──────────────
# Each: match=(manufacturer, product_name); set=field overrides; sources=offers.
KEEP: list[dict] = [
    {
        "match": ("HAHA Vending", "HAHA Mini 360C"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 3095,
                "high": 3095,
                "in_stock": True,
                "lead_min": 3,
                "url": "https://www.amequipmentsales.com/prodcat/smart-coolers/",
                "notes": "HAHA Mini smart cooler — ships in ~3 days",
            },
            {
                "dist": "VendGuys",
                "low": 3449,
                "high": 3449,
                "url": "https://vendguys.com/products/haha-smart-cooler-mini-360c",
            },
        ],
    },
    {
        "match": ("HAHA Vending", "HAHA PRO 542CT"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 4395,
                "high": 4395,
                "in_stock": True,
                "lead_min": 3,
                "url": "https://www.amequipmentsales.com/prodcat/smart-coolers/",
                "notes": "HAHA Pro smart cooler",
            },
            {
                "dist": "VendGuys",
                "low": 4700,
                "high": 4700,
                "url": "https://vendguys.com/products/haha-smart-cooler-pro-us542ct-3",
            },
        ],
    },
    {
        "match": ("HAHA Vending", "HAHA Freezer 550CT"),
        "set": {"equipment_type": "freezer"},
        "sources": [
            {
                "dist": "VendGuys",
                "low": 4949,
                "high": 4949,
                "url": "https://vendguys.com/products/haha-smart-cooler-freezer-us550ct",
            },
            {
                "dist": "A&M Equipment Sales",
                "low": 5895,
                "high": 5895,
                "url": "https://www.amequipmentsales.com/prodcat/smart-coolers/",
                "notes": "HAHA Frozen smart cooler",
            },
        ],
    },
    {
        "match": ("HAHA Vending", "HAHA Ultra 1200CT"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 6895,
                "high": 6895,
                "url": "https://www.amequipmentsales.com/prodcat/smart-coolers/",
                "notes": "HAHA Ultra dual-door smart cooler",
            },
            {
                "dist": "VendGuys",
                "low": 7300,
                "high": 7300,
                "url": "https://vendguys.com/products/haha-smart-cooler-ultra-us1200ct",
            },
        ],
    },
    {
        "match": ("Micromart", "Micromart Gen 5 Smart Fridge"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "VendGuys",
                "low": 6550,
                "high": 6550,
                "url": "https://vendguys.com/products/micromart-smart-store-gen-5-fridge",
            },
        ],
    },
    {
        "match": ("Cantaloupe", "Smart Store 600 Single"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "Cantaloupe",
                "low": 7495,
                "high": 7495,
                "url": "https://store.cantaloupe.com/products/smart-store-600-single",
                "notes": "Subscription option available (no upfront cost)",
            },
        ],
    },
    {
        "match": ("Cantaloupe", "Smart Store 700 Single"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "Cantaloupe",
                "low": 9495,
                "high": 9495,
                "url": "https://store.cantaloupe.com/products/smart-store-700-single",
            },
        ],
    },
    {
        # The "G319" cabinet is an Imbera glass-door cooler with Cantaloupe payment — not AI.
        "match": ("Cantaloupe", "G319 Cooler"),
        "set": {
            "equipment_type": "glass_cooler",
            "ai_features": False,
            "price_low": 1895,
            "price_high": 1895,
        },
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 1895,
                "high": 1895,
                "in_stock": True,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-coolers/",
                "notes": "Imbera G319 single-door cooler cabinet",
            },
        ],
    },
    {
        "match": ("WEIMI", "WEIMI AI Vision Smart Fridge"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "WEIMI",
                "low": 2698,
                "high": 3228,
                "url": "https://www.weimivending.com/AI-camera-vending-machine-with-weight-sense-technology.html",
                "notes": "B2B/wholesale, freight from Guangzhou; OEM/ODM available",
            },
        ],
    },
    {
        "match": ("WEIMI", "WEIMI Double Door Fresh Food"),
        "set": {"equipment_type": "smart_cooler"},
        "sources": [
            {
                "dist": "WEIMI",
                "low": 2641,
                "high": 3228,
                "url": "https://www.weimivending.com/weimi-smart-fridge-vending-machine.html",
                "notes": "B2B/wholesale, freight from Guangzhou",
            },
        ],
    },
]


# ── 3. New curated units (real A&M pricing) + micro-market offerings ───────────
# Each is a full unit dict plus a "sources" list. Matched idempotently on
# (manufacturer, product_name).
def _u(**kw: object) -> dict:
    base = {
        "reseller": None,
        "product_line": None,
        "price_is_starting": False,
        "ai_features": False,
        "is_locked": True,
        "data_confidence": "verified",
        "status": "active",
    }
    base.update(kw)
    return base


NEW: list[dict] = [
    # ── Combo machines ──
    {
        "unit": _u(
            manufacturer="AMS",
            product_name="AMS 39 Combo",
            product_line="AMS 39",
            equipment_type="combo",
            capacity_units=450,
            warranty_years=2,
            warranty_notes="2-year parts warranty; made in Yakima, WA",
            extended_warranty_available=True,
            connectivity="4G, WiFi",
            payment_types="EMV, NFC, credit/debit",
            certifications="UL, NSF, NAMA, Made in USA",
            highlights=(
                "Snacks + cold drinks in one cabinet — the micro-location workhorse\n"
                "Made in the USA (Yakima, WA); 2-year parts warranty\n"
                "iVend guaranteed-delivery sensor reduces refund disputes\n"
                "Ships in ~3 days from A&M"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-combo-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 7295,
                "high": 7295,
                "in_stock": True,
                "lead_min": 3,
                "notes": "Ships in 3 days",
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-combo-vending-machines/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="Seaga",
            product_name="Seaga QB4000 Combo",
            product_line="QB",
            equipment_type="combo",
            capacity_units=300,
            warranty_years=1,
            connectivity="optional telemetry",
            payment_types="EMV, NFC, credit/debit",
            highlights=(
                "Budget-friendly combo — lowest entry price in the category\n"
                "Compact footprint for tight break rooms\n"
                "Manufacturer-direct special pricing via A&M"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-combo-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 4395,
                "high": 4395,
                "notes": "MFG-direct sale price (reg. $5,395)",
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-combo-vending-machines/",
            },
        ],
    },
    # ── Drink machines ──
    {
        "unit": _u(
            manufacturer="Vendo",
            product_name="Vendo 721 Drink Machine",
            product_line="Vendo 700",
            equipment_type="drink",
            capacity_units=720,
            warranty_years=1,
            payment_types="EMV, NFC, credit/debit",
            highlights=(
                "High-capacity bottle/can drink machine for busy venues\n"
                "Proven Vendo reliability; large selection count\n"
                "Strong US parts/service availability"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-drink-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 5495,
                "high": 5495,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-drink-vending-machines/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="Royal",
            product_name="Royal 650 Drink Machine",
            product_line="Royal 650",
            equipment_type="drink",
            capacity_units=650,
            warranty_years=1,
            payment_types="EMV, NFC, credit/debit",
            highlights=(
                "Workhorse can/bottle vendor — widely deployed across the US\n"
                "Simple, serviceable mechanism; low cost of ownership\n"
                "Live-display option available"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-drink-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 5395,
                "high": 5395,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-drink-vending-machines/",
            },
        ],
    },
    # ── Snack machines ──
    {
        "unit": _u(
            manufacturer="AMS",
            product_name="AMS 39 Snack Machine",
            product_line="AMS 39",
            equipment_type="snack",
            capacity_units=450,
            warranty_years=2,
            warranty_notes="2-year parts warranty; made in Yakima, WA",
            extended_warranty_available=True,
            connectivity="4G, WiFi",
            payment_types="EMV, NFC, credit/debit",
            certifications="UL, NSF, NAMA, Made in USA",
            highlights=(
                "All-snack merchandiser — flexible tray/spiral configuration\n"
                "Made in the USA; 2-year parts warranty\n"
                "iVend guaranteed delivery sensor"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-snack-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 5695,
                "high": 5695,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-snack-vending-machines/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="USI",
            product_name="USI Mercato 4000 Snack Machine",
            product_line="Mercato",
            equipment_type="snack",
            capacity_units=400,
            warranty_years=1,
            payment_types="EMV, NFC, credit/debit",
            highlights=(
                "Glass-front snack vendor with bright merchandising\n"
                "Mid-capacity; good fit for offices and clinics\n"
                "Wittern/USI parts network"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-snack-vending-machines/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 6395,
                "high": 6395,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-snack-vending-machines/",
            },
        ],
    },
    # ── Glass-door coolers (non-smart) ──
    {
        "unit": _u(
            manufacturer="Imbera",
            product_name="Imbera VRD43 Double-Door Cooler",
            product_line="VRD",
            equipment_type="glass_cooler",
            capacity_cu_ft=43.0,
            warranty_years=5,
            warranty_notes="5-year compressor warranty",
            highlights=(
                "Double-door glass merchandiser — high drink capacity\n"
                "Energy-efficient; 5-year compressor warranty\n"
                "Pairs with a self-checkout kiosk for a micro market"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-coolers/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 3295,
                "high": 3295,
                "in_stock": True,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-coolers/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="Imbera",
            product_name="Imbera VFS24 Single-Door Freezer",
            product_line="VFS",
            equipment_type="glass_cooler",
            capacity_cu_ft=24.0,
            warranty_years=5,
            warranty_notes="5-year compressor warranty",
            operating_temp_low=-10.0,
            operating_temp_high=10.0,
            highlights=(
                "Glass-door freezer for ice cream and frozen grab-and-go\n"
                "Energy-efficient; 5-year compressor warranty\n"
                "Adds a frozen section to any micro market"
            ),
            product_url="https://www.amequipmentsales.com/prodcat/new-vending-machines/new-coolers/",
            data_source="https://www.amequipmentsales.com",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 3495,
                "high": 3495,
                "url": "https://www.amequipmentsales.com/prodcat/new-vending-machines/new-coolers/",
            },
        ],
    },
    # ── Micro market kiosk + packages (Starting-at pricing) ──
    {
        "unit": _u(
            manufacturer="Prime Micro Markets",
            product_name="Micro Market Self-Checkout Kiosk",
            product_line="Kiosk",
            equipment_type="kiosk",
            price_is_starting=True,
            price_low=1800,
            price_high=1800,
            connectivity="WiFi, Ethernet, 4G",
            payment_types="EMV, NFC, mobile wallet, credit/debit",
            certifications="PCI DSS",
            highlights=(
                "Self-checkout terminal: touchscreen + scanner + EMV/NFC reader + stand\n"
                "The hub of a micro market — shoppers scan and pay themselves\n"
                "Starting price is hardware only; final pricing by quote"
            ),
            data_source="Component estimate (kiosk hardware)",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 1800,
                "high": 1800,
                "notes": "Starting estimate — self-checkout kiosk hardware; final by quote",
                "url": "https://www.amequipmentsales.com/micro-markets/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="Prime Micro Markets",
            product_name="Micro Market Starter Package",
            product_line="Micro Market",
            equipment_type="micro_market",
            price_is_starting=True,
            price_low=4500,
            price_high=4500,
            connectivity="WiFi, Ethernet, 4G",
            payment_types="EMV, NFC, mobile wallet, credit/debit",
            certifications="PCI DSS",
            highlights=(
                "Entry micro market: self-checkout kiosk + 1 glass cooler + ambient racks\n"
                "Best for small offices (25–75 people)\n"
                "Starting estimate assembled from component costs; final pricing by quote"
            ),
            data_source="Component estimate (kiosk + 1 cooler + racks)",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 4500,
                "high": 4500,
                "notes": "Starting estimate — kiosk + 1 cooler + racks; configured to the space",
                "url": "https://www.amequipmentsales.com/micro-markets/",
            },
        ],
    },
    {
        "unit": _u(
            manufacturer="Prime Micro Markets",
            product_name="Micro Market Standard Package",
            product_line="Micro Market",
            equipment_type="micro_market",
            price_is_starting=True,
            price_low=7500,
            price_high=7500,
            connectivity="WiFi, Ethernet, 4G",
            payment_types="EMV, NFC, mobile wallet, credit/debit",
            certifications="PCI DSS",
            highlights=(
                "Full micro market: kiosk + 2 glass coolers + ambient + snack racks\n"
                "Best for medium sites (75–200 people); fresh food capable\n"
                "Starting estimate assembled from component costs; final pricing by quote"
            ),
            data_source="Component estimate (kiosk + 2 coolers + racks)",
        ),
        "sources": [
            {
                "dist": "A&M Equipment Sales",
                "low": 7500,
                "high": 7500,
                "notes": "Starting estimate — kiosk + 2 coolers + racks; configured to the space",
                "url": "https://www.amequipmentsales.com/micro-markets/",
            },
        ],
    },
]


# ── helpers ────────────────────────────────────────────────────────────────────


def _get_unit(db: Session, mfr: str, name: str) -> EquipmentUnit | None:
    return (
        db.query(EquipmentUnit)
        .filter(EquipmentUnit.manufacturer == mfr, EquipmentUnit.product_name == name)
        .first()
    )


def _attach_source(
    db: Session, unit: EquipmentUnit, dists: dict[str, Distributor], spec: dict
) -> bool:
    dist = dists[spec["dist"]]
    existing = (
        db.query(EquipmentSource)
        .filter(
            EquipmentSource.equipment_unit_id == unit.id,
            EquipmentSource.distributor_id == dist.id,
        )
        .first()
    )
    src = existing or EquipmentSource(equipment_unit_id=unit.id, distributor_id=dist.id)
    src.price_low = spec.get("low")
    src.price_high = spec.get("high", spec.get("low"))
    src.price_notes = spec.get("notes")
    src.distributor_url = spec.get("url")
    src.lead_time_days_min = spec.get("lead_min")
    src.lead_time_days_max = spec.get("lead_max")
    src.in_stock = spec.get("in_stock", False)
    src.last_verified = datetime.now()
    if not existing:
        db.add(src)
    return existing is None


_SENTINEL = "equipment_curated_v1"


def curate(force: bool = False) -> None:
    from app.models.settings import AppSetting

    with Session(engine) as db:
        # One-time guard: this overwrites curated fields (status/price/locks), so it must NOT
        # re-run on every deploy and clobber edits the team made in the UI. The sentinel lets
        # it sit safely in the Render preDeploy step — it applies once, then no-ops.
        if not force and db.get(AppSetting, _SENTINEL):
            print(f"Curation already applied ({_SENTINEL} set); skipping. Use --force to re-run.")
            return

        dists = ensure_distributors(db)
        db.flush()

        archived = 0
        for mfr, name in ARCHIVE:
            unit = _get_unit(db, mfr, name)
            if unit and unit.status != "archived":
                unit.status = "archived"
                archived += 1

        kept, sources_added = 0, 0
        for entry in KEEP:
            mfr, name = entry["match"]
            unit = _get_unit(db, mfr, name)
            if not unit:
                print(f"  ! KEEP target not found: {mfr} / {name}")
                continue
            for k, v in entry.get("set", {}).items():
                setattr(unit, k, v)
            unit.is_locked = True
            unit.data_confidence = "verified"
            unit.status = "active"
            db.flush()
            for spec in entry["sources"]:
                sources_added += int(_attach_source(db, unit, dists, spec))
            db.flush()
            unit.recompute_best_price()
            kept += 1

        created = 0
        for entry in NEW:
            data = entry["unit"]
            unit = _get_unit(db, data["manufacturer"], data["product_name"])
            if not unit:
                unit = EquipmentUnit(**data)
                db.add(unit)
                created += 1
            else:
                for k, v in data.items():
                    setattr(unit, k, v)
            db.flush()
            for spec in entry["sources"]:
                sources_added += int(_attach_source(db, unit, dists, spec))
            db.flush()
            unit.recompute_best_price()

        if not db.get(AppSetting, _SENTINEL):
            db.add(AppSetting(key=_SENTINEL, value=datetime.now().isoformat()))
        db.commit()

        active = db.query(EquipmentUnit).filter(EquipmentUnit.status == "active").count()
        total_sources = db.query(EquipmentSource).count()
    print(
        f"Curation complete: archived {archived}, curated {kept}, created {created} new units, "
        f"added {sources_added} sources. Active: {active}, sources: {total_sources}."
    )


if __name__ == "__main__":
    curate(force="--force" in sys.argv)
