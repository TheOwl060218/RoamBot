import json
from types import SimpleNamespace

import pytest

from roambot.providers.business_planner import plan_business_actions
from roambot.providers.protocols import ProviderError


class Http:
    def __init__(self, message):
        self.message = message
        self.body = None

    def post_json(self, **kwargs):
        self.body = kwargs["json_body"]
        self.timeout = kwargs.get("timeout")
        return {"choices": [{"message": self.message, "finish_reason": "tool_calls"}]}


def call(name, args):
    return {"type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_native_planner_selects_tasks_without_http_or_identity_parameters():
    http = Http(
        {
            "tool_calls": [
                call("favorite_place", {"place": 2}),
                call("create_plan_from_selection", {"name": "周末出游"}),
            ]
        }
    )
    result = plan_business_actions(
        http, "fixture", "fixture", None, SimpleNamespace(message="收藏第二个，再建计划"), {}
    )
    assert [a["tool"] for a in result["actions"]] == [
        "favorite_place",
        "create_plan_from_selection",
    ]
    assert len(http.body["tools"]) == 1
    steps = http.body["tools"][0]["function"]["parameters"]["properties"]["actions"]
    assert len(steps["items"]["anyOf"]) >= 40
    assert http.body["tool_choice"] == "auto"
    assert http.body["parallel_tool_calls"] is True


@pytest.mark.parametrize('configured, expected', [(7, 20), (35, 35)])
def test_business_planning_has_time_for_tool_catalog_without_shortening_custom_timeout(configured, expected):
    http = Http({'tool_calls': [call('navigate', {'page': 'explore'})]})
    http._timeout = configured
    plan_business_actions(http, 'fixture', 'fixture', None, SimpleNamespace(message='打开新推荐'), {})
    assert http.timeout == expected


def test_clipboard_is_only_exposed_after_an_explicit_copy_request():
    http = Http({"tool_calls": [call("copy_link", {})]})
    with pytest.raises(ProviderError):
        plan_business_actions(
            http, "fixture", "fixture", False, SimpleNamespace(message="生成邀请链接"), {}
        )
    result = plan_business_actions(
        http, "fixture", "fixture", False, SimpleNamespace(message="复制刚才的邀请链接"), {}
    )
    assert result["actions"][0]["tool"] == "copy_link"


def test_native_sequence_preserves_order_on_single_call_gateways():
    http = Http(
        {
            "tool_calls": [
                call(
                    "plan_business_actions",
                    {
                        "actions": [
                            {
                                "tool": "create_plan_from_selection",
                                "arguments": {"name": "周末出游"},
                            },
                            {"tool": "rotate_invite", "arguments": {}},
                        ],
                        "question": None,
                    },
                )
            ]
        }
    )
    result = plan_business_actions(
        http, "fixture", "fixture", False, SimpleNamespace(message="建立计划，再生成邀请"), {}
    )
    assert [a["tool"] for a in result["actions"]] == ["create_plan_from_selection", "rotate_invite"]


@pytest.mark.parametrize(
    "message",
    [
        {"tool_calls": [call("fetch_url", {"url": "https://example.com"})]},
        {"tool_calls": [call("create_plan_from_selection", {"user_id": "other"})]},
        {"tool_calls": [call("navigate", {"page": "https://example.com"})]},
        {"tool_calls": []},
        {
            "tool_calls": [
                call(
                    "plan_business_actions",
                    {
                        "actions": [
                            {"tool": "delete_history", "arguments": {}},
                        ],
                        "question": "删除哪条？",
                    },
                )
            ]
        },
        {
            "tool_calls": [
                call(
                    "plan_business_actions",
                    {
                        "actions": [
                            {"tool": "fetch_url", "arguments": {"url": "https://example.com"}},
                        ],
                        "question": None,
                    },
                )
            ]
        },
    ],
)
def test_native_planner_rejects_invalid_or_unsafe_output(message):
    with pytest.raises(ProviderError):
        plan_business_actions(
            Http(message), "fixture", "fixture", None, SimpleNamespace(message="操作"), {}
        )


def test_ambiguous_request_returns_question_without_mutations():
    result = plan_business_actions(
        Http({"content": "你指的是哪个计划？"}),
        "fixture",
        "fixture",
        None,
        SimpleNamespace(message="删除那个"),
        {},
    )
    assert result["actions"] == []
    assert result["question"] == "你指的是哪个计划？"


def test_explicit_action_sequence_uses_structured_mode_instead_of_incidental_prose():
    http = Http({'content': '需要根据选中的两个地点创建计划。', 'tool_calls': [call('plan_business_actions', {
        'actions': [{'tool': 'create_plan_from_selection', 'arguments': {'name': '周末'}}], 'question': None})]})
    result = plan_business_actions(http, 'fixture', 'fixture', None, SimpleNamespace(message='创建计划'), {})
    assert result['question'] is None
    assert [a['tool'] for a in result['actions']] == ['create_plan_from_selection']
    assert 'content' not in result


@pytest.mark.parametrize('calls', [
    [call('favorite_place', {'place': 2})],
    [call('plan_business_actions', {'actions': [{'tool': 'favorite_place', 'arguments': {'place': 2}}]})],
])
def test_prose_with_actions_without_explicit_structured_mode_remains_rejected(calls):
    with pytest.raises(ProviderError):
        plan_business_actions(Http({'content': '你确定吗？', 'tool_calls': calls}),
            'fixture', 'fixture', None, SimpleNamespace(message='收藏'), {})
