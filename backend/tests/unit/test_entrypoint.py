from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from roambot.config import Settings
from roambot.security.vault import CredentialVault


def live_settings(tmp_path: Path, secret_file: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        provider_mode="live",
        demo_mode=False,
        qweather_api_host="https://student.qweatherapi.com",
        llm_base_url="https://llm.example.com",
        llm_model="test-model",
        master_password_file=secret_file,
    )


class FakeStdin:
    def __init__(self, interactive: bool) -> None:
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


def test_resolve_master_password_reads_file_and_removes_only_trailing_newlines(
    tmp_path: Path,
) -> None:
    from roambot.entrypoint import resolve_master_password

    secret_file = tmp_path / "master-password"
    secret_file.write_bytes(b"  keep surrounding spaces  \r\n")
    secret_file.chmod(0o600)

    password = resolve_master_password(
        live_settings(tmp_path, secret_file),
        stdin=FakeStdin(False),
        prompt=lambda _: pytest.fail("prompt must not be used"),
    )

    assert password == "  keep surrounding spaces  "


def test_resolve_master_password_rejects_broad_posix_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from roambot.entrypoint import StartupConfigurationError, resolve_master_password

    secret_file = tmp_path / "master-password"
    secret_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr("roambot.entrypoint._posix_secret_mode", lambda _: 0o644)

    with pytest.raises(StartupConfigurationError, match="permissions"):
        resolve_master_password(live_settings(tmp_path, secret_file))


def test_resolve_master_password_prompts_only_for_a_tty(tmp_path: Path) -> None:
    from roambot.entrypoint import resolve_master_password

    settings = live_settings(tmp_path, tmp_path / "missing-secret")
    prompts: list[str] = []

    interactive = resolve_master_password(
        settings,
        stdin=FakeStdin(True),
        prompt=lambda text: prompts.append(text) or "prompted-secret",
    )
    non_interactive = resolve_master_password(
        settings,
        stdin=FakeStdin(False),
        prompt=lambda _: pytest.fail("non-interactive input must not prompt"),
    )

    assert interactive == "prompted-secret"
    assert non_interactive is None
    assert len(prompts) == 1


def test_resolve_master_password_consumes_cloud_environment_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from roambot.entrypoint import resolve_master_password

    settings = live_settings(tmp_path, tmp_path / "missing-secret")
    monkeypatch.setenv("ROAMBOT_MASTER_PASSWORD", "cloud-secret")

    password = resolve_master_password(
        settings,
        stdin=FakeStdin(False),
        prompt=lambda _: pytest.fail("non-interactive input must not prompt"),
    )

    assert password == "cloud-secret"
    assert "ROAMBOT_MASTER_PASSWORD" not in os.environ


def test_prepare_runtime_identity_is_a_noop_for_non_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import roambot.entrypoint as entrypoint

    settings = Settings(data_dir=tmp_path / "data", provider_mode="mock")
    monkeypatch.setattr(entrypoint, "_running_as_posix_root", lambda: False)
    monkeypatch.setattr(
        entrypoint,
        "_runtime_account",
        lambda: pytest.fail("non-root startup must not look up a runtime account"),
    )

    entrypoint.prepare_runtime_identity(settings)

    assert not settings.data_dir.exists()


def test_prepare_runtime_identity_owns_data_before_dropping_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import roambot.entrypoint as entrypoint

    settings = Settings(data_dir=tmp_path / "data", provider_mode="mock")
    account = SimpleNamespace(
        pw_name="roambot",
        pw_uid=10001,
        pw_gid=10001,
        pw_dir="/home/roambot",
    )
    events: list[tuple[object, ...]] = []
    monkeypatch.setattr(entrypoint, "_running_as_posix_root", lambda: True)
    monkeypatch.setattr(entrypoint, "_runtime_account", lambda: account)
    monkeypatch.setattr(
        entrypoint,
        "_chown_tree",
        lambda path, uid, gid: events.append(("chown", path, uid, gid)),
    )
    monkeypatch.setattr(
        entrypoint.os,
        "initgroups",
        lambda name, gid: events.append(("initgroups", name, gid)),
        raising=False,
    )
    monkeypatch.setattr(
        entrypoint.os,
        "setgid",
        lambda gid: events.append(("setgid", gid)),
        raising=False,
    )
    monkeypatch.setattr(
        entrypoint.os,
        "setuid",
        lambda uid: events.append(("setuid", uid)),
        raising=False,
    )

    entrypoint.prepare_runtime_identity(settings)

    assert settings.data_dir.is_dir()
    assert events == [
        ("chown", settings.data_dir, 10001, 10001),
        ("initgroups", "roambot", 10001),
        ("setgid", 10001),
        ("setuid", 10001),
    ]


def test_mock_main_starts_without_reading_a_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import roambot.entrypoint as entrypoint

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("spa", encoding="utf-8")
    settings = Settings(data_dir=tmp_path, provider_mode="mock", demo_mode=True)
    app = FastAPI()
    created: list[dict[str, object]] = []
    started: list[dict[str, object]] = []
    monkeypatch.setattr(entrypoint, "FRONTEND_DIST", dist)
    monkeypatch.setattr(entrypoint, "Settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "prepare_runtime_identity", lambda _: None)
    monkeypatch.setattr(
        entrypoint,
        "create_app",
        lambda **kwargs: created.append(kwargs) or app,
    )
    monkeypatch.setattr(
        entrypoint.uvicorn,
        "run",
        lambda application, **kwargs: started.append(
            {"application": application, **kwargs}
        ),
    )
    monkeypatch.setattr(
        entrypoint.CredentialVault,
        "unlock",
        lambda *_: pytest.fail("mock mode must not unlock a vault"),
    )

    assert entrypoint.main() == 0
    assert created == [
        {
            "settings": settings,
            "frontend_dist": dist,
            "provider_credentials": {},
        }
    ]
    assert started == [{"application": app, "host": "0.0.0.0", "port": 8000}]


def test_live_main_unlocks_once_and_passes_credentials_only_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import roambot.entrypoint as entrypoint

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("spa", encoding="utf-8")
    secret_file = tmp_path / "master-password"
    secret_file.write_text("vault-password\n", encoding="utf-8")
    secret_file.chmod(0o600)
    settings = live_settings(tmp_path, secret_file)
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create(
        "vault-password",
        {
            "amap_api_key": "amap-test-key",
            "qweather_api_key": "weather-test-key",
            "llm_api_key": "llm-test-key",
        },
    )
    original_unlock = CredentialVault.unlock
    unlock_calls: list[str] = []
    created: list[dict[str, object]] = []
    monkeypatch.setattr(entrypoint, "FRONTEND_DIST", dist)
    monkeypatch.setattr(entrypoint, "Settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "prepare_runtime_identity", lambda _: None)
    monkeypatch.setattr(
        entrypoint.CredentialVault,
        "unlock",
        lambda self, password: (
            unlock_calls.append(password) or original_unlock(self, password)
        ),
    )
    def capture_app(**kwargs: object) -> FastAPI:
        captured = dict(kwargs)
        raw_credentials = captured["provider_credentials"]
        assert isinstance(raw_credentials, dict)
        captured["provider_credentials"] = dict(raw_credentials)
        created.append(captured)
        return FastAPI()

    monkeypatch.setattr(entrypoint, "create_app", capture_app)
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda *_args, **_kwargs: None)

    assert entrypoint.main() == 0
    assert unlock_calls == ["vault-password"]
    assert created[0]["provider_credentials"] == {
        "amap_api_key": "amap-test-key",
        "qweather_api_key": "weather-test-key",
        "llm_api_key": "llm-test-key",
    }


def test_noninteractive_live_main_without_secret_exits_78_before_uvicorn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import roambot.entrypoint as entrypoint

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("spa", encoding="utf-8")
    settings = live_settings(tmp_path, tmp_path / "missing-secret")
    monkeypatch.setattr(entrypoint, "FRONTEND_DIST", dist)
    monkeypatch.setattr(entrypoint, "Settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "prepare_runtime_identity", lambda _: None)
    monkeypatch.setattr(entrypoint.sys, "stdin", FakeStdin(False))
    monkeypatch.setattr(
        entrypoint.uvicorn,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Uvicorn must not start"),
    )

    assert entrypoint.main() == 78
    assert (
        capsys.readouterr().err.strip()
        == "RoamBot live mode requires a readable master-password file"
    )
