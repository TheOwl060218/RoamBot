import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from roambot.domain.discovery import (
    BatchReview,
    DiscoveryRequest,
    Finish,
    InspectPlaces,
    PlaceIds,
    Publish,
    SearchContext,
    SearchEvidence,
    SearchPlaces,
)
from roambot.domain.models import Coordinate, Origin
from roambot.providers.discovery import (
    DiscoveryMap,
    InvalidDiscoveryStep,
    PublicSearch,
    TavilySearch,
    model_step,
    normalized_arguments,
    safe_public_url,
    source_mentions_place,
)
from roambot.providers.protocols import ProviderError
from roambot.services.discovery import DiscoveryRun, model_tool_view


class Maps:
    def __init__(self):
        self.calls = []

    def gps(self, point):
        self.calls.append(("gps", point.system))
        return point.model_copy(update={"system": "gcj02"})

    def geocode(self, name):
        self.calls.append(("geocode", name))
        return Origin(label=name, address=name, coordinate=Coordinate(longitude=120, latitude=31))

    def search(self, query, region, center, radius):
        self.calls.append(("search", query, region, center, radius))
        return [
            dict(
                id=f"amap:{i}",
                name=name,
                address="实际地址",
                city="苏州",
                coordinate={"longitude": 120, "latitude": 31, "system": "gcj02"},
                map_type="不属于旧六类",
                facts={},
                map_url=f"https://www.amap.com/detail/{i}",
            )
            for i, name in enumerate(("独立书店", "湖边绿地", "城市展览", "另一家书店"), 1)
        ]

    def route(self, center, place, mode):
        self.calls.append(("route", place["id"], mode))
        return {
            "mode": mode,
            "distance_km": 6.4 if place["id"] == "amap:4" else 4.2,
            "duration_minutes": 45,
            "estimated": False,
        }


class Web:
    def search(self, query):
        return [
            {
                "title": "场地介绍",
                "url": "https://example.org/venue",
                "excerpt": "独立书店介绍正文摘要",
                "kind": "search_excerpt",
            }
        ]


class Weather:
    def __init__(self):
        self.calls = []

    def daily(self, *args):
        self.calls.append(args)
        return []


def run(message="去苏州看看独立书店", **kwargs):
    return DiscoveryRun(DiscoveryRequest(message=message, **kwargs), Maps(), Weather(), Web(), None)


def load_places(agent):
    agent.act("set_context", SearchContext(region="苏州"))
    return agent.act("search_places", SearchPlaces(query="独立书店"))


def card(index, experience="看书", sources=None):
    return {
        "place_id": f"amap:{index}",
        "experience": experience,
        "reason": "依据已经检索到的地点资料，这个去处值得放进本次比较的选择之中。",
        "evidence_ids": sources or [f"e{index}"],
    }


def test_open_ended_place_does_not_require_date_origin_or_old_scenery_type():
    agent = run()
    found = load_places(agent)
    agent.act("publish_batch", Publish(cards=[card(1)]))
    snap = agent.snapshot()
    assert found[0]["map_type"] == "不属于旧六类"
    assert snap["cards"][0]["place"]["name"] == "独立书店"
    assert snap["cards"][0]["route"] is None and snap["cards"][0]["weather"] is None
    assert snap["context"]["start_date"] is None
    assert "score" not in snap["cards"][0]
    assert not agent.weather.calls
    assert all(c[0] != "route" for c in agent.maps.calls)


def test_missing_dimensions_cannot_be_silently_added_or_queried():
    agent = run()
    load_places(agent)
    with pytest.raises(ValueError, match="未提供日期"):
        agent.act("check_weather", PlaceIds(place_ids=["amap:1"]))
    with pytest.raises(ValueError, match="没有出发地"):
        agent.act("measure_routes", PlaceIds(place_ids=["amap:1"]))
    with pytest.raises(ValueError, match="原文证据"):
        agent.act("set_context", SearchContext(origin="北京", region="苏州"))
    with pytest.raises(ValueError, match="原文证据"):
        agent.act(
            "set_context",
            SearchContext(region="苏州", start_date=date.today(), end_date=date.today()),
        )


def test_actual_walking_route_enforces_limit_without_falling_back_to_straight_line():
    agent = run(
        "从苏州站出发，5km内看看", location=Coordinate(longitude=121, latitude=32, system="wgs84")
    )
    agent.act(
        "set_context",
        SearchContext(
            origin="苏州站", origin_quote="从苏州站出发", max_distance_km=5, distance_quote="5km内"
        ),
    )
    agent.act("search_places", SearchPlaces(query="书店"))
    with pytest.raises(ValueError, match="核实实际路线"):
        agent.act("publish_batch", Publish(cards=[card(1)]))
    agent.act("measure_routes", PlaceIds(place_ids=["amap:1", "amap:4"]))
    agent.act("publish_batch", Publish(cards=[card(1)]))
    with pytest.raises(ValueError, match="距离上限"):
        agent.act("publish_batch", Publish(cards=[card(4)]))
    assert agent.center_name == "苏州站"
    assert ("route", "amap:1", "walking") in agent.maps.calls
    assert not any(c[0] == "gps" for c in agent.maps.calls)


def test_free_form_experience_interleaving_is_stable_across_batches():
    agent = run()
    load_places(agent)
    agent.act(
        "publish_batch", Publish(cards=[card(1), card(4), card(2, "水边休息"), card(3, "看展")])
    )
    assert [c["place"]["id"] for c in agent.cards] == ["amap:1", "amap:2", "amap:3", "amap:4"]
    before = list(agent.cards)
    with pytest.raises(ValueError, match="重复"):
        agent.act("publish_batch", Publish(cards=[card(1)]))
    assert agent.cards == before


def test_reasons_cannot_cite_fabricated_or_other_place_evidence():
    agent = run()
    load_places(agent)
    for proof in ("missing", "e2"):
        with pytest.raises(ValueError, match="证据"):
            agent.act("publish_batch", Publish(cards=[card(1, sources=[proof])]))
    evidence = agent.act(
        "search_evidence", SearchEvidence(query="独立书店 介绍", place_ids=["amap:1"])
    )
    agent.act("publish_batch", Publish(cards=[card(1, sources=[evidence["evidence"][0]["id"]])]))
    assert agent.cards[0]["sources"][0]["excerpt"] == "独立书店介绍正文摘要"


def test_condition_changes_after_publish_require_a_new_turn():
    agent = run("去苏州或杭州看看")
    load_places(agent)
    agent.act("publish_batch", Publish(cards=[card(1)]))
    with pytest.raises(ValueError, match="下一轮"):
        agent.act("set_context", SearchContext(region="杭州"))


def test_model_gets_full_original_message_and_latest_dialogue_not_just_labels():
    original = "今天不想看景点，想找本小众摄影集坐着翻翻"
    agent = run(original)
    assert original in agent.messages[1]["content"]
    agent.act("finish", Finish(reply="已找到一些不同的去处。"))
    continuation = DiscoveryRun(
        DiscoveryRequest(message="这次改成杭州"), Maps(), Weather(), Web(), None, agent.snapshot()
    )
    assert original in continuation.messages[1]["content"]
    assert "这次改成杭州" in continuation.messages[1]["content"]


def test_public_search_returns_real_excerpt_urls_and_never_fetches_result_pages():
    calls = []

    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            text=(
                "<rss><channel><item><title>介绍</title><link>https://exam"
                "ple.org/a</link><description>一片开放绿地</description></item"
                "></channel></rss>"
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        results = PublicSearch(client).search("绿地")
    assert len(calls) == 1 and calls[0].startswith("https://cn.bing.com/search?")
    assert results[0]["excerpt"] == "一片开放绿地"
    assert results[0]["kind"] == "search_excerpt"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://127.0.0.1/a",
        "https://[::1]/a",
        "https://user:secret@example.org",
        "https://example.org:8443/a",
    ],
)
def test_public_links_reject_unsafe_schemes_hosts_and_credentials(url):
    assert safe_public_url(url) is None


def test_map_route_uses_requested_mode_and_real_provider_distance():
    calls = []

    def get(**kwargs):
        calls.append(kwargs)
        return {
            "status": "1",
            "infocode": "10000",
            "route": {"paths": [{"distance": "4200", "duration": "2400"}]},
        }

    amap = SimpleNamespace(
        _api_key="not-a-real-key",
        _http=SimpleNamespace(get_json=get),
        _require_success=lambda data: None,
    )
    route = DiscoveryMap(amap).route(
        Coordinate(longitude=120, latitude=31),
        {"coordinate": {"longitude": 120.02, "latitude": 31}},
        "walking",
    )
    assert calls[0]["path"] == "/v3/direction/walking"
    assert route == {
        "mode": "walking",
        "distance_km": 4.2,
        "duration_minutes": 40,
        "estimated": False,
    }


def test_model_schema_cannot_invent_place_ids_or_unknown_destructive_tools():
    def post(**kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "take_discovery_step",
                                    "arguments": json.dumps(
                                        {"tool": "delete_all", "arguments": {}}
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }

    provider = SimpleNamespace(
        _http=SimpleNamespace(post_json=post),
        _key="fake",
        _model="unchanged",
        _enable_thinking=False,
    )
    with pytest.raises(ProviderError):
        model_step(provider, [])


def test_partial_context_updates_preserve_unmentioned_information():
    agent = run("从苏州站出发，5km内看看，改去杭州也可以")
    agent.configure(
        SearchContext(
            origin="苏州站",
            origin_quote="从苏州站出发",
            max_distance_km=5,
            distance_quote="5km内",
            travel_mode="bicycling",
        )
    )
    agent.configure(SearchContext(region="杭州"))
    assert agent.context.origin == "苏州站"
    assert agent.context.max_distance_km == 5
    assert agent.context.travel_mode == "bicycling"


def test_invalid_model_parameters_return_feedback_instead_of_silent_retry_or_execution():
    agent = run()
    calls = []

    def step(messages):
        calls.append(messages[-1]["content"])
        if len(calls) == 1:
            raise InvalidDiscoveryStep([{"field": ["place_ids"], "type": "too_long"}])
        return "finish", Finish(reply="先查看苏州的不同去处。")

    agent.step = step
    agent.run()
    assert len(calls) == 2
    assert "too_long" in calls[1]
    assert not agent.maps.calls
    assert agent.status == "completed"


def test_cancellation_after_model_return_does_not_start_another_provider_call():
    agent = run()

    def step(messages):
        agent.cancelled.set()
        return "search_places", SearchPlaces(query="书店")

    agent.step = step
    agent.run()
    assert agent.status == "cancelled"
    assert not agent.maps.calls


def test_json_encoded_arrays_are_representation_only_and_do_not_bypass_id_checks():
    value = normalized_arguments(
        SearchEvidence, {"query": "地点资料", "place_ids": '["not-a-real-id"]'}
    )
    args = SearchEvidence.model_validate(value)
    agent = run()
    load_places(agent)
    with pytest.raises(ValueError, match="真实地点ID"):
        agent.act("search_evidence", args)
    assert (
        normalized_arguments(SearchEvidence, {"query": "资料", "place_ids": "[]"})["place_ids"]
        == []
    )


def test_unrelated_same_word_pages_are_not_bound_to_a_place():
    place = {"name": "紫藤花园口袋公园", "city": "苏州市"}
    assert not source_mentions_place(
        place, {"title": "紫藤植物百科", "excerpt": "紫藤可栽种在湖畔"}
    )
    assert source_mentions_place(
        place, {"title": "紫藤花园口袋公园介绍", "excerpt": "场地实际介绍"}
    )


def test_evidence_review_can_reject_a_plausible_but_unsupported_reason():
    agent = run()
    load_places(agent)
    agent.review = lambda cards: BatchReview(
        approved_ids=[],
        rejected=[{"place_id": "amap:1", "note": "资料没有证明该地点存在所需设施。"}],
    )
    result = agent.act("publish_batch", Publish(cards=[card(1)]))
    assert result["published"] == 0
    assert not agent.cards and agent.first_batch_ms is None


def test_tavily_adapter_uses_fixed_endpoint_and_query_focused_chunks_without_full_page():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/place",
                        "title": "地点官方介绍",
                        "content": "摘要",
                        "raw_content": "真实网页正文",
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = TavilySearch("fake-not-real", client).search("地点资料")
    assert str(calls[0].url) == "https://api.tavily.com/search"
    assert json.loads(calls[0].content)["search_depth"] == "basic"
    assert json.loads(calls[0].content)["include_raw_content"] is False
    assert json.loads(calls[0].content)["include_usage"] is True
    assert result[0]["kind"] == "search_excerpt"
    assert result[0]["excerpt"] == "摘要"


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_tavily_preserves_http_failure_category_without_response_body_or_retry(status):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"detail": "private-provider-body"})
        )
    ) as client:
        search = TavilySearch("not-a-credential", client)
        with pytest.raises(ProviderError) as caught:
            search.search("公开地点资料")
    assert caught.value.code == "tavily_http_" + str(status)
    assert "private-provider-body" not in str(caught.value)
    assert search.request_count == 1


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (httpx.ReadTimeout, "tavily_timeout"),
        (httpx.ProxyError, "tavily_proxy_error"),
        (httpx.ConnectError, "tavily_connect_error"),
    ],
)
def test_tavily_preserves_transport_failure_category_without_retry(failure, code):
    def fail(request):
        raise failure("private-transport-details", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        search = TavilySearch("not-a-credential", client)
        with pytest.raises(ProviderError) as caught:
            search.search("公开地点资料")
    assert caught.value.code == code
    assert "private-transport-details" not in str(caught.value)
    assert search.request_count == 1


def test_model_tool_view_preserves_all_entities_and_valid_json_for_large_evidence():
    result = [{"id": f"e{i}", "place_id": f"amap:{i}", "excerpt": "资料" * 8000} for i in range(18)]
    value = json.loads(json.dumps(model_tool_view(result), ensure_ascii=False))
    assert len(value) == 18
    assert value[-1]["id"] == "e17" and value[-1]["place_id"] == "amap:17"
    assert len(value[0]["excerpt"]) == 1200
    assert len(result[0]["excerpt"]) == 16000


def test_web_first_discovery_reuses_original_source_after_map_entity_verification():
    agent = run()
    agent.configure(SearchContext(region="苏州"))
    queries = []

    def search(query):
        queries.append(query)
        return [
            {
                "url": "https://example.org/bookshop",
                "title": "苏州独立书店介绍",
                "excerpt": "独立书店有摄影集阅览区。",
                "kind": "web_page",
            }
        ]

    agent.search.search = search
    initial = agent.act("search_evidence", SearchEvidence(query="摄影集 阅览空间"))
    assert initial["research_results"] and not agent.evidence
    places = agent.act("search_places", SearchPlaces(query="独立书店"))
    assert queries == ["苏州 摄影集 阅览空间"]
    evidence = places[0]["public_evidence"][0]
    assert evidence["place_id"] == "amap:1"
    assert evidence["url"] == "https://example.org/bookshop"
    assert "public_evidence" not in places[1]
    assert len(queries) == 1


def test_inspection_does_not_spend_web_searches_on_places_outside_hard_route_cap():
    agent = run("从苏州站出发，步行5公里内")
    agent.configure(
        SearchContext(
            origin="苏州站",
            origin_quote="从苏州站出发",
            max_distance_km=5,
            distance_quote="步行5公里内",
        )
    )
    agent.act("search_places", SearchPlaces(query="公园"))
    queries = []
    agent.search.search = lambda query: queries.append(query) or []
    result = agent.act(
        "inspect_places", InspectPlaces(place_ids=["amap:4"], research_focus="活动设施")
    )
    assert result and agent.routes["amap:4"]["distance_km"] > 5
    assert queries == []


def test_new_places_discovered_after_initial_searches_can_still_be_map_verified():
    agent = run()
    steps = iter(
        [
            ("set_context", SearchContext(region="苏州")),
            ("search_places", SearchPlaces(query="书店")),
            ("search_places", SearchPlaces(query="展览")),
            ("search_places", SearchPlaces(query="公开资料中新发现的地点")),
            ("finish", Finish(reply="已核实本轮检索到的具体地点。")),
        ]
    )
    agent.step = lambda messages: next(steps)
    agent.run()
    searches = [call for call in agent.maps.calls if call[0] == "search"]
    assert len(searches) == 3
    assert searches[-1][1] == "公开资料中新发现的地点"
    assert not agent.errors
