"""Opt-in, bounded semantic diagnostic using synthetic inputs only.

This is a local developer command, not an HTTP endpoint or production fallback.
The production arm calls the real provider implementation so its prompt cannot
silently drift away from the website's prompt.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

import httpx

from roambot.domain.assistant import AssistantModelReply, AssistantTurnRequest
from roambot.providers.assistant import OpenAICompatibleAssistantProvider
from roambot.providers.assistant_semantic_protocol import (
    normalize_semantic_output,
    semantic_messages,
)
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError
from roambot.services.assistant_interpretation import interpret_reply


def diagnostic_cases(today: date) -> list[AssistantTurnRequest]:
    return [
        AssistantTurnRequest(message="我想去苏州", revision=0, draft={}),
        AssistantTurnRequest(
            message="明天出发，玩4天",
            revision=1,
            draft={"main_origin": "常州", "destination_regions": ["320500"]},
        ),
        AssistantTurnRequest(
            message="别改旅行时间，同行改为南京出发，目的地改去嘉兴",
            revision=2,
            draft={
                "main_origin": "绍兴",
                "companion_origins": ["杭州"],
                "destination_regions": ["330200"],
                "start_date": today + timedelta(days=1),
                "end_date": today + timedelta(days=3),
                "max_distance_km": 120,
            },
        ),
    ]


def audit_cases(today: date) -> list[AssistantTurnRequest]:
    # Current independent failures. Real expected state/history are synthetic;
    # never copy these messages into production instructions.
    complete = {
        "main_origin": "广州",
        "companion_origins": ["佛山"],
        "start_date": today + timedelta(days=1),
        "end_date": today + timedelta(days=2),
        "max_distance_km": 120,
        "scenery_types": ["park"],
        "scenery_query": "绿地",
        "scenery_keywords": ["公园"],
        "destination_regions": ["350200"],
    }
    return [
        AssistantTurnRequest(
            message="目的地城市的限制也先取消",
            revision=1,
            draft={**complete, "destination_regions": ["350500"]},
            history=[
                {"role": "user", "content": "厦门先撤了，目的地换成泉州，其他照旧"},
                {"role": "assistant", "content": "条件已更新，可点击开始推荐。"},
            ],
        ),
        AssistantTurnRequest(
            message="距离再缩到六十公里；扬州是从那儿走还是到那儿玩，我还没拿准",
            revision=0,
            draft=complete,
        ),
        AssistantTurnRequest(
            message="先不管风景了，这项偏好取消",
            revision=1,
            draft={
                **complete,
                "scenery_types": ["museum"],
                "scenery_query": "室内展览",
                "scenery_keywords": ["展览"],
            },
            history=[
                {"role": "user", "content": "别推荐登山，我更想在室内逛展"},
                {"role": "assistant", "content": "条件已更新，可点击开始推荐。"},
            ],
        ),
    ]


def _redact_text(value: str, key: str) -> str:
    if key:
        for representation in {
            key,
            json.dumps(key)[1:-1],
            json.dumps(key, ensure_ascii=False)[1:-1],
        }:
            value = value.replace(representation, "[redacted]")
    return value


def _bounded(value: object, key: str, limit: int = 16384) -> str | None:
    # Redact before truncation, including a key echoed by a broken gateway.
    if not isinstance(value, str):
        return None
    return _redact_text(value, key)[:limit]


def _redact(value, key: str):
    if isinstance(value, str):
        return _redact_text(value, key)
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if isinstance(value, dict):
        return {name: _redact(item, key) for name, item in value.items()}
    return value


class _MinimalDateHttp:
    """Diagnostic-only schema substitution; normal provider decoding is unchanged."""

    def __init__(self, delegate: ProviderHttpClient):
        self.delegate = delegate

    def post_json(self, **options):
        from roambot.providers.assistant_parameters import assistant_parameter_tool

        tool = deepcopy(assistant_parameter_tool())
        full = tool["function"]["parameters"]
        full["properties"] = {
            name: full["properties"][name] for name in ("intent", "updates", "question")
        }
        full["properties"]["intent"]["enum"] = ["conditions"]
        full["properties"]["updates"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "date_request": full["$defs"]["AssistantParameterUpdates"]["properties"][
                    "date_request"
                ]
            },
        }
        full["$defs"] = {"AssistantDateRequest": full["$defs"]["AssistantDateRequest"]}
        tool["function"]["description"] = "仅提交本轮明确日期角色与片段，不猜未定日期。"
        body = {**options["json_body"], "tools": [tool]}
        return self.delegate.post_json(**{**options, "json_body": body})


def compare_assistant_protocols(
    client: httpx.Client,
    *,
    base_url: str,
    key: str,
    model: str,
    today: date,
    checkpoint=None,
    include_candidate: bool = False,
    audit: bool = False,
    date_roles: bool = False,
) -> dict:
    """No catalog queries, retries, credentials I/O, or user-supplied fixtures."""
    report = {
        "requested_model": _bounded(model, key, 120),
        "today": today.isoformat(),
        "synthetic_inputs_only": True,
        "comparison_not_acceptance": True,
        "request_limit": 3
        if date_roles
        else len(audit_cases(today))
        if audit
        else (9 if include_candidate else 6),
        "results": [],
    }
    http = ProviderHttpClient(
        client,
        provider="llm",
        base_url=base_url,
        timeout=45,
        secrets=(key,),
    )
    provider = OpenAICompatibleAssistantProvider(http, key, model, lambda: today)
    minimal_date_provider = OpenAICompatibleAssistantProvider(
        _MinimalDateHttp(http), key, model, lambda: today
    )
    observation: dict = {}

    def observe(response: httpx.Response):
        response.read()
        observation["http_status"] = response.status_code
        if len(response.content) > 131072:
            observation["capture_error"] = "response_too_large"
            return
        try:
            payload = response.json()
        except ValueError:
            observation["capture_error"] = "invalid_json"
            return
        if not isinstance(payload, dict):
            observation["capture_error"] = "invalid_envelope"
            return
        observation["returned_model"] = _bounded(payload.get("model"), key, 120)
        usage = payload.get("usage")
        if isinstance(usage, dict):
            observation["usage"] = {
                name: usage[name]
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                if type(usage.get(name)) is int
            }
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            observation["finish_reason"] = _bounded(choice.get("finish_reason"), key, 60)
            message = choice.get("message")
            if isinstance(message, dict):
                observation["content"] = _bounded(message.get("content"), key)
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    observation["tool_call_count"] = len(calls)
                    if len(calls) == 1 and isinstance(calls[0], dict):
                        function = calls[0].get("function")
                        if isinstance(function, dict):
                            observation["function_name"] = _bounded(function.get("name"), key, 80)
                            observation["arguments"] = _bounded(function.get("arguments"), key)

    client.event_hooks["response"].append(observe)
    try:
        if date_roles:
            end = today + timedelta(days=3)
            selected = [
                AssistantTurnRequest(
                    message=f"{end.month}月{end.day}日回来，出发那天还没决定", revision=0, draft={}
                ),
                AssistantTurnRequest(
                    message=f"先确定返程：{end.month}月{end.day}号回；哪天走还没想好",
                    revision=0,
                    draft={},
                ),
            ]
        else:
            selected = audit_cases(today) if audit else diagnostic_cases(today)
        for index, request in enumerate(selected):
            arms = (
                ("minimal_date_native", "production_protocol")
                if date_roles and index == 0
                else ("production_protocol",)
                if date_roles
                else ("production_protocol",)
                if audit
                else ("minimal_semantics", "production_protocol")
            )
            if include_candidate and not date_roles:
                arms += ("semantic_labels",)
            for arm in arms:
                observation.clear()
                row = {
                    "case": index + 1,
                    "arm": arm,
                    "input": request.model_dump(mode="json"),
                }
                started = perf_counter()
                try:
                    if arm == "semantic_labels":
                        payload = http.post_json(
                            operation="assistant_diagnostic",
                            path="/chat/completions",
                            headers={"Authorization": f"Bearer {key}"},
                            json_body={
                                "model": model,
                                "temperature": 0.2,
                                "max_tokens": 2048,
                                "response_format": {"type": "json_object"},
                                "messages": semantic_messages(request, None, today),
                            },
                        )
                        content = payload["choices"][0]["message"]["content"]
                        reply = AssistantModelReply.model_validate(
                            normalize_semantic_output(json.loads(content))
                        )
                        row["validated_reply"] = reply.model_dump(mode="json", exclude_unset=True)
                        resolved = interpret_reply(reply, request.draft, today)
                        row["resolved_patch"] = resolved.patch.model_dump(
                            mode="json", exclude_unset=True
                        )
                        row["resolved_question"] = resolved.question
                    elif arm in {"production_protocol", "minimal_date_native"}:
                        if arm == "production_protocol":
                            reply = provider.turn(request, None)
                        else:
                            reply = minimal_date_provider._request_reply(
                                [
                                    {
                                        "role": "system",
                                        "content": (
                                            "只识别这句话明确表达的旅行日期角色，调用指定函数提交日期片段。"
                                            "未明确的日期不猜测，不做日期运算；区分出发日、返程日与时长。"
                                            f"北京时间今天{today.isoformat()}。"
                                        ),
                                    },
                                    {"role": "user", "content": request.message},
                                ]
                            )
                        row["validated_reply"] = reply.model_dump(mode="json", exclude_unset=True)
                        resolved = interpret_reply(reply, request.draft, today)
                        row["resolved_patch"] = resolved.patch.model_dump(
                            mode="json",
                            exclude_unset=True,
                        )
                        row["resolved_question"] = resolved.question
                    else:
                        http.post_json(
                            operation="assistant_diagnostic",
                            path="/chat/completions",
                            headers={"Authorization": f"Bearer {key}"},
                            json_body={
                                "model": model,
                                "temperature": 0.2,
                                "max_tokens": 2048,
                                "response_format": {"type": "json_object"},
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": (
                                            "理解旅行对话，只输出JSON。当前条件是已经确认的状态。"
                                            "只输出这句话要求改变的字段，没提及或要求保持的字段省略。"
                                            "区分出发地、同行出发地和目的地省市，目的地不是出发地。"
                                            "字段：main_origin字符串、companion_origins数组、"
                                            "destination_region_names数组、offset_days整数(相对今天)、"
                                            "duration_days整数、question字符串(仅有歧义时)。"
                                            f"今天是{today.isoformat()}。"
                                        ),
                                    },
                                    {
                                        "role": "user",
                                        "content": json.dumps(
                                            {
                                                "current_conditions": request.draft.model_dump(
                                                    mode="json",
                                                    exclude_none=True,
                                                ),
                                                "message": request.message,
                                            },
                                            ensure_ascii=False,
                                        ),
                                    },
                                ],
                            },
                        )
                    row["status"] = "ok"
                except ProviderError as error:
                    row["status"] = error.code
                except (ValueError, TypeError, KeyError, IndexError):
                    row["status"] = "bad_response"
                row.update(observation)
                row["elapsed_ms"] = round((perf_counter() - started) * 1000)
                # Sanitize the whole row too: parsed replies may echo a key.
                safe_row = _redact(row, key)
                report["results"].append(safe_row)
                if checkpoint:
                    checkpoint(report)
                print(
                    f"Diagnostic case={index + 1} arm={arm} status={row['status']} "
                    f"elapsed_ms={row['elapsed_ms']}"
                )
                if row["status"] in {"configuration_error", "rate_limited"} or row.get(
                    "http_status"
                ) in (401, 403):
                    return report
    finally:
        client.event_hooks["response"].remove(observe)
    return report


def probe_assistant_parameters(*args, **kwargs):
    from roambot.providers.assistant_parameter_probe import probe_assistant_parameters as probe

    return probe(*args, **kwargs)


def run_assistant_diagnostic(
    base_url: str,
    key: str,
    model: str,
    output: Path,
    *,
    audit=False,
    parameters=False,
    date_roles=False,
) -> int:
    from datetime import datetime, timezone

    today = datetime.now(timezone(timedelta(hours=8))).date()
    output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint(report):
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with httpx.Client(timeout=45) as client:
        if parameters:
            report = probe_assistant_parameters(
                client,
                base_url=base_url,
                key=key,
                model=model,
                today=today,
                checkpoint=checkpoint,
            )
        else:
            report = compare_assistant_protocols(
                client,
                base_url=base_url,
                key=key,
                model=model,
                today=today,
                checkpoint=checkpoint,
                include_candidate=not audit,
                audit=audit,
                date_roles=date_roles,
            )
    print(f"Synthetic diagnostic saved: {output}")
    return 0 if len(report["results"]) == report["request_limit"] else 1
