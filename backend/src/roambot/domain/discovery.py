"""Open-ended discovery: goals remain natural language, facts remain typed."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from roambot.domain.models import Coordinate
from roambot.domain.business_tools import BusinessPlan
from roambot.domain.assistant import AssistantDateRequest, AssistantMessage


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DiscoveryView(Contract):
    focused_id: str | None = Field(default=None, max_length=200)
    selected_ids: list[str] = Field(default_factory=list, max_length=3)
    layer: str = Field(default="results", max_length=40)


class DiscoveryLocationDetails(Contract):
    source: Literal['device', 'selected'] = 'device'
    accuracy_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    captured_at: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    replace_origin: bool = False


class DiscoveryRequest(Contract):
    message: str = Field(min_length=1, max_length=2000)
    previous_id: str | None = Field(default=None, max_length=64)
    explore_mode: Literal['batch', 'area'] | None = None
    location: Coordinate | None = None
    use_location: bool = True
    location_details: DiscoveryLocationDetails | None = None
    view: DiscoveryView = Field(default_factory=DiscoveryView)
    conversation: list[AssistantMessage] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def location_metadata(self):
        if self.explore_mode and not self.previous_id:
            raise ValueError('继续探索需要原推荐会话。')
        if self.location_details and not self.location:
            raise ValueError('定位信息需要对应坐标。')
        if self.location_details and self.location_details.source == 'selected' and not self.location_details.name:
            raise ValueError('所选位置需要地点名称。')
        return self


class SearchContext(Contract):
    origin: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=100)
    max_distance_km: float | None = Field(default=None, gt=0, le=500)
    travel_mode: Literal["walking", "bicycling", "driving"] = "walking"
    start_date: date | None = None
    end_date: date | None = None
    origin_quote: str | None = Field(default=None, max_length=200)
    distance_quote: str | None = Field(default=None, max_length=200)
    date_quote: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def interval(self):
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("日期需成对给出，未提供时都留空。")
        if self.start_date and self.end_date < self.start_date:
            raise ValueError("结束日期早于开始日期。")
        return self


class SearchPlaces(Contract):
    query: str = Field(
        min_length=1,
        max_length=100,
        description="简短地点/设施检索词；地区由context.region限定，不重复地区和整段活动要求。",
    )


class PlaceIds(Contract):
    place_ids: list[str] = Field(min_length=1, max_length=6)


class SearchEvidence(Contract):
    query: str = Field(min_length=1, max_length=200)
    place_ids: list[str] = Field(default_factory=list, max_length=6)


class InspectPlaces(PlaceIds):
    research_focus: str | None = Field(default=None, max_length=100)


class ProposedCard(Contract):
    place_id: str = Field(min_length=1, max_length=200)
    experience: str = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=20, max_length=180)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class Publish(Contract):
    cards: list[ProposedCard] = Field(min_length=1, max_length=6)


class Finish(Contract):
    reply: str = Field(min_length=1, max_length=500)
    request_location: bool = False


class RejectedCard(Contract):
    place_id: str
    note: str = Field(min_length=1, max_length=180)


class DirectionCoverage(Contract):
    direction: int = Field(ge=1, le=6)
    place_ids: list[str] = Field(min_length=1, max_length=6)


class EvidenceNeed(Contract):
    place_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=160)
    date_sensitive: bool = False
    requirement: int | None = Field(default=None, ge=1, le=12,
        description="对应本轮用户条件的序号；有条件时必须填写，不得把偏好缺口当必要条件。")


class CollectionAssessment(Contract):
    requirement: int = Field(ge=1, le=12)
    satisfied: bool
    place_ids: list[str] = Field(default_factory=list, max_length=18)
    note: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def grounded_members(self):
        if self.satisfied and not self.place_ids:
            raise ValueError("整组要求通过时须引用实际参与判断的地点。")
        return self


class ReasonRevision(Contract):
    place_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=20, max_length=180)
    experience: str | None = Field(default=None, min_length=1, max_length=30)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class BatchReview(Contract):
    approved_ids: list[str] = Field(max_length=6)
    rejected: list[RejectedCard] = Field(max_length=6)
    evidence_query: str | None = Field(default=None, max_length=160)
    covered_directions: list[DirectionCoverage] = Field(default_factory=list, max_length=6)
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list, max_length=6)
    collection_assessments: list[CollectionAssessment] = Field(default_factory=list, max_length=12)
    reason_revisions: list[ReasonRevision] = Field(default_factory=list, max_length=6)
    source_assessment: dict | None = None


class ExperienceRequirement(Contract):
    text: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=200)
    role: Literal["goal", "condition"] = Field(
        default="condition",
        description="想进行的动作及体验目的用goal，包括可观察的活动；只有用户明确要求的属性、设施或政策用condition，不把实现活动所推测需要的设施增为门槛。",
    )
    scope: Literal["place", "collection"] = Field(
        default="place", description="place约束单个候选；collection约束整组结果，不能逐卡强制满足。"
    )
    importance: Literal["required", "preferred", "accepted"] = Field(default="required",
        description="required为核心目标/硬条件，preferred为希望更好的倾向；accepted为允许或不介意，不能当成正向偏好、排序优势或补查目标。")
    map_field: Literal["name_and_type", "map_type", "city", "address", "opentime_today", "opentime_week", "cost"] | None = Field(
        default=None,
        description="地图原始字段。name_and_type可用于明确自述主营业态，不证明细节设施、可进入性或服务政策。",
    )


class RequirementSupport(Contract):
    requirement: int = Field(ge=1, le=12)
    passage_ids: list[str] = Field(min_length=1, max_length=3)


class GroundedCard(ProposedCard):
    requirement_support: list[RequirementSupport] = Field(default_factory=list, max_length=12)


class UnsuitableCandidate(RejectedCard):
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class GroundedBatch(Contract):
    cards: list[GroundedCard] = Field(default_factory=list, max_length=6)
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list, max_length=6)
    not_suitable: list[UnsuitableCandidate] = Field(default_factory=list, max_length=6)


class RetrievalDirection(Contract):
    experience: str = Field(min_length=1, max_length=60)
    map_query: str = Field(min_length=1, max_length=100,
        description="核心活动的宽召回词，不含preferred条件；可取舍条件单独放preference_query。")
    web_query: str = Field(min_length=1, max_length=160,
        description="核心活动的资料查询，不把preferred属性作为全部结果的前提。")
    preference_query: str | None = Field(default=None, min_length=1, max_length=100,
        description="可选的偏好补充地图词。程序先保留全部核心检索，再在有余量时补搜本项。")


class TemporalIntent(Contract):
    quote: str = Field(min_length=1, max_length=200,
        description="本次新增/更正的日期原文，包含相对日期、星期或时间区间，逐字摘录。")
    request: AssistantDateRequest = Field(
        description="解释日历日期或相对今天的天数、持续天数；由程序算起止日期，不把开始/结束/时长混用。")


class RequirementGroup(Contract):
    quote: str = Field(min_length=1, max_length=200)
    operator: Literal["any", "all"]
    requirements: list[int] = Field(min_length=2, max_length=12,
        description="requirements中从1开始的逐地点必要项目序号。any任选一项，all每项都满足。")


class ActivityOption(Contract):
    quote: str = Field(min_length=1, max_length=100,
        description="该分支活动的逐字原话；不同活动分别填写，不合成一个复合场所。")
    experience: str = Field(min_length=1, max_length=60)
    map_query: str = Field(min_length=1, max_length=80,
        description="只召回本分支的一条简短关键词，不拼入其他可选活动、偏好或排除项。")
    web_query: str = Field(min_length=1, max_length=160)


class ActivityRelation(Contract):
    operator: Literal["any", "all"] = Field(
        description="any表示用户接受任一核心活动，all表示同一去处须同时满足这些活动。")
    quote: str = Field(min_length=1, max_length=200,
        description="包含相关核心活动及其关系的完整原话，程序按成员quote绑定，不要求模型重复编号。")
    importance: Literal["required", "preferred"] = "required"
    options: list[ActivityOption] = Field(default_factory=list, max_length=6)


class ModelActivityRelation(ActivityRelation):
    importance: Literal["required", "preferred"] = Field(...,
        description="这些活动是本次核心选择则required，只有可取舍的倾向才preferred，不能升级软偏好。")
    options: list[ActivityOption] = Field(..., min_length=2, max_length=6,
        description="分别解释每个可选活动并给各自的召回词；程序保留分支，不要求地点兼有所有选项。")


class CollectionIntent(Contract):
    quote: str = Field(min_length=1, max_length=200)
    importance: Literal["required", "preferred"] = Field(
        description="明确数量/多样性/分布要求为required，可取舍的希望为preferred；不能互换。")


class RetrievalPlan(Contract):
    explore_mode: Literal['batch', 'area'] | None = None
    temporal: TemporalIntent | None = None
    activity_relation: ActivityRelation | None = None
    collection_intent: CollectionIntent | None = None
    collection_quote: str | None = Field(default=None, min_length=1, max_length=200,
        description="用户对整组数量/种类/分布的明确原话。存在时还须填scope=collection的requirements。")
    requirement_groups: list[RequirementGroup] = Field(default_factory=list, max_length=6)
    intent: Literal["search", "business"] = "search"
    business_plan: BusinessPlan | None = None
    context: SearchContext
    goal: str = Field(min_length=1, max_length=500)
    web_queries: list[str] = Field(default_factory=list, max_length=6)
    map_queries: list[str] = Field(default_factory=list, max_length=6)
    directions: list[RetrievalDirection] = Field(default_factory=list, max_length=6)
    reuse_previous: bool = False
    request_location: bool = False
    nearby_quote: str | None = Field(default=None, min_length=1, max_length=200,
        description="仅用户要求在出发点周边或当前位置附近寻找时，逐字摘录对应原文。仅去某城市不填；距离默认值由程序处理。")
    clear_fields: list[Literal["origin", "region", "max_distance_km", "start_date", "end_date"]] = (
        Field(default_factory=list, max_length=5)
    )
    clear_quote: str | None = Field(default=None, max_length=200)
    travel_mode_quote: str | None = Field(default=None, max_length=200)
    requirements: list[ExperienceRequirement] = Field(default_factory=list, max_length=12)


class SearchContextUpdate(SearchContext):
    travel_mode_quote: str | None = Field(default=None, max_length=200)
    @model_validator(mode="after")
    def interval(self):
        # A native sparse update may contain one endpoint. The execution layer
        # must resolve it and validate a complete SearchContext before retrieval.
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期早于开始日期。")
        return self


class ModelRetrievalPlan(RetrievalPlan):
    # Mandatory nullable/empty decisions make omissions visible in the native
    # protocol while old stored plans and non-native adapters remain readable.
    context: SearchContextUpdate
    temporal: TemporalIntent | None = Field(...,
        description="先核对本轮是否提供可确定的出游日期/区间；有则解析，未说或仅泛指有空时才为null。")
    activity_relation: ModelActivityRelation | None = Field(...,
        description="多个核心活动时必须明确any或all并摘录关系原话；只有单一活动或无明确活动才null。不要把任选活动都降成偏好。")
    collection_intent: CollectionIntent | None = Field(...,
        description="先核对整组数量/多样性/分布要求；有则填原话quote及importance，否则null。程序编译为整组要求，不必在requirements重复。")
    requirement_groups: list[RequirementGroup] = Field(default_factory=list,
        description="额外复杂组合才填写；activity_relation由程序按原话编译成员，无需重复编号。")


class VenueLead(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    place_id: str | None = None
    source_urls: list[str] = Field(default_factory=list, max_length=4)
    source_ids: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def identified(self):
        if not self.name and not self.place_id:
            raise ValueError("候选须引用已有地点ID或给出待核实名称。")
        return self


class VenueSelection(Contract):
    venues: list[VenueLead] = Field(default_factory=list, max_length=12)
    evidence_query: str | None = Field(default=None, max_length=160)
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list, max_length=6)


class RecommendationBatch(Contract):
    cards: list[ProposedCard] = Field(default_factory=list, max_length=6)


TOOLS = {
    "inspect_places": (
        InspectPlaces,
        "批量核实候选：按已提供的信息取路线和天气；research_focus可补查每个地点的公开资料。",
    ),
    "set_context": (
        SearchContext,
        "设置本次已表达的地区、出发地、路程、出行方式、日期；未提供留空。",
    ),
    "search_places": (SearchPlaces, "按任意自然语言检索词搜索真实地点，不限类别。可换词多次检索。"),
    "search_evidence": (
        SearchEvidence,
        "检索本次地区的活动与地点资料，优先官方。place_ids=[]可先发现具体去处，"
        "随后search_places核实地点时自动关联已取得的对应资料，不必重复搜索。",
    ),
    "measure_routes": (PlaceIds, "按当前出发地和出行方式核实实际路线；没有出发地时不可用。"),
    "check_weather": (PlaceIds, "仅在用户提供日期时获取对应地点天气；非本轮维度不查询。"),
    "publish_batch": (
        Publish,
        "发布本批逐个写好的推荐理由，引用已返回的证据ID；已发布位置不再改变。",
    ),
    "finish": (Finish, "结束本轮。仅缺必要位置且无法继续时可request_location=true。"),
}


def native_tools(allowed=None):
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters.model_json_schema(),
            },
        }
        for name, (parameters, description) in TOOLS.items()
        if allowed is None or name in allowed
    ]
