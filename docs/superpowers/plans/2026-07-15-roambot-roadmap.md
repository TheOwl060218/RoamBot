# RoamBot Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this roadmap plan-by-plan. Each child plan contains checkbox (`- [ ]`) steps for tracking.

**Goal:** Deliver the approved RoamBot responsive Web application as four reviewable, testable milestones.

**Architecture:** React + TypeScript + Vite consumes `/api/v1` JSON endpoints from FastAPI. The backend owns deterministic recommendation logic, authentication, SQLite persistence, encrypted provider credentials, external API adapters, and authorization. Development runs frontend and backend separately; production packages both in one Docker image.

**Tech Stack:** Python >=3.12,<3.14 (local 3.12.13; Docker/CI 3.13), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, React, TypeScript, Vite, Vitest, Playwright, SQLite, Docker, GitLab CI.

## Global Constraints

- Work from the approved design: `docs/plans/2026-07-15-roambot-design.md`.
- V1 is a responsive Web application; do not implement a WeChat mini-program.
- Do not render maps, routes, navigation, or day-by-day itineraries.
- Guests may recommend and evaluate; favorites, history, and share management require login.
- V1 uses username and password only; do not collect phone numbers or add SMS/Web CAPTCHA services.
- Never place real provider credentials in chat, source, `.env`, Git, logs, SQLite business tables, Docker layers, tests, or CI.
- Automated tests and CI must use mock providers and make zero real provider requests.
- Keep scoring, scenery classification, authorization, and privacy rules in the backend only.
- Use TDD for every behavior: failing test, observed failure, minimal implementation, passing test, focused commit.
- Do not proceed to a later milestone until the current milestone's complete verification command passes.

---

## Execution Order

1. `2026-07-15-roambot-01-core-backend.md`
2. `2026-07-15-roambot-02-accounts-and-data.md`
3. `2026-07-15-roambot-03-react-webui.md`
4. `2026-07-15-roambot-04-providers-and-delivery.md`

## Milestone Deliverables

### Milestone 1: Core Backend

Produces a runnable FastAPI service with mock geocoding, POI, distance, weather, and LLM providers. Both public core endpoints work without login. Domain scoring, scenery mapping, multi-origin fairness, deterministic explanations, source-state metadata, and structured errors are covered by pytest.

Verification:

```powershell
python -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q
```

### Milestone 2: Accounts and Data

Adds SQLite/Alembic, Argon2 password hashing, server-side sessions, HttpOnly cookies, CSRF protection, favorites, history, anonymous shares, cache persistence, and the encrypted credential-vault CLI. Core public endpoints remain usable by guests.

Verification:

```powershell
python -m pytest backend/tests -q
```

### Milestone 3: React WebUI

Adds the responsive V1 interface, typed API client, recommendation/evaluation forms, normalized weight control, result cards, auth, favorites, history, shares, source/degradation states, Vitest coverage, and Playwright browser flows.

Verification:

```powershell
./scripts/test.ps1
```

### Milestone 4: Providers and Delivery

Adds real AMap, QWeather, and OpenAI-compatible adapters behind existing protocols; provider budgets, cache/degradation policy, manual smoke command, single-image Docker delivery, GitLab CI, README, and final evidence. Real credentials are requested only before the manual smoke task.

Verification:

```powershell
./scripts/test.ps1
docker build -t roambot:local .
docker run --rm -d --name roambot-check -p 8000:8000 -v roambot-check-data:/data roambot:local
```

Then verify `http://localhost:8000/api/v1/health` returns HTTP 200 and remove only the temporary `roambot-check` container. Do not delete a user data volume without explicit approval.

## Locked File Structure

```text
RoamBot/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── src/roambot/
│   │   ├── main.py                 # FastAPI app factory and static SPA hosting
│   │   ├── config.py               # Non-secret settings only
│   │   ├── cli.py                  # Admin credentials and smoke commands
│   │   ├── api/
│   │   │   ├── dependencies.py     # Request-scoped services/current user/CSRF
│   │   │   ├── errors.py           # Stable public error envelope
│   │   │   └── routes/             # health/auth/recommendations/favorites/history/shares
│   │   ├── domain/
│   │   │   ├── models.py           # Provider-independent Pydantic/domain types
│   │   │   ├── scenery.py          # POI-to-RoamBot deterministic tags
│   │   │   ├── scoring.py          # Weather, distance, fairness, popularity
│   │   │   └── ranking.py          # Hard filters, coverage penalty, final ordering
│   │   ├── providers/
│   │   │   ├── protocols.py        # Provider interfaces
│   │   │   ├── mock.py             # Deterministic demo/test providers
│   │   │   ├── factory.py          # Mock/live provider assembly
│   │   │   ├── http.py             # Sanitized HTTP boundary
│   │   │   ├── budget.py           # Request-local call limits
│   │   │   ├── cached.py           # Fresh persistent-cache wrappers
│   │   │   ├── amap.py             # AMap Web Service adapter
│   │   │   ├── qweather.py         # QWeather API v7 adapter
│   │   │   └── openai_compatible.py # OpenAI-compatible explanation adapter
│   │   ├── services/
│   │   │   ├── recommendations.py  # Core orchestration
│   │   │   ├── auth.py             # Registration/session lifecycle
│   │   │   └── personal_data.py    # Favorites/history/share use cases
│   │   ├── persistence/
│   │   │   ├── database.py         # Engine/session lifecycle
│   │   │   ├── tables.py           # SQLAlchemy tables
│   │   │   └── repositories.py     # Persistence boundaries
│   │   └── security/
│   │       ├── passwords.py        # Argon2 hashing
│   │       ├── sessions.py         # Random tokens and hashes
│   │       └── vault.py            # Scrypt + AES-GCM credential vault
│   └── tests/
│       ├── unit/
│       ├── api/
│       ├── integration/
│       └── fixtures/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/                     # Router, shell, query client
│   │   ├── api/                     # Typed JSON client and contracts
│   │   ├── features/                # search/auth/favorites/history/shares
│   │   ├── pages/                   # Route-level composition
│   │   └── styles/                  # Tokens, layout, responsive behavior
│   └── tests/
├── e2e/
├── scripts/
│   ├── test.ps1
│   └── test.sh
├── Dockerfile
├── Makefile
└── .gitlab-ci.yml
```

## Cross-Plan Interfaces

- Core service entry points:
  - `RecommendationService.recommend(request: RecommendationRequest) -> RecommendationResponse`
  - `RecommendationService.evaluate(request: PlaceEvaluationRequest) -> PlaceEvaluationResponse`
- API endpoints:
  - `POST /api/v1/recommendations`
  - `POST /api/v1/place-evaluations`
  - `/api/v1/auth/*`, `/api/v1/favorites`, `/api/v1/history/*`, `/api/v1/shares/*`
  - `GET /api/v1/public/shares/{token}`
- Session cookie name: `roambot_session`.
- State-changing requests after login require `X-CSRF-Token`.
- Every recommendation response includes `source_state` with `live`, `cache`, `demo`, or `degraded` values and user-visible notices.
- External adapters implement protocols from `backend/src/roambot/providers/protocols.py`; services never import concrete provider classes.
- Frontend consumes API contracts from `frontend/src/api/types.ts`; contract fixtures are verified against FastAPI responses.

## Review Gates

At each milestone:

1. Run the milestone verification command from a clean process.
2. Run `git diff --check`.
3. Review changed files against the approved design and this roadmap.
4. Confirm no real key or realistic-looking secret appears in Git diff.
5. Commit only the milestone's files with the commit messages specified in the child plan.
