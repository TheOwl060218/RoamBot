"""Malformed upstream responses must terminate safely without logging private values."""

import copy
import json

import pytest

from roambot.domain.discovery import GroundedBatch
from roambot.providers.discovery_workflow import (
    StructuredResponseError,
    parse_structured_response,
)
from roambot.services.discovery_sources import SourceNomination


def response(arguments=None):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "batch",
                                "arguments": json.dumps(arguments or {"cards": []}),
                            }
                        }
                    ]
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "envelope",
    [
        None,
        [],
        {},
        {"choices": None},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": None}]},
    ],
)
def test_broken_envelopes_have_a_safe_terminal_error(envelope):
    with pytest.raises(StructuredResponseError) as raised:
        parse_structured_response(envelope, "batch", GroundedBatch)
    assert raised.value.code == "bad_response" and raised.value.reason == "envelope"


@pytest.mark.parametrize(
    "change, reason",
    [
        ("length", "truncated"),
        ("no_tools", "tool_calls"),
        ("multiple", "tool_calls"),
        ("wrong_stage", "wrong_stage"),
        ("json", "arguments_json"),
        ("schema", "schema"),
    ],
)
def test_response_errors_identify_the_stage_without_leaking_output(caplog, change, reason):
    value = response()
    choice = value["choices"][0]
    calls = choice["message"]["tool_calls"]
    if change == "length":
        choice["finish_reason"] = "length"
    elif change == "no_tools":
        choice["message"] = {"content": "private test query"}
    elif change == "multiple":
        calls.append(copy.deepcopy(calls[0]))
    elif change == "wrong_stage":
        calls[0]["function"]["name"] = "private test query"
    elif change == "json":
        calls[0]["function"]["arguments"] = "private test query"
    else:
        calls[0]["function"]["arguments"] = json.dumps({"private test query": "private value"})
    with pytest.raises(StructuredResponseError) as raised:
        parse_structured_response(value, "batch", GroundedBatch)
    assert raised.value.reason == reason
    assert f"reason={reason}" in caplog.text
    assert "private" not in caplog.text and "private" not in str(raised.value)


def test_untrusted_finish_reason_cannot_leak_into_logs(caplog):
    value = response({"private test query": "private value"})
    value["choices"][0]["finish_reason"] = {"private test query": "private value"}
    with pytest.raises(StructuredResponseError):
        parse_structured_response(value, "batch", GroundedBatch)
    assert "finish_reason=unknown" in caplog.text and "private" not in caplog.text


def test_valid_arguments_preserve_normalization_and_validation():
    parsed = parse_structured_response(response({"cards": "[]"}), "batch", GroundedBatch)
    assert parsed.cards == []


def test_one_invalid_retrieval_lead_does_not_discard_valid_candidates(caplog):
    value = response(
        {
            "venues": [
                {"name": "独立书店", "source_ids": ["s1"]},
                {"name": "private test query", "invented_field": "private value"},
                {"name": "城市公园", "source_ids": '["s2"]'},
            ]
        }
    )
    parsed = parse_structured_response(value, "batch", SourceNomination)
    assert [(v.name, v.source_ids) for v in parsed.venues] == [
        ("独立书店", ["s1"]),
        ("城市公园", ["s2"]),
    ]
    assert "invalid_count=1 accepted_count=2" in caplog.text
    assert "private" not in caplog.text


@pytest.mark.parametrize(
    "venues",
    [
        [{"name": None}],
        [{"name": ""}],
        [None],
        [{"name": "place", "source_ids": ["s1", "s2", "s3", "s4", "s5"]}],
    ],
)
def test_no_valid_leads_remains_a_failure(venues):
    with pytest.raises(StructuredResponseError) as raised:
        parse_structured_response(response({"venues": venues}), "batch", SourceNomination)
    assert raised.value.reason == "schema"


def test_invalid_collection_and_oversized_nomination_are_not_silently_truncated():
    for venues in ("not an array", [{"name": f"place-{i}"} for i in range(13)]):
        with pytest.raises(StructuredResponseError):
            parse_structured_response(response({"venues": venues}), "batch", SourceNomination)


def test_invalid_candidate_filter_does_not_relax_other_stage_contracts():
    with pytest.raises(StructuredResponseError):
        parse_structured_response(
            response({"cards": [{"unknown": "field"}]}), "batch", GroundedBatch
        )


def test_malformed_model_envelope_terminates_workflow(tmp_path):
    from test_discovery_sources import workflow

    run, model = workflow(tmp_path)

    def invalid_plan(*args, **kwargs):
        return parse_structured_response({"choices": [{"message": None}]}, "plan", GroundedBatch)

    model.plan = invalid_plan
    run.run()
    result = run.snapshot()
    assert result["status"] == "failed" and not result["cards"]
    assert any(issue["code"] == "bad_response" for issue in result["issues"])


def truncated(arguments):
    value = response()
    value["choices"][0]["finish_reason"] = "length"
    value["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = arguments
    return value


@pytest.mark.parametrize("prefix", ["", '"public_note":"先核对位置",'])
def test_truncated_nomination_keeps_only_whole_candidates(caplog, prefix):
    arguments = "{" + prefix + '"venues":[{"name":"完整公园","source_ids":["s1"]},{"name":"不完整'
    parsed = parse_structured_response(
        truncated(arguments),
        "batch",
        SourceNomination,
        recover_truncated=SourceNomination.complete_prefix,
    )
    assert [(v.name, v.source_ids) for v in parsed.venues] == [("完整公园", ["s1"])]
    assert "discovery_response_recovered operation=batch reason=truncated" in caplog.text
    assert "完整公园" not in caplog.text and "不完整" not in caplog.text


@pytest.mark.parametrize(
    "arguments",
    [
        '{"venues":[{"name":"名字完整但对象未完","source_ids":',
        '{"venues":[',
        '{"venues":[]',
        '{"public_note":"未完成',
        '{"unknown":{},"venues":[{"name":"不能忽略前面的未知字段"}]',
        '{"venues":[{"name":"公园"} @',
        '{"venues":[{"name":null},{"name":"未完',
    ],
)
def test_incomplete_or_invalid_leads_are_never_completed_by_guessing(arguments):
    with pytest.raises(StructuredResponseError):
        parse_structured_response(
            truncated(arguments),
            "batch",
            SourceNomination,
            recover_truncated=SourceNomination.complete_prefix,
        )


def test_recovery_respects_strings_and_the_nomination_limit():
    name = '公园里的"venues":[{文字'
    complete = json.dumps({"name": name, "source_ids": []}, ensure_ascii=False)
    parsed = parse_structured_response(
        truncated('{"venues":[' + complete + ","),
        "batch",
        SourceNomination,
        recover_truncated=SourceNomination.complete_prefix,
    )
    assert parsed.venues[0].name == name
    with pytest.raises(StructuredResponseError):
        parse_structured_response(
            truncated(json.dumps({"venues": [{"name": str(i)} for i in range(13)]})),
            "batch",
            SourceNomination,
            recover_truncated=SourceNomination.complete_prefix,
        )


def test_recovery_does_not_apply_to_constraints_wrong_tools_or_unmarked_bad_json():
    with pytest.raises(StructuredResponseError):
        parse_structured_response(truncated('{"cards":[]}'), "batch", GroundedBatch)
    wrong = truncated('{"venues":[{"name":"公园"},')
    wrong["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "another_stage"
    with pytest.raises(StructuredResponseError):
        parse_structured_response(
            wrong, "batch", SourceNomination, recover_truncated=SourceNomination.complete_prefix
        )
    not_truncated = truncated('{"venues":[{"name":"公园"},')
    not_truncated["choices"][0]["finish_reason"] = "stop"
    with pytest.raises(StructuredResponseError):
        parse_structured_response(
            not_truncated,
            "batch",
            SourceNomination,
            recover_truncated=SourceNomination.complete_prefix,
        )


def test_source_nomination_recovers_with_one_existing_model_call():
    from types import SimpleNamespace

    from roambot.services.discovery_sources import DiscoverySourceModel

    requests = []
    value = truncated('{"venues":[{"name":"待地图核实的公园","source_ids":[]},{"name":"未完')
    value["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "nominate_source_places"

    def post(**kwargs):
        requests.append(kwargs)
        return value

    provider = SimpleNamespace(
        _model="same",
        _key="not-real",
        _enable_thinking=False,
        _http=SimpleNamespace(post_json=post),
    )
    model = DiscoverySourceModel(provider)
    result = model.nominate_sources([{"role": "user", "content": "公园散步"}], {}, [])
    assert len(result.venues) == 1 and len(requests) == 1
    assert requests[0]["json_body"]["max_tokens"] == 1200
