"""Model observations; the program, rather than the model, applies acceptance rules."""

import json
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from roambot.domain.discovery import (
    CollectionAssessment,
    Contract,
    DirectionCoverage,
)


class EventPeriod(Contract):
    start_date: date
    end_date: date
    evidence_id: str
    quote: str = Field(min_length=1, max_length=180,
        description="逐字摘录本地点网页给出的实际活动和展期/场次日期，不引用营业时段或用户日期。")

    @model_validator(mode="after")
    def ordered(self):
        if self.end_date < self.start_date:
            raise ValueError("活动结束日期不能早于开始日期。")
        return self


class ActivityEvidence(Contract):
    kind: Literal["ongoing", "event", "venue_only", "unknown"] = Field(
        description="ongoing常态业务/常设内容/持续自然环境；event有举办期限或场次的活动；venue_only只有承载空间；unknown尚不清楚实际内容。")
    period: EventPeriod | None = Field(default=None,
        description="event有实际网页排期依据才填写，否则null；不能用营业时间、名称或用户日期补造展期。")


class RequirementFinding(Contract):
    requirement: int = Field(ge=1, le=12)
    state: Literal["supported", "unknown", "contradicted"]
    activity: ActivityEvidence | None = None
    registration_alignment: Literal["aligned", "inconclusive", "conflicting", "venue_only"] | None = Field(
        default=None,
        description="登记业态是否支持此活动：aligned相符，inconclusive宽泛，conflicting冲突，venue_only仅证明承载空间而非活动实际举办。网页活动证据另由state判断。",
    )
    evidence_ids: list[str] = Field(default_factory=list, max_length=4,
        description="supported和contradicted必须引用本地点sources的id；unknown可空。不能仅在整卡evidence_ids引用后省略此处。")
    note: str = Field(default="", max_length=100,
        description="仅有直接反证的contradicted可说明具体事实；supported和unknown省略，不把未知改写成不存在。")

    @model_validator(mode="before")
    @classmethod
    def citation_cardinality(cls, value):
        if not isinstance(value, dict):
            return value
        value = dict(value)

        def array(refs):
            if isinstance(refs, str):
                try:
                    decoded = json.loads(refs)
                    if isinstance(decoded, list):
                        return decoded
                except ValueError:
                    pass
                return [refs]
            return refs

        if "evidence_ids" in value:
            value["evidence_ids"] = array(value["evidence_ids"])
        if "evidence_id" in value:
            singular = array(value.pop("evidence_id"))
            if "evidence_ids" in value and singular != value["evidence_ids"]:
                raise ValueError("单数和复数引用不一致，不能替模型选择依据。")
            value["evidence_ids"] = singular
        return value


class AnchoredFact(Contract):
    evidence_id: str
    quote: str = Field(min_length=1, max_length=120,
        description="逐字摘录对应source.value或excerpt的事实，不摘录用户愿望或推测。")

    @model_validator(mode="before")
    @classmethod
    def literal_value(cls, value):
        if not isinstance(value, dict) or "value" not in value:
            return value
        value = dict(value)
        literal = value.pop("value")
        if "quote" in value and value["quote"] != literal:
            raise ValueError("事实摘录的quote与value不一致。")
        value["quote"] = literal
        return value


class CandidateAssessment(Contract):
    place_id: str = Field(min_length=1, max_length=200)
    entity_matches: bool
    entity_scope: Literal["place", "collection", "administrative_area", "unknown"] | None = None
    anchored_facts: list[AnchoredFact] = Field(default_factory=list, max_length=2,
        description="先从本地点sources选一两项理由要用的真实事实，逐字quote并引用id；实时核验必须填写。")
    grounded_reason: str = Field(
        min_length=20,
        max_length=90,
        description="20至60字，只选一两项确知事实说明该去处的价值及适配。未知事项仅在checks记录，不在理由中提及；不写资料不足、核验过程或待确认提醒。",
    )
    experience: str = Field(
        min_length=1, max_length=30, description="简短的实际活动标签，不写整句说明或不确定属性。"
    )
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    broad_intent_matches: bool = Field(
        description="只在没有明确逐地点活动目标时使用；评估核心意图，不把可取舍偏好当必要条件。"
    )
    checks: list[RequirementFinding] = Field(default_factory=list, max_length=12)
    note: str = Field(default="", max_length=100,
        description="仅实体或核心意图不匹配且checks无法说明时填写。")


class NativeBatchAssessment(Contract):
    assessments: list[CandidateAssessment] = Field(max_length=6)
    covered_directions: list[DirectionCoverage] = Field(default_factory=list, max_length=6,
        description="仅在context确实给出requested_directions及序号时可填写；未给出必须省略或为空，不能猜编号。")
    collection_assessments: list[CollectionAssessment] = Field(default_factory=list, max_length=12)
    evidence_query: str | None = Field(default=None, max_length=160)


class LiveRequirementFinding(RequirementFinding):
    activity: ActivityEvidence | None = Field(...,
        description="role=goal必须独立判断是常态活动、限时活动还是只有场地；不是活动目标的条件填null。限时活动需网页排期，不能将临时活动当常设内容。")
    registration_alignment: Literal["aligned", "inconclusive", "conflicting", "venue_only"] = Field(
        description="独立核对登记分类对实际活动的支持。名称不能补证；宽泛为inconclusive，其他业态为conflicting，仅有活动承载空间、无实际活动依据为venue_only。网页可另证实际服务和时段。",
    )


class LiveCandidateAssessment(CandidateAssessment):
    entity_scope: Literal["place", "collection", "administrative_area", "unknown"] = Field(
        description="独立判断是否一个具体可前往的地点place；多个地点总称/系列为collection，行政搜索范围为administrative_area，不能确定为unknown。不能仅因地图有坐标就认定总称是具体场所。")
    checks: list[LiveRequirementFinding] = Field(default_factory=list, max_length=12)


class LiveBatchAssessment(NativeBatchAssessment):
    assessments: list[LiveCandidateAssessment] = Field(max_length=6)


class CandidateBatch(Contract):
    candidate_ids: list[str] = Field(max_length=6)


class CollectionReview(Contract):
    collection_assessments: list[CollectionAssessment] = Field(max_length=12)
