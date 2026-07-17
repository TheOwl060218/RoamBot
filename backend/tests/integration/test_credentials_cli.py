from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from roambot.cli import app
from roambot.security.vault import CredentialVault

MASTER_PASSWORD = "cli-master-password"
FAKE_AMAP_KEY = "fake-amap-key"
FAKE_QWEATHER_KEY = "fake-qweather-key"
FAKE_LLM_KEY = "fake-llm-key"


class PromptRecorder:
    def __init__(self, responses: list[str]) -> None:
        self.responses: Iterator[str] = iter(responses)
        self.calls: list[tuple[str, bool, bool]] = []

    def __call__(
        self,
        text: str,
        *,
        hide_input: bool = False,
        confirmation_prompt: bool = False,
        **_: object,
    ) -> str:
        self.calls.append((text, hide_input, confirmation_prompt))
        return next(self.responses)


def test_status_without_vault_reports_all_services_unconfigured_without_prompting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROAMBOT_DATA_DIR", str(tmp_path))
    prompt = PromptRecorder([])
    monkeypatch.setattr("roambot.cli.typer.prompt", prompt)

    result = CliRunner().invoke(app, ["credentials", "status"])

    assert result.exit_code == 0
    assert prompt.calls == []
    assert result.output.lower().count("unconfigured") == 3


def test_init_set_clear_and_status_use_hidden_prompts_and_redact_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROAMBOT_DATA_DIR", str(tmp_path))
    runner = CliRunner()

    init_prompt = PromptRecorder([MASTER_PASSWORD])
    monkeypatch.setattr("roambot.cli.typer.prompt", init_prompt)
    init = runner.invoke(app, ["credentials", "init"])

    set_prompt = PromptRecorder([MASTER_PASSWORD, FAKE_AMAP_KEY])
    monkeypatch.setattr("roambot.cli.typer.prompt", set_prompt)
    set_result = runner.invoke(app, ["credentials", "set", "amap"])

    clear_prompt = PromptRecorder([MASTER_PASSWORD])
    monkeypatch.setattr("roambot.cli.typer.prompt", clear_prompt)
    clear_result = runner.invoke(app, ["credentials", "clear", "amap"])

    status_prompt = PromptRecorder([MASTER_PASSWORD])
    monkeypatch.setattr("roambot.cli.typer.prompt", status_prompt)
    status = runner.invoke(app, ["credentials", "status"])

    for result in (init, set_result, clear_result, status):
        assert result.exit_code == 0
        for secret in (MASTER_PASSWORD, FAKE_AMAP_KEY, FAKE_QWEATHER_KEY, FAKE_LLM_KEY):
            assert secret not in result.output
    assert init_prompt.calls == [("主密码", True, True)]
    hidden_prompt_calls = set_prompt.calls + clear_prompt.calls + status_prompt.calls
    assert all(hide_input for _, hide_input, _ in hidden_prompt_calls)
    assert "unconfigured" in status.output.lower()


def test_reset_requires_exact_confirmation_and_preserves_sqlite_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROAMBOT_DATA_DIR", str(tmp_path))
    vault_path = tmp_path / "credentials.vault"
    database_path = tmp_path / "roambot.db"
    CredentialVault(vault_path).create(MASTER_PASSWORD, {"llm_api_key": FAKE_LLM_KEY})
    database_path.write_bytes(b"sqlite-sibling")
    runner = CliRunner()

    rejected = runner.invoke(app, ["credentials", "reset"], input="RESET-CREDENTIAL\n")

    assert rejected.exit_code != 0
    assert vault_path.exists()
    accepted = runner.invoke(app, ["credentials", "reset"], input="RESET-CREDENTIALS\n")
    assert accepted.exit_code == 0
    assert not vault_path.exists()
    assert database_path.read_bytes() == b"sqlite-sibling"
