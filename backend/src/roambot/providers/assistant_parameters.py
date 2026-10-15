"""One native semantic contract. No sentence parsing or business tool execution."""

from copy import deepcopy
from datetime import date
from typing import Literal

from pydantic import Field, create_model, field_validator, model_validator

from roambot.domain.assistant import (
    AnswerPlan,
    AssistantDateRequest,
    AssistantDraft,
    AssistantModelReply,
    AssistantPatch,
)
from roambot.domain.models import DomainModel, SceneryType
from roambot.domain.scenery_rules import TYPE_TERMS
from roambot.domain.semantic_preferences import (
    SCENERY_KEYWORD_LIMIT,
    SCENERY_QUERY_LIMIT,
    normalize_scenery_keywords,
    normalize_scenery_query,
)

ASSISTANT_FUNCTION_NAME = "submit_travel_intent"


class SceneryPreferenceParameters(DomainModel):
    """One complete preference, so a replacement cannot retain hidden old filters."""

    categories: list[SceneryType] | None = Field(max_length=6)
    description: str | None = Field(min_length=1, max_length=SCENERY_QUERY_LIMIT)
    keywords: list[str] | None = Field(max_length=4)

    _description = field_validator("description")(normalize_scenery_query)
    _keywords = field_validator("keywords")(normalize_scenery_keywords)


# Reuse field types and bounds, not the patch's stateful/legacy repair behavior.
_fields = {
    name: (field.annotation, deepcopy(field))
    for name, field in AssistantDraft.model_fields.items()
    if name
    not in {
        "start_date",
        "end_date",
        "destination_regions",
        "scenery_types",
        "scenery_query",
        "scenery_keywords",
    }
}
_fields.update(
    date_request=(AssistantDateRequest | None, None),
    destination_region_names=(list[str] | None, Field(default=None, max_length=50)),
    scenery_preference=(SceneryPreferenceParameters | None, None),
)
AssistantParameterUpdates = create_model(
    "AssistantParameterUpdates", __base__=DomainModel, **_fields
)
UPDATE_FIELDS = frozenset(AssistantParameterUpdates.model_fields)


def unique_parameter_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate keys before JSON can silently choose the last operation."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON parameter key")
        result[key] = value
    return result


class AssistantParameters(DomainModel):
    intent: Literal["conditions", "answer", "unsupported", "conversation"]
    updates: AssistantParameterUpdates = Field(default_factory=AssistantParameterUpdates)
    question: str | None = Field(default=None, min_length=1, max_length=200)
    quick_replies: list[str] = Field(default_factory=list, max_length=3)
    unsupported_preferences: list[str] = Field(default_factory=list, max_length=5)
    answer_plan: AnswerPlan | None = None

    @model_validator(mode="before")
    @classmethod
    def explicit_values_have_types(cls, value):
        if not isinstance(value, dict) or any(item is None for item in value.values()):
            raise ValueError("explicit parameter values cannot be null")
        updates = value.get("updates", {})
        if not isinstance(updates, dict):
            raise ValueError("updates must be an object")
        if updates.get("max_distance_km") is not None and type(updates["max_distance_km"]) not in {
            int,
            float,
        }:
            raise ValueError("distance must be a number")
        temporal = updates.get("date_request")
        if isinstance(temporal, dict):
            if any(item is None for item in temporal.values()):
                raise ValueError("explicit date values cannot be null")
            for field in ("start_date", "end_date"):
                if field in temporal:
                    item = temporal[field]
                    if (
                        not isinstance(item, str)
                        or len(item) != 10
                        or date.fromisoformat(item).isoformat() != item
                    ):
                        raise ValueError("date must be ISO calendar text")
        weights = updates.get("weights")
        if isinstance(weights, dict) and any(
            type(item) not in {int, float} for item in weights.values()
        ):
            raise ValueError("weights must contain numbers")
        for field in ("question", "quick_replies", "unsupported_preferences"):
            item = value.get(field)
            texts = item if isinstance(item, list) else [item] if item is not None else []
            if any(isinstance(text, str) and not text.strip() for text in texts):
                raise ValueError("model text must not be blank")
        return value

    @model_validator(mode="after")
    def consistent_operations(self):
        updated = self.updates.model_fields_set
        if self.intent != "conditions" and updated:
            raise ValueError("only condition intent may edit or resolve fields")
        if (self.intent == "answer") != (self.answer_plan is not None):
            raise ValueError("answer requires only a facts plan")
        return self


def compile_assistant_parameters(value: object) -> AssistantModelReply:
    parameters = AssistantParameters.model_validate(value)
    updates = parameters.updates.model_dump(exclude_unset=True)
    reply = {
        "intent": parameters.intent,
        "question": parameters.question,
        "quick_replies": parameters.quick_replies,
        "unsupported_preferences": parameters.unsupported_preferences,
        "answer_plan": parameters.answer_plan,
    }
    for field in ("date_request", "destination_region_names"):
        if field in updates:
            item = updates.pop(field)
            if field == "date_request" and item is None:
                updates.update(start_date=None, end_date=None)
            else:
                reply[field] = [] if field == "destination_region_names" and item is None else item
    if "scenery_preference" in updates:
        preference = updates.pop("scenery_preference")
        for internal, public in (
            ("categories", "scenery_types"),
            ("description", "scenery_query"),
            ("keywords", "scenery_keywords"),
        ):
            updates[public] = preference[internal] if preference is not None else None
    reply["patch"] = AssistantPatch.model_validate(updates)
    return AssistantModelReply.model_validate(reply)


def _nonnullable_schema(value):
    """Remove nullable defaults; explicit cancellation is enabled only at edit keys."""
    if isinstance(value, list):
        return [_nonnullable_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {
        key: _nonnullable_schema(item)
        for key, item in value.items()
        if not (key == "default" and item is None)
    }
    if "anyOf" in result:
        variants = [item for item in result["anyOf"] if item.get("type") != "null"]
        if len(variants) == 1:
            result.pop("anyOf")
            result.update(variants[0])
        else:
            result["anyOf"] = variants
    return result


def assistant_parameter_tool() -> dict:
    schema = _nonnullable_schema(AssistantParameters.model_json_schema())
    schema["$defs"]["SceneryType"]["description"] = (
        "后台候选分类编号，用于筛选，不是用户必须选择的菜单："
        + "；".join(f"{category.value}={'/'.join(terms)}" for category, terms in TYPE_TERMS.items())
    )
    dates = schema["$defs"]["AssistantDateRequest"]["properties"]
    date_descriptions = {
        "offset_days": (
            "出发日距离今天的有符号天数偏移，仅在出发时间明确时提供；"
            "不是游玩时长、不是日期序号，不从游玩天数推导。与start_date二选一。"
        ),
        "duration_days": (
            "游玩总时长（天），包含出发日；不是出发日的偏移或返程日期。"
            "没有确定出发日也可以单独提供时长，不猜测出发时间。"
        ),
        "start_date": (
            "用户确定的出发日，格式YYYY-MM-DD；与offset_days二选一。"
            "没有明确出发时间时省略，不能根据时长补出日期。"
        ),
        "end_date": (
            "用户确定的返程日，格式YYYY-MM-DD；不是游玩天数。仅给时长时不计算此字段，计算交给程序。"
        ),
    }
    for name, description in date_descriptions.items():
        dates[name]["description"] = description
    updates = schema["$defs"]["AssistantParameterUpdates"]["properties"]
    preference = schema["$defs"]["SceneryPreferenceParameters"]["properties"]
    preference["categories"]["description"] = (
        "正向筛选类别，与描述和检索词保持一致；null或空数组会搜索全部类型。"
        "有明确类别时填写新类别，不将排除旧类别写成取消全部。"
    )
    preference["description"]["description"] = "当前完整偏好原意，包括仍保留的要求与排除条件。"
    preference["keywords"]["description"] = "当前正向地点检索词；去掉过时检索词，不含排除项。"
    preference["keywords"]["items"].update(minLength=1, maxLength=SCENERY_KEYWORD_LIMIT)
    descriptions = {
        "main_origin": "用户本人的出发地，不是目的地；只在本轮明确修改时提供",
        "companion_origins": "同行出发地的完整新数组，保留仍同行者；不改主出发地",
        "destination_region_names": (
            "目的地行政区域限制：准备游玩的省市名称完整新数组，不是出发地或具体景点。"
            "与公里距离上限独立；取消本项不修改max_distance_km。"
        ),
        "max_distance_km": (
            "从出发地到目的地的公里距离上限，不是目的地省市的行政区域限制。"
            "与destination_region_names独立；只在明确调整或取消路程上限时修改。"
        ),
        "date_request": "本轮明确改变的日期片段；程序运算，省略部分沿用记忆或原时长",
        "scenery_preference": (
            "本轮明确调整风景时提交完整新偏好，类别、描述、检索词必须齐全并相互一致。"
            "替换要去掉不再适用的旧描述和旧检索词；只改变一项时其余仍适用值也一并提交。"
            "整体取消用null，单独取消一项则仅将该子项设null并保留其他子项。"
        ),
        "target_place": "明确要求评估的具体地点，不用省市替代",
        "weights": "只在明确调整时提供；总和100，单人fairness=0，多人20",
    }
    for name, description in descriptions.items():
        updates[name]["description"] = description
    updates["companion_origins"]["items"].update(minLength=1, maxLength=200)
    updates["destination_region_names"]["items"].update(minLength=1, maxLength=100)
    for field in [*updates.values(), *preference.values()]:
        if "$ref" in field:
            field["anyOf"] = [{"$ref": field.pop("$ref")}, {"type": "null"}]
        else:
            field["type"] = [field["type"], "null"]
            if "enum" in field:
                field["enum"] = [*field["enum"], None]
        field["description"] = field.get("description", "") + "；null仅表示明确取消，省略表示保留。"
    properties = schema["properties"]
    properties["intent"]["description"] = (
        "每次函数调用必须提供意图分类，包括只取消条件时："
        "conditions=填写、修改、取消或澄清旅行条件；"
        "answer=解读已提供的地点事实；unsupported=咨询未接入能力；conversation=一般闲聊。"
        "不能只提交updates而省略intent。"
    )
    properties["updates"]["description"] = (
        "每个字段只出现一次：新值表示修改，null表示明确取消已确认条件，省略表示保持。"
        "未确定、尚未决定、未提供不是取消；新地点角色未确定时保留旧地点并追问。"
    )
    properties["question"]["description"] = (
        "仅对未确定事项追问，包括本轮地点角色未定；其他明确修改仍可提交。"
        "不重复确认已明确新条件，不以清空旧条件代替追问。"
    )
    return {
        "type": "function",
        "function": {
            "name": ASSISTANT_FUNCTION_NAME,
            "description": (
                "提交本轮旅行条件的语义理解、澄清或事实解读计划。只返回数据，不执行业务。"
            ),
            "parameters": schema,
        },
    }
