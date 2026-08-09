from __future__ import annotations

import base64
import binascii
import json
import os
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from secrets import token_hex
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_ASSOCIATED_DATA = b"roambot-vault-v1"
_CREDENTIAL_NAMES = ("amap_api_key", "qweather_api_key", "llm_api_key")
_KDF_PARAMETERS = {"name": "scrypt", "n": 32768, "r": 8, "p": 1}
_CIPHER_NAME = "aes-256-gcm"


class VaultAuthenticationError(Exception):
    """Raised when a credential vault cannot be authenticated."""


class CredentialVault:
    def __init__(self, path: Path) -> None:
        self.path = path

    def create(
        self, master_password: str, credentials: Mapping[str, str | None] | None = None
    ) -> None:
        self._write(master_password, self._normalize_credentials(credentials or {}))

    def unlock(self, master_password: str) -> dict[str, str | None]:
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
            salt = self._decode_envelope(envelope, "kdf", "salt")
            nonce = self._decode_envelope(envelope, "cipher", "nonce")
            ciphertext = self._decode_envelope(envelope, "cipher", "ciphertext")
            self._validate_envelope(envelope)
            plaintext = AESGCM(self._derive_key(master_password, salt)).decrypt(
                nonce, ciphertext, _ASSOCIATED_DATA
            )
            decoded = json.loads(plaintext.decode("utf-8"))
            return self._normalize_credentials(decoded)
        except (
            InvalidTag,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            binascii.Error,
        ):
            raise VaultAuthenticationError("Unable to authenticate credential vault.") from None

    def update(self, master_password: str, credential_name: str, value: str) -> None:
        credentials = self.unlock(master_password)
        if credential_name not in _CREDENTIAL_NAMES or not isinstance(value, str):
            raise ValueError("Unsupported credential name or value.")
        credentials[credential_name] = value
        self._write(master_password, credentials)

    def clear(self, master_password: str, credential_name: str) -> None:
        credentials = self.unlock(master_password)
        if credential_name not in _CREDENTIAL_NAMES:
            raise ValueError("Unsupported credential name.")
        credentials[credential_name] = None
        self._write(master_password, credentials)

    def reset(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            raise VaultAuthenticationError("Unable to reset credential vault.") from None

    @staticmethod
    def _derive_key(master_password: str, salt: bytes) -> bytes:
        kdf = Scrypt(salt=salt, length=32, n=32768, r=8, p=1)
        return kdf.derive(master_password.encode("utf-8"))

    @staticmethod
    def _normalize_credentials(credentials: Mapping[str, Any]) -> dict[str, str | None]:
        if not isinstance(credentials, Mapping) or set(credentials) - set(_CREDENTIAL_NAMES):
            raise ValueError("Invalid credential vault.")
        normalized = {name: credentials.get(name) for name in _CREDENTIAL_NAMES}
        if any(value is not None and not isinstance(value, str) for value in normalized.values()):
            raise ValueError("Invalid credential vault.")
        return normalized

    @staticmethod
    def _decode_envelope(envelope: Mapping[str, Any], section: str, field: str) -> bytes:
        return base64.b64decode(envelope[section][field], validate=True)

    @staticmethod
    def _validate_envelope(envelope: Mapping[str, Any]) -> None:
        if (
            envelope["version"] != 1
            or envelope["kdf"].get("name") != _KDF_PARAMETERS["name"]
            or envelope["kdf"].get("n") != _KDF_PARAMETERS["n"]
            or envelope["kdf"].get("r") != _KDF_PARAMETERS["r"]
            or envelope["kdf"].get("p") != _KDF_PARAMETERS["p"]
            or envelope["cipher"].get("name") != _CIPHER_NAME
        ):
            raise ValueError("Invalid credential vault.")

    def _write(self, master_password: str, credentials: Mapping[str, str | None]) -> None:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        plaintext = json.dumps(
            self._normalize_credentials(credentials),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        ciphertext = AESGCM(self._derive_key(master_password, salt)).encrypt(
            nonce, plaintext, _ASSOCIATED_DATA
        )
        envelope = {
            "version": 1,
            "kdf": {
                **_KDF_PARAMETERS,
                "salt": base64.b64encode(salt).decode("ascii"),
            },
            "cipher": {
                "name": _CIPHER_NAME,
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            },
        }
        encoded = json.dumps(
            envelope, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.{token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(encoded)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
            with suppress(OSError):
                os.chmod(self.path, 0o600)
        finally:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
