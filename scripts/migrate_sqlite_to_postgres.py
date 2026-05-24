"""One-time data migration: copy all rows from the local SQLite DB into Postgres.

Phase 2 of RENDER_DEPLOYMENT_PLAN.md. This copies DATA ONLY — the target schema
must already exist, which it does after the first successful deploy (the preDeploy
step `scripts/init_db.py` builds it). Tables are copied parent-first (FK-safe),
Postgres identity sequences are
then reset to MAX(pk) so the app's next INSERT can't collide with copied keys, and
finally per-table row counts are verified source-vs-target.

The live data is tiny (hundreds of KB), so this runs in seconds.

Usage (PowerShell) — pass BOTH URLs explicitly to avoid any ambiguity:

    # 0. Make sure the Postgres driver is installed locally:
    pip install -r requirements.txt

    # 1. The schema is created by the first successful deploy (preDeploy runs
    #    scripts/init_db.py) — no manual schema step. Just confirm the deploy is
    #    green, then copy. Use --replace: the deployed app auto-seeds a governance
    #    rule on first start, so the target isn't empty and --replace gives a
    #    clean truncate-then-copy:
    python scripts/migrate_sqlite_to_postgres.py `
        --source "sqlite:///C:/Users/steve/smart_vend_data/smart_vend.db" `
        --target "<render EXTERNAL postgres url>" `
        --replace

If --source is omitted it falls back to the app's configured DATABASE_URL; the
script hard-stops if that doesn't resolve to SQLite (guards against a stray
$env:DATABASE_URL pointing the source at Postgres). --target falls back to
$TARGET_DATABASE_URL. Without --replace, the script refuses a non-empty target
(use --force to append instead of replace).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import (  # noqa: E402
    create_engine,
    func,
    insert,
    inspect,
    make_url,
    select,
    text,
)
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.schema import Table  # noqa: E402

# Register every model so Base.metadata holds all tables. app.models does not
# re-export crm / settings (they're side-effect imports in main.py), so add them.
import app.models  # noqa: E402, F401
import app.models.crm  # noqa: E402, F401
import app.models.settings  # noqa: E402, F401
from app.config import settings  # noqa: E402
from app.database import Base, _normalize_db_url  # noqa: E402


def _make_engine(url: str, label: str) -> Engine:
    normalized = _normalize_db_url(url)
    try:
        make_url(normalized)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERROR: invalid {label} URL: {exc}")
    return create_engine(normalized)


def _row_count(engine: Engine, table: Table) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def migrate(source_url: str, target_url: str, replace: bool, force: bool) -> None:
    src = _make_engine(source_url, "source")
    tgt = _make_engine(target_url, "target")

    if src.dialect.name != "sqlite":
        sys.exit(
            f"ERROR: source resolved to {src.dialect.name!r}, not sqlite.\n"
            "Pass --source explicitly (a stray $env:DATABASE_URL may be overriding it), e.g.\n"
            '  --source "sqlite:///C:/Users/steve/smart_vend_data/smart_vend.db"'
        )
    if tgt.dialect.name != "postgresql":
        sys.exit(f"ERROR: target resolved to {tgt.dialect.name!r}, expected postgresql.")

    tables = list(Base.metadata.sorted_tables)  # parent-first → FK-safe inserts

    # Precondition 1: target schema must already exist (built by alembic upgrade head).
    target_table_names = set(inspect(tgt).get_table_names())
    missing = [t.name for t in tables if t.name not in target_table_names]
    if missing:
        sys.exit(
            "ERROR: target is missing tables: "
            + ", ".join(missing)
            + "\nRun `alembic upgrade head` against the target first (see this file's docstring)."
        )

    # Precondition 2: don't silently copy onto a non-empty target. --replace
    # truncates first (recommended for Render — the app auto-seeds a governance
    # rule on first start); --force appends regardless; otherwise refuse.
    if not replace and not force:
        nonempty = [t.name for t in tables if _row_count(tgt, t) > 0]
        if nonempty:
            sys.exit(
                "ERROR: target already contains data in: "
                + ", ".join(nonempty)
                + "\nUse --replace to truncate-then-copy (recommended for a one-time migration),"
                + " or --force to append anyway."
            )

    print(f"Source: {src.url.render_as_string(hide_password=True)}")
    print(f"Target: {tgt.url.render_as_string(hide_password=True)}")
    print(f"Copying {len(tables)} tables (parent-first)...\n")

    total = 0
    with src.connect() as sconn, tgt.begin() as tconn:
        if replace:
            # Trusted identifiers from Base.metadata, not user input. CASCADE +
            # RESTART IDENTITY clears all tables and resets sequences in one go.
            names = ", ".join(f'"{t.name}"' for t in tables)
            print("Truncating target tables (--replace)...\n")
            tconn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))  # noqa: S608
        for table in tables:
            rows = [dict(m) for m in sconn.execute(select(table)).mappings()]
            if rows:
                tconn.execute(insert(table), rows)
            total += len(rows)
            print(f"  {table.name:<28} {len(rows):>6} rows")

        # Reset Postgres serial/identity sequences so the next app INSERT starts
        # past the highest copied primary key. Skip non-serial PKs (no sequence).
        print("\nResetting sequences...")
        for table in tables:
            for col in table.primary_key.columns:
                seq = tconn.execute(
                    text("SELECT pg_get_serial_sequence(:t, :c)"),
                    {"t": table.name, "c": col.name},
                ).scalar()
                if not seq:
                    continue
                # Core expression (not raw SQL) — identifiers can't be bind params anyway.
                max_id = tconn.execute(select(func.max(col))).scalar()
                if max_id:
                    tconn.execute(
                        text("SELECT setval(:seq, :val, true)"),
                        {"seq": seq, "val": max_id},
                    )
                    print(f"  {seq} -> {max_id}")

    # Verify row counts match per table.
    print("\nVerifying row counts...")
    mismatches = 0
    for table in tables:
        s_count = _row_count(src, table)
        t_count = _row_count(tgt, table)
        flag = "" if s_count == t_count else "   <-- MISMATCH"
        if s_count != t_count:
            mismatches += 1
        print(f"  {table.name:<28} src={s_count:>6}  tgt={t_count:>6}{flag}")

    print(f"\nCopied {total} rows across {len(tables)} tables.")
    if mismatches:
        sys.exit(f"ERROR: {mismatches} table(s) have mismatched counts — review above.")
    print("All row counts match. Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy SQLite data into Postgres (Phase 2 of the Render migration)."
    )
    parser.add_argument(
        "--source",
        default=settings.database_url,
        help="Source SQLAlchemy URL (default: the app's configured DATABASE_URL / local SQLite).",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("TARGET_DATABASE_URL"),
        help="Target Postgres URL (default: $TARGET_DATABASE_URL).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate target tables before copying (recommended one-time migration).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Append even if the target already contains data (may duplicate rows).",
    )
    args = parser.parse_args()

    if not args.target:
        sys.exit("ERROR: provide --target <postgres url> or set $TARGET_DATABASE_URL.")

    migrate(args.source, args.target, args.replace, args.force)


if __name__ == "__main__":
    main()
