import re

from roambot.security.passwords import hash_password, verify_password
from roambot.security.sessions import SessionSecrets, hash_token, new_token


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "correct horse battery staple"

    encoded = hash_password(password)

    assert password not in encoded
    assert encoded.startswith("$argon2")
    assert verify_password(encoded, password) is True
    assert verify_password(encoded, "wrong") is False


def test_password_verification_rejects_invalid_encoding_without_leaking_errors() -> None:
    assert verify_password("not-an-argon2-hash", "password") is False


def test_tokens_are_url_safe_and_hash_to_lowercase_sha256_hex() -> None:
    token = new_token()
    another_token = new_token()

    assert len(token) >= 43
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token)
    assert token != another_token

    digest = hash_token(token)
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert hash_token(token) == digest
    assert hash_token(another_token) != digest


def test_session_secrets_keep_plaintexts_distinct_and_expose_verifiable_hashes() -> None:
    secrets = SessionSecrets.create()

    assert secrets.session_token != secrets.csrf_token
    assert secrets.session_hash != secrets.csrf_hash
    assert secrets.session_token != secrets.session_hash
    assert secrets.csrf_token != secrets.csrf_hash
    assert hash_token(secrets.session_token) == secrets.session_hash
    assert hash_token(secrets.csrf_token) == secrets.csrf_hash
