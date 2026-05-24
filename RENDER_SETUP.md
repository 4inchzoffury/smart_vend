# Render Setup Runbook — `smart_vend`

Operational steps to take `smart_vend` live on Render. This is the **Phase 3** "do it
in the dashboard" companion to the decision record in `RENDER_DEPLOYMENT_PLAN.md`.
The deployable blueprint (`render.yaml`) is already on `main`.

> Legend: 🖱️ = dashboard click-work (yours) · 💻 = a command you run locally.

---

## 0. Prerequisites

- The repo is on the company Org: `github.com/prime-micro-markets/smart_vend`, branch **`main`** (done).
- A **Render account**. Sign up / log in at <https://render.com> using the company Gmail
  (`primemicromarkets@gmail.com`) so the account, like the repo, is company-owned.
- The secret values from your local `.env` handy (see the checklist in §3).

---

## 1. 🖱️ Connect Render to the GitHub Org

1. Render dashboard → **New** → **Blueprint**.
2. When prompted to connect a Git provider, choose **GitHub** and authorize the **Render GitHub app**
   against the **`prime-micro-markets`** organization (not your personal account).
3. Grant it access to the **`smart_vend`** repository.

## 2. 🖱️ Create resources from the blueprint

1. Select the **`smart_vend`** repo. Render reads `render.yaml` and shows two resources to create:
   - **`smart-vend`** — the web service (Starter, always-on)
   - **`smart-vend-db`** — managed Postgres (`basic-256mb`, region `virginia`)
2. Render will prompt for the env vars marked `sync: false`. Fill them per §3, then **Apply**.

---

## 3. Secret values checklist

`DATABASE_URL` (from the DB) and `SESSION_SECRET_KEY` (auto-generated) are handled by the blueprint —
**leave those alone**. Enter the rest at blueprint creation:

| Env var | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | `gsk_…` | **Required.** Free key from <https://console.groq.com> — powers the public chatbot. |
| `ANTHROPIC_API_KEY` | `sk-ant-…` | **Required.** Chatbot fallback + all internal AI. |
| `TAVILY_API_KEY` | `tvly-…` | Lead research / web search. |
| `GOOGLE_CLIENT_ID` | `…apps.googleusercontent.com` | Staff Google OAuth. |
| `GOOGLE_CLIENT_SECRET` | `GOCSPX-…` | Staff Google OAuth. |
| `ALLOWED_EMAILS` | `you@gmail.com,john@gmail.com` | Comma-separated staff Gmails allowed into the internal app. |
| `GMAIL_USER` | `primemicromarkets@gmail.com` | Outbound email + inbox monitor. |
| `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Gmail **app password**, not the account password. |
| `SPREADSHEET_ID` | the Sheet ID | For Google Sheets sync (pairs with the secret file in §5). |
| `FIRECRAWL_API_KEY` | optional | Leave blank if unused (falls back to BeautifulSoup). |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | optional | Leave blank unless used. |
| `CALENDLY_URL` / `CALENDLY_API_KEY` | optional | Leave blank unless used. |
| `GOOGLE_SHEETS_CREDS_FILE` | *(pre-set)* | Already `/etc/secrets/service_account.json` in the blueprint — see §5. |

> The app starts fine with optional keys blank; those features just return errors until configured.

---

## 4. 🖱️ First deploy

1. Render provisions Postgres, then builds the web service:
   - **build:** `pip install -r requirements.txt`
   - **preDeploy:** `python scripts/init_db.py` — on an empty DB it builds the full schema via
     `create_all` and stamps Alembic at head; on later deploys it runs `alembic upgrade head`.
     (Plain `alembic upgrade head` can't build from scratch — the initial migration is empty.)
   - **start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Open the service **Logs** and confirm it boots and the health check on `/` passes.
3. Note the public URL: **`https://smart-vend-kj32.onrender.com`** (your exact subdomain may differ).

## 5. 🖱️ Upload the Google service-account secret file

The Sheets credentials are a *file*, gitignored, so they aren't in env vars.

1. Web service → **Settings** → **Secret Files** → **Add Secret File**.
2. **Filename:** `service_account.json` (mounts at `/etc/secrets/service_account.json`, matching
   `GOOGLE_SHEETS_CREDS_FILE`).
3. **Contents:** paste the full contents of your local `secrets/service_account.json`.
4. Save and trigger a redeploy (Sheets sync stays broken until this exists; nothing else is affected).

## 6. 🖱️ Google OAuth redirect URIs

The app builds its `redirect_uri` from the request host, so **every host the app is reached by needs
its own authorized URI** (callback path is `/auth/callback`).

1. Google Cloud Console → **APIs & Services** → **Credentials** → your OAuth 2.0 Client.
2. Under **Authorized redirect URIs**, add the Render URL first:
   - `https://smart-vend-kj32.onrender.com/auth/callback`
3. (After the custom domain is live, §9) also add:
   - `https://primemicromarkets.com/auth/callback`
   - `https://www.primemicromarkets.com/auth/callback`
4. Save. Then test sign-in at `https://smart-vend-kj32.onrender.com/login`.

---

## 7. Phase 2 — migrate the live data (SQLite → Postgres)

The schema already exists from §4's preDeploy, and the app seeds a governance rule on first start, so
the target isn't empty — use **`--replace`** for a clean one-time copy.

1. 🖱️ Render → **`smart-vend-db`** → **Connections** → copy the **External Database URL**
   (`postgresql://…`). The *internal* URL only works from inside Render.
2. 💻 Locally, make sure the Postgres driver is installed: `pip install -r requirements.txt`
3. 💻 Run the migration (the script copies parent-first, resets sequences, and verifies row counts):
   ```powershell
   python scripts/migrate_sqlite_to_postgres.py `
       --source "sqlite:///C:/Users/steve/smart_vend_data/smart_vend.db" `
       --target "<EXTERNAL postgres url>" `
       --replace
   ```
4. Confirm the final output reads **"All row counts match. Migration complete."**

> **TLS caveat (local):** psycopg connects to Postgres over its own libpq SSL, which the local
> HTTPS-intercepting AV/proxy may block (`certificate verify failed`). If that happens, run the
> migration from a network without interception, or from a context Render trusts. The data is tiny,
> so any clean-network run finishes in seconds.

---

## 8. Verify

- Public: `https://smart-vend-kj32.onrender.com/` (landing) and the chatbot widget respond.
- Internal: sign in at `/login`; spot-check `/dashboard`, `/leads`, `/crm` — your migrated rows appear.
- A second deploy (push any commit to `main`) re-runs `alembic upgrade head` as a no-op and keeps data.

## 9. 🖱️ Custom domain (can follow once the above is verified)

1. Web service → **Settings** → **Custom Domains** → add `primemicromarkets.com` (and `www`).
2. Add the DNS records Render shows at your registrar; Render issues TLS automatically.
3. Pick one canonical host and 301-redirect the other (apex vs `www`).
4. Finish the OAuth redirect URIs in §6 for the live domain.
5. Off-site SEO tasks (Search Console, Business Profile) are **Phase 5** in `RENDER_DEPLOYMENT_PLAN.md`.

---

## Rollback / safety net

- The local Cloudflare Tunnel setup remains the fallback during cutover; nothing is torn down until
  Render is verified.
- Keep the `C:\Users\steve\smart_vend_data\smart_vend.db` snapshot until Postgres is confirmed good.
- DNS cutover (§9) is the last, fully reversible step.
