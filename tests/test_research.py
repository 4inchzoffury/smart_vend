from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.research import ResearchTask


def _make_task(db: Session, **kwargs) -> ResearchTask:
    defaults = {
        "task_number": "1.1",
        "section": 1,
        "section_name": "Market Validation",
        "what": "Build prospect list",
        "status": "not_started",
        "priority": "medium",
    }
    defaults.update(kwargs)
    task = ResearchTask(**defaults)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_research_index_empty(client: TestClient) -> None:
    resp = client.get("/research/")
    assert resp.status_code == 200
    assert "Research Tasks" in resp.text


def test_research_create(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/research/",
        data={
            "what": "Test task",
            "section": "1",
            "priority": "high",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db.query(ResearchTask).count() == 1
    task = db.query(ResearchTask).first()
    assert task is not None
    assert task.what == "Test task"
    assert task.priority == "high"
    assert task.section == 1


def test_research_index_shows_tasks(client: TestClient, db: Session) -> None:
    _make_task(db)
    resp = client.get("/research/")
    assert resp.status_code == 200
    assert "Build prospect list" in resp.text


def test_research_status_filter(client: TestClient, db: Session) -> None:
    _make_task(db, task_number="1.1", status="done")
    _make_task(db, task_number="1.2", what="Other task", status="not_started")
    resp = client.get("/research/?status=done", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "Build prospect list" in resp.text
    assert "Other task" not in resp.text


def test_research_toggle_status(client: TestClient, db: Session) -> None:
    task = _make_task(db, status="not_started")
    resp = client.post(f"/research/{task.id}/status")
    assert resp.status_code == 200
    db.refresh(task)
    assert task.status == "in_progress"


def test_research_toggle_status_cycles(client: TestClient, db: Session) -> None:
    task = _make_task(db, status="done")
    client.post(f"/research/{task.id}/status")
    db.refresh(task)
    assert task.status == "not_started"


def test_research_edit_form(client: TestClient, db: Session) -> None:
    task = _make_task(db)
    resp = client.get(f"/research/{task.id}/edit")
    assert resp.status_code == 200
    assert "Build prospect list" in resp.text


def test_research_update(client: TestClient, db: Session) -> None:
    task = _make_task(db)
    resp = client.post(
        f"/research/{task.id}",
        data={"what": "Updated task", "section": "1", "priority": "low", "status": "in_progress"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.refresh(task)
    assert task.what == "Updated task"
    assert task.status == "in_progress"


def test_research_delete(client: TestClient, db: Session) -> None:
    task = _make_task(db)
    resp = client.delete(f"/research/{task.id}")
    assert resp.status_code == 200
    assert db.query(ResearchTask).count() == 0


def test_research_404_on_missing(client: TestClient) -> None:
    resp = client.get("/research/9999/edit")
    assert resp.status_code == 404
