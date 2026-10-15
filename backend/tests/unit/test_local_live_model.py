import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from roambot.security.vault import CredentialVault


def test_local_startup_resolves_only_case_of_available_model(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[3] / "scripts" / "local_live.py"
    spec = importlib.util.spec_from_file_location("local_live_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.DIST = tmp_path / "frontend" / "dist"
    module.DIST.mkdir(parents=True)
    (module.DIST / "assets").mkdir()
    (module.DIST / "index.html").write_text("preview", encoding="utf-8")
    CredentialVault(tmp_path / "data/local-live/credentials.vault").create(
        "test-master",
        {
            "amap_api_key": "test-amap",
            "qweather_api_key": "test-weather",
            "llm_api_key": "test-llm",
        },
    )
    monkeypatch.setattr(module.sys, "argv", ["local_live.py"])
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["test-master", "test-js", "test-security"])
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "Qwen-Turbo"}, {"id": "Qwen3.7-Plus"}]}
        )
    )
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(
        module,
        "httpx",
        SimpleNamespace(Client=lambda **_: client, HTTPError=httpx.HTTPError),
        raising=False,
    )
    seen = []
    monkeypatch.setattr(
        module.uvicorn,
        "run",
        lambda app, **_: seen.append(
            (
                app.state.settings.llm_model,
                getattr(app.state.settings, "llm_enable_thinking", None),
                app.state.settings.assistant_timeout_seconds,
            )
        ),
    )
    monkeypatch.setattr(module, "configure_runtime_logging", lambda: None)
    assert module.main() == 0
    assert seen == [("Qwen3.7-Plus", False, 8)]


def _load_local_live():
    source = Path(__file__).resolve().parents[3] / "scripts" / "local_live.py"
    spec = importlib.util.spec_from_file_location("local_live_branches", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_gateway(module, monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        module,
        "httpx",
        SimpleNamespace(Client=lambda **_: client, HTTPError=httpx.HTTPError),
        raising=False,
    )


def test_gateway_model_returns_requested_id_on_exact_match(monkeypatch):
    module = _load_local_live()
    _patch_gateway(
        module,
        monkeypatch,
        lambda _: httpx.Response(200, json={"data": [{"id": "deepseek-v4-flash"}]}),
    )
    assert module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash") == ("deepseek-v4-flash")


def test_gateway_model_prompts_when_configured_id_is_absent(monkeypatch):
    module = _load_local_live()
    _patch_gateway(
        module,
        monkeypatch,
        lambda _: httpx.Response(200, json={"data": [{"id": "some-other-model"}]}),
    )
    monkeypatch.setattr("builtins.input", lambda _: "some-other-model")
    assert module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash") == ("some-other-model")


def test_gateway_model_cancels_when_prompt_is_dismissed(monkeypatch):
    module = _load_local_live()
    _patch_gateway(
        module,
        monkeypatch,
        lambda _: httpx.Response(200, json={"data": [{"id": "some-other-model"}]}),
    )
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(module.ModelConfigurationError, match="cancelled"):
        module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash")


def test_empty_catalog_reports_no_models(monkeypatch):
    module = _load_local_live()
    _patch_gateway(module, monkeypatch, lambda _: httpx.Response(200, json={"data": []}))
    with pytest.raises(module.ModelConfigurationError, match="no models"):
        module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash")


@pytest.mark.parametrize(
    "response,match",
    [
        (httpx.Response(401, json={"error": "x"}), "rejected the key"),
        (httpx.Response(403, json={"error": "x"}), "rejected the key"),
        (httpx.Response(500, text="boom"), "HTTP 500"),
        (httpx.Response(200, text="not-json"), "invalid JSON"),
        (httpx.Response(200, json={"unexpected": True}), "unexpected catalog shape"),
    ],
)
def test_gateway_failures_are_reported_not_swallowed(monkeypatch, response, match):
    module = _load_local_live()
    _patch_gateway(module, monkeypatch, lambda _: response)
    with pytest.raises(module.ModelConfigurationError, match=match):
        module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash")


def test_network_failure_is_not_treated_as_user_input_error(monkeypatch):
    module = _load_local_live()

    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    _patch_gateway(module, monkeypatch, handler)
    with pytest.raises(module.ModelConfigurationError, match="Unable to reach"):
        module.gateway_model("https://gw/v1", "k", "deepseek-v4-flash")
