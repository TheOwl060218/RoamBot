# RoamBot React WebUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved responsive V1 interface for guest recommendations, specified-place evaluation, accounts, favorites, history, and anonymous shares.

**Architecture:** React Router composes route-level pages, TanStack Query owns server state, and a small typed fetch client owns cookies/CSRF/error decoding. Feature folders own forms and views. Business scoring and authorization never run in the frontend; the UI renders backend contracts and non-sensitive local preferences only.

**Tech Stack:** Node.js 24 LTS, React 19.2, TypeScript, Vite 8, React Router, TanStack Query, Lucide React, Vitest, Testing Library, Playwright 1.61.

## Global Constraints

- Complete and verify plans 01 and 02 first; run the backend with deterministic mock providers during frontend work.
- First screen is the actual recommendation tool, not a marketing landing page.
- Do not add a map, route, navigation, itinerary, phone, SMS, CAPTCHA, OAuth, email, or password recovery UI.
- Use icons from Lucide for icon buttons and provide tooltips/accessible names.
- Cards have at most 8px radius; do not nest cards inside cards or float whole page sections as cards.
- Do not use gradients, decorative orbs, oversized hero text, negative letter spacing, or viewport-scaled font sizes.
- Desktop layout is input/results side by side; mobile layout is stacked and must have no overlap.
- Browser storage may contain only non-sensitive UI preferences such as weights; cookies are managed by the browser and private data stays server-side.
- Every task follows red-green-refactor and ends with a focused commit.

---

## File Map

- `frontend/src/app/router.tsx`: route tree.
- `frontend/src/app/AppShell.tsx`: top navigation and account menu.
- `frontend/src/app/queryClient.ts`: TanStack Query configuration.
- `frontend/src/api/types.ts`: API request/response contracts.
- `frontend/src/api/client.ts`: credentialed fetch, CSRF, structured errors.
- `frontend/src/features/search/`: mode form, origins, scenery, dates, weights, result cards.
- `frontend/src/features/auth/`: auth state and login/register UI.
- `frontend/src/features/favorites/`: favorite list and re-evaluate action.
- `frontend/src/features/history/`: snapshots, rerun, delete, clear, share.
- `frontend/src/features/shares/`: public snapshot view.
- `frontend/src/pages/`: route compositions only.
- `frontend/src/styles/`: design tokens, app shell, forms, results, responsive rules.
- `frontend/tests/`: Vitest/Testing Library tests.
- `e2e/`: Playwright user journeys and viewport checks.

### Task 1: Vite Project, Test Harness, and App Shell

**Files:**
- Create: `frontend/package.json` and generated `frontend/package-lock.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/eslint.config.js`
- Create: `frontend/src/vite-env.d.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/pages/PlaceholderPage.tsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/app.css`
- Create: `frontend/tests/setup.ts`
- Test: `frontend/tests/AppShell.test.tsx`

**Interfaces:**
- Produces: `AppShell({ children }: PropsWithChildren)`, placeholder routes `/`, `/favorites`, `/history`, `/share/:token`, and navigation labels 推荐/收藏/历史. Tasks 4-6 replace placeholder route elements; Task 1 does not implement the travel form.

- [ ] **Step 1: Verify Node**

Run:

```powershell
node --version
npm --version
```

Expected: Node `v24.x`. If missing, stop and ask the user to approve installing Node.js 24 LTS.

- [ ] **Step 2: Scaffold and install dependencies**

```powershell
npm create vite@latest frontend -- --template react-ts
Set-Location frontend
npm install
npm install react-router-dom @tanstack/react-query lucide-react
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @playwright/test
Set-Location ..
```

Expected: `frontend/package-lock.json` exists and commands exit 0. Do not hand-edit lock versions.

Add scripts to `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  }
}
```

Keep all standard Vite template entry and TypeScript/ESLint files listed above. Configure Vitest in `vite.config.ts` with `environment: "jsdom"`, `setupFiles: "./tests/setup.ts"`, and Vite proxy `/api` to `http://127.0.0.1:8000`.

- [ ] **Step 3: Write the failing shell test**

```tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppShell } from '../src/app/AppShell';

test('shows product navigation and usable main content', () => {
  render(
    <MemoryRouter>
      <AppShell><div>推荐表单</div></AppShell>
    </MemoryRouter>,
  );

  expect(screen.getByRole('link', { name: 'RoamBot' })).toBeVisible();
  expect(screen.getByRole('link', { name: '推荐' })).toBeVisible();
  expect(screen.getByRole('link', { name: '收藏' })).toBeVisible();
  expect(screen.getByRole('link', { name: '历史' })).toBeVisible();
  expect(screen.getByText('推荐表单')).toBeVisible();
});
```

- [ ] **Step 4: Run and observe failure**

Run `npm --prefix frontend test -- AppShell.test.tsx`.

Expected: import failure for `AppShell`.

- [ ] **Step 5: Implement the shell and restrained visual foundation**

Use semantic `header`, `nav`, and `main`. The shell header contains brand, three navigation links, and a guest-state account button with `UserRound` icon and `aria-label="账户"`; Task 5 replaces its guest action with the completed authentication flow.

`AppShell` renders `children` inside `main`. `router.tsx` temporarily uses `PlaceholderPage` with short headings for recommendation, favorites, history, and public share. Do not render inputs or `开始推荐` yet; Task 3 creates the form and Task 4 connects it as the final `/` workspace. The milestone exit criteria, not this scaffold task, enforce the final immediately usable first screen.

Define exact base tokens:

```css
:root {
  color: #17201d;
  background: #f4f7f5;
  font-family: Inter, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-synthesis: none;
  --surface: #ffffff;
  --surface-muted: #edf2ef;
  --ink: #17201d;
  --muted: #65726d;
  --border: #d8e0dc;
  --primary: #176b52;
  --primary-hover: #115640;
  --accent: #b94f35;
  --warning: #9a651c;
  --danger: #a43a3a;
  --radius: 6px;
}

* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; min-height: 100vh; }
button, input, select, textarea { font: inherit; }
:focus-visible { outline: 3px solid #79b8a3; outline-offset: 2px; }
```

No gradients or decorative background elements.

- [ ] **Step 6: Verify and commit**

Run frontend test, build, and lint; expect all exit 0. Commit `build: initialize React WebUI`.

### Task 2: Typed API Client and Auth State

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/app/queryClient.ts`
- Create: `frontend/src/features/auth/AuthProvider.tsx`
- Test: `frontend/tests/apiClient.test.ts`
- Test: `frontend/tests/AuthProvider.test.tsx`

**Interfaces:**
- Produces: `api.get/post/delete`, `ApiError`, `AuthProvider`, `useAuth()`, and TypeScript shapes matching FastAPI.

- [ ] **Step 1: Define exact frontend API contracts**

Mirror backend enums and response fields in `types.ts`. Include `RecommendationRequest`, `PlaceEvaluationRequest`, `RecommendationResponse`, `PlaceEvaluationResponse`, `RecommendationItem`, `SourceState`, `User`, `Favorite`, `HistorySummary`, `HistoryDetail`, and `PublicShare`. Do not add frontend-only score calculations.

- [ ] **Step 2: Write client tests with mocked fetch**

```ts
import { api, ApiError, setCsrfToken } from '../src/api/client';

test('sends cookies and csrf on mutations', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
  setCsrfToken('csrf-test');

  await api.post('/favorites', { provider_id: 'demo:lake' });

  expect(fetchMock).toHaveBeenCalledWith('/api/v1/favorites', expect.objectContaining({
    credentials: 'include',
    headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-test' }),
  }));
});

test('decodes the stable backend error envelope', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ error: { code: 'validation_error', message: '输入有误', fields: [] } }),
    { status: 422, headers: { 'Content-Type': 'application/json' } },
  )));

  await expect(api.get('/bad')).rejects.toEqual(expect.objectContaining<ApiError>({
    code: 'validation_error',
    status: 422,
  }));
});
```

- [ ] **Step 3: Implement client behavior**

- Prefix every path with `/api/v1`.
- Set `credentials: "include"`.
- Send `Content-Type: application/json` only when a body exists.
- Hold CSRF token in module memory only; never use localStorage/sessionStorage.
- On 204 return `undefined`; on structured errors throw `ApiError`; on malformed errors throw `ApiError("unexpected_error", "服务返回了无法识别的数据")` without exposing response internals.
- For mutations only, a 403 `csrf_invalid` starts at most one shared in-flight `GET /auth/me`, replaces the in-memory token, and retries the rejected mutation exactly once. The refresh request cannot recursively refresh itself. If refresh returns 401, clear auth state and do not retry. The backend rejects CSRF before provider calls or writes, so this single retry cannot duplicate a completed mutation.

- [ ] **Step 4: Implement auth provider**

On mount, query `/auth/me`; 401 means guest, not an application error. Each successful `/auth/me`, login, or auto-login registration response updates user and the latest in-memory CSRF token. Logout sends CSRF, clears state and query cache. `useAuth()` returns `{ user, isLoading, login, register, logout }`. Tests cover two concurrent 403 responses sharing one refresh call, one successful retry per mutation, and no retry loop when refresh fails.

- [ ] **Step 5: Verify and commit**

Run relevant Vitest files, build, lint; commit `feat: add typed Web API client`.

### Task 3: Recommendation/Evaluation Form and Normalized Weights

**Files:**
- Create: `frontend/src/features/search/TravelForm.tsx`
- Create: `frontend/src/features/search/OriginFields.tsx`
- Create: `frontend/src/features/search/ScenerySelector.tsx`
- Create: `frontend/src/features/search/WeightSegments.tsx`
- Create: `frontend/src/features/search/formState.ts`
- Test: `frontend/tests/TravelForm.test.tsx`
- Test: `frontend/tests/WeightSegments.test.tsx`

**Interfaces:**
- Produces `TravelFormProps = { initialMode?: "recommendation" | "place_evaluation"; isSubmitting?: boolean; fieldErrors?: Record<string, string>; onSubmit: (request: RecommendationRequest | PlaceEvaluationRequest) => void | Promise<void> }`, validated request values, and non-sensitive persisted weight preferences. Task 4's `SearchWorkspace` consumes it; this task does not modify `AppShell`.
- Produces `WeightSegmentsProps = { originCount: 1 | 2 | 3; value: RankingWeights; onChange: (value: RankingWeights) => void; onReset: () => void }`.

- [ ] **Step 1: Write mode and field behavior tests**

```tsx
test('specified place mode hides scenery and requires target', async () => {
  const user = userEvent.setup();
  render(<TravelForm onSubmit={vi.fn()} />);
  await user.click(screen.getByRole('radio', { name: '评估指定地点' }));
  expect(screen.getByLabelText('目标地点')).toBeVisible();
  expect(screen.queryByRole('group', { name: '风景类型' })).not.toBeInTheDocument();
});

test('allows at most two companion origins', async () => {
  const user = userEvent.setup();
  render(<TravelForm onSubmit={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: '添加同行人出发地' }));
  await user.click(screen.getByRole('button', { name: '添加同行人出发地' }));
  expect(screen.getByRole('button', { name: '添加同行人出发地' })).toBeDisabled();
  expect(screen.getAllByLabelText(/同行人.*出发地/)).toHaveLength(2);
});
```

Test client validation for blank origin, nonpositive distance, date outside seven days, missing scenery in recommendation mode, and missing target in evaluation mode.

- [ ] **Step 2: Write normalized weight tests**

Test single defaults `weather=40,distance=30,fairness=0,popularity=30`, multi defaults `40/0/40/20`, every edit keeps sum exactly 100, and reset restores person-count defaults. Each separator moves in 5-point increments and transfers weight only between its adjacent segments; zero-width segments remain keyboard reachable. Adding/removing a companion resets to the matching default. Persist only non-sensitive weights keyed by mode and `single|multi` under `roambot.ui.weights.v1`.

- [ ] **Step 3: Implement controls**

- Mode is a two-option segmented radio group.
- Scenery uses labeled checkboxes, not text pills pretending to be buttons.
- Default state is recommendation mode, city `苏州`, blank origins, no companions, 50 km, start/end tomorrow in `Asia/Shanghai`, no scenery, match mode `any`, and blank target. Dates use native date inputs with min today and max today+6.
- Companion rows use `Plus` and `Trash2` icon buttons with tooltips.
- Maximum distance uses a numeric input with `km` suffix.
- Labels and accessible group names are exactly those in SPEC. Mode switching preserves each mode's in-memory visible fields but the serializer omits all hidden-mode fields. Scenery values preserve first-selection order; deselection removes and reselection appends.
- `WeightSegments` renders one segmented bar with two separators for single and three for multi, visible percentages, and Reset. Its canonical values are integer percentages totaling 100; a separator changes only adjacent segments by 5 points. Coincident separators remain separately focusable with stable offset hit areas. Never compute result scores in this component.
- Apply the exact client error messages in SPEC, then let backend `error.fields` replace matching client errors.
- Submit copy is `开始推荐` or `评估这个地点`.

- [ ] **Step 4: Verify and commit**

Run `npm --prefix frontend test -- TravelForm.test.tsx WeightSegments.test.tsx`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build`; expect exit 0, then commit `feat: build travel request form`.

### Task 4: Results, Daily Weather, and Source States

**Files:**
- Create: `frontend/src/features/search/SearchWorkspace.tsx`
- Create: `frontend/src/features/search/ResultList.tsx`
- Create: `frontend/src/features/search/ResultCard.tsx`
- Create: `frontend/src/features/search/DailyWeatherList.tsx`
- Create: `frontend/src/features/search/SourceNotice.tsx`
- Create: `frontend/src/pages/SearchPage.tsx`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Test: `frontend/tests/ResultCard.test.tsx`

**Interfaces:**
- Consumes: the two core API endpoints.
- Produces: loading, live/cache/demo/degraded, empty, validation, provider-failure, and success views.

- [ ] **Step 1: Write result-state tests**

Test that:

- Submit disables only while the current request is pending and prevents duplicate calls.
- Demo response displays persistent `演示数据` notice.
- Cache response displays `地点信息来自近期缓存`.
- Degraded distance displays `直线估算` next to that distance.
- Empty items displays `规定范围内无检索结果` and backend notices.
- Result card shows total, weather, distance, fairness when present, `RoamBot 热度估算`, daily dates/scores/reasons, explanation, and risk notices.
- No map, route, navigation, or itinerary text/element exists.

- [ ] **Step 2: Implement workspace and query mutation**

Use TanStack `useMutation`. Keep the last successful result visible during a new request with an unobtrusive updating state; replace it only on success. Map `ApiError.fields` to form errors and show provider failures in a status region with `role="alert"`.

- [ ] **Step 3: Implement stable result layout**

Cards use a fixed score column, content column, and actions row with stable min sizes. Daily weather uses a horizontally scrollable table on narrow screens, never overlapping score/reason text. Only repeated destination results use card surfaces.

- [ ] **Step 4: Verify and commit**

Run result tests, build, lint; commit `feat: display explained recommendation results`.

### Task 5: Registration, Login, and Protected Navigation

**Files:**
- Create: `frontend/src/features/auth/AuthDialog.tsx`
- Create: `frontend/src/features/auth/RequireAuth.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Test: `frontend/tests/AuthDialog.test.tsx`
- Test: `frontend/tests/RequireAuth.test.tsx`

**Interfaces:**
- Consumes: `/auth/register`, `/login`, `/logout`, `/me`.

- [ ] **Step 1: Write auth UI tests**

Assert username/password registration and login, generic invalid-credentials copy, no phone/email/CAPTCHA inputs, logout state, and protected navigation opening login without blocking the `/` core page.

- [ ] **Step 2: Implement accessible auth dialog**

Use native `<dialog>` or an accessible modal with focus trapping and Escape close. Tabs/segmented controls switch login/register. Password input supports visibility toggle using `Eye/EyeOff` icons and accessible names. Do not mention unsupported recovery.

- [ ] **Step 3: Implement protected route behavior**

Unauthenticated `/favorites` or `/history` opens login and returns to the requested path after success. Anonymous `/share/:token` remains public.

- [ ] **Step 4: Verify and commit**

Run auth tests, build, lint; commit `feat: add local account interface`.

### Task 6: Favorites, History, and Anonymous Shares

**Files:**
- Create: `frontend/src/pages/FavoritesPage.tsx`
- Create: `frontend/src/pages/HistoryPage.tsx`
- Create: `frontend/src/pages/HistoryDetailPage.tsx`
- Create: `frontend/src/pages/PublicSharePage.tsx`
- Create: `frontend/src/features/favorites/FavoriteList.tsx`
- Create: `frontend/src/features/history/HistoryList.tsx`
- Create: `frontend/src/features/history/ShareActions.tsx`
- Test: `frontend/tests/FavoritesPage.test.tsx`
- Test: `frontend/tests/HistoryPage.test.tsx`
- Test: `frontend/tests/PublicSharePage.test.tsx`

**Interfaces:**
- Consumes: personal-data and public-share API endpoints from plan 02.

- [ ] **Step 1: Write personal-page tests**

Assert:

- Favorite rows show place metadata only; `重新评估` navigates to `/` with target prefilled but requires new origin/date.
- History is newest first, marked `历史快照`, and shows generated time.
- Rerun creates/navigates to a new history record; old snapshot remains.
- Delete confirmation explains that related shares stop working and favorites remain.
- Clear-all requires explicit confirmation.
- Share creation displays a copyable URL; revoke updates status.
- Public share works logged out and contains no username or detailed origin.

- [ ] **Step 2: Implement query/mutation hooks**

Feature hooks invalidate only relevant query keys. On 401, clear auth state and open login. On 404 public share, show a single `分享链接不可用或已撤销` state without revealing cause.

- [ ] **Step 3: Implement pages without nested cards**

Use full-width page layouts with tables/lists. Individual favorite/history rows may be cards on mobile but page sections remain unframed. Use `Heart`, `History`, `RefreshCw`, `Share2`, `Copy`, `Trash2`, and `X` icons with accessible labels.

- [ ] **Step 4: Verify and commit**

Run personal-page tests, build, lint; commit `feat: add favorites history and sharing UI`.

### Task 7: Responsive, Accessibility, and Visual QA

**Files:**
- Create: `frontend/src/styles/forms.css`
- Create: `frontend/src/styles/results.css`
- Create: `frontend/src/styles/responsive.css`
- Modify: all feature components needing accessible labels/status regions
- Test: `frontend/tests/accessibility.test.tsx`

**Interfaces:**
- Produces: stable desktop/mobile layouts at 1440x900, 1024x768, 390x844, and 360x800.

- [ ] **Step 1: Add static accessibility tests**

Test every form control has a label, icon-only buttons have accessible names, result changes use an `aria-live="polite"` status region, errors use `role="alert"`, and mode/weight controls are keyboard reachable.

- [ ] **Step 2: Implement exact responsive structure**

```css
.search-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.search-controls { position: sticky; top: 76px; }

@media (max-width: 800px) {
  .search-workspace { grid-template-columns: minmax(0, 1fr); gap: 18px; }
  .search-controls { position: static; }
  .app-nav__label { display: none; }
}
```

Use stable min/max widths, `overflow-wrap: anywhere`, and no viewport-based font sizing. Text, buttons, score badges, and daily rows must not resize their containers on hover/loading.

- [ ] **Step 3: Run manual browser screenshots**

Start backend mock server and Vite. Capture screenshots at all four viewports. Inspect for overlap, clipped Chinese text, horizontal page overflow, nested cards, blank states, and missing source notices. Use browser devtools or Playwright screenshots; do not approve from code inspection alone.

- [ ] **Step 4: Verify and commit**

Run all Vitest, build, lint; commit `style: complete responsive WebUI baseline`.

### Task 8: Playwright User Journeys

**Files:**
- Create: `playwright.config.ts`
- Create: `e2e/guest-recommendation.spec.ts`
- Create: `e2e/account-personal-data.spec.ts`
- Create: `e2e/public-share.spec.ts`
- Create: `e2e/responsive-layout.spec.ts`

**Interfaces:**
- Produces: browser-level acceptance evidence against real local frontend/backend processes with mock providers.

- [ ] **Step 1: Configure web servers**

Configure Playwright to start Uvicorn on 8000 and Vite on 5173, use `baseURL: "http://127.0.0.1:5173"`, `trace: "retain-on-failure"`, and projects for desktop Chromium plus mobile 390x844 Chromium. Use a temporary SQLite path per run.

- [ ] **Step 2: Implement exact journeys**

- Guest recommendation: fill 苏州站, 80km, future dates, 湖景, submit, see 金鸡湖 and demo notice, verify no history request is made.
- Account: register unique test username, recommend, favorite first result, open history, rerun, create share, delete original history, verify share unavailable and favorite remains.
- Public share: create via API setup, open in a fresh logged-out context, verify sanitized fields and no account navigation requirement.
- Responsive: at 1440x900 assert form/result bounding boxes do not intersect and form is left of result; at 390x844 assert result starts below form and `document.documentElement.scrollWidth === window.innerWidth`.

- [ ] **Step 3: Install browser and run**

```powershell
npx --prefix frontend playwright install chromium
npx playwright test
```

Expected: all journeys pass with no real provider requests.

- [ ] **Step 4: Commit**

Commit `test: cover critical WebUI journeys` with Playwright config and tests; do not commit transient screenshots/traces unless they are selected assignment evidence.

### Task 9: Cross-Platform One-Command Tests

**Files:**
- Create: `scripts/test.ps1`
- Create: `scripts/test.sh`
- Create: `Makefile`
- Modify: `AGENT_LOG.md`

- [ ] **Step 1: Implement scripts**

PowerShell script runs, in order, backend pytest, Ruff, frontend Vitest, frontend lint, frontend build, and Playwright. It exits immediately on any nonzero status. Shell script uses the same order. `Makefile` target `test` calls `./scripts/test.sh` for CI.

- [ ] **Step 2: Run complete verification**

```powershell
./scripts/test.ps1
git diff --check
```

Expected: all backend/frontend/browser tests and builds pass; diff check exits 0.

- [ ] **Step 3: Record evidence and commit**

Add exact test counts, viewport screenshots inspected, and human UI adjustments to `AGENT_LOG.md`. Commit `build: add full-stack verification commands`.

## Milestone Exit Criteria

- All approved pages and flows work against mock backend providers.
- Guest, account, personal-data, and anonymous-share boundaries match the backend.
- Desktop/mobile screenshots are nonblank, correctly framed, and have no overlap or page-level horizontal overflow.
- Browser storage contains no password, session token, CSRF token, history, share token, or provider key.
- `./scripts/test.ps1` passes without real credentials or network provider calls.
