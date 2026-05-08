from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import sheets
from app.views import templates

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/", response_class=HTMLResponse)
def sync_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "sync/index.html", {"active_nav": "sync"})


@router.post("/research/push", response_class=JSONResponse)
def sync_research_push(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(sheets.push_research_tasks(db))


@router.post("/research/pull", response_class=JSONResponse)
def sync_research_pull(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(sheets.pull_research_tasks(db))


@router.post("/inventory/push", response_class=JSONResponse)
def sync_inventory_push(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(sheets.push_product_catalog(db))


@router.post("/inventory/pull", response_class=JSONResponse)
def sync_inventory_pull(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(sheets.pull_product_catalog(db))


@router.post("/sales/push", response_class=JSONResponse)
def sync_sales_push(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(sheets.push_sales_pipeline(db))


@router.post("/full", response_class=JSONResponse)
def sync_full(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse({
        "research": sheets.push_research_tasks(db),
        "inventory": sheets.push_product_catalog(db),
        "sales": sheets.push_sales_pipeline(db),
    })
