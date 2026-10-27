"""Isolated comparison. Provider access is possible only with explicit --live.

Offline mode replays saved public facts with a deterministic model; it measures
scheduling, not natural-language quality. Live credentials enter via stdin only.
"""

import argparse
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))


def copy_cache_snapshot(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    if not source:
        return
    for path in Path(source).iterdir():
        aliases = {
            "discovery-facts.sqlite3": "facts.sqlite3",
            "discovery-public.sqlite3": "public.sqlite3",
            "facts.sqlite3": "facts.sqlite3",
            "public.sqlite3": "public.sqlite3",
        }
        if path.is_file() and path.name in aliases:
            with (
                closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as original,
                closing(sqlite3.connect(destination / aliases[path.name])) as target,
                target,
            ):
                original.backup(target)


def compare_pair(
    builders, seed, output, messages, *, live=False, credit_limit=4, cold_messages=()
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"live": live, "runs": [], "search_credits": 0, "stopped": None}
    for index, message in enumerate(messages):
        for label, build in builders.items():
            if live and (
                len(report["runs"]) >= 4 or credit_limit - report["search_credits"] < 2
            ):
                report["stopped"] = "live_budget_reserved"
                return save(report, output)
            folder = output / f"case-{index}-{label}"
            copy_cache_snapshot(None if message in cold_messages else seed, folder)
            run = build(message, folder)
            started = time.monotonic()
            run.run()
            elapsed = round((time.monotonic() - started) * 1000)
            result = run.snapshot()
            summary = {
                "case": index,
                "implementation": label,
                "message": message,
                "status": result["status"],
                "first_batch_ms": result.get("first_batch_ms"),
                "elapsed_ms": elapsed,
                "metrics": result.get("metrics", {}),
                "issues": result.get("issues", []),
                "cards": [
                    {
                        "name": c["place"]["name"],
                        "experience": c["experience"],
                        "reason": c["reason"],
                        "sources": [
                            {k: s[k] for k in ("title", "url", "excerpt") if k in s}
                            for s in c["sources"]
                            if s["kind"] in {"web_page", "search_excerpt"}
                        ],
                    }
                    for c in result["cards"]
                ],
            }
            report["runs"].append(summary)
            print(
                json.dumps(
                    {
                        "case": index,
                        "implementation": label,
                        "elapsed_ms": elapsed,
                        "first_batch_ms": summary["first_batch_ms"],
                        "cards": [c["name"] for c in summary["cards"]],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            usage = summary["metrics"].get("search_credits")
            if usage is None:
                report["search_credits"] = None
                report["stopped"] = "unknown_search_usage"
                return save(report, output)
            report["search_credits"] += usage
            if live and report["search_credits"] > credit_limit:
                report["stopped"] = "provider_reported_credit_overrun"
                return save(report, output)
            save(report, output)
    return save(report, output)


def save(report, output):
    (output / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def instrument_legacy(run):
    from roambot.providers.discovery_usage import capture_model_usage
    from roambot.services.discovery_execution import ExecutionTrace

    trace = ExecutionTrace()
    original_call, original_snapshot = run.model_call, run.snapshot

    def call(stage, invoke):
        def measured():
            start = time.monotonic()
            with capture_model_usage() as receipt:
                try:
                    return invoke()
                finally:
                    trace.record(stage, start, time.monotonic(), usage=receipt["usage"])

        return original_call(stage, measured)

    def snapshot():
        result = original_snapshot()
        result["metrics"]["execution"] = trace.snapshot()
        return result

    run.model_call, run.snapshot = call, snapshot
    return run


def live_builders(config):
    from pydantic import SecretStr
    from roambot.config import Settings
    from roambot.domain.discovery import DiscoveryRequest
    from roambot.persistence.discovery_cache import DiscoveryCache
    from roambot.persistence.discovery_knowledge import DiscoveryKnowledge
    from roambot.providers.discovery import DiscoveryMap, TavilySearch, review_batch
    from roambot.providers.discovery_workflow import DiscoveryModel
    from roambot.providers.factory import build_provider_runtime
    from roambot.security.vault import CredentialVault
    from roambot.services.discovery_orchestrator import DiscoveryOrchestrator
    from roambot.services.discovery_workflow import DiscoveryWorkflow

    values = CredentialVault(
        ROOT.parents[1] / "data/local-live/credentials.vault"
    ).unlock(config.pop("master"))
    settings = Settings(
        provider_mode="live",
        demo_mode=False,
        data_dir=ROOT / "data/discovery-live",
        llm_model=config["model"],
        llm_base_url=config["base"],
        llm_enable_thinking=config["thinking"],
        qweather_api_host=config["weather"],
    )
    runtime = build_provider_runtime(settings, values, cache_repository=None)
    values.clear()
    search_key = SecretStr(
        (ROOT / "data/local-discovery/tavily.key")
        .read_text(encoding="utf-8-sig")
        .strip()
    )

    def make(label):
        def build(message, folder):
            bundle = runtime.new_request_bundle()
            pure_review = lambda conversation, context, cards: review_batch(
                bundle.assistant, conversation, context, cards
            )
            cls = DiscoveryOrchestrator if label == "coordinated" else DiscoveryWorkflow
            extra = {"batch_reviewer": pure_review} if label == "coordinated" else {}
            run = cls(
                DiscoveryRequest(message=message),
                DiscoveryMap(runtime._adapters.places),
                bundle.weather,
                TavilySearch(search_key.get_secret_value()),
                DiscoveryModel(bundle.assistant),
                DiscoveryCache(folder / "facts.sqlite3"),
                "isolated-benchmark",
                source="live",
                reviewer=lambda cards: pure_review(
                    run.turns, run.review_context(), cards
                ),
                knowledge=DiscoveryKnowledge(folder / "public.sqlite3"),
                map_interval=0.55,
                **extra,
            )
            return run if label == "coordinated" else instrument_legacy(run)

        return build

    return {label: make(label) for label in ("legacy", "coordinated")}, runtime


def replay_builders(report, latency_ms):
    from roambot.domain.discovery import (
        BatchReview,
        DiscoveryRequest,
        GroundedBatch,
        RetrievalPlan,
        SearchContext,
        VenueSelection,
    )
    from roambot.persistence.discovery_cache import DiscoveryCache
    from roambot.services.discovery_orchestrator import DiscoveryOrchestrator
    from roambot.services.discovery_workflow import DiscoveryWorkflow

    saved = report["cards"]
    if not saved:
        raise ValueError("Replay requires at least one saved card")

    class Maps:
        def search(self, *args):
            return [c["place"] for c in saved]

    class Web:
        request_count = 0
        reported_credits = 0
        usage_response_count = 0
        usage_reported = True

        def search(self, query):
            self.request_count += 1
            self.usage_response_count += 1
            return [
                s
                for c in saved
                for s in c["sources"]
                if s["kind"] in {"web_page", "search_excerpt"}
            ]

    class Model:
        version = "offline-recorded-facts-v1"

        def plan(self, *args):
            time.sleep(latency_ms / 1000)
            return RetrievalPlan(
                context=SearchContext(region=saved[0]["place"]["city"]),
                goal="离线资料调度回放",
                map_queries=["已有地点"],
                web_queries=["已有资料"],
            )

        def nominate(self, *args):
            time.sleep(latency_ms / 1000)
            return VenueSelection(
                venues=[
                    {"name": c["place"]["name"], "place_id": c["place"]["id"]}
                    for c in saved
                ]
            )

        def compose(self, conversation, goal, context, candidates):
            time.sleep(latency_ms / 1000)
            lookup = {c["place"]["id"]: c for c in saved}
            return GroundedBatch(
                cards=[
                    {
                        "place_id": c["place"]["id"],
                        "experience": lookup[c["place"]["id"]]["experience"],
                        "reason": lookup[c["place"]["id"]]["reason"],
                        "evidence_ids": [
                            s["id"]
                            for s in c["sources"]
                            if s["kind"] in {"web_page", "search_excerpt"}
                        ][:3],
                    }
                    for c in candidates
                ]
            )

    def make(label):
        def build(message, folder):
            def review(conversation, context, cards):
                time.sleep(latency_ms / 1000)
                return BatchReview(
                    approved_ids=[c["place"]["id"] for c in cards], rejected=[]
                )

            cls = DiscoveryOrchestrator if label == "coordinated" else DiscoveryWorkflow
            extra = {"batch_reviewer": review} if label == "coordinated" else {}
            run = cls(
                DiscoveryRequest(message=message),
                Maps(),
                None,
                Web(),
                Model(),
                DiscoveryCache(folder / "facts.sqlite3"),
                "offline",
                source="demo",
                reviewer=lambda cards: review(run.turns, run.review_context(), cards),
                **extra,
            )
            return run if label == "coordinated" else instrument_legacy(run)

        return build

    return {label: make(label) for label in ("legacy", "coordinated")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--latency-ms", type=int, default=100)
    parser.add_argument("--message", action="append")
    parser.add_argument("--cold-message", action="append", default=[])
    args = parser.parse_args()
    runtime = None
    if args.live:
        config = json.load(sys.stdin)
        builders, runtime = live_builders(config)
        config.clear()
    elif args.snapshot:
        builders = replay_builders(
            json.loads(args.snapshot.read_text(encoding="utf-8")), args.latency_ms
        )
    else:
        parser.error(
            "offline mode requires --snapshot; provider calls require explicit --live"
        )
    try:
        compare_pair(
            builders,
            args.seed,
            args.output,
            args.message or ["已保存公开资料回放"],
            live=args.live,
            cold_messages=args.cold_message,
        )
    finally:
        if runtime:
            runtime.close()


if __name__ == "__main__":
    main()
