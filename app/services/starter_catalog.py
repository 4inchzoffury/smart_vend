"""Starter catalog: the ~25 common vending SKUs we seed for a fresh install.

Exposed as a service (rather than only a CLI script) so the in-app "Seed
starter catalog" button on the Catalog empty state can call the same function
without the import dance that a `scripts/` package would require.

Idempotent: existing rows are matched by SKU and only blank fields are filled
in. Sell prices and unit costs are intentionally left null — the operator
captures those from the comparator or supplier import once an account is open.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.inventory import Product
from app.models.settings import AppSetting

SENTINEL_KEY = "starter_products_seeded"


# Categories match app/routers/inventory.py::PRODUCT_CATEGORIES. Case packs
# reflect the standard distributor pack (24 cans, 48–64 single-serve snacks,
# 36 candy bars).
STARTER_PRODUCTS: list[dict] = [
    # Soda — 12oz cans, case of 24
    {
        "sku": "coke-12oz-can",
        "name": "Coca-Cola Classic 12oz",
        "brand": "Coca-Cola",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "diet-coke-12oz-can",
        "name": "Diet Coke 12oz",
        "brand": "Coca-Cola",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "sprite-12oz-can",
        "name": "Sprite 12oz",
        "brand": "Coca-Cola",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "dr-pepper-12oz-can",
        "name": "Dr Pepper 12oz",
        "brand": "Dr Pepper",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "pepsi-12oz-can",
        "name": "Pepsi 12oz",
        "brand": "Pepsi",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "mountain-dew-12oz-can",
        "name": "Mountain Dew 12oz",
        "brand": "Pepsi",
        "category": "beverage_soda",
        "unit_size": "12oz",
        "case_pack_qty": 24,
    },
    # Energy
    {
        "sku": "red-bull-8-4oz",
        "name": "Red Bull 8.4oz",
        "brand": "Red Bull",
        "category": "beverage_energy",
        "unit_size": "8.4oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "monster-original-16oz",
        "name": "Monster Energy 16oz",
        "brand": "Monster",
        "category": "beverage_energy",
        "unit_size": "16oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "celsius-sparkling-12oz",
        "name": "Celsius Sparkling 12oz",
        "brand": "Celsius",
        "category": "beverage_energy",
        "unit_size": "12oz",
        "case_pack_qty": 12,
    },
    # Water
    {
        "sku": "dasani-16-9oz",
        "name": "Dasani 16.9oz",
        "brand": "Coca-Cola",
        "category": "beverage_water",
        "unit_size": "16.9oz",
        "case_pack_qty": 24,
    },
    {
        "sku": "smartwater-20oz",
        "name": "Smartwater 20oz",
        "brand": "Glaceau",
        "category": "beverage_water",
        "unit_size": "20oz",
        "case_pack_qty": 24,
    },
    # Juice / sports
    {
        "sku": "gatorade-cool-blue-20oz",
        "name": "Gatorade Cool Blue 20oz",
        "brand": "Gatorade",
        "category": "beverage_juice",
        "unit_size": "20oz",
        "case_pack_qty": 24,
    },
    # Salty snacks — single-serve 1oz, case of 64 (Frito-Lay standard)
    {
        "sku": "doritos-nacho-1oz",
        "name": "Doritos Nacho Cheese 1oz",
        "brand": "Frito-Lay",
        "category": "snack_chips",
        "unit_size": "1oz",
        "case_pack_qty": 64,
    },
    {
        "sku": "lays-classic-1oz",
        "name": "Lay's Classic 1oz",
        "brand": "Frito-Lay",
        "category": "snack_chips",
        "unit_size": "1oz",
        "case_pack_qty": 64,
    },
    {
        "sku": "cheetos-crunchy-1oz",
        "name": "Cheetos Crunchy 1oz",
        "brand": "Frito-Lay",
        "category": "snack_chips",
        "unit_size": "1oz",
        "case_pack_qty": 64,
    },
    {
        "sku": "fritos-original-1oz",
        "name": "Fritos Original 1oz",
        "brand": "Frito-Lay",
        "category": "snack_chips",
        "unit_size": "1oz",
        "case_pack_qty": 64,
    },
    {
        "sku": "sunchips-harvest-1oz",
        "name": "SunChips Harvest Cheddar 1oz",
        "brand": "Frito-Lay",
        "category": "snack_chips",
        "unit_size": "1oz",
        "case_pack_qty": 64,
    },
    # Chocolate / candy bars
    {
        "sku": "snickers-1-86oz",
        "name": "Snickers 1.86oz",
        "brand": "Mars",
        "category": "snack_candy",
        "unit_size": "1.86oz",
        "case_pack_qty": 48,
    },
    {
        "sku": "mms-peanut-1-74oz",
        "name": "M&M's Peanut 1.74oz",
        "brand": "Mars",
        "category": "snack_candy",
        "unit_size": "1.74oz",
        "case_pack_qty": 48,
    },
    {
        "sku": "reeses-cup-1-5oz",
        "name": "Reese's Peanut Butter Cups 1.5oz",
        "brand": "Hershey",
        "category": "snack_candy",
        "unit_size": "1.5oz",
        "case_pack_qty": 36,
    },
    {
        "sku": "kitkat-1-5oz",
        "name": "Kit Kat 1.5oz",
        "brand": "Hershey",
        "category": "snack_candy",
        "unit_size": "1.5oz",
        "case_pack_qty": 36,
    },
    {
        "sku": "twix-1-79oz",
        "name": "Twix 1.79oz",
        "brand": "Mars",
        "category": "snack_candy",
        "unit_size": "1.79oz",
        "case_pack_qty": 36,
    },
    {
        "sku": "hersheys-almond-1-45oz",
        "name": "Hershey's with Almonds 1.45oz",
        "brand": "Hershey",
        "category": "snack_candy",
        "unit_size": "1.45oz",
        "case_pack_qty": 36,
    },
    # Healthy / breakfast
    {
        "sku": "pop-tarts-strawberry",
        "name": "Pop-Tarts Frosted Strawberry 2pk",
        "brand": "Kellogg's",
        "category": "snack_healthy",
        "unit_size": "3.67oz",
        "case_pack_qty": 12,
    },
    {
        "sku": "nature-valley-oats-honey",
        "name": "Nature Valley Oats 'n Honey 2pk",
        "brand": "General Mills",
        "category": "snack_healthy",
        "unit_size": "1.49oz",
        "case_pack_qty": 18,
    },
]


def ensure_starter_products(db: Session) -> tuple[int, int]:
    """Upsert starter products. Returns (created, backfilled) counts.

    Existing rows are only updated where a column is currently blank — the
    seed never clobbers manual edits.
    """
    created = backfilled = 0
    for data in STARTER_PRODUCTS:
        existing = (
            db.query(Product).filter(Product.sku == data["sku"]).first()
            or db.query(Product).filter(Product.sku.ilike(data["sku"])).first()
        )
        if existing is None:
            db.add(Product(**data))
            created += 1
        else:
            changed = False
            for key, value in data.items():
                if key == "sku":
                    continue
                if not getattr(existing, key, None):
                    setattr(existing, key, value)
                    changed = True
            if changed:
                backfilled += 1
    db.flush()
    return created, backfilled


def sentinel_set(db: Session) -> bool:
    """True once the CLI/preDeploy seed has run on this database."""
    row = db.get(AppSetting, SENTINEL_KEY)
    return bool(row and row.value)


def mark_sentinel(db: Session) -> None:
    row = db.get(AppSetting, SENTINEL_KEY)
    if row:
        row.value = "1"
    else:
        db.add(AppSetting(key=SENTINEL_KEY, value="1"))
