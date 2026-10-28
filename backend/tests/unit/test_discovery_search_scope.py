"""Search destinations must not fall back to unrelated device coordinates."""

from datetime import UTC
from types import SimpleNamespace

import pytest
from test_discovery import Maps, Weather
from test_discovery_sources import Search

from roambot.domain.discovery import DiscoveryRequest
from roambot.domain.models import Coordinate
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.services.discovery_sources import (
    DiscoverySourceModel,
    DiscoverySourceWorkflow,
    PlacePicks,
    SourceIntake,
    SourceNomination,
)


def scoped_workflow(
    tmp_path, monkeypatch, intake, *, previous=None, message="改去北京，找胡同拍照"
):
    stages = []

    def structured(provider, name, schema, instructions, data, tokens, *, recover_truncated=None):
        stages.append(name)
        if name == "plan_source_request":
            return SourceIntake.model_validate(intake)
        if name == "nominate_source_places":
            return SourceNomination(venues=[{"name": "独立书店"}])
        assert name == "select_outing_places"
        return PlacePicks(cards=[{"ref": "p1", "destination_ref": "p1", "experience": "漫步拍照"}])

    monkeypatch.setattr("roambot.services.discovery_sources.structured_call", structured)
    # Public city-centre coordinates, never a user's actual device location.
    point = Coordinate(longitude=104.06, latitude=30.68, system="wgs84")
    body = DiscoveryRequest(
        message=message, location=point, location_details={"source": "device", "accuracy_m": 60}
    )
    maps = Maps()
    maps.area = lambda point: "四川省 成都市 青羊区"
    run = DiscoverySourceWorkflow(
        body,
        maps,
        Weather(),
        Search(),
        DiscoverySourceModel(SimpleNamespace(_model="offline-scope")),
        DiscoveryCache(tmp_path / "scope.sqlite3"),
        "isolated-scope-owner",
        previous=previous,
    )
    return run, stages


@pytest.mark.parametrize("old_city,new_city", [("青岛", "北京"), ("南京", "扬州")])
def test_city_switch_uses_destination_even_when_patch_only_clears_old_city(
    tmp_path, monkeypatch, old_city, new_city
):
    run, stages = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {"region": None},
            "temporal": None,
            "search_scope": {"kind": "region", "region": new_city},
            "clear_fields": ["region"],
            "clear_quote": old_city,
            "research_query": f"{new_city}适合漫步拍照的地点",
        },
        previous={
            "context": {"region": old_city},
            "cards": [],
            "center": {"longitude": 104.06, "latitude": 30.68, "system": "gcj02"},
            "center_name": "旧设备定位",
        },
        message=f"不去{old_city}了，改去{new_city}漫步拍照",
    )
    run.run()
    assert run.status == "completed", run.errors
    assert run.context.region == new_city
    searches = [call for call in run.maps.calls if call[0] == "search"]
    assert searches and all(call[2:] == (new_city, None, None) for call in searches)
    assert not [call for call in run.maps.calls if call[0] in {"gps", "route", "geocode"}]
    assert run.center is None
    assert run.snapshot()["position"]["label"] == new_city
    assert run.snapshot()["position"]["source"] == "region"
    assert run.search.queries == [f"{new_city} {new_city}适合漫步拍照的地点"]
    assert stages == ["plan_source_request", "nominate_source_places", "select_outing_places"]
    assert run.metrics["model_calls"] == 3


def test_nearby_request_replaces_old_destination_and_uses_device_anchor(tmp_path, monkeypatch):
    run, stages = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "nearby", "region": None},
            "nearby_quote": "当前位置附近",
            "research_query": "适合漫步拍照的地方",
        },
        previous={"context": {"region": "北京"}, "cards": []},
        message="改看当前位置附近能拍照的地方",
    )
    run.run()
    assert run.status == "completed", run.errors
    assert run.context.region is None
    searches = [call for call in run.maps.calls if call[0] == "search"]
    assert searches and all(call[2] is None and call[3] == run.center for call in searches)
    assert run.center.system == "gcj02"
    assert ("gps", "wgs84") in run.maps.calls
    assert run.search.queries == ["四川省 成都市 青羊区 适合漫步拍照的地方"]
    assert len(stages) == 3


def test_new_city_drops_inherited_nearby_origin_and_radius(tmp_path, monkeypatch):
    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "region", "region": "北京"},
            "research_query": "北京胡同拍照",
        },
        previous={
            "context": {
                "origin": "旧出发点",
                "origin_quote": "旧出发点",
                "max_distance_km": 5,
                "distance_quote": "五公里",
            },
            "cards": [],
            "center": {"longitude": 104.06, "latitude": 30.68, "system": "gcj02"},
        },
    )
    run.run()
    assert run.status == "completed", run.errors
    assert run.context.region == "北京"
    assert run.context.origin is None and run.context.max_distance_km is None
    assert run.center is None
    assert not [call for call in run.maps.calls if call[0] in {"gps", "route", "geocode"}]


def test_new_city_keeps_explicit_new_origin_and_distance(tmp_path, monkeypatch):
    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {
                "origin": "北京站",
                "origin_quote": "北京站",
                "max_distance_km": 5,
                "distance_quote": "五公里",
            },
            "temporal": None,
            "search_scope": {"kind": "region", "region": "北京"},
            "research_query": "北京胡同拍照",
        },
        previous={"context": {"region": "青岛"}, "cards": []},
        message="改去北京，在北京站五公里内拍照",
    )
    run.run()
    assert run.status == "completed", run.errors
    assert run.context.origin == "北京站" and run.context.max_distance_km == 5
    assert ("geocode", "北京站") in run.maps.calls
    assert any(call[0] == "route" for call in run.maps.calls)


def test_scope_survives_archive_and_exhausted_pool_followup(tmp_path, monkeypatch):
    from datetime import datetime

    from roambot.domain.discovery_snapshot import DiscoveryArchive

    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "nearby", "region": None},
            "nearby_quote": "附近",
            "research_query": "附近摄影地点",
        },
        message="附近摄影",
    )
    run.run()
    archived = DiscoveryArchive.model_validate(
        run.snapshot() | {"generated_at": datetime.now(UTC), "source": "demo"}
    )
    assert archived.model_dump()["search_scope"] == {"kind": "nearby", "region": None}
    # Recovered result has no in-memory _explore_plan after a restart.
    previous = run.snapshot() | archived.model_dump(mode="json")
    previous["exploration_state"]["created_at"] = 0
    second = DiscoverySourceWorkflow(
        DiscoveryRequest(
            message="换一批",
            previous_id="owned",
            explore_mode="batch",
            location=run.body.location,
            location_details=run.body.location_details,
        ),
        Maps(),
        Weather(),
        Search(),
        run.model,
        DiscoveryCache(tmp_path / "followup.sqlite3"),
        "isolated-scope-owner",
        previous=previous,
    )
    second.maps.area = lambda point: "四川省 成都市 青羊区"
    second.run()
    searches = [call for call in second.maps.calls if call[0] == "search"]
    assert searches and all(call[3] is not None for call in searches)
    assert second.plan.search_scope.kind == "nearby"


def test_unrestricted_search_does_not_silently_search_device_neighbourhood(tmp_path, monkeypatch):
    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "unrestricted", "region": None},
            "clear_fields": ["region"],
            "clear_quote": "不限城市",
            "research_query": "适合旅行摄影的地方",
        },
        previous={"context": {"region": "北京"}, "cards": []},
        message="不限城市，看看适合旅行摄影的地方",
    )
    run.run()
    assert run.status == "completed", run.errors
    assert not run.request_location and run.center is None
    searches = [call for call in run.maps.calls if call[0] == "search"]
    assert searches and all(call[2:] == (None, None, None) for call in searches)
    assert run.search.queries == ["适合旅行摄影的地方"]
    assert not [call for call in run.maps.calls if call[0] == "gps"]


def test_owned_nearby_scope_can_continue_without_repeating_old_location_quote(
    tmp_path, monkeypatch
):
    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "nearby", "region": None},
            "research_query": "附近适合看书的地方",
        },
        previous={"context": {}, "cards": [], "search_scope": {"kind": "nearby", "region": None}},
        message="这次换成能看书的地方",
    )
    run.run()
    assert run.status == "completed", run.errors
    searches = [call for call in run.maps.calls if call[0] == "search"]
    assert searches and all(call[3] is not None for call in searches)


def test_planning_cache_separates_identical_text_with_different_owned_scope(tmp_path, monkeypatch):
    for kind in ("nearby", "unrestricted"):
        scope = {"kind": kind, "region": None}
        run, stages = scoped_workflow(
            tmp_path,
            monkeypatch,
            {
                "intent": "search",
                "context": {},
                "temporal": None,
                "search_scope": scope,
                "research_query": "可以看书的地方",
            },
            previous={
                "context": {},
                "cards": [],
                "search_scope": scope,
                "search_request": "可以看书的地方",
            },
            message="再看个能读书的地方",
        )
        run.run()
        assert run.status == "completed", run.errors
        assert run.plan.search_scope.kind == kind
        assert stages[0] == "plan_source_request"
        assert (run.center is None) == (kind == "unrestricted")


@pytest.mark.parametrize(
    "scope,nearby_quote",
    [
        (None, None),
        ({"kind": "region", "region": None}, None),
        ({"kind": "nearby", "region": None}, None),
        ({"kind": "nearby", "region": None}, "未出现在用户原话的附近要求"),
    ],
)
def test_missing_or_unsupported_scope_stops_before_retrieval(
    tmp_path, monkeypatch, scope, nearby_quote
):
    run, stages = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": scope,
            "nearby_quote": nearby_quote,
            "research_query": "北京胡同拍照",
        },
    )
    run.run()
    assert run.status == "failed" and run.errors
    assert stages == ["plan_source_request"]
    assert run.maps.calls == [] and run.search.queries == []


def test_empty_map_results_are_distinct_from_provider_failure(tmp_path, monkeypatch):
    run, stages = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "region", "region": "北京"},
            "research_query": "北京胡同拍照",
        },
    )
    run.maps.search = lambda *args: []
    run.run()
    assert run.metrics["retrieved_candidates"] == 0
    assert "没有找到符合本次搜索范围的地点" in run.snapshot()["reply"]
    assert stages == ["plan_source_request", "nominate_source_places"]
    assert run.errors == []


def test_provider_failure_is_not_reported_as_no_places(tmp_path, monkeypatch):
    from roambot.providers.protocols import ProviderError

    run, _ = scoped_workflow(
        tmp_path,
        monkeypatch,
        {
            "intent": "search",
            "context": {},
            "temporal": None,
            "search_scope": {"kind": "region", "region": "北京"},
            "research_query": "北京胡同拍照",
        },
    )

    def unavailable(*args):
        raise ProviderError("unavailable", "offline provider failure")

    run.maps.search = unavailable
    run.run()
    assert run.errors and run.status == "failed"
    assert run.snapshot()["reply"] == "这轮查询尚未完成。"
