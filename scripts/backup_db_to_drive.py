"""Write a consistent snapshot of the live SQLite database into a Google Drive
backup folder.

The live database lives on a local disk (off Google Drive) because SQLite cannot
lock reliably on Drive's virtual filesystem. This script uses SQLite's
``VACUUM INTO`` to produce a single, fully-consistent copy that is safe to store
on Drive (it is a static file — nothing keeps it open, so no locking is needed).

Usage:
    python scripts/backup_db_to_drive.py
    python scripts/backup_db_to_drive.py --dest "D:/some/other/folder" --keep 14

Run it on a schedule (e.g. Windows Task Scheduler) for automatic off-site backups.
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402

DEFAULT_KEEP = 30
DEFAULT_DEST = PROJECT_ROOT / "backups"


def _sqlite_path_from_url(url: str) -> Path:
    """Turn a SQLAlchemy sqlite URL into a filesystem Path."""
    if not url.startswith("sqlite"):
        raise SystemExit(f"DATABASE_URL is not SQLite, cannot back up: {url!r}")
    # sqlite:///relative/path  or  sqlite:///C:/abs/path
    raw = url.split("///", 1)[1] if "///" in url else url.split("//", 1)[1]
    p = Path(raw)
    if not p.is_absolute():
        p = (PROJECT_ROOT / raw).resolve()
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=str(DEFAULT_DEST),
                        help=f"Backup folder (default: {DEFAULT_DEST})")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"Number of recent backups to retain (default: {DEFAULT_KEEP})")
    args = parser.parse_args()

    src = _sqlite_path_from_url(settings.database_url)
    if not src.exists():
        raise SystemExit(f"Source database not found: {src}")

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = dest_dir / f"smart_vend_{stamp}.db"

    # VACUUM INTO writes a consistent snapshot, including any WAL contents.
    con = sqlite3.connect(str(src))
    try:
        con.execute("VACUUM INTO ?", (str(out_file),))
    finally:
        con.close()

    size_kb = out_file.stat().st_size / 1024
    print(f"Backup written: {out_file}  ({size_kb:.0f} KB)")

    # Retention: keep only the most recent --keep snapshots.
    snaps = sorted(dest_dir.glob("smart_vend_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in snaps[args.keep:]:
        old.unlink()
        print(f"Pruned old backup: {old.name}")


if __name__ == "__main__":
    main()
