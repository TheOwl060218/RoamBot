import json
from datetime import date

import httpx
import pytest

from roambot.domain.assistant import AssistantTurnRequest
from roambot.providers.assistant import AssistantFormatError, OpenAICompatibleAssistantProvider
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError


def native_call(arguments, *, name="submit_travel_intent", kind="function"):
    return {
        "id": "call-test",
        "type": kind,
        "function": {
            "name": name,
            "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
        },
    }


def response(calls, *, finish="stop", content=None):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": finish,
                    "message": {"role": "assistant", "content": content, "tool_calls": calls},
                }
            ]
        },
    )


def provider(client):
    return OpenAICompatibleAssistantProvider(
        ProviderHttpClient(
            client, provider="llm", base_url="https://fixture.invalid", secrets=("fake-key",)
        ),
        "fake-key",
        "unchanged-model",
        lambda: date(2026, 10, 13),
    )


def test_production_request_declares_native_contract_and_receives_parameters():
    def handle(request):
        body = json.loads(request.content)
        assert body["model"] == "unchanged-model"
        assert "response_format" not in body
        assert len(body["tools"]) == 1
        assert body["tool_choice"] == {
            "type": "function",
            "function": {"name": "submit_travel_intent"},
        }
        assert body["tools"][0]["function"]["parameters"]["required"] == ["intent"]
        intent = body["tools"][0]["function"]["parameters"]["properties"]["intent"]
        assert set(intent["enum"]) == {"conditions", "answer", "unsupported", "conversation"}
        assert all(label in intent.get("description", "") for label in intent["enum"])
        return response([native_call({"intent": "conditions", "updates": {"main_origin": "合肥"}})])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = provider(client).turn(
            AssistantTurnRequest(message="合肥出发", revision=0, draft={}), None
        )
    assert result.patch.model_dump(exclude_unset=True) == {"main_origin": "合肥"}


def test_sent_tool_documents_distance_and_region_as_independent_constraints():
    def handle(request):
        body = json.loads(request.content)
        fields = body["tools"][0]["function"]["parameters"]["$defs"]["AssistantParameterUpdates"][
            "properties"
        ]
        distance = fields["max_distance_km"]["description"]
        regions = fields["destination_region_names"]["description"]
        assert "公里" in distance and "省市" in distance
        assert "距离" in regions and "独立" in regions
        assert "null" in distance and "null" in regions
        assert body["tools"][0]["function"]["parameters"]["required"] == ["intent"]
        return response(
            [native_call({"intent": "conditions", "updates": {"destination_region_names": None}})]
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = provider(client).turn(
            AssistantTurnRequest(
                message="合成字段检查",
                revision=0,
                draft={"destination_regions": ["340100"], "max_distance_km": 90},
            ),
            None,
        )
    assert result.destination_region_names == []
    assert result.patch.model_fields_set == set()


@pytest.mark.parametrize(
    "calls,finish,content",
    [
        (None, "stop", '{"意图":"修改条件","更新":{"出发地":"合肥"}}'),
        ([], "stop", '{"intent":"conditions","patch":{"main_origin":"合肥"}}'),
        ([native_call({"intent": "conversation"})] * 2, "stop", None),
        ([native_call({"intent": "conversation"}, name="run_command")], "stop", None),
        ([native_call({"intent": "conversation"}, kind="invalid")], "stop", None),
        ([native_call({"intent": "conversation"})], "length", None),
        ([native_call("not-json")], "stop", None),
        ([native_call("x" * 16385)], "stop", None),
        (
            [
                native_call(
                    {"intent": "conditions", "updates": {"date_request": {"offset_days": None}}}
                )
            ],
            "stop",
            None,
        ),
        (
            [native_call({"intent": "conditions", "private_unknown": "PRIVATE_SENTINEL"})],
            "stop",
            None,
        ),
        ([None], "stop", None),
        (["invalid-call"], "stop", None),
    ],
)
def test_invalid_native_calls_reject_without_free_text_fallback(calls, finish, content, caplog):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: response(calls, finish=finish, content=content))
        ) as client,
        pytest.raises(ProviderError),
    ):
        provider(client).turn(
            AssistantTurnRequest(message="明天从苏州走", revision=0, draft={}), None
        )
    assert "PRIVATE_SENTINEL" not in caplog.text and "fake-key" not in caplog.text


def test_messages_preserve_real_history_current_state_and_pending_dates():
    def handle(request):
        messages = json.loads(request.content)["messages"]
        assert messages[1] == {"role": "assistant", "content": "从哪里出发？"}
        assert messages[2]["role"] == "system"
        current = json.loads(messages[2]["content"])
        assert current["current_conditions"]["main_origin"] == "广州"
        assert current["pending_date_request"] == {"duration_days": 3}
        assert messages[-1] == {"role": "user", "content": "明天走"}
        return response(
            [native_call({"intent": "conditions", "updates": {"date_request": {"offset_days": 1}}})]
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = provider(client).turn(
            AssistantTurnRequest(
                message="明天走",
                revision=7,
                draft={"main_origin": "广州"},
                history=[{"role": "assistant", "content": "从哪里出发？"}],
                conversation_state={"pending_date_request": {"duration_days": 3}},
            ),
            None,
        )
    assert result.date_request.offset_days == 1 and not result.patch.model_fields_set


def test_native_repair_uses_same_tool_and_memory_only_feedback(caplog):
    count = 0
    raw = '{"intent":"conditions","updates":{"scenery_query":""},"private":"PRIVATE_SENTINEL"}'

    def handle(request):
        nonlocal count
        count += 1
        body = json.loads(request.content)
        assert "tools" in body and "response_format" not in body
        if count == 1:
            return response([native_call(raw)])
        assert any(m["content"] == raw for m in body["messages"])
        return response(
            [
                native_call(
                    {
                        "intent": "conditions",
                        "updates": {"scenery_preference": None},
                    }
                )
            ]
        )

    request = AssistantTurnRequest(message="取消偏好", revision=0, draft={})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = provider(client)
        with pytest.raises(AssistantFormatError) as error:
            adapter.turn(request, None)
        result = adapter.repair_turn(request, None, error.value)
    assert count == 2
    assert result.patch.model_dump(exclude_unset=True) == {
        "scenery_query": None,
        "scenery_types": None,
        "scenery_keywords": None,
    }
    assert "PRIVATE_SENTINEL" not in caplog.text and "fake-key" not in caplog.text


@pytest.mark.parametrize("payload", [{"choices": [None]}, {"choices": [{"message": None}]}])
def test_malformed_envelope_is_provider_failure_not_server_exception(payload):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as client,
        pytest.raises(ProviderError),
    ):
        provider(client).turn(AssistantTurnRequest(message="测试", revision=0, draft={}), None)


@pytest.mark.parametrize(
    "arguments",
    [
        '{"intent":"conditions","updates":{"main_origin":"PRIVATE_PLACE","main_origin":null}}',
        '{"intent":"conditions","updates":{"main_origin":null,"main_origin":"PRIVATE_PLACE"}}',
        '{"intent":"conditions","intent":"conversation"}',
        '{"intent":"conditions","updates":{"date_request":{"duration_days":2,"duration_days":3}}}',
    ],
)
def test_duplicate_json_keys_cannot_choose_an_operation_by_serialization_order(arguments, caplog):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: response([native_call(arguments)]))
        ) as client,
        pytest.raises(AssistantFormatError) as failure,
    ):
        provider(client).turn(AssistantTurnRequest(message="修改条件", revision=0, draft={}), None)
    assert failure.value.problem == "json_syntax"
    assert "PRIVATE_PLACE" not in caplog.text


def test_current_preference_context_has_the_same_complete_shape_as_native_updates():
    def handle(request):
        messages = json.loads(request.content)["messages"]
        state = json.loads(messages[-2]["content"])["current_conditions"]
        assert state["scenery_preference"] == {
            "categories": ["lake"],
            "description": "湖边",
            "keywords": None,
        }
        assert not {"scenery_types", "scenery_query", "scenery_keywords"}.intersection(state)
        return response([native_call({"intent": "conversation"})])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = provider(client).turn(
            AssistantTurnRequest(
                message="谢谢",
                revision=0,
                draft={"scenery_types": ["lake"], "scenery_query": "湖边"},
            ),
            None,
        )
    assert not result.patch.model_fields_set


def test_system_offset_definition_agrees_with_schema_departure_role():
    from roambot.providers.assistant_parameter_messages import parameter_messages

    instructions = parameter_messages(
        AssistantTurnRequest(message="日期语义测试", revision=0, draft={}),
        None,
        date(2026, 10, 13),
    )[0]["content"]
    definition = next(
        sentence for sentence in instructions.split("。") if sentence.startswith("offset_days")
    )
    assert "出发日" in definition.split("；")[0].split("，")[0], (
        "system instructions must not widen an offset into any travel date"
    )
    assert "返程日" in definition and "end_date" in definition
    assert "未定" in definition and "不补" in definition
