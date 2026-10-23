import json
from types import SimpleNamespace

import pytest

from roambot.providers.discovery_answer import explain_discovery_result
from roambot.providers.protocols import ProviderError


class Http:
    def post_json(self, **kwargs):
        self.body = kwargs['json_body']
        return {'choices': [{'message': {'tool_calls': [{'function': {
            'name': 'answer_current_places', 'arguments': json.dumps({'reply': '第一处步行1.2公里。'})}}]}}]}


def test_question_uses_only_current_snapshot_facts_without_legacy_scores_or_untrusted_reason():
    http = Http()
    provider = SimpleNamespace(_http=http, _key='fixture', _model='fixture', _enable_thinking=False)
    card = {'place': {'id': 'owned-place', 'name': '水岸', 'city': '杭州', 'address': '湖边路',
        'map_type': '公园', 'coordinate': {'longitude': 120, 'latitude': 31},
        'facts': {'opentime_week': '09:00-18:00'}},
        'reason': '不应进入模型的旧推荐理由', 'experience': '未经核实的活动标签',
        'route': {'mode': 'walking', 'distance_km': 1.2, 'duration_minutes': 18}, 'weather': None}
    reply = explain_discovery_result(provider, '第一个有多远？', [], {'cards': [card], 'context': {}}, 'owned-place')
    assert reply == '第一处步行1.2公里。'
    inputs = json.loads(http.body['messages'][1]['content'])
    assert inputs['places'][0]['index'] == 1
    assert inputs['places'][0]['route'] == card['route']
    assert inputs['places'][0]['weather'] is None
    assert inputs['focused_id'] == 'owned-place'
    assert 'coordinate' not in inputs['places'][0]
    assert 'reason' not in inputs['places'][0] and 'experience' not in inputs['places'][0]
    assert http.body['parallel_tool_calls'] is False


def test_missing_model_does_not_invent_an_answer():
    with pytest.raises(ProviderError, match='尚未配置'):
        explain_discovery_result(SimpleNamespace(), '多远', [], {'cards': []})
