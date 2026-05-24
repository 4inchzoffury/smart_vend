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
| Chatbot AI | Multi-provider: Claude, Groq, OpenAI, Gemini, or Ollama (local) |
| Public URL | Cloudflare Tunnel (primemicromarkets.com) |
| Lint / Format | Ruff |
| Tests | pytest |

---

## Prerequisites

- Python 3.12+
- (Optional) A Google service account JSON file for Sheets sync
- (Optional) [Ollama](https://ollama.com/download/windows) — for local/free AI inference. Not a Python package; installs system-wide.

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

# AI / Lead generation (required for /leads/ agent jobs)
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
GMAIL_USER=youremail@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GOOGLE_BOOKING_URL=https://calendar.google.com/calendar/appointments/schedules/...

# Additional chatbot AI providers (all optional — chatbot defaults to Anthropic)
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Local AI via Ollama (no API key needed; Ollama must be installed and running)
# Change this in production if Ollama runs on a separate machine/VM
OLLAMA_BASE_URL=http://localhost:11434/v1

# Auth (required for staff login)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SESSION_SECRET_KEY=...            # generate: python -c "import secrets; print(secrets.token_hex(32))"
ALLOWED_EMAILS=comma,separated,list
```

`DATABASE_URL` and `DEBUG` can be left as-is for local development. `SPREADSHEET_ID` is only needed for Google Sheets sync. The AI lead generation features (`/leads/`) require `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`. Gmail keys are only needed to send emails; drafting works without them. All chatbot AI providers are optional — select the active one in Admin → Customer Service → AI Settings.

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

Double-click `start_public.bat`. This opens the Cloudflare Tunnel in a separate window and starts the app server. The app will be accessible at `https://primemicromarkets.com`.

---

## Local AI with Ollama (optional)

The customer-facing chatbot supports **Ollama** as a zero-cost, no-rate-limit local AI provider. Ollama is a standalone Windows/macOS/Linux app — it is NOT a Python package and does NOT go inside the project virtual environment.

### One-time setup

```powershell
# 1. Download and run the installer
#    https://ollama.com/download/windows
#    (Ollama auto-starts on login as a system tray app)

# 2. Pull the recommended model (~2 GB, fast on CPU)
ollama pull llama3.2:3b

# 3. Verify the OpenAI-compatible endpoint is up
curl http://localhost:11434/v1/models
```

### Enabling Ollama in the app

1. Start the app and log in as staff.
2. Navigate to **Customer Service → AI Settings** tab.
3. Select **"Ollama (Local / Free)"** from the Provider dropdown.
4. Pick a model (`llama3.2:3b` is the best choice for CPU-only machines).
5. Click **Save AI Settings**.

The status grid on that page shows a green indicator when Ollama is reachable and red when it is not running. The rate limit is raised to 500 messages/hour for local providers (no API cost).

### Model recommendations

| Model | Size | Best for |
|---|---|---|
| `llama3.2:3b` | ~2 GB | CPU-only machines, fastest response |
| `phi4-mini` | ~2.5 GB | CPU-only, good reasoning |
| `mistral:7b` | ~4 GB | Higher quality, needs ≥16 GB RAM on CPU |

### Cloud deployment

Set `OLLAMA_BASE_URL` in `.env` to point at a cloud-hosted Ollama instance:

```ini
OLLAMA_BASE_URL=http://<your-vm-ip>:11434/v1
```

A GPU VM (e.g. AWS `g4dn.xlarge` with NVIDIA T4) will run `llama3.2:3b` in under 1 second per response. Alternatively, **Groq** (already integrated, free tier, very fast Llama inference) is a simpler cloud option that requires no GPU VM.

---

## Cloud Deployment Checklist

This app currently runs on a single Windows machine via Cloudflare Tunnel. When migrating to a cloud server:

### Database

SQLite works for single-instance deployments. For a managed cloud server switch to PostgreSQL:

```ini
# .env (production)
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_vend
```

Install the adapter: `pip install psycopg2-binary`. Run `alembic upgrade head` on the new DB to apply migrations.

### Environment variables

Set all `.env` values as server environment variables (or use a secrets manager). Never commit `.env` to version control.

Key variables to update for cloud:
- `DATABASE_URL` → PostgreSQL connection string
- `OLLAMA_BASE_URL` → URL of cloud Ollama VM (or remove if using Groq instead)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` → add your cloud domain to Google OAuth authorized redirect URIs
- `SESSION_SECRET_KEY` → generate a fresh value for production
- `ALLOWED_EMAILS` → restrict to staff emails

### Public access

Two options:

**Option A — Keep Cloudflare Tunnel** (simplest, no firewall config needed):
```bash
cloudflared tunnel run prime-markets
```
Install `cloudflared` on the cloud VM and authenticate it once. `start_public.bat` logic translates directly to a Linux systemd service.

**Option B — Direct HTTPS** (nginx or Caddy reverse proxy):
```nginx
server {
    listen 443 ssl;
    server_name primemicromarkets.com;
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

### Process management (Linux)

Replace the `.bat` scripts with a `systemd` service:

```ini
# /etc/systemd/system/smart_vend.service
[Unit]
Description=Prime Micro Markets App
After=network.target

[Service]
WorkingDirectory=/opt/smart_vend
ExecStart=/opt/smart_vend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/opt/smart_vend/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now smart_vend
```

---

## Cloudflare Tunnel setup (one-time)

The tunnel `prime-markets` is already created and routed to `primemicromarkets.com`. If you ever need to recreate it on a new machine:

```powershell
# Install the tunnel agent
winget install Cloudflare.cloudflared

# Authenticate (opens browser)
cloudflared tunnel login

# Create the tunnel
cloudflared tunnel create prime-markets

# Point the subdomain at the tunnel
cloudflared tunnel route dns prime-markets primemicromarkets.com
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
