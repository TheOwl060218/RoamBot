# RoamBot Accounts and Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure local accounts, SQLite persistence, favorites, history, anonymous shares, provider cache storage, and an encrypted credential-vault CLI without blocking guest recommendations.

**Architecture:** SQLAlchemy repositories isolate persistence from domain services. Server-side sessions use random opaque tokens stored as SHA-256 hashes; a separate CSRF token hash protects authenticated mutations. Personal-data services enforce ownership in the backend. Provider credentials live in a Scrypt-derived AES-GCM file controlled only by a local Typer CLI.

**Tech Stack:** Python 3.13, SQLAlchemy 2, Alembic, SQLite, Argon2, cryptography AES-GCM/Scrypt, Typer, FastAPI, pytest.

## Global Constraints

- Complete and verify `2026-07-15-roambot-01-core-backend.md` first.
- Keep `POST /api/v1/recommendations` and `/place-evaluations` available to guests.
- V1 uses username/password only; no phone, SMS, email, OAuth, CAPTCHA, password recovery, export, or account deletion.
- Passwords, session tokens, CSRF tokens, share tokens, master passwords, and provider keys must never be logged or stored in plaintext.
- Deleting history must invalidate related shares and must not delete favorites.
- Favorites store place identity/metadata only, never old weather, score, or explanation.
- Treat the route table, success status codes, error codes, CSRF exemptions, and history transaction rules in `SPEC.md` as exact contracts.
- All cross-user access tests must fail in the backend even if the frontend request is forged.
- Every task follows red-green-refactor and ends with a focused commit.

---

## File Map

- `backend/src/roambot/config.py`: non-secret database/data-path and cookie settings.
- `backend/src/roambot/persistence/database.py`: SQLAlchemy engine/session factory.
- `backend/src/roambot/persistence/tables.py`: database schema.
- `backend/src/roambot/persistence/repositories.py`: user/session/place/favorite/history/share/cache repositories.
- `backend/alembic/`: schema migrations.
- `backend/src/roambot/security/passwords.py`: Argon2 password hashing.
- `backend/src/roambot/security/sessions.py`: opaque token generation and hashing.
- `backend/src/roambot/security/vault.py`: credential file format and encryption.
- `backend/src/roambot/services/auth.py`: registration/login/logout/current-session use cases.
- `backend/src/roambot/services/personal_data.py`: favorites/history/share ownership logic.
- `backend/src/roambot/api/routes/auth.py`: account endpoints and cookie lifecycle.
- `backend/src/roambot/api/routes/favorites.py`: favorite endpoints.
- `backend/src/roambot/api/routes/history.py`: history list/detail/rerun/delete/clear.
- `backend/src/roambot/api/routes/shares.py`: create/revoke/public share.
- `backend/src/roambot/cli.py`: local administrator commands.

### Task 1: SQLite Schema and Migration

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/roambot/config.py`
- Create: `backend/src/roambot/persistence/__init__.py`
- Create: `backend/src/roambot/persistence/database.py`
- Create: `backend/src/roambot/persistence/tables.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/__init__.py`
- Create: `backend/alembic/versions/0001_accounts_and_data.py`
- Test: `backend/tests/integration/test_database.py`

**Interfaces:**
- Produces: `Settings`, `make_sqlite_url(path)`, `create_engine_and_session_factory(path)`, `initialize_schema(engine)`, SQLAlchemy table classes, and migration revision `0001`.

- [ ] **Step 1: Add persistence dependencies**

Add to runtime dependencies in `backend/pyproject.toml`:

```toml
  "alembic>=1.16,<2",
  "pydantic-settings>=2.10,<3",
  "sqlalchemy>=2.0,<2.1",
```

Run `./.venv/Scripts/python.exe -m pip install -e "./backend[dev]"` and expect exit 0.

- [ ] **Step 2: Write migration tests**

Create `backend/tests/integration/test_database.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from roambot.persistence.database import make_sqlite_url


BUSINESS_TABLES = {
    "api_cache",
    "favorites",
    "histories",
    "places",
    "shares",
    "user_sessions",
    "users",
}


def test_upgrade_head_is_repeatable_and_creates_exact_schema(tmp_path: Path) -> None:
    url = make_sqlite_url(tmp_path / "test.db")
    config = Config("backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    inspector = inspect(create_engine(url))
    tables = set(inspector.get_table_names())
    assert tables == BUSINESS_TABLES | {"alembic_version"}
    assert {fk["referred_table"] for fk in inspector.get_foreign_keys("shares")} == {
        "histories",
        "users",
    }
    assert any(
        set(item["column_names"]) == {"provider", "provider_place_id"}
        for item in inspector.get_unique_constraints("places")
    )
```

- [ ] **Step 3: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/integration/test_database.py -q`.

Expected: import failure for `roambot.persistence.database`.

- [ ] **Step 4: Implement settings, engine, and tables**

Create `Settings` with these non-secret fields and defaults:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAMBOT_", extra="ignore")
    data_dir: Path = Path("data")
    database_name: str = "roambot.db"
    secure_cookies: bool = False
    session_hours: int = 24

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name
```

Use SQLAlchemy declarative mappings with the exact column types, nullability, foreign-key cascades, unique constraints, and indexes in SPEC section 8. In particular:

- `users`: `id`, `username`, `password_hash`, `created_at`.
- `user_sessions`: `id`, `user_id`, `token_hash`, `csrf_hash`, `expires_at`, `revoked_at`.
- `places`: `id`, `provider`, `provider_place_id`, `name`, `address`, `city`, `longitude`, `latitude`, `type_name`, `type_code`, `scenery_tags_json`, `updated_at`.
- `favorites`: `id`, `user_id`, `place_id`, `created_at`.
- `histories`: `id`, `user_id`, `mode`, `request_json`, `result_json`, `created_at`.
- `shares`: `id`, `owner_user_id`, `history_id`, `token_hash`, `created_at`, `revoked_at`.
- `api_cache`: `cache_key`, `provider`, `operation`, `payload_json`, `created_at`, `expires_at`.

`make_sqlite_url(path)` returns the absolute `sqlite+pysqlite:///...` URL. `create_engine_and_session_factory(path)` creates parent directories, sets SQLite `check_same_thread=False`, and installs a connection hook for `PRAGMA foreign_keys=ON`. UUIDs are application-generated lowercase strings; repository helpers normalize all datetimes to UTC and treat SQLite's timezone-less return values as UTC. JSON is canonical `Text`, never pickle. `initialize_schema(engine)` may call `Base.metadata.create_all(engine)` for repository unit tests, but the first integration test must exercise Alembic. `backend/alembic.ini` uses `script_location=%(here)s/alembic` and leaves `sqlalchemy.url` empty; `env.py` uses an injected nonblank URL first, otherwise `Settings().database_path`.

- [ ] **Step 5: Verify migration behavior**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/integration/test_database.py -q
$env:ROAMBOT_DATA_DIR = Join-Path ([System.IO.Path]::GetTempPath()) ("roambot-migration-" + [guid]::NewGuid())
./.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
Remove-Item Env:ROAMBOT_DATA_DIR
```

Expected: test passes and migration exits 0 using a temporary configured data path, not the user's production file.

- [ ] **Step 6: Commit**

```powershell
git add backend/pyproject.toml backend/src/roambot/config.py backend/src/roambot/persistence backend/alembic.ini backend/alembic backend/tests/integration/test_database.py
git commit -m "feat: add SQLite schema and migration"
```

### Task 2: Passwords, Opaque Sessions, and CSRF

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/roambot/security/__init__.py`
- Create: `backend/src/roambot/security/passwords.py`
- Create: `backend/src/roambot/security/sessions.py`
- Test: `backend/tests/unit/test_security.py`

**Interfaces:**
- Produces: `hash_password`, `verify_password`, `new_token`, `hash_token`, and `SessionSecrets`.

- [ ] **Step 1: Add Argon2 dependency**

Add `"argon2-cffi>=25,<26"` to runtime dependencies and reinstall editable backend.

- [ ] **Step 2: Write security tests**

```python
from roambot.security.passwords import hash_password, verify_password
from roambot.security.sessions import SessionSecrets, hash_token


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")
    assert "correct horse" not in encoded
    assert verify_password(encoded, "correct horse battery staple") is True
    assert verify_password(encoded, "wrong") is False


def test_session_secrets_store_only_hashes() -> None:
    secrets = SessionSecrets.create()
    assert secrets.session_token != secrets.session_hash
    assert secrets.csrf_token != secrets.csrf_hash
    assert hash_token(secrets.session_token) == secrets.session_hash
    assert hash_token(secrets.csrf_token) == secrets.csrf_hash
```

- [ ] **Step 3: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_security.py -q`.

Expected: import failure.

- [ ] **Step 4: Implement security helpers**

`passwords.py`:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return _hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False
```

`sessions.py`:

```python
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe


def new_token() -> str:
    return token_urlsafe(32)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionSecrets:
    session_token: str
    session_hash: str
    csrf_token: str
    csrf_hash: str

    @classmethod
    def create(cls) -> "SessionSecrets":
        session_token = new_token()
        csrf_token = new_token()
        return cls(session_token, hash_token(session_token), csrf_token, hash_token(csrf_token))
```

- [ ] **Step 5: Verify and commit**

Run tests and Ruff; expect all pass. Then:

```powershell
git add backend/pyproject.toml backend/src/roambot/security backend/tests/unit/test_security.py
git commit -m "feat: secure passwords and session secrets"
```

### Task 3: Repositories and Authentication Service

**Files:**
- Create: `backend/src/roambot/persistence/repositories.py`
- Create: `backend/src/roambot/services/auth.py`
- Test: `backend/tests/integration/test_auth_service.py`

**Interfaces:**
- Produces: `AuthService.register`, `.login`, `.authenticate`, `.rotate_csrf`, `.logout`, typed `SessionGrant`, and typed `AuthenticatedSession`.

- [ ] **Step 1: Write integration tests**

Tests must use a fresh temporary SQLite database and assert:

```python
def test_register_hashes_password_and_rejects_duplicate_username() -> None:
    service, session_factory = auth_fixture()
    grant = service.register("alice_01", "correct horse battery staple")
    with session_factory() as db:
        stored = db.get(UserTable, grant.user_id)
        assert stored is not None
        assert stored.password_hash != "correct horse battery staple"
        assert grant.session_token not in db.scalar(select(UserSessionTable.token_hash))
        assert grant.csrf_token not in db.scalar(select(UserSessionTable.csrf_hash))
    with pytest.raises(AuthError, match="username already exists"):
        service.register("alice_01", "another valid password")


def test_login_authenticate_and_logout_session() -> None:
    service, _ = auth_fixture()
    service.register("alice_01", "correct horse battery staple")
    logged_in = service.login("alice_01", "correct horse battery staple")
    assert service.authenticate(logged_in.session_token).username == "alice_01"
    before = service.authenticate(logged_in.session_token)
    new_csrf = service.rotate_csrf(logged_in.session_token)
    after = service.authenticate(logged_in.session_token)
    assert after.csrf_hash == hash_token(new_csrf)
    assert after.csrf_hash != before.csrf_hash
    assert after.expires_at == before.expires_at
    service.logout(logged_in.session_token)
    with pytest.raises(AuthError, match="invalid session"):
        service.authenticate(logged_in.session_token)
```

Implement `auth_fixture()` in `backend/tests/conftest.py`, not as production code.

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/integration/test_auth_service.py -q`.

Expected: imports fail.

- [ ] **Step 3: Implement repositories**

Create focused repository classes using a supplied `sessionmaker[Session]`:

- `UserRepository.create/get_by_username/get_by_id`.
- `SessionRepository.create/get_active_by_hash/replace_csrf_hash/revoke_by_hash`.
- Convert `IntegrityError` on username uniqueness into `DuplicateUsernameError` and roll back.
- Store UUID values as lowercase strings and UTC timestamps as timezone-aware datetimes.

- [ ] **Step 4: Implement authentication service**

Use username rule `^[A-Za-z0-9_]{3,32}$` and password length 8-128. A successful `register` creates the user and initial session in one transaction, so registration is automatic login. `register` and `login` return `SessionGrant(user_id, username, session_token, csrf_token, expires_at)`; expiry is fixed at creation time plus 24 hours. `login` must return the same generic `AuthError("invalid credentials")` for unknown username and wrong password. `authenticate(session_token)` must reject revoked or expired sessions and return `AuthenticatedSession(session_id, user_id, username, csrf_hash, expires_at)` with no plaintext token. `rotate_csrf(session_token)` generates a new plaintext token, atomically replaces only the active row's hash, leaves `expires_at` unchanged, and returns the new plaintext once. Only the service boundary handles plaintext tokens; repositories and logs never receive them.

- [ ] **Step 5: Verify and commit**

Run integration tests and Ruff. Then:

```powershell
git add backend/src/roambot/persistence/repositories.py backend/src/roambot/services/auth.py backend/tests/conftest.py backend/tests/integration/test_auth_service.py
git commit -m "feat: add local account and session service"
```

### Task 4: Authentication API, Cookie, and CSRF Enforcement

**Files:**
- Create: `backend/src/roambot/api/routes/auth.py`
- Modify: `backend/src/roambot/api/dependencies.py`
- Modify: `backend/src/roambot/main.py`
- Test: `backend/tests/api/test_auth.py`

**Interfaces:**
- Produces: `/api/v1/auth/register`, `/login`, `/logout`, `/me`; cookie `roambot_session`; header `X-CSRF-Token`.

- [ ] **Step 1: Write API security tests**

Assert these exact contracts:

- Register auto-logs in and returns 201 with `{"user":{"username":"alice_01"},"csrf_token":"<opaque>"}`.
- Login returns 200 with the same JSON shape.
- Both set `roambot_session` with `HttpOnly`, `SameSite=lax`, `Path=/`, and `Max-Age=86400`; production config adds `Secure`.
- `/me` returns the same JSON shape for a valid session, atomically replaces `csrf_hash`, invalidates the prior CSRF value, does not extend session expiry, and sends `Cache-Control: no-store`.
- Logout without `X-CSRF-Token`, or with a wrong token, returns 403 `csrf_invalid`.
- Successful logout clears the cookie and the old cookie no longer authenticates.
- Duplicate registration returns 409 `username_taken`; login always returns the same 401 `invalid_credentials` for unknown username and wrong password.
- Successful logout returns 204 with an empty body; `/me` without a valid session returns 401 `authentication_required`.

- [ ] **Step 2: Run and observe 404**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_auth.py -q`.

Expected: auth routes return 404.

- [ ] **Step 3: Implement auth dependencies and routes**

Create dependencies:

- `get_optional_session()` reads and hashes `roambot_session`; returns `None` when absent and raises 401 when invalid.
- `require_session()` converts absence to 401 `authentication_required`.
- `require_csrf()` hashes `X-CSRF-Token` and compares with the active session using `secrets.compare_digest`; missing or mismatch returns 403 `csrf_invalid`.
- `GET /auth/me` calls `rotate_csrf` after authentication and returns the one-time plaintext token. All auth success responses set `Cache-Control: no-store`.

Set cookies using:

```python
response.set_cookie(
    key="roambot_session",
    value=authenticated.session_token,
    httponly=True,
    secure=settings.secure_cookies,
    samesite="lax",
    max_age=settings.session_hours * 3600,
    path="/",
)
```

Keep session expiry fixed at 24 hours; `/me` never slides it. Clear with the same path, SameSite, and Secure settings. Do not expose session token in JSON.

- [ ] **Step 4: Verify and commit**

Run auth API tests, all existing tests, and Ruff. Then commit:

```powershell
git add backend/src/roambot/api backend/src/roambot/main.py backend/tests/api/test_auth.py
git commit -m "feat: expose secure account API"
```

### Task 5: Favorites and Place Metadata

**Files:**
- Extend: `backend/src/roambot/persistence/repositories.py`
- Extend: `backend/src/roambot/services/personal_data.py`
- Create: `backend/src/roambot/api/routes/favorites.py`
- Test: `backend/tests/api/test_favorites.py`

**Interfaces:**
- Produces: `GET /api/v1/favorites`, `POST /api/v1/favorites`, `DELETE /api/v1/favorites/{favorite_id}`.

- [ ] **Step 1: Write ownership and semantics tests**

Test login helpers must create Alice and Bob. Assert:

- Guest GET/POST/DELETE returns 401.
- Alice can favorite a `Destination` snapshot and receives 201.
- Repeating the same provider/provider ID returns 200 with the same favorite ID.
- Favorite JSON includes place metadata and `created_at`, but contains no weather, score, or explanation keys.
- Bob cannot delete Alice's favorite and receives 404, not 403, to avoid resource enumeration.

- [ ] **Step 2: Run and observe 404**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_favorites.py -q`.

- [ ] **Step 3: Implement favorite repository/service/routes**

- Upsert `places` by `(provider, provider_place_id)` from a validated `Destination`.
- Insert favorite by `(user_id, place_id)` and return the existing row on duplicate.
- List only rows joined to the current user.
- Delete using both `favorite_id` and `user_id` in the repository predicate.
- Require session + CSRF for POST/DELETE; GET requires session only.

- [ ] **Step 4: Verify and commit**

Run favorite tests, full backend tests, Ruff, then commit `feat: add private place favorites`.

### Task 6: History Capture, Rerun, Delete, and Clear

**Files:**
- Extend: `backend/src/roambot/persistence/repositories.py`
- Extend: `backend/src/roambot/services/personal_data.py`
- Modify: `backend/src/roambot/api/routes/recommendations.py`
- Create: `backend/src/roambot/api/routes/history.py`
- Test: `backend/tests/api/test_history.py`

**Interfaces:**
- Produces: `GET /api/v1/history`, `GET/DELETE /api/v1/history/{id}`, `POST /api/v1/history/{id}/rerun`, `DELETE /api/v1/history`.

- [ ] **Step 1: Write history tests**

Assert:

- Guest successful core requests create no history.
- Logged-in successful requests create one immutable snapshot after the result is complete.
- A logged-in core POST without a valid `X-CSRF-Token` returns 403 before provider work; the same payload without a session remains a valid guest request.
- Validation/provider failures create no history.
- Complete responses using fresh cache, demo mode, straight-line distance, partial-candidate weather exclusion, or template explanations create history with their source notices.
- History list is newest first and excludes full external responses, credentials, cookies, and CSRF tokens.
- Rerun invokes current recommendation service, creates a new history ID, and leaves the old JSON unchanged.
- Alice cannot read/delete/rerun Bob's history.
- Single delete and clear remove only the current user's histories and do not remove favorites.

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_history.py -q`.

- [ ] **Step 3: Implement capture and history routes**

- Core route receives optional authenticated session.
- Serialize the validated request and structured response only after success.
- Call external providers outside any database transaction. Open a short transaction only after a complete response exists; commit the history before returning 200, and roll back plus return 500 if persistence fails.
- Store `mode` as `recommendation` or `place_evaluation`.
- Never store headers, cookies, raw provider payloads, passwords, or credential status.
- Rerun deserializes through the current Pydantic request type, calls the service, then persists a new snapshot.
- All mutations require CSRF.

- [ ] **Step 4: Verify and commit**

Run history tests, full backend tests, Ruff, then commit `feat: persist private recommendation history`.

### Task 7: Anonymous Read-Only Shares and Delete Invalidation

**Files:**
- Extend: `backend/src/roambot/persistence/repositories.py`
- Extend: `backend/src/roambot/services/personal_data.py`
- Create: `backend/src/roambot/api/routes/shares.py`
- Modify: `backend/src/roambot/api/routes/history.py`
- Test: `backend/tests/api/test_shares.py`

**Interfaces:**
- Produces: `POST /api/v1/history/{id}/share`, `DELETE /api/v1/shares/{id}`, `GET /api/v1/public/shares/{token}`.
- Produces private create JSON `{"share":{"id","history_id","url","created_at"}}` and public `{"snapshot":{...}}` exactly as specified in root SPEC.

- [ ] **Step 1: Write share security tests**

Assert:

- Only the history owner can create/revoke a share.
- Create returns plaintext token exactly once inside relative `url`; database stores only SHA-256 hash. Repeating create revokes the prior active share and returns a new 201 link; the prior public link immediately fails.
- Anonymous public response contains only mode, city, dates, companion count, generated time, and item destination/weather/daily suitability/scores/explanation fields from the fixed SPEC shape.
- Public response deletes main/companion origin strings completely and excludes username, user ID, session/CSRF tokens, and internal share/history IDs.
- Revoked share and share whose history was deleted both return the same 404 `share_unavailable`.

- [ ] **Step 2: Run and observe 404**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_shares.py -q`.

- [ ] **Step 3: Implement share lifecycle**

- Generate 32-byte URL-safe token; store only `hash_token(token)`. In one transaction revoke any active share for the same owner/history before inserting the replacement.
- Redact `main_origin` and `companion_origins` from the public request summary.
- Public GET does not return owner identifiers or database primary keys; the authenticated create response may return its own share/history IDs for later revoke UI.
- When deleting/clearing history, revoke related shares in the same database transaction before deleting history.
- Public GET never calls recommendation, weather, map, or LLM providers.

- [ ] **Step 4: Verify and commit**

Run share/history tests, full backend tests, Ruff, then commit `feat: share sanitized history snapshots`.

### Task 8: Persistent Provider Cache Repository

**Files:**
- Extend: `backend/src/roambot/persistence/repositories.py`
- Test: `backend/tests/integration/test_cache_repository.py`

**Interfaces:**
- Produces: `CacheEntry(cache_key:str,provider:str,operation:str,payload_json:str,created_at:datetime,expires_at:datetime)`, `CacheRepository.get_fresh(cache_key:str,now:datetime)->CacheEntry|None`, `.put(cache_key,provider,operation,payload_json,created_at,expires_at)->None`, `.delete(cache_key)->None`, `.delete_expired(now)->int`.

- [ ] **Step 1: Write expiry and isolation tests**

Use a fixed aware-UTC clock. Assert fresh JSON is returned only while `now < expires_at`, `None` at/after expiry, upsert replaces provider/operation/payload/timestamps atomically, deleting one key affects no other row, and deleting expired rows returns its count without deleting fresh rows. Naive datetimes are rejected before SQL.

- [ ] **Step 2: Implement cache repository**

Store the already-computed 64-hex cache key and serialize payload with stable `json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`. The provider wrapper in milestone 4 computes the key from provider + operation + normalized parameters; the repository never receives credentials or raw request parameters.

- [ ] **Step 3: Verify and commit**

Run cache tests/full tests/Ruff, then commit `feat: persist expiring provider cache`.

### Task 9: Encrypted Credential Vault and Local Admin CLI

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/roambot/security/vault.py`
- Create: `backend/src/roambot/cli.py`
- Test: `backend/tests/unit/test_vault.py`
- Test: `backend/tests/integration/test_credentials_cli.py`

**Interfaces:**
- Produces: `CredentialVault.create/unlock/update/clear/reset` and the `credentials init|status|set|clear|reset` CLI command group.

- [ ] **Step 1: Add cryptography and CLI dependencies**

Add:

```toml
  "cryptography>=45,<47",
  "typer>=0.16,<1",
```

Add project script:

```toml
[project.scripts]
roambot = "roambot.cli:app"
```

Reinstall editable backend.

- [ ] **Step 2: Write vault tests**

Assert:

- Created file bytes contain none of the master password or three fake keys.
- Correct master password unlocks exact values; wrong password raises `VaultAuthenticationError` without partial data.
- With no vault, status reports all three booleans false without prompting. With an existing vault, status uses a hidden master-password prompt, authenticates and decrypts all-or-nothing, then reports only configured booleans.
- Update and normal clear require current master password.
- Reset requires exact confirmation phrase `RESET-CREDENTIALS` and removes only the vault file, not a sibling SQLite file.
- CLI uses hidden prompts; command output never contains supplied values.

- [ ] **Step 3: Run and observe failure**

Run vault and CLI tests; expect import failures.

- [ ] **Step 4: Implement the authenticated file format**

Use this JSON envelope:

```json
{
  "version": 1,
  "kdf": {"name": "scrypt", "salt": "base64", "n": 32768, "r": 8, "p": 1},
  "cipher": {"name": "aes-256-gcm", "nonce": "base64", "ciphertext": "base64"}
}
```

Derive 32 bytes with `cryptography.hazmat.primitives.kdf.scrypt.Scrypt`, encrypt canonical UTF-8 JSON with `AESGCM`, and use `b"roambot-vault-v1"` as associated data. Write via temporary file then atomic `Path.replace`. Set restrictive file permissions where supported and document Windows ACL limitations.

Allowed plaintext fields are `amap_api_key`, `qweather_api_key`, and `llm_api_key`. QWeather API host, LLM base URL, and model remain non-secret settings.

- [ ] **Step 5: Implement Typer commands**

Commands:

```text
roambot credentials init
roambot credentials status
roambot credentials set amap
roambot credentials set qweather
roambot credentials set llm
roambot credentials clear amap|qweather|llm
roambot credentials reset
```

Use `typer.prompt("主密码", hide_input=True, confirmation_prompt=True)` when creating the master password and hidden non-echo prompts for keys. Existing-vault `status` authenticates through `CredentialVault.unlock` but prints only booleans and never retains or writes decrypted values after the command exits. `reset` requires host filesystem access and typed confirmation but never deletes SQLite.

- [ ] **Step 6: Verify and commit**

Run vault/CLI/full backend tests and Ruff. Then commit `feat: manage encrypted provider credentials`.

### Task 10: Milestone Verification

**Files:**
- Modify: `backend/README.md`
- Modify: `AGENT_LOG.md`

- [ ] **Step 1: Document account/data behavior**

Add migration commands, cookie/CSRF behavior, guest boundary, favorite/history/share semantics, and credential CLI commands. Explicitly state that no real key is needed yet.

- [ ] **Step 2: Run fresh verification**

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests -q
./.venv/Scripts/python.exe -m ruff check backend
git diff --check
```

Expected: zero failures/errors.

- [ ] **Step 3: Inspect for accidental secrets**

```powershell
rg -n "AIza|sk-[A-Za-z0-9]|X-QW-Api-Key|api_key\s*=\s*['\"][^'\"]+" . --glob '!docs/**' --glob '!backend/tests/fixtures/**'
```

Expected: no real-looking credentials; configuration field names alone are acceptable after manual inspection.

- [ ] **Step 4: Record and commit**

Record exact test count and manual interventions in `AGENT_LOG.md`, then commit `docs: record accounts and data verification`.

## Milestone Exit Criteria

- Guests still use both core endpoints without an account.
- Passwords use Argon2; opaque session/CSRF/share secrets are stored only as hashes.
- Every personal resource is isolated by backend ownership checks.
- History deletion invalidates shares and leaves favorites intact.
- The vault passes wrong-password, no-plaintext, status-redaction, and reset-isolation tests.
- Full backend pytest and Ruff pass without network access or real credentials.
