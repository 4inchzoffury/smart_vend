"""Database bootstrap for deploys (Render preDeploy command).

Why this exists: the app's schema is created by SQLAlchemy `create_all` (see the
`app/main.py` lifespan), while Alembic only carries *incremental* changes. The
Alembic chain alone CANNOT build the schema from an empty database — the initial
migration is an empty baseline, and later migrations assume the create_all-managed
base tables already exist (e.g. `agent_jobs` has a foreign key to `prospects`).
SQLite tolerates that ordering; Postgres does not. So bootstrap explicitly:

  * Empty database   -> `create_all` builds the full current schema, then stamp
                        Alembic at head so a later `upgrade head` runs only NEW
                        migrations (and never re-creates what create_all made).
  * Existing schema  -> run `alembic upgrade head` to apply any pending migrations
                        before the app starts.

This runs before the web process (and its lifespan create_all), so on the very
first deploy it builds everything, and on later deploys it applies migrations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

# Register every model so create_all sees the full schema (app.models omits these).
import app.models  # noqa: E402, F401
import app.models.crm  # noqa: E402, F401
import app.models.settings  # noqa: E402, F401
from app.database import Base, engine  # noqa: E402


def main() -> None:
    existing = set(inspect(engine).get_table_names())
    app_tables = {t.name for t in Base.metadata.sorted_tables}
    present = app_tables & existing
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))

    if present:
        print(f"Existing schema detected ({len(present)} app tables) — alembic upgrade head.")
        command.upgrade(cfg, "head")
    else:
        print("Empty database — building schema via create_all, then stamping alembic at head.")
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
    print("Database bootstrap complete.")


if __name__ == "__main__":
    main()
