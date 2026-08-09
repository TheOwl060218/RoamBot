from __future__ import annotations

import getpass
import os
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import uvicorn
from pydantic import ValidationError

from roambot.config import ProviderMode, Settings
from roambot.main import create_app
from roambot.security.vault import CredentialVault, VaultAuthenticationError

FRONTEND_DIST = Path("/app/frontend/dist")
CONFIGURATION_EXIT_CODE = 78


class InputStream(Protocol):
    def isatty(self) -> bool: ...


class RuntimeAccount(Protocol):
    pw_name: str
    pw_uid: int
    pw_gid: int


class StartupConfigurationError(RuntimeError):
    pass


def _posix_secret_mode(path: Path) -> int | None:
    if os.name != "posix":
        return None
    return stat.S_IMODE(path.stat().st_mode)


def _running_as_posix_root() -> bool:
    return os.name == "posix" and os.geteuid() == 0


def _runtime_account() -> RuntimeAccount:
    import pwd

    return pwd.getpwnam("roambot")


def _chown_tree(root: Path, uid: int, gid: int) -> None:
    for current_root, directory_names, file_names in os.walk(root):
        os.chown(current_root, uid, gid, follow_symlinks=False)
        for name in [*directory_names, *file_names]:
            os.chown(
                Path(current_root) / name,
                uid,
                gid,
                follow_symlinks=False,
            )


def prepare_runtime_identity(settings: Settings) -> None:
    if not _running_as_posix_root():
        return

    try:
        account = _runtime_account()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _chown_tree(settings.data_dir, account.pw_uid, account.pw_gid)
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    except (KeyError, OSError):
        raise StartupConfigurationError(
            "Runtime user or data-directory initialization failed."
        ) from None


def resolve_master_password(
    settings: Settings,
    *,
    stdin: InputStream | None = None,
    prompt: Callable[[str], str] | None = None,
) -> str | None:
    if settings.provider_mode is ProviderMode.MOCK:
        return None

    secret_path = settings.master_password_file
    if secret_path.exists():
        mode = _posix_secret_mode(secret_path)
        if mode is not None and mode & 0o077:
            raise StartupConfigurationError(
                "Master-password file permissions allow group or world access."
            )
        try:
            buffer = bytearray(secret_path.read_bytes())
        except OSError:
            raise StartupConfigurationError(
                "Master-password file is not readable."
            ) from None
        try:
            try:
                password = buffer.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError:
                raise StartupConfigurationError(
                    "Master-password file is not valid UTF-8."
                ) from None
        finally:
            for index in range(len(buffer)):
                buffer[index] = 0
        if not password:
            raise StartupConfigurationError("Master-password file is empty.")
        return password

    environment_password = os.environ.pop("ROAMBOT_MASTER_PASSWORD", None)
    if environment_password is not None:
        if not environment_password:
            raise StartupConfigurationError(
                "ROAMBOT_MASTER_PASSWORD is empty."
            )
        return environment_password

    input_stream = stdin or sys.stdin
    if input_stream.isatty():
        read_password = prompt or getpass.getpass
        password = read_password("RoamBot master password: ")
        if password:
            return password
    return None


def _configured_credentials(values: dict[str, str | None]) -> dict[str, str]:
    names = ("amap_api_key", "qweather_api_key", "llm_api_key")
    credentials: dict[str, str] = {}
    for name in names:
        value = values.get(name)
        if not isinstance(value, str) or not value.strip():
            raise StartupConfigurationError("Live provider credentials are incomplete.")
        credentials[name] = value.strip()
    return credentials


def _configuration_error(message: str) -> int:
    print(message, file=sys.stderr)
    return CONFIGURATION_EXIT_CODE


def main() -> int:
    try:
        settings = Settings()
    except ValidationError:
        return _configuration_error("RoamBot configuration is invalid")

    if not (FRONTEND_DIST / "index.html").is_file():
        return _configuration_error("RoamBot frontend build is missing")

    try:
        prepare_runtime_identity(settings)
    except StartupConfigurationError:
        return _configuration_error("RoamBot data directory initialization failed")

    credentials: dict[str, str] = {}
    if settings.provider_mode is ProviderMode.LIVE:
        try:
            master_password = resolve_master_password(settings)
        except StartupConfigurationError:
            return _configuration_error(
                "RoamBot live mode requires a readable master-password file"
            )
        if master_password is None:
            return _configuration_error(
                "RoamBot live mode requires a readable master-password file"
            )
        try:
            values = CredentialVault(
                settings.data_dir / "credentials.vault"
            ).unlock(master_password)
            try:
                credentials = _configured_credentials(values)
            finally:
                values.clear()
        except (StartupConfigurationError, VaultAuthenticationError):
            return _configuration_error("RoamBot credential vault authentication failed")
        finally:
            master_password = None

    application = create_app(
        settings=settings,
        frontend_dist=FRONTEND_DIST,
        provider_credentials=credentials,
    )
    credentials.clear()
    uvicorn.run(application, host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
