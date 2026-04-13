from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_phase_a_metadata() -> None:
  client = TestClient(create_app())

  response = client.get("/api/v1/health")

  assert response.status_code == 200
  assert response.json() == {
    "status": "ok",
    "service": "Project Filum API",
    "phase": "Phase A",
    "environment": "development",
    "version": "0.1.0",
  }
