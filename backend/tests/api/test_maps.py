import httpx
from fastapi.testclient import TestClient

from roambot.config import Settings
from roambot.main import create_app


def test_map_configuration_is_disabled_without_both_credentials():
    response = TestClient(create_app()).get("/api/v1/maps/config")
    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_map_configuration_never_discloses_security_code():
    app = create_app(Settings(amap_js_key="test-browser-key", amap_js_security_code="test-secret"))
    response = TestClient(app).get("/api/v1/maps/config")
    assert response.json() == {
        "enabled": True,
        "key": "test-browser-key",
        "service_host": "/_AMapService",
    }
    assert "test-secret" not in response.text
    assert "test-secret" not in repr(app.state.settings)


def test_map_proxy_rejects_unknown_paths_without_network():
    client = TestClient(create_app())
    assert client.get("/api/v1/maps/_AMapService/v3/place/text").status_code == 404
    assert client.get("/api/v1/maps/_AMapService/v4/map/styles").status_code == 503
    assert client.get("/_AMapService/v3/place/text").status_code == 404
    assert client.get("/_AMapService/v3/direction/walking").status_code == 404
    assert client.get("/_AMapService/v4/map/styles").status_code == 503


def test_map_proxy_uses_fixed_host_and_server_secret_only():
    app = create_app(Settings(amap_js_key="test-browser-key", amap_js_security_code="test-secret"))

    def upstream(request):
        assert request.url.host == "webapi.amap.com"
        assert request.url.path == "/v4/map/styles"
        assert request.url.params["jscode"] == "test-secret"
        assert request.url.params["key"] == "test-browser-key"
        assert request.headers.get("cookie") is None
        return httpx.Response(
            200, content=b'{"ok":true}', headers={"Content-Type": "application/json"}
        )

    app.state.map_transport = httpx.MockTransport(upstream)
    response = TestClient(app).get(
        "/_AMapService/v4/map/styles?key=attacker&jscode=attacker",
        headers={"Cookie": "session=private"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "test-secret" not in response.text


def test_map_proxy_sanitizes_transport_failure():
    app = create_app(Settings(amap_js_key="test-browser-key", amap_js_security_code="test-secret"))

    def upstream(request):
        raise httpx.ConnectError("test-secret", request=request)

    app.state.map_transport = httpx.MockTransport(upstream)
    response = TestClient(app).get("/api/v1/maps/_AMapService/v4/map/styles")
    assert response.status_code == 502
    assert "test-secret" not in response.text


def test_ip_city_lookup_keeps_fixed_upstream_and_private_credentials():
    from types import SimpleNamespace
    from roambot.providers.amap import AMapProvider
    app = create_app(Settings(amap_js_key='test-browser-key', amap_js_security_code='test-secret'))
    app.state.provider_runtime = SimpleNamespace(_adapters=SimpleNamespace(geocoder=AMapProvider(None, 'test-web-key')))
    def upstream(request):
        assert request.url.host == 'restapi.amap.com'
        assert request.url.path == '/v3/ip'
        assert request.url.params['key'] == 'test-web-key'
        assert 'jscode' not in request.url.params
        assert request.headers.get('cookie') is None
        return httpx.Response(200, json={'status': '1', 'city': '苏州市', 'adcode': '320500'})
    app.state.map_transport = httpx.MockTransport(upstream)
    response = TestClient(app).get('/api/v1/maps/_AMapService/v3/ip?key=attacker&jscode=attacker',
        headers={'Cookie': 'session=private'})
    assert response.status_code == 200
    assert response.json()['city'] == '苏州市'
    assert 'test-secret' not in response.text


def test_ip_city_proxy_does_not_expose_private_web_key_or_fall_back_to_js_key():
    from types import SimpleNamespace
    from roambot.providers.amap import AMapProvider
    app = create_app(Settings(amap_js_key='test-browser-key', amap_js_security_code='test-secret'))
    client = TestClient(app)
    assert client.get('/api/v1/maps/_AMapService/v3/ip').status_code == 503
    app.state.provider_runtime = SimpleNamespace(_adapters=SimpleNamespace(geocoder=AMapProvider(None, 'test-web-key')))
    app.state.map_transport = httpx.MockTransport(lambda _: httpx.Response(200, text='test-web-key'))
    response = client.get('/api/v1/maps/_AMapService/v3/ip')
    assert response.status_code == 502
    assert 'test-web-key' not in response.text


def test_map_proxy_supports_sdk_initialization_log_without_forwarding_client_credentials():
    app = create_app(Settings(amap_js_key="test-browser-key", amap_js_security_code="test-secret"))

    def upstream(request):
        assert request.url.host == "restapi.amap.com"
        assert request.url.path == "/v3/log/init"
        assert request.url.params["key"] == "test-browser-key"
        assert request.url.params["jscode"] == "test-secret"
        assert request.headers.get("cookie") is None
        return httpx.Response(200, json={"status": "1"})

    app.state.map_transport = httpx.MockTransport(upstream)
    response = TestClient(app).get(
        "/api/v1/maps/_AMapService/v3/log/init?key=attacker&jscode=attacker",
        headers={"Cookie": "session=private"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "1"}
    assert "test-secret" not in response.text


def test_map_proxy_limits_calls_and_never_follows_redirects():
    app = create_app(Settings(amap_js_key="test-browser-key", amap_js_security_code="test-secret"))
    app.state.map_transport = httpx.MockTransport(
        lambda _: httpx.Response(302, headers={"Location": "https://untrusted.invalid"})
    )
    client = TestClient(app)
    assert client.get("/api/v1/maps/_AMapService/v4/map/styles").status_code == 502
    for _ in range(59):
        client.get("/api/v1/maps/_AMapService/v4/map/styles")
    assert client.get("/api/v1/maps/_AMapService/v4/map/styles").status_code == 429
