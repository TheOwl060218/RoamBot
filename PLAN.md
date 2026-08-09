# PLAN: RoamBot

## 0. 执行规则

- 产品边界以 `SPEC.md` 为最高依据；本计划不得扩展地图、路线、导航、逐日行程、手机号、短信、验证码、邮箱、OAuth 或密码找回。
- 本文件是陌生 agent 冷启动时可独立阅读的执行入口。`docs/superpowers/plans/` 中的一份路线图和四份子计划提供逐步代码片段与提交边界，但不得改变本文件和 SPEC 的接口语义。
- 实现严格按 M1、M2、M3、M4 顺序进行。每个任务执行红、绿、重构：先写并运行失败测试，再写最小实现，再运行聚焦测试和里程碑完整验证。
- 自动测试和 CI 固定使用 mock provider，不需要真实 API key，也不得产生真实高德、QWeather 或 LLM 调用。
- 真实凭据只在 M4.7 人工 smoke 前申请，并由用户通过本机隐藏 CLI 录入加密凭据库，不进入聊天、`.env`、源代码、Git、日志、Docker 镜像或 CI。
- 一个任务的验证没有通过时，不进入后续任务；不以“看起来正确”代替命令证据。
- 本计划中“运行 Ruff”固定指令为 `./.venv/Scripts/python.exe -m ruff check backend`；“完整 backend 测试”固定指令为 `./.venv/Scripts/python.exe -m pytest backend/tests -q`。不得用未写明的 IDE 检查代替。
- 前端聚焦测试固定使用 `npm --prefix frontend test -- <测试文件名>`，完整前端检查固定依次运行 `npm --prefix frontend test`、`npm --prefix frontend run lint`、`npm --prefix frontend run build`；这些 scripts 由 M3.1 固定创建。除已标明完成的 Task 1.1/1.2 外，当前 M1-M4 的 37 个实施任务状态全部为“待实施”，尚无产品代码；任务完成后必须在本文件和 `TASKS.md` 同步状态。

## 1. 规约与计划

### Task 1.1 Superpowers brainstorming

- 状态：已完成，用户已批准 `docs/plans/2026-07-15-roambot-design.md`。
- 证据：`SPEC_PROCESS.md` 记录 38 次迭代，`DECISIONS.md` 记录锁定决策。

### Task 1.2 Superpowers writing-plans

- 状态：已完成一份路线图和四份可执行子计划。
- 文件：
  - `docs/superpowers/plans/2026-07-15-roambot-roadmap.md`
  - `docs/superpowers/plans/2026-07-15-roambot-01-core-backend.md`
  - `docs/superpowers/plans/2026-07-15-roambot-02-accounts-and-data.md`
  - `docs/superpowers/plans/2026-07-15-roambot-03-react-webui.md`
  - `docs/superpowers/plans/2026-07-15-roambot-04-providers-and-delivery.md`
- 验证：必需标题、任务复选框、占位符、跨计划接口、凭据边界和 `git diff --check` 全部通过。

### Task 1.3 陌生 agent 冷启动验证

- 输入边界：只给陌生 agent `SPEC.md` 与 `PLAN.md`，不提供当前聊天或口头补充。
- 要求：选择两个不同层次的任务，复述目标，列出文件、第一条失败测试、最小实现和验证命令，并指出歧义。
- 通过标准：agent 能在不自行发明产品规则的情况下开始 TDD；发现的问题回填 `SPEC.md`、`PLAN.md` 和 `SPEC_PROCESS.md` 后再复测。

## 2. M1 核心后端 Mock 垂直切片

完整步骤见 `docs/superpowers/plans/2026-07-15-roambot-01-core-backend.md`。

### M1.1 Python 包与健康检查

- 文件均为 Create：`backend/pyproject.toml`、`backend/src/roambot/__init__.py`、`backend/src/roambot/main.py`、`backend/src/roambot/api/__init__.py`、`backend/src/roambot/api/routes/__init__.py`、`backend/src/roambot/api/routes/health.py`、`backend/tests/api/test_health.py`。
- 公开入口固定为 `roambot.main.create_app() -> FastAPI` 和模块级 `roambot.main.app = create_app()`；health router 导出 `router`。ASGI/Docker 使用 `roambot.main:app`，测试调用 `create_app()` 保持隔离。
- 启动顺序：本机开发使用 Codex bundled Python 3.12.13；创建 `backend/pyproject.toml` 与空 `backend/src/roambot/__init__.py`；再运行该解释器的 `-m venv .venv`、`./.venv/Scripts/python.exe -m pip install --upgrade pip`、`./.venv/Scripts/python.exe -m pip install -e "./backend[dev]"`。pyproject 使用 hatchling，runtime 为 FastAPI/httpx/Pydantic/Uvicorn，dev 为 httpx2（Starlette TestClient）、pytest/pytest-cov/Ruff；兼容范围固定为 `>=3.12,<3.14`，Docker 与 GitLab CI 仍使用 Python 3.13 验收。
- 第一条失败测试：`from roambot.main import create_app`，`TestClient(create_app()).get("/api/v1/health")` 必须得到 200 和严格 JSON `{"status":"ready"}`；在只存在包 `__init__.py` 时运行，预期因 `roambot.main` 不存在而 import FAIL。
- 最小实现：创建 API 包、`create_app`、模块级 app 和 health router；FastAPI title=`RoamBot API`、version=`0.1.0`，router prefix=`/api/v1`。不接数据库、推荐服务或 provider。
- 验证：红阶段/绿阶段均运行 `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_health.py -q`；绿阶段预期 `1 passed`，再运行 Ruff 预期退出 0。

### M1.2 请求、响应与领域模型

- 文件均为 Create：`backend/src/roambot/domain/models.py`、`backend/tests/unit/test_models.py`。
- 公开类型：`SceneryType`、`SceneryMatchMode`、`SourceKind`、`Coordinate`、`RankingWeights`、`TravelRequestBase`、`RecommendationRequest`、`PlaceEvaluationRequest`、`Origin`、`Destination`、`DailyWeather`、`DailySuitability`、`DistanceEstimate`、`GroupAccessibilityScore`、`ScoreBreakdown`、`SourceState`、`RecommendationItem`、`RecommendationResponse`、`PlaceEvaluationResponse`；字段、JSON 枚举值、默认和可空性逐项以 SPEC“领域/API 模型固定契约”为准。
- 第一条失败测试：导入 `RecommendationRequest`，使用 `scenery_types=["lake"]`、三个出发地、50 km、`Asia/Shanghai` 今天至 `today+6` 构造成功并得到 city“苏州”；空地址、三个 companion、0/501 km、空/重复风景、`today+7`、单人非零 fairness、隐藏模式字段即使 null 均用 `pytest.raises(pydantic.ValidationError)` 失败。初次预期模块 import 失败。
- 最小实现：Pydantic v2 frozen/extra-forbid/finite models；空白 trim，空城市回退苏州但 null 拒绝；weights 省略保持 None；`scenery_match_mode` 默认 any；日期使用 `Asia/Shanghai` 今天至今天后第 6 天闭区间。M1.2 定义全部上述类型，不实现评分、provider、路由或持久化。
- 验证：红阶段运行 `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py::test_recommendation_request_boundaries -q` 预期 import FAIL；绿阶段运行 `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py -q` 预期全部 PASS，再运行 Ruff。

### M1.3 风景分类规则

- 文件：`backend/src/roambot/domain/scenery_rules.py`、`backend/src/roambot/domain/scenery.py`、`backend/tests/unit/test_scenery.py`。
- 第一条失败测试：金鸡湖的名称和高德类型得到湖景与公园双标签；人工修正覆盖普通规则；未知地点返回空标签。
- 最小实现：按人工修正、`type/typecode` 词项、名称词项的顺序生成确定性多标签，不调用 LLM。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scenery.py -q`。

### M1.4 天气、距离、公平性、热度与排序

- 文件均为 Create：`backend/src/roambot/domain/scoring.py`、`backend/src/roambot/domain/ranking.py`、`backend/tests/unit/test_scoring.py`、`backend/tests/unit/test_ranking.py`。
- 公开接口：`clamp(value)->float`、`score_daily_weather(DailyWeather,frozenset[SceneryType])->DailySuitability`、`aggregate_weather(list[float])->float`、`score_distance(distance_km,max_distance_km)->float`、`score_fairness(list[float],max_distance_km)->float`、`score_popularity(rank,local_bonus=0)->float`、`normalize_weights(RankingWeights)->dict[str,float]`、`final_score(weather,distance,fairness,popularity,weights,coverage_ratio)->float`。
- 第一条失败测试：从 `roambot.domain.scoring` 导入 `aggregate_weather`，断言 `[90,85,30]` 得 `pytest.approx(56.833333, rel=1e-5)`，初次因模块不存在而 import 失败；随后覆盖 `score_distance(20,100)==80`、公平性大小关系、热度 rank 1=100/rank 25=4、权重 `4/3/0/3` 归一化和覆盖扣分。
- 最小实现：按 SPEC 天气阈值；距离用所有出发地平均距离的线性公式；公平性用总体标准差线性公式；热度为 `100-4*(rank-1)+bonus` 且 V1 bonus 表为空；所有组件 `clamp`/round 两位。`final_score` 使用四项归一化加权后扣 `20*(1-coverage_ratio)` 并再次 clamp；`ANY` 传 1，指定评估也传 1。服务层排序键固定为 `(-total, primary_distance, NFKC(name).strip(), provider_id)`。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scoring.py backend/tests/unit/test_ranking.py -q` 绿阶段全部 PASS；再运行 `./.venv/Scripts/python.exe -m ruff check backend`，预期退出 0。

### M1.5 Provider 协议与苏州 Mock

- 文件：`backend/src/roambot/providers/protocols.py`、`backend/src/roambot/providers/mock.py`、`backend/tests/unit/test_mock_providers.py`。
- 公开接口：`PlaceProvider.search(...,scenery_types:tuple[SceneryType,...],...)` 保留请求顺序；其余 geocoder/distance/weather/explanation 为同步协议。风景标签仍使用 `frozenset`，只有用户检索类型使用有序 tuple。
- 第一条失败测试：mock 可解析苏州站、检索金鸡湖、测量 1-3 个出发地距离、返回固定三日天气和模板解释；未知地址返回稳定 `ProviderError`。
- 最小实现：定义 geocoder、place、distance、weather、explanation 五个同步协议和完全确定性的苏州 provider bundle。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_mock_providers.py -q`。

### M1.6 推荐与指定地点评估服务

- 文件：`backend/src/roambot/services/recommendations.py`、`backend/tests/unit/test_recommendation_service.py`。
- 第一条失败测试：推荐先按主出发地最大距离硬过滤再排序；指定地点评估只返回目标地点；LLM 失败不改变分数和排名。
- 最小实现：编排五个 provider，应用单人 `40/30/0/30` 和多人 `40/0/40/20` 默认权重，允许用户权重归一化，最多返回五项并附 `SourceState`。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_recommendation_service.py -q`。

### M1.7 核心 API 与错误信封

- 文件：`backend/src/roambot/api/errors.py`、`backend/src/roambot/api/dependencies.py`、`backend/src/roambot/api/routes/recommendations.py`、`backend/tests/api/test_recommendations.py`。
- 第一条失败测试：游客 `POST /api/v1/recommendations` 返回排序结果和 demo 来源；非法距离返回 422 `validation_error`；指定目标不存在返回 404 `place_not_found`。
- 最小实现：提供两个核心 POST，使用统一 `{"error":{"code","message","fields"}}`，出发地找不到映射 422，目标地点找不到映射 404，provider 不可用映射 503。
- 验证：运行完整 backend pytest 与 Ruff，并检查 OpenAPI 中不存在凭据管理路由。

### M1.8 里程碑验证

- 文件：`backend/README.md`、`AGENT_LOG.md`。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q`、Ruff、`git diff --check`；结果必须无需网络和真实凭据。

## 3. M2 账户、SQLite 与个人数据

完整步骤见 `docs/superpowers/plans/2026-07-15-roambot-02-accounts-and-data.md`。

### M2.1 SQLite 与 Alembic

- 状态：已完成，提交 `f2e646f`。

- Modify：`backend/pyproject.toml`。Create：`backend/src/roambot/config.py`、`backend/src/roambot/persistence/__init__.py`、`database.py`、`tables.py`、`backend/alembic.ini`、`backend/alembic/env.py`、`script.py.mako`、`backend/alembic/versions/__init__.py`、`0001_accounts_and_data.py`、`backend/tests/integration/test_database.py`。
- 第一条失败测试：对 Alembic `Config("backend/alembic.ini")` 注入临时 SQLite URL，连续两次 `upgrade head` 后，业务表严格为 SPEC 的七张，全部表严格为这七张加 `alembic_version`；外键、唯一约束和索引与 SPEC 一致。初次因 Alembic 配置/迁移不存在而失败，不用 `metadata.create_all` 冒充迁移测试。
- 最小实现：添加 SQLAlchemy 2/Alembic/pydantic-settings，按 SPEC 精确列类型、FK cascade、约束与索引建立映射和 `0001`；SQLite 每连接启用 foreign keys。`alembic.ini` URL 留空，env.py 优先接受测试注入 URL，否则使用 `ROAMBOT_DATA_DIR/roambot.db`。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/integration/test_database.py -q`、完整 backend 测试和 Ruff；另在临时 `ROAMBOT_DATA_DIR` 下执行 `./.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head`，均退出 0。

### M2.2 密码、会话与 CSRF 基础

- 状态：已完成，提交 `f2e646f`。

- 文件：`backend/src/roambot/security/passwords.py`、`backend/src/roambot/security/sessions.py`、`backend/tests/unit/test_security.py`。
- 第一条失败测试：Argon2 哈希不含明文且可验证；session、CSRF 和 share token 的数据库值只保存 SHA-256 哈希。
- 最小实现：Argon2、不可预测 token、`secrets.compare_digest` 所需哈希帮助函数。
- 验证：安全单元测试与 Ruff。

### M2.3 认证服务

- 状态：已完成，提交 `f2e646f`。

- 文件：`backend/src/roambot/persistence/repositories.py`、`backend/src/roambot/services/auth.py`、`backend/tests/integration/test_auth_service.py`。
- 第一条失败测试：注册在一个事务中创建用户和 24 小时 session grant；用户名规则 `^[A-Za-z0-9_]{3,32}$`、密码 8-128 字符、重复名失败、未知用户名与错误密码返回相同错误、过期或撤销会话不可用；轮换 CSRF 后旧哈希失效但 session 到期时间不变。
- 最小实现：`register/login -> SessionGrant(user_id,username,session_token,csrf_token,expires_at)`；`authenticate -> AuthenticatedSession(session_id,user_id,username,csrf_hash,expires_at)`；`rotate_csrf(session_token)` 原子替换哈希并返回新明文；`logout` 撤销 session。repositories 只接收 token 哈希，永不接收或返回明文密码与 token。
- 验证：认证服务测试、完整 backend 测试和 Ruff。

### M2.4 认证 API 与 CSRF

- 状态：已完成，提交 `f37a5f0`。

- 文件：`backend/src/roambot/api/routes/auth.py`、`backend/src/roambot/api/dependencies.py`、`backend/tests/api/test_auth.py`。
- 第一条失败测试：注册 201 且自动登录，注册/登录都返回 `{"user":{"username":"alice_01"},"csrf_token":"<opaque>"}`，设置 `roambot_session` 的 `HttpOnly; SameSite=Lax; Path=/; Max-Age=86400` Cookie；`/me` 原子轮换 CSRF；旧 CSRF 或缺失 CSRF 的退出返回 403；成功退出为 204 空响应。
- 最小实现：`/auth/register|login` 创建固定 24 小时会话并设置 Cookie；`/auth/me` 只从 Cookie 认证，在数据库事务中替换 `csrf_hash` 后返回新明文；认证响应 `Cache-Control: no-store`；logout 校验 CSRF、撤销会话并用相同 Path/SameSite/Secure 属性清除 Cookie。JSON 永不返回 session token。
- 验证：认证 API 测试、完整 backend 测试和 Ruff。

### M2.5 收藏

- 状态：已完成，提交 `c4a150f`。

- 文件：`backend/src/roambot/services/personal_data.py`、`backend/src/roambot/api/routes/favorites.py`、`backend/tests/api/test_favorites.py`。
- 第一条失败测试：游客失败；首次收藏 201、重复收藏同一 ID 返回 200；Bob 删除 Alice 收藏得到 404；收藏不含天气、评分和解释。
- 最小实现：按用户和地点唯一约束保存地点元数据，GET 要登录，POST/DELETE 要登录和 CSRF，所有查询带 `user_id` 条件。
- 验证：收藏测试、完整 backend 测试和 Ruff。

### M2.6 历史

- 状态：已完成，提交 `c4a150f`。

- 文件：`backend/src/roambot/services/personal_data.py`、`backend/src/roambot/api/routes/history.py`、`backend/src/roambot/api/routes/recommendations.py`、`backend/tests/api/test_history.py`。
- 第一条失败测试：游客查询不写历史；登录用户完整成功结果写一条不可变快照；失败请求不写；rerun 新增 ID；跨用户读删改均失败。
- 最小实现：只在完整结果形成后用短事务写结构化请求和响应；有效缓存、demo、直线估算、部分候选天气排除和模板解释均作为带说明的成功历史；删除/清空不影响收藏。
- 验证：历史测试、完整 backend 测试和 Ruff。

### M2.7 匿名只读分享

- 状态：已完成，提交 `f3b8012`。

- Create：`backend/src/roambot/api/routes/shares.py`、`backend/tests/api/test_shares.py`。Modify：`backend/src/roambot/persistence/repositories.py`、`backend/src/roambot/services/personal_data.py`、`backend/src/roambot/api/routes/history.py`、`backend/src/roambot/main.py`。
- 公开接口：`ShareRepository.create_replacing_active(owner_user_id,history_id,token_hash,now)`、`.get_public_by_token_hash()`、`.revoke_owned()`、`.revoke_for_history()`；personal-data service 负责所有权和脱敏投影，路由不得直接操作 SQL。
- 第一条失败测试：Alice 对自己的 history POST 后严格得到 201 `{"share":{"id","history_id","url","created_at"}}`，URL 匹配 `/share/<43-char URL-safe token>` 且数据库不含明文；再次 POST 得新 share/URL，旧 public URL 立即 404 `share_unavailable`；Bob 创建/撤销为 404；公开 JSON 严格匹配 SPEC snapshot 且递归扫描无任何 origin/身份/内部 ID。初次因 share route 404 失败。
- 最小实现：每次创建在一事务撤销旧活动 share 并生成新 32-byte token；私有创建/撤销校验 session+CSRF+owner。公开 GET 只联查活动 share 和仍存在的历史，再投影固定 snapshot；不调用 provider。历史单删/清空在同事务撤销关联 shares；main 注册私有与公开 router。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/api/test_shares.py backend/tests/api/test_history.py -q`、完整 backend 测试和 Ruff 均退出 0。

### M2.8 Provider 缓存仓储

- 状态：已完成，提交 `f3b8012`。

- 文件：`backend/src/roambot/persistence/repositories.py`、`backend/tests/integration/test_cache_repository.py`。
- 公开接口：`CacheEntry(cache_key,provider,operation,payload_json,created_at,expires_at)`；`CacheRepository.get_fresh(cache_key,now)->CacheEntry|None`、`.put(cache_key,provider,operation,payload_json,created_at,expires_at)->None`、`.delete(cache_key)->None`、`.delete_expired(now)->int`；时间只接受 aware UTC。
- 第一条失败测试：固定 UTC 时钟下，未过期 JSON 可取，到期时立即 miss，upsert 原子替换，删除过期项不删除新鲜项。
- 最小实现：稳定 JSON 序列化；key 为 provider、操作和规范化参数的 SHA-256，不含凭据。
- 验证：缓存测试、完整 backend 测试和 Ruff。

### M2.9 加密凭据库与本机 CLI

- 状态：已完成；TDD、完整验证与安全评审证据见 `AGENT_LOG.md`。

- 文件：`backend/src/roambot/security/vault.py`、`backend/src/roambot/cli.py`、`backend/tests/unit/test_vault.py`、`backend/tests/integration/test_credentials_cli.py`。
- 第一条失败测试：文件字节和 CLI 输出均不含主密码或三种 fake key；错误主密码不能返回部分数据；reset 只删 vault，不删同目录 SQLite。
- 最小实现：Scrypt 参数 `n=32768,r=8,p=1` 派生 32 字节，AES-256-GCM 认证加密，原子写入；Typer 隐藏输入提供 init/status/set/clear/reset。
- 验证：vault、CLI、完整 backend 测试和 Ruff；不要求真实 key。

### M2.10 里程碑验证

- 状态：已完成；最终测试计数、迁移与秘密扫描证据见 `AGENT_LOG.md`。

- 文件：`backend/README.md`、`AGENT_LOG.md`。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests -q`、Ruff、Alembic 临时数据库、`git diff --check`。

## 4. M3 React 响应式 WebUI

完整步骤见 `docs/superpowers/plans/2026-07-15-roambot-03-react-webui.md`。

### M3.1 Vite、测试入口与应用壳

- Scaffold/Create 的完整边界：`frontend/package.json`、`package-lock.json`、`index.html`、`vite.config.ts`、`tsconfig.json`、`tsconfig.app.json`、`tsconfig.node.json`、`eslint.config.js`、`src/vite-env.d.ts`、`src/main.tsx`、`src/app/AppShell.tsx`、`src/app/router.tsx`、`src/pages/PlaceholderPage.tsx`、`src/styles/tokens.css`、`src/styles/app.css`、`tests/setup.ts`、`tests/AppShell.test.tsx`。先用 `npm create vite@latest frontend -- --template react-ts` 生成标准入口/配置，再安装 React Router、TanStack Query、Lucide、Vitest/jsdom/Testing Library/Playwright；不得手写 `package-lock.json`。
- `package.json` scripts 固定为 `dev:vite`、`build:tsc -b && vite build`、`lint:eslint .`、`test:vitest run`、`test:watch:vitest`、`e2e:playwright test`。Vite/Vitest 配置 `environment="jsdom"`、`setupFiles="./tests/setup.ts"`，开发代理 `/api` 到 `http://127.0.0.1:8000`。
- 公开接口：`AppShell({children}:PropsWithChildren)->JSX.Element`，语义结构固定为 header/nav/main；导航链接为 RoamBot(`/`)、推荐(`/`)、收藏(`/favorites`)、历史(`/history`)，账户按钮使用 Lucide `UserRound` 且 `aria-label="账户"`。router 先把 `/`、`/favorites`、`/history`、`/share/:token` 指向只有短标题的 `PlaceholderPage`；后续 M3.4-M3.6 逐项替换，占位页不是最终交付。
- 第一条失败测试：用 `MemoryRouter` 渲染 `<AppShell><div>工作区</div></AppShell>`，断言四个链接/账户按钮、`main` 内“工作区”；初次因 `AppShell.tsx` 不存在而 import FAIL。M3.1 不断言主出发地或“开始推荐”，避免提前实现 M3.3。
- 最小实现：Node 24 + React 19 + TypeScript/Vite 基础、完整构建入口、路由壳和克制样式 token；不实现表单、查询、结果、地图、路线或营销 hero。SPEC 的“首屏直接可操作”是 M3.3 表单和 M3.4 workspace 接入后的 M3 里程碑退出条件，不是 M3.1 独立交付。
- 验证：`npm --prefix frontend test -- AppShell.test.tsx`、`npm --prefix frontend run lint`、`npm --prefix frontend run build` 均退出 0。

### M3.2 类型化 API 客户端与认证上下文

- 文件：`frontend/src/api/types.ts`、`frontend/src/api/client.ts`、`frontend/src/features/auth/AuthProvider.tsx`、对应 Vitest。
- 第一条失败测试：请求前缀 `/api/v1`、携带 Cookie、注册/登录/`/auth/me` 更新内存 CSRF、mutation 发送 `X-CSRF-Token`；403 `csrf_invalid` 只触发一次 single-flight `/auth/me` 刷新并只重试原 mutation 一次；刷新 401 清空认证状态；稳定错误信封解析为 `ApiError`。
- 最小实现：镜像 backend 类型，CSRF 只保存在模块内存；启动时 `/auth/me` 的 401 表示游客，不是全局错误。刷新调用不得递归重试，多个并发 403 共用同一刷新 Promise，原 mutation 最多执行两次。
- 验证：API/client tests、frontend build 和 lint。

### M3.3 双模式表单与权重

- 文件均为 Create：`frontend/src/features/search/TravelForm.tsx`、`OriginFields.tsx`、`ScenerySelector.tsx`、`WeightSegments.tsx`、`formState.ts`、`frontend/src/styles/forms.css`、`frontend/tests/TravelForm.test.tsx`、`WeightSegments.test.tsx`。本任务不接 AppShell；M3.4 的 `SearchWorkspace` 消费该表单并接入 API。
- 公开接口：`TravelFormProps = {initialMode?: "recommendation"|"place_evaluation"; isSubmitting?: boolean; fieldErrors?: Record<string,string>; onSubmit:(request:RecommendationRequest|PlaceEvaluationRequest)=>void|Promise<void>}`；默认 `initialMode="recommendation"`、`isSubmitting=false`。`WeightSegmentsProps = {originCount:1|2|3; value:RankingWeights; onChange:(value:RankingWeights)=>void; onReset:()=>void}`。
- 第一条失败测试：`render(<TravelForm onSubmit={vi.fn()} />)`，断言默认出现“推荐地点”、城市苏州、50 km、明天日期、“风景类型”，不存在“目标地点”；切到“评估指定地点”后反向显示；初次因 `TravelForm.tsx` 不存在而 import 失败。另测最多两个同行人、固定字段错误、隐藏字段不提交、选择顺序和权重始终为 100。
- 最小实现：严格采用 SPEC 的默认值、字段/分组/按钮文案和客户端错误；模式切换保留各自内存状态但序列化省略隐藏字段。`WeightSegments` 使用 5% 步长相邻分配，单人 `40/30/0/30`、多人 `40/0/40/20`，人数状态改变即 reset；只生成请求权重，不计算结果分。样式由 `forms.css` 提供稳定尺寸和重叠零宽段的独立焦点。
- 验证：`npm --prefix frontend test -- TravelForm.test.tsx WeightSegments.test.tsx` 绿阶段全部 PASS；`npm --prefix frontend run lint` 与 `npm --prefix frontend run build` 退出 0。

### M3.4 推荐与评估结果工作区

- 文件：`frontend/src/features/search/SearchWorkspace.tsx`、`ResultList.tsx`、`ResultCard.tsx`、`DailyWeatherList.tsx`、`SourceNotice.tsx`、`frontend/src/pages/SearchPage.tsx`、`frontend/tests/SearchWorkspace.test.tsx`、`ResultCard.test.tsx`。
- 第一条失败测试：结果卡显示总分、分项、每日天气、距离、公平性、`RoamBot 热度估算`、解释和来源；demo/cache/直线估算/无结果均有明确状态。
- 最小实现：TanStack mutation 保留上一次成功结果直到新结果成功；结构稳定、按钮尺寸固定；不展示地图、路线、导航或行程。
- 验证：结果 Vitest、build、lint。

### M3.5 注册登录 UI

- 文件：`frontend/src/features/auth/AuthDialog.tsx`、`RequireAuth.tsx`、对应 Vitest。
- 第一条失败测试：用户名/密码注册登录、通用错误凭据提示、退出；页面不存在手机号、短信、验证码、邮箱或找回密码输入。
- 最小实现：游客核心页不阻断；访问收藏/历史时打开登录，成功后返回原路径。
- 验证：认证 Vitest、build、lint。

### M3.6 收藏、历史与分享页面

- 文件：`frontend/src/features/favorites/FavoriteList.tsx`、`frontend/src/features/history/HistoryList.tsx`、`ShareActions.tsx`、`frontend/src/features/shares/PublicSharePage.tsx`、对应 Vitest。
- 第一条失败测试：收藏重新评估要求新输入；历史标快照并支持 rerun/delete/clear；分享可创建、复制、撤销；匿名页不显示出发地址或账户身份。
- 最小实现：桌面列表、移动端单项卡片、Lucide 命令图标和可访问名称；公开分享无需登录。
- 验证：个人数据 Vitest、build、lint。

### M3.7 响应式视觉检查

- 文件：`frontend/src/styles/`、`frontend/tests/responsive.test.tsx`。
- 第一条失败测试：1440x900、1024x768、390x844、360x800 均无横向溢出、文字重叠和控件跳动；桌面左右、手机上下。
- 最小实现：克制的工具型界面、非单一色调、8px 以下卡片圆角、稳定网格尺寸和移动断点；无嵌套卡片或装饰色球。
- 验证：Vitest、四个视口真实截图和元素边界检查。

### M3.8 Playwright 用户旅程

- 文件：`playwright.config.ts`、`e2e/guest-recommendation.spec.ts`、`account-personal-data.spec.ts`、`public-share.spec.ts`、`responsive-layout.spec.ts`。
- 第一条失败测试：游客苏州推荐可见金鸡湖和 demo 标记；登录用户收藏、历史 rerun、分享、删除历史后链接失效；390x844 无横向溢出。
- 最小实现：Playwright 启动 mock FastAPI 和 Vite，桌面 Chromium 与 390x844 mobile project 使用临时 SQLite。
- 验证：`npx playwright test`，真实 provider 调用数为零。

### M3.9 一键测试脚本

- 文件：`scripts/test.ps1`、`scripts/test.sh`、`Makefile`、`AGENT_LOG.md`。
- 第一条失败测试：故意失败任一子命令时脚本立即非零退出。
- 最小实现：依次运行 backend pytest、Ruff、Vitest、frontend lint/build、Playwright。
- 验证：`./scripts/test.ps1` 与 `git diff --check`。

## 5. M4 真实 Provider 与交付

完整步骤见 `docs/superpowers/plans/2026-07-15-roambot-04-providers-and-delivery.md`。

### M4.1 非敏感配置与 Provider Factory

- 文件：`backend/src/roambot/config.py`、`backend/src/roambot/providers/factory.py`、`backend/tests/unit/test_config.py`、`test_provider_factory.py`。
- 第一条失败测试：默认 mock/demo；live 模式拒绝 demo、缺失账户 API Host/base URL/model 或缺少任一 vault key；错误中不出现值。
- 最小实现：`ProviderMode`、不含秘密的 Settings、mock/live `ProviderRuntime`；lifespan 只创建并关闭一次共享 HTTP client/runtime，每个请求由 runtime 创建带独立 `ProviderTrace` 的 bundle，测试可直接覆盖 request bundle。
- 验证：聚焦测试、完整 backend 测试和 Ruff，无网络。

### M4.2 脱敏 HTTP 与调用预算

- 文件：`backend/src/roambot/providers/http.py`、`budget.py`、对应单元测试。
- 第一条失败测试：429、500、timeout、坏 JSON 和 provider 错误的日志/异常不含三种 fake key、URL 参数或授权头；预算第 N+1 次调用稳定失败。
- 公开接口：`ProviderHttpClient(client:httpx.Client, provider:str, base_url:str, secrets:tuple[str,...])`；`get_json(*,operation:str,path:str,params:Mapping[str,str]|None=None,headers:Mapping[str,str]|None=None)->dict[str,Any]`。`ProviderOperation = geocode|poi_search|weather|distance|llm`；`ProviderBudget.consume(operation:ProviderOperation)->None`，超限抛 `ProviderBudgetExceeded`。适配器只传相对 path，不自行拼完整 URL。
- 最小实现：仅记录 provider、操作、状态、耗时、request ID；每请求最多 geocode 3、POI 6、weather 5、distance 5、LLM 1。`get_json` 负责 timeout、HTTP 状态、JSON object 校验和统一脱敏，绝不记录 URL/params/headers/body/raw response。
- 验证：HTTP/budget tests、完整 backend 测试和 Ruff。

### M4.3 高德适配器

- 文件：`backend/src/roambot/providers/amap.py`、`backend/tests/fixtures/amap/geocode_success.json`、`poi_around_success.json`、`poi_text_success.json`、`distance_success.json`、`backend/tests/unit/test_amap_provider.py`。
- 第一条失败测试：以 `https://restapi.amap.com` 和 MockTransport 验证 geocode 的 `/v3/geocode/geo?key&address&city&output=json`；50 km 内 around 的 `keywords,location,radius,sortrule=weight,region,city_limit=true,show_fields=business,page_size=25,page_num=1`；50 km 外 text 的同类城市约束；distance 的 `origins|destination|type=1`。同时覆盖 `status/infocode` 错误、空列表、畸形 POI、合成 ID、去重顺序、结果数不等和脱敏错误。
- 最小实现：GCJ-02；关键词固定为湖泊景区/海滩/古镇/博物馆/公园/山岳景区，按选择顺序每类一次、最多六次；around 半径限制 1-50000 米，text 后本地 haversine 粗过滤；只取第一页，按非空 ID 或名称+六位坐标去重，合并最多 25 个，缺 ID 生成稳定 SHA-256 前缀 ID；POI 必需 `name,location,type,typecode`；距离保序并把米/秒转为公里/分钟。只在 `status=1,infocode=10000` 成功，不请求路线几何或导航。
- 验证：AMap test、完整 backend 测试和 Ruff。

### M4.4 QWeather 适配器

- 文件均为 Create：`backend/src/roambot/providers/qweather.py`、`backend/tests/fixtures/qweather/weather_7d_success.json`、`backend/tests/unit/test_qweather_provider.py`。
- 公开接口：`QWeatherProvider(http:ProviderHttpClient,api_key:str,today:Callable[[],date])`；`daily(coordinate:Coordinate,start:date,end:date)->list[DailyWeather]`，满足 M1.5 的 `WeatherProvider` 同名签名。factory 先验证 `qweather_api_host` 为严格 `https://*.qweatherapi.com` 根 URL，再传给 `ProviderHttpClient`。
- 第一条失败测试：用 `https://test.qweatherapi.com`、fake key 和 MockTransport 构造 provider，调用 `daily(Coordinate(120.579,31.299),today,today+1)`；断言唯一请求为 `GET /v7/weather/7d?location=120.58%2C31.30&lang=zh&unit=m`、header 仅含 `X-QW-Api-Key` 凭据，返回按日期升序两项。初次因 `QWeatherProvider` import 失败。
- 最小实现：在 HTTP 前拒绝 `today..today+6` 外区间；一次 `get_json`；顶层 code 必须 200；按 SPEC 解析必需 daily 字段，风速取 day/night 最大，天气文案相同保留一次、不同用“转”，忽略区间外非日期字段，拒绝重复/缺日/畸形并使用固定 `forecast_unavailable|unavailable|bad_response` 错误。GCJ-02 坐标原值格式化两位，不逐日请求。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_qweather_provider.py -q`、完整 backend 测试与 Ruff 均退出 0，MockTransport 记录一次请求且 fake key 不出现在日志/异常。

### M4.5 新鲜缓存、候选上限与降级

- Create：`backend/src/roambot/providers/cached.py`、`trace.py`、`backend/tests/unit/test_cached_providers.py`、`backend/tests/unit/test_degradation_policy.py`。Modify：`backend/src/roambot/providers/factory.py`、`backend/src/roambot/services/recommendations.py`、`backend/tests/unit/test_provider_factory.py`、`backend/tests/unit/test_recommendation_service.py`。
- 公开接口：`make_cache_key(provider:str,operation:str,params:Mapping[str,JsonValue])->str`；`CACHE_TTLS={geocode:30d,poi_search:7d,distance:1d,weather:1h}`。四个装饰器构造器均为 `(inner,cache:CacheRepository,provider:str,clock:Callable[[],datetime],trace:ProviderTrace)`：`CachedGeocoder.geocode(address,city)->Origin`；`CachedPlaceProvider.search(center,city,scenery_types:tuple[SceneryType,...],radius_km)->list[Destination]` 与 `.resolve(name,city)->Destination`；`CachedDistanceProvider.measure(origins,destination)->list[DistanceEstimate]`；`CachedWeatherProvider.daily(coordinate,start,end)->list[DailyWeather]`。另定义 SPEC 的 `ProviderEvent`、`ProviderTrace.mark/to_source_state`、`ProviderBundle` 和 `ProviderRuntime.new_request_bundle()->ProviderBundle`。
- 第一条失败测试：直接导入上述五个 cache API，逐项断言 SPEC 四种 canonical key/payload；固定 UTC 时钟分别断言四类操作在 `expires_at-1us` 命中且不调用 inner、在 `expires_at` miss 并调用 inner；错误不写缓存、损坏/过期缓存不降级。另测每个 request bundle 的 trace 对象不同；发生于后来被排除候选的事件仍按 SPEC 进入成功响应 notices。再测合并候选保序粗过滤后只取前五项、精确超距不回填；部分/全部天气失败、距离直线估算、live 禁止 demo、固定 notices 顺序和 `SourceState` 优先级。初次因 `cached.py` 不存在而 import FAIL。
- 最小实现：cache-first decorators；有效 hit 标记 CACHE，损坏 entry 先 `.delete(key)`，provider 成功后按 TTL upsert，所有错误原样传播且不保存。推荐服务按“距离/估算→硬过滤→天气”限制五个候选；超距候选零天气调用；距离失败写 `duration_minutes=None,estimated=True`，部分天气失败排除并降级，全部实际进入天气步骤的候选失败时抛映射为 503 的稳定 provider error；不返回过期缓存。
- 验证：`./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_cached_providers.py backend/tests/unit/test_degradation_policy.py backend/tests/unit/test_provider_factory.py backend/tests/unit/test_recommendation_service.py -q`、完整 backend 测试、Ruff、`npm --prefix frontend test -- SearchWorkspace.test.tsx ResultCard.test.tsx` 和 mock Playwright journey 均退出 0。

### M4.6 OpenAI-compatible LLM 解释

- 文件：`backend/src/roambot/providers/openai_compatible.py`、`backend/tests/unit/test_explanation_provider.py`。
- 第一条失败测试：0 项不调用，1-5 项只调用一次 `/chat/completions`；prompt 不含用户名、详细出发地址、token 或 key；坏 JSON 使用稳定 provider error。
- 最小实现：低温度结构化 JSON 解释，按 destination ID 重排，20-180 字；输出只能改 explanation，不能改分数、排名或事实。
- 验证：解释 test、完整 backend 测试和 Ruff。

### M4.7 人工真实 API Smoke

- 文件：`backend/src/roambot/cli.py`、`backend/tests/integration/test_provider_smoke_cli.py`、`backend/README.md`。
- 第一条失败测试：注入 mock 后命令只打印 provider、脱敏状态、调用次数、缓存状态和时间，不打印 key、主密码、完整 URL、prompt 或私人地址。
- 最小实现：`roambot providers smoke` 固定执行 1 次 geocode、1 次 resolve、1 次 distance、1 次 weather、1 次 explanation，支持 `--skip-llm` 和 `--only`，不自动重试。
- 人工边界：只有执行到此任务才请用户申请凭据，并在一次真实调用前说明最多五次调用并单独征得批准。
- 验证：默认测试仍用 mock；真实结果只记录脱敏成功/失败和调用次数。

### M4.8 单 Docker 镜像

- Modify：`backend/src/roambot/main.py`。Create：`backend/src/roambot/entrypoint.py`、`backend/tests/api/test_static_serving.py`、`backend/tests/unit/test_entrypoint.py`、`Dockerfile`、`.dockerignore`、`docker-compose.yml`。
- 公开接口：M4.8 将 app factory 扩展为 `create_app(frontend_dist:Path|None=None)->FastAPI`；`entrypoint.resolve_master_password(mode,stdin_isatty,password_file)->str|None` 和 `entrypoint.main()->int`。默认 secret path `/run/secrets/roambot_master_password`，可由非秘密 `ROAMBOT_MASTER_PASSWORD_FILE` 覆盖；容器固定监听 `0.0.0.0:8000`，静态路径 `/app/frontend/dist`，数据 `/data`。
- 第一条失败测试：临时目录写 `index.html` 与 `assets/app.js` 后，`create_app(temp)` 的 `/`、`/history` 返回同一 index，真实 asset 200，缺失 asset/带后缀文件 404，`/api/v1/health` 200，`/api/v1/missing` 为 JSON 404；初次因 factory 不接受参数失败。entrypoint 测试 mock 模式无需密码；live+非 TTY+缺文件返回 78 和固定脱敏 stderr；文件只 trim 尾部 CR/LF；POSIX 可见时拒绝 group/world-readable。
- 最小实现：API 优先、assets 第二、suffixless fallback 最后；frontend_dist=None 不挂静态，生产缺 index 配置失败。entrypoint live 模式优先只读 password file，仅 TTY 可 getpass，绝不从环境变量值/argv取密码。三阶段镜像使用 `node:24-alpine`、`python:3.13-slim` wheel builder/runtime，最终非 root `roambot`、`EXPOSE 8000`、`VOLUME /data`、Python urllib healthcheck、CMD `python -m roambot.entrypoint`。
- Compose 服务固定名 `roambot`，默认 mock/demo，`8000:8000`，named volume `roambot-data:/data`；live profile 才把只读 secret 挂到固定路径，不含任何密码/key 字面值。
- 验证：先运行两个聚焦 pytest、`./scripts/test.ps1` 和 `docker build -t roambot:local .`。再执行 `docker run --rm -d --name roambot-check -p 8000:8000 -v roambot-check-data:/data -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true roambot:local`；`Invoke-RestMethod http://127.0.0.1:8000/api/v1/health` 严格得 ready，`Invoke-WebRequest` 验证 `/`、`/history` 200，并完成一次 mock 推荐；最后 `docker stop roambot-check`。`--rm` 自动删容器，不删除 named volume。

### M4.9 GitLab CI

- 文件：`ci/Dockerfile`、`.gitlab-ci.yml`、`backend/tests/integration/test_network_guard.py`、`scripts/test.sh`。
- 第一条失败测试：backend 测试阻止除 loopback 外的 socket；前端扫描阻止硬编码 provider/bearer/master-password 模式。
- 最小实现：名为 `unit-test` 的 job 在 Python 3.13 + Node 24 + Chromium 测试镜像运行完整脚本；成功后 `docker-build` 构建、mock health smoke 并推送 commit SHA 标签。
- 验证：本地构建/运行 CI 镜像；有 GitLab 权限时再用 CI Lint 和远端 pipeline，无法运行时明确记录，不虚报通过。

### M4.10 最终文档与证据

- 文件：`README.md`、`backend/README.md`、`REFLECTION.md`、`AGENT_LOG.md`、`TASKS.md`、`docs/evidence/verification.md`。
- 第一条失败检查：README 的命令在新进程不可复现、证据无测试计数、或 Git 中出现秘密/数据库/测试产物时不得完成。
- 最小实现：补齐 mock/live 运行、Docker、迁移、凭据恢复边界、费用、缓存降级、CI、已知限制和作业反思。
- 验证：完整测试、Ruff、frontend build、Playwright、`git diff --check`、秘密扫描、最终 Docker smoke、`superpowers:requesting-code-review`。

## 6. 最终交付物

- `SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`AGENT_LOG.md`、`DECISIONS.md`、`REFLECTION.md`。
- FastAPI、React WebUI、SQLite/Alembic、pytest/Vitest/Playwright、一键测试脚本。
- `Dockerfile`、数据卷说明、公开或课程要求的镜像发布记录。
- `.gitlab-ci.yml`，至少含名为 `unit-test` 的 job，以及最后一次实际 CI 结果。
- 桌面和手机界面证据；无地图、路线、导航或逐日行程。
- 真实 API smoke 的脱敏结果，或未执行的明确原因；不提交真实凭据。
