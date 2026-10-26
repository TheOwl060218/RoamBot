"""Opt-in synthetic model/latency experiment; never a production fallback."""

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx

from roambot.domain.assistant import AssistantTurnRequest
from roambot.providers.assistant import OpenAICompatibleAssistantProvider
from roambot.providers.assistant_diagnostics import _redact
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError
from roambot.services.assistant_interpretation import interpret_reply


def thinking_options(model: str) -> dict:
    """Only explicit known non-thinking controls, never an unsupported silent retry."""
    name = model.casefold()
    if name.startswith(
        (
            "qwen-plus",
            "qwen-max",
            "qwen3.8-max",
            "qwen3.8-flash",
            "qwen3.7-plus",
            "qwen3.7-flash",
            "qwen3.6-plus",
            "qwen3.6-flash",
        )
    ):
        if "preview" in name or "thinking" in name:
            raise ValueError("No verified non-thinking mode for this model ID")
        return {"enable_thinking": False}
    if name in {"deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4.1-flash"}:
        return {"thinking": {"type": "disabled"}}
    raise ValueError("No verified non-thinking mode for this model ID")


class _ExperimentHttp:
    def __init__(self, http: ProviderHttpClient, options: dict):
        self.http, self.options = http, options
        self.calls = 0
        self.telemetry = {}

    def post_json(self, **kwargs):
        self.calls += 1
        payload = self.http.post_json(
            **{**kwargs, "json_body": {**kwargs["json_body"], **self.options}}
        )
        usage = payload.get("usage")
        self.telemetry = {
            "returned_model": payload.get("model")
            if isinstance(payload.get("model"), str)
            else None,
            "usage": {
                key: usage[key]
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if type(usage.get(key)) is int
            }
            if isinstance(usage, dict)
            else {},
        }
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            self.telemetry["reasoning_content_present"] = bool(
                isinstance(message, dict) and message.get("reasoning_content")
            )
        return payload


def _cases(today: date):
    end = today + timedelta(days=3)
    return [
        (
            AssistantTurnRequest(
                message=f"{end.month}月{end.day}日回来，出发那天还没决定",
                revision=0,
                draft={},
            ),
            "return_date",
        ),
        (
            AssistantTurnRequest(
                message="路程改成七十五公里；合肥是出发还是目的地我还没确定",
                revision=0,
                draft={
                    "main_origin": "武汉",
                    "destination_regions": ["360100"],
                    "max_distance_km": 120,
                },
            ),
            "mixed_ambiguity",
        ),
        (
            AssistantTurnRequest(
                message="不逛公园了，改去文化展馆，其他条件留着",
                revision=0,
                draft={
                    "main_origin": "武汉",
                    "max_distance_km": 120,
                    "scenery_types": ["park"],
                    "scenery_query": "绿地",
                    "scenery_keywords": ["公园"],
                },
            ),
            "preference_replacement",
        ),
    ]


def _semantic_errors(reply, resolved, kind: str, today: date) -> list[str]:
    patch = resolved.patch.model_dump(mode="json", exclude_unset=True)
    errors = []
    if reply.intent != "conditions":
        errors.append("wrong_intent")
    if kind == "return_date":
        expected = {"end_date": (today + timedelta(days=3)).isoformat()}
        if (
            reply.date_request is None
            or reply.date_request.model_dump(mode="json", exclude_unset=True) != expected
        ):
            errors.append("wrong_date_role")
        if patch:
            errors.append("unrequested_confirmed_edit")
        if not resolved.question:
            errors.append("missing_departure_question")
    elif kind == "mixed_ambiguity":
        if patch != {"max_distance_km": 75}:
            errors.append("mixed_edit_or_unrequested_location_change")
        if not resolved.question:
            errors.append("missing_role_question")
    else:
        if set(patch) != {"scenery_types", "scenery_query", "scenery_keywords"}:
            errors.append("partial_preference_or_unrequested_edit")
        if "museum" not in (patch.get("scenery_types") or []):
            errors.append("missing_cultural_category")
        if "park" in (patch.get("scenery_types") or []):
            errors.append("old_category")
        if not patch.get("scenery_query") or patch["scenery_query"] == "绿地":
            errors.append("missing_or_stale_description")
        if not patch.get("scenery_keywords") or "公园" in patch["scenery_keywords"]:
            errors.append("missing_or_stale_search_terms")
    return errors


def compare_models(
    client: httpx.Client,
    *,
    base_url: str,
    key: str,
    baseline: str,
    candidate: str,
    today: date,
    checkpoint=None,
) -> dict:
    if baseline.casefold() != "qwen-turbo" or candidate.casefold() == baseline.casefold():
        raise ValueError("Keep the configured turbo baseline and select a distinct candidate")
    options = thinking_options(candidate)
    report = {
        "synthetic_inputs_only": True,
        "comparison_not_acceptance": True,
        "request_limit": 6,
        "request_io_timeout_seconds": 8,
        "latency_metric": "complete_validated_parameters_not_first_token",
        "latency_caution_ms": 5000,
        "thinking_policy": {baseline: "unchanged", candidate: options},
        "website_model_changed": False,
        "results": [],
        "summary": {},
    }
    for request, kind in _cases(today):
        for model in (baseline, candidate):
            http = _ExperimentHttp(
                ProviderHttpClient(
                    client, provider="llm", base_url=base_url, secrets=(key,), timeout=8
                ),
                options if model == candidate else {},
            )
            provider = OpenAICompatibleAssistantProvider(http, key, model, lambda: today)
            started = perf_counter()
            row = {"case": kind, "requested_model": model, "status": "ok", "semantic_errors": []}
            try:
                reply = provider.turn(request, None)
                resolved = interpret_reply(reply, request.draft, today, request.conversation_state)
                row["validated_reply"] = reply.model_dump(mode="json", exclude_unset=True)
                row["semantic_errors"] = _semantic_errors(reply, resolved, kind, today)
            except ProviderError as error:
                row["status"] = error.code
            row.update(http.telemetry)
            row["model_calls"] = http.calls
            row["elapsed_ms"] = round((perf_counter() - started) * 1000)
            row["latency_caution"] = row["elapsed_ms"] > 5000
            report["results"].append(_redact(row, key))
            for selected in (baseline, candidate):
                rows = [r for r in report["results"] if r["requested_model"] == selected]
                times = [r["elapsed_ms"] for r in rows if r["status"] == "ok"]
                report["summary"][selected] = {
                    "tested": len(rows),
                    "passed": sum(r["status"] == "ok" and not r["semantic_errors"] for r in rows),
                    "median_ms": median(times) if times else None,
                    "max_ms": max(times) if times else None,
                    "timeouts": sum(r["status"] == "timeout" for r in rows),
                    "over_5s": sum(r["latency_caution"] for r in rows),
                }
            if checkpoint:
                checkpoint(_redact(report, key))
            print(
                f"Model comparison case={kind} model={model} status={row['status']} "
                f"semantic_pass={row['status'] == 'ok' and not row['semantic_errors']} "
                f"elapsed_ms={row['elapsed_ms']}",
                flush=True,
            )
            if row["status"] in {"configuration_error", "rate_limited"}:
                return _redact(report, key)
            # Authentication/routing failures are represented as unavailable by the
            # shared production transport; do not spend more calls on that path.
            if row["status"] == "unavailable":
                return _redact(report, key)
    return _redact(report, key)


def run_model_comparison(
    base_url: str, key: str, baseline: str, candidate: str, output: Path
) -> int:
    from datetime import datetime, timezone

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        archive = output.with_name(
            output.stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json"
        )
        output.rename(archive)

    def checkpoint(report):
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    today = datetime.now(timezone(timedelta(hours=8))).date()
    with httpx.Client(timeout=8) as client:
        report = compare_models(
            client,
            base_url=base_url,
            key=key,
            baseline=baseline,
            candidate=candidate,
            today=today,
            checkpoint=checkpoint,
        )
    print("Small-sample latency summary (not a generalization or p95 claim):")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"Synthetic model comparison saved: {output}")
    return 0 if len(report["results"]) == 6 and report["summary"][candidate]["passed"] == 3 else 1
