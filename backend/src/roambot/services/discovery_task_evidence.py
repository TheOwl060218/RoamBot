"""Project selected source facts without asking a model to rewrite their meaning.

This is an evidence boundary shared by either presentation option. It neither
decides suitability nor claims that a provider record is an on-site guarantee.
"""

import copy

from roambot.services.discovery_assessment import display_fact_value


FIELD_LABELS = {
    "name_and_type": "名称与登记类型",
    "map_type": "登记类型",
    "city": "城市",
    "address": "地址",
    "opentime_today": "当日登记时段",
    "opentime_week": "登记营业信息",
    "cost": "参考消费",
}


def project_fact(card, evidence_id):
    """Return a venue-bound fact; labels and values cannot be model-generated."""
    place_id = card["place"]["id"]
    matching = [source for source in card["sources"] if source["id"] == evidence_id]
    if len(matching) != 1:
        raise ValueError("依据须对应本地点唯一的实际来源。")
    source = matching[0]
    if (source.get("place_id", place_id) != place_id
            or source["kind"] not in {"map_record", "web_page", "search_excerpt"}):
        raise ValueError("不能借用其他地点或测量记录生成地点属性。")
    # Select a whole typed value or a pre-bound passage, never an arbitrary
    # model-picked substring that might drop an exception or entry condition.
    text = (display_fact_value(source["value"]) if "value" in source
            else source.get("excerpt", ""))
    if not text:
        raise ValueError("空来源不能形成展示依据。")
    return {
        "place_id": place_id,
        "evidence_id": evidence_id,
        "source_id": source.get("evidence_id", evidence_id),
        "kind": source["kind"],
        "field": source.get("field"),
        "label": FIELD_LABELS.get(source.get("field"), "来源原文"),
        "text": text,
        "value": copy.deepcopy(source.get("value")),
        "url": source.get("url", ""),
    }


def selection_facts(cards, selections):
    """Resolve actual references, preserving the selection's venue identity."""
    by_id = {card["place"]["id"]: card for card in cards}
    result = {}
    for item in selections:
        if item.place_id not in by_id or item.place_id in result:
            raise ValueError("选择须对应唯一的真实候选。")
        if len(set(item.evidence_ids)) != len(item.evidence_ids):
            raise ValueError("选择依据不能重复。")
        result[item.place_id] = [project_fact(by_id[item.place_id], ref) for ref in item.evidence_ids]
    return result


def task_model_facts(cards):
    """One factual representation for model input and archived evidence.

    Do not also expose raw place.facts or rewritten source excerpts: those are
    parallel representations whose labels/scope can diverge from publication.
    Handles are batch-local; only resolved original references leave this call.
    """
    candidates, references = [], {}
    for card in cards:
        facts = []
        for source in card["sources"]:
            fact = project_fact(card, source["id"])
            handle = f"s{len(references) + 1}"
            references[handle] = fact["evidence_id"]
            facts.append({"id": handle, "kind": fact["kind"],
                          "field": fact["field"], "label": fact["label"],
                          "text": fact["text"]})
        candidates.append({"place": {"id": card["place"]["id"], "name": card["place"]["name"]},
                           "sources": facts, "route": copy.deepcopy(card.get("route")),
                           "weather": copy.deepcopy(card.get("weather"))})
    return candidates, references
