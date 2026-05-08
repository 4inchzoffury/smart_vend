"""Claude-powered agentic background jobs for lead research and email drafting."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models.agent import AgentJob
from app.models.sales import Prospect
from app.services import tavily

_TOOL_WEB_SEARCH: dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for local businesses in Bay County, FL. "
        "Use specific queries like 'gyms Panama City FL', 'hotels near Panama City Beach', "
        "'corporate offices Bay County Florida'. Call this multiple times with varied queries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string"},
        },
        "required": ["query"],
    },
}

_MAX_TOOL_CALLS = 10
_MAX_LOG_CHARS = 20_000


def _build_research_system_prompt(venue_types: list[str]) -> str:
    types_str = ", ".join(venue_types) if venue_types else "gyms, hotels, corporate offices, condos"
    return (
        f"You are a lead generation assistant for {settings.company_blurb}\n\n"
        f"Your goal: find real businesses in Bay County, FL that match these venue types: "
        f"{types_str}.\n\n"
        "Use the web_search tool as many times as needed to find specific businesses.\n"
        "For each business found, try to extract: company name, street address, city, venue type, "
        "estimated foot traffic (low/medium/high), contact name, and contact email if available."
        "\n\n"
        "When you have gathered enough results, output ONLY a valid JSON array. "
        "Each object must have these exact keys (use empty string if unknown):\n"
        '  company_name, address, city, venue_type, foot_traffic_estimate, '
        'contact_name, contact_email, notes\n\n'
        "Do not include any text before or after the JSON array. "
        "Only include businesses with a real company_name."
    )


def _extract_json_leads(text: str) -> list[dict[str, Any]]:
    """Extract the JSON array from Claude's final response text."""
    text = text.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return [d for d in data if isinstance(d, dict) and d.get("company_name")]
    except json.JSONDecodeError:
        return []


def run_research_job(job_id: int) -> None:
    """Background task: run the research agent to find prospects."""
    with Session(engine) as db:
        job = db.get(AgentJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now()
        db.commit()

        try:
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured in .env")

            import anthropic  # type: ignore[import-untyped]

            venue_types: list[str] = json.loads(job.input_params or "[]")
            system_prompt = _build_research_system_prompt(venue_types)

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            messages: list[dict[str, Any]] = [
                {"role": "user", "content": "Begin your research now and find businesses."}
            ]
            log_entries: list[dict[str, Any]] = []
            tool_call_count = 0

            while tool_call_count <= _MAX_TOOL_CALLS:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[_TOOL_WEB_SEARCH],
                    messages=messages,
                )

                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    leads = _extract_json_leads(final_text)
                    log_entries.append({"event": "end_turn", "leads_parsed": len(leads)})
                    break

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use" and block.name == "web_search":
                        tool_call_count += 1
                        query = block.input.get("query", "")
                        log_entries.append(
                            {"event": "tool_call", "query": query, "n": tool_call_count}
                        )
                        try:
                            results = tavily.search(query, max_results=5)
                            result_text = json.dumps(results)
                        except Exception as search_exc:
                            result_text = f"Search error: {search_exc}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})
            else:
                leads = []
                log_entries.append({"event": "max_tool_calls_reached"})

            created = skipped = 0
            for lead in leads:
                name = (lead.get("company_name") or "").strip()
                city = (lead.get("city") or "Panama City").strip()
                if not name:
                    continue
                exists = (
                    db.query(Prospect)
                    .filter(Prospect.company_name == name, Prospect.city == city)
                    .first()
                )
                if exists:
                    skipped += 1
                else:
                    p = Prospect(
                        company_name=name,
                        address=lead.get("address") or None,
                        city=city,
                        venue_type=lead.get("venue_type") or None,
                        foot_traffic_estimate=lead.get("foot_traffic_estimate") or None,
                        contact_name=lead.get("contact_name") or None,
                        contact_email=lead.get("contact_email") or None,
                        notes=lead.get("notes") or None,
                        source="agent",
                        pipeline_stage="lead",
                    )
                    db.add(p)
                    created += 1

            job.prospects_found = len(leads)
            job.prospects_created = created
            job.prospects_skipped = skipped
            job.agent_log = json.dumps(log_entries)[:_MAX_LOG_CHARS]
            job.status = "done"

        except Exception as exc:
            job.status = "error"
            job.error_message = str(exc)

        job.finished_at = datetime.now()
        db.commit()


def _build_email_draft_prompt(prospect: Prospect) -> str:
    calendly = settings.calendly_url
    scheduling_note = (
        f"Include this scheduling link for them to book a quick call: {calendly}"
        if calendly
        else "Suggest they reply to schedule a brief call or site visit."
    )
    return (
        f"You are writing a cold outreach email on behalf of Prime Vending.\n\n"
        f"About us: {settings.company_blurb}\n\n"
        f"Prospect details:\n"
        f"  Business: {prospect.company_name}\n"
        f"  Contact: {prospect.contact_name or 'the owner/manager'}\n"
        f"  Title: {prospect.contact_title or ''}\n"
        f"  Venue type: {prospect.venue_type or 'business'}\n"
        f"  City: {prospect.city}\n"
        f"  Notes: {prospect.notes or ''}\n\n"
        f"Write a short, friendly cold outreach email (3–4 paragraphs max). "
        f"Mention that we provide no-cost, cashless smart cooler machines that generate "
        f"passive revenue for the host location. Keep it conversational — not salesy. "
        f"{scheduling_note}\n\n"
        f"Format your response exactly as:\n"
        f"Subject: <subject line>\n\n"
        f"<email body>"
    )


def run_email_draft_job(job_id: int) -> None:
    """Background task: draft a personalized outreach email for a prospect."""
    with Session(engine) as db:
        job = db.get(AgentJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now()
        db.commit()

        try:
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured in .env")

            prospect = db.get(Prospect, job.prospect_id)
            if not prospect:
                raise RuntimeError(f"Prospect {job.prospect_id} not found")

            import anthropic  # type: ignore[import-untyped]

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": _build_email_draft_prompt(prospect)}],
            )

            full_text = response.content[0].text if response.content else ""

            subject = ""
            body = full_text
            subject_match = re.match(r"Subject:\s*(.+?)(\n|$)", full_text)
            if subject_match:
                subject = subject_match.group(1).strip()
                body = full_text[subject_match.end():].strip()

            job.draft_subject = subject
            job.draft_body = body
            job.status = "done"

        except Exception as exc:
            job.status = "error"
            job.error_message = str(exc)

        job.finished_at = datetime.now()
        db.commit()
