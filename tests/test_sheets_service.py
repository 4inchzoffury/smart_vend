"""Tests for Google Sheets sync service — all gspread calls are mocked."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models.inventory import Product
from app.models.research import ResearchTask
from app.models.sales import Prospect
from app.services import sheets


def _make_task(db: Session) -> ResearchTask:
    t = ResearchTask(
        task_number="1.1",
        section=1,
        section_name="Market Validation",
        what="Build prospect list",
        status="not_started",
        priority="medium",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_product(db: Session) -> Product:
    p = Product(
        sku="WATER-16OZ", name="Water 16oz", unit_cost=0.50, sell_price=1.50, on_hand_qty=10
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_prospect(db: Session) -> Prospect:
    p = Prospect(company_name="Bay Fitness", city="Panama City", pipeline_stage="lead")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _mock_worksheet() -> MagicMock:
    ws = MagicMock()
    ws.get_all_records.return_value = []
    return ws


def test_push_research_tasks_skipped_when_not_configured(db: Session) -> None:
    # When Sheets isn't configured, push should skip. Force the unconfigured
    # state explicitly so the test doesn't depend on ambient .env values
    # (a local .env may set SPREADSHEET_ID, which would otherwise attempt a real call).
    with patch.object(sheets, "_not_configured", return_value=True):
        result = sheets.push_research_tasks(db)
    assert result["status"] == "skipped"


def test_push_research_tasks_success(db: Session) -> None:
    _make_task(db)
    mock_ws = _mock_worksheet()
    with (
        patch.object(sheets, "_not_configured", return_value=False),
        patch.object(sheets, "_get_sheet", return_value=mock_ws),
    ):
        result = sheets.push_research_tasks(db)
    assert result["status"] == "ok"
    assert result["rows_pushed"] == 1
    mock_ws.clear.assert_called_once()
    mock_ws.update.assert_called_once()


def test_pull_research_tasks_creates_new(db: Session) -> None:
    mock_ws = _mock_worksheet()
    mock_ws.get_all_records.return_value = [
        {
            "task_number": "2.1",
            "section": 2,
            "section_name": "Finance",
            "what": "Get quotes",
            "why": "",
            "how_source": "",
            "owner": "",
            "due_date_raw": "",
            "status": "not_started",
            "priority": "medium",
            "notes": "",
            "is_strategic_decision": False,
        }
    ]
    with (
        patch.object(sheets, "_not_configured", return_value=False),
        patch.object(sheets, "_get_sheet", return_value=mock_ws),
    ):
        result = sheets.pull_research_tasks(db)
    assert result["status"] == "ok"
    # pull only updates existing tasks; new task_numbers are counted but not inserted
    assert result["created"] == 1


def test_pull_research_tasks_updates_existing(db: Session) -> None:
    task = _make_task(db)
    mock_ws = _mock_worksheet()
    mock_ws.get_all_records.return_value = [
        {
            "task_number": task.task_number,
            "section": task.section,
            "section_name": task.section_name,
            "what": "Updated what",
            "why": "",
            "how_source": "",
            "owner": "",
            "due_date_raw": "",
            "status": "done",
            "priority": "high",
            "notes": "",
            "is_strategic_decision": False,
        }
    ]
    with (
        patch.object(sheets, "_not_configured", return_value=False),
        patch.object(sheets, "_get_sheet", return_value=mock_ws),
    ):
        result = sheets.pull_research_tasks(db)
    db.refresh(task)
    assert result["status"] == "ok"
    assert result["updated"] == 1
    assert task.status == "done"
    assert task.priority == "high"


def test_push_product_catalog_success(db: Session) -> None:
    _make_product(db)
    mock_ws = _mock_worksheet()
    with (
        patch.object(sheets, "_not_configured", return_value=False),
        patch.object(sheets, "_get_sheet", return_value=mock_ws),
    ):
        result = sheets.push_product_catalog(db)
    assert result["status"] == "ok"
    assert result["rows_pushed"] == 1


def test_push_sales_pipeline_success(db: Session) -> None:
    _make_prospect(db)
    mock_ws = _mock_worksheet()
    with (
        patch.object(sheets, "_not_configured", return_value=False),
        patch.object(sheets, "_get_sheet", return_value=mock_ws),
    ):
        result = sheets.push_sales_pipeline(db)
    assert result["status"] == "ok"
    assert result["rows_pushed"] == 1
