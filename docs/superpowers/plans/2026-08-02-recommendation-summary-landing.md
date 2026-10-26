# Recommendation Summary Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End a successful recommendation at the compact current-query summary with a 20 px desktop gap or 12 px mobile gap before the results.

**Architecture:** Keep the existing result-first animation and form-collapse compensation, then schedule a post-layout scroll to `controlsRef` after `QuerySummary` exists. Hide the empty message reservation in summary mode and calculate scroll offset from the rendered sticky header height.

**Tech Stack:** React 19, TypeScript, CSS, Vitest, Playwright

## Global Constraints

- The summary card lands 16 px below the sticky header.
- Desktop summary-to-results gap is 20 px; mobile gap is 12 px.
- Do not add floating controls, instructional toasts, dependencies, or API changes.
- Preserve the existing smooth `修改条件` transition.

---

### Task 1: Land on the compact query summary

**Files:**
- Modify: `frontend/src/features/search/SearchWorkspace.tsx`
- Modify: `frontend/src/features/search/scrolling.ts`
- Modify: `frontend/src/styles/results.css`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Test: `frontend/tests/scrolling.test.ts`
- Test: `frontend/e2e/responsive-layout.spec.ts`

**Interfaces:**
- Consumes: `startSmoothScrollTo(getTarget, onComplete?)` and the existing `controlsRef`/`resultsRef` elements.
- Produces: a post-collapse summary landing and a header-aware scroll offset without changing component props or API types.

- [ ] **Step 1: Write failing interaction and layout tests**

Add a SearchWorkspace assertion that the post-submit flow schedules a second scroll after `editingConditions` becomes false. Extend the responsive Playwright test with:

```ts
const gap = results!.y - (summary!.y + summary!.height)
expect(gap).toBeCloseTo(viewport!.width <= 600 ? 12 : 20, 0)

const header = await page.locator('.shell-header').boundingBox()
expect(summary!.y).toBeCloseTo(header!.height + 16, 0)
```

- [ ] **Step 2: Run tests and verify the current behavior fails**

Run:

```powershell
vitest run tests/SearchWorkspace.test.tsx tests/scrolling.test.ts
playwright test responsive-layout
```

Expected: the summary landing or compact-gap assertion fails because scrolling stops at `resultsRef` and the empty message slot remains in layout.

- [ ] **Step 3: Implement the post-layout landing**

In `SearchWorkspace`, record a `controls` post-layout target before collapsing the form. After the collapse layout effect preserves the result position, start `startSmoothScrollTo(() => controlsRef.current)` so the final viewport includes the summary and edit action.

Render the message slot with a collapsed modifier:

```tsx
<div className={`workspace-message-slot${editingConditions ? '' : ' workspace-message-slot-collapsed'}`}>
```

- [ ] **Step 4: Implement compact spacing and dynamic header offset**

Use exact responsive gaps and remove the empty collapsed slot from grid layout:

```css
.search-workspace { gap: 20px; }
.workspace-message-slot-collapsed:empty { display: none; }

@media (max-width: 600px) {
  .search-workspace { gap: 12px; }
}
```

Calculate the scrolling offset from `.shell-header` and add 16 px, with the existing 76 px value as fallback when no header exists.

- [ ] **Step 5: Run focused and browser verification**

Run:

```powershell
vitest run tests/SearchWorkspace.test.tsx tests/scrolling.test.ts
playwright test responsive-layout
vite build
```

Expected: tests pass on desktop and mobile; the summary is visible below the sticky header, the result follows with the exact responsive gap, and both scroll directions remain smooth.

- [ ] **Step 6: Commit the implementation**

```powershell
git add frontend/src/features/search/SearchWorkspace.tsx frontend/src/features/search/scrolling.ts frontend/src/styles/results.css frontend/tests/SearchWorkspace.test.tsx frontend/tests/scrolling.test.ts frontend/e2e/responsive-layout.spec.ts docs/superpowers/plans/2026-08-02-recommendation-summary-landing.md
git commit -m "improve recommendation summary landing"
```
