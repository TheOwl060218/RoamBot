from types import SimpleNamespace
import time

from test_history import register

from roambot.api.routes.discovery import get_discovery_factory
from roambot.config import Settings
from roambot.domain.discovery import DiscoveryRequest, RetrievalPlan, SearchContext, VenueSelection, GroundedBatch, BatchReview
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.domain.discovery_snapshot import StoredCard
from roambot.providers.amap import AMapProvider
from roambot.services.discovery_orchestrator import DiscoveryOrchestrator
from roambot.services.discovery_workflow import DiscoveryWorkflow


def request_for(tmp_path, mode):
    amap = object.__new__(AMapProvider)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        provider_runtime=SimpleNamespace(_adapters=SimpleNamespace(places=amap)),
        settings=Settings(data_dir=tmp_path, discovery_search_api_key="controlled-not-a-real-key"),
        discovery_orchestration_mode=mode)))
    bundle = SimpleNamespace(assistant=SimpleNamespace(_model="unchanged-test-model"), weather=None)
    return request, bundle


def test_new_factory_preserves_job_contract_and_shares_process_gate(tmp_path):
    request, bundle = request_for(tmp_path, "coordinated")
    factory = get_discovery_factory(request, bundle)
    runs = [factory(DiscoveryRequest(message="苏州走走"), None) for _ in range(2)]
    assert all(isinstance(run, DiscoveryOrchestrator) for run in runs)
    assert runs[0].gate is runs[1].gate
    assert runs[0].gate.capacity == 2
    assert runs[0].model.provider is bundle.assistant
    assert set(DiscoveryWorkflow.snapshot(runs[0])) <= set(runs[0].snapshot())
    assert runs[0].snapshot()["workflow"] == "coordinated-v1"


def test_legacy_factory_is_retained_for_comparison(tmp_path):
    request, bundle = request_for(tmp_path, "legacy")
    run = get_discovery_factory(request, bundle)(DiscoveryRequest(message="苏州走走"), None)
    assert type(run) is DiscoveryWorkflow
    assert run.snapshot()["workflow"] == "adaptive-v2"


def controlled_factory(folder, *, business=False):
    places = [{"id": f"amap:coordinated{i}", "name": name, "city": "苏州", "address": "测试地址",
               "map_type": "受控测试场所", "coordinate": {"longitude": 120, "latitude": 31, "system": "gcj02"},
               "map_url": f"https://www.amap.com/detail/coordinated{i}", "facts": {}}
              for i, name in enumerate(("受控书店", "受控湖边"), 1)]
    sources = [{"title": p["name"] + "介绍", "url": f"https://example.org/{p['id']}",
                "kind": "web_page", "excerpt": p["name"] + "具有明确公开资料，可供参观休息，属于受控测试。"}
               for p in places]
    calls = []

    def plan(*args):
        calls.append("plan")
        return RetrievalPlan(context=SearchContext(region="苏州"), goal="受控测试",
            intent="business" if business else "search", map_queries=["受控场所"], web_queries=["受控资料"],
            business_plan={"actions": [{"tool": "close_layer", "arguments": {}}]} if business else None)

    def search(query):
        calls.append("search")
        return sources

    model = SimpleNamespace(version="controlled-api-model", plan=plan,
        nominate=lambda *args: VenueSelection(venues=[{"name": p["name"], "place_id": p["id"]} for p in places]),
        compose=lambda conversation, goal, context, candidates: GroundedBatch(cards=[{
            "place_id": c["place"]["id"], "experience": "受控休闲", "reason": "来自真实结构的受控测试资料，验证发布与归档链路，不调用真实Provider。",
            "evidence_ids": [s["id"] for s in c["sources"] if s["kind"] == "web_page"][:1]}
            for c in candidates]))

    def factory(body, previous):
        return DiscoveryOrchestrator(body, SimpleNamespace(search=lambda *args: places), None,
            SimpleNamespace(search=search), model, DiscoveryCache(folder / "facts.sqlite3"), "",
            previous, source="demo", batch_reviewer=lambda conversation, context, cards: BatchReview(
                approved_ids=[c["place"]["id"] for c in cards], rejected=[]))
    return factory, calls


def start_controlled(client, csrf):
    response = client.post("/api/v1/discovery/jobs", headers={"X-CSRF-Token": csrf},
                           json={"message": "受控测试"})
    assert response.status_code == 200
    key = response.json()["id"]
    for _ in range(100):
        snapshot = client.get("/api/v1/discovery/jobs/" + key).json()
        if snapshot["status"] != "running":
            return key, snapshot
        time.sleep(0.01)
    raise AssertionError("coordinated job did not reach its terminal state")


def test_coordinated_job_archives_once_and_restores_without_provider(auth_api_fixture, tmp_path):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "coordinated_archive")
    factory, calls = controlled_factory(tmp_path)
    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    key, snapshot = start_controlled(client, csrf)
    assert snapshot["status"] == "completed" and len(snapshot["cards"]) == 2
    assert snapshot["workflow"] == "coordinated-v1" and snapshot["history_id"]
    headers = {"X-CSRF-Token": csrf}
    saved = client.post("/api/v1/discovery/jobs/" + key + "/history", headers=headers)
    assert saved.status_code == 200 and saved.json()["history_id"] == snapshot["history_id"]
    assert len(client.get("/api/v1/history").json()["histories"]) == 1
    detail = client.get("/api/v1/history/" + snapshot["history_id"]).json()["history"]
    # Archive deliberately retains the complete StoredCard whitelist, not transient review flags.
    expected = [StoredCard.model_validate(c).model_dump(mode="json") for c in snapshot["cards"]]
    assert detail["mode"] == "discovery" and detail["result"]["cards"] == expected
    assert all(c["reviewed"] is True for c in snapshot["cards"])
    before = list(calls)
    client.app.state.discovery_jobs.jobs.pop(key)
    restored = client.post("/api/v1/discovery/history/" + snapshot["history_id"] + "/restore", headers=headers)
    assert restored.status_code == 200 and restored.json()["cards"] == expected
    assert calls == before


def test_coordinated_business_intake_never_searches_or_archives(auth_api_fixture, tmp_path):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "coordinated_intake")
    factory, calls = controlled_factory(tmp_path, business=True)
    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    _, snapshot = start_controlled(client, csrf)
    assert snapshot["intent"] == "business" and snapshot["status"] == "completed"
    assert calls == ["plan"] and snapshot["cards"] == [] and snapshot["history_id"] is None
    assert snapshot["metrics"]["model_calls"] == 1
