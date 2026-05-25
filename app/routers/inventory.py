from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models.agent import AgentJob
from app.models.inventory import InventoryLog, Product, ProductSource, Supplier
from app.services import inventory_agent, price_comparator
from app.services.inventory_agent import PRODUCT_CATEGORY_OPTIONS
from app.services.price_comparator import VENDOR_KEYS, load_vendor_settings, save_vendor_setting
from app.services.price_fetcher.models import VENDOR_META
from app.views import templates

router = APIRouter(prefix="/inventory", tags=["inventory"])

PRODUCT_CATEGORIES = [
    "beverage_water", "beverage_energy", "beverage_soda", "beverage_juice",
    "snack_chips", "snack_candy", "snack_healthy",
    "meal_sandwich", "meal_salad", "personal_care", "other",
]

# Human-readable labels for internal category slugs
CATEGORY_LABELS: dict[str, str] = {
    "beverage_water": "Water / Still Beverages",
    "beverage_energy": "Energy Drinks",
    "beverage_soda": "Soda / Soft Drinks",
    "beverage_juice": "Juice",
    "snack_chips": "Chips & Crisps",
    "snack_candy": "Candy & Confections",
    "snack_healthy": "Healthy Snacks",
    "meal_sandwich": "Sandwiches & Wraps",
    "meal_salad": "Salads & Fresh Food",
    "personal_care": "Gum, Mints & Personal Care",
    "other": "Other",
}


def _get_setting(db: Session, key: str, default: str = "") -> str:
    from app.models.settings import AppSetting

    row = db.get(AppSetting, key)
    return row.value if row else default


def _set_setting(db: Session, key: str, value: str) -> None:
    from app.models.settings import AppSetting

    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip().replace(",", "").replace("$", "")
    return int(value) if value.lstrip("-").isdigit() else None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", "").replace("$", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@router.get("/suppliers", response_class=HTMLResponse)
def suppliers_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request, "inventory/suppliers.html", {"active_nav": "inventory", "suppliers": suppliers}
    )


@router.post("/suppliers", response_class=HTMLResponse)
def supplier_create(
    name: str = Form(...),
    supplier_type: str = Form(""),
    account_number: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    website: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    supplier = Supplier(
        name=name,
        supplier_type=supplier_type or None,
        account_number=account_number or None,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        website=website or None,
        notes=notes or None,
    )
    try:
        db.add(supplier)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to create supplier %s", name)
        raise HTTPException(status_code=500, detail="Database error saving supplier")
    return RedirectResponse(url="/inventory/suppliers", status_code=303)


@router.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def supplier_edit_form(
    supplier_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        return Response(status_code=404)
    return templates.TemplateResponse(
        request, "inventory/supplier_edit.html",
        {"active_nav": "inventory", "supplier": supplier}
    )


@router.post("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_update(
    supplier_id: int,
    name: str = Form(...),
    supplier_type: str = Form(""),
    account_number: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    website: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        return Response(status_code=404)
    supplier.name = name
    supplier.supplier_type = supplier_type or None
    supplier.account_number = account_number or None
    supplier.contact_name = contact_name or None
    supplier.contact_email = contact_email or None
    supplier.contact_phone = contact_phone or None
    supplier.website = website or None
    supplier.notes = notes or None
    db.commit()
    return RedirectResponse(url="/inventory/suppliers", status_code=303)


@router.delete("/suppliers/{supplier_id}", response_class=HTMLResponse)
def supplier_delete(supplier_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    supplier = db.get(Supplier, supplier_id)
    if supplier:
        db.delete(supplier)
        db.commit()
    return HTMLResponse(content="", status_code=200)


@router.get("/", response_class=HTMLResponse)
def inventory_index(
    request: Request,
    category: str | None = None,
    supplier_id: str | None = None,
    low_stock: bool = False,
    seasonal: bool = False,
    init_supplier: str | None = None,
    tab: str = "products",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sid = int(supplier_id) if supplier_id else None
    init_sid = int(init_supplier) if init_supplier else None
    # Eager-load sources (+their suppliers) and the primary supplier so the Best
    # Source column and cost/margin don't fire a query per product (N+1).
    q = (
        db.query(Product)
        .options(
            selectinload(Product.sources).selectinload(ProductSource.supplier),
            joinedload(Product.primary_supplier),
        )
        .filter(Product.is_active.is_(True))
    )
    if category:
        q = q.filter(Product.category == category)
    if sid:
        q = q.filter(Product.primary_supplier_id == sid)
    if low_stock:
        q = q.filter(Product.par_level.is_not(None), Product.on_hand_qty < Product.par_level)
    if seasonal:
        q = q.filter(Product.is_seasonal.is_(True))
    products = q.order_by(Product.category, Product.name).all()

    margins = [p.margin_pct for p in products if p.margin_pct is not None]
    summary = {
        "total": len(products),
        "low_stock": sum(1 for p in products if p.is_low_stock),
        "avg_margin": (sum(margins) / len(margins)) if margins else None,
        "missing_cost": sum(1 for p in products if p.effective_cost is None),
        "sourced": sum(1 for p in products if p.source_count),
    }
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    db_cats = {r[0] for r in db.query(Product.category).distinct() if r[0]}
    categories = PRODUCT_CATEGORIES + [c for c in sorted(db_cats) if c not in PRODUCT_CATEGORIES]
    vendor_cfg = load_vendor_settings(db)
    compare_jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "price_comparison")
        .order_by(AgentJob.created_at.desc())
        .limit(5)
        .all()
    )
    search_provider = _get_setting(db, "inventory_search_provider", "duckduckgo")
    from app.config import settings as app_settings
    tavily_available = bool(app_settings.tavily_api_key)
    sourcing_jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "inventory_research")
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "inventory/index.html",
        {
            "active_nav": "inventory",
            "products": products,
            "suppliers": suppliers,
            "categories": categories,
            "category_labels": CATEGORY_LABELS,
            "category_filter": category,
            "supplier_filter": sid,
            "low_stock": low_stock,
            "seasonal_filter": seasonal,
            "summary": summary,
            "init_supplier_id": init_sid,
            "active_tab": tab,
            # comparator
            "vendor_keys": VENDOR_KEYS,
            "vendor_meta": VENDOR_META,
            "vendor_cfg": vendor_cfg,
            "compare_jobs": compare_jobs,
            "search_provider": search_provider,
            "tavily_available": tavily_available,
            # AI sourcing
            "category_options": PRODUCT_CATEGORY_OPTIONS,
            "current_provider": search_provider,
            "sourcing_jobs": sourcing_jobs,
        },
    )


@router.get("/search/usage", response_class=HTMLResponse)
def inventory_search_usage(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_tokens = (
        db.query(sql_func.sum(AgentJob.tokens_used))
        .filter(AgentJob.job_type == "inventory_research", AgentJob.created_at >= today_start)
        .scalar()
        or 0
    )
    total_tokens = (
        db.query(sql_func.sum(AgentJob.tokens_used))
        .filter(AgentJob.job_type == "inventory_research")
        .scalar()
        or 0
    )
    latest = (
        db.query(AgentJob)
        .filter(
            AgentJob.job_type == "inventory_research",
            AgentJob.ratelimit_tokens_remaining.isnot(None),
        )
        .order_by(AgentJob.finished_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        request,
        "leads/_usage_widget.html",
        {"today_tokens": today_tokens, "total_tokens": total_tokens, "latest_job": latest},
    )


@router.get("/search", response_class=HTMLResponse)
def inventory_search_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "inventory_research")
        .order_by(AgentJob.created_at.desc())
        .limit(100)
        .all()
    )
    current_provider = _get_setting(db, "inventory_search_provider", "duckduckgo")
    return templates.TemplateResponse(
        request,
        "inventory/search.html",
        {
            "active_nav": "inventory",
            "jobs": jobs,
            "category_options": PRODUCT_CATEGORY_OPTIONS,
            "current_provider": current_provider,
        },
    )


@router.post("/search", response_class=HTMLResponse)
def inventory_search_run(
    request: Request,
    background_tasks: BackgroundTasks,
    product_categories: list[str] = Form(default=[]),
    location_city: str = Form("Panama City"),
    location_state: str = Form("FL"),
    search_focus: str = Form(""),
    max_results: int = Form(15),
    search_provider: str = Form("duckduckgo"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    max_results = max(1, min(50, max_results))
    _set_setting(db, "inventory_search_provider", search_provider)

    # Auto-reset stale jobs stuck for over 2 hours
    stale_cutoff = datetime.now() - timedelta(hours=2)
    db.query(AgentJob).filter(
        AgentJob.job_type == "inventory_research",
        AgentJob.status.in_(["running", "pending"]),
        AgentJob.created_at < stale_cutoff,
    ).update({"status": "error", "error_message": "Auto-reset: exceeded 2-hour limit"})
    db.commit()

    location = f"{location_city.strip()}, {location_state.strip()}"
    params = {
        "product_categories": product_categories,
        "location": location,
        "search_focus": search_focus.strip(),
        "max_results": max_results,
        "search_provider": search_provider,
    }
    job = AgentJob(
        job_type="inventory_research",
        status="pending",
        input_params=json.dumps(params),
    )
    try:
        db.add(job)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to create inventory search job")
        raise HTTPException(status_code=500, detail="Database error creating job")
    background_tasks.add_task(inventory_agent.run_inventory_search_job, job.id)
    return RedirectResponse(url=f"/inventory/search/{job.id}", status_code=303)


@router.get("/search/jobs", response_class=HTMLResponse)
def inventory_search_jobs_list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "inventory_research")
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request, "inventory/_search_job_history.html", {"jobs": jobs}
    )


@router.get("/search/{job_id}/poll", response_class=HTMLResponse)
def inventory_search_poll(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return HTMLResponse(content="<div>Job not found</div>", status_code=404)
    supplier_results: list[dict] = []
    if job.status == "done" and job.draft_body:
        try:
            supplier_results = json.loads(job.draft_body)
        except Exception:
            supplier_results = []
    # Build a set of existing supplier names for status badges
    existing_names: set[str] = set()
    if supplier_results:
        names = [s.get("supplier_name", "").strip().lower() for s in supplier_results]
        rows = db.query(Supplier.name).filter(
            Supplier.name.in_([n for n in names if n])
        ).all()
        existing_names = {r[0].lower() for r in rows}
    return templates.TemplateResponse(
        request,
        "inventory/_search_job_status_card.html",
        {"job": job, "supplier_results": supplier_results, "existing_names": existing_names},
    )


@router.get("/search/{job_id}", response_class=HTMLResponse)
def inventory_search_job(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return Response(status_code=404)
    supplier_results: list[dict] = []
    if job.draft_body:
        try:
            supplier_results = json.loads(job.draft_body)
        except Exception:
            supplier_results = []
    existing_names: set[str] = set()
    supplier_id_map: dict[str, int] = {}
    if supplier_results:
        names = [s.get("supplier_name", "").strip().lower() for s in supplier_results]
        rows = db.query(Supplier.id, Supplier.name).filter(
            Supplier.name.in_([n for n in names if n])
        ).all()
        existing_names = {r[1].lower() for r in rows}
        supplier_id_map = {r[1].lower(): r[0] for r in rows}
    input_params: dict = {}
    if job.input_params:
        try:
            input_params = json.loads(job.input_params)
        except Exception:
            pass
    return templates.TemplateResponse(
        request,
        "inventory/search_job.html",
        {
            "active_nav": "inventory",
            "job": job,
            "supplier_results": supplier_results,
            "existing_names": existing_names,
            "supplier_id_map": supplier_id_map,
            "input_params": input_params,
        },
    )


@router.post("/search/{job_id}/delete", response_class=HTMLResponse)
def inventory_search_delete(job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if job and job.job_type == "inventory_research":
        db.delete(job)
        db.commit()
    return HTMLResponse(content="", status_code=200)


@router.get("/new", response_class=HTMLResponse)
def product_new_form(
    request: Request, supplier_id: int | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request,
        "inventory/_product_form.html",
        {"product": None, "suppliers": suppliers, "selected_supplier_id": supplier_id},
    )


@router.post("/", response_class=HTMLResponse)
def product_create(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    unit_cost: str = Form(""),
    sell_price: str = Form(""),
    unit_size: str = Form(""),
    case_pack_qty: str = Form(""),
    par_level: str = Form(""),
    is_seasonal: bool = Form(False),
    primary_supplier_id: str = Form(""),
    restock_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        parsed_cost = float(unit_cost) if unit_cost else None
        parsed_sell = float(sell_price) if sell_price else None
        parsed_pack = int(case_pack_qty) if case_pack_qty else None
        parsed_par = int(par_level) if par_level else None
        parsed_supplier = int(primary_supplier_id) if primary_supplier_id else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid numeric value: {exc}") from exc

    if parsed_cost is not None and parsed_cost < 0:
        raise HTTPException(status_code=422, detail="Unit cost cannot be negative")
    if parsed_par is not None and parsed_par < 0:
        raise HTTPException(status_code=422, detail="Par level cannot be negative")

    product = Product(
        sku=sku,
        name=name,
        brand=brand or None,
        category=category or None,
        unit_cost=parsed_cost,
        sell_price=parsed_sell,
        unit_size=unit_size or None,
        case_pack_qty=parsed_pack,
        par_level=parsed_par,
        is_seasonal=is_seasonal,
        primary_supplier_id=parsed_supplier,
        restock_notes=restock_notes or None,
    )
    try:
        db.add(product)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to create product %s", sku)
        raise HTTPException(status_code=500, detail="Database error saving product")
    return RedirectResponse(url="/inventory/", status_code=303)


# ---------------------------------------------------------------------------
# Price Comparator routes  (must be before /{product_id} wildcard routes)
# ---------------------------------------------------------------------------

@router.get("/compare/stores", response_class=HTMLResponse)
def compare_stores(
    request: Request,
    brand: str = Query("walmart"),
    compare_walmart_zip: str = Query(""),
    compare_sams_zip: str = Query(""),
) -> HTMLResponse:
    """Return nearby store list HTML for store picker in settings panel."""
    from app.services import store_locator

    zip_code = (compare_walmart_zip if brand == "walmart" else compare_sams_zip).strip()
    stores: list[dict] = []
    error: str | None = None

    if zip_code:
        try:
            stores = store_locator.find_stores(zip_code, brand)
        except Exception as exc:
            error = str(exc)
    else:
        error = "Enter a ZIP code first."

    return templates.TemplateResponse(
        request,
        "inventory/_store_picker.html",
        {
            "stores": stores,
            "brand": brand,
            "zip_code": zip_code,
            "error": error,
        },
    )


@router.post("/compare/settings", response_class=HTMLResponse)
def compare_settings_save(
    request: Request,
    compare_sams_zip: str = Form(""),
    compare_sams_club_id: str = Form(""),
    compare_sams_club_name: str = Form(""),
    compare_walmart_zip: str = Form(""),
    compare_walmart_store_id: str = Form(""),
    compare_walmart_store_name: str = Form(""),
    compare_webstaurantstore_email: str = Form(""),
    compare_vendors_supply_email: str = Form(""),
    compare_candy_machines_email: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Save vendor account config."""
    settings_to_save: dict[str, str] = {
        "compare_webstaurantstore_email": compare_webstaurantstore_email.strip(),
        "compare_vendors_supply_email": compare_vendors_supply_email.strip(),
        "compare_candy_machines_email": compare_candy_machines_email.strip(),
        "compare_sams_zip": compare_sams_zip.strip(),
        "compare_walmart_zip": compare_walmart_zip.strip(),
    }

    sams_club_id = compare_sams_club_id.strip()
    if sams_club_id:
        settings_to_save["compare_sams_club_id"] = sams_club_id
        if compare_sams_club_name.strip():
            settings_to_save["compare_sams_club_name"] = compare_sams_club_name.strip()

    walmart_store_id = compare_walmart_store_id.strip()
    if walmart_store_id:
        settings_to_save["compare_walmart_store_id"] = walmart_store_id
        if compare_walmart_store_name.strip():
            settings_to_save["compare_walmart_store_name"] = compare_walmart_store_name.strip()

    for key, value in settings_to_save.items():
        if value:
            save_vendor_setting(db, key, value)

    # Redirect so the full page reloads with updated vendor badges in the search form
    from starlette.responses import Response as StarletteResponse
    resp = StarletteResponse(status_code=200)
    resp.headers["HX-Redirect"] = "/inventory/?tab=compare"
    return resp


@router.post("/compare", response_class=HTMLResponse)
def compare_run(
    request: Request,
    background_tasks: BackgroundTasks,
    product_query: str = Form(...),
    vendors: list[str] = Form(default=[]),
    search_provider: str = Form("duckduckgo"),
    product_id: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    vendor_cfg = load_vendor_settings(db)
    params = {
        "product_query": product_query.strip(),
        "vendors": vendors or VENDOR_KEYS,
        "search_provider": search_provider,
        "vendor_config": vendor_cfg,
        # When launched from a product detail page, results can be saved back as
        # ProductSource rows for that SKU (see /sources/from-comparison).
        "product_id": _to_int(product_id),
    }
    job = AgentJob(
        job_type="price_comparison",
        status="pending",
        input_params=json.dumps(params),
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(price_comparator.run_price_comparison_job, job.id)
    return RedirectResponse(url=f"/inventory/compare/{job.id}", status_code=303)


@router.get("/compare/history", response_class=HTMLResponse)
def compare_history(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "price_comparison")
        .order_by(AgentJob.created_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(
        request, "inventory/_comparator_history.html", {"jobs": jobs}
    )


@router.get("/compare/{job_id}/poll", response_class=HTMLResponse)
def compare_poll(job_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return HTMLResponse(content="<div>Job not found</div>", status_code=404)
    results: list[dict] = []
    if job.status == "done" and job.draft_body:
        try:
            results = json.loads(job.draft_body)
            results.sort(key=lambda r: (r.get("unit_price") is None, r.get("unit_price") or 0))
        except Exception:
            pass
    input_params: dict = {}
    if job.input_params:
        try:
            input_params = json.loads(job.input_params)
        except Exception:
            pass
    target_product = None
    if input_params.get("product_id"):
        target_product = db.get(Product, input_params["product_id"])
    return templates.TemplateResponse(
        request,
        "inventory/_comparator_poll.html",
        {
            "job": job,
            "results": results,
            "input_params": input_params,
            "vendor_meta": VENDOR_META,
            "target_product": target_product,
        },
    )


@router.get("/compare/{job_id}", response_class=HTMLResponse)
def compare_results(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return Response(status_code=404)
    results: list[dict] = []
    if job.draft_body:
        try:
            results = json.loads(job.draft_body)
            results.sort(key=lambda r: (r.get("unit_price") is None, r.get("unit_price") or 0))
        except Exception:
            pass
    input_params: dict = {}
    if job.input_params:
        try:
            input_params = json.loads(job.input_params)
        except Exception:
            pass
    target_product = None
    if input_params.get("product_id"):
        target_product = db.get(Product, input_params["product_id"])
    return templates.TemplateResponse(
        request,
        "inventory/compare_results.html",
        {
            "active_nav": "inventory",
            "job": job,
            "results": results,
            "input_params": input_params,
            "vendor_meta": VENDOR_META,
            "target_product": target_product,
        },
    )


@router.post("/compare/{job_id}/delete", response_class=HTMLResponse)
def compare_delete(job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if job and job.job_type == "price_comparison":
        db.delete(job)
        db.commit()
    return HTMLResponse(content="", status_code=200)


# ---------------------------------------------------------------------------
# Restock Run — shopping list of below-par SKUs grouped by cheapest supplier
# (fixed path — must be declared before the /{product_id} wildcard below)
# ---------------------------------------------------------------------------

@router.get("/restock-run", response_class=HTMLResponse)
def restock_run(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    import math

    products = (
        db.query(Product)
        .options(
            selectinload(Product.sources).selectinload(ProductSource.supplier),
            joinedload(Product.primary_supplier),
        )
        .filter(
            Product.is_active.is_(True),
            Product.par_level.is_not(None),
            Product.on_hand_qty < Product.par_level,
        )
        .order_by(Product.category, Product.name)
        .all()
    )

    groups: dict[str, dict] = {}
    grand_total = 0.0
    for p in products:
        src = p.buying_source
        supplier_name = (
            src.supplier.name if src else (p.primary_supplier.name if p.primary_supplier else "Unassigned")
        )
        qty = p.qty_needed
        unit_cost = src.effective_unit_cost if src else p.effective_cost
        case_price = src.case_price if src else None
        pack = (src.case_pack_qty if src else None) or p.case_pack_qty
        cases = None
        line_cost = None
        if case_price and pack:
            cases = math.ceil(qty / pack)
            line_cost = cases * case_price
        elif unit_cost is not None:
            line_cost = qty * unit_cost

        grp = groups.setdefault(
            supplier_name,
            {"supplier_name": supplier_name, "lines": [], "subtotal": 0.0, "has_unknown": False},
        )
        grp["lines"].append(
            {
                "product": p,
                "qty_needed": qty,
                "source": src,
                "unit_cost": unit_cost,
                "case_price": case_price,
                "pack": pack,
                "cases": cases,
                "line_cost": line_cost,
                "in_stock": src.in_stock if src else False,
                "supplier_url": src.supplier_url if src else None,
            }
        )
        if line_cost is not None:
            grp["subtotal"] += line_cost
            grand_total += line_cost
        else:
            grp["has_unknown"] = True

    # Largest supplier orders first (tackle the big buys first); items with no
    # known supplier ("Unassigned") sink to the bottom.
    ordered = sorted(
        groups.values(),
        key=lambda g: (g["supplier_name"] == "Unassigned", -g["subtotal"], g["supplier_name"]),
    )
    return templates.TemplateResponse(
        request,
        "inventory/restock_run.html",
        {
            "active_nav": "inventory",
            "groups": ordered,
            "grand_total": grand_total,
            "total_skus": len(products),
            "category_labels": CATEGORY_LABELS,
        },
    )


# ---------------------------------------------------------------------------
# Product wildcard routes  (must be after all fixed-path routes above)
# ---------------------------------------------------------------------------

@router.get("/{product_id}/edit", response_class=HTMLResponse)
def product_edit_form(
    product_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request, "inventory/_product_form.html", {"product": product, "suppliers": suppliers}
    )


@router.post("/{product_id}", response_class=HTMLResponse)
def product_update(
    product_id: int,
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    unit_cost: str = Form(""),
    sell_price: str = Form(""),
    unit_size: str = Form(""),
    case_pack_qty: str = Form(""),
    par_level: str = Form(""),
    is_seasonal: bool = Form(False),
    primary_supplier_id: str = Form(""),
    restock_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    product.name = name
    product.brand = brand or None
    product.category = category or None
    product.unit_cost = float(unit_cost) if unit_cost else None
    product.sell_price = float(sell_price) if sell_price else None
    product.unit_size = unit_size or None
    product.case_pack_qty = int(case_pack_qty) if case_pack_qty else None
    product.par_level = int(par_level) if par_level else None
    product.is_seasonal = is_seasonal
    product.primary_supplier_id = int(primary_supplier_id) if primary_supplier_id else None
    product.restock_notes = restock_notes or None
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.post("/{product_id}/restock", response_class=HTMLResponse)
def product_restock(
    request: Request,
    product_id: int,
    qty: int = Form(...),
    notes: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    product.on_hand_qty += qty
    user = request.session.get("user") or {}
    log = InventoryLog(
        product_id=product_id,
        log_type="restock",
        qty_change=qty,
        qty_after=product.on_hand_qty,
        unit_cost_at_log=product.effective_cost,
        notes=notes or None,
        logged_by=user.get("email") or user.get("name"),
    )
    db.add(log)
    db.commit()
    dest = next if next.startswith("/inventory/") else "/inventory/"
    return RedirectResponse(url=dest, status_code=303)


@router.delete("/{product_id}", response_class=HTMLResponse)
def product_deactivate(product_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    product = db.get(Product, product_id)
    if product:
        product.is_active = False
        db.commit()
    return HTMLResponse(content="", status_code=200)


# ---------------------------------------------------------------------------
# Product detail page + per-supplier sourcing  (wildcard — keep after the above)
# ---------------------------------------------------------------------------

def _get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _sources_partial(request: Request, product: Product, db: Session) -> HTMLResponse:
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request,
        "inventory/_product_sources.html",
        {"product": product, "suppliers": suppliers},
    )


@router.get("/{product_id}", response_class=HTMLResponse)
def product_detail(
    product_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    product = _get_product_or_404(db, product_id)
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    logs = (
        db.query(InventoryLog)
        .filter(InventoryLog.product_id == product_id)
        .order_by(InventoryLog.logged_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "inventory/detail.html",
        {
            "active_nav": "inventory",
            "product": product,
            "suppliers": suppliers,
            "logs": logs,
            "category_labels": CATEGORY_LABELS,
        },
    )


@router.post("/{product_id}/sources", response_class=HTMLResponse)
def add_product_source(
    request: Request,
    product_id: int,
    supplier_id: str = Form(""),
    new_supplier_name: str = Form(""),
    supplier_url: str = Form(""),
    case_price: str = Form(""),
    case_pack_qty: str = Form(""),
    unit_cost: str = Form(""),
    unit_size: str = Form(""),
    min_order: str = Form(""),
    price_notes: str = Form(""),
    in_stock: bool = Form(False),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = _get_product_or_404(db, product_id)

    sup_id = _to_int(supplier_id)
    if not sup_id and new_supplier_name.strip():
        # Let the team add a supplier on the fly without leaving the form.
        existing = (
            db.query(Supplier).filter(Supplier.name == new_supplier_name.strip()).first()
        )
        if existing:
            sup_id = existing.id
        else:
            supplier = Supplier(name=new_supplier_name.strip())
            db.add(supplier)
            db.flush()
            sup_id = supplier.id
    if not sup_id:
        raise HTTPException(status_code=400, detail="A supplier is required")

    # Upsert: re-saving an existing supplier's price updates it rather than adding
    # a duplicate row for the same (product, supplier).
    source = next((s for s in product.sources if s.supplier_id == sup_id), None)
    if source is None:
        source = ProductSource(product_id=product.id, supplier_id=sup_id, origin="manual")
        db.add(source)
    source.supplier_url = supplier_url.strip() or None
    source.case_price = _to_float(case_price)
    source.case_pack_qty = _to_int(case_pack_qty) or product.case_pack_qty
    source.unit_cost = _to_float(unit_cost)
    source.unit_size = unit_size.strip() or None
    source.min_order = min_order.strip() or None
    source.price_notes = price_notes.strip() or None
    source.in_stock = in_stock
    source.last_verified = datetime.now()
    db.commit()
    db.refresh(product)
    return _sources_partial(request, product, db)


@router.post("/{product_id}/sources/{source_id}/delete", response_class=HTMLResponse)
def delete_product_source(
    request: Request, product_id: int, source_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    product = _get_product_or_404(db, product_id)
    source = db.get(ProductSource, source_id)
    if source and source.product_id == product.id:
        db.delete(source)
        db.commit()
        db.refresh(product)
    return _sources_partial(request, product, db)


@router.post("/{product_id}/sources/{source_id}/preferred", response_class=HTMLResponse)
def toggle_preferred_product_source(
    request: Request, product_id: int, source_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    product = _get_product_or_404(db, product_id)
    source = db.get(ProductSource, source_id)
    if source and source.product_id == product.id:
        # Only one preferred source per product.
        for s in product.sources:
            s.is_preferred = s.id == source_id and not source.is_preferred
        db.commit()
        db.refresh(product)
    return _sources_partial(request, product, db)


@router.post("/{product_id}/sources/from-comparison", response_class=HTMLResponse)
def save_source_from_comparison(
    product_id: int,
    vendor_name: str = Form(...),
    vendor_key: str = Form(""),
    unit_price: str = Form(""),
    case_price: str = Form(""),
    case_qty: str = Form(""),
    unit_size: str = Form(""),
    url: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Persist one price-comparator result as a ProductSource for this SKU.

    Maps the comparator vendor to a Supplier (found by name, else created), so an
    ephemeral search becomes a durable, comparable supplier price.
    """
    product = _get_product_or_404(db, product_id)
    name = vendor_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Vendor name required")

    supplier = (
        db.query(Supplier).filter(sql_func.lower(Supplier.name) == name.lower()).first()
    )
    if not supplier:
        meta = VENDOR_META.get(vendor_key, {})
        supplier = Supplier(name=name, supplier_type=meta.get("type") or "online")
        db.add(supplier)
        db.flush()

    # Upsert so re-saving the same vendor for this SKU refreshes its price rather
    # than piling up duplicate rows.
    source = next((s for s in product.sources if s.supplier_id == supplier.id), None)
    if source is None:
        source = ProductSource(
            product_id=product.id, supplier_id=supplier.id, origin="comparator"
        )
        db.add(source)
    source.supplier_url = url.strip() or None
    source.case_price = _to_float(case_price)
    source.case_pack_qty = _to_int(case_qty) or product.case_pack_qty
    source.unit_cost = _to_float(unit_price)
    source.unit_size = unit_size.strip() or None
    source.price_notes = notes.strip() or None
    source.last_verified = datetime.now()
    db.commit()
    return HTMLResponse(
        '<span class="badge bg-success"><i class="bi bi-check-lg me-1"></i>Saved to '
        f'<a href="/inventory/{product.id}" class="text-white text-decoration-underline">product</a></span>'
    )
