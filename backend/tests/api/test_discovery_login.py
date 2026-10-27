from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_discovery_commands import execute, intake_job, source_job
from test_history import PASSWORD, register

from roambot.api.routes.commands import get_business_planner


@pytest.mark.parametrize("method", ["register", "login"])
def test_login_keeps_only_this_browser_guest_results_under_new_session(auth_api_fixture, method):
    client, service, _ = auth_api_fixture()
    if method == "login":
        service.register("continuation_owner", PASSWORD)
    key = source_job(client, "")
    original = client.get("/api/v1/discovery/jobs/" + key).json()
    old_guest = client.cookies.get("roambot_assistant_identity")
    with TestClient(client.app) as other:
        other_key = source_job(other, "")
        response = client.post(
            "/api/v1/auth/" + method, json={"username": "continuation_owner", "password": PASSWORD}
        )
        assert response.status_code in {200, 201}
        assert not client.cookies.get("roambot_assistant_identity")
        csrf = response.json()["csrf_token"]
        restored = client.get("/api/v1/discovery/jobs/" + key)
        assert restored.status_code == 200
        assert restored.json()["cards"] == original["cards"]
        assert client.get("/api/v1/discovery/jobs/" + other_key).status_code == 404
        assert other.get("/api/v1/discovery/jobs/" + other_key).status_code == 200
        assert client.post("/api/v1/discovery/jobs/" + key + "/history").status_code == 403
        saved = client.post(
            "/api/v1/discovery/jobs/" + key + "/history", headers={"X-CSRF-Token": csrf}
        )
        assert saved.status_code == 200
        assert client.get("/api/v1/history/" + saved.json()["history_id"]).status_code == 200
        other.cookies.set("roambot_assistant_identity", old_guest)
        assert other.get("/api/v1/discovery/jobs/" + key).status_code == 404
    # A distinct session for the same account must not gain the first session's jobs.
    with TestClient(client.app) as second:
        assert (
            second.post(
                "/api/v1/auth/login", json={"username": "continuation_owner", "password": PASSWORD}
            ).status_code
            == 200
        )
        assert second.get("/api/v1/discovery/jobs/" + key).status_code == 404
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    register(client, "different_owner")
    assert client.get("/api/v1/discovery/jobs/" + key).status_code == 404


def test_invalid_login_does_not_claim_or_destroy_guest_results(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    key = source_job(client, "")
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "missing_user", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/discovery/jobs/" + key).status_code == 200


def test_login_resumes_previously_understood_favorite_once_without_another_model(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    source = source_job(client, "")
    intake = intake_job(
        client,
        "",
        source,
        message="收藏第一个",
        actions=[{"tool": "favorite_place", "arguments": {"place": 1}}],
    )

    def forbidden(*args):
        raise AssertionError("Login continuation must not reinterpret the command")

    client.app.dependency_overrides[get_business_planner] = lambda: forbidden
    command = {
        "request_id": str(uuid4()),
        "message": "收藏第一个",
        "intake_id": intake,
        "context": {"page": "/explore", "discovery_job_id": source, "layer": "results"},
    }
    assert client.post("/api/v1/assistant/commands/proposals", json=command).status_code == 401
    csrf = register(client, "resumed_favorite_owner")
    command["request_id"] = str(uuid4())
    planned = client.post(
        "/api/v1/assistant/commands/proposals", json=command, headers={"X-CSRF-Token": csrf}
    )
    assert planned.status_code == 200
    result = execute(client, csrf, planned.json())
    assert result.json()["status"] == "completed"
    assert execute(client, csrf, planned.json()).json() == result.json()
    favorites = client.get("/api/v1/favorites").json()["favorites"]
    assert len(favorites) == 1
    assert favorites[0]["place"]["provider_place_id"] == "verified1"
