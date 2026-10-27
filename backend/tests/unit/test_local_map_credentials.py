import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from roambot.security.vault import CredentialVault, VaultAuthenticationError

SERVICES = {
    "amap_api_key": "fake-amap",
    "qweather_api_key": "fake-weather",
    "llm_api_key": "fake-llm",
}
MAP = {"amap_js_key": "fake-js", "amap_js_security_code": "fake-security"}


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "local_map_test", Path(__file__).resolve().parents[3] / "scripts/local_live.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_map_pair_is_encrypted_and_survives_service_update(tmp_path):
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create("test-master", SERVICES)
    vault.update_many("test-master", MAP)
    vault.update("test-master", "llm_api_key", "replacement-llm")
    assert vault.unlock("test-master") == {**SERVICES, **MAP, "llm_api_key": "replacement-llm"}
    for secret in MAP.values():
        assert secret.encode() not in vault.path.read_bytes()
    before = vault.path.read_bytes()
    with pytest.raises(VaultAuthenticationError):
        vault.update_many("wrong-password", MAP)
    assert vault.path.read_bytes() == before


def test_missing_map_is_saved_once_and_next_start_does_not_prompt(tmp_path, monkeypatch):
    module = load_runner()
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create("test-master", SERVICES)
    answers = iter(MAP.values())
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    assert module.map_credentials(vault, "test-master", vault.unlock("test-master")) == MAP
    assert vault.unlock("test-master") == {**SERVICES, **MAP}
    monkeypatch.setattr(module.getpass, "getpass", lambda _: pytest.fail("must not prompt"))
    assert module.map_credentials(vault, "test-master", vault.unlock("test-master")) == MAP


def test_blank_second_map_value_leaves_vault_unchanged(tmp_path, monkeypatch):
    module = load_runner()
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create("test-master", SERVICES)
    before = vault.path.read_bytes()
    answers = iter(["fake-js", " "])
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    with pytest.raises(module.MapConfigurationError):
        module.map_credentials(vault, "test-master", vault.unlock("test-master"))
    assert vault.path.read_bytes() == before


def test_configure_map_is_offline_without_frontend_build(tmp_path, monkeypatch, capsys):
    module = load_runner()
    module.ROOT = tmp_path
    module.DIST = tmp_path / "missing-build"
    vault = CredentialVault(tmp_path / "data/local-live/credentials.vault")
    vault.create("test-master", {**SERVICES, **MAP})
    monkeypatch.setattr(module.sys, "argv", ["local_live.py", "--configure-map"])
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["test-master", "new-js", "new-security"])
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    monkeypatch.setattr(module, "gateway_model", lambda *_: pytest.fail("no network"))
    monkeypatch.setattr(module.uvicorn, "run", lambda *_args, **_kw: pytest.fail("no server"))
    assert module.main() == 0
    assert vault.unlock("test-master") == {
        **SERVICES,
        "amap_js_key": "new-js",
        "amap_js_security_code": "new-security",
    }
    output = capsys.readouterr().out
    assert "new-js" not in output and "new-security" not in output


@pytest.mark.parametrize("mode", [[], ["--probe"]])
def test_start_with_saved_map_only_prompts_for_password(tmp_path, monkeypatch, mode):
    module = load_runner()
    module.ROOT = tmp_path
    module.DIST = tmp_path / "frontend/dist"
    module.DIST.mkdir(parents=True)
    (module.DIST / "index.html").write_text("test-build", encoding="utf-8")
    vault = CredentialVault(tmp_path / "data/local-live/credentials.vault")
    vault.create("test-master", {**SERVICES, **MAP})
    before = vault.path.read_bytes()
    monkeypatch.setattr(module.sys, "argv", ["local_live.py", *mode])
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["test-master"])
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    monkeypatch.setattr(module, "gateway_model", lambda *_: "deepseek-v4-flash")
    seen = []

    def capture_app(**kwargs):
        settings = kwargs["settings"]
        assert kwargs["provider_credentials"] == SERVICES
        assert settings.amap_js_key.get_secret_value() == "fake-js"
        assert settings.amap_js_security_code.get_secret_value() == "fake-security"
        seen.append("server")
        return SimpleNamespace()

    monkeypatch.setattr(module, "create_app", capture_app)
    monkeypatch.setattr(module, "configure_runtime_logging", lambda: None)
    monkeypatch.setattr(module.uvicorn, "run", lambda *_args, **_kwargs: None)

    def capture_probe(*args):
        assert args[1:] == ("fake-llm", "deepseek-v4-flash")
        seen.append("probe")
        return 0

    monkeypatch.setattr(module, "probe_completion", capture_probe)
    assert module.main() == 0
    assert seen == (["probe"] if mode else ["server"])
    assert vault.path.read_bytes() == before


def test_cancel_map_update_keeps_previous_pair(tmp_path, monkeypatch):
    module = load_runner()
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create("test-master", {**SERVICES, **MAP})
    before = vault.path.read_bytes()
    answers = iter(["replacement-js"])

    def interrupted_input(_):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(module.getpass, "getpass", interrupted_input)
    with pytest.raises(KeyboardInterrupt):
        module.map_credentials(vault, "test-master", vault.unlock("test-master"), force=True)
    assert vault.path.read_bytes() == before


def test_semantic_diagnostic_needs_only_llm_and_never_starts_or_updates_vault(
    tmp_path, monkeypatch
):
    from roambot.providers import assistant_diagnostics

    module = load_runner()
    module.ROOT = tmp_path
    module.DIST = tmp_path / "missing-build"
    vault = CredentialVault(tmp_path / "data/local-live/credentials.vault")
    vault.create("test-master", {"llm_api_key": "fake-llm"})
    before = vault.path.read_bytes()
    monkeypatch.setattr(module.sys, "argv", ["local_live.py", "--diagnose-assistant"])
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    answers = iter(["test-master"])
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(answers))
    monkeypatch.setattr(module, "_available_model_ids", lambda *_: ["qwen3.7-plus"])
    monkeypatch.setattr(module, "gateway_model", lambda *_: pytest.fail("must not switch model"))
    monkeypatch.setattr(module, "map_credentials", lambda *_: pytest.fail("no maps"))
    monkeypatch.setattr(module.uvicorn, "run", lambda *_args, **_kw: pytest.fail("no server"))
    seen = []

    def run(base, key, model, output):
        seen.append((base, key, model, output))
        return 0

    monkeypatch.setattr(assistant_diagnostics, "run_assistant_diagnostic", run)
    assert module.main() == 0
    assert seen[0][1:3] == ("fake-llm", "qwen3.7-plus")
    assert seen[0][3] == tmp_path / "test-results/assistant-protocol-comparison.json"
    assert vault.path.read_bytes() == before


@pytest.mark.parametrize("flag", ["--parameters", "--audit", "--date-roles"])
def test_parameter_probe_is_private_and_has_no_catalog_or_startup_side_effects(
    tmp_path, monkeypatch, capsys, flag
):
    from roambot.providers import assistant_diagnostics

    module = load_runner()
    module.ROOT, module.DIST = tmp_path, tmp_path / "missing-build"
    vault = CredentialVault(tmp_path / "data/local-live/credentials.vault")
    vault.create("test-master", {"llm_api_key": "fake-llm"})
    before = vault.path.read_bytes()
    monkeypatch.setattr(module.sys, "argv", ["local_live.py", "--diagnose-assistant", flag])
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(module.getpass, "getpass", lambda _: "test-master")
    monkeypatch.setattr(module, "_available_model_ids", lambda *_: pytest.fail("no catalog call"))
    monkeypatch.setattr(module, "gateway_model", lambda *_: pytest.fail("no model switch"))
    monkeypatch.setattr(module, "map_credentials", lambda *_: pytest.fail("no maps"))
    monkeypatch.setattr(module.uvicorn, "run", lambda *_args, **_kw: pytest.fail("no server"))
    observed = []

    def run(base, key, model, output, **options):
        observed.append((key, model, output, options))
        return 0

    monkeypatch.setattr(assistant_diagnostics, "run_assistant_diagnostic", run)
    assert module.main() == 0
    assert observed == [
        (
            "fake-llm",
            "qwen3.7-plus",
            tmp_path
            / (
                "test-results/assistant-parameter-probe.json"
                if flag == "--parameters"
                else "test-results/assistant-date-role-comparison.json"
                if flag == "--date-roles"
                else "test-results/assistant-semantic-audit.json"
            ),
            {"parameters": True}
            if flag == "--parameters"
            else {"date_roles": True}
            if flag == "--date-roles"
            else {"audit": True},
        )
    ]
    assert vault.path.read_bytes() == before
    assert "fake-llm" not in capsys.readouterr().out


@pytest.mark.parametrize("mode", [None, "--holdout", "--holdout-focus"])
def test_model_comparison_selects_catalog_id_only_for_experiment_without_config_or_vault_change(
    tmp_path, monkeypatch, capsys, mode
):
    from roambot.providers import assistant_candidate_holdout, assistant_model_comparison

    module = load_runner()
    module.ROOT, module.DIST = tmp_path, tmp_path / "missing-build"
    vault = CredentialVault(tmp_path / "data/local-live/credentials.vault")
    vault.create("test-master", {"llm_api_key": "fake-llm"})
    before = vault.path.read_bytes()
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["local_live.py", "--compare-models"] + ([mode] if mode else []),
    )
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(module.getpass, "getpass", lambda _: "test-master")
    catalog_calls = []
    monkeypatch.setattr(
        module,
        "_available_model_ids",
        lambda *_: catalog_calls.append(1) or ["Qwen-Turbo", "Qwen-Plus"],
    )
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(module, "gateway_model", lambda *_: pytest.fail("no website model chooser"))
    monkeypatch.setattr(module, "map_credentials", lambda *_: pytest.fail("no map access"))
    monkeypatch.setattr(module.uvicorn, "run", lambda *_args, **_kw: pytest.fail("no server"))
    seen = []

    def run(base, key, baseline, candidate, output):
        seen.append((key, baseline, candidate, output))
        return 0

    monkeypatch.setattr(assistant_model_comparison, "run_model_comparison", run)
    options_seen = []

    def holdout_run(base, key, model, output, **options):
        options_seen.append(options)
        return run(base, key, None, model, output)

    monkeypatch.setattr(
        assistant_candidate_holdout,
        "run_candidate_holdout",
        holdout_run,
    )
    assert module.main() == 0
    assert catalog_calls == [1]
    assert seen == [
        (
            "fake-llm",
            None if mode else "Qwen-Turbo",
            "Qwen-Plus",
            tmp_path
            / (
                "test-results/assistant-candidate-focus.json"
                if mode == "--holdout-focus"
                else "test-results/assistant-candidate-holdout.json"
                if mode
                else "test-results/assistant-model-latency-comparison.json"
            ),
        )
    ]
    assert vault.path.read_bytes() == before
    assert "fake-llm" not in capsys.readouterr().out


def test_model_experiment_cannot_use_unverified_or_thinking_only_candidate(monkeypatch):
    module = load_runner()
    monkeypatch.setattr(
        module, "_available_model_ids", lambda *_: ["qwen-turbo", "qwen-plus", "glm-5.3"]
    )
    monkeypatch.setattr("builtins.input", lambda _: "glm-5.3")
    with pytest.raises(module.ModelConfigurationError):
        module.comparison_models("https://fixture.invalid", "fake-key", "qwen-turbo")
