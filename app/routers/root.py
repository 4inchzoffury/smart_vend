from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentJob
from app.models.email_approval import EmailApproval
from app.models.equipment import EquipmentUnit
from app.models.financial import MachineProForma
from app.models.inventory import Product
from app.models.location import Location
from app.models.research import ResearchTask
from app.models.sales import Prospect
from app.views import templates

router = APIRouter(tags=["root"])


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    research_counts = {
        s: db.query(ResearchTask).filter(ResearchTask.status == s).count()
        for s in ("not_started", "in_progress", "blocked", "done")
    }
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active_nav": "dashboard",
            "research_done": research_counts["done"],
            "research_in_progress": research_counts["in_progress"],
            "research_blocked": research_counts["blocked"],
            "research_not_started": research_counts["not_started"],
            "research_total": sum(research_counts.values()),
            "financial_count": db.query(MachineProForma).count(),
            "locations_active": db.query(Location).filter(Location.status == "active").count(),
            "locations_prospect": db.query(Location).filter(Location.status == "prospect").count(),
            "pipeline_leads": db.query(Prospect).filter(Prospect.pipeline_stage == "lead").count(),
            "pipeline_site_visits": db.query(Prospect)
            .filter(Prospect.pipeline_stage == "site_visit")
            .count(),
            "pipeline_signed": db.query(Prospect)
            .filter(Prospect.pipeline_stage == "signed")
            .count(),
            "inventory_skus": db.query(Product).filter(Product.is_active.is_(True)).count(),
            "inventory_low_stock": db.query(Product)
            .filter(
                Product.is_active.is_(True),
                Product.par_level.is_not(None),
                Product.on_hand_qty < Product.par_level,
            )
            .count(),
            "cs_pending_emails": db.query(EmailApproval)
            .filter(EmailApproval.status == "pending")
            .count(),
            "leads_research_runs": db.query(AgentJob)
            .filter(AgentJob.job_type == "research")
            .count(),
            "leads_prospects_created": db.query(func.sum(AgentJob.prospects_created))
            .filter(AgentJob.job_type == "research", AgentJob.status == "done")
            .scalar()
            or 0,
            "leads_drafts_ready": db.query(AgentJob)
            .filter(AgentJob.job_type == "email_draft", AgentJob.status == "done")
            .count(),
            "leads_running": db.query(AgentJob)
            .filter(AgentJob.status.in_(["pending", "running"]))
            .count(),
            "equipment_count": db.query(EquipmentUnit).count(),
        },
    )
