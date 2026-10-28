"""Source-first execution boundaries; no semantic quality claims."""

import pytest
from test_discovery import Maps, Weather

from roambot.domain.discovery import DiscoveryRequest, RetrievalPlan, SearchContext
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.services.discovery_sources import DiscoverySourceWorkflow, SourceNomination
from roambot.services.discovery_tasks import TaskSelection


class Search:
    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return [
            {
                "kind": "search_excerpt",
                "url": "https://example.org/book",
                "title": "具体介绍",
                "excerpt": "独立书店设有阅读座位。另有湖边绿地的资料链接。",
            },
            {
                "kind": "search_excerpt",
                "url": "https://example.org/lake",
                "title": "湖边绿地",
                "excerpt": "湖边绿地是一处可沿湖散步的公共空间。",
            },
        ]


class Model:
    version = "offline-source-boundary"

    def __init__(self):
        self.calls = []
        self.invalid = False
        self.map_only = False

    def plan(self, *args):
        self.calls.append("plan")
        return RetrievalPlan(
            context=SearchContext(region="苏州"), goal="放松", web_queries=["换个环境放松"]
        )

    def nominate_sources(self, conversation, context, documents):
        self.calls.append("nominate")
        assert documents[0]["url"] == "https://example.org/book"
        return SourceNomination(
            venues=[
                {"name": "独立书店", "source_ids": ["invented" if self.invalid else "s1"]},
                *([] if self.invalid else [{"name": "湖边绿地", "source_ids": ["s2"]}]),
            ]
        )

    def choose(self, conversation, context, cards, published):
        self.calls.append("choose")
        for card in cards:
            urls = {s["url"] for s in card["sources"] if s["kind"] == "search_excerpt"}
            assert urls == {
                "https://example.org/book"
                if card["place"]["id"] == "amap:1"
                else "https://example.org/lake"
            }
        card = cards[0]
        ref = next(
            s
            for s in card["sources"]
            if s["kind"] == ("map_record" if self.map_only else "search_excerpt")
        )
        return TaskSelection(
            cards=[
                {
                    "place_id": card["place"]["id"],
                    "experience": "阅读休闲",
                    "reason": "公开资料提到阅读座位，可作为这次换个环境放松的候选去处。",
                    "evidence_ids": [ref["id"]],
                }
            ]
        )


def workflow(tmp_path):
    model = Model()
    return DiscoverySourceWorkflow(
        DiscoveryRequest(message="换个环境放松"),
        Maps(),
        Weather(),
        Search(),
        model,
        DiscoveryCache(tmp_path / "source.sqlite3"),
        "isolated-source-actor",
    ), model


def test_followup_region_update_ignores_clearing_already_empty_conditions(tmp_path):
    run, _ = workflow(tmp_path)
    run.context = SearchContext(region="北京")
    # Shape returned by the approved real-model diagnostic: valid region update,
    # but redundant deletes of two absent optional conditions without a quote.
    plan = RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="去苏州赏秋",
        clear_fields=["origin", "max_distance_km"],
    )
    value = run.plan_context(plan)
    assert value.region == "苏州"
    assert value.origin is None and value.max_distance_km is None
    assert "origin" not in value.model_fields_set
    assert "max_distance_km" not in value.model_fields_set


@pytest.mark.parametrize(
    "field,context",
    [
        ("origin", {"origin": "已有出发地"}),
        ("region", {"region": "已有地区"}),
        ("max_distance_km", {"max_distance_km": 5}),
    ],
)
def test_effective_condition_delete_still_requires_user_evidence(tmp_path, field, context):
    run, _ = workflow(tmp_path)
    run.context = SearchContext(**context)
    with pytest.raises(ValueError, match="清空条件需要明确原文依据"):
        run.plan_context(
            RetrievalPlan(context=SearchContext(), goal="看看去处", clear_fields=[field])
        )


def test_clear_cannot_silently_override_a_newly_set_value(tmp_path):
    run, _ = workflow(tmp_path)
    with pytest.raises(ValueError, match="清空条件需要明确原文依据"):
        run.plan_context(
            RetrievalPlan(
                context=SearchContext(origin="新出发地"), goal="看看去处", clear_fields=["origin"]
            )
        )


def test_quoted_clear_keeps_existing_clear_behavior(tmp_path):
    run, _ = workflow(tmp_path)
    run.context = SearchContext(region="已有地区")
    run.turns = [{"role": "user", "content": "取消地区限制"}]
    value = run.plan_context(
        RetrievalPlan(
            context=SearchContext(),
            goal="看看去处",
            clear_fields=["region", "origin"],
            clear_quote="取消地区限制",
        )
    )
    assert value.region is None
    assert "region" in value.model_fields_set
    assert "origin" not in value.model_fields_set


def test_public_progress_is_optional_and_cannot_change_execution(tmp_path):
    run, model = workflow(tmp_path)
    model.public_note = "这次想换个环境，我会先看看能轻松停留的去处。"
    nominate = model.nominate_sources

    def narrated(*args):
        return nominate(*args).model_copy(
            update={"public_note": "接下来会核对这些候选的具体位置，再比较适合的去处。"}
        )

    model.nominate_sources = narrated
    run.run()
    assert run.status == "completed", run.errors
    assert model.calls == ["plan", "nominate", "choose"]
    assert run.budget.counts == {"model": 3, "search": 1}
    assert run.context.region == "苏州"
    assert run.search.queries == ["苏州 换个环境放松"]
    assert run.cards[0]["place"]["id"] == "amap:1"
    notes = run.snapshot()["progress_notes"]
    assert notes[0] == model.public_note
    assert notes[2] == "接下来会核对这些候选的具体位置，再比较适合的去处。"
    assert len(notes) > 3
    assert any("2 个候选" in note for note in notes)
    count = len(notes)
    notes.clear()
    assert len(run.snapshot()["progress_notes"]) == count
    assert "public_note" not in run.plan.model_dump()


def test_progress_stays_per_run_and_bounded_without_discarding_after_three_lines(tmp_path):
    run, _ = workflow(tmp_path)
    other, _ = workflow(tmp_path)
    for i in range(30):
        run.note_progress(f"实际阶段{i}")
    assert len(run.snapshot()["progress_notes"]) == 24
    assert run.snapshot()["progress_notes"][0] == "实际阶段6"
    assert other.snapshot()["progress_notes"] == []


@pytest.mark.parametrize("invalid", [None, 123, [], {"text": "ignored"}, " ", "字" * 101])
def test_bad_decorative_copy_does_not_reject_valid_nomination(invalid):
    value = SourceNomination(venues=[{"name": "独立书店"}], public_note=invalid)
    assert value.public_note is None
    assert value.venues[0].name == "独立书店"


def test_source_first_binds_public_evidence_and_never_reselects_omitted_venues(tmp_path):
    run, model = workflow(tmp_path)
    run.run()
    assert run.status == "completed", run.errors
    assert len(run.cards) == 1
    assert model.calls == ["plan", "nominate", "choose"]
    assert run.budget.counts == {"model": 3, "search": 1}
    assert run.snapshot()["workflow"] == "source-first-v2"
    assert run.cards[0]["sources"][0]["kind"] == "search_excerpt"
    assert run.search.queries == ["苏州 换个环境放松"]


def test_open_candidates_keep_nine_actual_places_without_per_place_web_gate(tmp_path):
    from roambot.services.discovery_sources import SelectedPlace, SelectedPlaces

    run, model = workflow(tmp_path)
    model.expanded_candidates = True
    template = run.maps.search("", None, None, None)[0]
    run.maps.search = lambda name, *args: [template | {"id": "amap:" + name, "name": name}]

    def nominate(*args):
        model.calls.append("nominate")
        return SourceNomination(venues=[{"name": "去处" + str(i)} for i in range(9)])

    def choose(conversation, context, cards, published):
        model.calls.append("choose")
        return SelectedPlaces(
            cards=[
                SelectedPlace(
                    place_id=c["place"]["id"],
                    experience="休闲",
                    evidence_ids=[next(s["id"] for s in c["sources"] if s["kind"] == "map_record")],
                )
                for c in cards
            ]
        )

    model.nominate_sources, model.choose = nominate, choose
    run.run()
    assert run.status == "completed", run.errors
    assert len(run.cards) == 9
    assert all(card["reason"] == "" for card in run.cards)
    assert model.calls == ["plan", "nominate", "choose"]
    assert len({card["place"]["id"] for card in run.cards}) == 9


def test_open_candidates_do_not_borrow_nominee_evidence_for_neighboring_places(tmp_path):
    run, model = workflow(tmp_path)
    model.expanded_candidates = True
    search = run.maps.search
    run.maps.search = lambda *args: [
        p | {"id": p["id"] + "-neighbor", "name": "相邻地点" + p["id"]} for p in search(*args)
    ]
    model.choose = lambda conversation, context, cards, published: TaskSelection(cards=[])
    run.run()
    assert run.places
    for card in run.candidate_facts(list(run.places)):
        assert all(s["kind"] == "map_record" for s in card["sources"])


def test_open_candidates_still_verify_map_places_when_public_search_is_empty(tmp_path):
    from roambot.services.discovery_sources import SelectedPlace, SelectedPlaces

    run, model = workflow(tmp_path)
    model.expanded_candidates = True
    run.search.search = lambda query: []

    def nominate(conversation, context, documents):
        model.calls.append("nominate")
        assert documents == []
        return SourceNomination(venues=[{"name": "独立书店"}])

    def choose(conversation, context, cards, published):
        model.calls.append("choose")
        return SelectedPlaces(
            cards=[
                SelectedPlace(
                    place_id=c["place"]["id"],
                    experience="休闲",
                    evidence_ids=[next(s["id"] for s in c["sources"] if s["kind"] == "map_record")],
                )
                for c in cards
            ]
        )

    model.nominate_sources, model.choose = nominate, choose
    run.run()
    assert run.cards and run.status == "completed", run.errors
    assert model.calls == ["plan", "nominate", "choose"]
    assert all(s["kind"] == "map_record" for c in run.cards for s in c["sources"])


def test_open_selection_sees_provider_alternatives_beyond_first_twelve(tmp_path):
    from roambot.services.discovery_sources import SelectedPlace, SelectedPlaces

    run, model = workflow(tmp_path)
    model.expanded_candidates = True
    template = run.maps.search("", None, None, None)[0]
    run.maps.search = lambda name, *args: [
        template | {"id": f"amap:{name}:{i}", "name": f"{name}对象{i}"} for i in range(3)
    ]
    model.nominate_sources = lambda *args: SourceNomination(
        venues=[{"name": f"区域{i}"} for i in range(12)]
    )

    def choose(conversation, context, cards, published):
        model.calls.append("choose")
        assert len(cards) == 24
        assert [c["place"]["id"] for c in cards][12:] == [f"amap:区域{i}:1" for i in range(12)]
        selected = cards[-1]
        return SelectedPlaces(
            cards=[
                SelectedPlace(
                    place_id=selected["place"]["id"],
                    experience="休闲",
                    evidence_ids=[
                        next(s["id"] for s in selected["sources"] if s["kind"] == "map_record")
                    ],
                )
            ]
        )

    model.choose = choose
    run.run()
    assert run.status == "completed", run.errors
    assert run.cards[0]["place"]["id"] == "amap:区域11:1"
    assert model.calls.count("choose") == 1


def test_current_request_survives_trimmed_dialogue_and_reaches_each_model_stage(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from roambot.services.discovery_sources import DiscoverySourceModel, PlacePicks, SourceIntake

    old = "南京看老建筑与水景，不去寺庙或商场"
    updated = "扬州看老建筑与水景，不去寺庙或商场"
    turns = [{"role": "user", "content": old}]
    for i in range(5):
        turns += [
            {"role": "assistant", "content": "已更新"},
            {"role": "user", "content": f"继续比较{i}"},
        ]
    seen = []

    def structured(provider, name, schema, instructions, data, tokens, *, recover_truncated=None):
        seen.append((name, data))
        if name == "plan_source_request":
            assert data["current_search_request"] == old
            assert old not in [t["content"] for t in data["conversation"]]
            return SourceIntake(
                intent="search",
                context={"region": "扬州"},
                temporal=None,
                search_scope={"kind": "region", "region": "扬州"},
                research_query=updated,
                display_title="扬州的老建筑与水景",
            )
        assert data["current_search_request"] == updated
        if name == "nominate_source_places":
            return SourceNomination(venues=[{"name": "独立书店"}])
        return PlacePicks(cards=[{"ref": "p1", "destination_ref": "p1", "experience": "休闲"}])

    monkeypatch.setattr("roambot.services.discovery_sources.structured_call", structured)
    run = DiscoverySourceWorkflow(
        DiscoveryRequest(message="改成扬州"),
        Maps(),
        Weather(),
        Search(),
        DiscoverySourceModel(SimpleNamespace(_model="offline")),
        DiscoveryCache(tmp_path / "request.sqlite3"),
        "request-owner",
        previous={
            "context": {"region": "南京"},
            "conversation": turns,
            "cards": [],
            "search_request": old,
        },
    )
    run.run()
    assert run.status == "completed", run.errors
    assert len(seen) == 3
    assert run.snapshot()["search_request"] == updated
    assert run.snapshot()["display_title"] == "扬州的老建筑与水景"


def test_request_state_is_part_of_planning_cache_key_and_new_intent_replaces_it(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from roambot.services.discovery_sources import DiscoverySourceModel, PlacePicks, SourceIntake

    planned = []

    def structured(provider, name, schema, instructions, data, tokens, *, recover_truncated=None):
        if name == "plan_source_request":
            planned.append(data["current_search_request"])
            return SourceIntake(
                intent="search",
                context={"region": "苏州"},
                temporal=None,
                search_scope={"kind": "region", "region": "苏州"},
                research_query="现在想找书店",
            )
        assert data["current_search_request"] == "现在想找书店"
        if name == "nominate_source_places":
            return SourceNomination(venues=[{"name": "独立书店"}])
        return PlacePicks(cards=[{"ref": "p1", "destination_ref": "p1", "experience": "阅读"}])

    monkeypatch.setattr("roambot.services.discovery_sources.structured_call", structured)
    cache = DiscoveryCache(tmp_path / "shared.sqlite3")
    for old in ("旧活动甲", "旧活动乙"):
        run = DiscoverySourceWorkflow(
            DiscoveryRequest(message="换个想法，找书店"),
            Maps(),
            Weather(),
            Search(),
            DiscoverySourceModel(SimpleNamespace(_model="offline")),
            cache,
            "same-owner",
            previous={
                "context": {"region": "苏州"},
                "cards": [],
                "conversation": [],
                "search_request": old,
            },
        )
        run.run()
        assert run.status == "completed", run.errors
        assert run.snapshot()["search_request"] == "现在想找书店"
    assert planned == ["旧活动甲", "旧活动乙"]


def test_trimmed_dialogue_can_keep_accepted_context_but_cannot_invent_a_changed_origin(tmp_path):
    from datetime import date, timedelta

    from roambot.services.discovery import DiscoveryRun

    tomorrow = date.today() + timedelta(days=1)
    context = SearchContext(
        origin="苏州站",
        origin_quote="从苏州站出发",
        max_distance_km=5,
        distance_quote="五公里内",
        start_date=tomorrow,
        end_date=tomorrow,
        date_quote="明天",
    )
    run = DiscoveryRun(
        DiscoveryRequest(message="再多给一些"),
        None,
        None,
        None,
        None,
        previous={"context": context.model_dump(mode="json"), "conversation": [], "cards": []},
    )
    assert run.validate_context_evidence(context) == context
    with pytest.raises(ValueError, match="origin"):
        run.validate_context_evidence(SearchContext(origin="杭州站", origin_quote="从苏州站出发"))
    with pytest.raises(ValueError, match="start_date"):
        run.validate_context_evidence(
            SearchContext(
                start_date=tomorrow, end_date=tomorrow + timedelta(days=1), date_quote="明天"
            )
        )


def test_invented_public_reference_cannot_trigger_map_or_selection(tmp_path):
    run, model = workflow(tmp_path)
    model.invalid = True
    run.maps.search = lambda *args: pytest.fail("Unbound nomination must not spend a map request")
    run.run()
    assert not run.cards and run.status == "failed"
    assert model.calls == ["plan", "nominate"]


def test_open_nomination_discards_wrong_citation_without_discarding_map_verifiable_lead(tmp_path):
    from roambot.services.discovery_sources import SelectedPlace, SelectedPlaces

    run, model = workflow(tmp_path)
    model.expanded_candidates = True
    calls = []
    search = run.maps.search

    def maps(*args):
        calls.append(args[0])
        return search(*args)

    run.maps.search = maps
    model.nominate_sources = lambda *args: SourceNomination(
        venues=[
            {"name": "独立书店", "source_ids": ["s2", "invented"]},
            {"name": "湖边绿地", "source_ids": ["s2", "s2"]},
        ]
    )

    def choose(conversation, context, cards, published):
        for card in cards:
            if card["place"]["name"] == "独立书店":
                assert all(s["kind"] == "map_record" for s in card["sources"])
        return SelectedPlaces(
            cards=[
                SelectedPlace(
                    place_id=c["place"]["id"],
                    experience="休闲",
                    evidence_ids=[next(s["id"] for s in c["sources"] if s["kind"] == "map_record")],
                )
                for c in cards
            ]
        )

    model.choose = choose
    run.run()
    assert sorted(calls) == sorted(["独立书店", "湖边绿地"])
    assert run.cards and run.status == "partial"
    assert sum(e["code"] == "unbound_source_venue" for e in run.errors) == 2
    for card in run.cards:
        assert all(s["id"] != "invented" for s in card["sources"])
        assert card["place"]["id"] in run.places


def test_map_category_alone_cannot_publish_in_source_first_mode(tmp_path):
    run, model = workflow(tmp_path)
    model.map_only = True
    run.run()
    assert not run.cards and run.status == "failed"
    assert model.calls == ["plan", "nominate", "choose"]


def test_name_of_child_or_other_branch_does_not_verify_source_venue_identity(tmp_path):
    run, model = workflow(tmp_path)
    search = run.maps.search
    run.maps.search = lambda *args: [p | {"name": p["name"] + "(另一分馆)"} for p in search(*args)]
    run.run()
    assert not run.cards and run.status == "failed"
    assert model.calls == ["plan", "nominate"]


def test_map_city_prefix_resolves_without_losing_actual_source_paragraph(tmp_path):
    run, model = workflow(tmp_path)
    search = run.maps.search
    run.maps.search = lambda *args: [
        place | {"name": "苏州市" + place["name"]} for place in search(*args)
    ]
    run.run()
    assert run.status == "completed", run.errors
    assert run.cards[0]["place"]["name"] == "苏州市独立书店"
    assert "独立书店设有阅读座位" in run.cards[0]["sources"][0]["excerpt"]
    assert model.calls == ["plan", "nominate", "choose"]


def test_city_prefix_does_not_merge_distinct_map_ids(tmp_path):
    run, model = workflow(tmp_path)
    search = run.maps.search

    def ambiguous(*args):
        return [
            variant
            for place in search(*args)
            for variant in (
                place | {"name": "苏州" + place["name"]},
                place | {"id": place["id"] + "-other", "name": "苏州市" + place["name"]},
            )
        ]

    run.maps.search = ambiguous
    run.run()
    assert not run.cards and run.status == "failed"
    assert model.calls == ["plan", "nominate"]


def test_device_location_supplies_coarse_search_area_without_manual_city_or_coordinate_query(
    tmp_path,
):
    from roambot.domain.models import Coordinate

    run, model = workflow(tmp_path)
    run.body.message = "在附近找个地方放松"
    run.turns[-1]["content"] = run.body.message
    run.location = Coordinate(longitude=120, latitude=31, system="wgs84")
    run.body.location = run.location
    original = model.plan

    def plan(*args):
        value = original(*args)
        value.context = SearchContext()
        value.nearby_quote = "在附近"
        return value

    model.plan = plan
    areas = []

    def area(point):
        areas.append(point.system)
        return "苏州市 姑苏区"

    run.maps.area = area
    run.run()
    assert run.status == "completed", run.errors
    assert areas == ["gcj02"]
    assert run.context.region is None and run.context.origin is None
    assert run.search.queries == ["苏州市 姑苏区 换个环境放松"]
    assert model.calls == ["plan", "nominate", "choose"]


def test_source_planner_has_public_question_contract_without_map_category_directions():
    import json
    from types import SimpleNamespace

    from roambot.services.discovery_sources import DiscoverySourceModel

    calls = []

    def native(**kwargs):
        calls.append(kwargs["json_body"])
        data = {
            "intent": "search",
            "context": {"region": "苏州"},
            "temporal": None,
            "search_scope": {"kind": "region", "region": "苏州"},
            "research_query": "可坐下来阅读的独立空间",
        }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "plan_source_request",
                                    "arguments": json.dumps(data),
                                }
                            }
                        ]
                    },
                }
            ]
        }

    provider = SimpleNamespace(
        _model="offline-native",
        _key="not-a-credential",
        _enable_thinking=False,
        _http=SimpleNamespace(post_json=native),
    )
    result = DiscoverySourceModel(provider).plan(
        [{"role": "user", "content": "苏州找地方坐着看书"}], {}, False, []
    )
    assert result.web_queries == ["可坐下来阅读的独立空间"] and not result.directions
    schema = calls[0]["tools"][0]["function"]["parameters"]
    assert "research_query" in schema["properties"] and "directions" not in schema["properties"]


@pytest.mark.parametrize(
    "address, expected",
    [
        ({"province": "江苏省", "city": "苏州市", "district": "姑苏区"}, "江苏省 苏州市 姑苏区"),
        ({"province": "上海市", "city": [], "district": "浦东新区"}, "上海市 浦东新区"),
        ({}, None),
        (None, None),
    ],
)
def test_reverse_area_keeps_only_administrative_scope(address, expected):
    from roambot.domain.models import Coordinate
    from roambot.providers.amap import AMapProvider
    from roambot.providers.discovery import DiscoveryMap
    from roambot.providers.protocols import ProviderError

    requests = []

    class Http:
        def get_json(self, **kwargs):
            requests.append(kwargs)
            return {
                "status": "1",
                "infocode": "10000",
                "regeocode": {
                    "addressComponent": address,
                    "formatted_address": "不能转发的街道和门牌",
                },
            }

    maps = DiscoveryMap(AMapProvider(Http(), "not-a-credential"))
    if expected is None:
        with pytest.raises(ProviderError):
            maps.area(Coordinate(longitude=120, latitude=31))
    else:
        assert maps.area(Coordinate(longitude=120, latitude=31)) == expected
    assert requests[0]["path"] == "/v3/geocode/regeo"
    assert requests[0]["params"]["extensions"] == "base"
