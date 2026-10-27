"""Resolve evidence observations against the actual user contract, not a global vote."""

import contextlib
import json
import re
from datetime import date, datetime, timedelta, timezone

from roambot.domain.discovery import (
    BatchReview,
    EvidenceNeed,
    ReasonRevision,
    RejectedCard,
    RequirementSupport,
)
from roambot.domain.discovery_assessment import RequirementFinding
from roambot.services.discovery_criteria import (
    collection_assessments,
    is_place_condition,
    supported_criteria,
)
from roambot.services.discovery_intent import requirement_groups, unmet_requirements
from roambot.services.discovery_revision import validated_revisions


def display_fact_value(value):
    if isinstance(value, dict):
        # A stable human representation of the same typed record, not new prose.
        return " ".join(
            str(value[key]) for key in sorted(value, key=lambda key: (key != "name", key))
        )
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def literal_source_text(source):
    value = source.get("value", "")
    return "\n".join(
        (
            source.get("excerpt", ""),
            display_fact_value(value),
            json.dumps(value, ensure_ascii=False),
        )
    )


def quoted_event_dates(quote):
    """Normalize explicit numeric dates; never obtain the year from the trip."""
    result = set()

    def add(year, month, day):
        with contextlib.suppress(ValueError):
            result.add(date(int(year), int(month), int(day)))

    for match in re.finditer(
        r"(?<!\d)(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})(?!\d)", quote
    ):
        add(*match.groups())
    years = {value.year for value in result}
    if len(years) == 1:
        year = next(iter(years))
        for match in re.finditer(r"(?<!\d)(\d{1,2})\s*[月./-]\s*(\d{1,2})(?!\d)", quote):
            add(year, *match.groups())
        months = {value.month for value in result}
        if len(months) == 1:
            for match in re.finditer(r"(?<!\d)(\d{1,2})日", quote):
                add(year, next(iter(months)), match.group(1))
    return result


def event_period_supported(activity, check, sources, context):
    period = activity.period
    if period is None:
        return False
    source = sources.get(period.evidence_id)
    if (
        not source
        or source["kind"] not in {"web_page", "search_excerpt"}
        or period.evidence_id not in check.evidence_ids
        or period.quote not in literal_source_text(source)
    ):
        return False
    quoted = quoted_event_dates(period.quote)
    if period.start_date not in quoted or period.end_date not in quoted:
        return False
    # A trip may contain one visit during the event; do not demand that an event
    # lasts for every day of a multi-day trip.
    if context.get("start_date"):
        start = date.fromisoformat(str(context["start_date"]))
        end = date.fromisoformat(str(context.get("end_date") or context["start_date"]))
        return period.start_date <= end and period.end_date >= start
    today = datetime.now(timezone(timedelta(hours=8))).date()
    return period.end_date >= today


def decide_assessment(observations, context, cards):
    by_id = {card["place"]["id"]: card for card in cards}
    observed = [item.place_id for item in observations.assessments]
    if len(observed) != len(set(observed)) or set(observed) != by_id.keys():
        raise ValueError("观察必须逐项覆盖本批真实候选。")
    criteria = context.get("user_request", {}).get("criteria", context.get("requirements", []))
    per_place = {r["index"]: r for r in criteria if r.get("scope", "place") == "place"}
    required = {i for i, r in per_place.items() if r.get("importance", "required") == "required"}
    goals = {i for i in required if per_place[i].get("role") == "goal"}
    groups = requirement_groups(
        criteria, context.get("user_request", {}).get("requirement_groups", [])
    )
    alternatives = {i for group in groups if group.operator == "any" for i in group.requirements}
    indices = {r["index"] for r in criteria}
    final_copy = [
        ReasonRevision(
            place_id=item.place_id,
            reason=item.grounded_reason,
            experience=item.experience,
            evidence_ids=item.evidence_ids,
        )
        for item in observations.assessments
    ]
    all_revisions = BatchReview(approved_ids=list(by_id), rejected=[], reason_revisions=final_copy)
    revisions = validated_revisions(all_revisions, cards)
    approved, rejected, needs = [], [], []
    for item in observations.assessments:
        observed_checks = {check.requirement: check for check in item.checks}
        if (
            len(observed_checks) != len(item.checks)
            or not (required - alternatives) <= observed_checks.keys()
            or not observed_checks.keys() <= indices
        ):
            raise ValueError("必须逐项观察必要条件，不能新加、遗漏或重复条件。")
        checks = {i: check for i, check in observed_checks.items() if i in per_place}
        for i in required - checks.keys():
            checks[i] = RequirementFinding(
                requirement=i, state="unknown", note="该可选分支未有观察依据。"
            )
        sources = {source["id"]: source for source in by_id[item.place_id]["sources"]}
        for fact in item.anchored_facts:
            source = sources.get(fact.evidence_id)
            if (
                not source
                or fact.evidence_id not in item.evidence_ids
                or source.get("place_id", item.place_id) != item.place_id
                or source["kind"] not in {"map_record", "web_page", "search_excerpt"}
            ):
                raise ValueError("理由事实必须引用本地点的实际地图或网页记录。")
            if fact.quote not in literal_source_text(source):
                raise ValueError("理由事实摘录未出现在所引用的实际资料中。")
        unproven_negative = set()
        for check in item.checks:
            if (
                len(check.evidence_ids) != len(set(check.evidence_ids))
                or not set(check.evidence_ids) <= sources.keys()
                or any(
                    sources[ref].get("place_id", item.place_id) != item.place_id
                    for ref in check.evidence_ids
                )
            ):
                raise ValueError("条件观察引用了未知或其他地点的资料。")
            if (
                check.requirement not in per_place
                or per_place[check.requirement].get("importance") == "accepted"
            ):
                # Permission/tolerance is not a venue claim. It contributes no
                # approval, preference advantage or factual evidence requirement.
                continue
            has_activity_basis = any(
                sources[ref]["kind"] in {"web_page", "search_excerpt", "map_record"}
                for ref in check.evidence_ids
            )
            if check.state == "supported" and not has_activity_basis:
                raise ValueError("活动或属性不能仅凭路线或天气认定满足。")
            if check.state == "contradicted" and not has_activity_basis:
                # An unproved negative is unknown, never positive evidence and
                # never a reason to veto a different supported OR alternative.
                unproven_negative.add(check.requirement)
        incapable = set()
        temporal_missing = set()
        for i, check in checks.items():
            if (
                check.activity is not None
                and check.activity.kind == "event"
                and not event_period_supported(check.activity, check, sources, context)
            ):
                temporal_missing.add(i)
            if (
                per_place[i].get("role") == "goal"
                and check.state == "supported"
                and check.activity is not None
            ) and (
                check.activity.kind in {"venue_only", "unknown"}
                or check.activity.kind == "event"
                and not event_period_supported(check.activity, check, sources, context)
            ):
                incapable.add(i)
            if (
                per_place[i].get("role") == "goal"
                and check.state == "supported"
                and check.registration_alignment in {"inconclusive", "conflicting", "venue_only"}
                and not any(
                    sources[ref]["kind"] in {"web_page", "search_excerpt"}
                    for ref in check.evidence_ids
                )
            ):
                # A venue name cannot repair missing/conflicting registered
                # activity evidence. This is an unknown, not a claim that the
                # service does not exist; targeted public evidence may resolve it.
                incapable.add(i)
        passages = {
            ref: {
                **source,
                "place_id": item.place_id,
                "evidence_id": source.get("evidence_id", ref),
            }
            for ref, source in sources.items()
        }
        for i in required:
            if checks[i].state != "supported" or not is_place_condition(per_place[i]):
                continue
            factual_support = supported_criteria(
                [per_place[i]],
                [RequirementSupport(requirement=i, passage_ids=checks[i].evidence_ids)],
                passages,
                item.place_id,
                allow_business_inference=True,
                cited_ids=item.evidence_ids,
            )
            if factual_support is None:
                incapable.add(i)
        supported = {i for i in required if checks[i].state == "supported"} - incapable
        missing = unmet_requirements(required, groups, supported)
        concrete = item.entity_scope in {None, "place"}
        matches = (
            concrete
            and item.entity_matches
            and not missing
            and (bool(goals) or item.broad_intent_matches)
        )
        if matches and item.place_id in revisions:
            approved.append(item.place_id)
        else:
            note = (
                "现有来源不足以证明必要属性。"
                if incapable.intersection(missing)
                else checks[missing[0]].note or "必要条件尚未有充分依据。"
                if missing
                else item.note or "地点或活动与本次核心需求不符。"
            )
            rejected.append(RejectedCard(place_id=item.place_id, note=note))
            for i in missing:
                if (
                    concrete
                    and item.entity_matches
                    and (checks[i].state == "unknown" or i in incapable or i in unproven_negative)
                ):
                    needs.append(
                        EvidenceNeed(
                            place_id=item.place_id,
                            requirement=i,
                            query=per_place[i]["text"],
                            date_sensitive=i in temporal_missing,
                        )
                    )
    approved_set = set(approved)
    coverage = [c for c in observations.covered_directions if set(c.place_ids) <= approved_set]
    collection_assessments(
        criteria,
        observations.collection_assessments,
        {c["id"] for c in context.get("already_published", [])} | set(by_id),
    )
    # A model may have assumed its own approval policy. Do not preserve a whole-
    # list pass if it relied on a card rejected by the actual program rules.
    collection = [
        c
        for c in observations.collection_assessments
        if set(c.place_ids)
        <= ({c["id"] for c in context.get("already_published", [])} | approved_set)
    ]
    return BatchReview(
        approved_ids=approved,
        rejected=rejected,
        evidence_needs=needs[:6],
        reason_revisions=[r for r in final_copy if r.place_id in approved_set],
        covered_directions=coverage,
        collection_assessments=collection,
        evidence_query=observations.evidence_query,
        source_assessment=observations.model_dump(mode="json"),
    )


def verify_source_assessment(decision, context, cards):
    """Reapply the rules at the immutable batch/publication boundary."""
    from roambot.domain.discovery_assessment import NativeBatchAssessment

    if decision.source_assessment is None:
        raise ValueError("直接候选核验需要逐项观察，不能只凭批准ID发布。")
    observations = NativeBatchAssessment.model_validate(decision.source_assessment)
    expected = decide_assessment(observations, context, cards)
    if decision != expected:
        raise ValueError("发布结论与真实候选、必要条件或最终描述不一致。")
