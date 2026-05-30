"""Bulk-import a supplier's price list into Products + ProductSources.

The Inventory module already supports per-product, per-supplier offers via
``ProductSource``. This module adds the *supplier-side* bulk path that auth-walled
B2B catalogs (Vistar today, future broadlines tomorrow) need — there's no scrape
path, so the team uploads what they have from the rep's order guide and we
turn it into Products + ProductSources in one round-trip.

Two ingestion modes share one persistence path (``ingest_supplier_offers``):

* **CSV / text** — ``parse_csv_text`` accepts a raw CSV blob and remaps any of
  a handful of common header spellings to our canonical field names. Tolerant
  of column reordering and missing optional fields.
* **AI extract** — ``ai_extract_rows`` asks Claude Haiku to extract the same
  fields from an unstructured catalog paste (PDF copy-paste, email body, etc.).
  Returns the structured rows without persisting them, so the route can show a
  preview before commit if needed.

The Anthropic call mirrors the model selection and missing-key pattern used
by ``app/services/inventory_agent.py`` so this stays one service to keep an
eye on.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.inventory import Product, ProductSource, Supplier

logger = logging.getLogger(__name__)

_AI_MODEL = "claude-haiku-4-5-20251001"

# Canonical field names. Anything else is mapped (or dropped) via ``_HEADER_ALIASES``.
CANONICAL_FIELDS: tuple[str, ...] = (
    "sku",
    "name",
    "brand",
    "category",
    "case_pack_qty",
    "case_price",
    "unit_size",
    "unit_cost",
    "min_order",
    "price_notes",
)

# Header spellings we accept on import — case-insensitive, punctuation-tolerant.
# Add new vendor-specific spellings here when they show up in the wild.
_HEADER_ALIASES: dict[str, str] = {
    # SKU
    "sku": "sku",
    "item": "sku",
    "item #": "sku",
    "item_no": "sku",
    "item number": "sku",
    "product code": "sku",
    "vendor sku": "sku",
    "vistar item": "sku",
    # Name / description
    "name": "name",
    "product": "name",
    "description": "name",
    "item description": "name",
    "product name": "name",
    "title": "name",
    # Brand
    "brand": "brand",
    "manufacturer": "brand",
    "mfg": "brand",
    # Category
    "category": "category",
    "department": "category",
    "section": "category",
    # Pack
    "case pack": "case_pack_qty",
    "case pack qty": "case_pack_qty",
    "pack": "case_pack_qty",
    "pack size": "case_pack_qty",
    "case qty": "case_pack_qty",
    "case count": "case_pack_qty",
    "units per case": "case_pack_qty",
    "units/case": "case_pack_qty",
    # Case price
    "case price": "case_price",
    "case cost": "case_price",
    "case $": "case_price",
    "wholesale": "case_price",
    "wholesale price": "case_price",
    # Unit cost (already-per-unit pricing)
    "unit cost": "unit_cost",
    "unit price": "unit_cost",
    "each": "unit_cost",
    "ea": "unit_cost",
    # Unit size
    "unit size": "unit_size",
    "size": "unit_size",
    "package size": "unit_size",
    # MOQ
    "min order": "min_order",
    "minimum": "min_order",
    "moq": "min_order",
    # Notes
    "notes": "price_notes",
    "comment": "price_notes",
    "comments": "price_notes",
}


@dataclass
class ImportRow:
    """One row staged for ingestion."""

    sku: str | None = None
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    case_pack_qty: int | None = None
    case_price: float | None = None
    unit_size: str | None = None
    unit_cost: float | None = None
    min_order: str | None = None
    price_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in CANONICAL_FIELDS}


@dataclass
class IngestResult:
    products_created: int = 0
    products_updated: int = 0
    sources_created: int = 0
    sources_updated: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return (
            self.products_created
            + self.products_updated
            # `skipped` is anything we couldn't ingest (e.g. missing name + sku)
            + len(self.skipped)
        )


# ── parsing ──────────────────────────────────────────────────────────────────

_MONEY_RE = re.compile(r"[^\d.\-]")


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = _MONEY_RE.sub("", str(v))
    if not s or s in {".", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None else None


def _canonical_header(raw: str) -> str | None:
    """Map a raw CSV header cell to a canonical field name, or None to drop it."""
    key = raw.strip().lower().replace("_", " ")
    return _HEADER_ALIASES.get(key)


def parse_csv_text(blob: str) -> list[ImportRow]:
    """Parse a CSV blob (with header row) into ``ImportRow``s.

    Tolerates extra columns (silently dropped), missing optional fields, and
    common header-name variants. Rows missing both ``sku`` and ``name`` are
    skipped silently — they carry no identity.
    """
    if not blob or not blob.strip():
        return []
    # `Sniffer` chokes on small inputs; just default to comma and let `csv` handle quoting.
    reader = csv.reader(io.StringIO(blob))
    try:
        headers = next(reader)
    except StopIteration:
        return []
    canonical = [_canonical_header(h) for h in headers]
    rows: list[ImportRow] = []
    for raw in reader:
        if not any(cell.strip() for cell in raw):
            continue
        d: dict[str, Any] = {}
        for header_key, cell in zip(canonical, raw, strict=False):
            if header_key is None:
                continue
            cell = cell.strip()
            if not cell:
                continue
            if header_key in {"case_pack_qty"}:
                d[header_key] = _to_int(cell)
            elif header_key in {"case_price", "unit_cost"}:
                d[header_key] = _to_float(cell)
            else:
                d[header_key] = cell
        if not d.get("sku") and not d.get("name"):
            continue
        rows.append(ImportRow(**{k: v for k, v in d.items() if k in CANONICAL_FIELDS}))
    return rows


# ── AI extraction ───────────────────────────────────────────────────────────

_AI_PROMPT = (
    "You are extracting structured product rows from a wholesale-distributor "
    "catalog or order guide. The input may be plain-text copy-paste from a PDF "
    "or web page.\n\n"
    "Output ONLY a JSON array. Each object MUST have exactly these keys "
    "(use null when unknown):\n"
    "  sku, name, brand, category, case_pack_qty, case_price, unit_size, "
    "unit_cost, min_order, price_notes\n\n"
    "Rules:\n"
    "- `case_price` is the price for the whole case (a number). `unit_cost` is "
    "the per-unit price when listed directly (rare).\n"
    "- `case_pack_qty` is the integer count of units in the case (e.g. 24, 36).\n"
    "- Money values are bare numbers (no $, no commas).\n"
    "- `category` is a short slug like 'beverage_water', 'beverage_energy', "
    "'beverage_soda', 'snack_chips', 'snack_candy', 'snack_healthy', "
    "'meal_sandwich', 'personal_care' — or null if unclear.\n"
    "- Drop any row that has neither sku nor name.\n"
    "- Start your response with `[` and end with `]`. No prose, no markdown fences."
)


class AIExtractError(RuntimeError):
    pass


def ai_extract_rows(text: str) -> list[ImportRow]:
    """Use Claude Haiku to pull structured rows from an unstructured catalog paste.

    Raises ``AIExtractError`` when ``ANTHROPIC_API_KEY`` is missing or the model
    returns malformed JSON — callers should surface the message to the operator.
    """
    if not text or not text.strip():
        return []
    if not settings.anthropic_api_key:
        raise AIExtractError(
            "ANTHROPIC_API_KEY is not configured — set it in .env (or use the CSV mode instead)."
        )
    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as e:
        raise AIExtractError(f"anthropic SDK not installed: {e}") from e

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=_AI_MODEL,
        max_tokens=4096,
        system=_AI_PROMPT,
        messages=[{"role": "user", "content": text[:20000]}],  # safety cap on token spend
    )
    body = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
    # Trim accidental markdown fences in case the model ignored instructions.
    if body.startswith("```"):
        body = body.strip("`")
        body = body[body.find("[") :]
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        # Last-ditch: extract the first bracketed array.
        m = re.search(r"\[.*]", body, re.DOTALL)
        if not m:
            raise AIExtractError(f"AI returned non-JSON output: {e}") from e
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e2:
            raise AIExtractError(f"AI returned malformed JSON: {e2}") from e2

    if not isinstance(data, list):
        raise AIExtractError("AI did not return a JSON array.")

    rows: list[ImportRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        d = {k: item.get(k) for k in CANONICAL_FIELDS}
        d["case_pack_qty"] = _to_int(d.get("case_pack_qty"))
        d["case_price"] = _to_float(d.get("case_price"))
        d["unit_cost"] = _to_float(d.get("unit_cost"))
        # Coerce nulls/empty strings to None for string fields.
        for k in ("sku", "name", "brand", "category", "unit_size", "min_order", "price_notes"):
            v = d.get(k)
            d[k] = v.strip() if isinstance(v, str) and v.strip() else None
        if not d.get("sku") and not d.get("name"):
            continue
        rows.append(ImportRow(**d))
    return rows


# ── persistence ─────────────────────────────────────────────────────────────


def _generate_sku(supplier: Supplier, row: ImportRow) -> str:
    """Fallback SKU when the catalog row has no item number.

    Format: ``<supplier-slug>-<slugified-name>`` — keeps product SKU unique and
    obviously synthetic so the team can replace it later.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", supplier.name.lower()).strip("-")[:12] or "supplier"
    name_part = re.sub(r"[^a-z0-9]+", "-", (row.name or "").lower()).strip("-")[:40]
    return f"{slug}-{name_part}"[:50]


def _find_product(db: Session, row: ImportRow) -> Product | None:
    if row.sku:
        p = db.query(Product).filter(Product.sku == row.sku).first()
        if p:
            return p
    if row.name:
        # Case-insensitive name match within the same category if specified;
        # avoids "Pepsi 12oz" colliding with "Pepsi Zero 12oz" across categories.
        q = db.query(Product).filter(Product.name.ilike(row.name))
        if row.category:
            q = q.filter(Product.category == row.category)
        return q.first()
    return None


def _supplier_origin(supplier: Supplier) -> str:
    """Stable per-supplier origin tag for ProductSource.origin."""
    slug = re.sub(r"[^a-z0-9]+", "_", supplier.name.lower()).strip("_")[:16] or "supplier"
    return f"{slug}_import"


def ingest_supplier_offers(db: Session, supplier_id: int, rows: list[ImportRow]) -> IngestResult:
    """Upsert Products + ProductSources for ``rows`` against ``supplier_id``.

    Idempotent: re-importing the same CSV updates the existing ProductSource
    in place (price/case-pack get refreshed, ``last_verified`` advances) rather
    than appending duplicates.
    """
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {supplier_id} not found")

    result = IngestResult()
    origin_tag = _supplier_origin(supplier)
    now = datetime.utcnow()

    for row in rows:
        if not (row.sku or row.name):
            result.skipped.append("missing both sku and name")
            continue

        product = _find_product(db, row)
        if product is None:
            sku = row.sku or _generate_sku(supplier, row)
            # Guard against synthetic-SKU collisions (rare; happens if two rows
            # share the same name with no real SKU). Drop the duplicate.
            if db.query(Product).filter(Product.sku == sku).first():
                result.skipped.append(f"duplicate synthetic SKU '{sku}'")
                continue
            product = Product(
                sku=sku,
                name=row.name or sku,
                brand=row.brand,
                category=row.category,
                case_pack_qty=row.case_pack_qty,
                unit_size=row.unit_size,
                primary_supplier_id=supplier.id,
                is_active=True,
            )
            db.add(product)
            db.flush()  # need product.id for the ProductSource below
            result.products_created += 1
        else:
            # Don't overwrite a hand-curated name/brand/category, but fill blanks.
            if not product.brand and row.brand:
                product.brand = row.brand
            if not product.category and row.category:
                product.category = row.category
            if not product.case_pack_qty and row.case_pack_qty:
                product.case_pack_qty = row.case_pack_qty
            if not product.unit_size and row.unit_size:
                product.unit_size = row.unit_size
            result.products_updated += 1

        # Find or create the ProductSource for this (product, supplier) pair.
        src = (
            db.query(ProductSource)
            .filter(
                ProductSource.product_id == product.id,
                ProductSource.supplier_id == supplier.id,
            )
            .first()
        )
        is_new = src is None
        if is_new:
            src = ProductSource(product_id=product.id, supplier_id=supplier.id)
            db.add(src)

        # Always refresh price + provenance on import — these are the fields the
        # operator paid us to update.
        src.case_price = row.case_price
        src.case_pack_qty = row.case_pack_qty
        src.unit_cost = row.unit_cost
        src.unit_size = row.unit_size or src.unit_size
        src.min_order = row.min_order or src.min_order
        src.price_notes = row.price_notes or src.price_notes
        src.origin = origin_tag
        src.last_verified = now

        if is_new:
            result.sources_created += 1
        else:
            result.sources_updated += 1

    db.commit()
    return result
