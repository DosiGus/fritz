from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app


class _RedisOk:
    def ping(self):
        return True

    def close(self):
        return None


def _client(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def override_db():
        try:
            yield session
        finally:
            pass

    monkeypatch.setattr("app.api.routes_health.redis.from_url", lambda _url: _RedisOk())
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), session


def test_health_is_liveness_only():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_checks_database_and_redis(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "checks": {"database": True, "redis": True}}
    finally:
        session.close()
        app.dependency_overrides.clear()
