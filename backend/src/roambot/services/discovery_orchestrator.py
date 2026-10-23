"""A bounded pipeline: workers calculate immutable results, one owner publishes."""

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from roambot.providers.discovery_usage import capture_model_usage
from roambot.providers.protocols import ProviderError
from roambot.services.discovery_batches import BatchWorker, freeze_batch
from roambot.services.discovery_execution import (
    ExecutionBudget,
    ExecutionStopped,
    ExecutionTrace,
    ModelGate,
)
from roambot.services.discovery_facts import collect_facts, freeze_facts
from roambot.services.discovery_workflow import DiscoveryWorkflow, Stopped
from roambot.services.discovery_scheduling import assessment_batch_size


class DiscoveryOrchestrator(DiscoveryWorkflow):
    def __init__(self, *args, gate=None, batch_reviewer, **kwargs):
        super().__init__(*args, **kwargs)
        self.gate = gate or ModelGate(2)
        self.budget = ExecutionBudget(self.cancelled, self.started + 120)
        self.trace = ExecutionTrace()
        self.revision, self.sequence, self.primary_sequence = 1, 0, 0
        self.worker = BatchWorker(
            self.model,
            batch_reviewer,
            self.trace,
            self.invoke_model,
            cache=self.cache,
            check=self.check,
        )

    def snapshot(self):
        result = super().snapshot()
        result["workflow"] = "coordinated-v1"
        result["metrics"]["execution"] = self.trace.snapshot()
        return result

    def check(self):
        try:
            self.budget.check()
        except ExecutionStopped as error:
            raise Stopped() from error

    def model_call(self, stage, call):
        return self.invoke_model(stage, call, None)

    def web_search(self, query):
        area = self.context.region or self.context.origin or self.center_name
        scoped = " ".join(value for value in (area, query) if value)
        self.web_seen.add(query)

        def search():
            try:
                self.budget.reserve("search")
            except ExecutionStopped as error:
                raise ProviderError("search_budget", "本轮检索预算已用完。") from error
            with self.metrics_lock:
                self.metrics["web_attempts"] += 1
            return self.search.search(scoped)

        return self.cached("web-basic-chunks-v2", scoped, 21600, search)

    def invoke_model(self, stage, call, sequence):
        for attempt in range(2):
            queued = time.monotonic()
            priority = 0 if sequence is None or sequence == self.primary_sequence else 1
            try:
                with self.gate.slot(self.budget, priority=priority):
                    self.budget.reserve("model")
                    start = time.monotonic()
                    with self.metrics_lock:
                        self.metrics["model_calls"] += 1
                    with capture_model_usage() as receipt:
                        try:
                            value = call()
                            self.budget.check()
                            return value
                        finally:
                            end = time.monotonic()
                            self.trace.record(
                                stage,
                                start,
                                end,
                                batch=sequence,
                                queue_ms=round((start - queued) * 1000),
                                usage=receipt["usage"],
                            )
                            with self.metrics_lock:
                                times = self.metrics["stages"]
                                times[stage] = times.get(stage, 0) + round((end - start) * 1000)
            except ExecutionStopped as error:
                raise Stopped() from error
            except ProviderError as error:
                if attempt or error.code != "bad_response":
                    raise
                with self.metrics_lock:
                    self.metrics["format_repairs"] = self.metrics.get("format_repairs", 0) + 1

    def apply_facts(self, result, revision):
        if result.batch.identity != self.scope or revision != self.revision:
            raise Stopped()
        data = result.batch.payload()
        if data["execution_id"] != self.execution_id:
            raise Stopped()
        for item in result.payload()["values"]:
            key, kind, value = item["id"], item["kind"], item["value"]
            if key not in data["ids"]:
                raise ValueError("Unknown fact result")
            (self.routes if kind == "route" else self.forecasts)[key] = value
            self.add_evidence(
                key,
                {"kind": "measure_routes" if kind == "route" else "check_weather", "facts": value},
            )
            with self.metrics_lock:
                self.metrics["cache_hits" if item["hit"] else "cache_misses"] += 1
            if item.get("error"):
                self.errors.append({"tool": "facts", "code": item["error"]})
        valid = []
        for key in data["ids"]:
            route = self.routes.get(key)
            if self.context.max_distance_km is not None and (
                not route
                or route.get("unavailable")
                or route["distance_km"] > self.context.max_distance_km
            ):
                continue
            valid.append(key)
        return valid

    def process_candidates(self, ids):
        self.pipeline(ids)
        if self.pending_nomination:
            self.pending_nomination = False
            nominees = self.nominate()
            shown = {c["place"]["id"] for c in self.cards}
            self.pipeline([key for key in nominees if key not in shown][: 12 - len(shown)])

    def process_supplement(self, ids):
        self.pipeline(ids)

    def pipeline(self, ids):
        ids = list(dict.fromkeys(ids))[:12]
        if not ids:
            return
        # Small result sets stay in one model batch; splitting them would add calls.
        direct = bool(getattr(self.model, "source_first", False))
        first = assessment_batch_size(len(ids), first=True) if direct else (
            len(ids) if len(ids) <= 6 else 3 if len(ids) <= 9 else 4)
        size = assessment_batch_size(6) if direct else 6
        groups = [ids[:first]] + [ids[i : i + size] for i in range(first, len(ids), size)]
        revision = self.revision
        start_sequence = self.sequence
        self.sequence += len(groups)
        self.primary_sequence = start_sequence
        states = {
            start_sequence + i: {"ids": group, "status": "queued"} for i, group in enumerate(groups)
        }
        models = ThreadPoolExecutor(max_workers=2, thread_name_prefix="discovery-model")
        facts = ThreadPoolExecutor(max_workers=1, thread_name_prefix="discovery-fact-batch")
        pending, next_fact, next_commit, tail_allowed = {}, start_sequence, start_sequence, False

        def schedule_fact():
            nonlocal next_fact
            if next_fact >= self.sequence or (next_fact > start_sequence and not tail_allowed):
                return
            if any(kind == "facts" for kind, _ in pending.values()):
                return
            seq = next_fact
            request = freeze_facts(self, seq, states[seq]["ids"], revision)
            future = facts.submit(
                collect_facts,
                request,
                self.maps,
                self.weather,
                self.cache,
                self.budget,
                self.map_interval,
            )
            pending[future] = ("facts", seq)
            states[seq]["status"] = "facts"
            next_fact += 1

        try:
            schedule_fact()
            while pending:
                self.check()
                if revision != self.revision:
                    raise Stopped()
                done, _ = wait(pending, timeout=0.025, return_when=FIRST_COMPLETED)
                for future in done:
                    kind, seq = pending.pop(future)
                    state = states[seq]
                    try:
                        result = future.result()
                        if kind == "facts":
                            valid = self.apply_facts(result, revision)
                            if valid:
                                batch = freeze_batch(self, seq, valid, revision)
                                state["batch"] = batch
                                pending[models.submit(self.worker.compose, batch)] = (
                                    "composition",
                                    seq,
                                )
                                state["status"] = "composition"
                            else:
                                state["status"] = "empty"
                                if seq == start_sequence:
                                    tail_allowed = True
                        elif kind == "composition":
                            state["draft"] = result
                            pending[models.submit(self.worker.review, state["batch"], result)] = (
                                "review",
                                seq,
                            )
                            state["status"] = "review"
                            if seq == start_sequence:
                                tail_allowed = True
                        else:
                            state["decision"], state["status"] = result, "ready"
                    except (Stopped, ExecutionStopped):
                        raise Stopped() from None
                    except Exception as error:
                        self.errors.append(
                            {"tool": kind, "code": getattr(error, "code", "invalid_result")}
                        )
                        state["status"] = "failed"
                        if seq == start_sequence:
                            tail_allowed = True
                while next_commit < self.sequence:
                    state = states[next_commit]
                    if state["status"] not in {"ready", "empty", "failed"}:
                        break
                    self.check()
                    if state["status"] == "ready":
                        self.commit_reviewed_batch(
                            state["batch"], state["draft"], state["decision"], revision=revision
                        )
                        self.trace.record(
                            "commit", time.monotonic(), time.monotonic(), batch=next_commit
                        )
                    state["status"] = "committed"
                    next_commit += 1
                schedule_fact()
        finally:
            # Inflight HTTP retains its gate slot. Late values cannot reach commit.
            models.shutdown(wait=False, cancel_futures=True)
            facts.shutdown(wait=False, cancel_futures=True)
