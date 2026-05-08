from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentJob
from app.models.sales import OutreachLog, Prospect
from app.services import agent, email_sender
from app.views import templates

router = APIRouter(prefix="/leads", tags=["leads"])

VENUE_TYPE_OPTIONS = [
    "gym",
    "hotel",
    "corporate office",
    "condo / apartment complex",
    "hospital / medical",
    "university / college",
    "government / military",
    "retail / shopping",
]


@router.get("/", response_class=HTMLResponse)
def leads_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    jobs = (
        db.query(AgentJob)
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "leads/index.html",
        {
            "active_nav": "leads",
            "jobs": jobs,
            "venue_options": VENUE_TYPE_OPTIONS,
        },
    )


@router.post("/research", response_class=HTMLResponse)
def leads_research(
    request: Request,
    background_tasks: BackgroundTasks,
    venue_types: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = AgentJob(
        job_type="research",
        status="pending",
        input_params=json.dumps(venue_types),
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(agent.run_research_job, job.id)
    return RedirectResponse(url=f"/leads/jobs/{job.id}", status_code=303)


@router.get("/jobs/", response_class=HTMLResponse)
def leads_jobs_list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    jobs = (
        db.query(AgentJob)
        .order_by(AgentJob.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(request, "leads/_job_history.html", {"jobs": jobs})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def leads_job_status(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return Response(status_code=404)
    return templates.TemplateResponse(
        request,
        "leads/job_status.html",
        {"active_nav": "leads", "job": job},
    )


@router.get("/jobs/{job_id}/poll", response_class=HTMLResponse)
def leads_job_poll(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return HTMLResponse(content="<div>Job not found</div>", status_code=404)
    return templates.TemplateResponse(
        request,
        "leads/_job_status_card.html",
        {"job": job},
    )


@router.get("/jobs/{job_id}/draft", response_class=HTMLResponse)
def leads_draft_review(
    job_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return Response(status_code=404)
    prospect = db.get(Prospect, job.prospect_id) if job.prospect_id else None
    return templates.TemplateResponse(
        request,
        "leads/draft_review.html",
        {"active_nav": "leads", "job": job, "prospect": prospect},
    )


@router.post("/prospects/{prospect_id}/draft", response_class=HTMLResponse)
def leads_draft_email(
    prospect_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    prospect = db.get(Prospect, prospect_id)
    if not prospect:
        return Response(status_code=404)
    job = AgentJob(
        job_type="email_draft",
        status="pending",
        prospect_id=prospect_id,
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(agent.run_email_draft_job, job.id)
    return RedirectResponse(url=f"/leads/jobs/{job.id}", status_code=303)


@router.post("/jobs/{job_id}/send", response_class=HTMLResponse)
def leads_send_email(
    job_id: int,
    request: Request,
    to_email: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if not job:
        return Response(status_code=404)
    prospect = db.get(Prospect, job.prospect_id) if job.prospect_id else None
    try:
        email_sender.send_email(to_address=to_email, subject=subject, body=body)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "leads/draft_review.html",
            {
                "active_nav": "leads",
                "job": job,
                "prospect": prospect,
                "send_error": str(exc),
            },
            status_code=500,
        )

    if prospect:
        log = OutreachLog(
            prospect_id=prospect.id,
            channel="email",
            direction="outbound",
            contacted_at=datetime.now(),
            subject_or_summary=subject,
            outcome="sent",
        )
        db.add(log)
        db.commit()
        return RedirectResponse(url=f"/sales/{prospect.id}", status_code=303)

    return RedirectResponse(url="/leads/", status_code=303)


@router.delete("/jobs/{job_id}", response_class=HTMLResponse)
def leads_job_delete(job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(AgentJob, job_id)
    if job:
        db.delete(job)
        db.commit()
    return HTMLResponse(content="", status_code=200)
