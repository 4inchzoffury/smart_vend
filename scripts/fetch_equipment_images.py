"""Ensure active equipment units have a real, locally-stored product photo.

Run:  python scripts/fetch_equipment_images.py            (download missing, set image_url)
      python scripts/fetch_equipment_images.py --force    (re-download all listed)

Files are stored under app/static/images/equipment/ keyed by a stable SLUG (not the DB id),
so the committed files survive on Render's ephemeral filesystem and match regardless of the
auto-assigned id on prod vs. local. The unit's image_url is pointed at the local copy.

If a committed file already exists for a slug, the download is skipped and image_url is just
(re)pointed at it — this is what runs harmlessly in the Render preDeploy step.

Source notes:
  * Traditional vending + glass coolers: A&M Equipment Sales product photos.
  * Cantaloupe SmartStores: Cantaloupe store CDN.
  * Micro-market kiosk/packages: representative real micro-market photos (365 CDN), since an
    assembled package has no single product photo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import engine
from app.models.equipment import EquipmentUnit

_IMG_DIR = Path(__file__).parent.parent / "app" / "static" / "images" / "equipment"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_CT_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

# (manufacturer, product_name) -> (image URL, stable slug filename stem)
IMAGE_SPECS: dict[tuple[str, str], tuple[str, str]] = {
    ("AMS", "AMS 39 Combo"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2016/08/ams39combobig2-opt-300x450.jpg",
        "ams-39-combo",
    ),
    ("Seaga", "Seaga QB4000 Combo"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2024/04/Seaga-QB4000.png",
        "seaga-qb4000-combo",
    ),
    ("AMS", "AMS 39 Snack Machine"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2016/08/AMS-39-Snack-opt-300x450.jpg",
        "ams-39-snack",
    ),
    ("USI", "USI Mercato 4000 Snack Machine"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2024/06/USI-Mercato-4000.png",
        "usi-mercato-4000",
    ),
    ("Imbera", "Imbera VRD43 Double-Door Cooler"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2015/12/VRD43_BLACK-STD_GRAVITY-300x450.png",
        "imbera-vrd43",
    ),
    ("Imbera", "Imbera VFS24 Single-Door Freezer"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2015/12/VFS24_BLACK-STD-300x450.png",
        "imbera-vfs24",
    ),
    ("Vendo", "Vendo 721 Drink Machine"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2015/12/vendo-621-721__57526-1-300x450.webp",
        "vendo-721",
    ),
    ("Royal", "Royal 650 Drink Machine"): (
        "https://www.amequipmentsales.com/wp-content/uploads/2015/12/royal-650-full-opt-300x450.jpg",
        "royal-650",
    ),
    ("Cantaloupe", "Smart Store 600 Single"): (
        "https://store.cantaloupe.com/cdn/shop/files/Store-SmartStore600Single_700x700.png?v=1751406904",
        "cantaloupe-smartstore-600",
    ),
    ("Cantaloupe", "Smart Store 700 Single"): (
        "https://store.cantaloupe.com/cdn/shop/files/Store-SmartStore700Single_512x512.png?v=1751406968",
        "cantaloupe-smartstore-700",
    ),
    ("Prime Micro Markets", "Micro Market Self-Checkout Kiosk"): (
        "https://365retailmarkets.com/sites/default/files/styles/width_scale_m/public/images/2024-05/PRODUCT_IMAGE_MM6_MINI.jpg.webp?itok=I3G2Qp45",
        "micro-market-kiosk",
    ),
    ("Prime Micro Markets", "Micro Market Starter Package"): (
        "https://365retailmarkets.com/sites/default/files/styles/width_scale_xl/public/images/2024-07/MM6-Markets-365-Micro-Market.jpg.webp?itok=_BR38Ou9",
        "micro-market-starter",
    ),
    ("Prime Micro Markets", "Micro Market Standard Package"): (
        "https://365retailmarkets.com/sites/default/files/styles/width_scale_xl/public/images/2024-07/MM6-Markets-365-Micro-Market.jpg.webp?itok=_BR38Ou9",
        "micro-market-standard",
    ),
}


def _existing_for(slug: str) -> Path | None:
    for ext in _CT_EXT.values():
        p = _IMG_DIR / f"{slug}{ext}"
        if p.exists() and p.stat().st_size > 1000:
            return p
    return None


def _download(url: str, slug: str) -> Path | None:
    _IMG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(
            timeout=20,
            follow_redirects=True,
            verify=False,  # noqa: S501 — local AV breaks TLS verify; harmless on Render
            headers={"User-Agent": _BROWSER_UA, "Accept": "image/*,*/*;q=0.8"},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "").split(";")[0].strip()
            ext = _CT_EXT.get(ct)
            if not ext:
                suffix = Path(url.split("?")[0]).suffix.lower()
                ext = suffix if suffix in _CT_EXT.values() else ".jpg"
            for old in _IMG_DIR.glob(f"{slug}.*"):
                old.unlink(missing_ok=True)
            dest = _IMG_DIR / f"{slug}{ext}"
            dest.write_bytes(resp.content)
            return dest
    except Exception as exc:  # noqa: BLE001
        print(f"  ! download failed for {slug}: {exc}")
        return None


def fetch(force: bool = False) -> None:
    ok, reused, failed = 0, 0, 0
    with Session(engine) as db:
        for (mfr, name), (url, slug) in IMAGE_SPECS.items():
            unit = (
                db.query(EquipmentUnit)
                .filter(EquipmentUnit.manufacturer == mfr, EquipmentUnit.product_name == name)
                .first()
            )
            if not unit:
                print(f"  ! unit not found: {mfr} / {name}")
                failed += 1
                continue

            path = None if force else _existing_for(slug)
            if path is not None:
                reused += 1
            else:
                path = _download(url, slug)
                if path is not None:
                    print(f"  [ok] {name} -> {path.name}")
                    ok += 1
                else:
                    failed += 1
                    continue

            unit.image_url = f"/static/images/equipment/{path.name}"
            db.commit()
    print(f"Images: {ok} downloaded, {reused} reused committed file, {failed} failed.")


if __name__ == "__main__":
    fetch(force="--force" in sys.argv)
