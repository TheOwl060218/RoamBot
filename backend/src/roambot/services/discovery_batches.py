"""Frozen batch computation. Only the coordinator may commit the returned values."""

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

from roambot.domain.discovery import BatchReview, GroundedBatch
from roambot.domain.discovery_execution import BatchInput, BatchResult
from roambot.domain.discovery_assessment import CandidateBatch
from roambot.services.discovery import model_tool_view
from roambot.services.discovery_grounding import candidate_view, entity_supported, referenced_passages, unsuitable_ids
from roambot.services.discovery_criteria import collection_assessments, criterion_view, supported_criteria
from roambot.services.discovery_revision import validated_revisions


def freeze_batch(run, sequence, ids, revision):
    passages, candidates = candidate_view(run, ids)
    context = run.request_context() | {
        "reference_date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "requirements": criterion_view(run.plan.requirements),
    }
    stable = {
        "execution_id": run.execution_id,
        "conversation": run.turns,
        "goal": run.body.message,
        "context": context,
        "directions": [d.model_dump() for d in run.plan.directions],
        "candidates": candidates,
        "passages": passages,
        "ids": ids,
        "assessment_only": bool(getattr(run.model, "source_first", False)),
    }
    signature = hashlib.sha256(
        json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return BatchInput.freeze(
        run.scope,
        revision,
        sequence,
        {
            **stable,
            "state_signature": signature,
            "review_context": run.review_context(),
        },
    )


def prepare_review(batch, draft):
    if draft.batch != batch:
        raise ValueError("Draft belongs to another batch")
    data = batch.payload()
    if data.get("assessment_only"):
        return prepare_direct_assessment(batch, draft, data)
    proposed = GroundedBatch.model_validate(draft.payload())
    candidates = {c["place"]["id"]: c for c in data["candidates"]}
    passages = data["passages"]
    accepted, reviews, rejected, seen, invalid_ids = [], [], [], set(), set()
    for card in proposed.cards:
        refs = referenced_passages(card, passages)
        support = supported_criteria(data["context"]["requirements"], card.requirement_support,
                                     passages, card.place_id,
                                     allow_business_inference=data["context"]["allow_business_inference"],
                                     cited_ids=card.evidence_ids)
        if (
            card.place_id not in candidates
            or card.place_id in seen
            or any(not s or s["place_id"] != card.place_id for s in refs)
            or support is None
        ):
            rejected.append("invalid_evidence")
            if card.place_id in candidates:
                invalid_ids.add(card.place_id)
            continue
        candidate = candidates[card.place_id]
        if not entity_supported(candidate["place"], refs):
            rejected.append("missing_entity_reference")
            continue
        seen.add(card.place_id)
        accepted.append(
            {
                "place_id": card.place_id,
                "experience": card.experience,
                "reason": card.reason,
                "evidence_ids": list(dict.fromkeys(s["evidence_id"] for s in refs)),
            }
        )
        reviews.append(
            {
                "place": candidate["place"],
                "experience": card.experience,
                "reason": card.reason,
                "sources": [p for p in passages.values() if p["place_id"] == card.place_id],
                **support,
                "route": candidate["route"],
                "weather": candidate["weather"],
            }
        )
    return BatchInput.freeze(
        batch.identity,
        batch.revision,
        batch.sequence,
        {
            "parent": batch.fingerprint,
            "draft": draft.payload_json,
            "conversation": data["conversation"],
            "context": data["review_context"],
            "cards": reviews,
            "publish_cards": accepted,
            "rejections": rejected,
            "invalid_proposal_ids": sorted(invalid_ids),
            "not_suitable": sorted(unsuitable_ids(proposed, candidates.keys(), passages)),
            "evidence_needs": [n.model_dump() for n in proposed.evidence_needs
                               if n.place_id in candidates],
        },
    )


def prepare_direct_assessment(batch, draft, data):
    selection = CandidateBatch.model_validate(draft.payload())
    candidates = {c["place"]["id"]: c for c in data["candidates"]}
    if (len(selection.candidate_ids) != len(set(selection.candidate_ids))
            or set(selection.candidate_ids) != candidates.keys()):
        raise ValueError("直接核验只能处理该冻结批次的全部真实候选。")
    reviews, accepted = [], []
    for key in selection.candidate_ids:
        candidate = candidates[key]
        refs = [p for p in data["passages"].values() if p["place_id"] == key]
        if not entity_supported(candidate["place"], refs):
            raise ValueError("直接核验仍需同地点实体依据。")
        reviews.append({"place": candidate["place"], "sources": refs,
                        "route": candidate["route"], "weather": candidate["weather"]})
        accepted.append({"place_id": key, "requires_final_copy": True,
                         "evidence_ids": list(dict.fromkeys(p["evidence_id"] for p in refs))})
    return BatchInput.freeze(batch.identity, batch.revision, batch.sequence, {
        "parent": batch.fingerprint, "draft": draft.payload_json,
        "conversation": data["conversation"], "context": data["review_context"],
        "cards": reviews, "publish_cards": accepted, "rejections": [],
        "invalid_proposal_ids": [], "not_suitable": [], "evidence_needs": [],
        "assessment_only": True,
    })


class BatchWorker:
    def __init__(self, model, reviewer, trace=None, call=None, cache=None, check=None):
        self.model, self.reviewer, self.trace = model, reviewer, trace
        self.call = call or (lambda stage, invoke, sequence: invoke())
        self.cache = cache
        self.check = check or (lambda: None)

    def composition_key(self, batch):
        data = batch.payload()
        return [
            getattr(self.model, "version", "test"),
            "composition-v8",
            data.get("assessment_only", False),
            data["conversation"],
            data["goal"],
            data["context"],
            data["candidates"],
        ]

    def cached(self, batch, kind, key):
        saved, hit = self.cache.get(batch.identity, kind, key) if self.cache else (None, False)
        if self.trace:
            now = time.monotonic()
            self.trace.record("cache_hit" if hit else "cache_miss", now, now, batch=batch.sequence)
        return saved, hit

    def compose(self, batch):
        self.check()
        data = batch.payload()
        if data.get("assessment_only"):
            return BatchResult.freeze(batch, CandidateBatch(
                candidate_ids=[c["place"]["id"] for c in data["candidates"]]
            ).model_dump())
        if not data["candidates"]:
            return BatchResult.freeze(batch, {"cards": []})
        saved, hit = self.cached(batch, "approved-composition-v1", self.composition_key(batch))
        if hit:
            return BatchResult.freeze(batch, saved)
        value = self.call(
            "composition",
            lambda: self.model.compose(
                data["conversation"],
                data["goal"],
                data["context"],
                compact_cards(data["candidates"]),
            ),
            batch.sequence,
        )
        return BatchResult.freeze(batch, value.model_dump(mode="json"))

    def review(self, batch, draft):
        self.check()
        review = prepare_review(batch, draft)
        data = review.payload()
        if not data["cards"]:
            if data.get("assessment_only"):
                from roambot.domain.discovery_assessment import NativeBatchAssessment
                from roambot.services.discovery_assessment import decide_assessment
                value = decide_assessment(NativeBatchAssessment(assessments=[]), data["context"], [])
            else:
                value = BatchReview(approved_ids=[], rejected=[])
        else:
            key = [
                getattr(self.model, "version", "test"),
                "review-v25",
                batch.payload()["context"]["reference_date"],
                data["conversation"],
                data["context"],
                data["cards"],
            ]
            saved, hit = self.cached(batch, "approved-review-v1", key)
            if hit:
                value = BatchReview.model_validate(saved)
            else:
                value = self.call(
                    "review",
                    lambda: self.reviewer(
                        data["conversation"], data["context"], compact_cards(data["cards"])
                    ),
                    batch.sequence,
                )
            expected = {c["place"]["id"] for c in data["cards"]}
            classified = value.approved_ids + [c.place_id for c in value.rejected]
            if len(classified) != len(set(classified)) or set(classified) != expected:
                raise ValueError("Review must classify every actual candidate exactly once")
            if data.get("assessment_only"):
                from roambot.services.discovery_assessment import verify_source_assessment
                verify_source_assessment(value, data["context"], data["cards"])
            validated_revisions(value, data["cards"])
            collection_assessments(
                data["context"]["user_request"]["criteria"], value.collection_assessments,
                {c["id"] for c in data["context"]["already_published"]} | set(value.approved_ids),
            )
            directions = data["context"]["requested_directions"]
            if any(
                c.direction > len(directions) or not set(c.place_ids) <= set(value.approved_ids)
                for c in value.covered_directions
            ):
                raise ValueError("Review direction references an unknown or unapproved item")
            if self.cache and not value.rejected and value.approved_ids and not data["rejections"]:
                self.check()
                self.cache.remember(
                    batch.identity, "approved-review-v1", key, value.model_dump(mode="json")
                )
                self.cache.remember(
                    batch.identity,
                    "approved-composition-v1",
                    self.composition_key(batch),
                    draft.payload(),
                )
        return BatchResult.freeze(review, value.model_dump(mode="json"))


def compact_cards(cards):
    result = []
    for card in cards:
        place = card["place"]
        compact_place = {
            k: v
            for k, v in place.items()
            if k in {"id", "name", "city", "address", "map_type", "parent_id", "verified_at"}
        }
        compact_place["facts"] = {
            k: v
            for k, v in place.get("facts", {}).items()
            if k in {"opentime_today", "opentime_week", "cost", "rating"}
        }
        sources = list({s["id"]: s for s in card["sources"]}.values())
        result.append({**card, "place": compact_place, "sources": sources})
    return model_tool_view(result)
