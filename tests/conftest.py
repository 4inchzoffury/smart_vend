import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all models with Base before create_all
from app.database import Base, get_db
from app.main import app
from app.services.auth import require_user


@pytest.fixture
def db():
    # StaticPool forces all connections to share one SQLite in-memory database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    # Protected routes depend on require_user, which 307-redirects to /login when
    # there's no session. Inject a stub user so the internal app is reachable in tests.
    app.dependency_overrides[require_user] = lambda: {
        "email": "test@example.com",
        "name": "Test User",
    }
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
