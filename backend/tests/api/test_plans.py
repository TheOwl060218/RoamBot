import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_history import evaluation_payload, recommendation_payload, register

from roambot.api.dependencies import get_provider_bundle
from roambot.providers.protocols import ProviderError

URL = "/api/v1/plans"


def test_close_voting_preserves_votes_blocks_edits_and_reopens(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "close_owner")
    plan, _ = create_plan(owner, csrf)
    path = f"{URL}/{plan['id']}"
    headers = {"X-CSRF-Token": csrf}
    link = invite(owner, csrf, plan["id"])
    cid = plan["candidates"][0]["id"]
    vote = {"preferred_id": cid, "acceptable_ids": []}
    with TestClient(owner.app) as guest:
        joined = guest.post(link + "/join", json={"nickname": "测试同行"}).json()
        guest_headers = {"X-Plan-CSRF": joined["anonymous_csrf"]}
        assert guest.put(link + "/vote", json=vote, headers=guest_headers).status_code == 200
        assert owner.put(path + "/vote", json=vote, headers=headers).status_code == 200
        before = owner.get(path).json()["plan"]["summary"]
        closed = owner.put(path + "/voting-close", headers=headers)
        assert closed.status_code == 200
        data = closed.json()["plan"]
        assert data["status"] == "closed" and data["final_candidate_id"] is None
        assert data["summary"] == before
        assert owner.put(path + "/voting-close", headers=headers).status_code == 200
        assert owner.put(path + "/vote", json=vote, headers=headers).status_code == 409
        assert guest.put(link + "/vote", json=vote, headers=guest_headers).status_code == 409
        with TestClient(owner.app) as newcomer:
            assert newcomer.get(link).json()["plan"]["summary"] == before
            assert newcomer.post(link + "/join", json={"nickname": "后来者"}).status_code == 409
        reopened = owner.delete(path + "/decision", headers=headers)
        assert reopened.status_code == 200
        assert reopened.json()["plan"]["status"] == "voting"
        assert reopened.json()["plan"]["summary"] == before
        with TestClient(owner.app) as newcomer:
            assert newcomer.get(link).json()["plan"]["summary"] is None
        assert guest.put(link + "/vote", json=vote, headers=guest_headers).status_code == 200
        assert owner.put(path + "/voting-close", headers=headers).status_code == 200
        decided = owner.put(path + "/decision", json={"candidate_id": cid}, headers=headers)
        assert decided.status_code == 200
        assert decided.json()["plan"]["status"] == "decided"
        assert owner.put(path + "/voting-close", headers=headers).status_code == 409


def test_close_voting_requires_owner_and_csrf(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "secure_close_owner")
    plan, _ = create_plan(owner, csrf)
    path = f"{URL}/{plan['id']}/voting-close"
    assert owner.put(path).status_code == 403
    with TestClient(owner.app) as other:
        assert other.put(path).status_code == 401
        other_csrf = register(other, "other_close_owner")
        assert other.put(path, headers={"X-CSRF-Token": other_csrf}).status_code == 404
    assert owner.get(f"{URL}/{plan['id']}").json()["plan"]["status"] == "voting"


def test_concurrent_close_and_guest_vote_never_write_after_close(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "race_close_owner")
    plan, _ = create_plan(owner, csrf)
    path = f"{URL}/{plan['id']}"
    headers = {"X-CSRF-Token": csrf}
    link = invite(owner, csrf, plan["id"])
    with TestClient(owner.app) as guest:
        joined = guest.post(link + "/join", json={"nickname": "并发同行"}).json()
        guest_headers = {"X-Plan-CSRF": joined["anonymous_csrf"]}
        body = {"preferred_id": plan["candidates"][0]["id"]}
        gate = Barrier(2)

        def close():
            gate.wait(timeout=10)
            return owner.put(path + "/voting-close", headers=headers)

        def vote():
            gate.wait(timeout=10)
            return guest.put(link + "/vote", json=body, headers=guest_headers)

        with ThreadPoolExecutor(max_workers=2) as pool:
            closing, voting = pool.submit(close), pool.submit(vote)
            closed, voted = closing.result(timeout=20), voting.result(timeout=20)
        assert closed.status_code == 200
        assert voted.status_code in {200, 409}
        before = closed.json()["plan"]["summary"]
        assert before["voted_count"] == (1 if voted.status_code == 200 else 0)
        assert owner.get(path).json()["plan"]["summary"] == before
        assert guest.put(link + "/vote", json=body, headers=guest_headers).status_code == 409


def test_ended_plan_rejects_close_vote_decision_and_reopen(auth_api_fixture):
    from roambot.persistence.tables import TravelPlanTable

    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "ended_close_owner")
    plan, _ = create_plan(owner, csrf)
    path = f"{URL}/{plan['id']}"
    headers = {"X-CSRF-Token": csrf}
    with factory.begin() as db:
        db.get(TravelPlanTable, plan["id"]).end_date = "2000-01-01"
    cid = plan["candidates"][0]["id"]
    assert owner.put(path + "/voting-close", headers=headers).status_code == 409
    assert owner.put(path + "/vote", json={"preferred_id": cid}, headers=headers).status_code == 409
    decision = owner.put(path + "/decision", json={"candidate_id": cid}, headers=headers)
    assert decision.status_code == 409
    assert owner.delete(path + "/decision", headers=headers).status_code == 409


def create_plan(client, csrf):
    payload = recommendation_payload()
    payload["scenery_types"] = ["lake", "museum", "old_town"]
    response = client.post("/api/v1/recommendations", json=payload, headers={"X-CSRF-Token": csrf})
    result = response.json()
    ids = [item["destination"]["provider_id"] for item in result["items"][:2]]
    assert len(ids) == 2
    created = client.post(
        URL,
        json={"history_id": result["history_id"], "candidate_ids": ids},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    return created.json()["plan"], result


def test_guest_cannot_create_or_receive_history_id(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    result = client.post("/api/v1/recommendations", json=recommendation_payload()).json()
    assert result.get("history_id") is None
    assert (
        client.post(URL, json={"history_id": "missing", "candidate_ids": ["a", "b"]}).status_code
        == 401
    )


def test_plan_copies_trusted_snapshot_and_survives_history_deletion(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "plan_owner")
    plan, result = create_plan(client, csrf)
    assert plan["status"] == "voting"
    assert plan["expected_count"] == 1
    assert plan["participants"][0]["role"] == "owner"
    assert plan["created_at"].endswith("+00:00") or plan["created_at"].endswith("Z")
    assert plan["candidates"][0]["snapshot"]["score"] == result["items"][0]["score"]
    assert "coordinate" not in plan["candidates"][0]["snapshot"]["destination"]
    assert "distances" not in plan["candidates"][0]["snapshot"]
    client.delete(f"/api/v1/history/{result['history_id']}", headers={"X-CSRF-Token": csrf})
    assert client.get(f"{URL}/{plan['id']}").status_code == 200
    renamed = client.patch(
        f"{URL}/{plan['id']}",
        json={"name": "周末同行", "expected_count": 3},
        headers={"X-CSRF-Token": csrf},
    )
    assert renamed.json()["plan"]["name"] == "周末同行"
    assert client.get(URL).json()["plans"][0]["expected_count"] == 3
    assert client.delete(f"{URL}/{plan['id']}", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get(URL).json()["plans"] == []


def test_creation_rejects_other_history_evaluation_invalid_candidates_and_csrf(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_plan")
    plan, result = create_plan(client, csrf)
    body = {"history_id": result["history_id"], "candidate_ids": ["fake", "fake2"]}
    assert (
        client.post(URL, json=body, headers={"X-CSRF-Token": csrf}).json()["error"]["code"]
        == "candidate_not_in_history"
    )
    assert client.post(URL, json=body).status_code == 403
    evaluation = client.post(
        "/api/v1/place-evaluations", json=evaluation_payload(), headers={"X-CSRF-Token": csrf}
    )
    assert evaluation.status_code == 200
    eid = client.get("/api/v1/history").json()["histories"][0]["id"]
    body["history_id"] = eid
    assert (
        client.post(URL, json=body, headers={"X-CSRF-Token": csrf}).json()["error"]["code"]
        == "history_not_eligible"
    )
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    other = register(client, "bob_plan")
    body["history_id"] = result["history_id"]
    assert client.post(URL, json=body, headers={"X-CSRF-Token": other}).status_code == 404
    for method, data in [("get", None), ("patch", {"name": "偷改"}), ("delete", None)]:
        response = getattr(client, method)(
            f"{URL}/{plan['id']}",
            **({"json": data} if data else {}),
            headers={"X-CSRF-Token": other},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "plan_not_found"


def invite(client, csrf, pid):
    response = client.post(f"{URL}/{pid}/invite/rotate", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    return "/api/v1/public/plans/" + response.json()["url"].split("/")[-1]


def test_invite_join_vote_visibility_and_own_identity(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "invite_owner")
    plan, _ = create_plan(owner, csrf)
    link = invite(owner, csrf, plan["id"])
    guest = TestClient(owner.app)
    before = guest.get(link).json()["plan"]
    assert before["summary"] is None and before["participants"] is None
    joined = guest.post(link + "/join", json={"nickname": "同行者"}).json()
    secret = joined["anonymous_csrf"]
    assert guest.cookies.get("roambot_plan_identity")
    headers = {"X-Plan-CSRF": secret}
    cids = [c["id"] for c in plan["candidates"]]
    assert (
        guest.put(link + "/vote", json={"preferred_id": cids[0], "acceptable_ids": []}).status_code
        == 403
    )
    voted = guest.put(
        link + "/vote", json={"preferred_id": cids[0], "acceptable_ids": [cids[1]]}, headers=headers
    ).json()["plan"]
    assert voted["summary"]["voted_count"] == 1
    assert voted["summary"]["candidates"][0]["acceptable_count"] == 1
    assert voted["me"]["preferred_id"] == cids[0]
    changed = guest.put(
        link + "/vote", json={"preferred_id": cids[1], "acceptable_ids": []}, headers=headers
    ).json()["plan"]
    assert changed["summary"]["candidates"][0]["preferred_count"] == 0
    assert changed["summary"]["candidates"][1]["acceptable_count"] == 1
    refreshed = guest.get(link).json()
    assert refreshed["plan"]["me"]["nickname"] == "同行者"
    headers = {"X-Plan-CSRF": refreshed["anonymous_csrf"]}
    other = TestClient(owner.app)
    duplicate = other.post(link + "/join", json={"nickname": " 同行者 "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "nickname_taken"
    private = json.dumps(voted, ensure_ascii=False)
    for forbidden in (
        "longitude",
        "latitude",
        "origin_label",
        "main_origin",
        "distances",
        "user_id",
    ):
        assert forbidden not in private
    participant = voted["me"]["id"]
    removed = owner.delete(
        f"{URL}/{plan['id']}/participants/{participant}", headers={"X-CSRF-Token": csrf}
    )
    assert removed.status_code == 204
    assert owner.get(f"{URL}/{plan['id']}").json()["plan"]["summary"]["voted_count"] == 0
    assert (
        guest.put(
            link + "/vote", json={"preferred_id": cids[0], "acceptable_ids": []}, headers=headers
        ).json()["error"]["code"]
        == "participant_required"
    )
    guest.close()
    other.close()


def test_guest_vote_response_keeps_csrf_for_editing_without_reload(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "edit_vote_owner")
    plan, _ = create_plan(owner, csrf)
    link = invite(owner, csrf, plan["id"])
    with TestClient(owner.app) as guest:
        joined = guest.post(link + "/join", json={"nickname": "改票者"}).json()
        first = guest.put(
            link + "/vote",
            json={"preferred_id": plan["candidates"][0]["id"]},
            headers={"X-Plan-CSRF": joined["anonymous_csrf"]},
        ).json()
        assert isinstance(first["anonymous_csrf"], str)
        changed = guest.put(
            link + "/vote",
            json={"preferred_id": plan["candidates"][1]["id"]},
            headers={"X-Plan-CSRF": first["anonymous_csrf"]},
        )
        assert changed.status_code == 200
        assert changed.json()["plan"]["me"]["preferred_id"] == plan["candidates"][1]["id"]


def test_plan_redacts_geocoded_origin_labels_from_free_text(auth_api_fixture):
    from roambot.persistence.tables import HistoryTable

    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "redaction_owner")
    plan, result = create_plan(owner, csrf)
    private_label = "测试专用私人出发地详情"
    with factory.begin() as db:
        history = db.get(HistoryTable, result["history_id"])
        stored = json.loads(history.result_json)
        stored["items"][0]["distances"][0]["origin_label"] = private_label
        stored["items"][0]["explanation"] = f"从{private_label}出发较近。"
        history.result_json = json.dumps(stored, ensure_ascii=False)
    response = owner.post(
        URL,
        json={
            "history_id": result["history_id"],
            "candidate_ids": [c["id"] for c in plan["candidates"]],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    assert private_label not in response.text


def test_invite_rotation_revoke_expiry_and_delete(auth_api_fixture):
    from roambot.persistence.tables import PlanInviteTable, TravelPlanTable

    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "rotate_owner")
    plan, _ = create_plan(owner, csrf)
    link = invite(owner, csrf, plan["id"])
    replacement = invite(owner, csrf, plan["id"])
    assert owner.get(link).json()["error"]["code"] == "invite_revoked"
    with factory.begin() as db:
        row = db.scalar(select(PlanInviteTable).where(PlanInviteTable.revoked_at.is_(None)))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert owner.get(replacement).json()["error"]["code"] == "invite_expired"
    replacement = invite(owner, csrf, plan["id"])
    owner.delete(f"{URL}/{plan['id']}/invite", headers={"X-CSRF-Token": csrf})
    assert owner.get(replacement).status_code == 404
    replacement = invite(owner, csrf, plan["id"])
    owner.delete(f"{URL}/{plan['id']}", headers={"X-CSRF-Token": csrf})
    assert owner.get(replacement).status_code == 404
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlanInviteTable)) == 0
        assert db.scalar(select(func.count()).select_from(TravelPlanTable)) == 0


def test_decision_reopen_and_invalid_vote_constraints(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "decide_owner")
    plan, _ = create_plan(owner, csrf)
    headers = {"X-CSRF-Token": csrf}
    pid = plan["id"]
    cid = plan["candidates"][0]["id"]
    link = invite(owner, csrf, pid)
    assert (
        owner.put(
            f"{URL}/{pid}/decision", json={"candidate_id": "fake"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        owner.put(
            f"{URL}/{pid}/vote",
            json={"preferred_id": cid, "acceptable_ids": ["fake"]},
            headers=headers,
        ).status_code
        == 422
    )
    owner.put(
        f"{URL}/{pid}/vote", json={"preferred_id": cid, "acceptable_ids": []}, headers=headers
    )
    decided = owner.put(f"{URL}/{pid}/decision", json={"candidate_id": cid}, headers=headers)
    assert decided.status_code == 200
    assert decided.json()["plan"]["final_candidate_id"] == cid
    assert owner.get(link).json()["plan"]["summary"]["voted_count"] == 1
    assert (
        owner.put(f"{URL}/{pid}/vote", json={"preferred_id": cid}, headers=headers).json()["error"][
            "code"
        ]
        == "vote_closed"
    )
    reopened = owner.delete(f"{URL}/{pid}/decision", headers=headers).json()["plan"]
    assert reopened["status"] == "voting" and reopened["final_candidate_id"] is None
    assert reopened["summary"]["voted_count"] == 1
    assert owner.delete(f"{URL}/{pid}/decision", headers=headers).status_code == 409


def test_weather_check_cooldown_failure_retention_and_end_date(auth_api_fixture):
    from roambot.api.routes.plans import get_plan_service
    from roambot.providers.factory import ProviderBundle
    from roambot.providers.mock import MockProviderBundle
    from roambot.providers.trace import ProviderTrace
    from roambot.services.plans import PlanService

    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "weather_owner")
    plan, _ = create_plan(owner, csrf)
    now = datetime.now(UTC)
    owner.app.dependency_overrides[get_plan_service] = lambda: PlanService(factory, lambda: now)
    headers = {"X-CSRF-Token": csrf}
    route = f"{URL}/{plan['id']}/weather-checks"
    first = owner.post(route, headers=headers)
    assert first.status_code == 200
    data = first.json()["plan"]
    assert all(c["latest_weather"]["status"] == "success" for c in data["candidates"])
    for candidate in data["candidates"]:
        check = candidate["latest_weather"]
        assert [d["date"] for d in check["daily_suitability"]] == [
            d["date"] for d in check["weather"]
        ]
        assert all(d["summary"] for d in check["daily_suitability"])
    snapshot = data["candidates"][0]["snapshot"]
    assert data["candidates"][0]["latest_weather"]["checked_at"].endswith(("+00:00", "Z"))
    assert owner.post(route, headers=headers).json()["error"]["code"] == "weather_check_cooldown"
    now += timedelta(hours=1, seconds=1)

    class FailingWeather:
        def daily(self, *_args):
            raise ProviderError("unavailable", "redacted")

    mock = MockProviderBundle.default()
    owner.app.dependency_overrides[get_provider_bundle] = lambda: ProviderBundle(
        mock.geocoder,
        mock.places,
        mock.distance,
        FailingWeather(),
        mock.explanations,
        ProviderTrace(),
    )
    failed = owner.post(route, headers=headers).json()["plan"]
    assert failed["candidates"][0]["latest_weather"]["status"] == "failed"
    assert (
        failed["candidates"][0]["latest_weather"]["weather"]
        == data["candidates"][0]["latest_weather"]["weather"]
    )
    assert failed["candidates"][0]["snapshot"] == snapshot
    assert failed["candidates"][0]["latest_weather"]["daily_suitability"] == (
        data["candidates"][0]["latest_weather"]["daily_suitability"]
    )
    now += timedelta(days=10)
    assert owner.post(route, headers=headers).json()["error"]["code"] == "invalid_plan_transition"


def test_weather_check_recomputes_advice_without_changing_snapshot(auth_api_fixture):
    from roambot.providers.factory import ProviderBundle
    from roambot.providers.mock import MockProviderBundle
    from roambot.providers.trace import ProviderTrace

    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "fresh_advice")
    plan, _ = create_plan(owner, csrf)
    mock = MockProviderBundle.default()

    class StormWeather:
        def daily(self, *args):
            return [
                day.model_copy(update={"precipitation_mm": 50, "wind_speed_kmh": 60})
                for day in mock.weather.daily(*args)
            ]

    owner.app.dependency_overrides[get_provider_bundle] = lambda: ProviderBundle(
        mock.geocoder,
        mock.places,
        mock.distance,
        StormWeather(),
        mock.explanations,
        ProviderTrace(),
    )
    result = owner.post(
        f"{URL}/{plan['id']}/weather-checks", headers={"X-CSRF-Token": csrf}
    )
    assert result.status_code == 200
    checked = result.json()["plan"]
    for before, after in zip(plan["candidates"], checked["candidates"], strict=True):
        assert after["snapshot"] == before["snapshot"]
        advice = after["latest_weather"]["daily_suitability"]
        assert advice and all(day["status"] == "not_recommended" for day in advice)
        assert all("50毫米" in day["summary"] and "60公里" in day["summary"] for day in advice)
    # Reading stored checks derives advice without calling providers again.
    owner.app.dependency_overrides[get_provider_bundle] = lambda: mock
    assert owner.get(f"{URL}/{plan['id']}").json()["plan"]["candidates"] == checked["candidates"]
    link = invite(owner, csrf, plan["id"])
    with TestClient(owner.app) as guest:
        public = guest.get(link).json()["plan"]
        assert public["summary"] is None
        assert public["candidates"] == checked["candidates"]


def test_owner_writes_and_guest_writes_enforce_separate_privileges(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "privilege_owner")
    plan, _ = create_plan(owner, csrf)
    link = invite(owner, csrf, plan["id"])
    guest = TestClient(owner.app)
    guest.post(link + "/join", json={"nickname": "普通同行者"})
    pid = plan["id"]
    endpoints = [
        ("post", f"{URL}/{pid}/invite/rotate", None),
        ("delete", f"{URL}/{pid}/invite", None),
        ("post", f"{URL}/{pid}/weather-checks", None),
        ("put", f"{URL}/{pid}/decision", {"candidate_id": plan["candidates"][0]["id"]}),
        ("delete", f"{URL}/{pid}/decision", None),
    ]
    for method, endpoint, body in endpoints:
        args = {"json": body} if body else {}
        assert getattr(guest, method)(endpoint, **args).status_code == 401
        assert getattr(owner, method)(endpoint, **args).status_code == 403
    guest.close()


def test_duplicate_candidates_forged_snapshots_and_blank_names_are_rejected(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "validation_owner")
    plan, result = create_plan(owner, csrf)
    cid = plan["candidates"][0]["id"]
    body = {"history_id": result["history_id"], "candidate_ids": [cid, cid]}
    headers = {"X-CSRF-Token": csrf}
    assert owner.post(URL, json=body, headers=headers).status_code == 422
    body["candidate_ids"] = [c["id"] for c in plan["candidates"]]
    body["score"] = 100
    assert owner.post(URL, json=body, headers=headers).status_code == 422
    assert (
        owner.patch(f"{URL}/{plan['id']}", json={"name": "   "}, headers=headers).status_code == 422
    )


def test_decided_weather_only_checks_final_candidate_and_checks_cascade(auth_api_fixture):
    from roambot.persistence.tables import PlanWeatherCheckTable

    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "final_weather")
    plan, _ = create_plan(owner, csrf)
    headers = {"X-CSRF-Token": csrf}
    path = f"{URL}/{plan['id']}"
    owner.put(
        path + "/decision", json={"candidate_id": plan["candidates"][0]["id"]}, headers=headers
    )
    checked = owner.post(path + "/weather-checks", headers=headers).json()["plan"]
    assert checked["candidates"][0]["latest_weather"] is not None
    assert checked["candidates"][1]["latest_weather"] is None
    owner.delete(path, headers=headers)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlanWeatherCheckTable)) == 0
