import pytest


def test_normalizes_province_coverage_without_mutating_input():
    from roambot.domain.regions import normalize_destination_regions

    values = ['320500', '320000', '330100', '320500']
    assert normalize_destination_regions(values) == ['320000', '330100']
    assert values == ['320500', '320000', '330100', '320500']


def test_rejects_unknown_region_and_county_selection():
    from roambot.domain.regions import normalize_destination_regions

    for values in [['000000'], ['320505'], ['杭州市']]:
        with pytest.raises(ValueError):
            normalize_destination_regions(values)


def test_catalog_has_municipality_and_direct_admin_city():
    from roambot.domain.regions import region_catalog

    rows = {row['adcode']: row for row in region_catalog()['regions']}
    assert rows['110000']['name'] == '北京市'
    assert rows['429004']['name'] == '仙桃市'
    assert rows['429004']['province_adcode'] == '420000'
    assert '110100' not in rows
    assert all(row['name'] not in {'市辖区', '县'} for row in rows.values())


def test_region_ancestry_uses_explicit_directory_and_does_not_guess_unknown():
    from roambot.domain.regions import resolve_region_codes

    assert resolve_region_codes('320505', None) == ('320000', '320500')
    assert resolve_region_codes('110101', None) == ('110000', '110000')
    assert resolve_region_codes('429004', None) == ('420000', '429004')
    assert resolve_region_codes('329999', None) == (None, None)


def test_catalog_callers_cannot_corrupt_future_responses():
    from roambot.domain.regions import region_catalog

    first = region_catalog()
    first['regions'][0]['name'] = 'wrong'
    assert region_catalog()['regions'][0]['name'] == '北京市'


def test_rejects_oversized_raw_selection():
    from roambot.domain.regions import normalize_destination_regions, region_catalog

    with pytest.raises(ValueError):
        normalize_destination_regions(['320000'] * (len(region_catalog()['regions']) + 1))
def test_region_directory_is_explicitly_in_wheel_manifest():
    import tomllib
    from pathlib import Path

    config = tomllib.loads((Path(__file__).resolve().parents[2] / 'pyproject.toml')
                          .read_text('utf-8'))
    mapping = config['tool']['hatch']['build']['targets']['wheel'].get('force-include', {})
    assert mapping.get('src/roambot/domain/data/regions.json') == 'roambot/domain/data/regions.json'
