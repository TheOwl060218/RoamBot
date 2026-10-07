# 同行计划决策工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 禁止子智能体；Codex 在当前会话执行，保留现有未提交工作。

**Goal:** 将用户已确认的双角色预览落实为正式应用，候选同步按日比较，投票不遮挡桌面内容。

**Architecture:** PlanPages 保留接口、鉴权、危险动作和确认框；共享 PlanComparison 负责候选与日期，PlanVotePanel 负责单份表单及开关。桌面正常 Grid 占位，手机使用同一表单的底部面板，不创建第二份草稿。

**Tech Stack:** 现有 React 19、TypeScript、CSS、Lucide、Vitest/Testing Library、Playwright＋系统 Chrome。

**Spec:** `docs/superpowers/specs/2026-10-06-plan-decision-workbench-design.md`

## 2026-10-07 执行结果

任务 1～4 的正式实现、聚焦验证、完整门禁与双角色截图已完成，保留未提交工作，停止供用户验收。下方为原始实施清单；具体覆盖以本节和 WORKBENCH_PROGRESS.md 为准，不把每个计划中的测试都宣称为新增或先 RED。

| 任务 | 实际结果 |
| --- | --- |
| 1 比较 | 4 项组件测试；跨年日期、同计划刷新/换计划、缺日、统一日期表、新天气不套旧建议 |
| 2 投票 | 5 项组件测试及页面/E2E；失败保留草稿、精确载荷、状态守卫、busy、防重复、Escape、断点单表单 |
| 3 编排 | 页面 18 项；原确认及权限保留，管理按需展开，打开管理收起投票但保留草稿 |
| 4 浏览器 | 全量 26 项桌面/手机通过；新工作台 6 项，另两份更新专项 4 项；1/2/3候选、三/六日期、1440/1280/1024/390、短高度、减少动画、无桌面遮挡 |

未另补 1 日特例和管理轮换/撤销/移除/删除的逐动作 UI 自动化，相关 API/确认逻辑保留并自审。用户视觉、真实手机、Live/公网待验证；作者自审不是独立审查。

## Global Constraints

- 不改后端、数据库、API、评分、匿名身份或权限规则。
- 不调用 Live，不下载依赖，不操作 Docker，不修改用户真实计划，不 commit/push。
- 先投后看严格沿用服务端返回的 summary，不从其他字段构造票数。
- 原推荐与最近检查明确区分；新的天气没有 suitability 时显示暂无判断，不借用旧建议。
- 唯一页头投票入口，桌面约 280ms 连续宽度变化，不缩放文字；手机底部面板，减少动画偏好立即切换。
- 原主题色；昵称胶囊适应内容，桌面保存与邀请按钮对齐；不补空卡或固定空栏。
- 保留已有未提交修改；正式应用开发与预览验证分别记账。

## Review Focus

1. 某个候选缺开始日天气：显示该日暂无天气记录，不偷换日期（任务 1）。
2. 同一计划刷新天气或投票请求失败：所选日期和草稿不丢，失败不清空已加载计划（任务 2、3）。
3. 已关闭/决定/结束及未加入参与者：不能打开可编辑投票，不能看到未授权汇总（任务 2、3）。
4. 三候选、六日期、长昵称、短视口同时出现：桌面不重叠，手机无横向页面溢出（任务 4）。
5. 断点切换与快速连续开关：只有一份可操作表单，关闭后不能 Tab 到隐藏控件，日期不重置（任务 2、4）。

## 文件边界

- 新建 `frontend/src/features/plans/PlanComparison.tsx`：共享日期、候选卡、统一全部日期明细。
- 新建 `frontend/src/features/plans/PlanVotePanel.tsx`：紧凑投票表单与展开容器；导出下列接口。
- 修改 `frontend/src/features/plans/PlanPages.tsx`：两个页面编排、管理按需展开、唯一投票入口；计划中心不重做。
- 修改 `frontend/src/styles/plans.css`：工作台布局、动画、移动端与管理控件对齐。
- 复用 `frontend/src/features/search/DailyWeatherList.tsx`；只在确需复用图标时做兼容提取，推荐页行为不变。
- 新建 `frontend/tests/PlanComparison.test.tsx`、`frontend/tests/PlanVotePanel.test.tsx`；更新 `frontend/tests/PlanPages.test.tsx`。
- 新建 `frontend/e2e/plan-decision-workbench.spec.ts`；更新 `frontend/e2e/floating-vote.spec.ts`、`frontend/e2e/plan-detail-layout.spec.ts` 中被新设计替代的布局断言，保留业务断言。
- 更新 `docs/PROJECT_HANDOFF.md`、`docs/competition/CODEX_PLAN_IMPLEMENTATION.md`，仅记录实际结果。

## Task 1：同步日期比较组件

**Interfaces:**

```ts
type PlanComparisonProps = {
  plan: TravelPlan
  decisionAction?: (candidate: PlanCandidate) => React.ReactNode
  toolbarActions?: React.ReactNode
}
export function PlanComparison(props: PlanComparisonProps): React.ReactNode
```

- [ ] 先写测试 `syncs the selected date across every candidate`：三个候选、六日期，默认开始日，点击第二日后每张卡只显示第二日天气；默认无全部日期列表。
- [ ] 测试 `does not replace a missing day with another date`：一个候选缺第二日，显示“该日暂无天气记录”，其他候选正常；不得显示该候选第一日天气作为替代。
- [ ] 测试 `does not reuse snapshot advice after a fresh weather check`：latest_weather 存在时仅使用其 weather；没有新 suitability 则显示暂无判断。失败检查继续显示保留天气并说明失败与来源。
- [ ] 测试 `keeps the selected date on a same-plan refresh`、`resets viewing state for a different plan`，通过 rerender 检查日期状态；不以数组引用变化重置。
- [ ] 测试 `opens a unified all-date comparison`：一个统一明细区，日期为行、候选为列；无 AI 推荐理由；默认不展开所有日期。
- [ ] 运行 `node node_modules/vitest/vitest.mjs run tests/PlanComparison.test.tsx`，记录有效 RED。
- [ ] 实现组件；候选使用稳定 id，保留最终目的地标记/优先顺序。日期用 UTC 日历递增生成计划范围，避免本地时区与跨月错误。当天显示复用 DailyWeatherList 的图标/建议语义，完整当日说明按需展开。
- [ ] 同命令 GREEN，并加入跨月计划日期测试。

## Task 2：占位投票栏与紧凑投票表单

**Interfaces:**

```ts
export type VoteBody = { preferred_id: string; acceptable_ids: string[] }
type PlanVotePanelProps = {
  plan: TravelPlan
  open: boolean
  busy: boolean
  error: string
  onClose: () => void
  onVote: (body: VoteBody) => Promise<boolean>
}
export function PlanVotePanel(props: PlanVotePanelProps): React.ReactNode
```

- [ ] 写 `keeps an unsubmitted draft when closed and reopened`：选择首选/可接受、收起再展开，选择保留且未调用 onVote。
- [ ] 写 `retains draft after a failed save and closes only on success`：onVote 返回 false 时保持面板/选择；返回 true 时才 onClose。首选从 acceptable_ids 排除，提交体保持原约定。
- [ ] 写 `keeps exactly one editable form and disables controls while busy`；同计划数据刷新不丢草稿，换计划重置；若候选被删除，不能提交已不存在 id。
- [ ] 写 `does not expose voting for a closed or ended plan`：closed/decided/ended、me=null 均无可操作表单。
- [ ] 写 Escape 关闭与焦点归还测试；隐藏区域 inert/不可聚焦。打开聚焦首选项，桌面为非模态区域，手机不错误声明锁住正文。
- [ ] 运行 `node node_modules/vitest/vitest.mjs run tests/PlanVotePanel.test.tsx`，记录 RED，然后实现、重跑 GREEN。
- [ ] 表单按“候选名／首选／可接受”紧凑排列，radio/checkbox 有完整可访问名称；单份表单使用 CSS 断点改变容器，不重复挂载。

## Task 3：两个页面接入与发起者管理

**Interfaces:** PlanPages 调用任务 1/2 的导出；onVote 保持 owned/public 原路径，匿名使用已有 `X-Plan-CSRF`。

- [ ] 新增页面测试：参与者不显示管理/决定/结束入口；未加入昵称表单保留；summary=null 时不暴露票数，已投后使用真实 summary。
- [ ] 新增发起者测试：管理默认收起，展开保留名称/人数修改、生成/轮换/撤销邀请、复制、移除成员、删除确认；结束/决定/重新开放复用原 ConfirmDialog。
- [ ] 新增 `uses one header voting entry without a floating launcher`：打开后同一入口变“收起投票”，关闭为去/继续/修改；不存在右下重复入口。
- [ ] 新增 owned/public 投票体、匿名 header、保存失败数据保留、busy 防重复请求测试；保留已有业务断言。
- [ ] 运行 `node node_modules/vitest/vitest.mjs run tests/PlanPages.test.tsx`，观察新增功能 RED；只替换已被用户明确否定的旧布局契约，不削弱权限断言。
- [ ] 接入共享比较/投票，删除旧 FloatingVote 与固定左管理栏；页头状态胶囊对长昵称友好，管理按钮桌面底线一致、手机自然堆叠。
- [ ] 重跑三份聚焦测试 GREEN，运行全量 Vitest，逐个解释失败，不能改断言掩盖业务回归。

## Task 4：响应式、动画与浏览器验收

**Interfaces:** 稳定选择器 `.plan-decision-workspace`、`.plan-comparison`、`.plan-comparison-card`、`.plan-vote-slot`；用于几何验收，不参与业务判断。

- [ ] 先写 fixture 浏览器测试：两个角色、三候选六日期；1440/1280/1024＋390px、短高度约 650px；1/2 个候选另测无补空卡。
- [ ] RED：桌面投票打开时比较与投票矩形不重叠，关闭后比较区恢复宽度；约 280ms 动画中宽度取样呈连续变化，DOM 节点不重建；断点切换草稿保留。减少动画偏好允许直接切换。
- [ ] RED：不出现 viewport 横向溢出；候选最小约 260px，空间不足时局部横向轨道；手机无空桌面栏，底部面板高度受限且可关闭；长昵称、管理按钮对齐。
- [ ] 实现 plans.css：闭合 0px 列→桌面约 310px 列、gap 同步过渡，文字不 scale；隐藏面板 inert，不靠 display:none 切断动画；手机不缩比较区。
- [ ] 更新旧两份专项 E2E 的布局断言，保留提交、CSRF、草稿、邀请、关闭状态测试。所有 UI fixture 请求全量拦截，不写演示库。
- [ ] `ROAMBOT_E2E_BROWSER_CHANNEL=chrome`，隔离端口 8010/5180、唯一 run id，由现有 Playwright 配置启动 Mock 服务；运行新专项及更新专项，再运行全量 E2E。若端口被占，检查后换隔离端口，不停止用户 8000/5173。
- [ ] 门禁：全量 Vitest、`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`、`node node_modules/vite/bin/vite.js build`、`git diff --check`。
- [ ] 实际查看两个角色截图：三候选、六日期、投票打开，以及发起者管理展开；截图必须等动画完成。自动几何通过不等于用户视觉验收。
- [ ] 更新交接及过程记录：新增 RED/GREEN、实际数量/命令、UI fixture 与隔离 Mock 业务 E2E分开；记录未验证 Live/公网/真实手机。保留用户服务、不提交、不推送。

## 停止点

用户批准后已执行至门禁/截图收尾；现在停止供用户视觉验收，不自动 commit/push。需要下载、用户服务/数据库变更或扩展权限时仍必须先获批准。
