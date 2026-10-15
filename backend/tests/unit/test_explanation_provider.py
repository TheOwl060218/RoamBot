import json
from datetime import date

import httpx
import pytest

from roambot.domain.models import (
    Coordinate,
    DailySuitability,
    DailyWeather,
    Destination,
    DistanceEstimate,
    ExplanationContext,
    GroupAccessibilityScore,
    RankingWeights,
    RecommendationItem,
    SceneryMatchMode,
    SceneryType,
    ScoreBreakdown,
)
from roambot.providers.http import ProviderHttpClient
from roambot.providers.openai_compatible import OpenAICompatibleExplanationProvider
from roambot.providers.protocols import ProviderError

FAKE_KEY = "llm-test-secret"
PRIVATE_ORIGIN = "我的私人家庭住址 123 号"


def item(provider_id: str, name: str) -> RecommendationItem:
    weather = DailyWeather(
        date=date(2026, 7, 20),
        condition="晴",
        temp_min_c=24,
        temp_max_c=31,
        precipitation_mm=0,
        wind_speed_kmh=10,
        humidity_percent=60,
        visibility_km=20,
        uv_index=7,
    )
    return RecommendationItem(
        destination=Destination(
            provider_id=provider_id,
            name=name,
            address="公开景点地址",
            city="苏州",
            coordinate=Coordinate(longitude=120.7, latitude=31.3),
            type_name="湖泊景区",
            type_code="test",
            scenery_tags=frozenset({SceneryType.LAKE}),
            popularity_rank=1,
        ),
        distances=[
            DistanceEstimate(
                origin_label=PRIVATE_ORIGIN,
                distance_km=12.3,
                duration_minutes=25,
            )
        ],
        group_accessibility=GroupAccessibilityScore(
            average_distance_km=12.3,
            max_distance_km=12.3,
            distance_variance=0,
            distance_stddev=0,
            fairness_score=100,
        ),
        weather=[weather],
        daily_suitability=[DailySuitability(date=weather.date, score=88, reasons=["天气适宜"])],
        score=ScoreBreakdown(
            weather=88,
            distance=75,
            fairness=100,
            popularity=90,
            coverage_penalty=0,
            total=84.2,
        ),
        explanation="",
    )


def provider_for(handler: object) -> OpenAICompatibleExplanationProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = ProviderHttpClient(
        client,
        provider="llm",
        base_url="https://llm.example.com",
        secrets=(FAKE_KEY,),
    )
    return OpenAICompatibleExplanationProvider(http, FAKE_KEY, "deepseek-v4-flash")


def explanation_context() -> ExplanationContext:
    return ExplanationContext(
        requested_scenery_types=(SceneryType.LAKE,),
        scenery_match_mode=SceneryMatchMode.COVER_ALL,
        display_weights=RankingWeights(
            weather=40,
            distance=30,
            fairness=0,
            popularity=30,
        ),
    )


def test_factory_non_thinking_policy_reaches_both_assistant_and_recommendation_calls():
    from roambot.config import Settings
    from roambot.domain.assistant import AssistantTurnRequest
    from roambot.providers.factory import _build_live_adapters

    bodies = []

    def handle(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert body["model"] == "qwen3.7-plus"
        assert body["enable_thinking"] is False
        if "tools" in body:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "type": "function",
                                        "function": {
                                            "name": "submit_travel_intent",
                                            "arguments": json.dumps(
                                                {
                                                    "intent": "conditions",
                                                    "updates": {"main_origin": "合肥"},
                                                }
                                            ),
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            )
        return response(
            [
                {
                    "destination_id": "test-place",
                    "reason": "此处天气晴朗而且距离较近，可结合当日实际情况选择游览。",
                }
            ]
        )

    settings = Settings(
        provider_mode="live",
        demo_mode=False,
        qweather_api_host="https://student.qweatherapi.com",
        llm_base_url="https://fixture.invalid/v1",
        llm_model="qwen3.7-plus",
        llm_enable_thinking=False,
    )
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapters = _build_live_adapters(
            settings=settings,
            credentials={
                "amap_api_key": "fake-amap",
                "qweather_api_key": "fake-weather",
                "llm_api_key": "fake-llm",
            },
            client=client,
            cache_repository=None,
        )
        result = adapters.assistant.turn(
            AssistantTurnRequest(message="合成测试", revision=0, draft={}), None
        )
        reasons = adapters.explanations.explain(
            [item("test-place", "测试景点")], explanation_context()
        )
    assert result.patch.main_origin == "合肥"
    assert len(bodies) == 2 and len(reasons) == 1


def response(explanations: list[dict[str, str]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"explanations": explanations},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        },
    )


def test_empty_items_make_no_llm_call() -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called")

    assert provider_for(forbidden).explain([], explanation_context()) == []


def test_one_call_uses_structured_request_and_reorders_output() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-flash"
        assert body["temperature"] == 0.2
        assert body["response_format"] == {"type": "json_object"}
        serialized = request.content.decode("utf-8")
        assert PRIVATE_ORIGIN not in serialized
        assert FAKE_KEY not in serialized
        assert "username" not in serialized
        assert "share_token" not in serialized
        assert '"score"' not in serialized
        assert '"address"' not in serialized
        assert '"coordinate"' not in serialized
        user_payload = json.loads(body["messages"][1]["content"])
        forecast = user_payload["destinations"][0]["weather"][0]
        assert forecast["wind_speed_kmh"] == 10
        assert forecast["visibility_km"] == 20
        assert forecast["uv_index"] == 7
        assert user_payload["preferences"]["requested_scenery_types"] == ["lake"]
        assert user_payload["preferences"]["scenery_match_mode"] == "cover_all"
        return response(
            [
                {
                    "destination_id": "poi-2",
                    "reason": "湖景环境舒适，综合距离与天气表现适合本次出行选择。",
                },
                {
                    "destination_id": "poi-1",
                    "reason": "天气适宜且路程压力较小，综合评分支持优先考虑这个地点。",
                },
            ]
        )

    explanations = provider_for(handler).explain(
        [item("poi-1", "金鸡湖景区"), item("poi-2", "湖滨公园")],
        explanation_context(),
    )

    assert len(requests) == 1
    assert explanations[0].startswith("天气适宜")
    assert explanations[1].startswith("湖景环境")


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        json.dumps({"explanations": []}),
        json.dumps(
            {
                "explanations": [
                    {
                        "destination_id": "unknown",
                        "reason": "这是一个长度足够但地点编号错误的推荐理由文本。",
                    }
                ]
            }
        ),
        json.dumps({"explanations": [{"destination_id": "poi-1", "reason": "太短"}]}),
        json.dumps(
            {
                "explanations": [
                    {
                        "destination_id": "poi-1",
                        "reason": "```这是一段被代码围栏包裹且长度足够的无效理由文本。```",
                    }
                ]
            }
        ),
    ],
)
def test_malformed_partial_or_markdown_output_is_rejected(content: str) -> None:
    provider = provider_for(
        lambda _: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    )

    with pytest.raises(ProviderError) as captured:
        provider.explain([item("poi-1", "金鸡湖景区")], explanation_context())
    assert captured.value.code == "bad_response"
    assert str(captured.value) == "AI 解释格式无效"
