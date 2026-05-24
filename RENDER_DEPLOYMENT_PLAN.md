# Hosting & Deployment Plan — Prime Micro Markets (`smart_vend`)

**Status:** Plan / decision record. No code changes made yet.
**Date:** 2026-05-21
**Decision:** Host on **Render** with **managed Postgres**. Domain: `primemicromarkets.com`.

---

## 1. Decision summary

| Question | Answer | Why |
|---|---|---|
| Where to host? | **Render** (web service + managed Postgres) | Best fit for "Claude manages it directly" (official MCP server + REST API), real managed database, predictable cost, deploys from the existing GitHub repo. |
| Is a DB setup needed? | **Yes — migrate SQLite → managed Postgres** | A business storing leads + CRM data needs automated backups and a path to scale. SQLite-on-disk has neither. |
| What powers the public chatbot? | **Groq free tier (`llama-3.1-8b-instant`), Claude Haiku fallback** | $0 for client traffic, ~5–10x faster than Haiku, and Groq does **not** train on inputs/outputs. Claude is used only for rare overflow. See §4a. |
| Estimated cost | **~$14/month** | $7 Starter web (always-on) + $7 managed Postgres. Public chatbot LLM adds $0 (Groq free tier). Free *web* tier rejected — it spins down after 15 min idle and would break OAuth sessions + in-flight background jobs. |

---

## 2. Why NOT Wix / GoDaddy / WordPress

These were the examples in the original ask, so to be explicit about why they're ruled out:

- `smart_vend` is a **FastAPI (Python ASGI) application**, not a website. It needs to run Python, hold persistent database connections, and run server-side background jobs.
- Wix and GoDaddy Website Builder host **static/managed sites** — no arbitrary Python runtime, no relational DB you control, no background workers.
- WordPress is **PHP + MySQL** for content management. Re-platforming this app onto WordPress would mean throwing the app away and rebuilding a fraction of it as plugins.
- None of them give an AI agent (Claude) a clean way to deploy code, run migrations, read logs, or query the database. They're a dead end for this codebase.

**Conclusion:** the choice is among *application* platforms (Render / Fly.io / Railway), not website builders.

---

## 3. Why Render over Fly.io and Railway

The deciding constraint was **"Claude can act directly to help manage it."**

| Capability | Render | Fly.io | Railway |
|---|---|---|---|
| Official MCP server for AI-agent management | ✅ Yes (`render.com/docs/mcp-server`) | ❌ | ❌ |
| Stable API key for scripted/CLI management (no browser-only login) | ✅ `RENDER_API_KEY` | ✅ `FLY_API_TOKEN` | ⚠️ token works but DX is dashboard-leaning |
| Truly **managed** Postgres (automated backups, no babysitting) | ✅ | ✅ (newer offering) | ✅ |
| Infra-as-code in the repo | ✅ `render.yaml` | ✅ `fly.toml` (+ Dockerfile required) | ⚠️ partial |
| Predictable flat monthly cost | ✅ | ⚠️ usage-metered | ⚠️ usage-metered |
| Simplicity for a non-DevOps business owner | ✅ Heroku-style | ⚠️ infra-level control | ✅ |

- **Fly.io** is the cheapest and most CLI-scriptable, with global edge — but it requires a Dockerfile and more hands-on infra control. Best if cost/edge ever dominate.
- **Railway** has the fastest push-to-deploy and auto-detects Python — but usage-based billing is harder to budget for a small business.

Render wins on the combination that matters here: **agent-manageable + managed DB + predictable cost + low operational burden.**

---

## 4. Target architecture on Render

```
                 primemicromarkets.com (DNS → Render, free TLS)
                              │
                   ┌──────────▼───────────┐
                   │  Render Web Service   │  Starter, always-on
                   │  FastAPI + Uvicorn    │
                   │  - public landing     │
                   │  - chatbot (public)   │
                   │  - internal app (OAuth)│
                   │  - BackgroundTasks     │  (in-process AI jobs)
                   └──────────┬───────────┘
                              │ DATABASE_URL (internal)
                   ┌──────────▼───────────┐
                   │ Render Managed Postgres│  daily backups
                   └───────────────────────┘

   Images: persistent disk mount OR Cloudflare R2 (decision pending — §7)
   Secrets: Render env vars (Anthropic, Tavily, Firecrawl, Gmail, Google OAuth, …)
   Config:  render.yaml blueprint committed to the repo
```

- Single web service serves both the public site (`/`, `/chatbot/*`) and the OAuth-protected internal app — same as today.
- Render's proxy provides TLS and sets `X-Forwarded-Proto`; the existing `ProxyHeadersMiddleware` and `https_only=True` session cookie already handle this correctly (no change needed there).
- Background AI jobs use request-scoped `BackgroundTasks` that run inside the web process — fine on an always-on Starter instance. **No separate worker service is required yet.**

---

## 4a. Public chatbot model — zero marginal cost

**Problem.** The public chatbot widget (`/chatbot/*`) is the one AI surface exposed to anonymous
visitors, so its traffic is unbounded and uncontrolled. Defaulting it to Anthropic Claude bills per
token on **every visitor message** — an open-ended cost on a public page.

**Why not self-host the model on Render.** The Starter web service (~0.5 CPU / 512 MB, §8) cannot run a
local LLM (Ollama) — a 3B+ model needs several GB of RAM and, on CPU, generates only a few tokens/sec
(*slower*, not faster). An instance large enough — or a GPU instance — costs **more per month than the
hosted API ever would**. Self-hosting on Render loses on both cost and speed.

**Decision.** Power the public chatbot with **Groq's free tier running `llama-3.1-8b-instant`**, with an
**Anthropic Claude Haiku fallback** for reliability. Researched May 2026:

| Option | $0 at our volume? | Speed vs Haiku | Privacy | Tool-calling | Verdict |
|---|---|---|---|---|---|
| **Groq free** (`llama-3.1-8b-instant`) | ✅ 14,400 req/day, 30 RPM | ✅ ~5–10x | ✅ Groq does **not** train on I/O; not retained by default | ✅ 128K ctx, tool use + JSON mode | **Chosen** |
| Gemini free (`gemini-2.0-flash`) | ✅ but ~1,000–1,500 req/day | ✅ ~3–5x | ❌ Google **uses free-tier data for training** (bad for lead-capture PII) | ✅ | Rejected (privacy; model **retired 2026-03-03**) |
| Local Ollama + Cloudflare Tunnel | ✅ (own PC) | ❌ CPU 3B is *slower* | ✅ fully private | ⚠️ unreliable on 3B | Rejected (fragile, slow, PC must stay on) |

- **Privacy.** The widget captures visitor names/emails (lead capture → sales pipeline), so a provider
  that trains on inputs is a non-starter. Groq contractually does not train on inputs/outputs and does
  not retain inference by default — Gemini's free tier does the opposite.
- **Free-tier headroom.** 14,400 requests/day / 30 RPM is far above a single widget's expected volume.
- **Reliability fallback.** If Groq 429s, is missing its key during cutover, or has an outage,
  `get_chatbot_reply` automatically falls back to Claude Haiku so the widget never goes dark — only rare
  overflow reaches the paid API. (`app/services/cs_chatbot_agent.py`, `_dispatch` + fallback.)
- **Scope.** This applies **only** to the public chatbot (the sole caller of `get_active_provider`). All
  internal/admin AI — lead gen, equipment specs, inventory, CS-manager drafting, Gmail monitor, price
  comparator — calls `anthropic.Anthropic(...)` directly and stays on Claude: low-volume, quality-
  sensitive, and staff-controlled.

---

## 5. Migration plan — phased

> Code changes are deferred. This section describes *what* will change so the work is scoped and reviewable later.

### Phase 1 — Make the app cloud-ready (on a feature branch)
1. **Add Postgres driver** — `psycopg[binary]` in `requirements.txt`.
2. **Make `app/database.py` engine config conditional.** The current `connect_args={"check_same_thread": False, "timeout": 30}` and the `PRAGMA journal_mode=WAL` listener are **SQLite-only** and will error on Postgres. Branch on the URL scheme so SQLite keeps its args locally while Postgres gets clean defaults (pool settings, `pool_pre_ping=True`).
3. **Add `render.yaml` blueprint** defining: the web service (build = `pip install -r requirements.txt`, start = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`), the managed Postgres instance, env-var wiring, and the persistent disk (if chosen in §7).
4. **Run migrations on deploy.** Add a release/pre-deploy command `alembic upgrade head`. Migrations already exist under `alembic/versions/`. (Note: `main.py` also calls `Base.metadata.create_all()` on startup, which safely creates any missing tables but does not alter columns — Alembic remains the source of truth.)
5. **Confirm secrets come only from env.** `app/config.py` already reads everything via pydantic-settings, so no `.env` ships to prod — values are set as Render env vars.

### Phase 2 — One-time data migration (SQLite → Postgres)
- Stand up the managed Postgres instance, run `alembic upgrade head` against it to build the schema.
- Export the current `smart_vend.db` data and load it into Postgres (per-table copy via SQLAlchemy, or `pgloader`). The DB is tiny today (~330 KB), so this is quick and low-risk.
- Verify row counts and spot-check CRM/leads/equipment tables.

### Phase 3 — Deploy & wire up
1. Connect the existing GitHub repo (`prime-micro-markets/smart_vend`, company-owned Org) to Render and deploy via the blueprint. Authorize Render against the **`prime-micro-markets`** Org, not a personal account.
2. Set all secrets as Render env vars: **`GROQ_API_KEY` (required — powers the public chatbot; free key from console.groq.com)**, `ANTHROPIC_API_KEY` (required — chatbot fallback + all internal AI), `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `GEMINI_API_KEY`/`OPENAI_API_KEY` (optional, only if used), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET_KEY` (generate a fresh one), `ALLOWED_EMAILS`, `SPREADSHEET_ID`. `DATABASE_URL` is injected by Render from the managed Postgres. The Groq default is set in code (`cs_chatbot_agent.py`); the CS settings UI (`/customer-service` → AI settings, persisted as `cs_ai_provider` / `cs_ai_model` in `AppSetting`) can override per environment.
3. **Google Sheets service account** — `secrets/service_account.json` is gitignored. Provide it on Render as a *secret file* (or base64 env var) and point `GOOGLE_SHEETS_CREDS_FILE` at it.
4. **Update Google OAuth** authorized redirect URIs to the Render URL first (`https://<service>.onrender.com/auth/callback`), then add the custom domain.
5. **Custom domain** — point `primemicromarkets.com` DNS at Render, enable automatic TLS, then finalize OAuth redirect URIs on the custom domain.

### Phase 4 — Hand Claude the keys (ongoing management)
- Configure the **Render MCP server** and/or set `RENDER_API_KEY` so Claude can, going forward: trigger deploys, tail logs, read/set env vars, run `alembic` migrations, and query Postgres on your behalf — directly, without you clicking through the dashboard.
- Add a short "Ops" section to `CLAUDE.md` documenting the common commands.

### Phase 5 — Public-site SEO & crawler hygiene (at / after custom-domain cutover)

> Goal: only the public surface (`/` landing, `/chatbot/*`) should be indexable; the OAuth-protected management app must be kept out of search results. Most of this is small, additive template/route work — the off-site items happen once the real domain is live. This is also what eliminates the scanner/crawler 404 noise currently seen in the console.

**A. `robots.txt` — served from the site root, not `/static/`**
- Crawlers fetch `https://primemicromarkets.com/robots.txt`. Because `StaticFiles` is mounted at `/static` (`app/main.py:67`), a file in `app/static/` would *not* answer that path. Add a dedicated route in `app/routers/public.py` returning `PlainTextResponse`.
- Allow the public pages, disallow the internal prefixes, and point to the sitemap:
  ```
  User-agent: *
  Allow: /$
  Allow: /chatbot/
  Disallow: /dashboard
  Disallow: /research/
  Disallow: /financial/
  Disallow: /locations/
  Disallow: /sales/
  Disallow: /crm/
  Disallow: /inventory/
  Disallow: /leads/
  Disallow: /equipment/
  Disallow: /customer-service/
  Disallow: /settings/
  Disallow: /sync/
  Disallow: /auth/
  Sitemap: https://primemicromarkets.com/sitemap.xml
  ```
- `robots.txt` only guides *crawling*, not *indexing* — pair it with the hard `noindex` in (D).

**B. `sitemap.xml`**
- Add a `/sitemap.xml` root route (XML response) listing public URLs — currently just the landing page; extend as public sub-pages are added. Generating it from a route keeps it in sync with code instead of going stale as a committed file.
- Referenced by `robots.txt` (A) and submitted in Search Console (F).

**C. Strengthen landing-page metadata (`app/templates/public/landing.html`)**
The page already has a strong `<title>` and `<meta name="description">`. Add to its `<head>`:
- `<link rel="canonical" href="https://primemicromarkets.com/">` — stops the `*.onrender.com` URL and www / non-www variants from competing as duplicate content.
- **Open Graph + Twitter Card** tags (`og:title`, `og:description`, `og:image`, `og:url`, `og:type=website`, `twitter:card=summary_large_image`) so shared links render a rich preview in iMessage / LinkedIn / Facebook / X. Needs a ~1200×630 social image (logo on a branded background, or a hero photo) added under `app/static/images/`.
- **Favicon / touch icons** generated from the existing `primeMM_Logo.png`.

**D. Keep the internal app out of the index (`app/templates/base.html`)**
- Add `<meta name="robots" content="noindex, nofollow">` to `base.html`'s `<head>`. The app is behind OAuth, but the login screen and error pages can still be crawled — this guarantees none of it surfaces and avoids advertising internal paths. Note the landing page is a *standalone* template (it does **not** extend `base.html`), so it stays fully indexable — exactly the split we want.

**E. Local-business structured data (JSON-LD) on the landing page**
- Embed a `LocalBusiness` JSON-LD block: business name, area served (Panama City, FL + surrounding), telephone, email (`primemicromarkets@gmail.com`), URL, logo, founder, and `sameAs` social links. High value for local search and lets Google render the business with rich detail. Veteran-owned status has no standard schema field — surface it in the description copy and (more importantly) on the Google Business Profile (F).

**F. Off-site launch tasks (after DNS cutover — no code)**
- **Google Search Console** — verify the domain (DNS TXT record, do it alongside the Render DNS step in Phase 3), submit `sitemap.xml`, then confirm the public page is indexed and the internal app is *not*.
- **Bing Webmaster Tools** — optional, can import the Search Console config.
- **Google Business Profile** — the single biggest local-SEO lever for a Panama City service business. Create/claim the listing, mark it **Veteran-Owned**, set the service area, hours, and photos, and link the site.
- **Canonical host redirect** — in Render, pick one canonical host (apex `primemicromarkets.com` vs `www`) and 301-redirect the other so a single host is indexed. Pairs with the custom-domain step in Phase 3.
- Optional: lightweight analytics (Plausible or GA4) to measure traffic once indexed.

---

## 6. Codebase-specific gotchas (caught during review)

- **SQLite-only engine args** in `app/database.py` (`check_same_thread`, WAL pragma) **must be guarded** before Postgres will connect. This is the single most important code change.
- **`https_only=True` session cookie + `ProxyHeadersMiddleware`** in `app/main.py` are already correct for running behind Render's TLS proxy — no change. (They were added for the Cloudflare Tunnel and carry over cleanly.)
- **`SessionMiddleware` added last** (outermost) — keep this ordering; it's already correct.
- **`app/models/settings.py` side-effect import** in `main.py` must stay so `AppSetting` registers before `create_all` — unchanged.
- **Background jobs** are request-scoped `BackgroundTasks`, not a daemon → always-on web instance is sufficient; free/spin-down tier would kill in-flight jobs and the HTMX status-polling UX.
- **WAL mode** is irrelevant under Postgres; the listener simply won't run for the Postgres engine.
- **`robots.txt` / `sitemap.xml` must be served from the site root**, but `StaticFiles` is mounted at `/static` (`app/main.py:67`) — so they need dedicated root routes in `app/routers/public.py`, not files dropped in `app/static/`. (Handled in Phase 5.)

---

## 7. Open decisions (resolve before Phase 1 code work)

1. **Image storage.** Committed brand images deploy with the code automatically. For *runtime-uploaded* images (e.g. equipment photo uploads via the equipment router), pick one:
   - **Persistent disk** mounted on the web service — simplest, +$0.25/GB/mo. Caveat: ties the service to a single instance (fine for now).
   - **Cloudflare R2 / object storage** — cleaner long-term, survives instance changes, slightly more code. Recommended if uploads will grow.
2. **Scheduled Gmail monitoring.** If you later want the inbox polled on a schedule (vs. on-demand), add a **Render Cron Job** rather than a long-lived loop in the web process.
3. **Staging environment.** Optional second Render service from a `staging` branch for safe testing before production deploys.

**Resolved:** *Public chatbot model cost* — decided in favor of the **Groq free tier** (`llama-3.1-8b-instant`)
with a Claude Haiku fallback; see §4a. Self-hosting a model on Render was rejected on cost + speed grounds.

---

## 8. Cost estimate

| Item | Plan | Monthly |
|---|---|---|
| Web service | Starter (always-on) | ~$7 |
| Managed Postgres | Basic (256 MB) | ~$7 |
| Public chatbot LLM | Groq free tier | $0 |
| Persistent disk (if chosen) | per GB | +$0.25/GB |
| Custom domain + TLS | included | $0 |
| **Total** | | **~$14/mo** |

> Public chatbot client traffic is $0 (Groq free tier). The Claude Haiku fallback only fires on rare Groq
> overflow/outage, so its cost is negligible. Internal/admin AI Claude usage is unchanged and low-volume.

---

## 9. Rollback / safety net

- The current **Cloudflare Tunnel + local** setup remains fully functional and is the fallback during cutover — nothing is removed until Render is verified.
- DNS cutover for `primemicromarkets.com` is the last step and is reversible.
- Keep the exported `smart_vend.db` snapshot until Postgres is verified in production.

---

## 10. Next action

When you're ready to execute, the first concrete step is **Phase 1** on a feature branch (Postgres driver + conditional engine config + `render.yaml`). Nothing in this plan has been applied to the code yet.
