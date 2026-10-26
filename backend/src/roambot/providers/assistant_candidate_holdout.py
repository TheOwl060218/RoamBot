"""Private candidate screening through the real service, never a website override."""

import importlib.util
import json
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import httpx

from roambot.domain.assistant import AssistantTurnRequest
from roambot.providers.assistant import OpenAICompatibleAssistantProvider
from roambot.providers.assistant_diagnostics import _redact
from roambot.providers.assistant_model_comparison import _ExperimentHttp, thinking_options
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService


class _Stopped(Exception):
    pass


class _BoundedHttp(_ExperimentHttp):
    def __init__(self, http, options, limit):
        super().__init__(http, options)
        self.limit, self.attempts = limit, []

    def post_json(self, **kwargs):
        if self.calls >= self.limit:
            raise _Stopped("request_budget")
        try:
            payload = super().post_json(**kwargs)
        except ProviderError as error:
            self.attempts.append({"status": error.code})
            # Do not retry routing, authentication or quota trouble in experiments.
            if error.code in {"configuration_error", "unavailable", "rate_limited"}:
                raise _Stopped(error.code) from None
            raise
        attempt = {"status": "received", **self.telemetry}
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            calls = message.get("tool_calls") if isinstance(message, dict) else None
            if isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], dict):
                function = calls[0].get("function")
                arguments = function.get("arguments") if isinstance(function, dict) else None
                if isinstance(arguments, str) and len(arguments) <= 16384:
                    # Private fixed synthetic suites only; never headers or reasoning.
                    attempt["synthetic_arguments"] = arguments
        self.attempts.append(attempt)
        return payload


def _acceptance_runner():
    source = Path(__file__).resolve().parents[4] / "scripts" / "assistant_acceptance.py"
    spec = importlib.util.spec_from_file_location("candidate_acceptance_runner", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_holdout(
    client: httpx.Client,
    *,
    base_url: str,
    key: str,
    model: str,
    today: date,
    checkpoint=None,
    scenarios=None,
    focus=False,
) -> dict:
    options = thinking_options(model)
    runner = _acceptance_runner()
    selected = runner.holdout_cases(today) if scenarios is None else scenarios
    if focus:
        selected = [
            scenario for scenario in selected if scenario["name"] == "holdout_destination_scope"
        ]
    planned = sum(len(scenario["turns"]) for scenario in selected)
    if planned > 15:
        raise ValueError("Candidate screening is limited to fifteen turns")
    http = _BoundedHttp(
        ProviderHttpClient(client, provider="llm", base_url=base_url, secrets=(key,), timeout=8),
        options,
        planned * 2,
    )
    provider = OpenAICompatibleAssistantProvider(http, key, model, lambda: today)
    service = AssistantService(
        provider,
        AssistantContextSigner(b"synthetic-candidate-facts-only", lambda: datetime.now(UTC)),
        lambda: today,
        demo=False,
    )
    report = {
        "synthetic_inputs_only": True,
        "screening_not_website_acceptance": True,
        "requested_model": model,
        "thinking_policy": options,
        "website_model_changed": False,
        "request_limit": planned * 2,
        "request_io_timeout_seconds": 8,
        "latency_metric": "complete_service_response_including_bounded_repair",
        "model_calls": 0,
        "stopped_reason": None,
        "results": [],
        "summary": {},
    }
    metadata = []

    class ServiceAdapter:
        def post(self, url, *, json):
            if url != "http://synthetic.local/api/v1/assistant/turns":
                raise ValueError("Only the in-process synthetic assistant endpoint is allowed")
            previous_calls = http.calls
            http.telemetry = {}
            try:
                response = service.turn(AssistantTurnRequest.model_validate(json))
                data, status = response.model_dump(mode="json", exclude_unset=True), 200
                error_code = None
            except ProviderError as error:
                data, status, error_code = {"error": {"code": error.code}}, 503, error.code
            metadata.append(
                {
                    **http.telemetry,
                    "model_calls": http.calls - previous_calls,
                    "parameter_attempts": http.attempts[previous_calls:],
                    "provider_error": error_code,
                }
            )
            return httpx.Response(status, json=data)

    def save(results):
        report["results"] = [{**row, **metadata[index]} for index, row in enumerate(results)]
        report["model_calls"] = http.calls
        times = [row["elapsed_seconds"] for row in results if row["status"] == 200]
        report["summary"] = {
            "planned": planned,
            "tested": len(results),
            "passed": sum(not row["errors"] for row in results),
            "median_seconds": median(times) if times else None,
            "max_seconds": max(times) if times else None,
            "over_5s": sum(row["elapsed_seconds"] > 5 for row in results),
            "failed_requests": sum(row["status"] != 200 for row in results),
        }
        if checkpoint:
            checkpoint(_redact(report, key))

    try:
        runner.evaluate(ServiceAdapter(), "http://synthetic.local", selected, checkpoint=save)
    except _Stopped as stopped:
        report["stopped_reason"] = str(stopped)
    save(report["results"])
    return _redact(report, key)


def run_candidate_holdout(base_url: str, key: str, model: str, output: Path, *, focus=False) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.rename(
            output.with_name(
                output.stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json"
            )
        )

    def checkpoint(report):
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    today = datetime.now(timezone(timedelta(hours=8))).date()
    with httpx.Client(timeout=8) as client:
        report = candidate_holdout(
            client,
            base_url=base_url,
            key=key,
            model=model,
            today=today,
            checkpoint=checkpoint,
            focus=focus,
        )
    print("Candidate holdout summary (not website/UI acceptance):")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"Synthetic candidate holdout saved: {output}")
    summary = report["summary"]
    return int(bool(report["stopped_reason"]) or summary["passed"] != summary["planned"])
