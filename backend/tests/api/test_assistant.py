from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from roambot.config import Settings
from roambot.main import create_app


def test_expired_cookie_does_not_permanently_block_guest_assistant(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        client.cookies.set(
            "roambot_session", "invalid-diagnostic-session", domain="testserver.local", path="/"
        )
        body = {"message": "明天从苏州站出发，80公里内，想去湖边", "revision": 0, "draft": {}}
        rejected = client.post("/api/v1/assistant/turns", json=body)
        assert rejected.status_code == 401
        assert "Max-Age=0" in rejected.headers["set-cookie"]
        assert "roambot_session" not in client.cookies
        recovered = client.post("/api/v1/assistant/turns", json=body)
        assert recovered.status_code == 200
        assert recovered.json()["patch"]["main_origin"] == "苏州站"


def test_demo_turn_and_rate_limit_ignore_forwarded_header(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        for i in range(10):
            response = client.post(
                "/api/v1/assistant/turns",
                json={"message": "苏州站明天看湖", "revision": i, "draft": {}, "history": []},
                headers={"X-Forwarded-For": f"1.2.3.{i}"},
            )
            assert response.status_code == 200
            assert response.json()["revision"] == i
            assert response.json()["source"] == "demo"
            assert response.json()["patch"]["main_origin"] == "苏州站"
        response = client.post(
            "/api/v1/assistant/turns",
            json={"message": "again", "revision": 10, "draft": {}},
            headers={"X-Forwarded-For": "4.3.2.1"},
        )
        assert response.status_code == 429


def test_bad_context_is_safe_and_does_not_call_model_or_queries(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.post(
            "/api/v1/assistant/turns",
            json={
                "message": "private-text",
                "revision": 0,
                "draft": {},
                "assistant_context": "invalid.private-context",
            },
        )
        assert response.status_code == 409
        assert "private" not in response.text
        assert client.get("/api/v1/health").status_code == 200


def test_answer_grounded_and_focused_scope(tmp_path):
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        result = client.post(
            "/api/v1/recommendations",
            json={
                "city": "苏州",
                "main_origin": "苏州站",
                "max_distance_km": 50,
                "start_date": today,
                "end_date": today,
                "scenery_types": ["lake"],
            },
        ).json()
        item = result["items"][0]
        body = {
            "message": "路程如何",
            "revision": 3,
            "draft": {},
            "assistant_context": result["assistant_context"],
            "focused_destination_id": item["destination"]["provider_id"],
        }
        answer = client.post("/api/v1/assistant/turns", json=body)
        assert answer.status_code == 200
        assert str(item["distances"][0]["distance_km"]) in answer.json()["reply"]
        assert "苏州站" not in answer.json()["reply"]
        body["focused_destination_id"] = "unknown"
        assert client.post("/api/v1/assistant/turns", json=body).status_code == 409


def test_ai_failure_does_not_block_recommendation(tmp_path, caplog):
    from roambot.api.dependencies import get_assistant_service
    from roambot.providers.protocols import ProviderError

    class Broken:
        def turn(self, request):
            raise ProviderError("unavailable", "private-error")

    app = create_app(Settings(data_dir=tmp_path))
    app.dependency_overrides[get_assistant_service] = lambda: Broken()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/turns",
            json={"message": "private-message", "revision": 0, "draft": {}},
        )
        assert response.status_code == 503
        assert "private" not in response.text
        today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        assert (
            client.post(
                "/api/v1/recommendations",
                json={
                    "city": "苏州",
                    "main_origin": "苏州站",
                    "max_distance_km": 50,
                    "start_date": today,
                    "end_date": today,
                    "scenery_types": ["lake"],
                },
            ).status_code
            == 200
        )
    assert "private" not in caplog.text
