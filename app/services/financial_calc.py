"""Pure functions for pro-forma P&L calculations — no DB access."""

from __future__ import annotations

import json
from typing import Any

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def build_12month_table(
    daily_transactions: float,
    avg_ticket_usd: float,
    cogs_pct: float,
    commission_pct: float = 0.0,
    restock_labor_monthly: float = 0.0,
    supplies_monthly: float = 0.0,
    insurance_monthly: float = 0.0,
    other_opex_monthly: float = 0.0,
    connectivity_monthly: float = 0.0,
    software_monthly: float = 0.0,
    seasonality_json: str | None = None,
) -> list[dict[str, Any]]:
    multipliers: list[float] = json.loads(seasonality_json) if seasonality_json else [1.0] * 12

    base_monthly_revenue = daily_transactions * avg_ticket_usd * 30.4
    fixed_opex = (
        restock_labor_monthly + supplies_monthly + insurance_monthly
        + other_opex_monthly + connectivity_monthly + software_monthly
    )

    rows = []
    cumulative = 0.0
    for i, mult in enumerate(multipliers):
        revenue = base_monthly_revenue * mult
        cogs = revenue * cogs_pct
        gross_profit = revenue - cogs
        commission = revenue * commission_pct
        total_opex = fixed_opex + commission
        net = gross_profit - total_opex
        cumulative += net
        rows.append({
            "month": MONTHS[i],
            "multiplier": mult,
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "cogs_pct": cogs_pct * 100,
            "total_opex": total_opex,
            "net": net,
            "cumulative": cumulative,
        })
    return rows


def calc_summary(
    table: list[dict[str, Any]],
    machine_cost: float,
    installation_cost: float = 0.0,
    initial_inventory_cost: float = 0.0,
) -> dict[str, Any]:
    total_investment = machine_cost + installation_cost + initial_inventory_cost
    annual_net = sum(r["net"] for r in table)
    avg_monthly_net = annual_net / 12 if table else 0.0

    # Payback: month when cumulative cash flow covers total investment
    payback_months: int | None = None
    running = -total_investment
    for i, row in enumerate(table):
        running += row["net"]
        if running >= 0 and payback_months is None:
            payback_months = i + 1

    steady_state_net = table[-1]["net"] if table else 0.0
    gross_margin_pct = (
        table[0]["gross_profit"] / table[0]["revenue"] * 100
        if table and table[0]["revenue"]
        else 0.0
    )

    return {
        "total_investment": total_investment,
        "annual_net": annual_net,
        "avg_monthly_net": avg_monthly_net,
        "steady_state_net": steady_state_net,
        "payback_months": payback_months,
        "gross_margin_pct": gross_margin_pct,
        "roi_pct": (annual_net / total_investment * 100) if total_investment else 0.0,
    }
