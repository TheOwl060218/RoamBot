"""Attribution and field meaning, not a substitute for recommendation quality."""
import copy

import pytest

from roambot.services.discovery_task_evidence import project_fact, task_model_facts


def card():
    return {"place": {"id": "actual"}, "sources": [
        {"id": "hours", "place_id": "actual", "kind": "map_record",
         "field": "opentime_week", "value": "周一至周日 00:00-24:00"},
        {"id": "spend", "place_id": "actual", "kind": "map_record", "field": "cost", "value": "81.00"},
        {"id": "page", "place_id": "actual", "kind": "web_page", "excerpt": "开放街道可免费进入，室内展馆另计。"},
        {"id": "route", "place_id": "actual", "kind": "measure_routes", "facts": {"distance_km": 2}},
    ]}


def test_projection_preserves_field_meaning_instead_of_turning_hours_or_spend_into_admission():
    value = card()
    before = copy.deepcopy(value)
    assert project_fact(value, "hours")["label"] == "登记营业信息"
    assert project_fact(value, "hours")["text"] == "周一至周日 00:00-24:00"
    assert project_fact(value, "spend")["label"] == "参考消费"
    with pytest.raises(TypeError):
        project_fact(value, "hours", quote="无门票限制")
    assert value == before


def test_actual_public_statement_is_retained_without_dropping_its_scope():
    fact = project_fact(card(), "page")
    assert fact["text"] == "开放街道可免费进入，室内展馆另计。"
    assert fact["label"] == "来源原文"


def test_model_and_publication_use_same_complete_facts_without_parallel_raw_metadata():
    value = card()
    value["place"].update(name="真实地点", facts={"unselected": "不应进入理由输入"})
    value["sources"] = value["sources"][:3]
    value["route"] = {"distance_km": 2}
    before = copy.deepcopy(value)
    candidates, references = task_model_facts([value])
    assert candidates[0]["place"] == {"id": "actual", "name": "真实地点"}
    assert candidates[0]["route"] == {"distance_km": 2}
    for source in candidates[0]["sources"]:
        published = project_fact(value, references[source["id"]])
        assert (source["label"], source["text"]) == (published["label"], published["text"])
    assert candidates[0]["sources"][2]["text"] == "开放街道可免费进入，室内展馆另计。"
    assert value == before


@pytest.mark.parametrize("bad", ["foreign", "measurement", "unknown"])
def test_foreign_measurement_or_nonexistent_fact_cannot_support_venue_attributes(bad):
    value = card()
    ref = "hours"
    if bad == "foreign":
        value["sources"][0]["place_id"] = "someone-else"
    elif bad == "measurement":
        ref = "route"
    else:
        ref = "missing"
    with pytest.raises(ValueError):
        project_fact(value, ref)
