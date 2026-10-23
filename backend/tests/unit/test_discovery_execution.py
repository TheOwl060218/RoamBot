import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from roambot.domain.discovery_execution import BatchInput
from roambot.services.discovery_execution import (
    ExecutionBudget,
    ExecutionStopped,
    ExecutionTrace,
    ModelGate,
)


def test_frozen_batch_ignores_source_mutations():
    source = {"cards": [{"id": "a", "reason": "original"}]}
    batch = BatchInput.freeze("owner", 1, 0, source)
    source["cards"][0]["reason"] = "changed"
    assert batch.payload()["cards"][0]["reason"] == "original"
    decoded = batch.payload()
    decoded["cards"].clear()
    assert batch.payload()["cards"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        batch.revision = 2
    assert batch.fingerprint != BatchInput.freeze("other", 1, 0, source).fingerprint


def test_atomic_budget_counts_failed_attempts():
    budget = ExecutionBudget(threading.Event(), time.monotonic() + 5)

    def attempt(kind):
        try:
            budget.reserve(kind)
            return True
        except ExecutionStopped:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(attempt, ["model"] * 30)) == 10
        assert sum(pool.map(attempt, ["search"] * 20)) == 2
    assert budget.counts == {"model": 10, "search": 2}


def test_gate_limits_two_across_runs_and_retains_cancelled_inflight_slot():
    gate = ModelGate(2)
    events = [threading.Event(), threading.Event(), threading.Event()]
    release = threading.Event()
    budgets = [ExecutionBudget(threading.Event(), time.monotonic() + 5) for _ in range(3)]

    def run(index):
        with gate.slot(budgets[index], priority=0):
            events[index].set()
            assert release.wait(3)

    with ThreadPoolExecutor(max_workers=3) as pool:
        one, two = pool.submit(run, 0), pool.submit(run, 1)
        assert events[0].wait(1) and events[1].wait(1)
        three = pool.submit(run, 2)
        budgets[0].cancelled.set()
        assert not events[2].wait(0.1), "cancel must not release an active HTTP slot"
        release.set()
        one.result()
        two.result()
        three.result()
    assert events[2].is_set() and gate.active == 0


def test_waiting_gate_is_cancellable_and_has_no_nested_wait():
    gate = ModelGate(1)
    budget = ExecutionBudget(threading.Event(), time.monotonic() + 2)
    with gate.slot(budget, priority=0):
        with pytest.raises(RuntimeError, match="nested"):
            with gate.slot(budget, priority=0):
                pass
        waiting = ExecutionBudget(threading.Event(), time.monotonic() + 2)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: _enter_gate(gate, waiting))
            waiting.cancelled.set()
            with pytest.raises(ExecutionStopped):
                future.result(timeout=1)
    assert gate.active == 0


def _enter_gate(gate, budget):
    with gate.slot(budget, priority=1):
        return True


def test_gate_prioritizes_first_batch_over_waiting_background():
    gate = ModelGate(1)
    budget = ExecutionBudget(threading.Event(), time.monotonic() + 4)
    order = []

    def run(label, priority):
        with gate.slot(budget, priority=priority):
            order.append(label)

    with ThreadPoolExecutor(max_workers=2) as pool:
        with gate.slot(budget, priority=0):
            background = pool.submit(run, "background", 1)
            first = pool.submit(run, "first", 0)
            deadline = time.monotonic() + 1
            while gate.waiting < 2 and time.monotonic() < deadline:
                time.sleep(0.005)
            assert gate.waiting == 2
        first.result()
        background.result()
    assert order == ["first", "background"]


def test_unknown_usage_is_not_zero():
    trace = ExecutionTrace()
    trace.record("composition", 1.0, 2.0, batch=0, usage=None)
    trace.record("review", 1.5, 2.5, batch=0, queue_ms=10,
                 usage={"prompt_tokens": 30, "completion_tokens": 10})
    snapshot = trace.snapshot()
    assert snapshot["model_usage"] is None
    assert snapshot["known_model_usage"] == {"prompt_tokens": 30, "completion_tokens": 10}
    assert snapshot["events"][0]["usage"] is None
    assert snapshot["events"][1]["queue_ms"] == 10
    snapshot["events"].clear()
    assert len(trace.snapshot()["events"]) == 2


def test_budget_cancellation_deadline_and_unknown_kind():
    budget = ExecutionBudget(threading.Event(), 10, clock=lambda: 11)
    with pytest.raises(ExecutionStopped):
        budget.reserve("model")
    current = ExecutionBudget(threading.Event(), time.monotonic() + 1)
    with pytest.raises(ValueError):
        current.reserve("unknown")
    assert current.counts == {"model": 0, "search": 0}
