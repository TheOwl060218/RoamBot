# RoamBot 项目交接说明（给新的 GPT/Codex）

> 请先完整阅读本文件，再读取文中指定的项目文件。不要根据“以前大概通过过”宣称当前版本完成，必须以新的验证结果为准。

## 1. 用户与协作方式

- 使用中文沟通，解释要让非专业学生也能理解，但技术结论必须准确。
- 用户非常重视效率。此前曾因过多陌生 agent、逐 task 审查和重复测试消耗大量时间与额度。后续采用“大里程碑集中检查”，不要创建大量 subagent，不要重复测试已由用户确认的视觉细节。
- 不安装新依赖，不引入高德/QWeather 专用 SDK，优先使用项目现有依赖与模式。
- 修改前先简短说明要改什么；长任务每约 30 秒给一句有效进展。
- 不要求用户在聊天中提供 API key、主密码或 Cookie。真实凭据只能由用户在本机隐藏终端或部署平台 secret 中录入。
- 自动测试、CI 和一般调试必须使用 Mock/demo，禁止消耗高德、QWeather 或 LLM 额度。
- 前端先确保功能、响应式和一致性；不要无边界地增加地图、导航、行程安排、短信验证或微信小程序。

## 2. 项目定位与已确认边界

- 项目：RoamBot，B 类非 harness 应用项目。
- 形态：React + TypeScript + Vite 前端，FastAPI 后端，SQLite 持久化，单 Docker 镜像分发。
- 功能：天气感知的风景地点推荐和指定地点评估；支持多人出发地、权重、账户、收藏、历史、重新查询和匿名只读分享。
- 外部服务：高德用于地理编码、POI、距离和地点评分；QWeather 用于天气；学校 OpenAI-compatible LLM 只润色推荐理由，不能改变事实、分数或排序。
- 明确不做：地图绘制、导航、逐日行程、票务、短信/验证码、密码找回、微信小程序。小程序只可能是作业全部完成后的独立扩展。
- 分数前端称为“出游匹配指数”，只用于比较本次候选地点，不冒充官方评分。
- 地点评分来源需明确标注为高德开放平台；距离与用时按查询时驾车路况估算或明确标注直线估算。
- 天气不应把户外偏好完全过滤掉；恶劣天气可以保留少量相关候选，但必须降低指数并明确提示不建议或谨慎前往。
- 最多返回 7 个地点，实际数量不是硬指标。

## 3. 关键路径与 Git 状态

- 工作区：`C:\Users\24188\Desktop\智能化软件工程师夏令营\RoamBot\.worktrees\roambot-v1`
- 分支：`feat/roambot-v1`
- 远程：`origin https://github.com/TheOwl060218/RoamBot.git`
- 最近已提交 commit：`f1ef636 document recommendation landing behavior`
- 2026-08-03 检查时，工作区仍有大量未提交修改：55 个已跟踪文件发生变化，另有多份新组件、测试和计划文档；已跟踪 diff 约 `2206 insertions / 465 deletions`。
- `frontend/src/features/search/ResultCard.tsx` 的删除属于前端重构的一部分，不要随意恢复。
- 不得 reset、checkout 或覆盖这些改动。先读 `git status` 和 diff，理解后继续。

建议首先阅读：

1. `SPEC.md`
2. `PLAN.md`
3. `SPEC_PROCESS.md`
4. `AGENT_LOG.md`
5. `DECISIONS.md`
6. `README.md`
7. `TASKS.md`
8. `docs/frontend-adjustments.md`
9. `docs/evidence/verification.md`
10. `docs/STUDENT_MANUAL_COMPLETION_CHECKLIST.md`

## 4. 最近几天完成的主要工作

### 后端与推荐逻辑

- 接入高德 POI、地点详情/建议词、距离和评分相关能力，并保留 Mock、缓存与失败降级。
- 改善湖景/海景分类，避免把“海景”简单等同于沙滩；风景类型使用高德 type/typecode、名称规则和少量人工修正，LLM 不参与分类。
- 调整天气、距离、地点评分、偏好覆盖和多人路程差异的评分逻辑。
- 多人“均衡”按相对路程差异判断，不只看绝对分钟差。
- 推荐理由优先使用受约束的 LLM 输出，失败时才使用确定性本地模板；LLM 不得修改候选、天气、分数或排序。
- 增加地点输入建议接口：`backend/src/roambot/api/routes/places.py`。

### 前端与交互

- 完成响应式单栏查询流程：查询前展示完整表单；查询后展示紧凑“当前查询”摘要和修改条件入口。
- 桌面端结果采用左侧候选列表、右侧详情；候选不足时避免为 7 项强留过高空白。
- 手机端使用顶部候选切换器；最新修改已实现循环切换：第 1 项向左到最后一项，最后一项向右回第 1 项。
- 开始推荐后平滑滚动到查询摘要；修改条件后平滑滚回表单。此前出现“先跳到结果再回到摘要”的错误，后来已修成直接平滑到摘要。
- 单日与多日天气布局已区分，增加天气图标、温度提示词和更短的适宜天气文案；不适宜时允许更完整说明。
- 按钮改为统一胶囊形，并提供 hover、按下、禁用和加载反馈。
- 登录/注册/退出增加反馈；密码框关闭后不保留，查询表单的共享字段仍保留。
- 游客可使用地点推荐和指定地点评估；收藏、历史、分享等个人数据操作或无效会话收到 401 时，前端显示登录提示并打开账户对话框。
- 收藏按钮使用星形，可再次点击取消；收藏页支持地点详情和重新评估。
- 历史列表改成整行可打开、右侧菜单悬浮，不应把下一条记录向下推；分享、删除、撤销增加反馈和统一确认框。
- 历史详情、公开分享和手机端表格/天气卡已做响应式修复。
- 分享页面必须保持脱敏，不能包含账户身份和详细出发地址。

### 最近新增或重点文件

- `frontend/src/features/search/MobileCandidateSwitcher.tsx`
- `frontend/src/features/search/QuerySummary.tsx`
- `frontend/src/features/search/CandidateList.tsx`
- `frontend/src/features/search/CandidateDrawer.tsx`
- `frontend/src/features/search/PlaceInput.tsx`
- `frontend/src/features/search/PlaceDetail.tsx`
- `frontend/src/features/search/scrolling.ts`
- `frontend/src/features/history/HistoryActionsMenu.tsx`
- `frontend/src/features/favorites/FavoriteDetail.tsx`
- `frontend/src/app/ConfirmDialog.tsx`
- 对应 Vitest/Playwright 测试已增加，2026-08-09 当前工作树完整 Mock 门禁已通过。

## 5. 当前已知状态，不能误报（2026-08-09 更新）

- 当前工作树已完成一次完整 Mock 门禁：后端 `283 passed`、Ruff 通过；前端 Vitest 14 个文件 `52 passed`；ESLint、TypeScript、Vite build 通过；Playwright 桌面/移动端 `8 passed`。
- Windows 一键测试现在会在隔离端口 `8010/5183` 自动启动并关闭浏览器测试服务；本次结束后两端口均已释放。
- 上述结果全部来自 Mock/demo，真实 provider 调用为 0；详细证据已写入 `docs/evidence/verification.md`。
- 当前工作树的 Docker 新鲜构建、Mock 冷启动 smoke 和秘密扫描均已通过；最终 commit、push 与新一轮远程 CI 尚未执行。
- `TASKS.md` 的已存在交付物已据实勾选；Task 12 仍未完成，因为最终远程 CI、公网 WebUI 和学生本人反思仍缺失。
- `REFLECTION.md` 目前只有提纲，必须由学生本人完成 1500-2500 字正文，禁止 AI 代写。
- 目前没有公网部署 URL，这是作业硬性缺口。
- README 中公开镜像/commit 信息可能是旧版本，最终发布后需要更新。
- 当前只确认了 GitHub remote；课程要求通过 NJU Git 仓库链接提交，是否还需添加课程远程仓库要让用户确认。

## 6. 游客查询契约已核对

- 最终产品契约保持“游客可使用核心推荐和指定地点评估，游客查询不写个人历史”。
- `SPEC.md`、`README.md`、推荐路由的 optional session/CSRF 处理，以及 `guest-recommendation.spec.ts` 当前一致。
- 401 仅用于需要账户的个人数据操作或无效会话；不再把旧交接中的一次 Live 401 现象视为当前产品契约。

## 7. 推荐的收尾顺序

### 第一步：只读检查

- 读取上述文档和 `git status`/diff。
- 不回退用户改动，不安装新依赖，不先做视觉重构。
- 确认 8000、5173 等测试端口没有被现有服务占用。

### 第二步：一次集中自动化门禁

在 Mock/demo 模式运行项目已有的一键脚本：

```powershell
$env:ROAMBOT_PROVIDER_MODE = 'mock'
$env:ROAMBOT_DEMO_MODE = 'true'
$env:PATH = 'C:\Users\24188\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

该脚本依次运行 pytest、Ruff、Vitest、ESLint、TypeScript、Vite build 和 Playwright。不要使用 `pnpm`：此前一次误用 `pnpm exec vitest` 移动了 `node_modules` 依赖，虽已恢复，但不应重演。不要在测试期间调用真实 provider。

若门禁失败，使用 systematic debugging 定位根因，只修失败项并重跑必要范围；最后再重新跑一次完整门禁。

### 第三步：Docker 最终构建与冷启动

- 用当前工作树构建一个新的本地镜像。
- 使用新的临时容器名和 Mock/demo 配置冷启动，不占用或删除用户已有 `roambot-check-data` 卷。
- 验证 `/api/v1/health`、首页和 SPA 路由。
- smoke 完成后关闭临时容器；不要删除用户的正式数据卷。

### 第四步：安全与文档证据

- 扫描源码、Git diff、配置、日志和文档，不得出现真实 key、主密码、Cookie 或 token。
- 运行 `git diff --check`。
- 将准确的最新测试数量、Docker 镜像和 smoke 结果写入 `AGENT_LOG.md` 与 `docs/evidence/verification.md`。
- 更新 `TASKS.md` 的 Task 12 与最终交付项，但只能勾选真实完成的内容。
- 不代写 `REFLECTION.md`，最多帮助学生核对其本人写完后的结构和语病。

### 第五步：分支与远程

- 完整门禁通过后，展示 diff/stat 和待提交文件，让用户审阅。
- 按 `finishing-a-development-branch` 流程让用户决定：本地合并、推送并创建 PR、或保留分支。
- 不擅自删除 worktree，不强推，不把 feature 分支直接覆盖 main。
- push 后等待最后一次 CI/CD 实际通过，再把 run/commit 记录写入证据。

### 第六步：部署与提交

- 协助用户选择支持 Docker、HTTPS、secret 和持久卷的平台。
- 部署账户、支付授权、真实凭据和最终提交必须由用户本人操作。
- 获得公网 URL 后，验证桌面/手机、登录、Live 查询、收藏、历史和匿名分享。
- 更新 README 的部署架构、公开 URL、最终镜像和已知限制。

## 8. 安全和成本红线

- 绝不让用户把 key 粘贴到聊天。
- 绝不把真实 key 作为 Docker 命令参数、Git 文件或截图内容。
- 自动测试始终 Mock/demo；真实 smoke 只能由用户明确授权，并先说明最大调用次数。
- 不删除命名卷，不清空凭据库，不 reset Git，不覆盖未提交工作。
- 不把本地测试写成远程 CI 成功，不把旧镜像写成最新镜像，不把计划中的公网部署写成已部署。

## 9. 给新 GPT 的首条行动指令

收到本文件后，请这样开始：

1. 用两三句话复述当前状态和未完成项，证明理解交接内容。
2. 说明本轮只做收尾，不重新设计功能。
3. 先检查工作树和测试端口，再从完整 Mock 门禁继续。
4. 遇到需要真实凭据、部署账户、课程仓库地址或分支集成决策时，再向用户请求操作或确认。
