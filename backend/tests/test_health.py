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


def test_health_endpoint_allows_local_dev_cors() -> None:
  client = TestClient(create_app())

  response = client.get(
    "/api/v1/health",
    headers={"Origin": "http://127.0.0.1:5173"},
  )

  assert response.status_code == 200
  assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
