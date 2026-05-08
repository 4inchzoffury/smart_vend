# Prime Micro Markets

Internal management platform for Prime Micro Markets, a veteran-owned smart cooler vending business based in Panama City, FL (51% Stephen Russell Troup, veteran; 49% John Michael Johnson). Covers research task tracking, financial modeling, machine/location management, a sales pipeline, inventory, and AI-powered lead generation — all in one FastAPI web app backed by SQLite.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI 0.115 + Uvicorn |
| Database | SQLite + SQLAlchemy 2.0 (sync) + Alembic |
| Templates | Jinja2 + Bootstrap 5.3 |
| Dynamic UI | HTMX 1.9 |
| Config | pydantic-settings + python-dotenv |
| Google Sheets | gspread + google-auth (service account) |
| AI / Lead Gen | Anthropic Claude + Tavily web search |
| Public URL | Cloudflare Tunnel (primemicromarkets.com) |
| Lint / Format | Ruff |
| Tests | pytest |

---

## Prerequisites

- Python 3.12+
- (Optional) A Google service account JSON file for Sheets sync

---

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```ini
DATABASE_URL=sqlite:///./smart_vend.db
GOOGLE_SHEETS_CREDS_FILE=./secrets/service_account.json
SPREADSHEET_ID=your_google_spreadsheet_id_here
DEBUG=false

# AI / Lead generation
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
GMAIL_USER=youremail@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
CALENDLY_URL=https://calendly.com/yourname/30min
```

`DATABASE_URL` and `DEBUG` can be left as-is. `SPREADSHEET_ID` is only needed for Google Sheets sync. The AI lead generation features (`/leads/`) require `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` — the app runs fine without them but agent jobs will return an error until they are set. Gmail keys are only needed to actually send emails; drafting works without them.

### 4. (Optional) Set up Google Sheets sync

1. Create a Google Cloud service account and download the JSON key file.
2. Place the file at `secrets/service_account.json` (this directory is gitignored).
3. Share your Google Spreadsheet with the service account's email address (Editor permission).
4. Set `SPREADSHEET_ID` in `.env` to the ID from your spreadsheet's URL.

---

## Running the app

### Local only

Double-click `start_local.bat` or run:

```bash
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000`. The database tables are created automatically on first run.

### Public (Cloudflare Tunnel)

Double-click `start_public.bat`. This opens the Cloudflare Tunnel in a separate window and starts the app server. The app will be accessible at `https://app.primemicromarkets.com`.

---

## Cloudflare Tunnel setup (one-time)

The tunnel `prime-markets` is already created and routed to `app.primemicromarkets.com`. If you ever need to recreate it on a new machine:

```powershell
# Install the tunnel agent
winget install Cloudflare.cloudflared

# Authenticate (opens browser)
cloudflared tunnel login

# Create the tunnel
cloudflared tunnel create prime-markets

# Point the subdomain at the tunnel
cloudflared tunnel route dns prime-markets app.primemicromarkets.com
```

After setup, `start_public.bat` handles everything with one click.

---

## Seeding research tasks

A one-shot seed script parses the Research Tracker markdown file and inserts tasks into the database. It is idempotent — re-running it skips rows that already exist.

```bash
python scripts/seed_research_tasks.py "path/to/Research_Tracker_Next_Steps_v1.0.md"
```

---

## Modules

| URL | Module | Description |
|---|---|---|
| `/` | Dashboard | Summary cards for all modules |
| `/research/` | Research Tasks | Task board grouped by section; inline status toggle via HTMX |
| `/financial/` | Financial Calculator | Pro-forma P&L scenarios with live HTMX recalculation |
| `/locations/` | Locations & Machines | Location cards with status filter; machine assignment |
| `/sales/` | Sales Pipeline | Kanban board by stage; outreach log per prospect |
| `/inventory/` | Inventory | Product catalog with margin color-coding; restock logging |
| `/sync/` | Google Sheets Sync | Manual push/pull per entity |
| `/leads/` | AI Lead Generation | Claude + Tavily agent finds prospects; drafts and sends cold outreach emails |

---

## Database migrations

Alembic is configured for schema migrations. The initial schema is already stamped.

```bash
# Generate a new migration after changing a model
alembic revision --autogenerate -m "describe the change"

# Apply pending migrations
alembic upgrade head

# Check current revision
alembic current
```

---

## Development

### Run tests

```bash
pytest
```

Tests use an in-memory SQLite database and mock all Google Sheets calls — no credentials required.

### Lint and format

```bash
# Check
ruff check .

# Auto-fix
ruff check . --fix

# Format
ruff format .
```

### Project structure

```
app/
  main.py             # App factory, lifespan, router mounts
  config.py           # Settings (pydantic-settings)
  database.py         # SQLAlchemy engine, session, Base
  models/             # SQLAlchemy ORM models
  routers/            # FastAPI route handlers
  services/
    financial_calc.py # Pure P&L calculation functions
    sheets.py         # Google Sheets push/pull helpers
    agent.py          # Claude agentic loop (research + email draft jobs)
    tavily.py         # Tavily web search wrapper
    email_sender.py   # Gmail SMTP sender
  templates/          # Jinja2 HTML templates
  static/             # CSS and JS assets
alembic/              # Database migrations
scripts/
  seed_research_tasks.py  # One-shot research task importer
tests/                # pytest test suite
secrets/              # Gitignored — put service account JSON here
```
