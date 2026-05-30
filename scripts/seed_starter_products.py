"""Seed a starter catalog of common vending SKUs (CLI wrapper).

Run once:  python scripts/seed_starter_products.py
Force:     python scripts/seed_starter_products.py --force

Why this exists:
    An empty Products tab is the single biggest source of friction for a new
    install. With no rows, the page reads as a 14-field form and four empty
    tables. Seeding ~25 of the most common vending SKUs gives the operator a
    working catalog they can immediately price (via Find Prices) and stock.

The data + idempotent upsert logic live in ``app/services/starter_catalog.py``
so the in-app "Seed starter catalog" button calls the exact same function
without importing from ``scripts/``. This file is the CLI surface only.

Gated behind an AppSetting sentinel (``starter_products_seeded``) so the
``preDeploy`` block runs it exactly once per environment. Pass ``--force`` to
re-run after a wipe; the in-app button always ignores the sentinel.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.inventory import Product
from app.services.starter_catalog import ensure_starter_products, mark_sentinel, sentinel_set

Base.metadata.create_all(bind=engine)


def seed(*, force: bool = False) -> None:
    with Session(engine) as db:
        if not force and sentinel_set(db):
            total = db.query(Product).count()
            print(
                f"Starter products already seeded (sentinel set). "
                f"Products total: {total}. Pass --force to re-run."
            )
            return
        created, backfilled = ensure_starter_products(db)
        mark_sentinel(db)
        db.commit()
        total = db.query(Product).count()
    print(f"Starter products: {created} created, {backfilled} backfilled. Products total: {total}.")


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
