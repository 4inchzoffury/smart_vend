"""Tests for the revamped customer-service email queue.

Covers the two things the overhaul changed: how inbound mail is classified, and
that polling is non-destructive (never marks the live Gmail inbox read) and
idempotent (dedups on repeat polls).
"""

from __future__ import annotations

import base64

from sqlalchemy.orm import Session

from app.models.email_approval import EmailApproval


def _make_message(sender: str, subject: str, body: str, thread_id: str = "t1") -> dict:
    return {
        "threadId": thread_id,
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
    }


# ── Classification heuristics ─────────────────────────────────────────────────


def test_classify_heuristics(db: Session, monkeypatch) -> None:
    from app.services import cs_email_agent

    monkeypatch.setattr(cs_email_agent.settings, "allowed_emails", "owner@primemicromarkets.com")
    monkeypatch.setattr(cs_email_agent.settings, "gmail_user", "primemicromarkets@gmail.com")
    # Empty key forces the no-network degrade path for unknown senders.
    monkeypatch.setattr(cs_email_agent.settings, "groq_api_key", "")

    cat, _ = cs_email_agent.classify_email("Re: x", "b", "owner@primemicromarkets.com", db)
    assert cat == "internal"

    cat, _ = cs_email_agent.classify_email("Receipt", "b", "no-reply@stripe.com", db)
    assert cat == "other"

    # Unknown sender + no classifier available → queued for manual triage, not lost.
    cat, reason = cs_email_agent.classify_email("Hello", "b", "stranger@gmail.com", db)
    assert cat == "unclassified"
    assert reason


# ── Polling: classify, auto-draft, non-destructive, idempotent ────────────────


def test_poll_classifies_autodrafts_and_is_non_destructive(db: Session, monkeypatch) -> None:
    from app.services import cs_email_agent, gmail_monitor

    monkeypatch.setattr(gmail_monitor, "get_valid_access_token", lambda d: "tok")

    posts: list = []
    monkeypatch.setattr(gmail_monitor, "_gmail_post", lambda *a, **k: posts.append((a, k)) or {})

    def fake_get(path: str, token: str, params: dict | None = None) -> dict:
        if path == "messages":
            return {"messages": [{"id": "m1"}]}
        if path == "messages/m1":
            return _make_message("Jane Doe <jane@example.com>", "Do you serve gyms?", "Hi there")
        return {}

    monkeypatch.setattr(gmail_monitor, "_gmail_get", fake_get)
    monkeypatch.setattr(
        cs_email_agent, "classify_email", lambda s, b, e, d: ("customer", "Asking about service")
    )
    drafted: list[int] = []
    monkeypatch.setattr(cs_email_agent, "draft_reply", lambda ap, d: drafted.append(ap.id))

    created = gmail_monitor.poll_new_emails(db)
    assert len(created) == 1
    assert created[0].category == "customer"
    assert created[0].classification_reason == "Asking about service"
    assert drafted == [created[0].id]  # customer mail is auto-drafted
    assert posts == []  # never mutates Gmail — no removeLabelIds / mark-read call

    # A second poll of the same message creates nothing new (dedup).
    assert gmail_monitor.poll_new_emails(db) == []
    assert db.query(EmailApproval).count() == 1


def test_poll_does_not_autodraft_non_customer(db: Session, monkeypatch) -> None:
    from app.services import cs_email_agent, gmail_monitor

    monkeypatch.setattr(gmail_monitor, "get_valid_access_token", lambda d: "tok")
    monkeypatch.setattr(gmail_monitor, "_gmail_post", lambda *a, **k: {})

    def fake_get(path: str, token: str, params: dict | None = None) -> dict:
        if path == "messages":
            return {"messages": [{"id": "v1"}]}
        return _make_message("Sales <sales@vendor.com>", "Buy our racks", "Pitch")

    monkeypatch.setattr(gmail_monitor, "_gmail_get", fake_get)
    monkeypatch.setattr(
        cs_email_agent, "classify_email", lambda s, b, e, d: ("vendor", "B2B pitch")
    )
    drafted: list[int] = []
    monkeypatch.setattr(cs_email_agent, "draft_reply", lambda ap, d: drafted.append(ap.id))

    created = gmail_monitor.poll_new_emails(db)
    assert created[0].category == "vendor"
    assert drafted == []  # only customer mail is auto-drafted


# ── Queue filtering + tab badge ───────────────────────────────────────────────


def _approval(
    message_id: str, subject: str, category: str, status: str = "pending"
) -> EmailApproval:
    return EmailApproval(
        gmail_thread_id=f"t-{message_id}",
        gmail_message_id=message_id,
        sender_email="x@example.com",
        original_subject=subject,
        original_body="body",
        category=category,
        status=status,
    )


def test_email_queue_category_filter_and_badge(client, db: Session) -> None:
    db.add_all(
        [
            _approval("c1", "Customer A", "customer"),
            _approval("c2", "Customer B", "customer"),
            _approval("v1", "Vendor Pitch", "vendor"),
        ]
    )
    db.commit()

    r_cust = client.get("/customer-service/email-queue?category=customer")
    assert "Customer A" in r_cust.text
    assert "Customer B" in r_cust.text
    assert "Vendor Pitch" not in r_cust.text
    # Tab badge counts only pending customer mail (2), not the vendor row.
    assert 'bg-danger ms-1">2<' in r_cust.text

    r_other = client.get("/customer-service/email-queue?category=other")
    assert "Vendor Pitch" in r_other.text
    assert "Customer A" not in r_other.text
