# Railway Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish RoamBot at a stable HTTPS WebUI URL while preserving SQLite data, encrypted provider credentials, and the repository's non-root runtime boundary.

**Architecture:** Railway builds the existing root `Dockerfile`, exposes container port 8000, and mounts one persistent volume at `/data`. Railway starts the container as root only long enough for RoamBot to repair the mounted volume ownership; the Python entrypoint then drops to the existing `roambot` account before opening the database or serving requests. Railway stores only the vault master password as a sealed service variable; Amap, QWeather, and LLM keys remain inside `/data/credentials.vault` encrypted with AES-256-GCM.

**Tech Stack:** Docker, Python 3.13, FastAPI/Uvicorn, Railway, SQLite, pytest, GitHub Actions.

## Global Constraints

- Keep all provider API keys out of Git, logs, Docker image layers, browser code, and Railway service variables.
- Preserve the existing `/data` contract for `roambot.db`, cache data, and `credentials.vault`.
- The final application process must run as UID/GID 10001, even when Railway launches the image as root for volume initialization.
- Public deployment must use HTTPS and `ROAMBOT_SECURE_COOKIES=true`.
- Deployment evidence and documentation changes stay on `feat/roambot-v1` until a reviewed PR merges them into `main`.

---

### Task 1: Cloud-safe master-password resolution

**Files:**
- Modify: `backend/src/roambot/entrypoint.py`
- Test: `backend/tests/unit/test_entrypoint.py`

**Interfaces:**
- Consumes: `Settings.master_password_file` and the process environment.
- Produces: `resolve_master_password()` support for one-time `ROAMBOT_MASTER_PASSWORD` consumption without changing provider credential storage.

- [x] **Step 1: Write the failing test**

Add a test that sets `ROAMBOT_MASTER_PASSWORD`, calls `resolve_master_password()` with no password file and non-interactive stdin, then asserts that the returned value matches and the environment variable has been removed.

- [x] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_entrypoint.py -q`

Expected: FAIL because the current resolver ignores `ROAMBOT_MASTER_PASSWORD`.

- [x] **Step 3: Implement minimal behavior**

After the password-file branch and before the TTY branch, consume the sealed value with `os.environ.pop("ROAMBOT_MASTER_PASSWORD", None)`, reject blank content, and return the nonblank value.

- [x] **Step 4: Run focused tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_entrypoint.py -q`

Expected: PASS.

### Task 2: Railway volume ownership and privilege drop

**Files:**
- Modify: `backend/src/roambot/entrypoint.py`
- Test: `backend/tests/unit/test_entrypoint.py`
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: `Settings.data_dir`, POSIX root status, and the existing `roambot` account.
- Produces: `prepare_runtime_identity(settings: Settings) -> None`, which owns `/data` as UID/GID 10001 and drops privileges before vault/database access.

- [x] **Step 1: Write failing tests**

Add tests showing that non-root execution is a no-op and that root execution changes the data tree owner before calling `initgroups`, `setgid`, and `setuid` in that order.

- [x] **Step 2: Verify failure**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_entrypoint.py -q`

Expected: FAIL because `prepare_runtime_identity` does not exist.

- [x] **Step 3: Implement the helper**

On POSIX root execution, create the data directory, recursively change its ownership to the `roambot` account, then call `initgroups`, `setgid`, and `setuid`. Call the helper immediately after settings validation and before reading the master password, credential vault, or database.

- [x] **Step 4: Keep the image user declaration**

Retain `USER roambot` in `Dockerfile`. Railway will set `RAILWAY_RUN_UID=0` only for its launcher; the application entrypoint restores UID/GID 10001 itself.

- [x] **Step 5: Run focused tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_entrypoint.py -q`

Expected: PASS.

### Task 3: Container verification

**Files:**
- Verify: `Dockerfile`
- Verify: `docker-compose.yml`

**Interfaces:**
- Consumes: the production image and an isolated Docker volume.
- Produces: evidence that normal Mock startup and Railway-style root startup both serve `/api/v1/health` while the Python process runs as UID 10001.

- [x] **Step 1: Run backend quality gates**

Run Ruff and the backend test suite using the repository's existing test script.

- [x] **Step 2: Build the production image**

Run: `docker build -t roambot:railway-check .`

- [x] **Step 3: Verify ordinary Mock startup**

Run the image with its default user, Mock mode, and a new temporary volume; verify `/api/v1/health` returns HTTP 200.

- [x] **Step 4: Verify Railway-style startup**

Run the same image with UID 0 and a new root-owned volume; verify `/api/v1/health` returns HTTP 200 and inspect the server process UID as 10001.

### Task 4: Railway project and public verification

**Files:**
- Modify after verified facts exist: `README.md`
- Modify after verified facts exist: `TASKS.md`
- Modify after verified facts exist: `AGENT_LOG.md`
- Modify after verified facts exist: `docs/evidence/verification.md`

**Interfaces:**
- Consumes: GitHub branch `feat/roambot-v1`, the production Dockerfile, the encrypted local vault, and user-owned Railway/provider accounts.
- Produces: an HTTPS WebUI URL and reproducible deployment evidence.

- [ ] **Step 1: Create the Railway service from GitHub**

Connect `TheOwl060218/RoamBot`, choose `feat/roambot-v1`, let Railway detect the root `Dockerfile`, and configure target port 8000.

- [ ] **Step 2: Attach persistent storage**

Attach one Railway volume at `/data` and set `RAILWAY_RUN_UID=0` so the entrypoint can establish volume ownership before dropping privileges.

- [ ] **Step 3: Deploy in Mock mode**

Set `ROAMBOT_PROVIDER_MODE=mock`, `ROAMBOT_DEMO_MODE=true`, and `ROAMBOT_SECURE_COOKIES=true`; generate a Railway domain and verify the health endpoint and WebUI.

- [ ] **Step 4: Upload encrypted credentials**

Upload only `credentials.vault` to `/data`. Store its master password as the sealed `ROAMBOT_MASTER_PASSWORD` Railway variable; never paste provider keys into Railway or chat.

- [ ] **Step 5: Switch to Live mode**

Set `ROAMBOT_PROVIDER_MODE=live`, `ROAMBOT_DEMO_MODE=false`, the account-specific QWeather HTTPS host, LLM HTTPS base URL, and LLM model. Redeploy and verify one bounded real recommendation.

- [ ] **Step 6: Run public acceptance**

Verify registration/login, recommendation, favorite/history persistence after restart, anonymous share in a private browser, responsive mobile layout, health endpoint, and redacted logs.

- [ ] **Step 7: Record only observed facts**

Add the final URL, deployed commit SHA, architecture, CI/CD flow, cost boundary, and acceptance evidence to the four documentation files listed above.

- [ ] **Step 8: Finish through PR**

Run the complete local gate, commit and push `feat/roambot-v1`, create a GitHub PR to `main`, wait for CI success, then merge without deleting the feature branch.
