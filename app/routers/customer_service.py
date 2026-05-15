"""Customer Service Manager — employee portal."""

from __future__ import annotations

import json
import secrets
from collections import defaultdict
from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat import ChatMessage
from app.models.cs_governance import CSGovernanceRule
from app.models.email_approval import EmailApproval
from app.models.settings import AppSetting
from app.services import cs_manager_agent
from app.services.auth import require_user
from app.views import templates

router = APIRouter(prefix="/customer-service", tags=["customer_service"])

# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row else default


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def _gmail_connected(db: Session) -> bool:
    row = db.get(AppSetting, "gmail_refresh_token")
    return bool(row and row.value)


def _pending_emails_count(db: Session) -> int:
    return db.query(EmailApproval).filter(EmailApproval.status == "pending").count()


def _pending_escalations_count(db: Session) -> int:
    row = db.get(AppSetting, "chatbot_escalation_pending")
    if not row or not row.value:
        return 0
    try:
        return len(json.loads(row.value))
    except Exception:
        return 0


def _get_escalations(db: Session) -> list:
    row = db.get(AppSetting, "chatbot_escalation_pending")
    if not row or not row.value:
        return []
    try:
        return json.loads(row.value)
    except Exception:
        return []


_QUICK_PROMPTS = [
    "What are customers asking most often?",
    "Suggest a new governance rule based on recent chats",
    "Review the current governance rules and flag any gaps",
    "How should I respond to an unhappy customer?",
    "Draft a reply to a customer asking about pricing",
]

_PROVIDERS = [
    ("anthropic", "Anthropic Claude (Paid)"),
    ("groq", "Groq / Llama (Free)"),
    ("openai", "OpenAI (Paid)"),
    ("gemini", "Google Gemini (Free tier)"),
    ("ollama", "Ollama (Local / Free)"),
]


def _ollama_running() -> bool:
    """Return True if Ollama's HTTP server responds on its configured base URL."""
    import urllib.request

    from app.config import settings as app_settings

    base = app_settings.ollama_base_url.replace("/v1", "").rstrip("/")
    try:
        urllib.request.urlopen(base, timeout=1)  # noqa: S310
        return True
    except Exception:
        return False


# ── Main page ─────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def cs_index(
    request: Request,
    flash_type: str = "",
    flash_msg: str = "",
    user: dict = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Load manager chat history for the active tab
    session_id = f"manager:{user.get('email', 'employee')}"
    manager_msgs = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role.in_(["user", "assistant"]),
        )
        .order_by(ChatMessage.created_at)
        .limit(50)
        .all()
    )
    flash = {"type": flash_type, "message": flash_msg} if flash_msg else None
    chat_history = _build_chat_history_context(db)

    return templates.TemplateResponse(
        request,
        "customer_service/index.html",
        {
            "active_nav": "customer_service",
            "user": user,
            "gmail_connected": _gmail_connected(db),
            "pending_emails": _pending_emails_count(db),
            "pending_escalations": _pending_escalations_count(db),
            "manager_msgs": manager_msgs,
            "quick_prompts": _QUICK_PROMPTS,
            "flash": flash,
            **chat_history,
        },
    )


# ── Governance Rules ──────────────────────────────────────────────────────────


@router.get("/governance", response_class=HTMLResponse)
def cs_governance(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "customer_service/_governance_rules.html",
        {"rules": rules},
    )


@router.post("/governance", response_class=HTMLResponse)
def cs_governance_create(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    rule_text: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Determine next display_order
    max_order = db.query(sql_func.max(CSGovernanceRule.display_order)).scalar() or 0
    rule = CSGovernanceRule(
        category=category,
        title=title.strip(),
        rule_text=rule_text.strip(),
        display_order=max_order + 1,
    )
    db.add(rule)
    db.commit()
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    return templates.TemplateResponse(
        request, "customer_service/_governance_list.html", {"rules": rules}
    )


@router.put("/governance/{rule_id}", response_class=HTMLResponse)
def cs_governance_update(
    rule_id: int,
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    rule_text: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rule = db.get(CSGovernanceRule, rule_id)
    if not rule:
        return Response(status_code=404)
    rule.category = category
    rule.title = title.strip()
    rule.rule_text = rule_text.strip()
    rule.updated_at = datetime.now()
    db.commit()
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    return templates.TemplateResponse(
        request, "customer_service/_governance_list.html", {"rules": rules}
    )


@router.delete("/governance/{rule_id}", response_class=HTMLResponse)
def cs_governance_delete(
    rule_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    rule = db.get(CSGovernanceRule, rule_id)
    if rule:
        db.delete(rule)
        db.commit()
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    return templates.TemplateResponse(
        request, "customer_service/_governance_list.html", {"rules": rules}
    )


@router.patch("/governance/{rule_id}/toggle", response_class=HTMLResponse)
def cs_governance_toggle(
    rule_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    rule = db.get(CSGovernanceRule, rule_id)
    if not rule:
        return Response(status_code=404)
    rule.is_active = not rule.is_active
    rule.updated_at = datetime.now()
    db.commit()
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    return templates.TemplateResponse(
        request, "customer_service/_governance_list.html", {"rules": rules}
    )


# ── Email Queue ───────────────────────────────────────────────────────────────


@router.get("/email-queue", response_class=HTMLResponse)
def cs_email_queue(
    request: Request,
    status: str = "pending",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    approvals = (
        db.query(EmailApproval)
        .filter(EmailApproval.status == status)
        .order_by(EmailApproval.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {
            "approvals": approvals,
            "status": status,
            "gmail_connected": _gmail_connected(db),
        },
    )


@router.post("/email-queue/{approval_id}/approve", response_class=HTMLResponse)
def cs_email_approve(
    approval_id: int,
    request: Request,
    user: dict = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    approval = db.get(EmailApproval, approval_id)
    if not approval or approval.status != "pending":
        return Response(status_code=404)

    try:
        from app.services import gmail_monitor

        gmail_monitor.send_reply_via_gmail_api(approval, db)
        approval.status = "sent"
        approval.reviewed_by = user.get("email", "")
        approval.reviewed_at = datetime.now()
        approval.sent_at = datetime.now()
    except Exception as exc:
        approval.status = "approved"
        approval.reviewed_by = user.get("email", "")
        approval.reviewed_at = datetime.now()
        approval.review_notes = f"Send failed: {exc}"
    db.commit()
    db.refresh(approval)
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {
            "approvals": [approval],
            "status": approval.status,
            "gmail_connected": _gmail_connected(db),
        },
    )


@router.post("/email-queue/{approval_id}/reject", response_class=HTMLResponse)
def cs_email_reject(
    approval_id: int,
    request: Request,
    user: dict = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    approval = db.get(EmailApproval, approval_id)
    if not approval:
        return Response(status_code=404)
    approval.status = "rejected"
    approval.reviewed_by = user.get("email", "")
    approval.reviewed_at = datetime.now()
    db.commit()
    db.refresh(approval)
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {
            "approvals": [approval],
            "status": approval.status,
            "gmail_connected": _gmail_connected(db),
        },
    )


@router.post("/email-queue/{approval_id}/edit-draft", response_class=HTMLResponse)
def cs_email_edit_draft(
    approval_id: int,
    request: Request,
    draft_subject: str = Form(...),
    draft_body: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    approval = db.get(EmailApproval, approval_id)
    if not approval:
        return Response(status_code=404)
    approval.draft_subject = draft_subject.strip()
    approval.draft_body = draft_body.strip()
    db.commit()
    db.refresh(approval)
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {"approvals": [approval], "status": "pending", "gmail_connected": _gmail_connected(db)},
    )


@router.post("/email-queue/{approval_id}/generate-draft", response_class=HTMLResponse)
def cs_generate_draft(
    approval_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from app.services import gmail_monitor

    approval = db.get(EmailApproval, approval_id)
    if not approval:
        return Response(status_code=404)
    gmail_monitor.draft_ai_reply(approval, db)
    db.refresh(approval)
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {"approvals": [approval], "status": "pending", "gmail_connected": _gmail_connected(db)},
    )


@router.delete("/email-queue/{approval_id}", response_class=HTMLResponse)
def cs_email_delete(
    approval_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    approval = db.get(EmailApproval, approval_id)
    if approval:
        db.delete(approval)
        db.commit()
    new_count = _pending_emails_count(db)
    badge_inner = f'<span class="badge bg-danger ms-1">{new_count}</span>' if new_count > 0 else ""
    oob = f'<span id="email-tab-badge" hx-swap-oob="true">{badge_inner}</span>'
    return HTMLResponse(oob)


@router.post("/email-queue/clear-resolved", response_class=HTMLResponse)
def cs_email_clear_resolved(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    db.query(EmailApproval).filter(
        EmailApproval.status.in_(["sent", "rejected"])
    ).delete(synchronize_session=False)
    db.commit()
    approvals = (
        db.query(EmailApproval)
        .filter(EmailApproval.status == "pending")
        .order_by(EmailApproval.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "customer_service/_email_queue.html",
        {"approvals": approvals, "status": "pending", "gmail_connected": _gmail_connected(db)},
    )


# ── Escalations ───────────────────────────────────────────────────────────────


@router.get("/escalations", response_class=HTMLResponse)
def cs_escalations(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    escalations = _get_escalations(db)
    return templates.TemplateResponse(
        request,
        "customer_service/_escalations.html",
        {"escalations": escalations, "pending_escalations": len(escalations)},
    )


@router.post("/escalations/dismiss-all", response_class=HTMLResponse)
def cs_escalation_dismiss_all(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    _set_setting(db, "chatbot_escalation_pending", json.dumps([]))
    return templates.TemplateResponse(
        request,
        "customer_service/_escalations.html",
        {"escalations": [], "pending_escalations": 0},
    )


@router.post("/escalations/{index}/dismiss", response_class=HTMLResponse)
def cs_escalation_dismiss(
    index: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    escalations = _get_escalations(db)
    if 0 <= index < len(escalations):
        escalations.pop(index)
        _set_setting(db, "chatbot_escalation_pending", json.dumps(escalations))
    return templates.TemplateResponse(
        request,
        "customer_service/_escalations.html",
        {"escalations": escalations, "pending_escalations": len(escalations)},
    )


# ── Gmail OAuth ───────────────────────────────────────────────────────────────


@router.get("/gmail/connect")
def cs_gmail_connect(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    from app.services import gmail_monitor

    state = secrets.token_urlsafe(16)
    request.session["gmail_oauth_state"] = state
    redirect_uri = str(request.url_for("cs_gmail_callback"))
    auth_url, _ = gmail_monitor.build_gmail_auth_url(redirect_uri, state)
    return RedirectResponse(auth_url)


@router.get("/gmail/callback", name="cs_gmail_callback")
def cs_gmail_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            f"/customer-service/?flash_type=danger&flash_msg=Gmail+OAuth+error:+{error}"
        )

    saved_state = request.session.pop("gmail_oauth_state", None)
    if not saved_state or saved_state != state:
        return RedirectResponse(
            "/customer-service/?flash_type=danger&flash_msg=OAuth+state+mismatch"
        )

    try:
        from app.services import gmail_monitor

        redirect_uri = str(request.url_for("cs_gmail_callback"))
        token_data = gmail_monitor.exchange_code_for_tokens(code, redirect_uri)
        gmail_monitor.store_tokens(db, token_data)
    except Exception as exc:
        return RedirectResponse(
            f"/customer-service/?flash_type=danger&flash_msg=Token+exchange+failed:+{exc}"
        )

    return RedirectResponse(
        "/customer-service/?flash_type=success&flash_msg=Gmail+inbox+connected+successfully!"
    )


@router.post("/gmail/poll", response_class=HTMLResponse)
def cs_gmail_poll(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from app.services import gmail_monitor

    if not _gmail_connected(db):
        return HTMLResponse('<span class="text-danger small">Gmail not connected.</span>')

    background_tasks.add_task(gmail_monitor.poll_and_draft)
    return HTMLResponse(
        '<span class="text-success small"><i class="bi bi-check me-1"></i>Polling started…</span>'
    )


# ── Manager AI Chat ───────────────────────────────────────────────────────────


@router.post("/manager-chat", response_class=HTMLResponse)
def cs_manager_chat(
    request: Request,
    message: str = Form(...),
    user: dict = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    employee_email = user.get("email", "employee")
    session_id = f"manager:{employee_email}"

    # Save user message
    db.add(ChatMessage(session_id=session_id, role="user", content=message.strip()))
    db.commit()

    # Synchronous manager response
    reply = cs_manager_agent.run_manager_response(employee_email, message.strip(), db)

    # Save assistant response
    asst_msg = ChatMessage(session_id=session_id, role="assistant", content=reply)
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    # Return both bubbles as HTML
    user_html = (
        f'<div class="chat-msg chat-msg--user">'
        f'<div class="chat-bubble chat-bubble--user">{message.strip()}</div></div>'
    )
    asst_html = (
        f'<div class="chat-msg chat-msg--assistant">'
        f'<div class="chat-bubble chat-bubble--assistant">{reply}</div>'
        f'<div class="chat-ts">{asst_msg.created_at.strftime("%H:%M") if asst_msg.created_at else ""}</div>'
        f"</div>"
    )
    return HTMLResponse(content=user_html + asst_html)


# ── Chat History ──────────────────────────────────────────────────────────────


def _parse_dt(v: object) -> datetime | None:
    """Coerce a value to datetime — SQLite aggregate functions return ISO strings, not datetime objects."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        return None


def _build_chat_history_context(db: Session) -> dict:
    """Query public chatbot sessions and group them by calendar date."""
    sessions_raw = (
        db.query(
            ChatMessage.session_id,
            sql_func.count(ChatMessage.id).label("msg_count"),
            sql_func.max(ChatMessage.created_at).label("last_at"),
            sql_func.min(ChatMessage.created_at).label("started_at"),
        )
        .filter(~ChatMessage.session_id.like("manager:%"))
        .group_by(ChatMessage.session_id)
        .order_by(sql_func.max(ChatMessage.created_at).desc())
        .limit(100)
        .all()
    )

    sessions = []
    for row in sessions_raw:
        first_msg = (
            db.query(ChatMessage.content)
            .filter(
                ChatMessage.session_id == row.session_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.id)
            .first()
        )
        sessions.append(
            {
                "session_id": row.session_id,
                "msg_count": row.msg_count,
                "last_at": _parse_dt(row.last_at),
                "started_at": _parse_dt(row.started_at),
                "first_message": first_msg[0][:80] if first_msg else "(no messages)",
            }
        )

    today = date_type.today()
    yesterday = today - timedelta(days=1)

    grouped: defaultdict = defaultdict(list)
    for s in sessions:
        day = s["last_at"].date() if s["last_at"] else today
        grouped[day].append(s)

    session_groups = [
        {"date": d, "sessions": grouped[d]}
        for d in sorted(grouped.keys(), reverse=True)
    ]

    return {
        "session_groups": session_groups,
        "total_sessions": len(sessions),
        "today": today,
        "yesterday": yesterday,
    }


@router.get("/chat-history", response_class=HTMLResponse)
def cs_chat_history(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "customer_service/_chat_history.html",
        _build_chat_history_context(db),
    )


# ── Chat History Delete ───────────────────────────────────────────────────────


@router.post("/chat-history/{session_id}/delete", response_class=HTMLResponse)
def cs_chat_history_delete_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(
        synchronize_session=False
    )
    db.commit()
    return HTMLResponse("")


@router.post("/chat-history/clear", response_class=HTMLResponse)
def cs_chat_history_delete_all(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    db.query(ChatMessage).filter(
        ChatMessage.session_id.notlike("manager:%")
    ).delete(synchronize_session=False)
    db.commit()
    return templates.TemplateResponse(
        request,
        "customer_service/_chat_history.html",
        {"session_groups": [], "total_sessions": 0, "today": date_type.today(), "yesterday": date_type.today()},
    )


# ── AI Settings ───────────────────────────────────────────────────────────────


@router.get("/ai-settings", response_class=HTMLResponse)
def cs_ai_settings(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    from app.config import settings as app_settings
    from app.services.cs_chatbot_agent import PROVIDER_MODELS, get_active_provider

    current_provider, current_model = get_active_provider(db)

    key_status = [
        ("anthropic", "Claude", bool(app_settings.anthropic_api_key), "Paid"),
        ("groq", "Groq", bool(app_settings.groq_api_key), "Free tier"),
        ("openai", "OpenAI", bool(app_settings.openai_api_key), "Paid"),
        ("gemini", "Gemini", bool(app_settings.gemini_api_key), "Free tier"),
        ("ollama", "Ollama", _ollama_running(), "Local"),
    ]

    return templates.TemplateResponse(
        request,
        "customer_service/_ai_settings.html",
        {
            "providers": _PROVIDERS,
            "provider_models": PROVIDER_MODELS,
            "current_provider": current_provider,
            "current_model": current_model,
            "key_status": key_status,
        },
    )


@router.post("/ai-settings", response_class=HTMLResponse)
def cs_ai_settings_save(
    request: Request,
    provider: str = Form(...),
    model: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _set_setting(db, "cs_ai_provider", provider)
    _set_setting(db, "cs_ai_model", model)
    return HTMLResponse(
        f'<span class="text-success"><i class="bi bi-check-circle me-1"></i>'
        f"Saved — chatbot now using <strong>{provider}</strong> / <strong>{model}</strong></span>"
    )
