from __future__ import annotations

import json
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentJob
from app.models.inventory import InventoryLog, Product, Supplier
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
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        website=website or None,
        notes=notes or None,
    )
    db.add(supplier)
    db.commit()
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
    init_supplier: str | None = None,
    tab: str = "products",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sid = int(supplier_id) if supplier_id else None
    init_sid = int(init_supplier) if init_supplier else None
    q = db.query(Product).filter(Product.is_active.is_(True))
    if category:
        q = q.filter(Product.category == category)
    if sid:
        q = q.filter(Product.primary_supplier_id == sid)
    if low_stock:
        q = q.filter(Product.par_level.is_not(None), Product.on_hand_qty < Product.par_level)
    products = q.order_by(Product.category, Product.name).all()
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
    _set_setting(db, "inventory_search_provider", search_provider)
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
    db.add(job)
    db.commit()
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
    par_level: str = Form(""),
    primary_supplier_id: str = Form(""),
    restock_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = Product(
        sku=sku,
        name=name,
        brand=brand or None,
        category=category or None,
        unit_cost=float(unit_cost) if unit_cost else None,
        sell_price=float(sell_price) if sell_price else None,
        unit_size=unit_size or None,
        par_level=int(par_level) if par_level else None,
        primary_supplier_id=int(primary_supplier_id) if primary_supplier_id else None,
        restock_notes=restock_notes or None,
    )
    db.add(product)
    db.commit()
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
    db: Session = Depends(get_db),
) -> HTMLResponse:
    vendor_cfg = load_vendor_settings(db)
    params = {
        "product_query": product_query.strip(),
        "vendors": vendors or VENDOR_KEYS,
        "search_provider": search_provider,
        "vendor_config": vendor_cfg,
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
    return templates.TemplateResponse(
        request,
        "inventory/_comparator_poll.html",
        {"job": job, "results": results, "input_params": input_params, "vendor_meta": VENDOR_META},
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
    return templates.TemplateResponse(
        request,
        "inventory/compare_results.html",
        {
            "active_nav": "inventory",
            "job": job,
            "results": results,
            "input_params": input_params,
            "vendor_meta": VENDOR_META,
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
    par_level: str = Form(""),
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
    product.par_level = int(par_level) if par_level else None
    product.primary_supplier_id = int(primary_supplier_id) if primary_supplier_id else None
    product.restock_notes = restock_notes or None
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.post("/{product_id}/restock", response_class=HTMLResponse)
def product_restock(
    product_id: int,
    qty: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    product.on_hand_qty += qty
    log = InventoryLog(
        product_id=product_id,
        log_type="restock",
        qty_change=qty,
        qty_after=product.on_hand_qty,
        notes=notes or None,
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.delete("/{product_id}", response_class=HTMLResponse)
def product_deactivate(product_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    product = db.get(Product, product_id)
    if product:
        product.is_active = False
        db.commit()
    return HTMLResponse(content="", status_code=200)
