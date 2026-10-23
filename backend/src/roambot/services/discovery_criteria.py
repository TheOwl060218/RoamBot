"""One criterion/evidence contract for serial and coordinated execution."""


def criterion_view(requirements):
    return [{"index": i, **r.model_dump()} for i, r in enumerate(requirements, 1)]


def is_place_condition(criterion):
    return (
        criterion.get("role", "condition") == "condition"
        and criterion.get("scope", "place") == "place"
    )


def collection_assessments(criteria, assessments, available_ids):
    """Validate whole-list decisions against user criteria and actual members."""
    indices = {r["index"] for r in criteria if r.get("scope", "place") == "collection"}
    result = {}
    for assessment in assessments:
        index = assessment.requirement
        if (index not in indices or index in result
                or len(assessment.place_ids) != len(set(assessment.place_ids))
                or not set(assessment.place_ids) <= set(available_ids)):
            raise ValueError("整组判断必须引用真实的整组要求和已通过地点，不能重复或跨组借用。")
        result[index] = assessment.model_dump()
    return result


def supported_criteria(
    criteria, supports, passages, place_id, *, allow_business_inference=False, cited_ids=()
):
    by_index = {r["index"]: r for r in criteria}
    required = {i for i, r in by_index.items()
                if is_place_condition(r) and r.get("importance", "required") == "required"}
    supplied = [s.requirement for s in supports]
    if (
        len(supplied) != len(set(supplied))
        or not required <= set(supplied)
        or not set(supplied) <= by_index.keys()
    ):
        return None
    result = {"required_experiences": [], "preferred_experiences": []}
    joint = (
        {
            p["evidence_id"]: p
            for key in [*cited_ids, *(key for support in supports for key in support.passage_ids)]
            if (p := passages.get(key))
            and p["place_id"] == place_id
            and p.get("field") == "name_and_type"
            and p["kind"] == "map_record"
        }
        if allow_business_inference
        else {}
    )
    for support in supports:
        criterion = by_index[support.requirement]
        proof = [passages.get(key) for key in support.passage_ids]
        if any(not p or p["place_id"] != place_id for p in proof):
            return None
        if criterion.get("importance") == "accepted":
            continue
        # Goals still undergo whole-request suitability review. They aren't
        # factual claims requiring a source to repeat the user's intended action.
        # Even optional goal citations must be real and bound to this venue.
        if not is_place_condition(criterion):
            continue
        # Route/weather may be valid card citations, but cannot prove an activity.
        # Retain them in the card's source set; don't treat them as feature support.
        proof = [p for p in proof if p["kind"] not in {"measure_routes", "check_weather"}]
        if not proof:
            return None
        # Reuse only the same explicitly cited registration record. A different
        # place or an uncited name cannot repair a generic category reference.
        shared = [
            joint[p["evidence_id"]]
            for p in proof
            if p
            and p.get("field") in {"map_type", "address", "city"}
            and criterion.get("map_field") is None
            and p["evidence_id"] in joint
        ]
        proof += shared
        if any(
            not p
            or p["place_id"] != place_id
            or not (
                p["kind"] in {"web_page", "search_excerpt"}
                or (
                    p["kind"] == "map_record"
                    and p.get("field")
                    and (
                        (p["field"] != "name_and_type" and p["field"] == criterion.get("map_field"))
                        or (
                            p["field"] == "name_and_type"
                            and allow_business_inference
                            and criterion.get("map_field") in {None, "name_and_type"}
                        )
                        or (p.get("field") in {"map_type", "address", "city"} and shared)
                    )
                )
            )
            for p in proof
        ):
            return None
        key = (
            "preferred_experiences"
            if criterion.get("importance") == "preferred"
            else "required_experiences"
        )
        result[key].append(
            {
                "requirement": criterion["text"],
                "quotes": [p["excerpt"] for p in proof],
                "map_field": criterion.get("map_field"),
            }
        )
    return result
