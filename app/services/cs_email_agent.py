"""Inbound-email intelligence for the customer-service queue.

Two jobs, kept out of the Gmail transport layer (``gmail_monitor``):

  1. ``classify_email`` — decide whether an inbound message is genuine customer
     mail or something else (vendor pitch, newsletter, internal, spam). A free
     heuristic pre-filter handles the obvious cases; everything else goes to a
     free Groq classifier. Customer-reply *quality* stays on Claude (see
     ``draft_reply``); cheap, high-volume triage stays on Groq — same cost split
     as the public chatbot.
  2. ``draft_reply`` — generate a governance-aware reply draft for customer mail
     on Claude Haiku.

Both degrade gracefully: a missing key or API error never loses an email — it is
queued as ``unclassified`` for manual triage, or its draft is marked
``draft_failed`` with the error recorded.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.models.cs_governance import CSGovernanceRule
from app.models.email_approval import EmailApproval
from app.services.json_extract import extract_json_list

_log = logging.getLogger(__name__)

# Allowed classifier buckets. Anything outside this set is coerced to "other".
VALID_CATEGORIES = {
    "customer",
    "vendor",
    "promotional",
    "internal",
    "spam",
    "other",
    "unclassified",
}

_GROQ_MODEL = "llama-3.1-8b-instant"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_DRAFT_MODEL = "claude-haiku-4-5-20251001"

# Automated / machine senders that never warrant a customer reply.
_AUTOMATED_LOCALPART_RE = re.compile(
    r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce|notifications?|"
    r"donotreply|automated)",
    re.IGNORECASE,
)

# Rule-category → display label, mirrored from the chatbot prompt builder so the
# email draft reads the same governance rules the chatbot follows.
_RULE_CATEGORY_LABELS = {
    "tone": "Tone & Style",
    "info_policy": "Information Policy",
    "escalation": "Escalation Rules",
    "knowledge": "Company Knowledge",
    "custom": "Additional Rules",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _internal_addresses() -> set[str]:
    """Lower-cased set of team/owner addresses (the app allowlist + the inbox)."""
    addrs = {a.strip().lower() for a in settings.allowed_emails.split(",") if a.strip()}
    if settings.gmail_user:
        addrs.add(settings.gmail_user.strip().lower())
    return addrs


def _localpart(email: str) -> str:
    return email.split("@", 1)[0] if "@" in email else email


# ── Classification ──────────────────────────────────────────────────────────


def classify_email(subject: str, body: str, sender_email: str, db: Session) -> tuple[str, str]:
    """Return ``(category, reason)`` for an inbound email.

    Heuristics run first (free, deterministic); the Groq classifier handles the
    rest. Never raises — degrades to ``("unclassified", ...)`` so the message is
    still queued for manual triage.
    """
    sender = (sender_email or "").strip().lower()

    # ── Heuristic pre-filter ──
    if sender and sender in _internal_addresses():
        return "internal", "From a team/owner address"
    if _AUTOMATED_LOCALPART_RE.search(_localpart(sender)):
        return "other", "Automated / no-reply sender"

    # ── Groq classifier ──
    if not settings.groq_api_key:
        return "unclassified", "Classifier unavailable — needs manual triage"

    system = (
        "You triage inbound email for Prime Micro Markets, a veteran-owned smart "
        "cooler vending company in Bay County, FL that places self-checkout coolers "
        "in gyms, hotels, offices, and other host locations.\n"
        "Classify the email into exactly one category:\n"
        "  customer    — a current or prospective customer / host-location partner "
        "(interest, questions, support, complaints, scheduling)\n"
        "  vendor      — a supplier, B2B sales pitch, or cold solicitation TO the company\n"
        "  promotional — a newsletter, marketing blast, or promotion\n"
        "  spam        — spam or phishing\n"
        "  other       — anything else (automated notices, receipts, personal mail)\n"
        'Respond with ONLY JSON: {"category": "<one of the above>", '
        '"reason": "<under 15 words>"}'
    )
    user = f"From: {sender_email}\nSubject: {subject}\n\n{(body or '')[:1500]}"

    try:
        raw = _groq_chat(system, user, max_tokens=120)
        records = extract_json_list(raw, context="email classification")
        record = records[0] if records else {}
        category = str(record.get("category", "")).strip().lower()
        reason = str(record.get("reason", "")).strip()[:200]
        if category not in VALID_CATEGORIES or category == "unclassified":
            return "other", reason or "Unrecognized category from classifier"
        return category, reason or "Classified by AI"
    except Exception as exc:  # noqa: BLE001 — triage must never crash the poller
        _log.warning("Email classifier failed (%s); leaving unclassified.", exc)
        return "unclassified", "Classifier unavailable — needs manual triage"


def _groq_chat(system: str, user: str, *, max_tokens: int) -> str:
    """Single-shot Groq completion via the OpenAI-compatible endpoint."""
    from openai import OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=settings.groq_api_key, base_url=_GROQ_BASE_URL)
    response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0,
    )
    return response.choices[0].message.content or ""


# ── Draft generation ──────────────────────────────────────────────────────────


def build_email_draft_prompt(db: Session) -> str:
    """System prompt for drafting an email reply, including active governance rules.

    Reuses the same governance rules the public chatbot follows, but framed for
    email (no chat-widget-specific instructions).
    """
    rules = (
        db.query(CSGovernanceRule)
        .filter(CSGovernanceRule.is_active.is_(True))
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )

    prompt = (
        "You draft customer-service email replies for Prime Micro Markets, a "
        "veteran-owned smart cooler vending company serving Bay County, FL "
        "(Panama City area).\n\n"
        f"{settings.company_blurb}\n\n"
    )

    if rules:
        grouped: dict[str, list[CSGovernanceRule]] = {}
        for r in rules:
            grouped.setdefault(r.category, []).append(r)
        sections = []
        for cat, cat_rules in grouped.items():
            label = _RULE_CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
            items = "\n".join(f"  - {r.rule_text}" for r in cat_rules)
            sections.append(f"**{label}:**\n{items}")
        prompt += "RULES YOU MUST FOLLOW:\n" + "\n\n".join(sections) + "\n\n"

    prompt += (
        "Write a professional, friendly reply. Address the customer's concern "
        "directly and concisely. Sign as 'Prime Micro Markets Team'. When scheduling "
        "comes up, invite them to reply or email primemicromarkets@gmail.com.\n\n"
        "Format your reply EXACTLY as:\n"
        "Subject: <subject line starting with Re:>\n\n"
        "<email body>"
    )
    return prompt


def draft_reply(approval: EmailApproval, db: Session) -> None:
    """Generate a governance-aware AI draft for ``approval`` (Claude Haiku)."""
    if not settings.anthropic_api_key:
        approval.status = "draft_failed"
        approval.review_notes = "ANTHROPIC_API_KEY not configured."
        db.commit()
        return

    try:
        import anthropic  # type: ignore[import-untyped]

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        system = build_email_draft_prompt(db)
        user = (
            f"Reply to this email from "
            f"{approval.sender_name or approval.sender_email}:\n\n"
            f"Subject: {approval.original_subject}\n\n"
            f"{approval.original_body}"
        )
        response = client.messages.create(
            model=_DRAFT_MODEL,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = response.content[0].text if response.content else ""

        subject_match = re.match(r"Subject:\s*(.+?)(\n|$)", text)
        if subject_match:
            approval.draft_subject = subject_match.group(1).strip()
            approval.draft_body = text[subject_match.end() :].strip()
        else:
            approval.draft_subject = f"Re: {approval.original_subject}"
            approval.draft_body = text.strip()

        approval.status = "pending"
    except Exception as exc:  # noqa: BLE001 — surface the error in the UI, don't crash
        approval.status = "draft_failed"
        approval.review_notes = str(exc)

    db.commit()
