# Photo homepage implementation ledger

## 2026-10-08 Mobile clear photo follow-up

- User approved removal of both mobile blur and shade. Only max-width600px overlays are hidden; desktop layers and mobile layout stay unchanged.
- New browser RED: mobile blur still visible; desktop overlay retention passed. GREEN homepage/mobile-feedback checks18/18 (25.2s), full Vitest186/186 (32.32s), ESLint/tsc/build exit0. Isolated Mock8010/5180, separate .playwright-data/home-clear-20261008. No live providers, actual phones or full E2E rerun.
- Screenshot evidence/home-clear-mobile-chromium-20261008.png visually checked. Secondary white labels now have weak contrast against bright sky; user notified, text styling left unchanged within approved scope. No commit/push/deployment.

Plan: docs/superpowers/plans/2026-10-08-photo-home.md

- Pre-flight: Task 1 produces HomePage and optional AuthDialog initialMode; Task 2 routes those components; Task 3 exercises their public behavior. No interface conflict.
- Ruling: Work in the approved current experiment/ui-clean-a checkout, preserving previous uncommitted UI changes. A new clean worktree would omit those changes and test a different product. No dependency installation, commits, pushes or deployment.
- Ruling: Repository AGENTS forbids subagents; execute and review locally. Shell-oriented skill ledger scripts are replaced with this durable Windows-friendly ledger; no commits means preserve this record rather than delete it.
- Task 1: in progress. Frontend baseline running; tests first.
- Baseline: Vitest 26 files / 171 passed (22.50s).
- Task 1: complete. Auth initialMode RED (register button absent); initial homepage missing-module error replaced with minimal null scaffold, then 8 genuine missing-controls RED assertions. GREEN HomePage/AuthDialog 13 tests. First GREEN had a test selector ambiguity (output is also role=status); scoped status to main, no product workaround. Photo copied as 227680-byte JPEG, original unchanged.
- Task 2: in progress. AppShell navigation RED expected /recommend but href=/.
- Task 2: complete. Favorite/plan/history RED returned / instead of /recommend. Migrated explicit query routes and state-preserving backlinks. Updated old tests whose brand-reset expectation is intentionally superseded by brand-to-home without clearing results. History test waits for async rerun navigation rather than asserting before API completion. Full Vitest 28 files / 183 passed (23.32s), exit 0.
- Task 3: browser checks include guest/login row geometry, actual image loading, mobile label centering, registration/cancel/plans continuation, query reload and retained draft, 320px long account names, six desktop hover controls, 375px low-height delayed initialization, reduced motion and failed/guarded logout. Mock auth fixtures plus isolated Mock backend; no real provider calls.
- Browser iterations: initial 6/8 passed; two timeouts were a test-only incorrect close-button label (actual aria-label is 关闭). Next full suite 67/68: hover RED exposed real specificity bug. Width-specific RED measured 1425/1440 and 375/390, tracing to global stable scrollbar-gutter. Scoped html:has(.home-scene) resets gutter only on homepage. Button-specific 1.08 selectors now outrank generic 1.01. Extra delayed-session/logout checks 2/2 passed. Final full-suite result recorded below after completion.
- ESLint, tsc and final Vite build exit 0. Build: 1865 modules, JPEG227.68kB, CSS73.73kB, JS410.53kB. Frontend diff --check exit 0 (existing CRLF warnings only).
- Review: self-review under repository no-subagent rule, not independent review. Home auth uses existing provider/CSRF/dialog validation; credentials not persisted by homepage. Query route refresh exercised through Vite fallback. Deferred/outside scope: live provider, actual phone/touch hardware, production hosting fallback and new third-party integration; no claim of these validations. Work stays on current branch without commit/push/deployment.
- Final browser verification: system Edge, full Mock/demo suite 70/70 passed (2.1m), exit 0; includes 12 new homepage checks across desktop/mobile projects. Guest/logged screenshots on both viewports saved in docs/competition/evidence/photo-home-*-20261008.png and visually checked. Desktop1440/mobile390, narrow320 and low-height375 covered; real mobile devices not tested.
- Completion ruling: keep experiment/ui-clean-a and all existing changes in place, matching the approved no-commit/no-push plan. No merge menu or branch cleanup needed. New homepage only resets html gutter while present, so query form retains its original stable gutter. No unresolved self-review blockers.
- Cleanup: sent Ctrl+C to only this turn's backend/frontend sessions51250/43588. Both terminated; netstat found no listeners on8010/5180. Get-NetTCPConnection was denied (read-only check), so verified via netstat. User8000/5173 untouched. No data deleted.
