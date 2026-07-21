# Proportional Weight Bar and Match Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace linked weight sliders with one three-segment control, fix group fairness at 20%, and present internal scores as a user-facing trip match index with qualitative dimensions.

**Architecture:** Keep the backend `RankingWeights` wire contract, but introduce a frontend-only `DisplayWeights` value that always totals 100 across weather, distance, and popularity. A pure conversion function emits single-origin weights unchanged or group weights scaled to 80 plus fixed fairness 20. Result-card labeling remains a pure presentation concern over the existing numeric score breakdown.

**Tech Stack:** React 19, TypeScript 6, CSS, Vitest/Testing Library, Playwright, FastAPI/Pydantic, pytest.

## Global Constraints

- No new dependency and no real provider call.
- Display weights use integer 5% steps, permit zero, and total exactly 100.
- Group effective weights use `display * 0.8` plus `fairness=20`; single effective weights use `fairness=0`.
- Keep numeric scores in API/history data; remove score language and sub-score numbers only from user-facing cards.
- One concentrated review after all three tasks, matching the user's efficiency preference.

---

### Task 1: Display Weight Model and Fixed Fairness Contract

**Files:**
- Modify: `frontend/src/features/search/formState.ts`
- Modify: `frontend/src/features/search/TravelForm.tsx`
- Test: `frontend/tests/TravelForm.test.tsx`
- Modify: `backend/src/roambot/domain/models.py`
- Modify: `backend/src/roambot/services/recommendations.py`
- Test: `backend/tests/unit/test_models.py`
- Test: `backend/tests/unit/test_recommendation_service.py`

**Interfaces:**
- Produces: `DisplayWeights = { weather: number; distance: number; popularity: number }`.
- Produces: `toRankingWeights(display, originCount): RankingWeights`.
- Produces: defaults `displayWeights = {weather:40,distance:30,popularity:30}` and effective group defaults `{weather:32,distance:24,fairness:20,popularity:24}`.

- [ ] **Step 1: Write failing frontend submission and persistence tests**

Assert a single-origin submit emits `40/30/0/30`, adding a companion emits `32/24/20/24`, and the new storage key ignores the old four-weight record.

- [ ] **Step 2: Run focused frontend tests and observe RED**

Run: `node frontend/node_modules/vitest/vitest.mjs run frontend/tests/TravelForm.test.tsx`

- [ ] **Step 3: Implement the display model and conversion**

Use:

```ts
export type DisplayWeights = Pick<RankingWeights, 'weather' | 'distance' | 'popularity'>

export function toRankingWeights(value: DisplayWeights, originCount: 1 | 2 | 3): RankingWeights {
  return originCount === 1
    ? { ...value, fairness: 0 }
    : { weather: value.weather * 0.8, distance: value.distance * 0.8,
        fairness: 20, popularity: value.popularity * 0.8 }
}
```

Change storage to `roambot.ui.display-weights.v2` and validate exactly three non-negative integer values totaling 100.

- [ ] **Step 4: Write failing backend contract/default tests**

Assert multi-origin defaults equal `32/24/20/24`; explicit multi-origin weights reject fairness other than 20 or a non-100 total; single-origin still rejects nonzero fairness.

- [ ] **Step 5: Implement backend validation and defaults, then run focused suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_models.py backend/tests/unit/test_recommendation_service.py -q
node frontend/node_modules/vitest/vitest.mjs run frontend/tests/TravelForm.test.tsx
```

- [ ] **Step 6: Commit Task 1**

Commit: `feat: fix group fairness at twenty percent`

### Task 2: One Three-Segment Weight Bar

**Files:**
- Modify: `frontend/src/features/search/WeightSegments.tsx`
- Modify: `frontend/src/styles/forms.css`
- Create: `frontend/tests/WeightSegments.test.tsx`
- Modify: `frontend/tests/accessibility.test.tsx`

**Interfaces:**
- Consumes: `DisplayWeights` and `onChange(DisplayWeights)` from Task 1.
- Produces: two cumulative boundaries `[weather, weather + distance]`, converted back to three percentages.

- [ ] **Step 1: Write failing component tests**

Require exactly two slider handles, labels and percentages for three dimensions, 5% keyboard changes, no crossing, allowed overlap, reset, and total 100 after every change.

- [ ] **Step 2: Run the component tests and observe RED**

Run: `node frontend/node_modules/vitest/vitest.mjs run frontend/tests/WeightSegments.test.tsx`

- [ ] **Step 3: Implement cumulative-boundary helpers and the accessible control**

Use two `role="slider"` handles over one stable track. Pointer movement converts client X to 0–100, rounds to 5, clamps boundary 1 to `[0,boundary2]` and boundary 2 to `[boundary1,100]`; arrow keys move by 5. Render labels and values below the track so zero-width segments remain legible.

- [ ] **Step 4: Add responsive styling and verify component/accessibility tests**

Ensure a minimum 44px touch target, no negative/overlapping text layout, three fixed legend cells, and visible focus outlines.

- [ ] **Step 5: Commit Task 2**

Commit: `feat: replace weight sliders with proportion bar`

### Task 3: Trip Match Index Presentation and Final Verification

**Files:**
- Create: `frontend/src/features/search/matchLabels.ts`
- Modify: `frontend/src/features/search/ResultCard.tsx`
- Modify: `frontend/src/styles/results.css`
- Create: `frontend/tests/ResultCard.test.tsx`
- Modify: `frontend/e2e/guest-recommendation.spec.ts`
- Modify: `SPEC.md`
- Modify: `AGENT_LOG.md`

**Interfaces:**
- Produces: pure dimension label functions using thresholds `85/70/50`.
- Produces: integer “出游匹配指数”, qualitative dimension labels, and the fixed comparison disclaimer.

- [ ] **Step 1: Write failing result-card tests**

Assert the card shows `出游匹配指数`, rounded integer total, qualitative weather/distance/popularity labels, group-only balance label, and the disclaimer. Assert it does not render numeric sub-scores or the user-facing text `分项评分`/`总分`.

- [ ] **Step 2: Implement label helpers and card rendering**

Map thresholds exactly as the design table. Determine group mode from `item.distances.length > 1`; omit balance for single-origin results.

- [ ] **Step 3: Update the E2E expectation and documentation**

Keep all internal API fields unchanged. Record the fixed 20% rule and clarify that the index compares only candidates in the current query.

- [ ] **Step 4: Run one concentrated verification**

Run focused tests, full backend/frontend test/lint/type/build, Playwright desktop/mobile, `git diff --check`, and the existing secret scan. Rebuild `roambot:local`, replace only `roambot-check` while retaining `roambot-check-data`, and verify `/api/v1/health` before handoff.

- [ ] **Step 5: Commit and push after user-visible verification**

Commit: `feat: present trip match index`.

