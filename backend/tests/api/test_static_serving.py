from pathlib import Path

from fastapi.testclient import TestClient

from roambot.main import create_app


def frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><body>RoamBot SPA</body></html>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("window.ROAMBOT = true", encoding="utf-8")
    return dist


def test_production_serves_index_for_root_and_client_routes(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dist=frontend_dist(tmp_path)))

    root = client.get("/")
    history = client.get("/history")

    assert root.status_code == 200
    assert history.status_code == 200
    assert root.text == history.text
    assert "RoamBot SPA" in root.text
    assert root.headers["content-type"].startswith("text/html")


def test_production_serves_assets_without_capturing_api_or_missing_files(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(frontend_dist=frontend_dist(tmp_path)))

    asset = client.get("/assets/app.js")
    health = client.get("/api/v1/health")
    missing_api = client.get("/api/v1/missing")
    missing_asset = client.get("/assets/missing.js")
    suffixed_path = client.get("/robots.txt")

    assert asset.status_code == 200
    assert asset.text == "window.ROAMBOT = true"
    assert "javascript" in asset.headers["content-type"]
    assert health.status_code == 200
    assert health.json() == {"status": "ready"}
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert missing_api.json()["error"]["code"] == "not_found"
    assert missing_asset.status_code == 404
    assert "RoamBot SPA" not in missing_asset.text
    assert suffixed_path.status_code == 404
    assert "RoamBot SPA" not in suffixed_path.text


def test_development_without_dist_keeps_api_and_has_no_spa_routes() -> None:
    client = TestClient(create_app(frontend_dist=None))

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").status_code == 404
    assert client.get("/history").status_code == 404
