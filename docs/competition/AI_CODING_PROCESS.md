# RoamBot AI Coding 开发过程记录

> 2026-10-06 同行计划增量由 **Codex** 实现，不能归属为湛卢代码生成。P1～P6 与收尾审查实际记录见 [CODEX_PLAN_IMPLEMENTATION.md](CODEX_PLAN_IMPLEMENTATION.md)；当前均未提交，无新增 Commit SHA。原湛卢候选对比与 P0 记录保持不变。Mock 自动通过不等于用户人工验收或 Live 验证。

> 用途：第五届“移动云杯”智算应用创新大赛 AI Coding 赛道的过程证据索引。
>
> 原则：本文件只记录能够由原生对话、代码差异、Commit 或测试输出核验的事实。暑期训练营阶段已有代码不追溯标注为湛卢生成；未实际运行的内容不写成“已验证”。

## 1. 证据来源与保存方式

- 湛卢平台原生对话：保留需求拆解、RED/GREEN 输出、人工批准节点和环境排查过程，作为主要过程证据。
- Git Commit：保存功能边界和修改前后差异，Commit SHA 作为可复核索引。
- 本地测试输出：保存 Vitest、Playwright、ESLint、TypeScript 与 Vite build 的实际命令和结果；截图时不得包含密钥、Token、Cookie、数据库内容或主密码。
- 人工审查：记录被发现的问题、采纳或拒绝的建议以及原因，不用“AI 自动完成”替代人工判断。

## 2. 本次参赛增量的已提交基线

以下 5 个 Commit 位于 `competition/ai-coding` 基线，均可通过 `git show <SHA>` 核验：

| Commit | 内容 | 主要证据 |
| --- | --- | --- |
| `59f7964` | 确定性的候选地点对比逻辑及单元测试 | `compareLogic.ts`；两轮 RED→GREEN；14 项逻辑测试 |
| `12a403c` | 可访问的候选对比组件及组件测试 | `CandidateComparison.tsx`；UI RED→GREEN；13 项组件测试 |
| `7c47a22` | 将候选对比接入搜索结果页 | `SearchWorkspace` 接入与页面测试 |
| `b5fcbe1` | 候选对比样式 | `results.css` |
| `36e0422` | 桌面/手机响应式候选对比 E2E 与系统 Chrome channel 配置 | Playwright spec；当时的完整门禁记录 |

该阶段的真实过程包含：需求拆解、缺失模块导致的有效 RED、最小实现 GREEN、人工审查发现 `popularity=null`、三候选文案和空结论兜底问题、第二轮 RED→GREEN、UI 契约修正、页面接入、E2E 与 Node/Python/Playwright/Chrome 环境排查。详细原始证据保留在湛卢原生对话，不在本文件中补造对话或截图。

## 3. 2026-10-04 前端清理 Phase 0

### 3.1 目标与协作边界

目标是收口中断的 `SearchWorkspace` 双栏重构，不扩展比赛功能：

- 左栏常驻查询表单；有结果时继续显示查询摘要、候选列表和候选对比选择器。
- 右栏无结果时显示示例场景，有结果时显示地点详情和对比表。
- 删除旧的“表单/摘要二选一”状态，不恢复已经废弃的 `editingConditions` 流程。
- 保留 Mock 演示边界，不调用真实 Provider，不操作 Docker，不推送远程。

工作分工如实记录：

- 湛卢此前已经开始双栏 UI 清理，但一次长段替换中断，工作区处于可读但无法通过类型检查的中间状态。
- 人工决定保持新双栏方向，并批准 Codex 协助收口；不是回退到暑期版本。
- Codex 完成中间状态诊断、聚焦测试契约更新、最小代码收口、回归测试和门禁验证。
- 经用户明确批准，GPT-6 仅进行只读前端复核和 E2E 异常复核，没有直接修改代码。其发现的直接回归是：对比状态上移后，旧结果选中的 3 个 ID 可能使新结果候选全部禁用。

### 3.2 RED→GREEN 证据

1. 初始 TypeScript RED：`tsc -b` 报 12 个错误，集中于已删除状态/Ref 的残留引用，以及滚动函数导入不一致。
2. `SearchWorkspace` 聚焦 RED：11 个测试中 10 个失败，直接错误为 `editingConditions is not defined`；说明中断重构尚未收口。
3. 最小实现后 GREEN：`SearchWorkspace.test.tsx` 11/11 通过，TypeScript 通过。
4. 人工/GPT-6 审查新增回归测试：替换候选集合后应丢弃不可用的旧选中 ID。该测试先失败，证明新候选被错误禁用。
5. `useCandidateComparison` 过滤无效 ID 后 GREEN：`CandidateComparison.test.tsx` 14/14 通过。
6. 将旧 E2E 的“修改条件”和“结果后隐藏表单”断言更新为当前常驻表单契约；没有通过删除核心交互断言来规避失败。

### 3.3 实际验证记录

环境边界：Node `v24.19.0`，Playwright `1.62.1`，系统 Chrome channel，FastAPI Mock 后端；未调用 Live Provider。

| 检查 | 实际结果 |
| --- | --- |
| 聚焦 Playwright：响应式布局 + 候选对比，桌面/手机 | 4/4 通过，约 11 秒 |
| 全量 Playwright，桌面/手机 | 10/10 通过，约 31.3 秒 |
| Vitest 全量 | 17 个文件，82/82 通过，约 16.27 秒 |
| ESLint 全量 | 退出码 0，无错误输出 |
| TypeScript `tsc -b` | 退出码 0，无错误输出 |
| Vite build | 退出码 0；1847 modules transformed；约 1.43 秒 |

Playwright 环境排查边界：直接由 Playwright `webServer` 启动 Uvicorn/Vite 时，页面断言和 Chrome 关闭都完成，但 Windows 子进程回收发生挂起。为区分环境生命周期问题与产品失败，验证改用隔离端口手动启动 Mock 后端和 Vite，再设置 `PW_REUSE_SERVERS=1` 复用服务。上述 4/4 和 10/10 均是在该隔离环境中真实完成；测试结束后隔离端口已释放。该现象不写成前端缺陷，也没有通过升级依赖或放宽断言掩盖。

### 3.4 当前尚未完成或待确认

- Phase 0 工作区修改尚未 Commit；提交前需人工审查完整 diff，并明确湛卢既有修改与 Codex 收口修改的边界。
- 顶部空白区域的内容设计尚未开始，需要先讨论信息层级与比赛叙事。
- 移动端和双栏内部滚动策略仍需单独设计；本阶段只保证现有契约通过。
- 合适卡片的 hover `scale(1.01)` 尚未实施，需要先明确作用范围并兼顾 `prefers-reduced-motion`、键盘焦点和触摸设备。
- 示例场景触发的摘要是否完全对应实际请求、侧栏拖动条键盘可访问性、中间宽度布局风险，仍是已识别但未在 Phase 0 扩展处理的事项。
- Live Provider、远程部署和真实第三方 API 本轮未验证，不得在参赛材料中写成已验证。

## 4. 2026-10-05 首次使用引导与滚动体验改进

### 4.1 人工决策与实施范围

本轮先围绕比赛现场的首次使用者体验讨论方案，再由人工确认采用以下范围：

- 顶部空白区域增加长期可用的三步快速引导，不写比赛倒计时或一次性宣传语。
- 推荐完成后的自动滚动只执行一次，将左栏“当前查询”与侧栏可视区域顶部对齐；不改为持续吸顶。
- 候选对比选择器按已选数量给出下一步提示；选择 2～3 个候选后出现“查看对比结果（N）”按钮。
- 点击该按钮后，右栏滚动到对比表、将其设为键盘焦点并短暂高亮，解决首次使用者不知道结果位置的问题。
- 仅对可点击的示例卡与候选卡增加 `scale(1.01)` hover/focus 反馈；触摸设备不强制 hover，并尊重 `prefers-reduced-motion`。

明确未做：不移动对比表的数据归属、不增加弹窗、不修改推荐算法、不调用真实 Provider、不做大规模页面重构。

GPT-6 在本轮只承担只读设计/实现复核；具体范围、交互选择与是否采纳由人工决定，代码实施与验证由 Codex 完成。不得将其描述为 GPT-6 独立完成前端。

### 4.2 本轮 RED→GREEN

1. 在实现前新增聚焦测试，覆盖：长期可见的快速引导、候选数量提示与跳转按钮、点击后对比表焦点/高亮，以及布局发生变化时按实时位置对齐。
2. 初始 RED：3 个测试文件共 30 项，结果为 26 通过、4 失败；失败分别对应上述四类尚未实现的行为。
3. 最小实现后 GREEN：同一组聚焦测试 30/30 通过，没有删除或放宽失败断言。
4. Playwright 增加桌面端实际顶部对齐断言，并在桌面/手机对比流程中验证“查看对比结果”会把焦点和高亮带到右栏对比表。

### 4.3 实际验证记录

环境边界：Node `v24.19.0`，Playwright `1.62.1`，系统 Chrome channel；E2E 使用隔离端口上的 FastAPI Mock 后端和 Vite 前端，未调用 Live Provider。

| 检查 | 实际结果 |
| --- | --- |
| 聚焦 Vitest：组件、滚动与工作区 | 3 个文件，30/30 通过 |
| 聚焦 Playwright：响应式布局 + 候选对比，桌面/手机 | 4/4 通过，约 10.4 秒 |
| 全量 Vitest | 17 个文件，86/86 通过，约 16.35 秒 |
| 全量 Playwright，桌面/手机 | 10/10 通过，约 31.3 秒 |
| ESLint 全量 | 退出码 0，无错误输出 |
| TypeScript `tsc -b` | 退出码 0，无错误输出 |
| Vite build | 退出码 0；1847 modules transformed；CSS 41.89 kB（gzip 8.15 kB），JS 358.19 kB（gzip 112.52 kB）；约 1.76 秒 |

人工界面检查使用隐藏的本地浏览器完成：确认顶部快速引导可见且不过度占高；推荐完成后左栏“当前查询”与侧栏顶部对齐；选择两个候选后提示按钮出现；点击后右栏移动到对比表并显示短暂高亮。该检查仅证明本地 Mock 演示界面行为，不证明 Live Provider 或远程部署可用。

### 4.4 当前边界

- 本轮及此前 Phase 0 的工作区修改仍未 Commit、未 push；提交前仍需人工审查完整 diff。
- Live Provider、远程部署、真实第三方 API 与真实地点数据本轮均未验证。
- 快速引导的最终文案与视觉高度可在人工演示后微调，但不应据此扩展新功能。
- 浏览器人工检查不是正式可访问性审计；现有键盘焦点、语义结构与 reduced-motion 处理已有自动测试和静态检查支撑。

### 4.5 人工复核后的滚动留白修正

人工查看实际界面后进一步明确：推荐完成时，“当前查询”不应与左侧滚动容器完全贴顶，而应在其上方保留与页面横向 gutter 一致的留白。该要求只影响本次推荐完成后的自动滚动终点，不改变重新查询、查看对比结果或用户手动滚动。

本次修正继续使用 RED→GREEN：滚动单测先将期望终点由贴顶的 `450` 改为保留 `24px` 后的 `426`，旧实现实际仍返回 `450`，形成有效 RED；随后让容器滚动工具读取目标的 `scroll-margin-top`，并由页面响应式 gutter 提供桌面 `24px`、手机 `14px` 的统一间距。聚焦 Vitest 为 15/15，通过后全量 Vitest 为 17 个文件、86/86；ESLint、`tsc -b`、Vite build 均退出 0；系统 Chrome + FastAPI Mock 的全量 Playwright 桌面/手机 10 项流程无失败。一次移动端天气布局旧断言在首轮出现约 11px 的瞬时时序偏差，单独复跑通过，因此没有修改与本需求无关的天气布局。

同时，人工已否决此前加入的“三步快速开始”顶部栏，并决定在后续 P0 中删除；截至本条记录写入时该栏仍存在于未提交工作区，不能描述为已经删除。顶部导航调整和旅行计划协作功能同样不属于本次滚动留白修正。

## 5. 建议提交时附带的证据

- 湛卢原生对话中每轮 RED、GREEN、人工审查和批准节点的截图或导出。
- 上述 5 个 Commit 的 `git show --stat` 与关键 diff。
- Phase 0 与本轮首次使用引导的最终 Commit（创建后补充 SHA）及其与本文件的对应关系。
- 终端测试摘要截图：86/86 Vitest、10/10 Playwright、ESLint/tsc 退出 0、Vite build 成功。
- Mock 演示录屏，并在画面或解说中明确“演示数据 / Mock”，避免被理解为真实 Provider 已上线。
- 一份“AI 建议被拒绝或延期”的清单，例如：不恢复旧状态机、不盲目升级依赖、不把环境进程回收问题包装成产品通过、不在 Phase 0 顺手加入顶部内容和 hover 动效。

## 6. 2026-10-05 P0：删除“三步快速开始”与独立“首页”按钮（推荐 UI 基线）

### 6.1 背景与人工决定

本轮只做“阶段 0：当前 UI 基线”，不改旅行计划的阶段 1～6。工作区 `experiment/ui-clean-a` 保留此前湛卢、Codex 与人工协作的所有未提交成果，不回退、不覆盖。GitHub 上已有人工备份 `backup/ui-clean-a-pre-p0-20261005`（Commit `506f12f`），仅用于异常时人工恢复，本轮不使用。

人工审阅后的决定并如实记录：

- “三步快速开始”顶部栏此前曾被实现并被旧测试当作“长期可见”契约覆盖；人工查看实际界面后认为它不符合最终顶部设计，明确拒绝并决定在 P0 删除。
- 独立“首页”按钮被人工决定取消；由现有“推荐”导航与 RoamBot 品牌承担“回到推荐工作区并恢复初始推荐状态”的入口。
- 本记录不把被拒绝方案写成从未发生，也不删除第 4.5 节对该方案的既有预记录。

### 6.2 修改范围

为完成上述删除并回归到稳定基线，改动了四个前端文件与两个测试文件：

- `frontend/src/features/search/SearchWorkspace.tsx`：删除 `quick-start-guide` 区块。
- `frontend/src/styles/results.css`：删除全部 `quick-start-*` 基础样式及其 `@media` 响应式规则。
- `frontend/src/app/AppShell.tsx`：删除独立“首页”按钮与 `HomeIcon` 引用，把 `goHome`（返回 `/` 并派发 `HOME_RESET_REQUEST_EVENT`）挂到 RoamBot 品牌与“推荐”导航。
- `frontend/src/styles/app.css`：删除 `.home-button` 及其 hover 样式，桌面 header 网格由 4 列收敛为 `auto minmax(0,1fr) 40px`，删除移动端为 home-button 保留的网格占位。
- 测试：`frontend/tests/SearchWorkspace.test.tsx` 与 `frontend/tests/AppShell.test.tsx`（见 RED）。

保留未动：左栏常驻查询表单、无结果示例场景、候选列表与候选对比选择器、“查看对比结果（N）”引导、对比表焦点与短暂高亮、已调浅的按钮填充色、hover/focus 反馈、桌面/移动端响应式、推荐完成后的 gutter 留白与 `scroll-margin-top` 联动、Mock/demo 能力；不修改推荐算法、评分、后端接口或数据模型。

### 6.3 RED→GREEN

按 RED→GREEN 执行，先改/补测试再改实现：

1. 修改 `SearchWorkspace.test.tsx` 旧契约，并新增两条行为测试：初始表单仍可见且不再显示“三步找到适合这次出行的地方”；点击 RoamBot 品牌可恢复初始推荐状态；点击“推荐”同样恢复初始推荐状态。
2. 在 `AppShell.test.tsx` 新增：顶部不再存在名为“首页”的独立按钮，同时“推荐”入口保留。
3. 有效 RED：聚焦 `SearchWorkspace.test.tsx` + `AppShell.test.tsx` 共 17 项，13 通过、4 失败；失败原因分别是旧 `home-button` 仍存在、旧 `quick-start` 标题仍存在、以及品牌/“推荐”尚未挂响重置事件（点击后仍停留在 with-result 状态）。
4. 最小实现 GREEN：同一组聚焦测试 17/17 通过。

### 6.4 完整门禁结果

环境边界：Node（codex runtime）、`.venv` FastAPI Mock/demo 后端、系统 Chrome channel，未调用 Live Provider，未下载新浏览器或依赖，未操作 Docker。

| 检查 | 实际结果 |
| --- | --- |
| 聚焦 Vitest（SearchWorkspace + AppShell） | 17/17 通过 |
| 全量 Vitest | 17 个文件，89/89 通过，约 14 秒 |
| ESLint 全量 | 退出码 0，无错误输出 |
| TypeScript `tsc -b` | 退出码 0，无错误输出 |
| Vite build | 退出码 0；1847 modules transformed；CSS 40.26 kB（gzip 7.94 kB），JS 356.91 kB（gzip 112.21 kB）；约 0.64 秒 |
| 全量 Playwright 桌面/手机 | 10/10 通过（干净数据环境），约 38.1 秒 |

Playwright 环境说明：本轮使用隔离端口（8010 Mock 后端 / 5180 前端）手工启动并复用。**首轮全量运行的 4 个桌面用例失败**，失败点均为“提交推荐后 `.place-detail` 未出现 / 登录对话框行为”，而同批 mobile 全部通过；经排查为自建隔离数据目录被前序运行反复写入导致的状态污染与首次并行加载时序，并非本次功能回归。按约定未放宽断言、未修改无关模块，而是在清空隔离数据目录并重启 Mock 后端后单独复现该用例如下：先是相关桌面用例单独串行复跑 3 通过、`account-personal-data` 仍失败，清空数据目录并重启后端后再跑 `account-personal-data` 2/2 通过，随后干净环境全量 10/10 通过。

### 6.5 人工审查发现的跨路由问题与最小修复

人工审查发现一个 P0 阻塞问题：`AppShell.goHome()` 在非推荐页（如 `/favorites`、`/history`）执行时先 `navigate('/')` 再派发 `HOME_RESET_REQUEST_EVENT`，而 `SearchWorkspace` 此时尚未挂载，事件丢失；推荐页随后挂载时仍可能从 sessionStorage 恢复旧推荐结果，不符合“从收藏、历史等页面点击 RoamBot 品牌或‘推荐’后，进入干净初始推荐状态”的 P0 契约。

1. 新增两条真实跨路由行为测试（`SearchWorkspace.test.tsx`）：初始路由位于 `/favorites`、`SearchWorkspace` 未挂载、sessionStorage 预存推荐结果，分别点击 RoamBot 品牌与“推荐”导航，断言导航到 `/` 后 `.search-workspace` 为 empty、旧地点结果不出现、推荐表单可见。
2. 有效 RED：聚焦 `SearchWorkspace.test.tsx` + `AppShell.test.tsx` 共 19 项，17 通过、2 失败；两条跨路由用例均因旧缓存恢复（`search-workspace-with-result`）而失败，失败原因符合预期。
3. 最小修复：`AppShell.goHome()` 先始终调用现有 `clearSearchResult()`（清结果与 selected place 的 sessionStorage）；只有当当前路径不是 `/` 时才调用 `navigate('/')`；随后始终派发 `HOME_RESET_REQUEST_EVENT`，以清理可能已经挂载的 SearchWorkspace 内存 state，未挂载场景则在挂载时读到干净的 storage。不引入 `setTimeout` 等时序补丁，不清除表单草稿或权重偏好。品牌与“推荐”均经由共享的 `goHome` 覆盖该行为。
4. GREEN：二次聚焦 19/19 通过。

跨路由修复后的二次完整门禁（实际运行）：

| 检查 | 实际结果 |
| --- | --- |
| 聚焦 Vitest（SearchWorkspace + AppShell） | 19/19 通过 |
| 全量 Vitest | 17 个文件，91/91 通过，约 16.9 秒 |
| ESLint 全量 | 退出码 0，无错误输出 |
| TypeScript `tsc -b` | 退出码 0，无错误输出 |
| Vite build | 退出码 0；1847 modules transformed；CSS 40.26 kB（gzip 7.94 kB），JS 356.91 kB（gzip 112.21 kB）；约 0.56 秒 |
| 全量 Playwright 桌面/手机 | 10/10 通过（干净数据环境），约 35.6 秒 |

### 6.6 当前边界与未验证

- P0 已完成人工审查，并作为本节所在的独立 Git 提交形成后续阶段基线；尚未 push。
- 真实 Provider、远程部署与真实第三方 API 本轮未验证，不得写成已验证。
- 旅行计划阶段 1～6 未开始实施，也未写成已完成。
