"""Gmail API integration for monitoring the company inbox and drafting AI replies.

OAuth flow: Google OAuth 2.0 with gmail.readonly + gmail.send scopes.
Tokens are stored in AppSetting (gmail_refresh_token, gmail_access_token, gmail_token_expiry).
The existing GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are reused.
"""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_approval import EmailApproval
from app.models.settings import AppSetting

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


# ── Settings helpers ──────────────────────────────────────────────────────────


def _get(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    return row.value if row else ""


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


# ── OAuth helpers ─────────────────────────────────────────────────────────────


def build_gmail_auth_url(redirect_uri: str, state: str) -> tuple[str, str]:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}", state


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


def store_tokens(db: Session, token_data: dict) -> None:
    _set(db, "gmail_access_token", token_data.get("access_token", ""))
    refresh = token_data.get("refresh_token", "")
    if refresh:
        _set(db, "gmail_refresh_token", refresh)
    expires_in = int(token_data.get("expires_in", 3600))
    expiry = (datetime.now(tz=UTC) + timedelta(seconds=expires_in)).isoformat()
    _set(db, "gmail_token_expiry", expiry)
    db.commit()


def get_valid_access_token(db: Session) -> str:
    refresh_token = _get(db, "gmail_refresh_token")
    if not refresh_token:
        raise RuntimeError(
            "Gmail not connected. Visit /customer-service/gmail/connect to authorize."
        )

    # Check if current token is still valid
    expiry_str = _get(db, "gmail_token_expiry")
    access_token = _get(db, "gmail_access_token")
    if access_token and expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if datetime.now(tz=UTC) < expiry - timedelta(minutes=5):
                return access_token
        except Exception:
            pass

    # Refresh the token
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

    store_tokens(db, token_data)
    return token_data["access_token"]


# ── Gmail API calls ───────────────────────────────────────────────────────────


def _gmail_get(path: str, token: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{_GMAIL_BASE}/{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
        resp.raise_for_status()
        return resp.json()


def _gmail_post(path: str, token: str, body: dict) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{_GMAIL_BASE}/{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        return decoded.strip()

    # Recurse into parts
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    # Fallback: decode HTML part if no plain text
    if mime_type == "text/html" and body_data:
        html = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        # Strip tags roughly
        return re.sub(r"<[^>]+>", " ", html).strip()

    return ""


def _extract_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def poll_new_emails(db: Session) -> list[EmailApproval]:
    """Fetch new unread customer emails and create EmailApproval records."""
    token = get_valid_access_token(db)
    result = _gmail_get(
        "messages",
        token,
        params={"q": "is:unread -from:me category:primary", "maxResults": "20"},
    )
    messages = result.get("messages", [])
    created: list[EmailApproval] = []

    for msg_ref in messages:
        msg_id = msg_ref["id"]

        # Skip if already processed
        existing = db.query(EmailApproval).filter(EmailApproval.gmail_message_id == msg_id).first()
        if existing:
            continue

        try:
            msg = _gmail_get(f"messages/{msg_id}", token, params={"format": "full"})
        except Exception:
            continue

        headers = msg.get("payload", {}).get("headers", [])
        sender_raw = _extract_header(headers, "From")
        subject = _extract_header(headers, "Subject") or "(no subject)"
        thread_id = msg.get("threadId", msg_id)
        body = _extract_body(msg.get("payload", {}))

        # Parse sender name and email
        sender_name = ""
        sender_email = sender_raw
        m = re.match(r'^"?([^"<]+?)"?\s*<([^>]+)>', sender_raw)
        if m:
            sender_name = m.group(1).strip()
            sender_email = m.group(2).strip()

        approval = EmailApproval(
            gmail_thread_id=thread_id,
            gmail_message_id=msg_id,
            sender_email=sender_email,
            sender_name=sender_name,
            original_subject=subject,
            original_body=body or "(empty body)",
            status="pending",
        )
        try:
            db.add(approval)
            db.flush()  # catch UNIQUE violation before commit
        except IntegrityError:
            db.rollback()
            continue

        # Mark email as read
        try:
            _gmail_post(f"messages/{msg_id}/modify", token, {"removeLabelIds": ["UNREAD"]})
        except Exception:
            pass

        db.commit()
        db.refresh(approval)
        created.append(approval)

    return created


def draft_ai_reply(approval: EmailApproval, db: Session) -> None:
    """Use Claude to draft a reply for an EmailApproval record."""
    if not settings.anthropic_api_key:
        approval.status = "draft_failed"
        db.commit()
        return

    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            f"You are drafting a customer service email reply for Prime Micro Markets, "
            f"a veteran-owned smart cooler vending company in Bay County, FL.\n\n"
            f"Original email from {approval.sender_name or approval.sender_email}:\n"
            f"Subject: {approval.original_subject}\n\n"
            f"{approval.original_body}\n\n"
            f"Write a professional, friendly reply email. Address the customer's concern. "
            f"Sign as 'Prime Micro Markets Team'.\n\n"
            f"Format your reply as:\n"
            f"Subject: <subject line starting with Re:>\n\n"
            f"<email body>"
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""

        import re as _re

        subject_match = _re.match(r"Subject:\s*(.+?)(\n|$)", text)
        if subject_match:
            approval.draft_subject = subject_match.group(1).strip()
            approval.draft_body = text[subject_match.end() :].strip()
        else:
            approval.draft_subject = f"Re: {approval.original_subject}"
            approval.draft_body = text.strip()

        approval.status = "pending"
    except Exception as exc:
        approval.status = "draft_failed"
        approval.review_notes = str(exc)

    db.commit()


def send_reply_via_gmail_api(approval: EmailApproval, db: Session) -> None:
    """Send an approved email reply using the Gmail API (sends FROM the company inbox)."""
    token = get_valid_access_token(db)

    msg = MIMEMultipart()
    msg["To"] = approval.sender_email
    msg["Subject"] = approval.draft_subject or f"Re: {approval.original_subject}"
    msg["In-Reply-To"] = approval.gmail_message_id
    msg["References"] = approval.gmail_message_id
    msg.attach(MIMEText(approval.draft_body or "", "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    _gmail_post("messages/send", token, {"raw": raw, "threadId": approval.gmail_thread_id})


def poll_and_draft() -> None:
    """Poll Gmail and create approval records. AI drafts are generated on demand."""
    from app.database import engine

    with Session(engine) as db:
        poll_new_emails(db)
