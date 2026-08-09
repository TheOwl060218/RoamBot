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


def test_inland_sand_beach_is_not_classified_as_sea_scenery() -> None:
    tags = classify_scenery(
        name="阳澄湖人工沙滩",
        type_name="风景名胜;沙滩",
        type_code="110000",
        overrides={},
    )

    assert SceneryType.SEA not in tags


def test_explicit_marine_place_is_classified_as_sea_scenery() -> None:
    tags = classify_scenery(
        name="连云港海滨浴场",
        type_name="风景名胜;海水浴场",
        type_code="110000",
        overrides={},
    )

    assert SceneryType.SEA in tags


def test_business_names_containing_binhai_are_not_classified_as_sea() -> None:
    bathhouse = classify_scenery(
        name="滨海浴室",
        type_name="生活服务;洗浴推拿场所",
        type_code="071400",
        overrides={},
    )
    restaurant = classify_scenery(
        name="滨海肉圆",
        type_name="餐饮服务;中餐厅",
        type_code="050100",
        overrides={},
    )

    assert SceneryType.SEA not in bathhouse
    assert SceneryType.SEA not in restaurant
