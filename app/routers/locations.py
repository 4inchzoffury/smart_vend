from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.location import Location, Machine
from app.views import templates

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/", response_class=HTMLResponse)
def locations_index(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = db.query(Location)
    if status:
        query = query.filter(Location.status == status)
    locations = query.order_by(Location.name).all()
    return templates.TemplateResponse(
        request,
        "locations/index.html",
        {"active_nav": "locations", "locations": locations, "status_filter": status},
    )


@router.get("/new", response_class=HTMLResponse)
def location_new_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "locations/_location_form.html", {"location": None}
    )


@router.post("/", response_class=HTMLResponse)
def location_create(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    city: str = Form("Panama City"),
    state: str = Form("FL"),
    zip_code: str = Form(""),
    venue_type: str = Form(""),
    foot_traffic_estimate: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    status: str = Form("prospect"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    location = Location(
        name=name,
        address=address or None,
        city=city,
        state=state,
        zip_code=zip_code or None,
        venue_type=venue_type or None,
        foot_traffic_estimate=foot_traffic_estimate or None,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        status=status,
        notes=notes or None,
    )
    db.add(location)
    db.commit()
    return RedirectResponse(url="/locations/", status_code=303)


@router.get("/{location_id}", response_class=HTMLResponse)
def location_detail(
    location_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    location = db.get(Location, location_id)
    if not location:
        return Response(status_code=404)
    machines = db.query(Machine).filter(Machine.location_id == location_id).all()
    return templates.TemplateResponse(
        request,
        "locations/detail.html",
        {"active_nav": "locations", "location": location, "machines": machines},
    )


@router.get("/{location_id}/edit", response_class=HTMLResponse)
def location_edit_form(
    location_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    location = db.get(Location, location_id)
    if not location:
        return Response(status_code=404)
    return templates.TemplateResponse(
        request, "locations/_location_form.html", {"location": location}
    )


@router.post("/{location_id}", response_class=HTMLResponse)
def location_update(
    location_id: int,
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    city: str = Form("Panama City"),
    state: str = Form("FL"),
    zip_code: str = Form(""),
    venue_type: str = Form(""),
    foot_traffic_estimate: str = Form(""),
    foot_traffic_notes: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    contract_status: str = Form("none"),
    status: str = Form("prospect"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    location = db.get(Location, location_id)
    if not location:
        return Response(status_code=404)
    location.name = name
    location.address = address or None
    location.city = city
    location.state = state
    location.zip_code = zip_code or None
    location.venue_type = venue_type or None
    location.foot_traffic_estimate = foot_traffic_estimate or None
    location.foot_traffic_notes = foot_traffic_notes or None
    location.contact_name = contact_name or None
    location.contact_email = contact_email or None
    location.contact_phone = contact_phone or None
    location.contract_status = contract_status
    location.status = status
    location.notes = notes or None
    db.commit()
    return RedirectResponse(url=f"/locations/{location_id}", status_code=303)


@router.delete("/{location_id}", response_class=HTMLResponse)
def location_delete(location_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    location = db.get(Location, location_id)
    if location:
        db.delete(location)
        db.commit()
    return RedirectResponse(url="/locations/", status_code=303)
