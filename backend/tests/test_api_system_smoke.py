"""Smoke del sistema API: rutas públicas, protección y OpenAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import API_BUILD_ID, app


@pytest.fixture
def client():
    return TestClient(app)


def test_public_health_and_docs(client):
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["build_id"] == API_BUILD_ID

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    schema = openapi.json()
    assert schema.get("openapi", "").startswith("3.")
    paths = schema.get("paths", {})
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths or "/auth/login" in paths


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/crud/warehouses",
        "/api/v1/crud/appointment-franjas?warehouse_id=1",
        "/api/v1/appointments/unload-teams?warehouse_id=1",
        "/api/v1/crud/profile/me",
    ],
)
def test_protected_routes_require_auth(client, path):
    response = client.get(path)
    assert response.status_code in (401, 403), f"{path} -> {response.status_code}"


def test_login_invalid_credentials(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "no-existe@ferragro.com", "password": "wrong-password-xyz"},
    )
    assert response.status_code in (401, 400, 422)


def test_openapi_lists_core_appointment_paths(client):
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    keys = "".join(paths.keys())
    assert "available-slots" in keys
    assert "unload-teams" in keys
    assert "appointment-franjas" in keys
    assert "appointment-franjas/fecha/resumen" in keys
