"""Smoke del API FastAPI (sin autenticacion)."""

from fastapi.testclient import TestClient

from app.main import API_BUILD_ID, app


def test_health_returns_ok_envelope():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["build_id"] == API_BUILD_ID


def test_openapi_schema_available():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema.get("openapi", "").startswith("3.")
    assert "/health" in schema.get("paths", {})
