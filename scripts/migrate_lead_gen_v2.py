"""Run once: add lead-gen v2 columns and create app_settings table."""
import pathlib
import sqlite3

db_path = pathlib.Path(__file__).parent.parent / "smart_vend.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

migrations = [
    "ALTER TABLE prospects ADD COLUMN website TEXT",
    "ALTER TABLE prospects ADD COLUMN source_job_id INTEGER",
    "ALTER TABLE prospects ADD COLUMN template_draft_subject TEXT",
    "ALTER TABLE prospects ADD COLUMN template_draft_body TEXT",
    """CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
]

for sql in migrations:
    try:
        cur.execute(sql)
        print(f"OK:   {sql[:70]}")
    except sqlite3.OperationalError as e:
        print(f"SKIP ({e}): {sql[:70]}")

conn.commit()
conn.close()
print("\nMigration complete.")
