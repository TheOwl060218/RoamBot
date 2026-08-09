from fastapi.testclient import TestClient

from roambot.main import create_app


def test_health_returns_ready() -> None:
    response = TestClient(create_app()).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
