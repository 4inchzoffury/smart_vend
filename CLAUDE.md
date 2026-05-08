# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`smart_vend` is the internal management platform for Prime Vending, a veteran-owned smart cooler vending business (51% Stephen Russell Troup, veteran; 49% John Michael Johnson) based in Panama City, FL. The company is pursuing VOB (Veteran-Owned Business) certification.

## Tooling (inferred from .gitignore)

- **Linter/formatter:** Ruff (`ruff check .` / `ruff format .`)
- **Tests:** pytest (`pytest` to run all; `pytest path/to/test_file.py::test_name` for a single test)
- **Virtual environment:** `.venv` (standard `python -m venv .venv` or `uv venv`)

## Web Framework

FastAPI + Jinja2 templates + Bootstrap 5 + HTMX. Run the dev server with:

```bash
uvicorn app.main:app --reload
```

## Notes

- Database: SQLite via SQLAlchemy 2.0 (sync). File: `smart_vend.db` (gitignored).
- Google Sheets creds go in `secrets/service_account.json` (gitignored). Copy `.env.example` → `.env` and fill in.
- Seed research tasks: `python scripts/seed_research_tasks.py "<path_to_Research_Tracker.md>"`
- Streamlit secrets go in `.streamlit/secrets.toml` (already gitignored).
