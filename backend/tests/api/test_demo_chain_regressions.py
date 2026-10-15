"""Recording-flow regressions, with isolated SQLite and Mock providers only."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, local
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_favorites import FAVORITES_URL, favorite_payload
from test_history import evaluation_payload, recommendation_payload, register
from test_plans import URL, create_plan, invite

from roambot.api.dependencies import get_provider_bundle
from roambot.persistence.cache import SessionCacheStore
from roambot.persistence.tables import (
    ApiCacheTable,
    HistoryTable,
    PlanWeatherCheckTable,
    TravelPlanTable,
)
from roambot.providers.cached import CachedWeatherProvider
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.providers.trace import ProviderTrace
from roambot.services.plans import CHINA


def test_weather_cache_miss_can_write_same_database(auth_api_fixture):
    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "cache_lock_owner")
    plan, _ = create_plan(owner, csrf)
    engine = factory.kw["bind"]
    event.listen(
        engine, "checkout", lambda connection, *_: connection.execute("PRAGMA busy_timeout=100")
    )
    trace = ProviderTrace()
    weather = CachedWeatherProvider(
        MockProviderBundle.default().weather,
        SessionCacheStore(factory),
        "fixture",
        lambda: datetime.now(UTC),
        trace,
    )
    owner.app.dependency_overrides[get_provider_bundle] = lambda: SimpleNamespace(
        weather=weather, trace=trace
    )
    response = owner.post(f"{URL}/{plan['id']}/weather-checks", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert all(
        c["latest_weather"]["status"] == "success" for c in response.json()["plan"]["candidates"]
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ApiCacheTable)) > 0
        assert db.scalar(select(func.count()).select_from(PlanWeatherCheckTable)) == len(
            plan["candidates"]
        )


def test_favorite_cannot_rewrite_another_users_shared_place(auth_api_fixture):
    alice, _, _ = auth_api_fixture()
    csrf_a = register(alice, "isolated_alice")
    original = alice.post(
        FAVORITES_URL, json=favorite_payload(), headers={"X-CSRF-Token": csrf_a}
    ).json()
    with TestClient(alice.app) as bob:
        csrf_b = register(bob, "isolated_bob")
        payload = favorite_payload(name="Forged shared name")
        payload["destination"]["address"] = "Forged address"
        payload["destination"]["coordinate"]["longitude"] = 100
        added = bob.post(FAVORITES_URL, json=payload, headers={"X-CSRF-Token": csrf_b})
        assert added.status_code == 201
        assert (
            alice.get(FAVORITES_URL).json()["favorites"][0]["place"]
            == original["favorite"]["place"]
        )
        # Once both users have the place, neither can change the other's stored data.
        before_b = bob.get(FAVORITES_URL).json()["favorites"][0]["place"]
        alice.post(FAVORITES_URL, json=payload, headers={"X-CSRF-Token": csrf_a})
        assert bob.get(FAVORITES_URL).json()["favorites"][0]["place"] == before_b


@pytest.mark.parametrize("mode", ["recommendation", "place_evaluation"])
def test_expired_history_rerun_is_actionable_and_preserves_snapshot(auth_api_fixture, mode):
    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "expired_history_owner")
    endpoint, payload = (
        ("recommendations", recommendation_payload())
        if mode == "recommendation"
        else ("place-evaluations", evaluation_payload())
    )
    response = owner.post(f"/api/v1/{endpoint}", json=payload, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    history_id = owner.get("/api/v1/history").json()["histories"][0]["id"]
    yesterday = datetime.now(CHINA).date() - timedelta(days=1)
    with factory.begin() as db:
        row = db.get(HistoryTable, history_id)
        request = json.loads(row.request_json)
        request.update(start_date=yesterday.isoformat(), end_date=yesterday.isoformat())
        row.request_json = json.dumps(request)
    before = owner.get(f"/api/v1/history/{history_id}").json()
    response = owner.post(f"/api/v1/history/{history_id}/rerun", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "history_dates_expired"
    assert {f["path"] for f in response.json()["error"]["fields"]} == {"start_date", "end_date"}
    assert owner.get(f"/api/v1/history/{history_id}").json() == before
    assert len(owner.get("/api/v1/history").json()["histories"]) == 1


def test_other_invite_tab_does_not_invalidate_guest_vote(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "multi_tab_owner")
    plan, _ = create_plan(owner, csrf)
    other_plan, _ = create_plan(owner, csrf)
    link = invite(owner, csrf, plan["id"])
    other_link = invite(owner, csrf, other_plan["id"])
    with TestClient(owner.app) as guest:
        first = guest.post(link + "/join", json={"nickname": "同行"}).json()["anonymous_csrf"]
        assert guest.get(link).status_code == 200
        assert guest.get(other_link).status_code == 200
        guest.post(other_link + "/join", json={"nickname": "同行"})
        body = {"preferred_id": plan["candidates"][0]["id"], "acceptable_ids": []}
        assert (
            guest.put(link + "/vote", json=body, headers={"X-Plan-CSRF": first}).status_code == 200
        )
        assert (
            guest.put(link + "/vote", json=body, headers={"X-Plan-CSRF": "invalid"}).status_code
            == 403
        )


def test_ongoing_plan_checks_remaining_days_without_rewriting_dates(auth_api_fixture):
    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "ongoing_owner")
    plan, _ = create_plan(owner, csrf)
    today = datetime.now(CHINA).date()
    with factory.begin() as db:
        row = db.get(TravelPlanTable, plan["id"])
        row.start_date = (today - timedelta(days=1)).isoformat()
        row.end_date = (today + timedelta(days=1)).isoformat()
    calls = []
    mock = MockProviderBundle.default()

    class FutureWeather:
        def daily(self, coordinate, start, end):
            calls.append((start, end))
            if start < today:
                raise ProviderError("bad_request", "past dates")
            return mock.weather.daily(coordinate, start, end)

    owner.app.dependency_overrides[get_provider_bundle] = lambda: SimpleNamespace(
        weather=FutureWeather(), trace=ProviderTrace()
    )
    response = owner.post(f"{URL}/{plan['id']}/weather-checks", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert all(
        c["latest_weather"]["status"] == "success" for c in response.json()["plan"]["candidates"]
    )
    assert calls == [(today, today + timedelta(days=1))] * len(plan["candidates"])
    after = response.json()["plan"]
    assert after["start_date"] == (today - timedelta(days=1)).isoformat()
    assert after["candidates"][0]["snapshot"] == plan["candidates"][0]["snapshot"]


def test_concurrent_weather_checks_commit_once(auth_api_fixture):
    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "concurrent_weather_owner")
    plan, _ = create_plan(owner, csrf)
    barrier, thread = Barrier(2), local()
    mock = MockProviderBundle.default()

    class ConcurrentWeather:
        def daily(self, *args):
            if not getattr(thread, "started", False):
                thread.started = True
                barrier.wait(timeout=5)
            return mock.weather.daily(*args)

    owner.app.dependency_overrides[get_provider_bundle] = lambda: SimpleNamespace(
        weather=ConcurrentWeather(), trace=ProviderTrace()
    )

    def check():
        return owner.post(f"{URL}/{plan['id']}/weather-checks", headers={"X-CSRF-Token": csrf})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: check(), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 429]
    assert (
        next(r for r in responses if r.status_code == 429).json()["error"]["code"]
        == "weather_check_cooldown"
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlanWeatherCheckTable)) == 2


@pytest.mark.parametrize("action", ["decide", "delete"])
def test_weather_fetch_revalidates_plan_changes_before_commit(auth_api_fixture, action):
    owner, _, factory = auth_api_fixture()
    csrf = register(owner, "weather_change_owner")
    plan, _ = create_plan(owner, csrf)
    headers = {"X-CSRF-Token": csrf}
    path = f"{URL}/{plan['id']}"
    mock = MockProviderBundle.default()

    class ChangingWeather:
        changed = False

        def daily(self, *args):
            if not self.changed:
                self.changed = True
                response = (
                    owner.delete(path, headers=headers)
                    if action == "delete"
                    else owner.put(
                        path + "/decision",
                        headers=headers,
                        json={"candidate_id": plan["candidates"][0]["id"]},
                    )
                )
                assert response.status_code == (204 if action == "delete" else 200)
            return mock.weather.daily(*args)

    weather = ChangingWeather()
    owner.app.dependency_overrides[get_provider_bundle] = lambda: SimpleNamespace(
        weather=weather, trace=ProviderTrace()
    )
    result = owner.post(path + "/weather-checks", headers=headers)
    assert result.status_code == (404 if action == "delete" else 200)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlanWeatherCheckTable)) == (
            0 if action == "delete" else 1
        )
    if action == "decide":
        assert result.json()["plan"]["candidates"][1]["latest_weather"] is None
