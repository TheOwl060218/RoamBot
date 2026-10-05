# 交接任务：完成 `experiment/ui-clean-a` 的 SearchWorkspace 重构

> **2026-10-05 状态更正：本文记录的是此前中断时的历史交接，不再是当前执行说明。** 下文所述 TypeScript 错误和缺失 state/ref 已经完成收口，当前工作区已经通过 Vitest、ESLint、TypeScript、Vite build 以及 Mock 模式的桌面/移动端 Playwright。后续 P0 应以 `docs/superpowers/specs/2026-10-05-travel-plan-collaboration-design.md` 第 18 节、人工提供的 P0 Prompt 与 `docs/competition/AI_CODING_PROCESS.md` 为准；不得重新实现下文已经废弃的 landing/editing 状态机。本文仅保留用于追溯中断背景。

> 本文件是给下一个智能体的交接 Prompt。请按以下指令继续此前未完成的 UI 重构。

## 一、背景与现状

项目：`RoamBot`（前端 `frontend/`，React 19 + Vite + TypeScript + Vitest）。
当前分支：`experiment/ui-clean-a`。
工作区有一批**未提交**改动，重构进行到一半，`SearchWorkspace.tsx` **当前无法通过类型检查**，属于中断的中间状态，需要你把它补完并让测试通过。

### 已改动文件（git status 可见，均未提交）
- modified：`frontend/e2e/responsive-layout.spec.ts`、`frontend/src/app/AppShell.tsx`、`frontend/src/features/search/CandidateComparison.tsx`、`frontend/src/features/search/QuerySummary.tsx`、`frontend/src/features/search/ResultList.tsx`、`frontend/src/features/search/SearchWorkspace.tsx`、`frontend/src/features/search/formState.ts`、`frontend/src/features/search/scrolling.ts`、`frontend/src/styles/app.css`、`frontend/src/styles/results.css`、`frontend/src/styles/tokens.css`
- untracked：`frontend/src/features/search/SampleScenes.tsx`、`frontend/src/features/search/useCandidateComparison.ts`
- 已实现部分：`AppShell.tsx` 新增「首页」按钮并派发 `HOME_RESET_REQUEST_EVENT`（`goHome`）；`scrolling.ts` 已提供 `startSmoothScrollInContainer` 与 `startSmoothScrollTo`；`formState.ts` 已有 `HOME_RESET_REQUEST_EVENT`、`clearSearchResult` 等；候选对比组件与测试已就位。

## 二、核心卡点（必须修复）

`SearchWorkspace.tsx` 当前引用了一批**未声明/未导入**的标识符，`tsc -b` 报 12 个错误。你必须在 `SearchWorkspace` 组件内补齐这些 state/ref，并修正 import：

1. **`startSmoothScrollInContainer` 未导入**（line 108、191 使用，`scrolling.ts` 中已导出）。
   当前 import 的是 `startSmoothScrollTo`，且因未使用而报 TS6133。→ 需要按下面的滚动语义统一 import（见第四节）。
2. **`editingConditions`（useState<boolean>）缺失**（line 236、238、266、323 使用）：控制侧栏控件区显示 `TravelForm`（true）还是 `QuerySummary`（false）。
3. **`landingAfterSubmit`（useState<boolean>）缺失**（line 236、249 使用）：提交成功后短暂处于「landing」展示态。
4. **`landingSummaryRef`（useRef）缺失**（line 250 使用，挂到 `.query-summary-landing` 容器）。
5. **`controlsRef`（useRef）缺失**（line 279 使用，挂到 `<aside>`）。
6. **`transitioningToEdit`（useState<boolean>）缺失**（line 323 使用）：编辑切换过渡期间禁用候选切换器。
7. **`editConditions` 函数体不完整**（line 188-193）：当前只滚动到 `formRef`，未真正切换 `editingConditions`。注意命名：`editingConditions`（state）与 `editConditions`（函数）需共存，别混淆。

## 三、目标行为契约（以 `frontend/tests/SearchWorkspace.test.tsx` 为准）

测试已写好期望，你的实现必须让它们通过。关键点：

1. **提交后 landing**（测试「lands on the query summary without visiting the results first」）：
   - 提交成功后，在侧栏渲染一个副本 `.query-summary-landing`（包着 `QuerySummary`），其父容器 `.search-controls` 需要带 `search-controls-landing` class。
   - **滚动方式是窗口级 `startSmoothScrollTo(getTarget, onComplete)`**，滚动目标为 Landing 容器。注意测试 mock 的是 `startSmoothScrollTo` 并断言它被调用、目标带 `query-summary-landing`、父类含 `search-controls-landing`。当前实现误用了 sidebar 内的 `startSmoothScrollInContainer`，需要改为 `startSmoothScrollTo`。
2. **编辑态**（测试「selects one candidate at a time and reopens the existing form in place」「expands the form before starting the upward scroll animation」）：
   - 点击「重新查询 / 修改条件」→ `editingConditions=true`，侧栏从 `QuerySummary` 切换为 `TravelForm`（出现「开始推荐」按钮），且 `.search-controls` 带 `search-controls-editing`。
   - 表单展开必须在向上滚动动画**之前**完成（在 rAF 被 mock 的用例下，「开始推荐」按钮已出现）。
3. **initialTarget 直入编辑态**（测试「opens a requested place evaluation even when a previous result is cached」）：
   - 当以 `initialMode="place_evaluation"` + `initialTarget` 打开时，即使有缓存 result，也直接显示 `TravelForm`（radio「评估指定地点」选中、目标地点有值），且**不出现**「修改条件 / 重新查询」按钮。
4. **结果态**（测试「submits the form and displays a complete recommendation result」）：
   - 提交后有结果时 `.search-workspace` 不带 `search-workspace-empty`；显示「修改条件」按钮（注意见下面冲突）、隐藏「开始推荐」；`.workspace-message-slot` 带 `workspace-message-slot-collapsed`。
5. **候选切换器**：`ResultList` 的 `candidateSwitcherEnabled` 传入 `!editingConditions && !transitioningToEdit`（当前 line 323 已这样写，补齐 state 即可）。

## 四、已知的不一致（需要你决策并二选一）

- **按钮文案冲突**：`QuerySummary.tsx` 按钮已从「修改条件」改为「重新查询」，但测试 `SearchWorkspace.test.tsx` line 174/295/312 仍查找「修改条件」。请统一：**推荐改回「修改条件」**（保持测试原样，改动最小），若你选择保留「重新查询」则必须同步更新测试三处。
- **`.query-summary-landing` 的 CSS 缺失**：`results.css` 目前只有 `.search-controls.search-controls-landing { max-width: 100% }`，`.query-summary-landing` 本身无样式。请补足（可参考 `.query-summary` 样式，并处理与 `.search-controls-landing` 的布局配合）。
- **旧滚动逻辑需重写**：`SearchWorkspace` 内原 `useEffect`(scrollToSummaryVersion / requestSummaryScroll，line 103-113 附近) 走的是 sidebar 容器滚动，与第 3 节的 landing 语义（窗口滚动 `startSmoothScrollTo`）不匹配，请按目标行为重写：提交成功后在落地页展示 landing 副本并向上平滑滚动到它。

## 五、实施建议

- 在 `SearchWorkspace` 组件内补上缺失的 state/ref 初始化（`editingConditions`、`landingAfterSubmit`、`transitioningToEdit` 初始值 `false`；`controlsRef`、`landingSummaryRef` 用 `useRef`）。
- 重写 `editConditions`：设置 `setEditingConditions(true)`，并按契约触发滚动/过渡。
- 在 `submit()` 成功后根据目标行为设置 `landingAfterSubmit` 与滚动；用 `startSmoothScrollTo` 而非 `startSmoothScrollInContainer`。
- 处理 `initialMode`/`initialTarget` 的直入编辑态逻辑。
- 保持与已有子组件接口一致（`QuerySummary` 的 `onEdit`、`TravelForm` 的 `onSubmit`、`ResultList` 的 `candidateSwitcherEnabled` 等）。
- **不要**改动已确认的产品行为或重开已定稿的 UI 议题，除非有可复现证据。

## 六、验证

在 `frontend/` 目录执行（本项目 `npx` 不在 PATH，用本地二进制或 npm scripts）：
1. 类型检查：`node_modules\.bin\tsc.cmd -b`（或 `npm run build` 中的 tsc 部分）——必须 0 错误。
2. 单元测试：`npm test`（vitest run）——重点 `SearchWorkspace.test.tsx` 全绿。
3. Lint：`npm run lint`（eslint）——0 报错。
4. E2E：`npm run e2e`——**必须使用 Mock/demo 模式**（见 AGENTS.md），不要跑真实 provider 测试。
5. 完成后如有必要，同步 `docs/PROJECT_HANDOFF.md`（仅当项目状态发生变化时）。

## 七、约束（务必遵守）

- 不得请求、打印、存储或提交任何 API key / 凭据 / cookie / token。
- 自动化校验一律用 Mock/demo 模式；未经用户明确要求不跑真实 provider 测试。
- 不擅自 commit / push（除非用户明确要求）。
- 代码风格：React Hooks、TS，保持与现有文件一致，不加多余注释。
