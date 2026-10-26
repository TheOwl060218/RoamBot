import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_discovery import Maps, Weather
from test_discovery_workflow import Model

from roambot.domain.discovery import BatchReview, DiscoveryRequest, SearchContext, VenueSelection
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.providers.protocols import ProviderError
from roambot.services.discovery import DiscoveryJobs
from roambot.services.discovery_batches import freeze_batch
from roambot.services.discovery_execution import ModelGate
from roambot.services.discovery_orchestrator import DiscoveryOrchestrator
from roambot.services.discovery_workflow import Stopped


class EightMaps(Maps):
    def search(self, *args):
        original = super().search(*args)
        extra = []
        for index, value in enumerate(original, 5):
            item = copy.deepcopy(value)
            item.update(id=f"amap:{index}", name=value["name"] + "分馆")
            extra.append(item)
        return original + extra


class EightWeb:
    def search(self, query):
        return [
            {
                "title": p["name"] + "介绍",
                "url": f"https://example.org/{p['id']}",
                "excerpt": p["name"] + "有明确公开资料，提供可供参观的空间及当地活动。",
                "kind": "search_excerpt",
            }
            for p in EightMaps().search("", "苏州", None, None)
        ]


class EightModel(Model):
    def nominate(self, *args):
        self.calls.append("nominate")
        return VenueSelection(
            venues=[
                {"name": p["name"], "place_id": p["id"]}
                for p in EightMaps().search("", "苏州", None, None)
            ]
        )


def build(tmp_path, *, model=None, reviewer=None, scope="one", gate=None):
    return DiscoveryOrchestrator(
        DiscoveryRequest(message="苏州找不同体验"),
        EightMaps(),
        Weather(),
        EightWeb(),
        model or EightModel(),
        DiscoveryCache(tmp_path / "facts.sqlite3"),
        scope,
        source="demo",
        gate=gate or ModelGate(2),
        batch_reviewer=reviewer
        or (
            lambda conversation, context, cards: BatchReview(
                approved_ids=[c["place"]["id"] for c in cards], rejected=[]
            )
        ),
    )


def test_next_composition_overlaps_first_review_and_keeps_order(tmp_path):
    review_entered, tail_entered = threading.Event(), threading.Event()
    main_thread = threading.get_ident()

    class Overlap(EightModel):
        def compose(self, *args):
            assert threading.get_ident() != main_thread
            if len(args[3]) == 5:
                assert review_entered.wait(2)
                tail_entered.set()
            return super().compose(*args)

    def review(conversation, context, cards):
        if len(cards) == 3:
            review_entered.set()
            assert tail_entered.wait(2), "tail composition must run before first review exits"
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    run = build(tmp_path, model=Overlap(), reviewer=review)
    run.run()
    assert run.status == "completed", run.errors
    assert tail_entered.is_set()
    assert [c["place"]["id"] for c in run.cards[:3]] == ["amap:1", "amap:2", "amap:3"]
    assert len(run.cards) == 8 and len({c["place"]["id"] for c in run.cards}) == 8
    assert run.metrics["model_calls"] == 6
    assert run.snapshot()["workflow"] == "coordinated-v1"


def test_failed_early_batch_unblocks_later_valid_batch(tmp_path):
    def review(conversation, context, cards):
        if len(cards) == 3:
            raise ProviderError("unavailable", "test unavailable")
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    run = build(tmp_path, reviewer=review)
    run.run()
    assert run.status == "partial", run.errors
    assert len(run.cards) == 5
    assert {c["place"]["id"] for c in run.cards} == {f"amap:{i}" for i in range(4, 9)}


@pytest.mark.parametrize("change", ["cancel", "revision"])
def test_cancel_and_revision_discard_late_results(tmp_path, change):
    entered, release = threading.Event(), threading.Event()

    def review(conversation, context, cards):
        entered.set()
        assert release.wait(2)
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    run = build(tmp_path, reviewer=review)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run.run)
        assert entered.wait(2)
        if change == "cancel":
            run.cancelled.set()
        else:
            run.revision += 1
        release.set()
        future.result(timeout=5)
    assert not run.cards
    assert run.status in {"cancelled", "failed"}


def test_two_runs_share_gate_not_private_state(tmp_path):
    gate = ModelGate(2)
    runs = [build(tmp_path / str(i), scope=str(i), gate=gate) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda run: run.run(), runs))
    assert all(run.status == "completed" and len(run.cards) == 8 for run in runs)
    runs[0].cards[0]["reason"] = "private mutation"
    assert runs[1].cards[0]["reason"] != "private mutation"
    assert gate.active == 0


def test_small_batch_does_not_add_model_roundtrips(tmp_path):
    run = build(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()[:4]
    before = run.metrics["model_calls"]
    run.process_candidates(ids)
    assert len(run.cards) == 4
    assert run.metrics["model_calls"] - before == 2


def test_route_cap_rejects_first_five_but_checks_later_valid_candidates(tmp_path):
    class Routes(EightMaps):
        def route(self, center, place, mode):
            self.calls.append(("route", place["id"], mode))
            return {
                "mode": mode,
                "distance_km": 8 if int(place["id"].split(":")[1]) <= 5 else 3,
                "duration_minutes": 20,
                "estimated": False,
            }

    model = EightModel(
        SearchContext(
            origin="苏州站",
            origin_quote="从苏州站出发",
            max_distance_km=5,
            distance_quote="5公里内",
        )
    )
    run = build(tmp_path, model=model)
    run.turns = [{"role": "user", "content": "从苏州站出发，5公里内看看"}]
    run.maps = Routes()
    run.run()
    assert run.status == "completed", run.errors
    assert {c["place"]["id"] for c in run.cards} == {"amap:6", "amap:7", "amap:8"}
    assert len([call for call in run.maps.calls if call[0] == "route"]) == 8
    assert all(c["route"]["distance_km"] == 3 for c in run.cards)


def test_failed_web_attempts_do_not_escape_shared_search_budget(tmp_path):
    run = build(tmp_path)

    def fail(query):
        raise ProviderError("unavailable", "controlled failure")

    run.search.search = fail
    for _ in range(2):
        with pytest.raises(ProviderError, match="controlled failure"):
            run.web_search("同一个失败的查询")
    with pytest.raises(ProviderError) as error:
        run.web_search("另一个查询")
    assert error.value.code == "search_budget"
    assert run.metrics["web_attempts"] == 2
    assert run.budget.counts["search"] == 2


def test_cancel_during_http_discards_response_before_private_cache_write(tmp_path):
    def review(conversation, context, cards):
        run.cancelled.set()
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    run = build(tmp_path, reviewer=review)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()[:4]
    run.facts(ids)
    batch = freeze_batch(run, 0, ids, run.revision)
    draft = run.worker.compose(batch)
    with pytest.raises(Stopped):
        run.worker.review(batch, draft)
    _, hit = run.cache.get(run.scope, "approved-composition-v1", run.worker.composition_key(batch))
    assert hit is False
    assert run.trace.snapshot()["events"], "already-issued model usage must still be recorded"


def test_job_cancel_acknowledgement_serializes_with_publication_lock(tmp_path):
    run = build(tmp_path)
    jobs = DiscoveryJobs()
    jobs.jobs["controlled"] = ("one", time.monotonic(), run)
    entered = threading.Event()

    def cancel():
        entered.set()
        jobs.stop("one", "controlled")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with run.lock:
            future = pool.submit(cancel)
            assert entered.wait(1)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.05)
        future.result(timeout=1)
    assert run.cancelled.is_set()
    jobs.close()


def test_same_owner_identical_jobs_cannot_exchange_execution_receipts(tmp_path):
    runs = [build(tmp_path / str(i)) for i in range(2)]
    prepared = []
    for run in runs:
        run.plan = run.model.plan()
        run.configure_plan()
        ids = run.retrieve()[:4]
        run.facts(ids)
        prepared.append(freeze_batch(run, 0, ids, run.revision))
    draft = runs[0].worker.compose(prepared[0])
    decision = runs[0].worker.review(prepared[0], draft)
    with pytest.raises(ValueError):
        runs[1].commit_reviewed_batch(prepared[0], draft, decision, revision=runs[1].revision)
    assert runs[1].cards == []
