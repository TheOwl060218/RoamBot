"""Short, venue-bound passages with immutable citation handles."""

import json
import re
from datetime import datetime, timedelta, timezone

from roambot.domain.discovery_text import venue_paragraphs
from roambot.persistence.discovery_knowledge import tokens

MAP_FIELDS = (
    "name_and_type",
    "city",
    "address",
    "map_type",
    "opentime_today",
    "opentime_week",
    "cost",
)


def metadata_only(requirements):
    required = [r for r in requirements if r.role == "condition" and r.scope == "place"
                and r.importance == "required"]
    return bool(required) and all(r.map_field and r.map_field != "name_and_type" for r in required)


def can_evaluate_map(run):
    return metadata_only(run.plan.requirements) or (
        bool(run.reviewer) and (bool(run.plan.requirements)
                               or bool(getattr(run.model, "source_first", False)))
    )


def map_fact_passages(place, source):
    result = []
    today = datetime.now(timezone(timedelta(hours=8))).date()
    for field in MAP_FIELDS:
        value = (
            {"name": place["name"], "map_type": place.get("map_type", "")}
            if field == "name_and_type"
            else (
                place.get(field)
                if field in {"city", "address", "map_type"}
                else place.get("facts", {}).get(field)
            )
        )
        if value is None or value == "":
            continue
        if field == "name_and_type" and not value["map_type"]:
            continue
        if field == "opentime_today":
            verified = place.get("verified_at")
            if (
                not verified
                or datetime.fromtimestamp(verified, timezone(timedelta(hours=8))).date() != today
            ):
                continue
        result.append(
            {
                "id": source["id"] + ".f." + field,
                "evidence_id": source["id"],
                "place_id": place["id"],
                "kind": "map_record",
                "field": field,
                "value": value,
                "title": place["name"],
                "url": source.get("url", ""),
                "excerpt": field + "=" + json.dumps(value, ensure_ascii=False),
            }
        )
    return result


def candidate_view(run, ids):
    passages, candidates = {}, []
    for key in ids:
        sources = []
        for evidence in run.evidence.values():
            if evidence["place_id"] != key:
                continue
            if evidence["kind"] in {"web_page", "search_excerpt"}:
                fragments = passage_view(run.places[key], evidence, run.plan.requirements)
            elif evidence["kind"] == "map_record":
                fragments = map_fact_passages(run.places[key], evidence)
            else:
                fragments = [{**evidence, "evidence_id": evidence["id"]}]
            for passage in fragments:
                passages[passage["id"]] = passage
                sources.append(
                    {k: v for k, v in passage.items() if k not in {"evidence_id", "place_id"}}
                )
        if any(s["kind"] in {"web_page", "search_excerpt"} for s in sources) or (
            can_evaluate_map(run) and any(s.get("field") for s in sources)
        ):
            candidates.append(
                {
                    "place": run.places[key],
                    "sources": sources,
                    "route": run.routes.get(key),
                    "weather": run.forecasts.get(key),
                }
            )
    return passages, candidates


def referenced_passages(card, passages):
    ids = list(card.evidence_ids)
    ids += [key for support in card.requirement_support for key in support.passage_ids]
    return [passages.get(key) for key in dict.fromkeys(ids)]


def entity_supported(place, refs):
    from roambot.providers.discovery import source_mentions_place

    return any(
        s
        and (
            (s["kind"] in {"web_page", "search_excerpt"} and source_mentions_place(place, s))
            or (s["kind"] == "map_record" and s.get("field") in MAP_FIELDS)
        )
        for s in refs
    )


def unsuitable_ids(proposed, eligible_ids, passages):
    conflicts = {c.place_id for c in proposed.cards} | {n.place_id for n in proposed.evidence_needs}
    result = set()
    for item in proposed.not_suitable:
        refs = [passages.get(key) for key in item.evidence_ids]
        if (
            item.place_id in eligible_ids
            and item.place_id not in conflicts
            and all(p and p["place_id"] == item.place_id for p in refs)
            and any(p["kind"] in {"map_record", "web_page", "search_excerpt"} for p in refs)
        ):
            result.add(item.place_id)
    return result


def cited_sources(sources, refs):
    result = []
    for source in sources:
        selected = [p for p in refs if p.get("evidence_id") == source["id"] and p.get("excerpt")]
        if selected:
            source = {**source, "excerpt": "\n\n".join(p["excerpt"] for p in selected)}
        result.append(source)
    return result


def passage_view(place, source, requirements):
    name = re.split(r"[（(]", place["name"], maxsplit=1)[0]
    paragraphs = venue_paragraphs(place, source)
    pieces = []
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[。！？!?])", paragraph)
        chunk = ""
        for sentence in sentences:
            if len(chunk + sentence) > 360 and chunk:
                pieces.append(chunk)
                chunk = ""
            if len(sentence) > 360:
                pieces.extend(sentence[i : i + 360] for i in range(0, len(sentence), 360))
            else:
                chunk += sentence
        if chunk:
            pieces.append(chunk)
    focus = set(tokens(" ".join(r.text for r in requirements)))
    ranked = sorted(
        enumerate(pieces),
        key=lambda pair: (-len(focus.intersection(tokens(pair[1]))), -(name in pair[1]), pair[0]),
    )
    chosen = sorted(ranked[:3], key=lambda pair: pair[0])
    return [
        {
            "id": source["id"] + f".p{i + 1}",
            "kind": source["kind"],
            "title": source.get("title", ""),
            "url": source.get("url", ""),
            "excerpt": piece,
            "evidence_id": source["id"],
            "place_id": place["id"],
        }
        for i, piece in chosen
    ]
