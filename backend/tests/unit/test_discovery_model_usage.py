import json
from types import SimpleNamespace

from test_discovery_batches import ready_run
from roambot.domain.discovery import BatchReview, GroundedBatch
from roambot.providers.discovery_usage import capture_model_usage, record_model_usage
from roambot.providers.discovery_workflow import DiscoveryModel, structured_call
from roambot.services.discovery_batches import BatchWorker, freeze_batch
from roambot.services.discovery_execution import ExecutionTrace
import pytest


def test_usage_capture_is_request_local_and_unknown_is_not_zero():
    with capture_model_usage() as outer:
        record_model_usage({"usage": {"prompt_tokens": 30, "completion_tokens": 10}})
        with capture_model_usage() as inner:
            record_model_usage({})
        assert inner["usage"] is None
        assert outer["usage"] == {"prompt_tokens": 30, "completion_tokens": 10}
    record_model_usage({"usage": {"prompt_tokens": 99, "completion_tokens": 99}})
    assert outer["usage"]["prompt_tokens"] == 30


def test_structured_call_records_usage_without_changing_return_type():
    def post_json(**kwargs):
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 3}, "choices": [{
            "finish_reason": "tool_calls", "message": {"tool_calls": [{"function": {
                "name": "batch", "arguments": json.dumps({"cards": []})}}]}}]}
    provider = SimpleNamespace(_http=SimpleNamespace(post_json=post_json), _model="same",
                               _key="not-real", _enable_thinking=False)
    with capture_model_usage() as result:
        value = structured_call(provider, "batch", GroundedBatch, "test", {}, 100)
    assert isinstance(value, GroundedBatch) and result["usage"]["prompt_tokens"] == 10


def test_search_plan_repair_uses_contract_feedback_and_same_configured_model():
    sent = []

    def post_json(**kwargs):
        sent.append(kwargs["json_body"])
        return {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [
            {"function": {"name": "repair_search_plan", "arguments": json.dumps({
                "context": {"region": "苏州", "max_distance_km": 5, "distance_quote": "附近"},
                "goal": "苏州附近放松", "request_location": True,
                "temporal": None, "collection_intent": None, "activity_relation": None})}}]}}]}

    provider = SimpleNamespace(_http=SimpleNamespace(post_json=post_json), _model="same",
                               _key="not-real", _enable_thinking=False)
    plan = DiscoveryModel(provider).repair_plan(
        [{"role": "user", "content": "苏州附近放松"}], {}, False,
        {"context": {"origin": "苏州", "max_distance_km": 5}}, "缺少原文依据")
    assert plan.context.origin is None and plan.request_location
    assert plan.context.max_distance_km == 5
    payload = json.loads(sent[0]["messages"][1]["content"])
    assert payload["validation_error"] == "缺少原文依据"
    assert payload["rejected_plan"]["context"]["origin"] == "苏州"
    assert sent[0]["model"] == "same"


def test_exact_cache_only_reuses_approved_private_inputs(tmp_path):
    run, ids = ready_run(tmp_path)
    calls = []

    def review(conversation, context, cards):
        calls.append("review")
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    worker = BatchWorker(run.model, review, cache=run.cache)
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    worker.review(batch, draft)
    before = len(run.model.calls)
    repeated = worker.compose(batch)
    worker.review(batch, repeated)
    assert len(run.model.calls) == before and calls == ["review"]
    run.turns.append({"role": "user", "content": "不要室内，朋友不去，我还是原来出发地"})
    changed = freeze_batch(run, 0, ids, 1)
    worker.compose(changed)
    assert len(run.model.calls) == before + 1
    run.scope = "another-owner"
    worker.compose(freeze_batch(run, 0, ids, 1))
    assert len(run.model.calls) == before + 2


def test_rejected_review_does_not_cache_draft_or_decision_as_success(tmp_path):
    run, ids = ready_run(tmp_path)
    calls = []

    def review(conversation, context, cards):
        calls.append(1)
        return BatchReview(approved_ids=[], rejected=[
            {"place_id": c["place"]["id"], "note": "依据不足，不通过"} for c in cards])

    worker = BatchWorker(run.model, review, cache=run.cache)
    batch = freeze_batch(run, 0, ids, 1)
    for _ in range(2):
        draft = worker.compose(batch)
        worker.review(batch, draft)
    assert calls == [1, 1]
    assert run.model.calls.count("compose") == 2


def test_commit_events_do_not_make_known_model_usage_unknown():
    trace = ExecutionTrace()
    trace.record("composition", 1, 2, usage={"prompt_tokens": 3, "completion_tokens": 4})
    trace.record("commit", 2, 2)
    assert trace.snapshot()["model_usage"] == {"prompt_tokens": 3, "completion_tokens": 4}


def test_invalid_direction_review_is_not_cached_as_approved(tmp_path):
    run, ids = ready_run(tmp_path)
    count = []

    def review(conversation, context, cards):
        count.append(1)
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[],
            covered_directions=[{"direction": 1, "place_ids": [cards[0]["place"]["id"]]}])

    worker = BatchWorker(run.model, review, cache=run.cache)
    batch = freeze_batch(run, 0, ids, 1)
    for _ in range(2):
        draft = worker.compose(batch)
        with pytest.raises(ValueError, match="direction"):
            worker.review(batch, draft)
    assert count == [1, 1]


@pytest.mark.parametrize("field", ["evidence", "reason", "date"])
def test_exact_review_inputs_invalidate_changed_facts_and_text(tmp_path, field):
    run, ids = ready_run(tmp_path)
    calls = []

    def review(conversation, context, cards):
        calls.append(1)
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])

    worker = BatchWorker(run.model, review, cache=run.cache)
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    worker.review(batch, draft)
    if field == "reason":
        from roambot.domain.discovery_execution import BatchResult
        changed = draft.payload()
        changed["cards"][0]["reason"] += "这次多看一会儿。"
        draft = BatchResult.freeze(batch, changed)
    else:
        if field == "evidence":
            next(e for e in run.evidence.values() if e["kind"] == "search_excerpt")["excerpt"] += "新资料。"
        else:
            from datetime import date, timedelta
            tomorrow = date.today() + timedelta(days=1)
            run.context = run.context.model_copy(update={"start_date": tomorrow, "end_date": tomorrow})
        batch = freeze_batch(run, 0, ids, 1)
        draft = worker.compose(batch)
    worker.review(batch, draft)
    assert len(calls) == 2
