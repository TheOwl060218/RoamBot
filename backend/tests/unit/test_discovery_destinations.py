"""Identity and route boundaries, without a model or external requests."""

import copy
from types import SimpleNamespace

import pytest
from test_discovery_sources import workflow

from roambot.domain.models import Coordinate
from roambot.services.discovery_sources import DiscoverySourceModel, PlacePicks


def candidates(tmp_path):
    run, _ = workflow(tmp_path)
    template = run.maps.search("", None, None, None)[0]
    places = [
        copy.deepcopy(template)
        | {
            "id": f"amap:{i}",
            "name": name,
            "map_type": kind,
            "address": address,
            "parent_id": parent,
            "facts": {"opentime_week": "周一休息，其余日期10:00-18:00"},
        }
        for i, (name, kind, address, parent) in enumerate(
            [
                ("北岸湖景区", "风景名胜", "北岸路1号", None),
                ("北岸湖", "自然地名", "北岸区", None),
                ("北岸湖", "餐饮服务", "南街18号", None),
                ("湖畔书屋", "书店", "湖畔公园内", "1"),
            ],
            1,
        )
    ]
    run.ingest(places)
    return run, places


def test_selection_groups_aliases_but_keeps_real_objects_and_own_facts(tmp_path, monkeypatch):
    run, places = candidates(tmp_path)
    original = run.candidate_facts([p["id"] for p in places])
    before = copy.deepcopy(original)
    observed = []

    def call(provider, name, schema, instructions, data, tokens):
        observed.append(data)
        assert name == "select_outing_places"
        return PlacePicks(
            cards=[
                {"ref": "p2", "destination_ref": "p1", "experience": "湖畔"},
                {"ref": "p1", "destination_ref": "p1", "experience": "湖畔"},
                {"ref": "p3", "destination_ref": "p3", "experience": "用餐"},
                {"ref": "p4", "destination_ref": "p4", "experience": "阅读"},
            ]
        )

    monkeypatch.setattr("roambot.services.discovery_sources.structured_call", call)
    selected = DiscoverySourceModel(SimpleNamespace(_model="offline")).choose([], {}, original, [])
    assert len(observed) == 1
    assert [c.place_id for c in selected.cards] == ["amap:2", "amap:3", "amap:4"]
    anchor = next(s["id"] for s in original[1]["sources"] if s["kind"] == "map_record")
    assert selected.cards[0].evidence_ids == [anchor]
    assert original == before
    flat = observed[0]["candidates"]
    assert flat[3]["place"]["parent_ref"] == "p1"
    assert flat[2]["place"]["address"] == "南街18号"
    assert flat[0]["facts"]["opentime_week"] == "周一休息，其余日期10:00-18:00"
    assert all("coordinate" not in c["place"] for c in flat)


@pytest.mark.parametrize("destination, city", [("invented", None), ("p2", "其他城市")])
def test_selection_cannot_bind_unknown_or_other_city_destination(
    tmp_path, monkeypatch, destination, city
):
    run, places = candidates(tmp_path)
    cards = run.candidate_facts([p["id"] for p in places])
    if city:
        cards[1]["place"]["city"] = city
    monkeypatch.setattr(
        "roambot.services.discovery_sources.structured_call",
        lambda *args: PlacePicks(
            cards=[{"ref": "p1", "destination_ref": destination, "experience": "休闲"}]
        ),
    )
    with pytest.raises(ValueError):
        DiscoverySourceModel(SimpleNamespace(_model="offline")).choose([], {}, cards, [])


def test_reserve_uses_same_identity_binding_without_automatically_accepting_omissions(
    tmp_path, monkeypatch
):
    run, places = candidates(tmp_path)
    cards = run.candidate_facts([p["id"] for p in places])
    monkeypatch.setattr(
        "roambot.services.discovery_sources.structured_call",
        lambda *args: PlacePicks(
            cards=[{"ref": "p1", "destination_ref": "p1", "experience": "湖畔"}],
            reserve_cards=[
                {"ref": "p2", "destination_ref": "p1", "experience": "湖畔"},
                {"ref": "p3", "destination_ref": "p3", "experience": "用餐"},
            ],
        ),
    )
    selected = DiscoverySourceModel(SimpleNamespace(_model="offline")).choose([], {}, cards, [])
    assert [c.place_id for c in selected.cards] == ["amap:1"]
    assert [c.place_id for c in selected.reserve_cards] == ["amap:3"]
    assert "amap:4" not in [c.place_id for c in selected.cards + selected.reserve_cards]


def test_same_target_shares_measurement_without_merging_place_identity(tmp_path):
    run, places = candidates(tmp_path)
    run.center = Coordinate(longitude=120, latitude=31, system="gcj02")
    measured = []

    def route(center, place, mode):
        measured.append(place["id"])
        return {"mode": mode, "distance_km": 4.2, "duration_minutes": 45, "estimated": False}

    run.maps.route = route
    ids = [p["id"] for p in places]
    assert run.facts(ids) == ids
    assert measured == ["amap:1"]
    assert set(run.routes) == set(ids)
    run.routes["amap:1"]["distance_km"] = 99
    assert run.routes["amap:2"]["distance_km"] == 4.2
    for key in ids:
        assert any(
            s["place_id"] == key and s["kind"] == "measure_routes" for s in run.evidence.values()
        )
    assert len(run.places) == 4


def test_geometric_filter_never_substitutes_for_actual_route_or_optional_limit(tmp_path):
    run, places = candidates(tmp_path)
    run.center = Coordinate(longitude=120, latitude=31, system="gcj02")
    run.context.max_distance_km = 5
    run.places["amap:2"]["coordinate"]["longitude"] = 121
    # Give every independent target its own point.
    run.places["amap:3"]["coordinate"] = {"longitude": 120.001, "latitude": 31, "system": "gcj02"}
    run.places["amap:4"]["coordinate"] = {"longitude": 120.002, "latitude": 31, "system": "gcj02"}
    measured = []

    def route(center, place, mode):
        measured.append(place["id"])
        return {
            "mode": mode,
            "distance_km": 6.4 if place["id"] == "amap:3" else 4.2,
            "duration_minutes": 45,
            "estimated": False,
        }

    run.maps.route = route
    ids = [p["id"] for p in places]
    assert run.facts(ids) == ["amap:1", "amap:4"]
    assert set(measured) == {"amap:1", "amap:3", "amap:4"}
    assert run.metrics["geographic_precheck_excluded"] == 1
    run.context.max_distance_km = None
    assert run.facts(ids) == ids
    assert "amap:2" in measured
