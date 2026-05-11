# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`smart_vend` is the internal management platform for Prime Micro Markets, a veteran-owned smart cooler vending business (51% Stephen Russell Troup, veteran; 49% John Michael Johnson) based in Panama City, FL. The company is pursuing VOB (Veteran-Owned Business) certification. Public domain: `primemicromarkets.com`.

## Commands

```bash
# Run dev server
uvicorn app.main:app --reload

# Lint / format
ruff check .
ruff check . --fix
ruff format .

# Tests
pytest
pytest path/to/test_file.py::test_name   # single test

# Database migrations
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic current

# Seed research tasks (idempotent)
python scripts/seed_research_tasks.py "path/to/Research_Tracker.md"
```

## Tech Stack

FastAPI 0.115 + Uvicorn · SQLite + SQLAlchemy 2.0 (sync) + Alembic · Jinja2 + Bootstrap 5.3 · HTMX 1.9 · pydantic-settings · Anthropic Claude + Tavily · Cloudflare Tunnel · Ruff · pytest

## Architecture

### App factory (`app/main.py`)

`main.py` imports all routers and mounts them. The lifespan handler calls `Base.metadata.create_all()` on startup (auto-creates tables, no migration needed for fresh installs). `SessionMiddleware` must be added last (outermost). `ProxyHeadersMiddleware` is required to trust `X-Forwarded-Proto` from Cloudflare Tunnel — without it, OAuth redirects break.

`app/models/settings.py` must be imported in `main.py` via a side-effect import (`from app.models import settings as _settings_models`) to register `AppSetting` with `Base` before `create_all` runs.

### Auth (`app/routers/auth.py`, `app/services/auth.py`)

Google OAuth via `authlib` + Starlette `SessionMiddleware`. `require_user` is a FastAPI dependency injected via `dependencies=[Depends(require_user)]` on protected routers in `main.py`. Public routes (`/`, `/login`, `/auth/*`, `/chatbot/*`) are mounted without this dependency.

### HTMX partial rendering pattern

Routers detect `request.headers.get("HX-Request") == "true"` and return partial templates (prefixed `_`) instead of full pages. Example: `GET /equipment/` returns `equipment/index.html` normally but `equipment/_unit_grid.html` for HTMX filter swaps.

### Background jobs (AgentJob pattern)

Long-running AI tasks (equipment refresh, lead research, email drafting) use FastAPI `BackgroundTasks`. A job row is written to `agent_jobs` with `status="pending"`, then the background function updates it through `running` → `done`/`error`. HTMX polls `/equipment/refresh/{job_id}/poll` (or equivalent) to stream status back to the UI. `AgentJob.agent_log` stores a JSON list of event dicts. `AgentJob.prospects_created` is overloaded for the equipment refresh job to store `units_updated`.

### AppSetting

Key-value config persisted in SQLite (`app_settings` table). Currently used to remember `search_provider` (duckduckgo vs tavily) between equipment refresh runs. Accessed via `_get_setting` / `_set_setting` helpers in routers.

### Templates

`app/views.py` creates the single shared `Jinja2Templates` instance and registers a `fromjson` filter. All routers import `templates` from there. Templates live in `app/templates/<module>/`.

## Site Layout

| URL prefix | Module | Auth |
|---|---|---|
| `/` | Public landing page | None |
| `/login`, `/auth/*` | Google OAuth flow | None |
| `/chatbot/*` | Customer-facing chatbot | None |
| `/dashboard` | Summary dashboard | Required |
| `/equipment/` | Equipment Catalog + AI spec refresh | Required |
| `/research/` | Research task board | Required |
| `/financial/` | Pro-forma P&L calculator | Required |
| `/locations/` | Locations & machine assignment | Required |
| `/sales/` | Sales pipeline (Kanban) | Required |
| `/inventory/` | Product catalog + restock log | Required |
| `/sync/` | Google Sheets push/pull | Required |
| `/leads/` | AI lead generation + email outreach | Required |
| `/customer-service/` | CS governance/approval queue | Required |

## Key Config (`.env`)

```ini
DATABASE_URL=sqlite:///./smart_vend.db
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
GMAIL_USER=primemicromarkets@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SESSION_SECRET_KEY=...
ALLOWED_EMAILS=comma,separated,list
GOOGLE_SHEETS_CREDS_FILE=./secrets/service_account.json
SPREADSHEET_ID=...
```

Google Sheets sync needs `secrets/service_account.json` (gitignored). The app starts without any API keys set — AI features return errors until configured.

## Database Notes

- SQLite file: `smart_vend.db` (gitignored)
- Tests use in-memory SQLite with mocked Sheets calls — no credentials needed
- Schema changes require an Alembic migration; `create_all` only adds missing tables, does not alter columns
