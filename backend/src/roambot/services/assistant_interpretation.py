"""Resolve semantic model fields; never parse the user's sentence to guess intent."""

import re
from datetime import date, timedelta

from roambot.domain.assistant import (
    AssistantConversationState,
    AssistantDateRequest,
    AssistantDraft,
    AssistantModelReply,
    AssistantPatch,
)
from roambot.domain.regions import normalize_destination_regions, region_catalog


def _region_alias(name: str) -> str:
    return re.sub(
        r"(?:特别行政区|维吾尔自治区|壮族自治区|回族自治区|自治区|省|市)$", "", name.strip()
    )


def resolve_region_names(names: list[str]) -> list[str]:
    rows = region_catalog()["regions"]
    by_code = {row["adcode"]: row for row in rows}
    codes = []
    for name in names:
        exact = [r for r in rows if r["name"] == name.strip()]
        matches = exact or [r for r in rows if _region_alias(r["name"]) == _region_alias(name)]
        if not matches:
            # Match qualified city names through directory ancestry, never by
            # taking a suffix from an arbitrary location or guessing a province.
            compact = re.sub(r"\s+", "", name)
            matches = [
                row
                for row in rows
                if row["level"] == "city"
                and (province := by_code.get(row["province_adcode"]))
                and compact
                in {
                    prefix + suffix
                    for prefix in (province["name"], _region_alias(province["name"]))
                    for suffix in (row["name"], _region_alias(row["name"]))
                }
            ]
        if len(matches) != 1:
            raise ValueError("unknown or ambiguous administrative name")
        codes.append(matches[0]["adcode"])
    return normalize_destination_regions(codes)


def combine_date_fragments(
    current: AssistantDateRequest,
    pending: AssistantDateRequest | None,
    today: date,
) -> AssistantDateRequest:
    """Combine model-interpreted fields only; never extract from user wording."""
    values = pending.model_dump(exclude_none=True) if pending else {}
    updates = current.model_dump(exclude_none=True)
    if "offset_days" in updates:
        updates["start_date"] = today + timedelta(days=updates.pop("offset_days"))
    if "start_date" in updates:
        values.pop("offset_days", None)
    # A new duration/end replaces the older alternative, rather than creating
    # an artificial conflict between two different turns. Explicit alternatives
    # in the same turn still go through the normal consistency check.
    if "duration_days" in updates and "end_date" not in updates:
        values.pop("end_date", None)
    if "end_date" in updates and "duration_days" not in updates:
        values.pop("duration_days", None)
    return AssistantDateRequest.model_validate(values | updates)


def next_conversation_state(
    previous: AssistantConversationState, reply: AssistantModelReply
) -> AssistantConversationState:
    if "start_date" in reply.patch.model_fields_set:
        return AssistantConversationState()
    if reply.date_request is not None:
        return AssistantConversationState(pending_date_request=reply.date_request)
    return previous


def interpret_reply(
    reply: AssistantModelReply,
    draft: AssistantDraft,
    today: date,
    conversation_state: AssistantConversationState | None = None,
) -> AssistantModelReply:
    updates = reply.patch.model_dump(exclude_unset=True)
    question = reply.question
    if "destination_region_names" in reply.model_fields_set:
        try:
            updates["destination_regions"] = resolve_region_names(
                reply.destination_region_names or []
            )
        except ValueError:
            updates.pop("destination_regions", None)
            question = "请明确目的地的省或市名称；同名地区请带上省份。"
    temporal = reply.date_request
    if temporal is not None:
        temporal = combine_date_fragments(
            temporal, conversation_state.pending_date_request if conversation_state else None, today
        )
        updates.pop("start_date", None)
        updates.pop("end_date", None)
        start = temporal.start_date
        if temporal.offset_days is not None:
            start = today + timedelta(days=temporal.offset_days)
        start = start or draft.start_date
        if start is None:
            question = "准备哪天出发？确定出发日期后，我会按你说的天数计算。"
        else:
            duration = temporal.duration_days
            if duration is None:
                duration = (
                    (draft.end_date - draft.start_date).days + 1
                    if (draft.start_date and draft.end_date and draft.end_date >= draft.start_date)
                    else 1
                )
            end = temporal.end_date or start + timedelta(days=duration - 1)
            if not today <= start <= end <= today + timedelta(days=6):
                question = (
                    f"你选的是{start}至{end}；目前可查询{today}至"
                    f"{today + timedelta(days=6)}的天气，请调整日期。"
                )
            elif (
                temporal.end_date
                and temporal.duration_days
                and (end - start).days + 1 != temporal.duration_days
            ):
                question = "出行天数和结束日期不一致，以哪一个为准？"
            else:
                updates.update(start_date=start, end_date=end)
    return reply.model_copy(
        update={
            "patch": AssistantPatch.model_validate(updates),
            "question": question,
            "date_request": temporal,
        }
    )
