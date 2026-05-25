import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentJob
from app.models.equipment import Distributor, EquipmentSource, EquipmentUnit
from app.views import templates

logger = logging.getLogger(__name__)

_EQUIPMENT_IMG_DIR = Path(__file__).parent.parent / "static" / "images" / "equipment"
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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


router = APIRouter(prefix="/equipment", tags=["equipment"])

_MANUFACTURERS = [
    "HAHA Vending",
    "Cantaloupe",
    "365 Retail Markets",
    "Micromart",
    "SandStar",
    "WEIMI",
    "Avanti Markets",
    "Crane Merchandising Systems",
    "AMS",
    "Seaga",
    "USI",
    "Vendo",
    "Royal",
    "Imbera",
    "Jofemar",
]

# Insertion order doubles as the catalog's category display order.
_TYPES = {
    "smart_cooler": "AI Smart Cooler",
    "freezer": "Smart Freezer",
    "combo": "Combo Machine",
    "drink": "Drink Machine",
    "snack": "Snack Machine",
    "glass_cooler": "Glass-Door Cooler",
    "kiosk": "Micro Market Kiosk",
    "micro_market": "Micro Market",
}


def _grouped_units(units: list[EquipmentUnit]) -> list[tuple[str, str, list[EquipmentUnit]]]:
    """Bucket units by equipment_type in _TYPES (category) order for sectioned display."""
    by_type: dict[str, list[EquipmentUnit]] = {}
    for u in units:
        by_type.setdefault(u.equipment_type, []).append(u)
    groups = [(k, label, by_type[k]) for k, label in _TYPES.items() if k in by_type]
    # Append any unexpected/legacy types (e.g. old "ambient") so nothing silently vanishes.
    for k, items in by_type.items():
        if k not in _TYPES:
            groups.append((k, k.replace("_", " ").title(), items))
    return groups


def _active_refresh_job(db: Session) -> AgentJob | None:
    """Return the most recent running/pending equipment refresh job, if any."""
    return (
        db.query(AgentJob)
        .filter(
            AgentJob.job_type == "equipment_refresh",
            AgentJob.status.in_(["pending", "running"]),
        )
        .order_by(AgentJob.created_at.desc())
        .first()
    )


@router.get("/", response_class=HTMLResponse)
def equipment_index(
    request: Request,
    tab: str = "catalog",
    manufacturer: str | None = None,
    equipment_type: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = db.query(EquipmentUnit)
    if not include_archived:
        query = query.filter(EquipmentUnit.status == "active")
    if manufacturer:
        query = query.filter(EquipmentUnit.manufacturer == manufacturer)
    if equipment_type:
        query = query.filter(EquipmentUnit.equipment_type == equipment_type)
    units = query.order_by(EquipmentUnit.manufacturer, EquipmentUnit.product_name).all()
    grouped = _grouped_units(units)

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            request,
            "equipment/_unit_grid.html",
            {"grouped": grouped, "units": units, "type_labels": _TYPES},
        )

    # Only show filter buttons for types/manufacturers that have active units in the DB.
    active = db.query(EquipmentUnit).filter(EquipmentUnit.status == "active")
    existing_types = {
        row[0] for row in active.with_entities(EquipmentUnit.equipment_type).distinct()
    }
    existing_manufacturers_set = {
        row[0] for row in active.with_entities(EquipmentUnit.manufacturer).distinct()
    }
    available_type_labels = {k: v for k, v in _TYPES.items() if k in existing_types}
    # Preserve preferred ordering from _MANUFACTURERS, then append any unlisted ones alphabetically
    available_manufacturers = [m for m in _MANUFACTURERS if m in existing_manufacturers_set]
    available_manufacturers += sorted(
        m for m in existing_manufacturers_set if m not in set(_MANUFACTURERS)
    )

    distributors = db.query(Distributor).order_by(Distributor.name).all()

    active_job = _active_refresh_job(db)
    all_jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "equipment_refresh")
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    last_job = all_jobs[0] if all_jobs else None
    unit_count = db.query(EquipmentUnit).filter(EquipmentUnit.status == "active").count()
    archived_count = db.query(EquipmentUnit).filter(EquipmentUnit.status == "archived").count()
    current_provider = _get_setting(db, "search_provider", "duckduckgo")

    return templates.TemplateResponse(
        request,
        "equipment/index.html",
        {
            "active_nav": "equipment",
            "active_tab": tab,
            "units": units,
            "grouped": grouped,
            "manufacturers": available_manufacturers,
            "type_labels": available_type_labels,
            "selected_manufacturer": manufacturer or "",
            "selected_type": equipment_type or "",
            "include_archived": include_archived,
            "distributors": distributors,
            "active_job": active_job,
            "all_jobs": all_jobs,
            "last_job": last_job,
            "unit_count": unit_count,
            "archived_count": archived_count,
            "current_provider": current_provider,
        },
    )


@router.get("/compare", response_class=HTMLResponse)
def equipment_compare(
    request: Request,
    ids: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    units = db.query(EquipmentUnit).filter(EquipmentUnit.id.in_(unit_ids)).all()
    id_order = {uid: idx for idx, uid in enumerate(unit_ids)}
    units = sorted(units, key=lambda u: id_order.get(u.id, 999))
    return templates.TemplateResponse(
        request,
        "equipment/compare.html",
        {
            "active_nav": "equipment",
            "units": units,
            "type_labels": _TYPES,
        },
    )


@router.get("/refresh")
def refresh_landing() -> RedirectResponse:
    """Redirect old /equipment/refresh URL to the new tabbed layout."""
    return RedirectResponse(url="/equipment/?tab=refresh", status_code=302)


@router.post("/refresh", response_class=HTMLResponse)
def equipment_refresh_start(
    request: Request,
    background_tasks: BackgroundTasks,
    search_provider: str = Form("duckduckgo"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Actually start the refresh job — only called when user clicks 'Start Refresh'."""
    from app.services.equipment_agent import run_equipment_refresh_job

    # Auto-reset stale jobs stuck for over 2 hours before checking for active job
    stale_cutoff = datetime.now() - timedelta(hours=2)
    db.query(AgentJob).filter(
        AgentJob.job_type == "equipment_refresh",
        AgentJob.status.in_(["running", "pending"]),
        AgentJob.created_at < stale_cutoff,
    ).update({"status": "error", "error_message": "Auto-reset: exceeded 2-hour limit"})
    db.commit()

    # Don't double-start if one is already running
    existing = _active_refresh_job(db)
    if existing:
        return RedirectResponse(url="/equipment/?tab=refresh", status_code=303)

    _set_setting(db, "search_provider", search_provider)

    job = AgentJob(
        job_type="equipment_refresh",
        status="pending",
        input_params=json.dumps({"unit_ids": [], "search_provider": search_provider}),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_equipment_refresh_job, job.id)
    return RedirectResponse(url="/equipment/?tab=refresh", status_code=303)


@router.get("/refresh/{job_id}/poll", response_class=HTMLResponse)
def refresh_poll(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    return templates.TemplateResponse(
        request,
        "equipment/_refresh_status.html",
        {"job": job},
    )


@router.post("/refresh/{job_id}/delete", response_class=HTMLResponse)
def refresh_delete(job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if job and job.job_type == "equipment_refresh":
        db.delete(job)
        db.commit()
    return HTMLResponse(content="", status_code=200)


# ── Sourcing (price comparison) ───────────────────────────────────────────────


def _get_unit_or_404(db: Session, unit_id: int) -> EquipmentUnit:
    unit = db.get(EquipmentUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Equipment unit not found")
    return unit


def _sources_partial(request: Request, unit: EquipmentUnit, db: Session) -> HTMLResponse:
    distributors = db.query(Distributor).order_by(Distributor.name).all()
    return templates.TemplateResponse(
        request,
        "equipment/_sources.html",
        {"unit": unit, "distributors": distributors},
    )


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip().replace(",", "").replace("$", "")
    return int(value) if value.isdigit() else None


@router.post("/{unit_id}/sources", response_class=HTMLResponse)
def add_source(
    request: Request,
    unit_id: int,
    distributor_id: str = Form(""),
    new_distributor_name: str = Form(""),
    distributor_url: str = Form(""),
    price_low: str = Form(""),
    price_high: str = Form(""),
    price_notes: str = Form(""),
    lead_time_days_min: str = Form(""),
    lead_time_days_max: str = Form(""),
    in_stock: bool = Form(False),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = _get_unit_or_404(db, unit_id)

    dist_id = _to_int(distributor_id)
    if not dist_id and new_distributor_name.strip():
        # Let the team add a supplier on the fly without leaving the form.
        existing = (
            db.query(Distributor).filter(Distributor.name == new_distributor_name.strip()).first()
        )
        if existing:
            dist_id = existing.id
        else:
            dist = Distributor(name=new_distributor_name.strip())
            db.add(dist)
            db.flush()
            dist_id = dist.id
    if not dist_id:
        raise HTTPException(status_code=400, detail="A distributor is required")

    source = EquipmentSource(
        equipment_unit_id=unit.id,
        distributor_id=dist_id,
        distributor_url=distributor_url.strip() or None,
        price_low=_to_int(price_low),
        price_high=_to_int(price_high),
        price_notes=price_notes.strip() or None,
        lead_time_days_min=_to_int(lead_time_days_min),
        lead_time_days_max=_to_int(lead_time_days_max),
        in_stock=in_stock,
        last_verified=datetime.now(),
    )
    db.add(source)
    db.flush()
    db.refresh(unit)
    unit.recompute_best_price()
    db.commit()
    db.refresh(unit)
    return _sources_partial(request, unit, db)


@router.post("/{unit_id}/sources/{source_id}/delete", response_class=HTMLResponse)
def delete_source(
    request: Request,
    unit_id: int,
    source_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = _get_unit_or_404(db, unit_id)
    source = db.get(EquipmentSource, source_id)
    if source and source.equipment_unit_id == unit.id:
        db.delete(source)
        db.flush()
        db.refresh(unit)
        unit.recompute_best_price()
        db.commit()
        db.refresh(unit)
    return _sources_partial(request, unit, db)


@router.post("/{unit_id}/sources/{source_id}/preferred", response_class=HTMLResponse)
def toggle_preferred_source(
    request: Request,
    unit_id: int,
    source_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = _get_unit_or_404(db, unit_id)
    source = db.get(EquipmentSource, source_id)
    if source and source.equipment_unit_id == unit.id:
        # Only one preferred source per unit.
        for s in unit.sources:
            s.is_preferred = s.id == source_id and not source.is_preferred
        db.commit()
        db.refresh(unit)
    return _sources_partial(request, unit, db)


# ── Archive / restore ─────────────────────────────────────────────────────────


@router.post("/{unit_id}/archive")
def archive_unit(unit_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    unit = _get_unit_or_404(db, unit_id)
    unit.status = "archived"
    db.commit()
    return RedirectResponse(url="/equipment/", status_code=303)


@router.post("/{unit_id}/unarchive")
def unarchive_unit(unit_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    unit = _get_unit_or_404(db, unit_id)
    unit.status = "active"
    db.commit()
    return RedirectResponse(url=f"/equipment/{unit_id}", status_code=303)


# ── Images ────────────────────────────────────────────────────────────────────


@router.post("/{unit_id}/update-image", response_class=HTMLResponse)
async def equipment_update_image(
    request: Request,
    unit_id: int,
    image_url: str = Form(""),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = db.get(EquipmentUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Equipment unit not found")

    new_url: str | None = None

    if image_file and image_file.filename:
        suffix = Path(image_file.filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            return templates.TemplateResponse(
                request,
                "equipment/_image_edit.html",
                {
                    "unit": unit,
                    "error": f"File type '{suffix}' not allowed. Use jpg, png, webp, or gif.",
                },  # noqa: E501
            )
        _EQUIPMENT_IMG_DIR.mkdir(parents=True, exist_ok=True)
        dest = _EQUIPMENT_IMG_DIR / f"{unit_id}{suffix}"
        with dest.open("wb") as f:
            shutil.copyfileobj(image_file.file, f)
        new_url = f"/static/images/equipment/{unit_id}{suffix}"
    elif image_url.strip():
        new_url = image_url.strip()

    if new_url is not None:
        unit.image_url = new_url
        db.commit()

    return templates.TemplateResponse(
        request,
        "equipment/_image_edit.html",
        {"unit": unit, "success": new_url is not None},
    )


@router.post("/{unit_id}/clear-image", response_class=HTMLResponse)
def equipment_clear_image(
    request: Request,
    unit_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = db.get(EquipmentUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Equipment unit not found")
    # Remove local file if it lives under our equipment image directory
    if unit.image_url and unit.image_url.startswith("/static/images/equipment/"):
        local_path = Path(__file__).parent.parent / unit.image_url.lstrip("/")
        local_path.unlink(missing_ok=True)
    unit.image_url = None
    db.commit()
    return templates.TemplateResponse(
        request,
        "equipment/_image_edit.html",
        {"unit": unit, "success": True},
    )


@router.get("/{unit_id}", response_class=HTMLResponse)
def equipment_detail(
    request: Request,
    unit_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    unit = db.get(EquipmentUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Equipment unit not found")
    distributors = db.query(Distributor).order_by(Distributor.name).all()
    return templates.TemplateResponse(
        request,
        "equipment/detail.html",
        {
            "active_nav": "equipment",
            "unit": unit,
            "distributors": distributors,
            "type_labels": _TYPES,
        },
    )
