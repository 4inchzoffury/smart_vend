from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.research import ResearchSection, ResearchTask
from app.views import templates

router = APIRouter(prefix="/research", tags=["research"])

_STATUS_CYCLE = ["not_started", "in_progress", "blocked", "done"]

# Default sections — used to seed the DB on first run
_DEFAULT_SECTIONS: dict[int, str] = {
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

_sections_seeded = False


def _ensure_sections_seeded(db: Session) -> None:
    global _sections_seeded
    if _sections_seeded:
        return
    if db.query(ResearchSection).count() == 0:
        for num, name in _DEFAULT_SECTIONS.items():
            db.add(ResearchSection(id=num, name=name, sort_order=num * 10))
        db.commit()
    _sections_seeded = True


def _load_sections(db: Session) -> list[ResearchSection]:
    _ensure_sections_seeded(db)
    return db.query(ResearchSection).order_by(ResearchSection.sort_order).all()


def _status_counts(db: Session) -> dict[str, int]:
    return {
        s: db.query(ResearchTask).filter(ResearchTask.status == s).count()
        for s in _STATUS_CYCLE
    }


def _board_context(db: Session, status: str | None, section: int | None) -> dict:
    sections_db = _load_sections(db)
    section_names = {s.id: s.name for s in sections_db}
    section_order = [s.id for s in sections_db]

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
        "section_names": section_names,
        "section_order": section_order,
        "sections_db": sections_db,
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
def research_new_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    sections_db = _load_sections(db)
    section_names = {s.id: s.name for s in sections_db}
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {"task": None, "section_names": section_names},
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
    section_obj = db.get(ResearchSection, section)
    section_name = section_obj.name if section_obj else f"Section {section}"
    existing_count = db.query(ResearchTask).filter(ResearchTask.section == section).count()
    task = ResearchTask(
        task_number=f"{section}.{existing_count + 1}",
        section=section,
        section_name=section_name,
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
    sections_db = _load_sections(db)
    section_names = {s.id: s.name for s in sections_db}
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {"task": task, "section_names": section_names},
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


# ── Section management ────────────────────────────────────────────────────────

@router.post("/sections/new", response_class=HTMLResponse)
def research_section_create(
    request: Request,
    section_name: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _ensure_sections_seeded(db)
    max_order = db.query(ResearchSection).order_by(ResearchSection.sort_order.desc()).first()
    new_order = (max_order.sort_order + 10) if max_order else 10
    db.add(ResearchSection(name=section_name.strip(), sort_order=new_order))
    db.commit()
    return RedirectResponse(url="/research/", status_code=303)


@router.post("/sections/{section_id}/move", response_class=HTMLResponse)
def research_section_move(
    section_id: int,
    request: Request,
    dir: str = Query(..., pattern="^(up|down)$"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    sections = db.query(ResearchSection).order_by(ResearchSection.sort_order).all()
    ids = [s.id for s in sections]
    if section_id not in ids:
        return Response(status_code=404)

    idx = ids.index(section_id)
    if dir == "up" and idx > 0:
        a, b = sections[idx - 1], sections[idx]
        a.sort_order, b.sort_order = b.sort_order, a.sort_order
        db.commit()
    elif dir == "down" and idx < len(sections) - 1:
        a, b = sections[idx], sections[idx + 1]
        a.sort_order, b.sort_order = b.sort_order, a.sort_order
        db.commit()

    ctx = _board_context(db, status=None, section=None)
    return templates.TemplateResponse(request, "research/_task_board.html", ctx)
