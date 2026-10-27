"""Separate local deployments share a hostname but not authentication cookies."""

from http.cookies import SimpleCookie

from test_history import register


def candidate_settings(client):
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"session_cookie_name": "roambot_candidate_session"}
    )


def test_two_databases_on_same_hostname_can_login_and_logout_independently(auth_api_fixture):
    baseline, _, _ = auth_api_fixture()
    candidate, _, _ = auth_api_fixture()
    candidate_settings(candidate)
    register(baseline, "baseline_cookie_user")
    csrf = register(candidate, "candidate_cookie_user")
    candidate.cookies.update(baseline.cookies)
    baseline.cookies.update(candidate.cookies)
    assert baseline.get("/api/v1/auth/me").json()["user"]["username"] == "baseline_cookie_user"
    assert candidate.get("/api/v1/auth/me").json()["user"]["username"] == "candidate_cookie_user"
    # /me rotates CSRF: use the current candidate token for its own logout.
    csrf = candidate.get("/api/v1/auth/me").json()["csrf_token"]
    logged_out = candidate.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 204
    deleted = SimpleCookie(logged_out.headers["set-cookie"])
    assert set(deleted) == {"roambot_candidate_session"}
    assert candidate.get("/api/v1/auth/me").status_code == 401
    assert baseline.get("/api/v1/auth/me").status_code == 200


def test_invalid_candidate_cookie_clear_does_not_remove_baseline_cookie(auth_api_fixture):
    candidate, _, _ = auth_api_fixture()
    candidate_settings(candidate)
    candidate.cookies.set("roambot_session", "baseline-opaque", domain="testserver.local", path="/")
    candidate.cookies.set(
        "roambot_candidate_session", "candidate-invalid", domain="testserver.local", path="/"
    )
    response = candidate.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert set(SimpleCookie(response.headers["set-cookie"])) == {"roambot_candidate_session"}
    assert candidate.cookies.get("roambot_session") == "baseline-opaque"
