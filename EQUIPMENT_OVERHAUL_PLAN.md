# Equipment Page Overhaul — Implementation Plan

Internal equipment catalog at `/equipment/`. Goal: turn it from a static spec list into an
accurate, image-complete **sourcing & procurement** tool the ops team can actually buy from.

## Decisions locked with Steve

| Question | Decision |
|---|---|
| Micro markets / kiosks (custom-quoted everywhere) | **List with a "Starting at" price** (sourced from real components; final by quote) |
| Distributor / sourcing depth | **Full price-comparison sourcing** — multiple distributors per unit, best-buy highlighted |
| Images | **Real manufacturer/distributor photos, downloaded & stored locally** |
| Traditional-vending breadth | **Curated best-sellers (~8–12 new units)** |

Hard rules from Steve: equipment must **stay accurate**; **no price = not listed** (markets/kiosks
use a clearly-labeled "Starting at"); **every unit has a real picture**; add
**A&M Equipment Sales** (amequipmentsales.com) as a distributor; cover **AI smart coolers +
micro markets + traditional vending**.

---

## What's wrong today (live prod, 21 units)

**Accuracy regressions from the AI-refresh job (the #1 thing to fix):**
- `Cantaloupe Kiosk` → **$995** — bad product match.
- `Cantaloupe Micro Market` → **$1,795–$9,495** — that's a cooler price range, not a market.
- `Crane Merchant Combo 5591` → **$10,995–$11,995** sourced from Crane's **European** site (seed had ~$5–7.5k).

**7 units have no price** (violate the rule): `365 PicoCooler Vision`, `SandStar ARK`,
`Jofemar Vision ES Plus`, `365 NanoMarket`, `Avanti Self-Checkout Kiosk`, `365 Micro Market`,
`Avanti Micro Market`.

**6 priced units have no image:** Cantaloupe Smart Store 600 & 700, Crane Merchant Combo,
AMS Sensit Touch 39, Cantaloupe Kiosk, Cantaloupe Micro Market. One image (`PicoCooler`, id 9)
is a **hotlinked external URL** that will eventually break.

**Root cause to address:** the AI refresh overwrites curated data with no guard, so accuracy
decays every run. The overhaul adds a verified/locked guard so this can't keep happening.

---

## Part 1 — Data model (`app/models/equipment.py` + Alembic migration)

Pricing moves from a single number on the unit to **per-distributor sources**, with the unit
keeping a denormalized "best price" for fast catalog rendering.

**New `Distributor` table** (supplier directory):
`id, name, website, phone, location, distributor_type (distributor|manufacturer|reseller),
financing (bool), fast_ship (bool), notes, created_at`.

**New `EquipmentSource` table** (unit ↔ distributor offering):
`id, equipment_unit_id (FK, indexed), distributor_id (FK), distributor_url, price_low,
price_high, price_notes, lead_time_days_min, lead_time_days_max, in_stock (bool),
stock_notes, last_verified (datetime), created_at`.

**`EquipmentUnit` additions:**
- `category` is replaced/served by an expanded `equipment_type` set (see Part 4).
- `price_is_starting: bool` — drives the "Starting at $X" label for markets/kiosks.
- `status: str = "active"` — `active | archived`. We **archive, never hard-delete**, so
  removals are reversible and prod stays safe.
- `is_verified: bool` (or reuse `data_confidence == "verified"`) — protects curated rows from
  AI-refresh overwrite.
- `price_low/price_high` stay as the denormalized **best (lowest) price across sources**,
  recomputed by a helper whenever sources change.

**Migration:** `alembic revision --autogenerate` creates `distributors`, `equipment_sources`,
and the new `equipment_units` columns. Per the repo's bootstrap gotcha, existing prod runs
`alembic upgrade head` (not `create_all`), so the migration is **required** for prod — verify
`alembic upgrade head` applies cleanly on a copy of the prod schema.

---

## Part 2 — Data curation (accuracy pass)

Run as a reviewed `scripts/curate_equipment.py` (idempotent), then applied to prod after backup.

**Fix corrupted prices** → set verified values + real US source link, mark `data_confidence="verified"`:
- Crane Merchant Combo → defensible US price w/ source; if none, archive and rely on the
  AMS/USI combos we can actually source.
- Cantaloupe Kiosk / Cantaloupe Micro Market → see consolidation below.

**Resolve the 7 no-price units:**

| Unit | Action |
|---|---|
| 365 PicoCooler Vision | Archive (contact-only, no defensible price) |
| SandStar ARK | Archive (demo-only pricing) |
| Jofemar Vision ES Plus | Archive (no US price) |
| 365 NanoMarket, Avanti Kiosk, Cantaloupe Kiosk | Consolidate into **Micro-Market Kiosk** package(s) with sourced "Starting at" pricing; list 365/Cantaloupe/Avanti as platform options in the detail, not as priced SKUs |
| 365 / Cantaloupe / Avanti Micro Market | Consolidate into PMM **Micro-Market packages** (Starter / Standard / Premium) priced "Starting at" from real components (kiosk + coolers + racks) — this is what PMM actually deploys |

Every price assigned in this pass gets a real source row and `verified` confidence. Anything that
can't be defensibly priced is **archived**, not shown.

---

## Part 3 — Distributor sourcing data (`scripts/seed_distributors.py`)

Seed the supplier directory and attach `EquipmentSource` rows so the team sees where to buy:
- **A&M Equipment Sales** — Lithonia, GA · 770-482-7993 · since 1964 · financing + Fast-Ship.
- **VendGuys**, **GeniusVend** (existing HAHA sources), **AVS Companies**, **Cantaloupe direct**,
  **365 Retail Markets direct**, **Micromart**, plus manufacturer-direct rows where relevant.

Example multi-source rows (real prices gathered this session):
- HAHA Mini 360C: VendGuys **$3,449** · A&M **$3,095 (best)**
- HAHA Pro 542CT: VendGuys $4,700 · A&M **$4,395 (best)**
- HAHA Ultra 1200CT: VendGuys $7,300 · A&M **$6,895 (best)**
- HAHA Freezer 550CT: VendGuys $4,949 · A&M **$5,895**

Catalog card shows **best price + "N sources"**; detail shows the full comparison.

---

## Part 4 — Catalog expansion (curated ~8–12, all priced + sourced from A&M)

**Expanded `equipment_type` map** (router `_TYPES` + icons + brand color chips for AMS, Seaga,
USI, Vendo, Royal, Imbera, Crane, A&M):
`smart_cooler, freezer, combo, drink, snack, glass_cooler, kiosk, micro_market`.

**New units (representative best-sellers, real A&M pricing):**
- Combo: **AMS 39 Combo** $7,295 · **Seaga QB4000** $4,395
- Drink: **Vendo 721** $5,495 · **Royal 650** $5,395
- Snack: **AMS 39 Snack** $5,695 · **USI Mercato 4000** $6,395
- Glass-door coolers (non-smart): **Imbera VR10** $1,495 · **Imbera VRD43 double-door** $3,295 · **Imbera VFS24 freezer** $3,495
- Micro-market package(s): "Starting at" tiers built from the above components.

Final 8–12 chosen during implementation for category balance + image availability.

---

## Part 5 — Images (real, stored locally) — `scripts/fetch_equipment_images.py`

Reuse the existing `_download_image` + og:image scraper + Firecrawl fallback. For every active
unit missing a local image (the 6 above + all new units), pull the product photo from its best
source URL and store at `app/static/images/equipment/{id}.{ext}`. Localize the id 9 hotlink (if
that unit survives). Target **100% real-photo coverage**; branded placeholder remains only as a
last-resort safety net.

---

## Part 6 — UI / UX (what makes it useful for the ops team)

**Catalog (`index.html`, `_unit_grid.html`):**
- Group into category sections (Smart Coolers, Freezers, Combo, Drink, Snack, Glass Coolers,
  Kiosks, Micro Markets); updated filter chips + brand chips.
- Card: **best price** (or "Starting at"), **"N distributors / best: A&M"** badge, lead time,
  AI badge, verified/needs-review indicator.

**Detail (`detail.html`):**
- New **Sourcing & Procurement** card: distributor comparison table (name · price · lead time ·
  in-stock · link), **best price highlighted**, supplier contact (phone/website/financing/fast-ship).
- "Starting at" treatment for markets/kiosks with a "final pricing by quote" note.
- **Inline source add/edit/delete** (HTMX) so the team maintains prices themselves.
- `verified` vs `needs review` badge.

**New Distributors tab** (third tab in `/equipment/`, beside Catalog & AI Refresh): supplier
directory with contacts, specialties, financing, Fast-Ship, typical lead times.

**Compare page:** add a best-price / best-source row.

**AI Refresh hardening:** skip units marked `verified`/`status=archived`; never overwrite a
verified price. Stops the accuracy decay that caused today's bad data.

---

## Part 7 — Routers / services (`app/routers/equipment.py`)

- Update `_TYPES` / `_MANUFACTURERS`; group catalog by category; eager-load sources; add a
  `best_price()` helper on the unit (min across sources, recomputed on source change).
- New endpoints: `GET /equipment/distributors` (tab); `POST/PUT/DELETE /equipment/{id}/sources`
  (HTMX inline editing); archive/unarchive toggle.
- Filter active-only by default; AI-refresh guard for verified/archived units.

## Part 8 — Tests (`pytest`, in-memory SQLite)

Unit↔source relationship; `best_price` computation; no-price exclusion / archive filtering;
catalog grouping; detail sourcing render; AI-refresh-skips-verified guard.

## Part 9 — Migration & deploy

1. `alembic revision --autogenerate -m "distributors + equipment sources"`; verify
   `alembic upgrade head` on a prod-schema copy.
2. Run locally: migration → `seed_distributors.py` → `curate_equipment.py` →
   catalog-expansion seed → `fetch_equipment_images.py`. Verify on local dev server.
3. **Back up prod** (snapshot) → apply curation/seed against prod Postgres (reviewed; archive,
   don't delete) → fetch images.
4. `ruff check . --fix && ruff format . && pytest` → commit → push `main` → Render auto-deploy
   (preDeploy runs `init_db.py` / `alembic upgrade head`).

## Risks / call-outs

- **Prod data changes**: removals are archives (reversible); confirm the archive list before
  applying. Backup first.
- **Image hotlink fragility**: solved by local storage.
- **Re-corruption**: solved by the AI-refresh verified-guard.
- **Micro-market "Starting at"** numbers are estimates built from real component costs and are
  labeled as such — final pricing remains by quote.
