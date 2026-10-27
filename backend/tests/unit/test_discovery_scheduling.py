"""First result is smaller; every remaining real candidate is still processed."""

import copy

import pytest
from test_discovery import Maps
from test_discovery_workflow import workflow

from roambot.domain.discovery import EvidenceNeed, ExperienceRequirement, GroundedBatch


@pytest.mark.parametrize(
    "count,first", [(2, 2), (4, 4), (6, 2), (8, 2), (9, 3), (10, 4), (11, 2), (12, 2)]
)
def test_first_batch_is_visible_before_tail_without_more_model_rounds(tmp_path, count, first):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    original = Maps().search("", "苏州", None, None)
    places = []
    for index in range(count):
        place = copy.deepcopy(original[index % len(original)])
        place.update(id=f"amap:{index + 1}", name=place["name"] + f"分馆{index + 1}")
        places.append(place)
    run.research_sources = [
        {
            "url": f"https://example.org/place/{i}",
            "title": p["name"],
            "excerpt": p["name"] + "有明确公开的场地资料。",
            "kind": "search_excerpt",
        }
        for i, p in enumerate(places)
    ]
    run.ingest(places)
    compose = run.model.compose
    batch_sizes, prefixes = [], []

    def record(*args):
        if batch_sizes:
            assert len(run.cards) >= first, "first batch must publish before tail generation"
        batch_sizes.append(len(args[3]))
        prefixes.append([c["place"]["id"] for c in run.cards])
        return compose(*args)

    run.model.compose = record
    run.process_candidates([p["id"] for p in places])
    assert batch_sizes[0] == first
    assert all(size <= 6 for size in batch_sizes)
    assert len(batch_sizes) <= 1 + max(0, (count - 4 + 5) // 6)
    assert run.metrics["model_calls"] == 2 * len(batch_sizes)
    assert len(run.cards) == count
    assert {c["place"]["id"] for c in run.cards} == {p["id"] for p in places}
    final = [c["place"]["id"] for c in run.cards]
    assert all(final[: len(prefix)] == prefix for prefix in prefixes)


def test_promising_first_gap_is_resolved_before_generating_the_whole_tail(tmp_path):
    run = workflow(tmp_path, message="做本次活动")
    run.plan = run.model.plan()
    run.plan.requirements = [ExperienceRequirement(text="本次活动", quote="本次活动")]
    run.configure_plan()
    source_places = Maps().search("", "苏州", None, None)
    places = []
    for i in range(12):
        place = copy.deepcopy(source_places[i % 4])
        place.update(id=f"amap:{i + 1}", name=place["name"] + f"分馆{i + 1}")
        places.append(place)
    run.ingest(places)
    original = run.model.compose
    events = []

    def compose(*args):
        ids = [p["place"]["id"] for p in args[3]]
        events.append(("compose", ids))
        if len(events) == 1:
            return GroundedBatch(
                cards=[],
                evidence_needs=[EvidenceNeed(place_id=ids[0], query="关键依据", requirement=1)],
            )
        return original(*args)

    def supplement():
        events.append(("supplement", []))
        return [places[0]["id"]]

    run.model.compose = compose
    run.supplement = supplement
    run.process_candidates([p["id"] for p in places])
    assert events[0] == ("compose", ["amap:1", "amap:2"])
    assert events[1][0] == "supplement"
    assert events[2] == ("compose", ["amap:1"])
    assert len(run.cards) == 11
    assert {c["place"]["id"] for c in run.cards} == {p["id"] for p in places} - {"amap:2"}
    assert any(n.place_id == "amap:2" for n in run.pending_evidence_needs())
