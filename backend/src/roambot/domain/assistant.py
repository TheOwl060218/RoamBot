"""Bounded conversational inputs; never coordinates, tools or business actions."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from roambot.domain.models import DomainModel, RankingWeights, SceneryMatchMode, SceneryType
from roambot.domain.regions import normalize_destination_regions
from roambot.domain.semantic_preferences import (
    normalize_scenery_keywords,
    normalize_scenery_query,
)


class AssistantDraft(DomainModel):
    mode: Literal["recommendation", "place_evaluation"] | None = None
    main_origin: str | None = Field(default=None, min_length=1, max_length=200)
    companion_origins: list[str] | None = Field(default=None, max_length=2)
    start_date: date | None = None
    end_date: date | None = None
    max_distance_km: float | None = Field(default=None, gt=0, le=500)
    scenery_types: list[SceneryType] | None = Field(default=None, max_length=6)
    scenery_match_mode: SceneryMatchMode | None = None
    scenery_query: str | None = None
    scenery_keywords: list[str] | None = None
    destination_regions: list[str] | None = Field(default=None, max_length=50)
    target_place: str | None = Field(default=None, min_length=1, max_length=200)
    weights: RankingWeights | None = None

    _scenery_query = field_validator("scenery_query")(normalize_scenery_query)
    _scenery_keywords = field_validator("scenery_keywords")(normalize_scenery_keywords)

    @field_validator("main_origin", "target_place")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("text must not be blank")
        return value

    @field_validator("companion_origins")
    @classmethod
    def strip_companions(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        values = [v.strip() for v in values]
        if any(not v or len(v) > 200 for v in values):
            raise ValueError("invalid companion origin")
        return values

    @field_validator("destination_regions")
    @classmethod
    def regions(cls, values: list[str] | None) -> list[str] | None:
        return normalize_destination_regions(values) if values is not None else None

    @field_validator("weights")
    @classmethod
    def total_weights(cls, value: RankingWeights | None) -> RankingWeights | None:
        if value and abs(sum(value.model_dump().values()) - 100) > 1e-6:
            raise ValueError("weights must total 100")
        return value


class AssistantPatch(AssistantDraft):
    """Sparse changes. Do not silently rewrite a model's semantic mistakes."""


class AssistantMessage(DomainModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AnswerPlan(DomainModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=7)
    topic: Literal["overview", "weather", "journey", "fairness", "rating"]


class AssistantDateRequest(DomainModel):
    """Model-interpreted temporal intent; arithmetic belongs to the application."""

    start_date: date | None = None
    offset_days: int | None = Field(default=None, ge=-366, le=366, strict=True)
    duration_days: int | None = Field(default=None, ge=1, le=31, strict=True)
    end_date: date | None = None

    @model_validator(mode="after")
    def has_unambiguous_anchor(self):
        if self.start_date is not None and self.offset_days is not None:
            raise ValueError("use either calendar start or relative offset")
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("date request must contain a temporal condition")
        return self


class AssistantConversationState(DomainModel):
    """Uncommitted semantic date fragments, not searchable confirmed conditions."""

    pending_date_request: AssistantDateRequest | None = None

    @model_validator(mode="before")
    @classmethod
    def explicit_empty_marker(cls, value):
        # Sparse response serialization must distinguish clearing pending memory
        # from an old server that did not supply any conversation-state field.
        if isinstance(value, dict) and "pending_date_request" not in value:
            return {"pending_date_request": None, **value}
        return value


class AssistantTurnRequest(DomainModel):
    message: str = Field(min_length=1, max_length=2000)
    revision: int = Field(ge=0, strict=True)
    draft: AssistantDraft
    history: list[AssistantMessage] = Field(default_factory=list, max_length=6)
    conversation_state: AssistantConversationState = Field(
        default_factory=AssistantConversationState
    )
    assistant_context: str | None = Field(default=None, max_length=65536)
    focused_destination_id: str | None = Field(default=None, max_length=200)


class AssistantModelReply(DomainModel):
    intent: Literal["conditions", "answer", "unsupported", "conversation"]
    patch: AssistantPatch = Field(default_factory=AssistantPatch)
    question: str | None = Field(default=None, min_length=1, max_length=200)
    quick_replies: list[str] = Field(default_factory=list, max_length=3)
    unsupported_preferences: list[str] = Field(default_factory=list, max_length=5)
    answer_plan: AnswerPlan | None = None
    date_request: AssistantDateRequest | None = None
    destination_region_names: list[str] | None = Field(default=None, max_length=50)

    @field_validator("destination_region_names")
    @classmethod
    def bounded_region_names(cls, values):
        if values is not None and any(
            not value.strip() or len(value) > 100 or any(c in value for c in "<>\n\r")
            for value in values
        ):
            raise ValueError("invalid region name")
        return values

    @field_validator("question", "quick_replies", "unsupported_preferences")
    @classmethod
    def safe_model_text(cls, value):
        values = value if isinstance(value, list) else [value]
        if any(v and (len(v) > 200 or "<" in v or ">" in v or "http" in v.lower()) for v in values):
            raise ValueError("model text must be bounded plain text")
        return value

    @model_validator(mode="after")
    def exclusive_intent(self) -> AssistantModelReply:
        if self.intent == "answer":
            if (
                self.answer_plan is None
                or self.patch.model_fields_set
                or self.date_request is not None
                or "destination_region_names" in self.model_fields_set
            ):
                raise ValueError("answer requires facts plan and cannot edit conditions")
        elif self.answer_plan is not None:
            raise ValueError("only answers have facts plans")
        if self.intent in {"unsupported", "conversation"} and (
            self.patch.model_fields_set
            or self.date_request is not None
            or "destination_region_names" in self.model_fields_set
        ):
            raise ValueError("pure capability replies cannot edit conditions")
        return self


class AssistantTurnResponse(DomainModel):
    revision: int
    reply: str = Field(max_length=4000)
    patch: AssistantPatch = Field(default_factory=AssistantPatch)
    confirmed_fields: list[str] = Field(
        default_factory=list, max_length=len(AssistantPatch.model_fields)
    )
    question: str | None = Field(default=None, max_length=200)
    quick_replies: list[str] = Field(default_factory=list, max_length=3)
    unsupported_preferences: list[str] = Field(default_factory=list, max_length=5)
    conversation_state: AssistantConversationState = Field(
        default_factory=AssistantConversationState
    )
    source: Literal["live", "demo", "degraded"]


def merge_assistant_patch(
    draft: AssistantDraft,
    patch: AssistantPatch,
    today: date,
    *,
    validate_existing_dates: bool = True,
) -> AssistantDraft:
    updates = patch.model_dump(exclude_unset=True)
    if ("start_date" in updates) != ("end_date" in updates):
        raise ValueError("date updates must be atomic")
    if "companion_origins" in updates and "weights" not in updates and draft.weights:
        fairness = 20 if updates["companion_origins"] else 0
        old = draft.weights
        total = old.weather + old.distance + old.popularity
        if total <= 0:
            raise ValueError("invalid relative weights")
        updates["weights"] = {
            "weather": old.weather / total * (100 - fairness),
            "distance": old.distance / total * (100 - fairness),
            "popularity": old.popularity / total * (100 - fairness),
            "fairness": fairness,
        }
    merged = AssistantDraft.model_validate(draft.model_dump() | updates)
    # A saved query can age while the page is open. Conversation may edit an
    # independent field without accepting those old dates for a new search.
    if validate_existing_dates or "start_date" in updates:
        if merged.start_date and not today <= merged.start_date <= today + timedelta(days=6):
            raise ValueError("start date outside forecast window")
        if merged.end_date and not today <= merged.end_date <= today + timedelta(days=6):
            raise ValueError("end date outside forecast window")
        if merged.start_date and merged.end_date and merged.end_date < merged.start_date:
            raise ValueError("end date precedes start date")
    if merged.weights and merged.weights.fairness != (20 if merged.companion_origins else 0):
        raise ValueError("fairness does not match origins")
    return merged


def required_question(draft: AssistantDraft, today: date) -> str | None:
    if not draft.main_origin:
        return "从哪里出发？"
    if not (
        draft.start_date
        and draft.end_date
        and today <= draft.start_date <= draft.end_date <= today + timedelta(days=6)
    ):
        return "准备哪天出发、哪天结束？可选择未来7天。"
    if draft.mode == "place_evaluation":
        if not draft.target_place:
            return "想评估哪个具体地点？"
    elif not (
        draft.scenery_types
        or draft.destination_regions
        or draft.scenery_query
        or draft.scenery_keywords
    ):
        return "想看什么风景？"
    if not draft.destination_regions and not draft.max_distance_km:
        return "想去哪些省市，或接受多远的路程？"
    return None
