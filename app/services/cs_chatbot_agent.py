"""Customer-facing chatbot agent with governance-rule-driven system prompt."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models.chat import ChatMessage
from app.models.cs_governance import CSGovernanceRule
from app.models.settings import AppSetting
from app.services import calendly as calendly_svc

_MAX_TOOL_CALLS = 5
_MAX_HISTORY = 10
_RATE_LIMIT_PER_HOUR = 20

_CATEGORY_LABELS = {
    "tone": "Tone & Style",
    "info_policy": "Information Policy",
    "escalation": "Escalation Rules",
    "knowledge": "Company Knowledge",
    "custom": "Additional Rules",
}

# ── Provider / model defaults ────────────────────────────────────────────────

_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

PROVIDER_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
    "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "llama-3.1-70b-versatile"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "gemini": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"],
}


def get_active_provider(db: Session) -> tuple[str, str]:
    """Return (provider, model) from AppSetting, falling back to defaults."""
    p_row = db.get(AppSetting, "cs_ai_provider")
    m_row = db.get(AppSetting, "cs_ai_model")
    provider = (p_row.value if p_row else None) or _DEFAULT_PROVIDER
    model = (m_row.value if m_row else None) or _DEFAULT_MODEL
    return provider, model


# ── System prompt ────────────────────────────────────────────────────────────


def build_chatbot_system_prompt(db: Session) -> str:
    rules = (
        db.query(CSGovernanceRule)
        .filter(CSGovernanceRule.is_active.is_(True))
        .order_by(CSGovernanceRule.display_order, CSGovernanceRule.id)
        .all()
    )

    base = (
        f"You are a helpful customer service assistant for Prime Micro Markets, "
        f"a Service-Disabled Veteran-Owned smart cooler vending company serving "
        f"Bay County, FL (Panama City area).\n\n"
        f"{settings.company_blurb}\n\n"
        f"You help answer questions from potential and existing host location partners.\n\n"
    )

    if rules:
        grouped: dict[str, list[CSGovernanceRule]] = {}
        for r in rules:
            grouped.setdefault(r.category, []).append(r)

        rule_sections = []
        for cat, cat_rules in grouped.items():
            label = _CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
            items = "\n".join(f"  - {r.rule_text}" for r in cat_rules)
            rule_sections.append(f"**{label}:**\n{items}")

        base += "RULES YOU MUST FOLLOW:\n" + "\n\n".join(rule_sections) + "\n\n"

    calendly_note = (
        (
            "When asked about scheduling or booking a meeting, use the "
            "check_calendly_availability tool to fetch real-time available slots."
        )
        if settings.calendly_api_key
        else (
            f"When asked about scheduling, direct them to: {settings.calendly_url}"
            if settings.calendly_url
            else "When asked about scheduling, ask them to email us at primemicromarkets@gmail.com."
        )
    )

    base += (
        f"{calendly_note}\n\n"
        f"When a question or situation is beyond your ability to resolve — such as legal matters, "
        f"contract disputes, or situations requiring human judgement — use the "
        f"request_human_followup tool.\n\n"
        f"Keep responses concise and helpful. You are representing a professional business."
    )
    return base


# ── Tool definitions ─────────────────────────────────────────────────────────

_TOOL_CALENDLY = {
    "name": "check_calendly_availability",
    "description": (
        "Check real-time availability and return the next available booking slots. "
        "Use this when a customer asks about scheduling a call, demo, or site visit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Brief reason the customer wants to schedule (optional)",
            }
        },
        "required": [],
    },
}

_TOOL_ESCALATE = {
    "name": "request_human_followup",
    "description": (
        "Use this when the customer needs a human team member — e.g., billing issues, "
        "legal matters, contract questions, or persistent frustration."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why human follow-up is needed",
            },
            "urgency": {
                "type": "string",
                "enum": ["normal", "high"],
                "description": "Urgency level",
            },
        },
        "required": ["reason"],
    },
}

# OpenAI-format equivalents (used for Groq, OpenAI, Gemini-OpenAI-compat)
_TOOL_CALENDLY_OAI = {
    "type": "function",
    "function": {
        "name": "check_calendly_availability",
        "description": _TOOL_CALENDLY["description"],
        "parameters": _TOOL_CALENDLY["input_schema"],
    },
}

_TOOL_ESCALATE_OAI = {
    "type": "function",
    "function": {
        "name": "request_human_followup",
        "description": _TOOL_ESCALATE["description"],
        "parameters": _TOOL_ESCALATE["input_schema"],
    },
}


def _handle_tool(name: str, tool_input: dict, session_id: str, db: Session) -> str:
    if name == "check_calendly_availability":
        try:
            slots = calendly_svc.get_upcoming_slots(max_slots=8)
            return calendly_svc.format_slots_for_chat(slots)
        except Exception as exc:
            if settings.calendly_url:
                return f"Book directly here: {settings.calendly_url}"
            return f"Unable to fetch availability ({exc}). Please email primemicromarkets@gmail.com to schedule."

    if name == "request_human_followup":
        reason = tool_input.get("reason", "Not specified")
        urgency = tool_input.get("urgency", "normal")
        # Log escalation request
        db.add(
            ChatMessage(
                session_id=session_id,
                role="tool",
                tool_name="request_human_followup",
                content=json.dumps({"reason": reason, "urgency": urgency}),
            )
        )
        # Append to escalation pending list in AppSetting
        key = "chatbot_escalation_pending"
        row = db.get(AppSetting, key)
        try:
            existing = json.loads(row.value) if row else []
        except Exception:
            existing = []
        existing.append(
            {
                "session_id": session_id,
                "reason": reason,
                "urgency": urgency,
                "created_at": datetime.now().isoformat(),
            }
        )
        if row:
            row.value = json.dumps(existing[-50:])  # keep last 50
        else:
            db.add(AppSetting(key=key, value=json.dumps(existing[-50:])))
        db.commit()
        return "Human follow-up requested. A team member will reach out shortly."

    return "Unknown tool."


# ── Rate limiting ─────────────────────────────────────────────────────────────


def _is_rate_limited(session_id: str, db: Session) -> bool:
    cutoff = datetime.now() - timedelta(hours=1)
    count = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= cutoff,
        )
        .count()
    )
    return count >= _RATE_LIMIT_PER_HOUR


# ── History loader ────────────────────────────────────────────────────────────


def _load_history(session_id: str, db: Session) -> list[dict]:
    msgs = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role.in_(["user", "assistant"]),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(_MAX_HISTORY)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


# ── Anthropic runner ─────────────────────────────────────────────────────────


def _run_anthropic(
    messages: list[dict], system: str, model: str, session_id: str, db: Session
) -> str:
    import anthropic  # type: ignore[import-untyped]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    tool_calls = 0

    while tool_calls <= _MAX_TOOL_CALLS:
        response = client.messages.create(
            model=model,
            max_tokens=768,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=[_TOOL_CALENDLY, _TOOL_ESCALATE],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return "".join(b.text for b in response.content if hasattr(b, "text"))

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls += 1
                result = _handle_tool(block.name, block.input, session_id, db)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    # Fallback: extract any text from the last assistant turn
    last = messages[-1] if messages else {}
    content = last.get("content", [])
    if isinstance(content, list):
        return (
            "".join(b.text for b in content if hasattr(b, "text"))
            or "I'm sorry, I couldn't generate a response."
        )
    return str(content) or "I'm sorry, I couldn't generate a response."


# ── OpenAI-compatible runner (Groq + OpenAI) ─────────────────────────────────


def _run_openai_compat(
    messages: list[dict],
    system: str,
    model: str,
    api_key: str,
    base_url: str | None,
    session_id: str,
    db: Session,
) -> str:
    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        return "OpenAI SDK not installed. Run: pip install openai"

    client = OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
    oai_messages = [{"role": "system", "content": system}] + [
        {
            "role": m["role"],
            "content": m["content"] if isinstance(m["content"], str) else str(m["content"]),
        }
        for m in messages
    ]
    tool_calls_count = 0

    while tool_calls_count <= _MAX_TOOL_CALLS:
        response = client.chat.completions.create(
            model=model,
            messages=oai_messages,
            tools=[_TOOL_CALENDLY_OAI, _TOOL_ESCALATE_OAI],
            tool_choice="auto",
            max_tokens=768,
        )
        choice = response.choices[0]
        msg = choice.message
        oai_messages.append(
            {"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls}
        )

        if choice.finish_reason == "stop" or not msg.tool_calls:
            return msg.content or "I'm sorry, I couldn't generate a response."

        for tc in msg.tool_calls:
            tool_calls_count += 1
            try:
                tool_input = json.loads(tc.function.arguments)
            except Exception:
                tool_input = {}
            result = _handle_tool(tc.function.name, tool_input, session_id, db)
            oai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    return "I'm sorry, I encountered an issue generating a response."


# ── Gemini runner ─────────────────────────────────────────────────────────────


def _run_gemini(messages: list[dict], system: str, model: str, session_id: str, db: Session) -> str:
    # Use Gemini's OpenAI-compatible endpoint
    return _run_openai_compat(
        messages=messages,
        system=system,
        model=model,
        api_key=settings.gemini_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        session_id=session_id,
        db=db,
    )


# ── Main background task ─────────────────────────────────────────────────────


def get_chatbot_reply(session_id: str, user_message: str, db: Session, before_id: int = 0) -> str:
    """Synchronous Claude call using the caller's DB session. Saves and returns the reply."""
    if _is_rate_limited(session_id, db):
        reply = (
            "You've sent a lot of messages recently. Please email us directly at "
            "primemicromarkets@gmail.com and we'll be happy to help!"
        )
        db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
        db.commit()
        return reply

    provider, model = get_active_provider(db)
    system = build_chatbot_system_prompt(db)

    # Load history excluding the current user message to avoid duplicates
    q = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.role.in_(["user", "assistant"]),
    )
    if before_id:
        q = q.filter(ChatMessage.id < before_id)
    history_rows = q.order_by(ChatMessage.created_at.desc()).limit(_MAX_HISTORY).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]
    messages = history + [{"role": "user", "content": user_message}]

    try:
        if provider == "anthropic":
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not configured.")
            reply = _run_anthropic(messages, system, model, session_id, db)

        elif provider == "groq":
            if not settings.groq_api_key:
                raise RuntimeError("GROQ_API_KEY not configured.")
            reply = _run_openai_compat(
                messages, system, model,
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                session_id=session_id, db=db,
            )

        elif provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY not configured.")
            reply = _run_openai_compat(
                messages, system, model,
                api_key=settings.openai_api_key,
                base_url=None,
                session_id=session_id, db=db,
            )

        elif provider == "gemini":
            if not settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY not configured.")
            reply = _run_gemini(messages, system, model, session_id, db)

        else:
            raise RuntimeError(f"Unknown provider: {provider}")

    except Exception as exc:
        reply = (
            f"I'm sorry, I ran into an issue. Please contact us at "
            f"primemicromarkets@gmail.com. (Error: {exc})"
        )

    db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
    db.commit()
    return reply
