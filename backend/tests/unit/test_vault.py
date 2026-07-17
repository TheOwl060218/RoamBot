import json
from pathlib import Path

import pytest

from roambot.security.vault import CredentialVault, VaultAuthenticationError

MASTER_PASSWORD = "test-master-password"
WRONG_PASSWORD = "wrong-test-master-password"
CREDENTIALS = {
    "amap_api_key": "fake-amap-key",
    "qweather_api_key": "fake-qweather-key",
    "llm_api_key": "fake-llm-key",
}


def test_vault_encrypts_credentials_and_unlocks_exact_values(tmp_path: Path) -> None:
    path = tmp_path / "credentials.vault"
    vault = CredentialVault(path)

    vault.create(MASTER_PASSWORD, CREDENTIALS)

    raw = path.read_bytes()
    envelope = json.loads(raw)
    assert envelope["version"] == 1
    assert envelope["kdf"]["name"] == "scrypt"
    assert envelope["cipher"]["name"] == "aes-256-gcm"
    for secret in (MASTER_PASSWORD, *CREDENTIALS.values()):
        assert secret.encode() not in raw
    assert vault.unlock(MASTER_PASSWORD) == CREDENTIALS


@pytest.mark.parametrize("tamper", [False, True])
def test_vault_rejects_wrong_passwords_and_tampering_without_partial_values(
    tmp_path: Path, tamper: bool
) -> None:
    path = tmp_path / "credentials.vault"
    vault = CredentialVault(path)
    vault.create(MASTER_PASSWORD, CREDENTIALS)

    if tamper:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        ciphertext = envelope["cipher"]["ciphertext"]
        envelope["cipher"]["ciphertext"] = ciphertext[:-1] + ("A" if ciphertext[-1] != "A" else "B")
        path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(VaultAuthenticationError) as error:
        vault.unlock(MASTER_PASSWORD if tamper else WRONG_PASSWORD)

    assert "fake" not in str(error.value).lower()
    assert "master" not in str(error.value).lower()


def test_update_and_clear_require_authentication(tmp_path: Path) -> None:
    vault = CredentialVault(tmp_path / "credentials.vault")
    vault.create(MASTER_PASSWORD)

    with pytest.raises(VaultAuthenticationError):
        vault.update(WRONG_PASSWORD, "amap_api_key", CREDENTIALS["amap_api_key"])
    assert vault.unlock(MASTER_PASSWORD)["amap_api_key"] is None

    vault.update(MASTER_PASSWORD, "amap_api_key", CREDENTIALS["amap_api_key"])
    assert vault.unlock(MASTER_PASSWORD)["amap_api_key"] == CREDENTIALS["amap_api_key"]

    with pytest.raises(VaultAuthenticationError):
        vault.clear(WRONG_PASSWORD, "amap_api_key")
    assert vault.unlock(MASTER_PASSWORD)["amap_api_key"] == CREDENTIALS["amap_api_key"]

    vault.clear(MASTER_PASSWORD, "amap_api_key")
    assert vault.unlock(MASTER_PASSWORD)["amap_api_key"] is None


def test_reset_removes_only_the_vault_file(tmp_path: Path) -> None:
    path = tmp_path / "credentials.vault"
    database = tmp_path / "roambot.db"
    database.write_bytes(b"sqlite-sibling")
    vault = CredentialVault(path)
    vault.create(MASTER_PASSWORD)

    vault.reset()

    assert not path.exists()
    assert database.read_bytes() == b"sqlite-sibling"
