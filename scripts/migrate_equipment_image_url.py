"""Add image_url column to equipment_units table.

Run once:  python scripts/migrate_equipment_image_url.py
Safe to run multiple times — skips if column already exists.
"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "smart_vend.db"

conn = sqlite3.connect(str(db_path))
try:
    conn.execute("ALTER TABLE equipment_units ADD COLUMN image_url VARCHAR(500)")
    conn.commit()
    print("Added image_url column to equipment_units")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("Column image_url already exists — skipping")
    else:
        raise
finally:
    conn.close()
