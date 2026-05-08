from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sales import OutreachLog, Prospect
from app.views import templates

router = APIRouter(prefix="/sales", tags=["sales"])

PIPELINE_STAGES = ["lead", "contacted", "site_visit", "proposal", "signed", "lost"]


@router.get("/", response_class=HTMLResponse)
def sales_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    prospects_by_stage: dict[str, list[Prospect]] = {s: [] for s in PIPELINE_STAGES}
    for prospect in db.query(Prospect).order_by(Prospect.next_action_date).all():
        stage = prospect.pipeline_stage if prospect.pipeline_stage in prospects_by_stage else "lead"
        prospects_by_stage[stage].append(prospect)
    return templates.TemplateResponse(
        request,
        "sales/index.html",
        {
            "active_nav": "sales",
            "prospects_by_stage": prospects_by_stage,
            "stages": PIPELINE_STAGES,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def prospect_new_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "sales/_prospect_form.html", {"prospect": None}
    )


@router.post("/", response_class=HTMLResponse)
def prospect_create(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(""),
    contact_title: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    venue_type: str = Form(""),
    address: str = Form(""),
    city: str = Form("Panama City"),
    tier: str = Form(""),
    source: str = Form(""),
    next_action: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    prospect = Prospect(
        company_name=company_name,
        contact_name=contact_name or None,
        contact_title=contact_title or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        venue_type=venue_type or None,
        address=address or None,
        city=city,
        tier=tier or None,
        source=source or None,
        next_action=next_action or None,
        notes=notes or None,
    )
    db.add(prospect)
    db.commit()
    return RedirectResponse(url="/sales/", status_code=303)


@router.get("/{prospect_id}", response_class=HTMLResponse)
def prospect_detail(
    prospect_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    prospect = db.get(Prospect, prospect_id)
    if not prospect:
        return Response(status_code=404)
    return templates.TemplateResponse(
        request,
        "sales/detail.html",
        {"active_nav": "sales", "prospect": prospect, "stages": PIPELINE_STAGES},
    )


@router.post("/{prospect_id}/stage", response_class=HTMLResponse)
def prospect_advance_stage(
    prospect_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    prospect = db.get(Prospect, prospect_id)
    if not prospect:
        return Response(status_code=404)
    idx = (
        PIPELINE_STAGES.index(prospect.pipeline_stage)
        if prospect.pipeline_stage in PIPELINE_STAGES
        else 0
    )
    if idx < len(PIPELINE_STAGES) - 1:
        prospect.pipeline_stage = PIPELINE_STAGES[idx + 1]
        db.commit()
    return RedirectResponse(url="/sales/", status_code=303)


@router.post("/{prospect_id}/log", response_class=HTMLResponse)
def prospect_log_outreach(
    prospect_id: int,
    request: Request,
    channel: str = Form(...),
    subject_or_summary: str = Form(""),
    outcome: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    log = OutreachLog(
        prospect_id=prospect_id,
        channel=channel,
        contacted_at=datetime.now(),
        subject_or_summary=subject_or_summary or None,
        outcome=outcome or None,
        notes=notes or None,
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url=f"/sales/{prospect_id}", status_code=303)


@router.delete("/{prospect_id}", response_class=HTMLResponse)
def prospect_delete(prospect_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    prospect = db.get(Prospect, prospect_id)
    if prospect:
        db.delete(prospect)
        db.commit()
    return HTMLResponse(content="", status_code=200)
