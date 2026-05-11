from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.views import templates

router = APIRouter(tags=["public"])


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/landing.html", {})


@router.post("/contact", response_class=HTMLResponse)
async def contact(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    company: str = Form(...),
    venue_type: str = Form(...),
    daily_traffic: str = Form(""),
    message: str = Form(""),
) -> HTMLResponse:
    # Best-effort email notification (non-blocking if not configured)
    try:
        from app.config import settings
        from app.services.email_sender import send_email

        if settings.gmail_user and settings.gmail_app_password:
            body = (
                f"New location assessment request from {first_name} {last_name}\n\n"
                f"Email: {email}\n"
                f"Phone: {phone}\n"
                f"Company: {company}\n"
                f"Venue Type: {venue_type}\n"
                f"Daily Traffic: {daily_traffic}\n\n"
                f"Message:\n{message}"
            )
            send_email(
                to_address=settings.gmail_user,
                subject=f"New Assessment Request – {company}",
                body=body,
            )
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "public/landing.html",
        {"contact_success": True},
    )
