from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.financial import MachineProForma
from app.services.financial_calc import build_12month_table, calc_summary

# --- Pure calc unit tests ---

def test_build_12month_table_basic() -> None:
    rows = build_12month_table(
        daily_transactions=10,
        avg_ticket_usd=5.0,
        cogs_pct=0.40,
        commission_pct=0.10,
        restock_labor_monthly=100.0,
    )
    assert len(rows) == 12
    first = rows[0]
    expected_revenue = 10 * 5.0 * 30.4
    assert abs(first["revenue"] - expected_revenue) < 0.01
    assert abs(first["cogs_pct"] - 40.0) < 0.01
    assert first["cumulative"] == first["net"]


def test_build_12month_cumulative() -> None:
    rows = build_12month_table(daily_transactions=10, avg_ticket_usd=5.0, cogs_pct=0.5)
    for i, row in enumerate(rows[1:], start=1):
        assert abs(row["cumulative"] - sum(r["net"] for r in rows[: i + 1])) < 0.01


def test_calc_summary_payback() -> None:
    # Very profitable scenario — should pay back in month 1
    rows = build_12month_table(
        daily_transactions=100, avg_ticket_usd=10.0, cogs_pct=0.20
    )
    summary = calc_summary(rows, machine_cost=1000.0)
    assert summary["payback_months"] is not None
    assert summary["payback_months"] <= 12
    assert summary["total_investment"] == 1000.0
    assert summary["annual_net"] > 0


def test_calc_summary_no_payback() -> None:
    # Unprofitable scenario — net is negative
    rows = build_12month_table(
        daily_transactions=1,
        avg_ticket_usd=1.0,
        cogs_pct=0.99,
        restock_labor_monthly=500.0,
    )
    summary = calc_summary(rows, machine_cost=50_000.0)
    assert summary["payback_months"] is None


def test_calc_summary_gross_margin() -> None:
    rows = build_12month_table(daily_transactions=10, avg_ticket_usd=5.0, cogs_pct=0.30)
    summary = calc_summary(rows, machine_cost=0)
    assert abs(summary["gross_margin_pct"] - 70.0) < 0.01


# --- HTTP endpoint tests ---

def _make_scenario(db: Session, **kwargs) -> MachineProForma:
    defaults = {
        "name": "Test Scenario",
        "machine_cost": 5000.0,
        "daily_transactions": 20.0,
        "avg_ticket_usd": 4.0,
        "cogs_pct": 0.40,
    }
    defaults.update(kwargs)
    s = MachineProForma(**defaults)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_financial_index_empty(client: TestClient) -> None:
    resp = client.get("/financial/")
    assert resp.status_code == 200
    assert "Financial" in resp.text


def test_financial_calculator_get(client: TestClient) -> None:
    resp = client.get("/financial/calculator")
    assert resp.status_code == 200


def test_financial_calculate_htmx(client: TestClient) -> None:
    resp = client.get(
        "/financial/calculate",
        params={
            "machine_cost": 5000,
            "daily_transactions": 20,
            "avg_ticket_usd": 4,
            "cogs_pct": 40,
        },
    )
    assert resp.status_code == 200
    assert "revenue" in resp.text.lower() or "Revenue" in resp.text


def test_financial_save_and_list(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/financial/calculator",
        data={
            "name": "Gym Location",
            "machine_cost": "6000",
            "daily_transactions": "25",
            "avg_ticket_usd": "4.50",
            "cogs_pct": "38",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db.query(MachineProForma).count() == 1
    s = db.query(MachineProForma).first()
    assert s is not None
    assert s.name == "Gym Location"
    assert abs(s.cogs_pct - 0.38) < 0.001


def test_financial_detail(client: TestClient, db: Session) -> None:
    s = _make_scenario(db)
    resp = client.get(f"/financial/{s.id}")
    assert resp.status_code == 200
    assert "Test Scenario" in resp.text


def test_financial_copy(client: TestClient, db: Session) -> None:
    s = _make_scenario(db)
    resp = client.post(f"/financial/{s.id}/copy", follow_redirects=False)
    assert resp.status_code == 303
    assert db.query(MachineProForma).count() == 2
    copy = db.query(MachineProForma).filter(MachineProForma.id != s.id).first()
    assert copy is not None
    assert "copy" in copy.name


def test_financial_delete(client: TestClient, db: Session) -> None:
    s = _make_scenario(db)
    resp = client.delete(f"/financial/{s.id}", follow_redirects=False)
    assert resp.status_code == 303
    assert db.query(MachineProForma).count() == 0


def test_financial_404(client: TestClient) -> None:
    assert client.get("/financial/9999").status_code == 404
