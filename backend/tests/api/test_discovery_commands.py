import time
import pytest
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from test_history import register

from roambot.api.routes.commands import get_business_planner
from roambot.api.routes.discovery import get_discovery_factory
from roambot.domain.discovery import Finish, RetrievalPlan, SearchContext
from roambot.services.discovery import DiscoveryRun


def source_job(client, csrf, *, message="取得测试结果", conversation=None, search_request=None):
    def factory(body, previous):
        run = DiscoveryRun(
            body,
            None,
            None,
            None,
            lambda _: ("finish", Finish(reply="已取得受控测试地点。")),
            source="demo",
        )
        run.cards = [
            {
                "place": {
                    "id": f"amap:verified{i}",
                    "name": name,
                    "address": "服务端核实地址",
                    "city": "苏州",
                    "coordinate": {"longitude": 120.6, "latitude": 31.3, "system": "gcj02"},
                    "map_type": "开放休闲场所",
                    "map_url": f"https://www.amap.com/detail/verified{i}",
                    "facts": {},
                },
                "experience": "休闲",
                "reason": "此处是服务端受控测试结果，未使用真实Provider。",
                "sources": [],
                "route": None,
                "weather": None,
            }
            for i, name in enumerate(("真实测试书店", "真实测试湖边"), 1)
        ]
        if conversation is not None:
            run.turns = conversation
        run.search_request = search_request
        return run

    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    response = client.post(
        "/api/v1/discovery/jobs", headers={"X-CSRF-Token": csrf}, json={"message": message}
    )
    assert response.status_code == 200
    key = response.json()["id"]
    for _ in range(50):
        if client.get("/api/v1/discovery/jobs/" + key).json()["status"] != "running":
            break
        time.sleep(0.01)
    return key


def proposal(client, csrf, key):
    client.app.dependency_overrides[get_business_planner] = lambda: (
        lambda request, context: {
            "actions": [{"tool": "favorite_place", "arguments": {"place": 2}}],
            "question": None,
        }
    )
    return client.post(
        "/api/v1/assistant/commands/proposals",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": str(uuid4()),
            "message": "收藏第二个",
            "context": {
                "page": "/explore",
                "discovery_job_id": key,
                "visible_places": [{"id": "fake", "name": "伪造客户端地点"}],
            },
        },
    )


def execute(client, csrf, body):
    return client.post(
        "/api/v1/assistant/commands/execute",
        headers={"X-CSRF-Token": csrf},
        json={"request_id": body["request_id"], "proposal": body["proposal"], "confirmed": False},
    )


def intake_job(client, csrf, source, *, message="收藏第二个", actions=None, view=None):
    def factory(body, previous):
        run = DiscoveryRun(body, None, None, None,
            lambda _: ("finish", Finish(reply="移交操作执行器。")))
        run.plan = RetrievalPlan(intent="business", context=SearchContext(), goal=body.message,
            business_plan={"actions": actions or [{"tool": "favorite_place", "arguments": {"place": 2}}]})
        return run
    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    started = client.post('/api/v1/discovery/jobs', headers={'X-CSRF-Token': csrf},
        json={"message": message, "previous_id": source, "view": view or {}})
    assert started.status_code == 200
    key = started.json()['id']
    for _ in range(100):
        if client.get('/api/v1/discovery/jobs/' + key).json()['status'] == 'completed': break
        time.sleep(.001)
    return key


def test_reuses_owned_understanding_without_second_model_and_retains_real_auth_and_replay(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_one_model")
    source = source_job(client, csrf)
    intake = intake_job(client, csrf, source)
    def forbidden(*args): raise AssertionError('A second model must not run')
    client.app.dependency_overrides[get_business_planner] = lambda: forbidden
    planned = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf},
        json={"request_id": str(uuid4()), "message": "收藏第二个", "intake_id": intake,
            "context": {"page": "/explore", "discovery_job_id": source, "layer": "results"}})
    assert planned.status_code == 200, planned.json()
    result = execute(client, csrf, planned.json())
    assert result.json()['status'] == 'completed'
    assert client.delete('/api/v1/discovery/jobs/' + intake, headers={'X-CSRF-Token': csrf}).status_code == 200
    assert execute(client, csrf, planned.json()).json() == result.json()
    favorites = client.get('/api/v1/favorites').json()['favorites']
    assert [f['place']['name'] for f in favorites] == ['真实测试湖边']


def test_task_native_intake_reaches_existing_executor_without_second_planner(auth_api_fixture, tmp_path):
    import json
    from roambot.persistence.discovery_cache import DiscoveryCache
    from roambot.services.discovery_tasks import DiscoveryTaskModel, DiscoveryTaskWorkflow

    client, _, _ = auth_api_fixture()
    csrf = register(client, "task_native_handoff")
    source = source_job(client, csrf)
    calls = []

    def native_call(**kwargs):
        calls.append(kwargs["json_body"])
        result = {"intent": "business", "context": {}, "temporal": None, "directions": [],
                  "business_plan": {"actions": [{"tool": "favorite_place", "arguments": {"place": 2}}]}}
        return {"choices": [{"finish_reason": "stop", "message": {"tool_calls": [{"function": {
            "name": "plan_task", "arguments": json.dumps(result)}}]}}]}

    provider = SimpleNamespace(_model="offline-native-fixture", _key="not-a-credential",
        _enable_thinking=False, _http=SimpleNamespace(post_json=native_call))
    cache = DiscoveryCache(tmp_path / "task-native.sqlite3")
    client.app.dependency_overrides[get_discovery_factory] = lambda: (
        lambda body, previous: DiscoveryTaskWorkflow(body, None, None, None,
            DiscoveryTaskModel(provider), cache, "", previous))
    def forbidden(*args):
        raise AssertionError("Simple task must reuse the intake plan")
    client.app.dependency_overrides[get_business_planner] = lambda: forbidden
    started = client.post('/api/v1/discovery/jobs', headers={'X-CSRF-Token': csrf},
        json={"message": "收藏第二个", "previous_id": source})
    assert started.status_code == 200
    intake = started.json()['id']
    for _ in range(100):
        snapshot = client.get('/api/v1/discovery/jobs/' + intake).json()
        if snapshot['status'] != 'running': break
        time.sleep(.001)
    assert snapshot['status'] == 'completed', snapshot
    planned = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf},
        json={"request_id": str(uuid4()), "message": "收藏第二个", "intake_id": intake,
              "context": {"page": "/explore", "discovery_job_id": source}})
    assert planned.status_code == 200, planned.json()
    assert execute(client, csrf, planned.json()).json()['status'] == 'completed'
    assert len(calls) == 1
    data = json.loads(calls[0]['messages'][1]['content'])
    assert [p['id'] for p in data['previous_places']] == ['amap:verified1', 'amap:verified2']
    assert [f['place']['name'] for f in client.get('/api/v1/favorites').json()['favorites']] == ['真实测试湖边']


@pytest.mark.parametrize('change', ['message', 'source', 'focused', 'selection', 'layer'])
def test_reused_understanding_is_bound_to_original_message_source_and_view(auth_api_fixture, change):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_bound_" + change)
    source = source_job(client, csrf)
    intake = intake_job(client, csrf, source)
    body = {"request_id": str(uuid4()), "message": "收藏第二个", "intake_id": intake,
        "context": {"page": "/explore", "discovery_job_id": source, "layer": "results"}}
    if change == 'message': body['message'] = '收藏第一个'
    elif change == 'source': body['context']['discovery_job_id'] = 'different-source'
    elif change == 'focused': body['context']['focused_id'] = 'amap:verified1'
    elif change == 'selection': body['context']['selected_ids'] = ['amap:verified1']
    else: body['context']['layer'] = 'map'
    response = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf}, json=body)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'intake_context_changed'
    assert client.get('/api/v1/favorites').json()['favorites'] == []


def test_other_account_cannot_reuse_intake_even_for_a_ui_action(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_intake_owner")
    source = source_job(client, csrf)
    intake = intake_job(client, csrf, source, actions=[{"tool": "close_layer", "arguments": {}}])
    with TestClient(client.app) as other:
        other_csrf = register(other, "discovery_intake_other")
        response = other.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': other_csrf},
            json={"request_id": str(uuid4()), "message": "收藏第二个", "intake_id": intake,
                "context": {"page": "/explore", "discovery_job_id": source}})
        assert response.status_code == 404


def test_complex_intake_keeps_full_business_planner_fallback(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_complex")
    source = source_job(client, csrf)
    intake = intake_job(client, csrf, source)
    client.app.state.discovery_jobs.jobs[intake][2].plan.business_plan = None
    called = []
    def planner(body, context):
        called.append(body.message)
        return {"actions": [{"tool": "list_favorites", "arguments": {}}]}
    client.app.dependency_overrides[get_business_planner] = lambda: planner
    response = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf},
        json={"request_id": str(uuid4()), "message": "收藏第二个", "intake_id": intake,
            "context": {"page": "/explore", "discovery_job_id": source}})
    assert response.status_code == 200
    assert called == ['收藏第二个']


def test_compare_task_binds_and_opens_both_places_atomically(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, 'discovery_atomic_compare')
    source = source_job(client, csrf)
    intake = intake_job(client, csrf, source, message='前两个放在一起看看差别',
        actions=[{'tool': 'compare_places', 'arguments': {'places': [1, 2]}}])
    result = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf},
        json={'request_id': str(uuid4()), 'message': '前两个放在一起看看差别', 'intake_id': intake,
            'context': {'page': '/explore', 'discovery_job_id': source}})
    assert result.status_code == 200
    completed = execute(client, csrf, result.json()).json()
    assert completed['status'] == 'completed'
    assert completed['steps'][0]['result']['effect'] == {'tool': 'show_comparison',
        'arguments': {'ids': ['amap:verified1', 'amap:verified2']}}


def test_favorite_binds_actual_discovery_place_without_fake_score_or_legacy_history(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_favorite_owner")
    key = source_job(client, csrf)
    planned = proposal(client, csrf, key)
    assert planned.status_code == 200
    result = execute(client, csrf, planned.json())
    assert result.json()["status"] == "completed", result.json()
    favorites = client.get("/api/v1/favorites").json()["favorites"]
    assert len(favorites) == 1
    assert favorites[0]["place"]["name"] == "真实测试湖边"
    assert favorites[0]["place"]["provider_place_id"] == "verified2"
    assert favorites[0]["place"]["scenery_tags"] == []
    histories = client.get("/api/v1/history").json()["histories"]
    assert len(histories) == 1 and histories[0]["mode"] == "discovery"
    assert histories[0]["start_date"] is None and histories[0]["end_date"] is None
    archived = client.get('/api/v1/history/' + histories[0]['id']).json()['history']
    assert 'score' not in str(archived['result'])
    assert 'scenery_tags' not in str(archived['result'])
    assert execute(client, csrf, planned.json()).json() == result.json()
    assert len(client.get("/api/v1/favorites").json()["favorites"]) == 1


def test_mixed_requery_and_write_cannot_favorite_the_old_discovery_result(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_mixed_owner")
    key = source_job(client, csrf)
    client.app.dependency_overrides[get_business_planner] = lambda: (
        lambda request, context: {
            "actions": [
                {"tool": "favorite_place", "arguments": {"place": 1}},
                {"tool": "run_recommendation", "arguments": {}},
            ],
            "question": None,
        }
    )
    response = client.post("/api/v1/assistant/commands/proposals",
        headers={"X-CSRF-Token": csrf}, json={"request_id": str(uuid4()),
            "message": "重新查杭州然后收藏第一个", "context": {
                "page": "/explore", "discovery_job_id": key}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "discovery_task_not_connected"
    assert client.get("/api/v1/favorites").json()["favorites"] == []


def test_releasing_handoffs_does_not_exhaust_job_capacity_or_remove_source(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_handoff_owner")
    source = source_job(client, csrf)
    def factory(body, previous):
        run = DiscoveryRun(body, None, None, None,
            lambda _: ("finish", Finish(reply="移交操作执行器。")))
        run.plan = SimpleNamespace(intent="business")
        return run
    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    for _ in range(66):
        started = client.post('/api/v1/discovery/jobs', headers={'X-CSRF-Token': csrf},
            json={'message': '关闭地图', 'previous_id': source})
        assert started.status_code == 200
        key = started.json()['id']
        for _ in range(100):
            if client.get('/api/v1/discovery/jobs/' + key).json()['status'] == 'completed':
                break
            time.sleep(.001)
        assert client.delete('/api/v1/discovery/jobs/' + key,
            headers={'X-CSRF-Token': csrf}).status_code == 200
        assert client.get('/api/v1/discovery/jobs/' + key).status_code == 404
    assert len(client.get('/api/v1/discovery/jobs/' + source).json()['cards']) == 2


def test_other_account_cannot_use_discovery_job_even_with_spoofed_visible_places(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_private_owner")
    key = source_job(client, csrf)
    with TestClient(client.app) as other:
        other_csrf = register(other, "discovery_other_user")
        planned = proposal(other, other_csrf, key)
        assert planned.status_code == 404
        assert other.get("/api/v1/favorites").json()["favorites"] == []


def test_current_discovery_question_returns_reply_without_legacy_redirect_and_replays_once(auth_api_fixture, monkeypatch):
    client, _, _ = auth_api_fixture()
    csrf = register(client, 'discovery_answer_owner')
    source = source_job(client, csrf)
    calls = []
    def answer(provider, message, conversation, snapshot, focused):
        calls.append(snapshot)
        assert [c['place']['id'] for c in snapshot['cards']] == ['amap:verified1', 'amap:verified2']
        assert focused == 'amap:verified2'
        return '第二处是当前结果中的真实测试湖边。'
    monkeypatch.setattr('roambot.services.business_executor.explain_discovery_result', answer)
    client.app.state.provider_runtime = SimpleNamespace(new_request_bundle=lambda: SimpleNamespace(assistant=object()), close=lambda: None)
    intake = intake_job(client, csrf, source, message='第二个是什么地方', actions=[{'tool': 'explain_result', 'arguments': {}}],
        view={'focused_id':'amap:verified2','selected_ids':[],'layer':'detail'})
    def forbidden(*args): raise AssertionError('Owned intake must not repeat planning')
    client.app.dependency_overrides[get_business_planner] = lambda:forbidden
    proposed = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token':csrf}, json={
        'request_id':str(uuid4()),'message':'第二个是什么地方','intake_id':intake,
        'context':{'page':'/explore','discovery_job_id':source,'focused_id':'amap:verified2','layer':'detail',
                   'visible_places':[{'id':'fake','name':'伪造客户端地点'}]}})
    assert proposed.status_code == 200, proposed.text
    result = execute(client, csrf, proposed.json())
    assert result.status_code == 200 and result.json()['status'] == 'completed'
    assert result.json()['steps'][0]['result'] == {'reply':'第二处是当前结果中的真实测试湖边。'}
    assert execute(client, csrf, proposed.json()).json() == result.json()
    assert len(calls) == 1


def test_discovery_answer_failure_is_read_only_and_other_account_cannot_get_facts(auth_api_fixture, monkeypatch):
    from roambot.providers.protocols import ProviderError
    client, _, _ = auth_api_fixture()
    csrf = register(client, 'discovery_answer_private')
    source = source_job(client, csrf)
    calls=[]
    def answer(*args):
        calls.append(True)
        raise ProviderError('timeout','结果问答暂未完成')
    monkeypatch.setattr('roambot.services.business_executor.explain_discovery_result', answer)
    client.app.state.provider_runtime=SimpleNamespace(new_request_bundle=lambda:SimpleNamespace(assistant=object()),close=lambda:None)
    client.app.dependency_overrides[get_business_planner]=lambda:(lambda *args:{'actions':[{'tool':'explain_result','arguments':{}}]})
    def ask(browser, token, *, rejected=False):
        p=browser.post('/api/v1/assistant/commands/proposals',headers={'X-CSRF-Token':token},json={
            'request_id':str(uuid4()),'message':'第二个多远','context':{'page':'/explore','discovery_job_id':source}})
        if rejected:
            assert p.status_code == 404 and p.json()['error']['code']=='discovery_not_found'
            return
        assert p.status_code == 200
        return execute(browser,token,p.json()).json()
    result=ask(client,csrf)
    assert result['status']=='failed' and result['error']['code']=='timeout'
    with TestClient(client.app) as other:
        other_csrf=register(other,'discovery_answer_other')
        ask(other,other_csrf,rejected=True)
    assert len(calls)==1


def test_new_plan_question_uses_plan_snapshot_instead_of_background_discovery(auth_api_fixture, monkeypatch):
    from datetime import datetime, timedelta, timezone
    client, _, _ = auth_api_fixture()
    csrf=register(client,'discovery_plan_answer')
    source=source_job(client,csrf)
    original=client.get('/api/v1/discovery/jobs/'+source).json()
    day=(datetime.now(timezone(timedelta(hours=8))).date()+timedelta(days=1)).isoformat()
    created=client.post('/api/v1/plans',headers={'X-CSRF-Token':csrf},json={
        'history_id':original['history_id'],'candidate_ids':[c['place']['id'] for c in original['cards']],
        'name':'新的出游计划','start_date':day,'end_date':day})
    assert created.status_code==201
    plan=created.json()['plan']
    jobs=client.app.state.discovery_jobs
    jobs.jobs[source][2].cards[0]['place']['name']='不应使用的后台结果'
    seen=[]
    def answer(provider,message,conversation,snapshot,focused):
        seen.append(snapshot)
        assert snapshot['context']['name']=='新的出游计划'
        assert [c['place']['id'] for c in snapshot['cards']]==[c['id'] for c in plan['candidates']]
        assert snapshot['cards'][0]['place']['name']=='真实测试书店'
        assert all(c['route'] is None for c in snapshot['cards'])
        return '计划保留了这两处候选，本次没有查询个人路程。'
    monkeypatch.setattr('roambot.services.business_executor.explain_discovery_result',answer)
    client.app.state.provider_runtime=SimpleNamespace(new_request_bundle=lambda:SimpleNamespace(assistant=object()),close=lambda:None)
    client.app.dependency_overrides[get_business_planner]=lambda:(lambda *args:{'actions':[{'tool':'explain_result','arguments':{}}]})
    p=client.post('/api/v1/assistant/commands/proposals',headers={'X-CSRF-Token':csrf},json={
        'request_id':str(uuid4()),'message':'这两个计划地点有什么区别','context':{
            'page':'/plans/'+plan['id'],'plan_id':plan['id'],'discovery_job_id':source}})
    assert p.status_code==200
    result=execute(client,csrf,p.json()).json()
    assert result['status']=='completed'
    assert result['steps'][0]['result']['reply']=='计划保留了这两处候选，本次没有查询个人路程。'
    assert len(seen)==1


def test_expired_discovery_cannot_be_favorited_after_proposal(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_expiring_owner")
    key = source_job(client, csrf)
    planned = proposal(client, csrf, key)
    jobs = client.app.state.discovery_jobs
    actor, started, run = jobs.jobs[key]
    jobs.jobs[key] = (actor, started - 1801, run)
    result = execute(client, csrf, planned.json())
    assert result.json()["status"] == "failed"
    assert client.get("/api/v1/favorites").json()["favorites"] == []
