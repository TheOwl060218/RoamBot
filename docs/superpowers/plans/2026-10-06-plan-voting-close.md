# 结束投票与历史工作区回流 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许发起者结束投票而暂不决定目的地，并让历史重新查询回到可继续操作的推荐工作区。

**Architecture:** 扩展现有计划状态为 voting/closed/decided，通过 SQLite 同一写事务保证关闭与投票互斥。前端复用现有详情、导航和白卡片工作台；历史重查仍由既有接口生成新历史，再把结果与请求恢复到工作区，不重复请求推荐。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、SQLite、React、TypeScript、Vitest、现有 Playwright。

**Spec:** `docs/superpowers/specs/2026-10-06-plan-voting-close-design.md`；历史重查行为依据同日用户批准的“查看历史保留快照／重新查询回工作区”讨论。

## Global Constraints

- 用户数据库不能清空；迁移只在隔离测试副本验证，不操作当前用户数据。
- 普通查询仍允许游客；closed 不授予匿名用户管理权限。
- 不 Live、不 Docker、不安装依赖、不 commit/push/PR/merge。
- 延续 `experiment/ui-clean-a` 未提交工作区；不另建分支或搬移已实现内容。
- 本会话由 Codex 自行执行；仓库禁止子智能体，最终作者自审需如实标明，不伪称独立审查。
- 不自行重启用户 8000/5173 服务。浏览器完整验收需用户允许启动隔离 Mock 服务后执行；未执行不能记为通过。

## Review Focus

1. SQLite 迁移重建父表不能丢失计划关联候选、匿名参与者或票数；迁移任务加入保留关联行测试。
2. 关闭后并发到达的 owner/anonymous 改票均必须在事务内拒绝；服务任务覆盖两条写入路径。
3. closed 下未投者只读汇总可见，voting 未投者仍隐藏；服务任务覆盖此隐私边界。
4. 历史请求不同日期／评估模式／多人权重不能因回流变成当前草稿；回流任务检查实际恢复值。
5. 重查失败不能清除当前结果或跳走；回流任务覆盖网络拒绝及按钮锁。

### Task 1: 数据迁移和关闭状态服务

**Files:** 创建 `backend/alembic/versions/0005_plan_voting_closed.py`；修改 `persistence/tables.py`、`api/plan_models.py`、`api/routes/plans.py`、`services/plans.py`；测试 `backend/tests/api/test_plans.py`、`backend/tests/integration/test_database.py`。

**Interfaces:** 生产 `PlanService.close_voting(user_id, plan_id)` 与 `PUT /api/v1/plans/{plan_id}/voting-close`，返回 OwnedEnvelope；status 增加 closed。既有 decision/reopen 接口名称不改。

- [ ] 先补关闭测试，核心断言：
  ```python
  assert closed.status_code == 200
  assert closed.json()["plan"]["status"] == "closed"
  assert closed.json()["plan"]["final_candidate_id"] is None
  assert after_close_vote.status_code == 409
  assert reopened.json()["plan"]["summary"] == previous_summary
  ```
  每个 response 从真实 TestClient 接口取得；使用已有 create_plan/register fixture，不模拟服务。分别覆盖 owner、匿名改票、其他账户、无 CSRF、重复关闭、过期、关闭后决定以及未投者可见性。
- [ ] 运行 `.venv\Scripts\python.exe -m pytest backend/tests/api/test_plans.py -q --tb=short`；预期新增关闭流程因路由不存在而失败，先辨别 fixture 错误。
- [ ] Alembic revision 连到 0004，用 SQLite batch 迁移 CHECK 为 voting/closed/decided；保留旧行与所有外键关联。升级测试从真实 0004 数据库升级后断言旧行数量、引用、内容不变，允许写入 closed；不在用户数据库执行。
- [ ] 在同一 BEGIN IMMEDIATE 事务中查所有者、过期和状态，关闭幂等；decide 允许 voting/closed，reopen 允许 closed/decided。保持投票路径的非 voting 拒绝、邀请加入拒绝；serialize 在 closed/decided 或已投时允许 public 汇总，仍沿用字段白名单。
- [ ] 运行上述聚焦测试与 integration/test_database.py，全部通过后运行 `.venv\Scripts\python.exe -m pytest backend/tests -q --tb=no` 和 Ruff；预期全量通过。
- [ ] 记录实际 RED/GREEN、迁移与权限证据；不提交。

### Task 2: 页面与导航闭环

**Files:** 修改 `frontend/src/api/types.ts`、`features/plans/PlanPages.tsx`、`PlanNavigation.tsx`、`planPresentation.ts`（按现有职责）、`tests/PlanPages.test.tsx`、`tests/PlanNavigation.test.tsx`、`e2e/travel-plan.spec.ts`。

**Interfaces:** 消费 Task 1 的 closed 和关闭路由；页面仍使用当前 plan envelope。closed 文案统一“待决定”，不是已结束归档。

- [ ] 先补用户行为测试：确认前 put 未调用，确认后调用 `/plans/p1/voting-close`；closed 下没有投票表单，仍有确定地点和重新开放操作。请求失败保留投票中状态、显示错误。中心与导航显示待决定，卡片入口“决定目的地”。
- [ ] 运行 `node node_modules/vitest/vitest.mjs run tests/PlanPages.test.tsx tests/PlanNavigation.test.tsx`，预期新状态缺失导致失败。
- [ ] 增加关闭确认按钮，仅 owner 操作；明确说明已有票保留。closed 邀请只读；复用现有 reopen/decision。天气 closed 检查全部候选，不改评分。中心排序待决定→投票中→已决定，保留用户确认的卡片局部横滑与白卡主题。
- [ ] 聚焦、全量 Vitest、ESLint、tsc、Vite build 全通过；记录命令结果。不启动用户服务、不提交。
- [ ] 扩展 Mock E2E 关闭→邀请只读→决定／重开；等隔离服务获准启动才运行，未运行保留待验证标记。

### Task 3: 历史重查返回工作区

**Files:** 修改 `frontend/src/pages/HistoryPage.tsx`，按需创建 `features/history/restoreHistorySearch.ts`；复用 `features/search/formState.ts` 存储 API；测试 `tests/PersonalPages.test.tsx`，必要时新增 `tests/restoreHistorySearch.test.ts`。

**Interfaces:** 消费既有 `HistoryDetail {id,request,result,...}`，生成当前页 SearchResult（query_request、history_id、history_owner）和 TravelFormDraft，保存后 navigate('/')。仅推荐历史可创建计划；评估历史继续评估模式。当前登录用户名来自 useAuth，不信任历史外来 owner 字符串。

- [ ] 先用真实 MemoryRouter/Routes 测试点击重查：一次 `/history/{id}/rerun` 后停在 `/`，工作区有新结果；不跳新历史详情、不第二次 post recommendations。失败仍留历史页。
- [ ] 恢复草稿测试分别检查城市、日期、距离、同行人、风景类型、目标地点、坐标、权重。后端 4 项权重转回现有显示 3 项比例时排除 fairness，零和时沿用默认值；不重算结果评分。
- [ ] 运行聚焦 PersonalPages/恢复测试，预期当前 navigate('/history/...') 导致失败。
- [ ] 实现先保存新结果/请求/选中首候选，再导航工作区；历史查看页面保持只读。使用现有存储容错，不能以 storage 禁用导致无限跳转。
- [ ] 运行全量前端与静态/构建检查；记录失败、修正和证据。更新 PROJECT_HANDOFF、CODEX_PLAN_IMPLEMENTATION、TRAVEL_PLAN_DEMO。

## 完成边界

完成三个任务后单独自审权限、迁移、路由/缓存与隐私，不扩大修复范围。只把真实运行的测试写成通过。若浏览器服务未获允许，自动单元测试与构建可完成，但浏览器端到端仍待验证，不宣称全部完成。

当前状态：用户已批准并以 inline 方式连续实施；Task 1/2/3 代码、单元/API/迁移及静态门禁完成。扩展 E2E 文件已写但未运行，隔离服务启动与用户数据迁移需要新增批准。详细执行和未验证项见 docs/competition/VOTING_CLOSE_PROGRESS.md；步骤复核以该记录为准。未经授权不提交。
