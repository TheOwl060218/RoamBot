# 执行记录 — plan: docs/superpowers/plans/2026-10-06-plan-voting-close.md

2026-10-06：用户批准连续执行；当前 branch experiment/ui-clean-a，HEAD 00f4e80，保留所有已有未提交修改。

Ruling: 不新建 worktree、不分派子智能体、不按技能默认提交 — 用户/仓库明确要求保留本工作区与未提交改动，禁止子智能体 — 代价为最终作者自审弱于独立审查。
Ruling: Windows 下直接用本文追踪步骤，不运行 Bash 记账脚本 — 复用项目既有 Markdown 证据，避免引入新工具链 — 保留测试命令及结果，不能靠提交范围恢复阶段。
Pre-flight: Task 1 输出 closed/envelope，Task 2 消费同名状态/接口；Task 3 复用历史响应独立回流，不复用或伪造计划状态。

## Task 1 — 实现与自动化通过

关闭 API/权限/幂等/过期/公开汇总、重开保留票、关闭后决定已实现。迁移 0005 重建 SQLite CHECK 时仅在迁移连接关闭 FK 检查，之后检查关联完整性并恢复；升级测试从 0004 插入旧计划、候选、参与者、首选和可接受票，连续升级两次后内容仍在。

RED: `pytest backend/tests/api/test_plans.py backend/tests/integration/test_database.py -q --tb=short`，4 failed / 17 passed，新增三条关闭流程缺路由，新增迁移测试因旧 CHECK 不允许 closed 失败。
初次实现后 20 passed / 1 failed：原有 head 检查仍断言 0004，按新迁移链更新为 0005；不是功能 RED。最终新增关闭与匿名投票 Barrier 并发测试（不伪称 RED），允许锁先后的 200/409 两种正确结果，关闭响应之后票数不再变化。
最终 `pytest backend/tests -q --tb=no`：**316 passed**；`ruff check backend`：退出 0。

## Task 2 — 实现通过，浏览器待验

页面四项新增契约 RED：4 failed / 8 passed（缺少结束按钮、closed 状态文案、中心优先排序）。实现确认操作、失败保留投票中、邀请页只读与决定/重开操作后，PlanPages + PlanNavigation 聚焦 **15 passed**。导航 closed 展示用例是在实现后补充，不能写成独立 RED。白卡主题和局部横滑沿用原布局。

## Task 3 — 实现与自动化通过

RED: PersonalPages 返回了“不应进入历史详情”页面；恢复模块 import 不存在。首次 GREEN 排查发现历史页引入 useAuth 后旧测试缺 AuthProvider，补真实上下文包装（测试环境修正，不是产品缺陷）。之后个人页与恢复测试通过。
作者自审追加：存储不可写但可读旧草稿时，当前查询显示旧城市；比例四舍五入可能合计 101。两个有效 RED（2 failed / 10 passed）后，摘要优先使用本次路由恢复的草稿，距离权重限于剩余比例，合计恢复为 100。首次缓存测试用了不完整旧草稿并触发异常，随后修正为完整有效旧草稿重新确认真实文案失败，未把 fixture 错误当功能 RED。

Ruling: 回流数据除 sessionStorage 外还通过 navigate state 传递，SearchPage 在新的 location.key 挂载工作区 — 存储禁用不能让新结果丢失或恢复旧结果 — 增加 SearchPage/SearchWorkspace/TravelForm 的窄初始化接口，无额外网络请求。字段恢复包括日期、坐标、同行地、景观、评估地点和权重；history_owner 来自当前账户，不信任外来字段。

## 最终门禁（本轮实际执行）

- 仓库根：`.venv\Scripts\python.exe -m pytest backend/tests -q --tb=no` → **316 passed**。
- 仓库根：`.venv\Scripts\python.exe -m ruff check backend` → 退出 0。
- frontend：`node node_modules/vitest/vitest.mjs run` → **20 文件，117 passed**。
- frontend：`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b` → 分别退出 0。
- frontend：`node node_modules/vite/bin/vite.js build` → 1855 modules；CSS 50.76 kB / JS 385.58 kB，退出 0。
- 本机 Node 24.19.0、已有 .venv Python 3.12.14；实际命令使用已定位 Node 全路径以避开 PATH 差异；没有安装/升级依赖。

## 作者自审及未验证边界

按 requesting-code-review 检查权限、迁移、缓存与边界；仓库禁止子智能体，所以仅作者自审，无独立审查。权限在 WRITE 会话/CSRF 与 owned 检查内；关闭、加入、owner/guest 投票、决定均在 SQLite BEGIN IMMEDIATE 内检查状态。公开数据继续白名单序列化。历史失败不跳转、不清旧结果；查看快照仍只读。

`frontend/e2e/travel-plan.spec.ts` 已扩展关闭→同行者只读→重开保留→关闭后决定，以及历史重查回工作区；**未启动服务、未运行该 E2E**，不得沿用此前 12/2 通过作为本轮证据。

完成边界：三个任务的代码及自动化门禁完成；浏览器视觉/端到端验收仍待授权隔离 Mock 服务后执行。当前用户数据库迁移也未获执行授权。`create_all` 不能更新已有 CHECK；有 0004 基线与无 Alembic 版本的库需区别处理，先停写备份和审核 schema，再在副本验证，不能盲目 stamp。本轮所有迁移测试使用临时测试库，未更改真实账户或计划数据。

不评价/不执行：Live 供应商、公网部署、真实手机触摸、用户现有服务重启（超出授权）；历史时期不完整请求的兼容（本次只覆盖既有接口当前合法模型，遇到实际失败再定位）。未 commit/push/PR/merge、未 Docker。

## 用户随后批准：真实本地演示库备份、升级与启动

用户确认使用 `data-competition-demo`，授权审核、备份、迁移并重启。没有发现运行中的 RoamBot Uvicorn 进程；未结束其他服务。

只读审核发现演示库和默认 data 库均无 alembic_version、travel_plans CHECK 仍为 voting/decided，完整性与外键正常。仅修改用户选择的演示库，默认 data 库未改。SQLite backup 原库存于 `data-competition-demo/backups/before-0005-20261006-201314/roambot-before-0005.db`；副本、审计摘要和本地维护脚本均在被 Git 忽略的演示数据目录，不作为比赛交付物上传。

升级前与标准 0004 数据库逐项比对全部业务表：列类型/空值/default/主键、唯一约束、索引、外键以及 CHECK 相同；因此有证据将未版本化旧库标记 0004，而非盲目 stamp。先升级备份副本到 0005，逐表比较行数与内容 SHA256 摘要不变；再次确认原库和备份未变化后才对原演示库执行 stamp 0004 + upgrade head。升级后全部业务记录摘要不变，revision=0005、integrity_check=ok、foreign_key_check=0。

启动已有 .venv Uvicorn，显式 Mock/demo、数据库绝对路径和名称、secure cookies=false，绑定 127.0.0.1:8000。启动 Vite 绑定 127.0.0.1:5173（strictPort）；都使用隐藏后台进程，无 Docker、无安装/下载。health 200；OpenAPI 关闭路由存在，OwnedPlan/PublicPlan status enum 为 voting/closed/decided；前端 200、经 Vite 代理 health 200 ready。

初次 schema 检查使用了不存在的 TravelPlanResponse 名称得到 False，随后按真实 OwnedPlan/PublicPlan 核对确认正确，属于检查脚本定位问题，不是功能缺陷。没有登录用户账户或操作实际计划来测试。未运行浏览器完整 E2E，不能据 HTTP 200 宣称 UI 全链路验收完成。启动保留供用户测试；用户可使用同一浏览器和原账户继续，备份含私人数据需保留在本机。

本次进程记录：后端 launcher 83548 / Uvicorn worker 92060，前端 Vite 93828。若仍是这次进程，停止可用 `Stop-Process -Id 83548,92060,93828 -ErrorAction SilentlyContinue`；后续重新启动后 PID 会改变，不应盲目复用。日志在被忽略的 data-competition-demo 内，未提交、未推送。
