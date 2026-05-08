from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.research import ResearchTask
from app.views import templates

router = APIRouter(prefix="/research", tags=["research"])

_STATUS_CYCLE = ["not_started", "in_progress", "blocked", "done"]

SECTION_NAMES: dict[int, str] = {
    1: "Market Validation",
    2: "Equipment Vendor Due Diligence",
    3: "Legal, Regulatory, Compliance",
    4: "Financial Modeling & Capital Strategy",
    5: "Sales Pipeline & First Contracts",
    6: "Technology & Web",
    7: "Operational Setup",
    8: "Strategic Decisions Pending",
    9: "Industry Knowledge to Build",
}


def _status_counts(db: Session) -> dict[str, int]:
    return {
        s: db.query(ResearchTask).filter(ResearchTask.status == s).count()
        for s in _STATUS_CYCLE
    }


def _board_context(
    db: Session,
    status: str | None,
    section: int | None,
) -> dict:
    query = db.query(ResearchTask)
    if status:
        query = query.filter(ResearchTask.status == status)
    if section:
        query = query.filter(ResearchTask.section == section)
    tasks = query.order_by(ResearchTask.section, ResearchTask.task_number).all()

    sections: dict[int, list[ResearchTask]] = {}
    for task in tasks:
        sections.setdefault(task.section, []).append(task)

    counts = _status_counts(db)
    return {
        "sections": sections,
        "section_names": SECTION_NAMES,
        "status_filter": status,
        "section_filter": section,
        "status_counts": counts,
        "total": db.query(ResearchTask).count(),
        "active_nav": "research",
    }


@router.get("/", response_class=HTMLResponse)
def research_index(
    request: Request,
    status: str | None = None,
    section: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ctx = _board_context(db, status, section)
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "research/_task_board.html" if is_htmx else "research/index.html"
    return templates.TemplateResponse(request, template, ctx)


@router.get("/new", response_class=HTMLResponse)
def research_new_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {"task": None, "section_names": SECTION_NAMES},
    )


@router.post("/", response_class=HTMLResponse)
def research_create(
    request: Request,
    what: str = Form(...),
    section: int = Form(...),
    why: str = Form(""),
    how_source: str = Form(""),
    owner: str = Form(""),
    due_date_raw: str = Form(""),
    priority: str = Form("medium"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    existing_count = db.query(ResearchTask).filter(ResearchTask.section == section).count()
    task = ResearchTask(
        task_number=f"{section}.{existing_count + 1}",
        section=section,
        section_name=SECTION_NAMES.get(section, f"Section {section}"),
        what=what,
        why=why or None,
        how_source=how_source or None,
        owner=owner or None,
        due_date_raw=due_date_raw or None,
        priority=priority,
        notes=notes or None,
    )
    db.add(task)
    db.commit()

    if request.headers.get("HX-Request") == "true":
        ctx = _board_context(db, status=None, section=None)
        return templates.TemplateResponse(request, "research/_task_board.html", ctx)
    return RedirectResponse(url="/research/", status_code=303)


@router.get("/{task_id}/edit", response_class=HTMLResponse)
def research_edit_form(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if not task:
        return Response(status_code=404)
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {"task": task, "section_names": SECTION_NAMES},
    )


@router.post("/{task_id}", response_class=HTMLResponse)
def research_update(
    task_id: int,
    request: Request,
    what: str = Form(...),
    why: str = Form(""),
    how_source: str = Form(""),
    owner: str = Form(""),
    due_date_raw: str = Form(""),
    priority: str = Form("medium"),
    status: str = Form("not_started"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if not task:
        return Response(status_code=404)
    task.what = what
    task.why = why or None
    task.how_source = how_source or None
    task.owner = owner or None
    task.due_date_raw = due_date_raw or None
    task.priority = priority
    task.status = status
    task.notes = notes or None
    db.commit()
    db.refresh(task)

    if request.headers.get("HX-Request") == "true":
        ctx = _board_context(db, status=None, section=None)
        return templates.TemplateResponse(request, "research/_task_board.html", ctx)
    return RedirectResponse(url="/research/", status_code=303)


@router.post("/{task_id}/status", response_class=HTMLResponse)
def research_toggle_status(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if not task:
        return Response(status_code=404)
    idx = _STATUS_CYCLE.index(task.status) if task.status in _STATUS_CYCLE else 0
    task.status = _STATUS_CYCLE[(idx + 1) % len(_STATUS_CYCLE)]
    db.commit()
    db.refresh(task)
    return templates.TemplateResponse(
        request, "research/_task_row.html", {"task": task}
    )


@router.delete("/{task_id}", response_class=HTMLResponse)
def research_delete(task_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if task:
        db.delete(task)
        db.commit()
    return HTMLResponse(content="", status_code=200)
