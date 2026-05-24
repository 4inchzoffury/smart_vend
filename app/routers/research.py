from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.research import ResearchSection, ResearchTask, TaskDependency
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


def _ensure_sections_seeded(db: Session) -> None:
    # Seed the default sections on first run. Idempotent and checked per call:
    # a module-level "already seeded" cache would leak across test databases and
    # would also suppress re-seeding after a restart if the table were emptied.
    # The COUNT is trivial against this tiny table.
    if db.query(ResearchSection).count() == 0:
        for num, name in _DEFAULT_SECTIONS.items():
            db.add(ResearchSection(id=num, name=name, sort_order=num * 10))
        db.commit()


def _load_sections(db: Session) -> list[ResearchSection]:
    _ensure_sections_seeded(db)
    return db.query(ResearchSection).order_by(ResearchSection.sort_order).all()


def _load_deps(db: Session, task_ids: list[int]) -> dict[int, list[ResearchTask]]:
    """Return {task_id: [prerequisite ResearchTask, ...]} for the given task IDs."""
    if not task_ids:
        return {}
    links = db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).all()
    if not links:
        return {}
    dep_ids = list({lnk.depends_on_task_id for lnk in links})
    dep_map = {t.id: t for t in db.query(ResearchTask).filter(ResearchTask.id.in_(dep_ids)).all()}
    result: dict[int, list[ResearchTask]] = {}
    for lnk in links:
        dep_task = dep_map.get(lnk.depends_on_task_id)
        if dep_task:
            result.setdefault(lnk.task_id, []).append(dep_task)
    return result


def _save_deps(db: Session, task_id: int, dep_ids: list[int]) -> None:
    """Replace all dependencies for task_id with the given dep_ids."""
    db.query(TaskDependency).filter(TaskDependency.task_id == task_id).delete()
    for dep_id in dep_ids:
        if dep_id != task_id:
            db.add(TaskDependency(task_id=task_id, depends_on_task_id=dep_id))


_PRIORITY_LEVELS = ["high", "medium", "low"]


def _status_counts(db: Session) -> dict[str, int]:
    return {
        s: db.query(ResearchTask).filter(ResearchTask.status == s).count() for s in _STATUS_CYCLE
    }


def _priority_counts(db: Session) -> dict[str, int]:
    return {
        p: db.query(ResearchTask).filter(ResearchTask.priority == p).count()
        for p in _PRIORITY_LEVELS
    }


def _board_context(
    db: Session,
    status: str | None,
    section: int | None,
    priority: str | None = None,
) -> dict:
    sections_db = _load_sections(db)
    section_names = {s.id: s.name for s in sections_db}
    section_order = [s.id for s in sections_db]

    query = db.query(ResearchTask)
    if status:
        query = query.filter(ResearchTask.status == status)
    if section:
        query = query.filter(ResearchTask.section == section)
    if priority:
        query = query.filter(ResearchTask.priority == priority)
    tasks = query.order_by(ResearchTask.section, ResearchTask.sort_order, ResearchTask.id).all()

    sections: dict[int, list[ResearchTask]] = {}
    for task in tasks:
        sections.setdefault(task.section, []).append(task)

    counts = _status_counts(db)
    p_counts = _priority_counts(db)
    visible_ids = [t.id for ts in sections.values() for t in ts]
    deps_by_task = _load_deps(db, visible_ids)
    return {
        "sections": sections,
        "section_names": section_names,
        "section_order": section_order,
        "sections_db": sections_db,
        "status_filter": status,
        "section_filter": section,
        "priority_filter": priority,
        "status_counts": counts,
        "priority_counts": p_counts,
        "total": db.query(ResearchTask).count(),
        "active_nav": "research",
        "deps_by_task": deps_by_task,
    }


@router.get("/", response_class=HTMLResponse)
def research_index(
    request: Request,
    status: str | None = None,
    section: int | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ctx = _board_context(db, status, section, priority)
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "research/_filters_board.html" if is_htmx else "research/index.html"
    return templates.TemplateResponse(request, template, ctx)


@router.get("/new", response_class=HTMLResponse)
def research_new_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    sections_db = _load_sections(db)
    section_names = {s.id: s.name for s in sections_db}
    all_tasks = db.query(ResearchTask).order_by(ResearchTask.section, ResearchTask.sort_order).all()
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {
            "task": None,
            "section_names": section_names,
            "all_tasks": all_tasks,
            "current_dep_ids": set(),
        },
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
    depends_on: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    section_obj = db.get(ResearchSection, section)
    section_name = section_obj.name if section_obj else f"Section {section}"
    existing = db.query(ResearchTask).filter(ResearchTask.section == section)
    existing_count = existing.count()
    max_order_row = existing.order_by(ResearchTask.sort_order.desc()).first()
    next_sort_order = (max_order_row.sort_order + 10) if max_order_row else 10
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
        sort_order=next_sort_order,
    )
    db.add(task)
    db.flush()
    _save_deps(db, task.id, depends_on)
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
    all_tasks = db.query(ResearchTask).order_by(ResearchTask.section, ResearchTask.sort_order).all()
    current_dep_ids = {
        lnk.depends_on_task_id
        for lnk in db.query(TaskDependency).filter(TaskDependency.task_id == task_id).all()
    }
    return templates.TemplateResponse(
        request,
        "research/_task_form.html",
        {
            "task": task,
            "section_names": section_names,
            "all_tasks": all_tasks,
            "current_dep_ids": current_dep_ids,
        },
    )


@router.post("/{task_id}", response_class=HTMLResponse)
def research_update(
    task_id: int,
    request: Request,
    what: str = Form(...),
    section: int = Form(...),
    why: str = Form(""),
    how_source: str = Form(""),
    owner: str = Form(""),
    due_date_raw: str = Form(""),
    priority: str = Form("medium"),
    status: str = Form("not_started"),
    notes: str = Form(""),
    depends_on: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if not task:
        return Response(status_code=404)
    if task.section != section:
        section_obj = db.get(ResearchSection, section)
        task.section = section
        task.section_name = section_obj.name if section_obj else f"Section {section}"
    task.what = what
    task.why = why or None
    task.how_source = how_source or None
    task.owner = owner or None
    task.due_date_raw = due_date_raw or None
    task.priority = priority
    task.status = status
    task.notes = notes or None
    _save_deps(db, task_id, depends_on)
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
    deps_by_task = _load_deps(db, [task.id])
    return templates.TemplateResponse(
        request, "research/_task_row.html", {"task": task, "deps_by_task": deps_by_task}
    )


@router.post("/{task_id}/duplicate", response_class=HTMLResponse)
def research_duplicate(
    task_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    source = db.get(ResearchTask, task_id)
    if not source:
        return Response(status_code=404)
    existing = db.query(ResearchTask).filter(ResearchTask.section == source.section)
    max_order_row = existing.order_by(ResearchTask.sort_order.desc()).first()
    next_sort_order = (max_order_row.sort_order + 10) if max_order_row else 10
    new_count = existing.count() + 1
    duplicate = ResearchTask(
        task_number=f"{source.section}.{new_count}",
        section=source.section,
        section_name=source.section_name,
        what=f"Duplicated from {source.what}",
        why=source.why,
        how_source=source.how_source,
        owner=source.owner,
        due_date_raw=source.due_date_raw,
        priority=source.priority,
        status="not_started",
        notes=source.notes,
        is_strategic_decision=source.is_strategic_decision,
        sort_order=next_sort_order,
    )
    db.add(duplicate)
    db.commit()
    ctx = _board_context(db, status=None, section=None)
    return templates.TemplateResponse(request, "research/_task_board.html", ctx)


@router.delete("/{task_id}", response_class=HTMLResponse)
def research_delete(task_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    task = db.get(ResearchTask, task_id)
    if task:
        db.delete(task)
        db.commit()
    return HTMLResponse(content="", status_code=200)


# ── Task reordering ───────────────────────────────────────────────────────────


class _ReorderBody(BaseModel):
    ids: list[int]


@router.post("/sections/{section_id}/reorder")
def research_section_reorder(
    section_id: int,
    body: _ReorderBody,
    db: Session = Depends(get_db),
) -> Response:
    for position, task_id in enumerate(body.ids):
        task = db.get(ResearchTask, task_id)
        if task and task.section == section_id:
            task.sort_order = position * 10
    db.commit()
    return Response(status_code=204)


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


@router.delete("/sections/{section_id}", response_class=HTMLResponse)
def research_section_delete(
    section_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    section = db.get(ResearchSection, section_id)
    if not section:
        return Response(status_code=404)
    task_count = db.query(ResearchTask).filter(ResearchTask.section == section_id).count()
    if task_count:
        return HTMLResponse(
            content=(
                f'<div class="alert alert-warning alert-dismissible m-2 py-2" role="alert">'
                f"Move or delete the {task_count} task(s) in this section first."
                f'<button type="button" class="btn-close" data-bs-dismiss="alert">'
                f"</button></div>"
            ),
            status_code=409,
        )
    db.delete(section)
    db.commit()
    ctx = _board_context(db, status=None, section=None)
    return templates.TemplateResponse(request, "research/_task_board.html", ctx)


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
