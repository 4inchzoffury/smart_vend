import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentJob
from app.models.equipment import EquipmentUnit
from app.views import templates

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
    "HAHA Vending", "Cantaloupe", "365 Retail Markets", "Micromart", "SandStar", "WEIMI",
    "Avanti Markets", "Crane Merchandising Systems", "AMS", "Jofemar",
]
_TYPES = {
    "smart_cooler": "Smart Cooler",
    "freezer": "Freezer",
    "ambient": "Ambient/Snack",
    "kiosk": "Micro Market Kiosk",
    "micro_market": "Micro Market",
}


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
    manufacturer: str | None = None,
    equipment_type: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = db.query(EquipmentUnit)
    if manufacturer:
        query = query.filter(EquipmentUnit.manufacturer == manufacturer)
    if equipment_type:
        query = query.filter(EquipmentUnit.equipment_type == equipment_type)
    units = query.order_by(EquipmentUnit.manufacturer, EquipmentUnit.product_name).all()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            request,
            "equipment/_unit_grid.html",
            {"units": units, "type_labels": _TYPES},
        )

    # Only show filter buttons for types/manufacturers that have units in the DB
    existing_types = {
        row[0] for row in db.query(EquipmentUnit.equipment_type).distinct().all()
    }
    existing_manufacturers_set = {
        row[0] for row in db.query(EquipmentUnit.manufacturer).distinct().all()
    }
    available_type_labels = {k: v for k, v in _TYPES.items() if k in existing_types}
    # Preserve preferred ordering from _MANUFACTURERS, then append any unlisted ones alphabetically
    available_manufacturers = [m for m in _MANUFACTURERS if m in existing_manufacturers_set]
    available_manufacturers += sorted(
        m for m in existing_manufacturers_set if m not in set(_MANUFACTURERS)
    )

    active_job = _active_refresh_job(db)
    return templates.TemplateResponse(
        request,
        "equipment/index.html",
        {
            "active_nav": "equipment",
            "units": units,
            "manufacturers": available_manufacturers,
            "type_labels": available_type_labels,
            "selected_manufacturer": manufacturer or "",
            "selected_type": equipment_type or "",
            "active_refresh_job": active_job,
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


@router.get("/refresh", response_class=HTMLResponse)
def refresh_landing(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Confirmation / status page — does NOT start a job on load."""
    active_job = _active_refresh_job(db)
    all_jobs = (
        db.query(AgentJob)
        .filter(AgentJob.job_type == "equipment_refresh")
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    last_job = all_jobs[0] if all_jobs else None
    unit_count = db.query(EquipmentUnit).count()
    current_provider = _get_setting(db, "search_provider", "duckduckgo")
    return templates.TemplateResponse(
        request,
        "equipment/refresh.html",
        {
            "active_nav": "equipment",
            "active_job": active_job,
            "last_job": last_job,
            "all_jobs": all_jobs,
            "unit_count": unit_count,
            "current_provider": current_provider,
        },
    )


@router.post("/refresh", response_class=HTMLResponse)
def equipment_refresh_start(
    request: Request,
    background_tasks: BackgroundTasks,
    search_provider: str = Form("duckduckgo"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Actually start the refresh job — only called when user clicks 'Start Refresh'."""
    from app.services.equipment_agent import run_equipment_refresh_job

    # Don't double-start if one is already running
    existing = _active_refresh_job(db)
    if existing:
        return RedirectResponse(url="/equipment/refresh", status_code=303)

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
    return RedirectResponse(url="/equipment/refresh", status_code=303)


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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Equipment unit not found")

    new_url: str | None = None

    if image_file and image_file.filename:
        suffix = Path(image_file.filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            return templates.TemplateResponse(
                request,
                "equipment/_image_edit.html",
                {"unit": unit, "error": f"File type '{suffix}' not allowed. Use jpg, png, webp, or gif."},
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
        from fastapi import HTTPException
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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Equipment unit not found")
    return templates.TemplateResponse(
        request,
        "equipment/detail.html",
        {
            "active_nav": "equipment",
            "unit": unit,
            "type_labels": _TYPES,
        },
    )
