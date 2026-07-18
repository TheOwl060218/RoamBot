from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from roambot.domain.models import RecommendationItem
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError


class _Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_id: str = Field(min_length=1)
    reason: str = Field(min_length=20, max_length=180)

    @field_validator("destination_id", "reason")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("reason")
    @classmethod
    def reject_markdown_fences(cls, value: str) -> str:
        if "```" in value:
            raise ValueError("markdown fences are not allowed")
        return value


class _ExplanationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanations: list[_Explanation]


class OpenAICompatibleExplanationProvider:
    def __init__(
        self,
        http: ProviderHttpClient,
        api_key: str,
        model: str,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._model = model

    def explain(self, items: list[RecommendationItem]) -> list[str]:
        if not items:
            return []
        if len(items) > 5:
            raise ProviderError("bad_request", "AI 解释最多支持五个地点")

        payload = self._http.post_json(
            operation="llm",
            path="/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json_body={
                "model": self._model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你只根据给定事实生成简短中文推荐理由，不得虚构。"
                            "输出严格 JSON：explanations 数组，每项含 destination_id 和 reason。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "destinations": [_public_summary(item) for item in items],
                                "limitations": "距离和天气为本次评估快照，仅用于推荐理由。",
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
            },
        )
        try:
            choices = payload["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError
            first = choices[0]
            if not isinstance(first, dict):
                raise ValueError
            message = first["message"]
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError
            decoded = json.loads(message["content"])
            envelope = _ExplanationEnvelope.model_validate(decoded)
            by_id = {entry.destination_id: entry.reason for entry in envelope.explanations}
            expected_ids = [item.destination.provider_id for item in items]
            if len(by_id) != len(envelope.explanations) or set(by_id) != set(expected_ids):
                raise ValueError
            return [by_id[destination_id] for destination_id in expected_ids]
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ):
            raise ProviderError("bad_response", "AI 解释格式无效") from None


def _public_summary(item: RecommendationItem) -> dict[str, object]:
    return {
        "destination_id": item.destination.provider_id,
        "name": item.destination.name,
        "scenery": sorted(tag.value for tag in item.destination.scenery_tags),
        "score": item.score.model_dump(mode="json"),
        "distance_km": [distance.distance_km for distance in item.distances],
        "weather": [
            {
                "date": day.date.isoformat(),
                "condition": day.condition,
                "temp_min_c": day.temp_min_c,
                "temp_max_c": day.temp_max_c,
                "precipitation_mm": day.precipitation_mm,
            }
            for day in item.weather
        ],
    }
