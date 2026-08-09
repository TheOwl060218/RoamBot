import json
from pathlib import Path

import httpx
import pytest

from roambot.domain.models import Coordinate, Origin, SceneryType
from roambot.providers.amap import AMapProvider
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "amap"
FAKE_KEY = "amap-test-secret"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def provider_for(handler: object) -> AMapProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = ProviderHttpClient(
        client,
        provider="amap",
        base_url="https://restapi.amap.com",
        secrets=(FAKE_KEY,),
    )
    return AMapProvider(http, FAKE_KEY)


def test_geocode_uses_exact_endpoint_and_maps_gcj02_coordinate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/geocode/geo"
        assert dict(request.url.params) == {
            "key": FAKE_KEY,
            "address": "Suzhou Railway Station",
            "city": "Suzhou",
            "output": "json",
        }
        return httpx.Response(200, json=fixture("geocode_success.json"))

    result = provider_for(handler).geocode("Suzhou Railway Station", "Suzhou")
    assert result.coordinate == Coordinate(longitude=120.617, latitude=31.335)
    assert result.label == "Suzhou Railway Station"


def test_geocode_empty_and_provider_errors_are_stable_and_sanitized() -> None:
    empty = {"status": "1", "info": "OK", "infocode": "10000", "count": "0", "geocodes": []}
    with pytest.raises(ProviderError) as missing:
        provider_for(lambda _: httpx.Response(200, json=empty)).geocode("missing", "Suzhou")
    assert missing.value.code == "not_found"

    failed = {"status": "0", "info": FAKE_KEY, "infocode": "10001"}
    with pytest.raises(ProviderError) as unavailable:
        provider_for(lambda _: httpx.Response(200, json=failed)).geocode("station", "Suzhou")
    assert unavailable.value.code == "unavailable"
    assert FAKE_KEY not in str(unavailable.value)


def test_geocode_retries_without_city_when_city_hint_has_no_result() -> None:
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": "0",
                    "geocodes": [],
                },
            )
        return httpx.Response(200, json=fixture("geocode_success.json"))

    result = provider_for(handler).geocode("上海外滩", "苏州")

    assert result.coordinate == Coordinate(longitude=120.617, latitude=31.335)
    assert calls[0]["city"] == "苏州"
    assert "city" not in calls[1]


def test_input_tips_use_city_as_a_hint_and_parse_coordinates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/assistant/inputtips"
        assert dict(request.url.params) == {
            "key": FAKE_KEY,
            "keywords": "南京大学",
            "city": "苏州",
            "citylimit": "false",
            "datatype": "poi",
            "output": "json",
        }
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "1",
                "tips": [{
                    "id": "poi-1",
                    "name": "南京大学苏州校区东区",
                    "district": "江苏省苏州市虎丘区",
                    "address": "太湖大道1520号",
                    "location": "120.1,31.1",
                }],
            },
        )

    values = provider_for(handler).suggest(" 南京大学 ", "苏州")

    assert values[0].name == "南京大学苏州校区东区"
    assert values[0].district == "江苏省苏州市虎丘区"
    assert values[0].coordinate == Coordinate(longitude=120.1, latitude=31.1)


def test_input_tips_return_at_most_five_places() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "tips": [
                    {"id": str(index), "name": f"地点{index}", "location": "120.1,31.1"}
                    for index in range(8)
                ],
            },
        )

    assert len(provider_for(handler).suggest("地点", "苏州")) == 5


def test_resolve_uses_text_search_and_prefers_exact_normalized_name() -> None:
    payload = fixture("poi_text_success.json")
    payload["pois"] = [payload["pois"][1], payload["pois"][0]]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/place/text"
        assert dict(request.url.params) == {
            "key": FAKE_KEY,
            "keywords": "同里古镇",
            "region": "苏州",
            "city_limit": "true",
            "show_fields": "business",
            "page_size": "25",
            "page_num": "1",
            "output": "json",
        }
        return httpx.Response(200, json=payload)

    result = provider_for(handler).resolve(" 同里古镇 ", "苏州")
    assert result.provider_id == "amap:B002"
    assert SceneryType.OLD_TOWN in result.scenery_tags


def test_search_preserves_type_then_provider_order_and_deduplicates() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["keywords"])
        assert request.url.path == "/v5/place/around"
        assert dict(request.url.params) == {
            "key": FAKE_KEY,
            "keywords": request.url.params["keywords"],
            "region": "苏州",
            "city_limit": "true",
            "show_fields": "business",
            "page_size": "25",
            "page_num": "1",
            "output": "json",
            "location": "120.617,31.335",
            "radius": "50000",
            "sortrule": "weight",
        }
        return httpx.Response(200, json=fixture("poi_around_success.json"))

    results = provider_for(handler).search(
        Coordinate(longitude=120.617, latitude=31.335),
        "苏州",
        (SceneryType.LAKE, SceneryType.LAKE, SceneryType.PARK),
        50,
    )

    assert calls == ["湖泊景区", "公园"]
    assert [item.name for item in results] == ["金鸡湖景区", "湖滨公园"]
    assert results[1].provider_id.startswith("amap:synthetic:")
    assert [item.popularity_rank for item in results] == [1, 2]
    assert [item.rating for item in results] == [4.8, 4.5]


def test_search_keeps_provider_rank_local_to_each_scenery_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = fixture("poi_around_success.json")
        if request.url.params["keywords"] == "公园":
            payload["count"] = "1"
            payload["pois"] = [
                {
                    "id": "PARK-ONLY",
                    "name": "独立公园",
                    "location": "120.690000,31.310000",
                    "type": "公园广场;公园",
                    "typecode": "110101",
                    "address": "公园路1号",
                    "cityname": "苏州",
                    "business": {"rating": "4.6"},
                }
            ]
        return httpx.Response(200, json=payload)

    results = provider_for(handler).search(
        Coordinate(longitude=120.617, latitude=31.335),
        "苏州",
        (SceneryType.LAKE, SceneryType.PARK),
        50,
    )

    assert [item.name for item in results] == ["金鸡湖景区", "湖滨公园", "独立公园"]
    assert [item.popularity_rank for item in results] == [1, 2, 1]
    assert [item.rating for item in results] == [4.8, 4.5, 4.6]


@pytest.mark.parametrize("raw_rating", [True, [], {}, "not-rating", "6.0", "-1"])
def test_invalid_business_rating_becomes_missing(raw_rating: object) -> None:
    payload = fixture("poi_around_success.json")
    payload["pois"][0]["business"]["rating"] = raw_rating

    results = provider_for(
        lambda _: httpx.Response(200, json=payload)
    ).search(
        Coordinate(longitude=120.617, latitude=31.335),
        "苏州",
        (SceneryType.LAKE,),
        50,
    )

    assert results[0].rating is None


def test_radius_above_50_km_uses_text_and_locally_filters_far_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/place/text"
        assert "location" not in request.url.params
        assert "radius" not in request.url.params
        return httpx.Response(200, json=fixture("poi_text_success.json"))

    results = provider_for(handler).search(
        Coordinate(longitude=120.617, latitude=31.335),
        "苏州",
        (SceneryType.OLD_TOWN,),
        100,
    )
    assert [item.name for item in results] == ["同里古镇"]


def test_empty_around_search_falls_back_to_text_with_local_radius_filter() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v5/place/around":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": "0",
                    "pois": [],
                },
            )
        assert request.url.path == "/v5/place/text"
        assert "location" not in request.url.params
        assert "radius" not in request.url.params
        return httpx.Response(200, json=fixture("poi_around_success.json"))

    results = provider_for(handler).search(
        Coordinate(longitude=120.617, latitude=31.335),
        "苏州",
        (SceneryType.LAKE,),
        50,
    )

    assert calls == ["/v5/place/around", "/v5/place/text"]
    assert len(results) == 2
    assert SceneryType.LAKE in results[0].scenery_tags


def test_no_scenery_type_skips_http_and_malformed_declared_results_fail() -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called")

    assert (
        provider_for(forbidden).search(
            Coordinate(longitude=120, latitude=31), "苏州", (), 20
        )
        == []
    )

    malformed = {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": "1",
        "pois": [{"id": "broken", "name": "missing fields"}],
    }
    with pytest.raises(ProviderError) as captured:
        provider_for(lambda _: httpx.Response(200, json=malformed)).search(
            Coordinate(longitude=120, latitude=31),
            "苏州",
            (SceneryType.PARK,),
            20,
        )
    assert captured.value.code == "bad_response"


def test_distance_request_preserves_origin_order_and_converts_units() -> None:
    origins = [
        Origin(label="A", address="A", coordinate=Coordinate(longitude=120.1, latitude=31.1)),
        Origin(label="B", address="B", coordinate=Coordinate(longitude=120.2, latitude=31.2)),
    ]
    destination_provider = provider_for(
        lambda _: httpx.Response(200, json=fixture("poi_around_success.json"))
    )
    destination = destination_provider.search(
        Coordinate(longitude=120.6, latitude=31.3), "苏州", (SceneryType.LAKE,), 20
    )[0]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/distance"
        assert dict(request.url.params) == {
            "key": FAKE_KEY,
            "origins": "120.1,31.1|120.2,31.2",
            "destination": "120.7,31.32",
            "type": "1",
            "output": "json",
        }
        return httpx.Response(200, json=fixture("distance_success.json"))

    results = provider_for(handler).measure(origins, destination)
    assert [(item.origin_label, item.distance_km, item.duration_minutes) for item in results] == [
        ("A", 12.35, 30.0),
        ("B", 25.0, 60.0),
    ]
    assert all(item.estimated is False for item in results)


def test_distance_rejects_more_than_100_origins_and_partial_results() -> None:
    coordinate = Coordinate(longitude=120, latitude=31)
    origins = [Origin(label=str(index), address="x", coordinate=coordinate) for index in range(101)]
    destination_provider = provider_for(
        lambda _: httpx.Response(200, json=fixture("poi_around_success.json"))
    )
    destination = destination_provider.search(
        coordinate, "苏州", (SceneryType.LAKE,), 20
    )[0]
    with pytest.raises(ProviderError) as too_many:
        provider_for(lambda _: pytest.fail("HTTP should not be called")).measure(
            origins, destination
        )
    assert too_many.value.code == "bad_request"

    with pytest.raises(ProviderError) as partial:
        provider_for(lambda _: httpx.Response(200, json={
            "status": "1", "info": "OK", "infocode": "10000", "results": []
        })).measure(origins[:1], destination)
    assert partial.value.code == "bad_response"
