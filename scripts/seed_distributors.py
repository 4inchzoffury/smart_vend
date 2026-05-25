"""Seed the distributors table (supplier directory).

Run once:  python scripts/seed_distributors.py

Idempotent: matches on the unique distributor name. ``ensure_distributors`` is also
imported by scripts/curate_equipment.py so curation can run standalone.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.equipment import Distributor

Base.metadata.create_all(bind=engine)

DISTRIBUTORS: list[dict] = [
    {
        "name": "A&M Equipment Sales",
        "website": "https://www.amequipmentsales.com",
        "phone": "770-482-7993",
        "location": "Lithonia, GA",
        "distributor_type": "distributor",
        "financing": True,
        "fast_ship": True,
        "notes": (
            "Family-owned since 1964. New + refurbished vending machines, glass-door "
            "coolers, smart coolers, and micro markets. Equipment financing and a "
            "Fast-Ship program for in-stock units."
        ),
    },
    {
        "name": "VendGuys",
        "website": "https://vendguys.com",
        "distributor_type": "reseller",
        "notes": "Online reseller of HAHA AI smart coolers and Micromart smart fridges.",
    },
    {
        "name": "GeniusVend",
        "website": "https://geniusvend.com",
        "distributor_type": "reseller",
        "notes": "HAHA Vending AI smart cooler reseller.",
    },
    {
        "name": "Cantaloupe",
        "website": "https://store.cantaloupe.com",
        "distributor_type": "manufacturer",
        "notes": (
            "Maker of SmartStore AI coolers and a full micro market platform "
            "(formerly USA Technologies). Subscription options available."
        ),
    },
    {
        "name": "Micromart",
        "website": "https://www.micromart.com",
        "distributor_type": "manufacturer",
        "notes": "Smart fridge manufacturer. Strong warranty: 3-year + 5-year compressor.",
    },
    {
        "name": "WEIMI",
        "website": "https://www.weimivending.com",
        "location": "Guangzhou, China",
        "distributor_type": "manufacturer",
        "notes": "B2B/OEM AI smart fridge manufacturer. Lowest acquisition cost; freight import.",
    },
    {
        "name": "Southern Equipment Sales",
        "website": "https://www.southernequipmentsales.com",
        "distributor_type": "distributor",
        "notes": "US vending equipment distributor (AMS and others).",
    },
]


def ensure_distributors(db: Session) -> dict[str, Distributor]:
    """Get-or-create each distributor; return a name→Distributor map."""
    out: dict[str, Distributor] = {}
    for data in DISTRIBUTORS:
        row = db.query(Distributor).filter(Distributor.name == data["name"]).first()
        if row:
            # Refresh contact/notes in case they were edited here.
            for k, v in data.items():
                setattr(row, k, v)
        else:
            row = Distributor(**data)
            db.add(row)
        out[data["name"]] = row
    db.flush()
    return out


def seed() -> None:
    with Session(engine) as db:
        ensure_distributors(db)
        db.commit()
        count = db.query(Distributor).count()
    print(f"Distributors seeded. Total now: {count}.")


if __name__ == "__main__":
    seed()
