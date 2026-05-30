"""Seed/upgrade the priority wholesale-supplier accounts named in research task #7.2.

Run once:  python scripts/seed_suppliers.py

Idempotent: existing rows are matched by name (case-insensitive) and **upgraded
in place** — contact info, website, address, notes, priority and account_status
get overwritten on each run so the seed remains the source of truth. Goldring
Gulf is the only net-new row for now. Costco is intentionally excluded: there is
no Costco serving Panama City; only Sam's Club is the local cash-and-carry
option.

Distinct from ``scripts/seed_distributors.py`` (equipment suppliers) — this
script targets product/inventory suppliers (``app.models.inventory.Supplier``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.inventory import Supplier

Base.metadata.create_all(bind=engine)


# Each entry has an optional ``match_aliases`` list — names the row may already
# have in the DB so the seed can rename in place. ``name`` is the canonical
# value we want post-seed.
PRIORITY_SUPPLIERS: list[dict] = [
    {
        "name": "Vistar (Performance Food Group)",
        "match_aliases": [
            "Vistar (Performance Food Group)",
            "Performance Food Group",
            "Vistar",
        ],
        "supplier_type": "broadline_distributor",
        "contact_email": "VistarCustomerFirst@pfgc.com",
        "contact_phone": "1-800-880-9900",
        "website": "https://www.vistar.com/",
        "priority": 10,
        "account_status": "not_started",
        "notes": (
            "Categories: snacks, candy, beverages, food-service, vending consumables. "
            "Pricing: B2B wholesale; order guide pricing after account opens (no public catalog). "
            "Delivery: vending-specific broadline; ships as small as one carton to FL Panhandle. "
            "Onboard FIRST — primary distributor and the main lever on COGS."
        ),
    },
    {
        "name": "Goldring Gulf Distributing",
        "match_aliases": ["Goldring Gulf Distributing", "Goldring Gulf", "Gulf Distributing"],
        "supplier_type": "beverage_distributor",
        "website": "https://gulfdistributing.com/goldringgulfdistributing/",
        "address": "927 Mulberry Ave, Panama City, FL 32401",
        "priority": 20,
        "account_status": "not_started",
        "notes": (
            "Categories: beverages (Red Bull, Snapple, 7-UP, 90+ brands). "
            "Pricing: rep-driven; no public catalog. Ask rep for cooler/SKU pricing sheet. "
            "Delivery: local Panama City branch. "
            "Local beverage account — opens cooler door for energy-drink margin."
        ),
    },
    {
        "name": "Sam's Club Business",
        "match_aliases": ["Sam's Club Business", "Sam's Club", "Sams Club"],
        "supplier_type": "warehouse_club",
        "website": "https://www.samsclub.com/b/sam-s-club-business",
        "priority": 30,
        "account_status": "not_started",
        "notes": (
            "Categories: snacks, beverages, candy, fill-in items. "
            "Pricing: member pricing; Business membership ~$35/yr. "
            "Delivery: in-club pickup; same-day fill-in option. "
            "Cash-and-carry fill-in for hot-selling SKUs between Vistar runs."
        ),
    },
]


def _find_existing(db: Session, names: list[str]) -> Supplier | None:
    """Find the first existing row matching any name in ``names`` (case-insensitive)."""
    for n in names:
        row = db.query(Supplier).filter(sql_func.lower(Supplier.name) == n.lower()).first()
        if row:
            return row
    return None


def ensure_priority_suppliers(db: Session) -> tuple[int, int]:
    """Upsert each priority supplier. Returns (created, updated) counts."""
    created = updated = 0
    for data in PRIORITY_SUPPLIERS:
        aliases = data.pop("match_aliases")
        row = _find_existing(db, aliases)
        if row is None:
            row = Supplier(**data)
            db.add(row)
            created += 1
        else:
            for k, v in data.items():
                setattr(row, k, v)
            updated += 1
    db.flush()
    return created, updated


def seed() -> None:
    with Session(engine) as db:
        created, updated = ensure_priority_suppliers(db)
        db.commit()
        total = db.query(Supplier).count()
    print(
        f"Priority suppliers seeded: {created} created, {updated} upgraded in place. "
        f"Suppliers total: {total}."
    )


if __name__ == "__main__":
    seed()
