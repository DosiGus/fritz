from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.models import ApiRequestLog, AuditEvent, Base, FoodAlias, NutritionItem
from app.db.repositories.audit_events import AuditEventRepository
from app.db.session import get_db
from app.main import app


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

    monkeypatch.setattr(settings, "admin_token", "secret-token")
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    return client, session


def _auth_headers() -> dict:
    return {"X-Admin-Token": "secret-token"}


def test_admin_routes_require_token(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        assert client.get("/admin/stats").status_code == 401
        assert client.get("/admin/stats", headers=_auth_headers()).status_code == 200
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_admin_sentry_test_requires_dsn_and_audits(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        monkeypatch.setattr(settings, "sentry_dsn", "https://example@sentry.local/1")
        monkeypatch.setattr("app.api.routes_admin.sentry_sdk.capture_message", lambda *args, **kwargs: "event-123")

        response = client.post("/admin/sentry-test", headers=_auth_headers())

        assert response.status_code == 200
        assert response.json() == {"sent": True, "event_id": "event-123"}
        event = session.query(AuditEvent).filter(AuditEvent.event_type == "admin_action").one()
        assert event.payload["action"] == "sentry_test_sent"
        assert event.payload["sentry_event_id"] == "event-123"
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_admin_action_writes_audit_event(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        response = client.post(
            "/admin/food-aliases",
            headers=_auth_headers(),
            json={"alias": "magerquark", "canonical_name": "Quark"},
        )
        assert response.status_code == 200

        event = session.query(AuditEvent).filter(AuditEvent.event_type == "admin_action").one()
        assert event.payload["action"] == "food_alias_created"
        assert event.payload["alias"] == "magerquark"
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_admin_error_endpoints_return_persisted_errors(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        session.add(
            ApiRequestLog(
                service="open_food_facts",
                endpoint="/cgi/search.pl",
                method="GET",
                success=False,
                status_code=500,
                error="boom",
            )
        )
        AuditEventRepository(session).create(event_type="llm_parse_error", payload={"reason": "invalid_json"})
        AuditEventRepository(session).create(event_type="voice_transcription_empty", payload={"file_id": "abc"})
        session.commit()

        api_errors = client.get("/admin/api-errors", headers=_auth_headers()).json()
        llm_errors = client.get("/admin/llm-errors", headers=_auth_headers()).json()
        voice_errors = client.get("/admin/voice-errors", headers=_auth_headers()).json()

        assert api_errors[0]["service"] == "open_food_facts"
        assert llm_errors[0]["event_type"] == "llm_parse_error"
        assert voice_errors[0]["event_type"] == "voice_transcription_empty"
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_nutrition_review_can_be_resolved_with_item_and_alias(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        review = AuditEventRepository(session).create(
            event_type="nutrition_review_needed",
            payload={"raw_text": "100g Fantasienudel", "items": ["Fantasienudel"]},
        )

        pending = client.get("/admin/nutrition-reviews", headers=_auth_headers()).json()
        assert len(pending) == 1
        assert pending[0]["resolved"] is False

        response = client.post(
            f"/admin/nutrition-reviews/{review.id}/resolve",
            headers=_auth_headers(),
            json={
                "canonical_name": "Fantasienudel",
                "alias": "fantasienudel",
                "kcal_100g": 123,
                "protein_100g": 4,
                "carbs_100g": 20,
                "fat_100g": 2,
                "note": "Added from beta review",
            },
        )

        assert response.status_code == 200
        assert response.json()["resolved"] is True
        assert session.query(NutritionItem).filter(NutritionItem.canonical_name == "Fantasienudel").one()

        pending_after = client.get("/admin/nutrition-reviews", headers=_auth_headers()).json()
        assert pending_after == []
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_nutrition_review_resolution_defaults_alias_from_review_payload(monkeypatch):
    client, session = _client(monkeypatch)
    try:
        review = AuditEventRepository(session).create(
            event_type="nutrition_review_needed",
            payload={"raw_text": "100g Fantasienudel", "items": ["Fantasienudel"]},
        )

        response = client.post(
            f"/admin/nutrition-reviews/{review.id}/resolve",
            headers=_auth_headers(),
            json={
                "canonical_name": "Fantasienudel",
                "kcal_100g": 123,
                "protein_100g": 4,
                "carbs_100g": 20,
                "fat_100g": 2,
            },
        )

        assert response.status_code == 200
        alias = session.query(FoodAlias).filter(FoodAlias.alias == "fantasienudel").one()
        assert alias.canonical_name == "Fantasienudel"
    finally:
        session.close()
        app.dependency_overrides.clear()
