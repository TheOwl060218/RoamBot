"""Map-provided arrival points, without contacting providers."""
from types import SimpleNamespace

import pytest

from roambot.domain.models import Coordinate
from roambot.providers.discovery import DiscoveryMap


def maps_with(payload):
    calls = []
    def get(**request):
        calls.append(request)
        return payload
    return DiscoveryMap(SimpleNamespace(_api_key='isolated',
        _http=SimpleNamespace(get_json=get), _require_success=lambda value: None)), calls


def test_search_preserves_district_and_real_entrance_without_replacing_poi():
    maps, _ = maps_with({'pois': [{'id': 'real-poi', 'name': '真实公园',
        'location': '120.6,31.3', 'cityname': '苏州市', 'adname': '吴中区',
        'navi': {'entr_location': '120.61,31.31'}, 'business': {'cost': '0'}}]})
    place = maps.search('公园', None, None, None)[0]
    assert place['coordinate'] == Coordinate(longitude=120.6, latitude=31.3).model_dump()
    assert place['facts']['district'] == '吴中区'
    assert place['facts']['entr_location'] == '120.61,31.31'


@pytest.mark.parametrize('entrance,expected', [
    ('120.61,31.31', '120.61,31.31'), ('invalid', '120.6,31.3'),
    ('NaN,31', '120.6,31.3'), ('200,100', '120.6,31.3'),
    ([], '120.6,31.3'), ('', '120.6,31.3'),
])
def test_route_targets_valid_entrance_or_original_poi(entrance, expected):
    maps, calls = maps_with({'route': {'paths': [{'distance': '2300', 'duration': '1800'}]}})
    place = {'coordinate': Coordinate(longitude=120.6, latitude=31.3).model_dump(),
             'facts': {'entr_location': entrance}}
    result = maps.route(Coordinate(longitude=120.5, latitude=31.2), place, 'walking')
    assert calls[0]['params']['destination'] == expected
    assert result['distance_km'] == 2.3
