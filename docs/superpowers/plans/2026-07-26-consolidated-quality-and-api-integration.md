# RoamBot Consolidated Quality and API Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the accepted functional and interaction defects, then implement AMap input tips and reuse QWeather weather icons without broad visual redesign.

**Architecture:** Keep provider facts deterministic in the FastAPI backend and keep presentation state in the React application. Extend existing provider abstractions and API types instead of adding vendor SDKs. Preserve the current page structure; defer overall card imagery, color system, borders, and desktop composition to the later visual-design pass.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest, React, TypeScript, Vite, Vitest, Testing Library.

## Global Constraints

- Write a failing focused test before each production change and confirm the expected failure.
- Do not expose API keys, passwords, exact private origins, or session tokens to browser storage or logs.
- Do not add maps, route drawing, navigation, itinerary planning, SMS, or new vendor SDK dependencies.
- Keep real API calls out of automated tests; use existing fake HTTP/provider seams.
- Batch verification after each major backend/frontend group rather than after every small copy or CSS change.

---

### Task 1: Deterministic provider and recommendation correctness

**Files:**
- Modify: `backend/src/roambot/providers/amap.py`
- Modify: `backend/src/roambot/domain/scenery.py`
- Modify: `backend/src/roambot/domain/scenery_rules.py`
- Modify: `backend/src/roambot/domain/scoring.py`
- Modify: `backend/src/roambot/domain/ranking.py`
- Modify: `backend/src/roambot/services/recommendations.py`
- Test: `backend/tests/unit/test_amap_provider.py`
- Test: `backend/tests/unit/test_scenery.py`
- Test: `backend/tests/unit/test_scoring.py`
- Test: `backend/tests/unit/test_ranking.py`
- Test: `backend/tests/unit/test_recommendation_service.py`
- Test: `backend/tests/unit/test_explanation_provider.py`

- [ ] Add failing tests for city-hinted geocoding followed by unrestricted fallback, strict sea semantics, indoor heat wording, relative multi-origin burden, and partial LLM-group retry/fallback.
- [ ] Run the focused tests and confirm they fail for the missing behavior.
- [ ] Implement the smallest provider/domain/service changes that satisfy the accepted rules.
- [ ] Run the focused backend test group once and resolve regressions.

### Task 2: Stable search, history, authentication, and favorite interactions

**Files:**
- Modify: `frontend/src/features/search/SearchWorkspace.tsx`
- Modify: `frontend/src/features/search/TravelForm.tsx`
- Modify: `frontend/src/features/search/formState.ts`
- Modify: `frontend/src/features/history/HistoryList.tsx`
- Modify: `frontend/src/features/auth/AuthDialog.tsx`
- Modify: `frontend/src/features/auth/AuthProvider.tsx`
- Modify: `frontend/src/features/search/ResultCard.tsx`
- Modify: `frontend/src/features/favorites/FavoriteList.tsx`
- Modify: `frontend/src/styles/forms.css`
- Modify: `frontend/src/styles/personal.css`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Test: `frontend/tests/TravelForm.test.tsx`
- Test: `frontend/tests/AuthDialog.test.tsx`
- Test: `frontend/tests/PersonalPages.test.tsx`
- Test: `frontend/tests/ResultCard.test.tsx`

- [ ] Add failing tests for fixed validation-message space, query progress/locking, preserved in-tab drafts/results, immediate history rerun locking, generic login failures, auth-field clearing, success toasts, star favorite toggling, and navigable favorite cards.
- [ ] Run the focused frontend tests and confirm expected failures.
- [ ] Implement shared interaction state and minimal stable styling without redesigning the entire page.
- [ ] Run the focused frontend test group once and resolve regressions.

### Task 3: AMap input tips and coordinate reuse

**Files:**
- Modify: `backend/src/roambot/providers/protocols.py`
- Modify: `backend/src/roambot/providers/amap.py`
- Modify: `backend/src/roambot/providers/cached.py`
- Modify: `backend/src/roambot/api/routes/recommendations.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/features/search/OriginFields.tsx`
- Modify: `frontend/src/features/search/TravelForm.tsx`
- Test: `backend/tests/unit/test_amap_provider.py`
- Test: `backend/tests/api/test_recommendations.py`
- Test: `frontend/tests/TravelForm.test.tsx`
- Test: `frontend/tests/ApiClient.test.ts`

- [ ] Add failing backend and frontend tests for minimum input length, five-result limit, non-strict origin city preference, strict target-city lookup, debounce/stale-response handling, free-text fallback, and selected-coordinate invalidation after editing.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the input-tips endpoint and accessible combobox using existing HTTP utilities, with short caching and no vendor SDK.
- [ ] Run the focused provider/API/form tests once.

### Task 4: QWeather icon reuse and daily-card hierarchy

**Files:**
- Modify: `backend/src/roambot/domain/models.py`
- Modify: `backend/src/roambot/providers/qweather.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/features/search/DailyWeatherList.tsx`
- Modify: `frontend/src/styles/results.css`
- Test: `backend/tests/unit/test_qweather_provider.py`
- Test: `frontend/tests/ResultCard.test.tsx`

- [ ] Add failing tests proving day/night icon codes are parsed from the existing seven-day response and rendered with a readable weather, temperature, and advice hierarchy.
- [ ] Run the focused tests and confirm expected failures without any extra provider request.
- [ ] Extend the existing models and UI; keep two-to-seven day layouts stable and avoid the former `4 + 1` wrapping.
- [ ] Run the focused backend and frontend tests once.

### Task 5: Consolidated verification and manual regression handoff

**Files:**
- Modify: `DECISIONS.md` only if implementation differs from an accepted rule
- Modify: `docs/frontend-adjustments.md` to mark implemented interaction items while retaining deferred visual items
- Modify: `AGENT_LOG.md` with concise evidence required by the assignment

- [ ] Run the complete backend suite once.
- [ ] Run frontend tests, typecheck, and production build once.
- [ ] Run only the critical Playwright/browser flows for search, cross-city input, auth, history rerun, and favorite toggle.
- [ ] Produce a short manual regression list for the user; do not claim deferred visual redesign is complete.
