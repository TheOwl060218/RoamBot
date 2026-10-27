import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roambot.api.dependencies import AuthApiError
from roambot.api.routes.discovery import get_discovery_factory
from roambot.config import Settings
from roambot.domain.discovery import Finish
from roambot.main import create_app
from roambot.providers.amap import AMapProvider
from roambot.services.discovery import DiscoveryRun


def test_jobs_are_actor_isolated_and_no_mandatory_query_form_is_required(tmp_path):
    app = create_app(Settings(provider_mode="mock", data_dir=tmp_path, secure_cookies=False))

    def factory(body, previous):
        return DiscoveryRun(
            body,
            None,
            None,
            None,
            lambda messages: (
                "finish",
                Finish(reply="只需明确想在哪个城市附近看看。", request_location=True),
            ),
            previous,
        )

    app.dependency_overrides[get_discovery_factory] = lambda: factory
    with TestClient(app) as one, TestClient(app) as two:
        started = one.post("/api/v1/discovery/jobs", json={"message": "我想出去走走"})
        assert started.status_code == 200
        key = started.json()["id"]
        for _ in range(100):
            result = one.get("/api/v1/discovery/jobs/" + key)
            if result.json()["status"] != "running":
                break
            time.sleep(0.01)
        assert result.status_code == 200
        assert result.json()["context"]["start_date"] is None
        assert result.json()["request_location"] is True
        assert two.get("/api/v1/discovery/jobs/" + key).status_code == 404
        assert (
            two.post(
                "/api/v1/discovery/jobs", json={"message": "接着刚才", "previous_id": key}
            ).status_code
            == 404
        )
        assert one.delete("/api/v1/discovery/jobs/" + key).status_code == 200


def test_live_prototype_does_not_silently_substitute_mock_recommendations(tmp_path):
    app = create_app(Settings(provider_mode="mock", data_dir=tmp_path))
    with TestClient(app) as client:
        result = client.post("/api/v1/discovery/jobs", json={"message": "附近找本摄影集看看"})
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "configuration_error"


def test_real_discovery_requires_configured_search_instead_of_unreliable_fallback():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                provider_runtime=SimpleNamespace(
                    _adapters=SimpleNamespace(
                        places=object.__new__(AMapProvider),
                    )
                ),
                settings=Settings(),
            )
        )
    )
    with pytest.raises(AuthApiError) as error:
        get_discovery_factory(request, bundle=None)
    assert error.value.status_code == 503
    assert error.value.code == "discovery_search_not_configured"
