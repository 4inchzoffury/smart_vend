"""Dev helper: create all database tables without running migrations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.models  # noqa: F401 — register all models with Base
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
print("Database tables created.")
