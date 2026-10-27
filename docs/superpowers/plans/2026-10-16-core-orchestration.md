# RoamBot Core Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user and AGENTS.md prohibit subagents; execute natively in this session.

**Goal:** 在保留既有业务的前提下，通过不可变任务输入、统一提交和有限并行降低推荐等待，并提供可核验的时间、质量与用量对比。

**Architecture:** 一次结构化理解后分流业务或推荐。新推荐协调器复用已有Provider与校验，将工作任务的计算结果和运行对象的修改分开；首批优先、后批有限并行、所有卡片按批次顺序提交。保留旧编排作为隔离对照和回退。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、threading/concurrent.futures、现有SQLite缓存、pytest；React/TypeScript、Vitest、Playwright。无新依赖。

**Spec:** `docs/superpowers/specs/2026-10-16-core-orchestration-design.md`。

## Global Constraints

- 每job及进程级发现流程模型并发上限均为2，地图/天气读取沿用最多4线程及现有限速。
- 整轮最多10次模型请求、2次实际公开搜索、120秒；失败、重试和格式修复计入实际次数。
- 候选保留现有最多12项，每批发布最多6项；首批优先2–3项不同真实体验，不凑数、不重排已发布卡片。
- 语义审查保留，机械校验不交给模型；没有日期不查天气，没有中心不编路线，硬距离上限必须实际核实。
- 原业务执行器、权限、CSRF、身份、幂等、确认、历史/分享/计划数据合同和页面层级保留。
- 既有未提交修改不覆盖；无自动提交、无子代理、无换模型、无部署、不动8026。沿用当前隔离工作树。
- 分阶段批量验证；首轮真实比较最多4次推荐运行、Tavily实际credits最多4，usage未知即停止后续付费请求。
- 私有缓存按身份隔离，公共库不保存对话、位置或生成结论；缓存仅精确命中，不进行相似意图复用。

## Review Focus

1. 同一账号连续改口，较慢旧响应到达时不能覆盖新任务——Task 3、4的版本/取消测试。
2. 两个用户同时请求，后台批次不能泄露私有证据或绕过全局并发——Task 1、3的身份与共享gate测试。
3. 早批次失败而后批次已完成，不能永久等待或丢掉其他合格卡片——Task 3的失败终结和顺序测试。
4. Provider未返回usage或请求失败，费用不能记成0，额度不能被错误释放——Task 1、5的失败/未知用量测试。
5. 新历史/分享/计划改动尚未最终验收，工厂替换不能改变归档次数或对象绑定——Task 2、4、6的API业务回归。

## File Structure and Commands

新增 `domain/discovery_execution.py` 定义冻结的内部合同；
新增 `services/discovery_execution.py` 管理预算、许可和任务计时；
新增 `services/discovery_batches.py` 提供纯计算的批次准备/生成/审查；
新增 `services/discovery_orchestrator.py` 管理依赖、提交与终态。
`services/discovery.py` 提供共享内部提交出口；`services/discovery_workflow.py` 保留旧执行路径和兼容辅助逻辑。
`providers/discovery*.py` 提供可选用量回调；`api/routes/discovery.py` 只调整工厂接线。

PowerShell工作目录为本worktree；后端命令前设置：

```powershell
$taskPython = (Resolve-Path '../../.venv/Scripts/python.exe').Path
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend/src')
$taskBase = 'test-results/pytest-orchestration-' + [guid]::NewGuid().ToString('N')
```

每轮使用新的临时目录和JUnit报告；长输出写入 `test-results`，读取汇总和失败详情。
前端使用现有Node绝对路径，不安装新包。文档、测试和产物各自列出，不自动git add/commit。

### Task 1: 不可变执行合同、预算与分段记录

**Files:** 新增 `domain/discovery_execution.py`、`services/discovery_execution.py`；新增 `backend/tests/unit/test_discovery_execution.py`。

**Interfaces:**
- `BatchInput(identity: str, revision: int, sequence: int, payload_json: str, fingerprint: str)` 为冻结dataclass；内部JSON为规范化的深拷贝，不引用运行对象。
- `BatchResult(batch: BatchInput, payload_json: str)` 返回不可变任务产物。
- `ExecutionBudget(cancelled, deadline, model_limit=10, search_limit=2, clock=time.monotonic)`；`reserve(kind)` 原子计数，失败不返还，`check()` 拒绝取消和到期。
- `ModelGate(capacity=2)`；`slot(budget, priority)` 返回context manager，许可等待可取消，priority较小优先；只有HTTP实际退出才释放。
- `ExecutionTrace.record(stage, started, finished, *, batch=None, queue_ms=0, usage=None)`、`snapshot()` 返回线程安全指标；缺失usage为None。

- [ ] 写测试并运行RED：`test_frozen_batch_ignores_source_mutations`（修改原字典后payload不变）；`test_atomic_budget_counts_failed_attempts`（20线程争抢只允许10模型/2搜索）；`test_gate_limits_two_across_runs_and_retains_cancelled_inflight_slot`；`test_waiting_gate_is_cancellable_and_has_no_nested_wait`；`test_unknown_usage_is_not_zero`。
- [ ] RED命令：`& $taskPython -m pytest backend/tests/unit/test_discovery_execution.py --basetemp $taskBase -q`。预期新合同/行为尚不存在而失败，不能因拼写或测试环境失败而算RED。
- [ ] 实现上述合同、原子预算、优先许可和trace；不调用真实Provider，不引入新的数据库。
- [ ] GREEN：同一文件全部通过；使用Event/Barrier验证并行，不靠宽松时间断言。

### Task 2: 分离准备、生成、审查与统一提交

**Files:** 新增 `services/discovery_batches.py`、`backend/tests/unit/test_discovery_batches.py`；修改 `services/discovery.py`、`services/discovery_workflow.py`；复用 `services/discovery_grounding.py`。

**Interfaces:**
- `freeze_batch(run, sequence: int, ids: list[str], revision: int) -> BatchInput`：协调线程提取用户意图、证据、地点、路线/天气和规则版本。
- `BatchWorker(model, reviewer, trace)`；`compose(batch: BatchInput) -> BatchResult`、`review(batch: BatchInput, draft: BatchResult) -> BatchResult`：只调用模型并返回结果，不修改run。
- `prepare_review(batch: BatchInput, draft: BatchResult) -> BatchInput`：纯函数校验证据归属及requirements，生成冻结审查输入。
- `DiscoveryRun.commit_reviewed_batch(batch, draft, decision, *, revision: int) -> dict`：只接收内部对象，重新校验指纹/版本/取消/真实ID/路线与证据；有序追加后返回published/total/rejected。
- 旧 `act('publish_batch')` 仍执行原审查，再调用共享提交部分；新路径不再进入会重复审查的旧分支。

- [ ] 写测试并运行RED：`test_batch_compute_does_not_mutate_run`；`test_review_decision_is_bound_to_exact_draft_and_revision`；`test_cancelled_batch_cannot_publish`；`test_commit_rechecks_route_cap_and_foreign_evidence`；`test_new_commit_does_not_call_reviewer_twice`。
- [ ] 预期：缺少新接口或未阻止陈旧提交而失败；随后实现最小分离，保留现有逐卡坏引用拒绝、片段和体验规则。
- [ ] GREEN：新批次测试及 `backend/tests/unit/test_discovery.py`、`test_discovery_workflow.py` 全部通过；旧路径的实际审查次数不增加。
- [ ] 运行 `backend/tests/api/test_discovery_archives.py` 与 `test_discovery_commands.py`，确认没有重复归档或改变业务对象来源。

### Task 3: 有限并行协调器与稳定发布

**Files:** 新增 `services/discovery_orchestrator.py`、`backend/tests/unit/test_discovery_orchestrator.py`；按需要给旧helper增加独立结果接口，不在后台调用会改动共享run的方法。

**Interfaces:**
- `DiscoveryOrchestrator` 保持 `DiscoveryWorkflow` 的构造依赖、`bind_scope(actor)`、`run()`、`snapshot()`、`cancelled`、`history_id` 与 `persistence_pending` 合同，新增注入 `gate: ModelGate`。
- 协调器持有本轮 `revision`、冻结输入和各批状态（prepared/composing/reviewing/ready/failed/committed）；后台仅返回Task 1的结果。
- 路线/天气读取也返回结果，由协调器合并后冻结下一阶段输入。提名、补查和覆盖合并仍由协调器统一驱动。
- 首批开始审查后才允许后批模型生成；多个后台结果按sequence排队，只有协调线程修改公开快照。

- [ ] 写测试并运行RED：`test_next_composition_overlaps_first_review` 用两个Event互相证明重叠；`test_first_batch_gets_priority`；`test_reverse_completion_keeps_append_order`。
- [ ] 加失败场景RED：`test_failed_early_batch_unblocks_later_valid_batch`；`test_cancel_and_revision_discard_late_results`；`test_two_runs_never_share_evidence_or_coverage`；`test_missing_direction_supplement_reserves_budget_once`。
- [ ] 加硬约束RED：`test_rejected_near_candidates_do_not_hide_later_valid_candidate`，超过实际路程上限的前候选不能导致后续可行项漏查。
- [ ] 实现依赖调度和有限线程池；复用Task 1预算/gate，Task 2冻结计算与提交；没有模型任务嵌套等待同一线程池。
- [ ] GREEN：执行新协调器测试和原发现流程测试，首批、后批、取消、失败、方向缺口均保持正确终态。

### Task 4: 工厂接线、生命周期与业务回归

**Files:** 修改 `api/routes/discovery.py`；新增 `backend/tests/api/test_discovery_orchestration.py`；必要时最小调整 `services/discovery.py` job管理；保留原路由及前端合同。

**Interfaces:** 工厂在app实例共享 `ModelGate(2)`；通过内部工厂覆盖选择旧/新执行器。隔离测试显式选择新实现，默认运行实例在最终验收前仍使用旧实现；不新增供客户端绕过限制的参数。

- [ ] 写测试并运行RED：`test_new_factory_preserves_job_snapshot_contract`；`test_owner_change_and_cancel_never_archive_stale_results`；`test_terminal_archive_runs_once_after_commits`；`test_business_intake_never_searches_or_creates_recommendation_history`。
- [ ] 实现工厂共享gate和新旧实现接线；保留业务分流、现有history恢复/重查/分享及计划快照API。
- [ ] GREEN：上述测试及 `test_discovery_jobs.py`、`test_discovery_commands.py`、`test_discovery_archives.py`、既有command与plan API相关测试通过。
- [ ] 与当前浏览器Mock合同核对：新增指标仅增量扩展，不能依赖前端知道后台批次状态。

### Task 5: 减少重复输入、精确复用与真实用量

**Files:** 修改 `providers/discovery_workflow.py`、`providers/discovery.py`、`services/discovery_batches.py`；必要时复用 `persistence/discovery_cache.py`；新增 `backend/tests/unit/test_discovery_model_usage.py`。

**Interfaces:** `structured_call(..., *, record_usage=None)` 保持既有返回模型类型；`review_batch(..., *, record_usage=None)` 保持旧参数兼容；回调仅接收响应usage，未知为None，不记录原prompt或凭据。

- [ ] 写测试并运行RED：`test_usage_callback_preserves_unknown_and_failed_counts`；`test_compact_payload_preserves_negation_role_and_source_scope`；`test_exact_private_cache_invalidates_reason_date_evidence_and_identity`；`test_failed_or_rejected_review_is_not_cached_as_approved`。
- [ ] 将冗余地图元数据、重复证据和无关段落从模型输入删除，保留意图原文、改口、硬限制、片段ID、来源和时效；沿用现有每卡具体理由，不放宽事实标准。
- [ ] 仅在新 `BatchWorker` 接入短时私有精确输入缓存：组合完整输入指纹及身份/规则版本，TTL最多300秒，实际路线和天气仍遵守原TTL；缓存命中不新增模型请求。旧 `DiscoveryWorkflow` 仍保留现有不缓存个性化生成的基线，不删除或修改 `test_repeat_query_reuses_facts_but_does_not_cache_personalized_model_replies` 的原断言。
- [ ] GREEN：新用量/缓存测试、旧Provider解析/未知ID/跨实体证据/时效/草地反例回归通过。
- [ ] 保存旧/新可控延迟重放报告：同时列wall time和各阶段累计时间，不能把并行累计时间相加冒充总时间。

### Task 6: 集中验收、有限真实对比与本地切换

**Files:** 新增 `docs/core-orchestration-acceptance.md`；追加 `docs/PROJECT_HANDOFF.md`、更新 `docs/conversational-goal.md` 的本轮状态；新增测试侧 `scripts/benchmark_discovery_orchestration.py`（只在显式参数下调用真实Provider，不自动加载或输出凭据）。

**Interfaces:** 基准脚本输入旧/新工厂、冻结资料/缓存初始快照、需求列表及调用预算；输出每次运行版本、首批/全部时间、实际结果、issues、模型次数/token、搜索usage。原始结果不覆盖。

- [ ] 先为benchmark写测试并运行RED：`test_benchmark_compares_identical_initial_cache_without_real_calls`；`test_live_budget_stops_on_unknown_usage`，默认离线且不能误触真实Provider。
- [ ] 实现benchmark及独立测试目录；对比时每次从相同缓存初始状态复制到隔离临时目录，不删除或污染已有运行数据。
- [ ] 后端全量：`& $taskPython -m pytest backend/tests --basetemp $taskBase --junitxml=test-results/orchestration-backend.xml -q`。通过后仅在新改动或失败原因要求时重跑。
- [ ] 前端在 `frontend` 下设置 `$taskNode='C:\Users\24188\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'`，分别运行 `& $taskNode node_modules/vitest/vitest.mjs run`、`& $taskNode node_modules/typescript/bin/tsc -b`、`& $taskNode node_modules/eslint/bin/eslint.js .`、`& $taskNode node_modules/vite/bin/vite.js build`、`& $taskNode node_modules/@playwright/test/cli.js test --config playwright.discovery.config.ts`。浏览器覆盖desktop/mobile/reduced-motion，失败保留断言并定位。
- [ ] 沿用授权做最多4次推荐真实对比（已有资料、新地区，各新旧一次，串行执行），Tavily credits最多4。另核对原常见业务分流仍复用一次理解，实际变更在隔离业务数据中验证。
- [ ] 结果要求：无新增推荐错误、无硬限制/权限回归、搜索预算未超；已有资料样本首批及全部时间相对同条件旧基线各至少改善20%。若不达标，旧默认保留，报告原因，不伪称完成。
- [ ] 达标后才将工厂默认切换到新编排，并复验工厂专项；仅更新本地8033，核验进程、源码哈希、实际HTTP资源和一轮限定烟测；8026与Railway保持不动。
- [ ] 更新验收文档：已修改、自动测试、浏览器、真实模型和残余项分开。真实小样本不报告P95或普遍准确率；Safari、真机与全站聊天目标未覆盖部分继续明确记录。

## Handoff and Self-review

本计划原生执行，禁止子代理和自动提交。前述六个任务共用一份本计划专属ledger，记录RED/GREEN、变更和裁决；已完成任务不重复。
合同在Task 1定义、Task 2消费；Task 3组合计算与提交；Task 4保持现有API；Task 5不改变其返回类型；Task 6验证与切换。
已有历史/计划源码仅作为兼容边界，不先回滚，也不借本计划宣称其全部真实验收完成。
当前只完成计划编写；用户审阅本计划后进入Task 1，尚未运行或修改产品编排代码。
