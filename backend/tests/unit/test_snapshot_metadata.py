from roambot.services.snapshot_metadata import display_city


def test_destination_cities_are_unique_and_do_not_modify_request():
    request = {"city": ""}
    items = [{"destination": {"city": city}} for city in ["上海", "上海", "杭州", ""]]
    assert display_city(request, items) == "上海、杭州"
    assert request == {"city": ""}


def test_explicit_legacy_city_is_preserved_and_empty_results_stay_empty():
    assert display_city({"city": "苏州"}, [{"destination": {"city": "上海"}}]) == "苏州"
    assert display_city({"city": ""}, []) == ""
