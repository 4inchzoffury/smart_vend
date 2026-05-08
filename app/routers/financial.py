from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.financial import MachineProForma
from app.services.financial_calc import build_12month_table, calc_summary
from app.views import templates

router = APIRouter(prefix="/financial", tags=["financial"])


@router.get("/", response_class=HTMLResponse)
def financial_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    scenarios = db.query(MachineProForma).order_by(MachineProForma.updated_at.desc()).all()
    return templates.TemplateResponse(
        request, "financial/index.html", {"active_nav": "financial", "scenarios": scenarios}
    )


@router.get("/calculator", response_class=HTMLResponse)
def financial_calculator(
    request: Request,
    scenario_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    scenario = db.get(MachineProForma, scenario_id) if scenario_id else None
    return templates.TemplateResponse(
        request, "financial/calculator.html", {"active_nav": "financial", "scenario": scenario}
    )


@router.get("/calculate", response_class=HTMLResponse)
def financial_calculate(
    request: Request,
    machine_cost: float = 0,
    installation_cost: float = 0,
    initial_inventory_cost: float = 0,
    daily_transactions: float = 0,
    avg_ticket_usd: float = 0,
    cogs_pct: float = 0,
    commission_pct: float = 0,
    restock_labor_monthly: float = 0,
    supplies_monthly: float = 0,
    insurance_monthly: float = 0,
    other_opex_monthly: float = 0,
) -> HTMLResponse:
    # Normalise percent inputs: accept either 0–100 or 0–1
    cogs = cogs_pct / 100 if cogs_pct > 1 else cogs_pct
    comm = commission_pct / 100 if commission_pct > 1 else commission_pct
    table = build_12month_table(
        daily_transactions=daily_transactions,
        avg_ticket_usd=avg_ticket_usd,
        cogs_pct=cogs,
        commission_pct=comm,
        restock_labor_monthly=restock_labor_monthly,
        supplies_monthly=supplies_monthly,
        insurance_monthly=insurance_monthly,
        other_opex_monthly=other_opex_monthly,
    )
    summary = calc_summary(
        table=table,
        machine_cost=machine_cost,
        installation_cost=installation_cost,
        initial_inventory_cost=initial_inventory_cost,
    )
    return templates.TemplateResponse(
        request, "financial/_proforma_result.html", {"table": table, "summary": summary}
    )


@router.post("/calculator", response_class=HTMLResponse)
def financial_save(
    request: Request,
    name: str = Form(...),
    machine_cost: float = Form(...),
    installation_cost: float = Form(0),
    initial_inventory_cost: float = Form(0),
    daily_transactions: float = Form(...),
    avg_ticket_usd: float = Form(...),
    cogs_pct: float = Form(...),
    commission_pct: float = Form(0),
    restock_labor_monthly: float = Form(0),
    supplies_monthly: float = Form(0),
    insurance_monthly: float = Form(0),
    other_opex_monthly: float = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    scenario = MachineProForma(
        name=name,
        machine_cost=machine_cost,
        installation_cost=installation_cost,
        initial_inventory_cost=initial_inventory_cost,
        daily_transactions=daily_transactions,
        avg_ticket_usd=avg_ticket_usd,
        cogs_pct=cogs_pct / 100 if cogs_pct > 1 else cogs_pct,
        commission_pct=commission_pct / 100 if commission_pct > 1 else commission_pct,
        restock_labor_monthly=restock_labor_monthly,
        supplies_monthly=supplies_monthly,
        insurance_monthly=insurance_monthly,
        other_opex_monthly=other_opex_monthly,
        notes=notes or None,
    )
    db.add(scenario)
    db.commit()
    return RedirectResponse(url="/financial/", status_code=303)


@router.get("/{scenario_id}", response_class=HTMLResponse)
def financial_detail(
    scenario_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    scenario = db.get(MachineProForma, scenario_id)
    if not scenario:
        return Response(status_code=404)
    table = build_12month_table(
        daily_transactions=scenario.daily_transactions,
        avg_ticket_usd=scenario.avg_ticket_usd,
        cogs_pct=scenario.cogs_pct,
        commission_pct=scenario.commission_pct,
        restock_labor_monthly=scenario.restock_labor_monthly,
        supplies_monthly=scenario.supplies_monthly,
        insurance_monthly=scenario.insurance_monthly,
        other_opex_monthly=scenario.other_opex_monthly,
        seasonality_json=scenario.seasonality_json,
    )
    summary = calc_summary(
        table=table,
        machine_cost=scenario.machine_cost,
        installation_cost=scenario.installation_cost,
        initial_inventory_cost=scenario.initial_inventory_cost,
    )
    return templates.TemplateResponse(
        request,
        "financial/detail.html",
        {"active_nav": "financial", "scenario": scenario, "table": table, "summary": summary},
    )


@router.post("/{scenario_id}/copy", response_class=HTMLResponse)
def financial_copy(scenario_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    original = db.get(MachineProForma, scenario_id)
    if not original:
        return Response(status_code=404)
    copy = MachineProForma(
        name=f"{original.name} (copy)",
        machine_cost=original.machine_cost,
        installation_cost=original.installation_cost,
        initial_inventory_cost=original.initial_inventory_cost,
        daily_transactions=original.daily_transactions,
        avg_ticket_usd=original.avg_ticket_usd,
        cogs_pct=original.cogs_pct,
        commission_pct=original.commission_pct,
        restock_labor_monthly=original.restock_labor_monthly,
        supplies_monthly=original.supplies_monthly,
        insurance_monthly=original.insurance_monthly,
        other_opex_monthly=original.other_opex_monthly,
        seasonality_json=original.seasonality_json,
        notes=original.notes,
    )
    db.add(copy)
    db.commit()
    return RedirectResponse(url="/financial/", status_code=303)


@router.delete("/{scenario_id}", response_class=HTMLResponse)
def financial_delete(scenario_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    scenario = db.get(MachineProForma, scenario_id)
    if scenario:
        db.delete(scenario)
        db.commit()
    return RedirectResponse(url="/financial/", status_code=303)
