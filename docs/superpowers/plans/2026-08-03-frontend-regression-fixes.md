# Frontend Regression Fixes Plan

**Goal:** Finish the confirmed result, favorite, history, and public-share layout fixes without changing recommendation behavior.

**Scope:** Frontend components, styles, and focused unit/E2E regression tests only.

## 1. Results Workspace

- Add regression coverage for adaptive candidate height, scroll chaining, the mobile match grid, and weather-column spacing.
- Remove the fixed seven-row visual reservation while retaining a capped independently scrollable candidate list.
- Let wheel input chain to the page at an inner pane boundary.
- Keep three match facts on one row except on genuinely narrow screens, where they stack in one column.

## 2. Favorite Interaction

- Add regression coverage for a visible guest favorite action and login-dialog handoff.
- Keep the favorite control visible for guests and open the existing account dialog when used.
- Restyle the selected favorite action and align favorite-detail actions to the lower right.

## 3. History And Public Share

- Add regression coverage for share feedback, menu containment, stable detail actions, and mobile share layout.
- Open desktop history actions inward within the current row; use a mobile bottom action sheet without reflowing later rows.
- Route share results to the page toast and keep detail-page action width stable.
- Reflow public share cards into a readable single-column mobile layout.

## 4. Verification

- Run focused Vitest suites after each implementation batch.
- Run the frontend build and the affected Playwright specs.
- Recheck only the changed desktop/mobile paths in the browser.
