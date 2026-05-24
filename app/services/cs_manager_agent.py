"""Customer Service Manager AI — employee-facing agent."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models.cs_governance import CSGovernanceRule
from app.models.email_approval import EmailApproval


def build_manager_system_prompt(db: Session) -> str:
    rules = (
        db.query(CSGovernanceRule)
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )
    rule_lines = "\n".join(
        f"  [{r.category.upper()}] {'✓' if r.is_active else '✗'} {r.title}: {r.rule_text}"
        for r in rules
    )

    pending_count = db.query(EmailApproval).filter(EmailApproval.status == "pending").count()

    return (
        f"You are the Customer Service AI Manager for Prime Micro Markets, a veteran-owned "
        f"smart cooler vending company in Bay County, FL.\n\n"
        f"Your role: help the human employee team govern the customer-facing chatbot, "
        f"analyze customer interactions, draft email replies, and advise on best practices "
        f"for customer service. You are professional, knowledgeable, and practical.\n\n"
        f"CURRENT GOVERNANCE RULES (what the chatbot follows):\n{rule_lines or 'None set.'}\n\n"
        f"EMAIL QUEUE: {pending_count} email(s) currently awaiting approval.\n\n"
        f"COMPANY INFO: {settings.company_blurb}\n\n"
        f"When an employee asks you to update a rule, provide the suggested rule_text and "
        f"category so they can add it via the Governance Rules tab. "
        f"When drafting email replies, write professionally and per the governance tone rules. "
        f"Be concise and actionable in your responses."
    )


def run_manager_response(employee_email: str, user_message: str, db: Session) -> str:
    """Synchronous Claude call for manager chat. Returns the assistant's response text."""
    if not settings.anthropic_api_key:
        return "ANTHROPIC_API_KEY is not configured. Please set it in .env to use the Manager Chat."

    import anthropic  # type: ignore[import-untyped]

    system = build_manager_system_prompt(db)

    from app.models.chat import ChatMessage

    history_rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == f"manager:{employee_email}",
            ChatMessage.role.in_(["user", "assistant"]),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()
    )
    messages = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]
    messages.append({"role": "user", "content": user_message})

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    return response.content[0].text if response.content else "I couldn't generate a response."
