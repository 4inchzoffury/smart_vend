"""Google Sheets sync helpers.

Authentication uses a service account JSON file. Set GOOGLE_SHEETS_CREDS_FILE and
SPREADSHEET_ID in .env before calling any sync function.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings

_client = None


def _get_client():  # type: ignore[return]
    """Return a cached gspread client, re-authenticating as needed."""
    global _client
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            settings.google_sheets_creds_file, scopes=scopes
        )
        _client = gspread.authorize(creds)
    except Exception as exc:
        return {"error": str(exc)}
    return _client


def _get_sheet(tab_name: str):
    client = _get_client()
    if isinstance(client, dict):
        return client  # error dict
    try:
        return client.open_by_key(settings.spreadsheet_id).worksheet(tab_name)
    except Exception as exc:
        return {"error": str(exc)}


def _not_configured() -> bool:
    return not settings.spreadsheet_id or not settings.google_sheets_creds_file


def push_research_tasks(db: Session) -> dict[str, Any]:
    if _not_configured():
        return {"status": "skipped", "reason": "SPREADSHEET_ID not configured"}
    from app.models.research import ResearchTask

    sheet = _get_sheet("Research_Tasks")
    if isinstance(sheet, dict):
        return {"status": "error", **sheet}

    tasks = db.query(ResearchTask).order_by(ResearchTask.section, ResearchTask.task_number).all()
    header = ["task_number", "section_name", "what", "why", "how_source", "owner",
              "due_date_raw", "status", "priority", "notes", "updated_at"]
    rows = [header] + [
        [
            t.task_number, t.section_name, t.what, t.why or "", t.how_source or "",
            t.owner or "", t.due_date_raw or "",
            t.status.replace("_", " ").title(), t.priority,
            t.notes or "", str(t.updated_at or ""),
        ]
        for t in tasks
    ]
    sheet.clear()
    sheet.update(rows, "A1")

    now = datetime.now()
    for t in tasks:
        t.synced_at = now
    db.commit()
    return {"status": "ok", "rows_pushed": len(tasks)}


def pull_research_tasks(db: Session) -> dict[str, Any]:
    if _not_configured():
        return {"status": "skipped", "reason": "SPREADSHEET_ID not configured"}
    from app.models.research import ResearchTask

    sheet = _get_sheet("Research_Tasks")
    if isinstance(sheet, dict):
        return {"status": "error", **sheet}

    status_map = {
        "not started": "not_started",
        "in progress": "in_progress",
        "blocked": "blocked",
        "done": "done",
    }

    rows = sheet.get_all_records()
    updated = created = 0
    for row in rows:
        task_number = str(row.get("task_number", "")).strip()
        if not task_number:
            continue
        task = db.query(ResearchTask).filter(ResearchTask.task_number == task_number).first()
        raw_status = str(row.get("status", "")).lower()
        status = status_map.get(raw_status, "not_started")
        if task:
            task.status = status
            task.notes = str(row.get("notes", "")) or None
            task.priority = str(row.get("priority", "medium")).lower() or "medium"
            updated += 1
        else:
            created += 1
    db.commit()
    return {"status": "ok", "updated": updated, "created": created}


def push_product_catalog(db: Session) -> dict[str, Any]:
    if _not_configured():
        return {"status": "skipped", "reason": "SPREADSHEET_ID not configured"}
    from app.models.inventory import Product

    sheet = _get_sheet("Product_Catalog")
    if isinstance(sheet, dict):
        return {"status": "error", **sheet}

    products = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .order_by(Product.category, Product.name)
        .all()
    )
    header = ["sku", "name", "brand", "category", "unit_cost", "sell_price",
              "unit_size", "par_level", "on_hand_qty", "supplier"]
    rows = [header] + [
        [
            p.sku, p.name, p.brand or "", p.category or "",
            p.unit_cost or "", p.sell_price or "",
            p.unit_size or "", p.par_level or "", p.on_hand_qty,
            p.primary_supplier.name if p.primary_supplier else "",
        ]
        for p in products
    ]
    sheet.clear()
    sheet.update(rows, "A1")
    return {"status": "ok", "rows_pushed": len(products)}


def pull_product_catalog(db: Session) -> dict[str, Any]:
    if _not_configured():
        return {"status": "skipped", "reason": "SPREADSHEET_ID not configured"}
    from app.models.inventory import Product

    sheet = _get_sheet("Product_Catalog")
    if isinstance(sheet, dict):
        return {"status": "error", **sheet}

    rows = sheet.get_all_records()
    updated = 0
    for row in rows:
        sku = str(row.get("sku", "")).strip()
        if not sku:
            continue
        product = db.query(Product).filter(Product.sku == sku).first()
        if product:
            if row.get("sell_price"):
                product.sell_price = float(row["sell_price"])
            if row.get("par_level"):
                product.par_level = int(row["par_level"])
            updated += 1
    db.commit()
    return {"status": "ok", "updated": updated}


def push_sales_pipeline(db: Session) -> dict[str, Any]:
    if _not_configured():
        return {"status": "skipped", "reason": "SPREADSHEET_ID not configured"}
    from app.models.sales import Prospect

    sheet = _get_sheet("Sales_Pipeline")
    if isinstance(sheet, dict):
        return {"status": "error", **sheet}

    prospects = db.query(Prospect).order_by(Prospect.pipeline_stage, Prospect.company_name).all()
    header = ["company_name", "contact_name", "contact_email", "contact_phone",
              "venue_type", "city", "pipeline_stage", "tier", "next_action",
              "next_action_date", "notes"]
    rows = [header] + [
        [
            p.company_name, p.contact_name or "", p.contact_email or "",
            p.contact_phone or "", p.venue_type or "", p.city,
            p.pipeline_stage, p.tier or "", p.next_action or "",
            str(p.next_action_date or ""), p.notes or "",
        ]
        for p in prospects
    ]
    sheet.clear()
    sheet.update(rows, "A1")
    return {"status": "ok", "rows_pushed": len(prospects)}
