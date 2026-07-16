from roambot.domain.models import SceneryType
from roambot.domain.scenery import classify_scenery


def test_type_and_name_can_produce_multiple_tags() -> None:
    tags = classify_scenery(
        name="金鸡湖景区",
        type_name="风景名胜;公园广场;公园",
        type_code="110101",
        overrides={},
    )

    assert tags == frozenset({SceneryType.LAKE, SceneryType.PARK})


def test_override_replaces_ambiguous_rules() -> None:
    tags = classify_scenery(
        name="测试地点",
        type_name="风景名胜",
        type_code="110000",
        overrides={"测试地点": frozenset({SceneryType.MUSEUM})},
    )

    assert tags == frozenset({SceneryType.MUSEUM})


def test_unknown_place_is_not_guessed() -> None:
    assert classify_scenery("甲乙丙", "地名地址信息", "190000", {}) == frozenset()
