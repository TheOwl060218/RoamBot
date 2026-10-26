"""Bounded scheduling primitives; no business writes and no provider credentials."""

import copy
import heapq
import threading
import time
from contextlib import contextmanager


class ExecutionStopped(RuntimeError):
    pass


class ExecutionBudget:
    def __init__(self, cancelled, deadline, model_limit=10, search_limit=2, clock=time.monotonic):
        self.cancelled, self.deadline, self.clock = cancelled, deadline, clock
        self.limits = {"model": model_limit, "search": search_limit}
        self._counts = {"model": 0, "search": 0}
        self.lock = threading.Lock()

    def check(self):
        if self.cancelled.is_set() or self.clock() >= self.deadline:
            raise ExecutionStopped("Discovery cancelled or deadline exceeded")

    def reserve(self, kind):
        if kind not in self.limits:
            raise ValueError("Unknown discovery budget")
        with self.lock:
            self.check()
            if self._counts[kind] >= self.limits[kind]:
                raise ExecutionStopped(f"Discovery {kind} budget exhausted")
            self._counts[kind] += 1

    @property
    def counts(self):
        with self.lock:
            return dict(self._counts)


class ModelGate:
    def __init__(self, capacity=2):
        if capacity < 1:
            raise ValueError("Model capacity must be positive")
        self.capacity = capacity
        self.condition = threading.Condition()
        self._active, self.serial = 0, 0
        self.queue = []
        self.local = threading.local()

    @property
    def active(self):
        with self.condition:
            return self._active

    @property
    def waiting(self):
        with self.condition:
            return len(self.queue)

    @contextmanager
    def slot(self, budget, priority=0):
        if getattr(self.local, "entered", False):
            raise RuntimeError("nested model gate would deadlock")
        with self.condition:
            ticket = (priority, self.serial)
            self.serial += 1
            heapq.heappush(self.queue, ticket)
            try:
                while True:
                    budget.check()
                    if self._active < self.capacity and self.queue[0] == ticket:
                        heapq.heappop(self.queue)
                        self._active += 1
                        self.local.entered = True
                        break
                    self.condition.wait(timeout=0.025)
            except BaseException:
                self.queue.remove(ticket)
                heapq.heapify(self.queue)
                self.condition.notify_all()
                raise
        try:
            yield
        finally:
            with self.condition:
                self.local.entered = False
                self._active -= 1
                self.condition.notify_all()


class ExecutionTrace:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = []

    def record(self, stage, started, finished, *, batch=None, queue_ms=0, usage=None):
        safe_usage = None
        if isinstance(usage, dict):
            fields = {
                k: usage[k]
                for k in ("prompt_tokens", "completion_tokens")
                if type(usage.get(k)) is int and usage[k] >= 0
            }
            if len(fields) == 2:
                safe_usage = fields
        with self.lock:
            self.events.append(
                {
                    "stage": stage,
                    "start": started,
                    "end": finished,
                    "duration_ms": round((finished - started) * 1000),
                    "batch": batch,
                    "queue_ms": queue_ms,
                    "usage": safe_usage,
                }
            )

    def snapshot(self):
        with self.lock:
            events = copy.deepcopy(self.events)
        known = {"prompt_tokens": 0, "completion_tokens": 0}
        for event in events:
            for key, value in (event["usage"] or {}).items():
                known[key] += value
        model_events = [
            event
            for event in events
            if event["stage"]
            in {"planning", "nomination", "composition", "review", "collection", "selection"}
        ]
        complete = bool(model_events) and all(event["usage"] is not None for event in model_events)
        return {
            "events": events,
            "known_model_usage": known,
            "model_usage": known.copy() if complete else None,
        }
