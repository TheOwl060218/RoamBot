# Unified Frontend Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild RoamBot's frontend into a consistent lake-blue, responsive experience with desktop list-detail workspaces, mobile candidate navigation, compact history rows, and usable favorite details while preserving all existing product behavior.

**Architecture:** Keep the current React, React Router, and API boundaries. Split result comparison from full place details, store only UI selection and form-collapse state locally, and reuse the same detail renderer in live results and history snapshots. CSS remains organized by semantic tokens plus page-level styles; no new styling or component dependency is introduced.

**Tech Stack:** React 19, TypeScript 6, React Router 7, TanStack Query, Lucide React, CSS, Vitest, Testing Library, Playwright, Python/FastAPI/Pydantic backend tests.

## Global Constraints

- Do not add location images, maps, navigation, route drawing, itinerary planning, new third-party APIs, or new frontend dependencies.
- Keep the existing recommendation algorithm, score formula, Provider budgets, loading progress mechanism, and toast mechanism unchanged.
- Use `#176F8A` as the lake-blue brand color; the match index remains lake blue at every value.
- Use positive green, caution amber, and danger brick red only with an icon or explicit text label.
- Text and icon-text buttons are pill-shaped; icon-only buttons are circular; information containers keep 6-8px radii.
- All buttons implement default, hover, pressed, focus-visible, loading, and disabled states without layout shifts.
- Desktop list-detail mode begins at 1024px; narrower viewports use normal document scrolling and mobile candidate navigation.
- Multi-day weather never uses horizontal scrolling on mobile.
- Suitable-day copy is concise; caution and not-recommended copy may explain risk and alternatives.
- Existing dirty worktree changes are user-owned. Stage only files intentionally included in each task and never revert unrelated changes.
- Run targeted tests after each task, then one consolidated build, lint, unit, E2E, and visual pass at the end.

---

## File Structure

### New focused components

- `frontend/src/features/search/QuerySummary.tsx`: collapsed query facts and “修改条件”.
- `frontend/src/features/search/CandidateList.tsx`: comparable candidate rows for desktop and initial mobile view.
- `frontend/src/features/search/PlaceDetail.tsx`: one selected destination's full details.
- `frontend/src/features/search/MobileCandidateSwitcher.tsx`: sticky previous/current/next selector.
- `frontend/src/features/search/CandidateDrawer.tsx`: accessible mobile candidate sheet.
- `frontend/src/features/history/HistoryActionsMenu.tsx`: history overflow actions and share states.
- `frontend/src/features/favorites/FavoriteDetail.tsx`: read-only favorite facts and evaluation action.

### Existing files with changed responsibilities

- `SearchWorkspace.tsx`: request state, form collapse, selected candidate, favorite state.
- `ResultList.tsx`: result heading, notices, and responsive list-detail composition.
- `ResultCard.tsx`: removed after its detail markup moves into `PlaceDetail.tsx`.
- `DailyWeatherList.tsx`: single-day panel and multi-day rows.
- `HistoryList.tsx`: compact clickable rows.
- `FavoriteList.tsx`: selectable compact favorites rather than large action cards.
- `tokens.css`, `forms.css`, `app.css`, `results.css`, `personal.css`, `auth.css`: semantic visual system and responsive layout.

---

### Task 1: Lake-Blue Visual Foundation and Button Contract

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/forms.css`
- Modify: `frontend/src/styles/app.css`
- Modify: `frontend/src/styles/auth.css`
- Modify: `frontend/src/styles/personal.css`
- Test: `frontend/e2e/guest-recommendation.spec.ts`

**Interfaces:**
- Consumes: existing classes `.primary-button`, `.text-button`, `.icon-text-button`, `.icon-button`, `.danger-button`, `.account-button`.
- Produces: semantic CSS variables and a shared pressed-state contract used by every later task.

- [ ] **Step 1: Extend the existing Playwright flow with visual-system assertions**

Add assertions after the recommendation form loads:

```ts
const submit = page.getByRole('button', { name: '开始推荐' })
await expect(submit).toHaveCSS('border-radius', '999px')
await expect(page.locator('.brand-mark')).toHaveCSS('background-color', 'rgb(23, 111, 138)')
```

- [ ] **Step 2: Run the focused E2E test and confirm the old green theme fails**

Run: `npm run e2e -- guest-recommendation.spec.ts`

Expected: FAIL on the brand color and pill radius assertions.

- [ ] **Step 3: Replace visual tokens and centralize button states**

Define the approved token roles in `tokens.css`, then make all button families use:

```css
transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease, transform 100ms ease;
```

Use `border-radius: 999px` for text buttons, `border-radius: 50%` for icon buttons, and this shared pressed rule without changing layout:

```css
.primary-button:active:not(:disabled),
.text-button:active:not(:disabled),
.icon-text-button:active:not(:disabled),
.icon-button:active:not(:disabled),
.danger-button:active:not(:disabled),
.account-button:active:not(:disabled) {
  transform: scale(0.98);
}
```

Update navigation, dialogs, inputs, toast typography, and focus colors to use the same tokens. Do not change loading or toast control flow.

- [ ] **Step 4: Run the focused E2E test and frontend build**

Run: `npm run e2e -- guest-recommendation.spec.ts`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit the visual foundation**

```bash
git add frontend/src/styles/tokens.css frontend/src/styles/forms.css frontend/src/styles/app.css frontend/src/styles/auth.css frontend/src/styles/personal.css frontend/e2e/guest-recommendation.spec.ts
git commit -m "style: establish lake-blue interface system"
```

### Task 2: Risk-Aware Weather Copy and Daily Layout

**Files:**
- Modify: `backend/src/roambot/domain/scoring.py`
- Modify: `backend/tests/unit/test_scoring.py`
- Modify: `frontend/src/features/search/DailyWeatherList.tsx`
- Modify: `frontend/src/styles/results.css`
- Modify: `frontend/tests/ResultCard.test.tsx`

**Interfaces:**
- Consumes: `DailySuitability.status`, `DailySuitability.summary`, and `DailyWeather[]`.
- Produces: concise `suitable` summaries, explanatory caution/danger summaries, `weather-list-single`, and `weather-list-multi` variants.

- [ ] **Step 1: Change backend tests to require concise suitable indoor copy**

Replace the old indoor expectation with:

```py
assert "室内参观受高温影响较小" not in result.summary
assert "往返途中" in result.summary
assert "防暑" in result.summary or "防晒" in result.summary
```

Add a caution/not-recommended assertion that the summary retains the date, factual weather risk, and actionable advice.

- [ ] **Step 2: Run the focused backend test and confirm failure**

Run: `python -m pytest backend/tests/unit/test_scoring.py -q`

Expected: FAIL because the old indoor explanation remains.

- [ ] **Step 3: Update weather summary generation without changing suitability scores**

In `scoring.py`, keep all numeric score and threshold logic unchanged. For suitable indoor heat, emit only the actionable travel clause, for example:

```py
reasons.append("往返途中注意防暑防晒")
```

Keep caution and not-recommended branches factual and explanatory.

- [ ] **Step 4: Write frontend tests for single-day and multi-day structures**

Assert that one day uses `weather-list-single`, multiple days use `weather-list-multi`, dates are Chinese, temperature has the “温度” label, and all conditions render a Lucide icon.

- [ ] **Step 5: Run the frontend test and confirm the old grid fails**

Run: `npm test -- ResultCard.test.tsx`

Expected: FAIL on the new single/multi class and row structure.

- [ ] **Step 6: Implement single-day panel and multi-day rows**

Make `DailyWeatherList` choose a stable variant:

```tsx
const variant = weather.length === 1 ? 'single' : 'multi'
return <div className={`weather-list weather-list-${variant}`}>...</div>
```

Multi-day rows use normal vertical flow on mobile and never `overflow-x: auto`. Preserve icons, Chinese dates, status text, and summaries.

- [ ] **Step 7: Run focused backend and frontend tests**

Run: `python -m pytest backend/tests/unit/test_scoring.py -q`

Expected: PASS.

Run: `npm test -- ResultCard.test.tsx`

Expected: PASS.

- [ ] **Step 8: Commit weather copy and presentation**

```bash
git add backend/src/roambot/domain/scoring.py backend/tests/unit/test_scoring.py frontend/src/features/search/DailyWeatherList.tsx frontend/src/styles/results.css frontend/tests/ResultCard.test.tsx
git commit -m "feat: clarify daily weather guidance"
```

### Task 3: Desktop Query Summary and List-Detail Results

**Files:**
- Create: `frontend/src/features/search/QuerySummary.tsx`
- Create: `frontend/src/features/search/CandidateList.tsx`
- Create: `frontend/src/features/search/PlaceDetail.tsx`
- Modify: `frontend/src/features/search/SearchWorkspace.tsx`
- Modify: `frontend/src/features/search/ResultList.tsx`
- Delete: `frontend/src/features/search/ResultCard.tsx`
- Modify: `frontend/src/features/search/TravelForm.tsx`
- Modify: `frontend/src/features/search/formState.ts`
- Modify: `frontend/src/styles/results.css`
- Modify: `frontend/src/styles/forms.css`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Rename/Modify: `frontend/tests/ResultCard.test.tsx` to `frontend/tests/PlaceDetail.test.tsx`

**Interfaces:**
- `QuerySummary({ draft, onEdit })` renders submitted conditions.
- `CandidateList({ items, selectedId, onSelect })` renders compact comparison rows.
- `PlaceDetail({ item, onFavorite, isFavorite, favoritePending })` renders one complete destination.
- `ResultList` receives `selectedId` and `onSelect`; it no longer renders all full details.
- `formState.ts` adds `loadSelectedPlaceId()` and `saveSelectedPlaceId(id: string)` using session storage.

- [ ] **Step 1: Write failing workspace tests**

Cover these behaviors:

```tsx
expect(screen.getByRole('button', { name: '修改条件' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: /苏州博物馆/ })).toHaveAttribute('aria-current', 'true')
await user.click(screen.getByRole('button', { name: /金鸡湖景区/ }))
expect(screen.getByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
```

Also assert a single full `PlaceDetail` is rendered and the form reopens in place.

- [ ] **Step 2: Run focused tests and confirm the current full-card list fails**

Run: `npm test -- SearchWorkspace.test.tsx ResultCard.test.tsx`

Expected: FAIL because the form stays expanded and every item renders a full card.

- [ ] **Step 3: Extract `PlaceDetail` and candidate summaries**

Move the current full-card markup into `PlaceDetail.tsx`. Build compact candidate buttons with rank, name, tags, fixed lake-blue index, distance, rating, and weather status. Keep the full data source notice above the list-detail workspace.

- [ ] **Step 4: Add selected-item and form-collapse state**

In `SearchWorkspace`:

```ts
const [selectedId, setSelectedId] = useState(() => loadSelectedPlaceId())
const [editingConditions, setEditingConditions] = useState(() => result === null)
```

After a successful query, select the first item, save its ID, and collapse the form. When loaded selection is missing, fall back to the first item. `QuerySummary` uses the latest `TravelFormDraft` and `onEdit` only toggles the existing form.

- [ ] **Step 5: Implement desktop equal-height workspace styles**

At `>=1024px`, use a constrained results viewport with candidate and detail panes. Both panes receive `min-height: 0` and independent `overflow-y: auto`. Do not apply this internal scrolling below 1024px.

- [ ] **Step 6: Run focused tests and build**

Run: `npm test -- SearchWorkspace.test.tsx PlaceDetail.test.tsx TravelForm.test.tsx`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 7: Commit desktop results workspace**

```bash
git add frontend/src/features/search frontend/src/styles/results.css frontend/src/styles/forms.css frontend/tests/SearchWorkspace.test.tsx frontend/tests/PlaceDetail.test.tsx frontend/tests/TravelForm.test.tsx
git commit -m "feat: add desktop result comparison workspace"
```

### Task 4: Mobile Candidate Switcher and Drawer

**Files:**
- Create: `frontend/src/features/search/MobileCandidateSwitcher.tsx`
- Create: `frontend/src/features/search/CandidateDrawer.tsx`
- Modify: `frontend/src/features/search/ResultList.tsx`
- Modify: `frontend/src/styles/results.css`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Test: `frontend/e2e/guest-recommendation.spec.ts`

**Interfaces:**
- `MobileCandidateSwitcher({ items, selectedId, onSelect, onOpenDrawer, visible })` provides previous/next navigation.
- `CandidateDrawer({ open, items, selectedId, onSelect, onClose })` provides a modal candidate list with focus management.
- `ResultList` owns an `IntersectionObserver` sentinel for the initial candidate list and passes visibility to the switcher.

- [ ] **Step 1: Write failing mobile component tests**

Mock `IntersectionObserver`, mark the candidate list as outside the viewport, and assert:

```tsx
expect(screen.getByRole('button', { name: '上一个地点' })).toBeInTheDocument()
await user.click(screen.getByRole('button', { name: /1\/5/ }))
expect(screen.getByRole('dialog', { name: '选择候选地点' })).toBeInTheDocument()
```

Assert choosing a drawer item changes the detail without scrolling the document to the original list.

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `npm test -- SearchWorkspace.test.tsx`

Expected: FAIL because no switcher or candidate drawer exists.

- [ ] **Step 3: Implement the sticky switcher**

Keep the original list in document flow. Observe a sentinel after it and show the switcher only below 1024px when the list is above the viewport. Previous and next wrap only within list bounds and disable at the ends.

- [ ] **Step 4: Implement the accessible bottom drawer**

The drawer uses `role="dialog"`, `aria-modal="true"`, Esc close, backdrop close, focus entry, focus restoration, and body scroll locking. Selecting a candidate closes the drawer and calls `onSelect` without `scrollIntoView`.

- [ ] **Step 5: Add a mobile Playwright path**

At `390 x 844`, query, scroll the initial candidate list away, switch destination, open the drawer, choose another destination, and assert the selected heading changes.

- [ ] **Step 6: Run component and E2E tests**

Run: `npm test -- SearchWorkspace.test.tsx`

Expected: PASS.

Run: `npm run e2e -- guest-recommendation.spec.ts`

Expected: PASS.

- [ ] **Step 7: Commit mobile navigation**

```bash
git add frontend/src/features/search/MobileCandidateSwitcher.tsx frontend/src/features/search/CandidateDrawer.tsx frontend/src/features/search/ResultList.tsx frontend/src/styles/results.css frontend/tests/SearchWorkspace.test.tsx frontend/e2e/guest-recommendation.spec.ts
git commit -m "feat: add mobile candidate navigation"
```

### Task 5: Compact History Rows and Overflow Actions

**Files:**
- Create: `frontend/src/features/history/HistoryActionsMenu.tsx`
- Modify: `frontend/src/features/history/HistoryList.tsx`
- Modify: `frontend/src/features/history/ShareActions.tsx`
- Modify: `frontend/src/pages/HistoryPage.tsx`
- Modify: `frontend/src/styles/personal.css`
- Test: `frontend/tests/PersonalPages.test.tsx`

**Interfaces:**
- `HistoryActionsMenu({ historyId, shareState, rerunning, onRerun, onDelete })` owns the `···` menu.
- The history row is a single navigation target; menu clicks stop propagation.
- Existing confirmation and request-lock callbacks remain owned by `HistoryPage`.

- [ ] **Step 1: Write failing history interaction tests**

Assert compact row text, whole-row history link, one overflow button per row, hidden secondary actions before opening, and visible requery/share/delete actions after opening.

- [ ] **Step 2: Run the focused personal-page test**

Run: `npm test -- PersonalPages.test.tsx`

Expected: FAIL because actions are currently all visible.

- [ ] **Step 3: Implement compact rows and menu behavior**

Use semantic row columns for type/city, dates/count, saved time, and overflow. The overflow menu supports outside click, Esc, focus movement, and destructive styling. Keep current share creation, copy, revoke, requery lock, and confirmation behavior.

- [ ] **Step 4: Add responsive row styles**

Desktop columns align across records. Below 700px, each row becomes a two-line summary with overflow on the right; no action wraps to a new uncontrolled row.

- [ ] **Step 5: Run focused tests and build**

Run: `npm test -- PersonalPages.test.tsx ConfirmDialog.test.tsx`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 6: Commit history redesign**

```bash
git add frontend/src/features/history frontend/src/pages/HistoryPage.tsx frontend/src/styles/personal.css frontend/tests/PersonalPages.test.tsx frontend/tests/ConfirmDialog.test.tsx
git commit -m "feat: streamline history actions"
```

### Task 6: Favorite List-Detail Workspace

**Files:**
- Create: `frontend/src/features/favorites/FavoriteDetail.tsx`
- Modify: `frontend/src/features/favorites/FavoriteList.tsx`
- Modify: `frontend/src/pages/FavoritesPage.tsx`
- Modify: `frontend/src/styles/personal.css`
- Test: `frontend/tests/PersonalPages.test.tsx`
- Test: `frontend/e2e/account-personal-data.spec.ts`

**Interfaces:**
- `FavoriteList({ favorites, selectedId, onSelect })` renders compact selectable rows.
- `FavoriteDetail({ favorite, onRemove })` renders existing place facts and the evaluation link.
- `FavoritesPage` owns `selectedId`, delete state, empty state, and mobile list/detail navigation.

- [ ] **Step 1: Write failing favorite workspace tests**

Assert the first favorite is selected by default, clicking a second row replaces the detail, the selected row uses `aria-current`, and the detail contains rating source, address, star toggle, and “重新评估”.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `npm test -- PersonalPages.test.tsx`

Expected: FAIL because favorites currently render as independent cards without details.

- [ ] **Step 3: Implement desktop favorite list-detail layout**

Default to the first available favorite. After deletion, select the next item or previous item; when none remain, show a full-width empty state. Use only fields already present on `Favorite.place`; do not request new data.

- [ ] **Step 4: Implement mobile list-to-detail flow**

Below 1024px, selecting a favorite switches to the detail view. A back button returns to the list and restores the saved list scroll offset.

- [ ] **Step 5: Run component and account E2E tests**

Run: `npm test -- PersonalPages.test.tsx`

Expected: PASS.

Run: `npm run e2e -- account-personal-data.spec.ts`

Expected: PASS.

- [ ] **Step 6: Commit favorite workspace**

```bash
git add frontend/src/features/favorites frontend/src/pages/FavoritesPage.tsx frontend/src/styles/personal.css frontend/tests/PersonalPages.test.tsx frontend/e2e/account-personal-data.spec.ts
git commit -m "feat: add favorite detail workspace"
```

### Task 7: Consolidated Responsive, Accessibility, and Regression Pass

**Files:**
- Modify: `frontend/src/styles/app.css`
- Modify: `frontend/src/styles/forms.css`
- Modify: `frontend/src/styles/results.css`
- Modify: `frontend/src/styles/personal.css`
- Modify: `frontend/src/styles/auth.css`
- Modify: `frontend/e2e/guest-recommendation.spec.ts`
- Modify: `frontend/e2e/account-personal-data.spec.ts`
- Modify: `docs/frontend-adjustments.md`

**Interfaces:**
- Consumes every component and CSS contract from Tasks 1-6.
- Produces verified layouts at the five required viewport sizes and an updated work log that marks superseded visual items complete.

- [ ] **Step 1: Add final E2E assertions for high-risk layouts**

Cover seven candidates, seven days, long place names, multi-origin results, no rating, field error stability, empty history, empty favorites, dialogs, and pressed button state. Use canvas/screenshot inspection only for visual properties not reliable in JSDOM.

- [ ] **Step 2: Run the full frontend unit suite**

Run: `npm test`

Expected: PASS with no unhandled promise or accessibility warnings.

- [ ] **Step 3: Run backend tests affected by copy and API compatibility**

Run: `python -m pytest backend/tests/unit/test_scoring.py backend/tests/api/test_recommendations.py backend/tests/api/test_history.py backend/tests/api/test_shares.py -q`

Expected: PASS.

- [ ] **Step 4: Run lint and production build**

Run: `npm run lint`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Run full Playwright workflows**

Run: `npm run e2e`

Expected: PASS for guest, account, history, share, and favorite flows.

- [ ] **Step 6: Perform one concentrated visual review**

Capture and inspect `1920x1080`, `1440x900`, `1024x768`, `390x844`, and `360x800`. Verify no blank panes, overflow, overlap, horizontal weather scroll, layout jump, clipped focus outline, or unreadable muted text. Verify pressed state with pointer down before pointer up.

- [ ] **Step 7: Update the frontend adjustment record**

Mark the unified layout, lake-blue theme, weather rows, history, favorites, and button-state items implemented. Record that images remain explicitly deferred and that this design supersedes older image and green-theme notes.

- [ ] **Step 8: Commit final polish and evidence**

```bash
git add frontend/src/styles frontend/e2e docs/frontend-adjustments.md
git commit -m "test: verify unified responsive experience"
```

## Execution Order and Review Gates

Execute Tasks 1-4 as the first major block, then perform one focused functional check of recommendation and mobile switching. Execute Tasks 5-6 as the second block, then check history and favorites. Task 7 is the only full-suite and full visual review. Do not dispatch separate review agents for individual CSS edits.
