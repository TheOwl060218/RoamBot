"""A reviewer may edit wording, never the venue, facts, permissions or constraints."""


def validated_revisions(decision, cards):
    by_id = {card["place"]["id"]: card for card in cards}
    result = {}
    for revision in decision.reason_revisions:
        key = revision.place_id
        if key not in by_id or key not in decision.approved_ids or key in result:
            raise ValueError("修订必须属于本批已通过的真实地点，不能重复或替被拒地点放行。")
        sources = {source["id"]: source for source in by_id[key]["sources"]}
        if (
            len(revision.evidence_ids) != len(set(revision.evidence_ids))
            or not set(revision.evidence_ids) <= sources.keys()
            or any(sources[ref].get("place_id", key) != key for ref in revision.evidence_ids)
            or not any(
                sources[ref]["kind"] in {"map_record", "web_page", "search_excerpt"}
                for ref in revision.evidence_ids
            )
        ):
            raise ValueError("修订只能引用该地点本次已审查的资料，不能补造证据或用路线证明活动。")
        result[key] = revision
    return result


def revised_fields(card, revisions):
    revision = revisions.get(card["place"]["id"])
    return (
        {
            "reason": revision.reason,
            **({"experience": revision.experience} if revision.experience else {}),
        }
        if revision
        else {}
    )
