import pytest

from roambot.domain.regions import region_catalog
from roambot.services.assistant_interpretation import resolve_region_names


@pytest.mark.parametrize("name", ["江苏省苏州市", "江苏苏州", "江苏省 苏州市", "江苏苏州市"])
def test_qualified_city_resolves_through_actual_province_relationship(name):
    assert resolve_region_names([name]) == ["320500"]


def test_every_catalog_city_accepts_its_qualified_official_name():
    rows = region_catalog()["regions"]
    provinces = {row["adcode"]: row["name"] for row in rows if row["level"] == "province"}
    for row in rows:
        if row["level"] == "city":
            assert resolve_region_names([provinces[row["province_adcode"]] + row["name"]]) == [
                row["adcode"]
            ]


@pytest.mark.parametrize(
    "name", ["浙江省苏州市", "江苏省宁波市", "江苏省苏州市未知区", "未知省苏州市", "吉林"]
)
def test_incorrect_ancestry_and_ambiguous_names_cannot_silently_choose_city(name):
    with pytest.raises(ValueError):
        resolve_region_names([name])
