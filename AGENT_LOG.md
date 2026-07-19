# AGENT_LOG

## 2026-07-10 Task 0.0 项目启动

- Superpowers 技能：尚未安装，先记录前置条件。
- 关键上下文：作业要求 B 类应用项目；项目题目改为“RoamBot：支持多人汇合的天气感知风景出行推荐助手”。
- 人工决策：
  - 选择 B 类应用方向。
  - 放弃 12306、机票作为核心功能。
  - 不强接 SunsetBot。
  - 增加 1-2 个额外出发地址，支持多人汇合。
  - 明确本项目不是自主 agent，LLM 只做解释生成。
- 环境检查：
  - Git 可用。
  - Docker 命令可用，但 `C:\Users\24188\.docker\config.json` 读取存在权限警告。
  - 系统 PATH 未发现 Node.js。
  - 系统 `python` 入口运行异常。
  - Codex bundled Node.js 可用：v24.14.0。
  - Codex bundled Python 可用：3.12.13。
- 产出：
  - 初始化项目目录 `sunny-week-travel`，后续重命名为 `RoamBot`。
  - 初始化 Git 仓库。
  - 创建 `TASKS.md`、`SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`AGENT_LOG.md` 初稿。
  - 初始提交：`da88eed initialize project planning docs`。

## 2026-07-10 Task 0.1 Superpowers 接入确认

- Superpowers 技能：用户在当前会话中显式接入 `Superpowers` 插件。
- 关键上下文：Superpowers 作为开发流程工具使用，不作为 RoamBot 运行时依赖；RoamBot 代码、Docker 镜像和最终用户运行环境不需要引入 Superpowers。
- 人工决策：
  - 后续将通过访谈式 brainstorming 复核需求。
  - 将问答记录写入 `SPEC_PROCESS.md`，并把明确约束同步到 `SPEC.md` / `PLAN.md`。
- 备注：当前插件未暴露为可直接调用的 `brainstorming` 工具，流程证据将通过对话、文档修订、commit 记录体现。

## 2026-07-10 Task 1.1 新窗口接续与文档瑕疵修正

- Superpowers 技能：按用户要求继续使用 Superpowers brainstorming 流程推进。
- 关键上下文：新窗口通过截图与项目文件接续上一会话；当前仍处于规约与计划阶段，未进入实现代码。
- 人工干预：
  - 用户要求继续按作业文档步骤追问，并修正交接文档中的旧项目名。
  - 将 `TASKS.md` 与本日志中容易误导冷启动 agent 的 `sunny-week-travel` 说明修正为当前项目名 `RoamBot`，同时保留“初始名后续重命名”的历史。
- 过程提醒：用户希望后续及时收缩上下文，避免窗口再次因长上下文中断。

## 2026-07-10 Task 1.1 API 选择继续访谈

- Superpowers 技能：继续使用 brainstorming，一次只确认一个关键外部依赖。
- 人工决策：
  - 地图服务主选高德地图 Web 服务 API。
  - 天气服务主选 QWeather（和风天气）每日天气预报 API。
- 文档更新：
  - 将地图与天气 API 选择同步到 `DECISIONS.md`、`SPEC.md`、`SPEC_PROCESS.md`。
  - 将“推荐游玩时长不依赖地图 API”写入风险与设计边界。
  - 将 LLM 解释模块确定为 OpenAI-compatible provider 抽象，默认演示模型使用学校额度平台的 DeepSeek V4 Flash；测试与 CI 使用 mock/template，不消耗 token。
  - 将多人公平性确定为距离差异/方差越小越公平，并补充 API 成本控制边界：测试/CI mock，真实演示限制候选数量和调用次数。
  - 明确产品边界：前端不展示地图、路线或导航，只用结果卡片展示距离、每日天气、评分和推荐理由；高德仅作为后台数据服务。
  - 确定正式交付平台为响应式 Web 应用；登录、收藏、历史记录和分享按 Web 功能设计。微信小程序仅在主项目全部验收完成后作为独立可选扩展。
  - 确定网页登录使用本地用户名和密码，支持注册、登录和退出；密码仅保存安全哈希，不做邮箱验证、找回密码或第三方登录。
  - 确定收藏只保存地点关联，不保存旧天气、旧评分或推荐理由；重新打开收藏时按新输入和当前可用天气重新评估。
  - 确定历史仅记录成功查询的输入、生成时间和结果摘要；旧结果标为历史快照，重新查询生成新记录，失败请求不记录。
  - 确定分享采用可撤销的匿名只读链接，公开脱敏历史快照；不暴露账户和详细出发地址，不做社交或微信专用分享接口。
  - 确定使用 SQLite 保存个人数据，并通过 Docker 数据卷持久化；Docker 作为正式分发方式。
  - 本机检查：Docker CLI 29.4.0 已安装，但 Docker Engine 当前未运行；实现阶段构建镜像前需启动 Docker Desktop。
  - 确定历史支持删除单条和清空全部；删除历史会使关联分享链接失效，不影响收藏，暂不做数据导出或账户注销。
  - 确定游客可直接使用核心推荐和指定地点评估；收藏、历史和分享管理要求登录，游客查询不写入个人历史。
  - 修正凭据方案：真实 API key 不再依赖 `.env`，改用带主密码的加密凭据库；所有管理操作仅限本机管理员终端，紧急重置需要主机权限且不删除用户数据。
  - 确定 Web 架构为 React + TypeScript + Vite 前端与 FastAPI 后端；开发时分开运行，生产时同域名、单 Docker 镜像部署；测试采用 pytest、Vitest 和 Playwright。
  - 确定风景类型由高德 POI 类别、地点名称关键词和少量人工修正规则生成；允许多标签，未知地点不交给 LLM 猜测。
  - 确定高德 POI 失败时可使用有效缓存；内置苏州数据仅限显式演示模式并强制标注，正式模式不得静默使用。
  - 确定景区热度以高德 POI 综合排名和少量本地修正估算，必须标为 RoamBot 热度估算；此前确认的默认权重和用户自定义权重保持不变。
  - 确定多日天气分为每日适宜度平均分的 70% 加最差一天适宜度的 30%，结果限制在 0-100 分。
  - 接受 WebUI 页面结构作为 V1 基线；前后端分离后通过开发服务器、桌面与手机检查持续调整前端，但不改变后端评分和数据语义。
  - 确定 `/api/v1` 契约；推荐与指定地点使用独立接口并共享领域服务；服务端会话使用 HttpOnly Cookie 和 CSRF 防护，浏览器只保存非敏感界面偏好。
  - 确定真实 API 凭据推迟到 provider 适配器和 mock 测试通过后的人工冒烟测试阶段；用户仅在本机隐藏终端录入，不在聊天中提供。
  - 用户批准完整设计；V1 不收集手机号、不发送短信验证码、不接入网页验证码服务，进入 writing-plans 阶段。

## 2026-07-15 Task 1.2 Superpowers writing-plans

- Superpowers 技能：使用 `writing-plans` 将批准设计拆成可由后续执行者逐项完成的 TDD 计划。
- 产出：
  - `docs/superpowers/plans/2026-07-15-roambot-roadmap.md`
  - `docs/superpowers/plans/2026-07-15-roambot-01-core-backend.md`
  - `docs/superpowers/plans/2026-07-15-roambot-02-accounts-and-data.md`
  - `docs/superpowers/plans/2026-07-15-roambot-03-react-webui.md`
  - `docs/superpowers/plans/2026-07-15-roambot-04-providers-and-delivery.md`
- 关键执行边界：
  - 实现顺序固定为核心后端、账户与数据、WebUI、provider 与交付。
  - 每项功能先写失败测试，再做最小实现，再运行聚焦验证和完整验证。
  - 自动测试与 GitLab CI 强制 mock，真实凭据只在人工 smoke 前由用户通过隐藏 CLI 录入。
  - 高德单次推荐最多 3 次地理编码、6 次 POI 检索、5 次距离查询；QWeather 最多 5 次，LLM 最多 1 次。
- 自检修正：计划与批准设计逐条对照后，修正了距离和天气降级、缓存 TTL、风景枚举、provider 文件名及来源状态优先级；清除了计划占位写法。
- 安全瑕疵修正：`.env.example` 不再包含 API key 字段，README 不再要求把真实 key 写进 `.env` 或环境变量。
- 下一步：按作业文档执行陌生 agent 冷启动验证；尚未开始产品代码实现，也不需要用户提供真实 API。

## 2026-07-15 Task 1.3 第一次陌生 agent 冷启动

- 隔离方式：独立 agent 不继承本对话，只读 `SPEC.md` 与 `PLAN.md`，不允许读取其他项目文件、联网或编辑。
- 推演任务：天气抽象与评分、FastAPI Web API。
- 结论：需先修订文档。
- 主要证据：每日天气阈值/单位/缺失值、七日时区、覆盖语义、完整 API 路由/状态/错误、CSRF、降级历史、公开分享脱敏和 SPA fallback 均不足；根 PLAN 又把可执行细节外包给冷启动不可读的子计划。
- 已采取修订：SPEC 锁定上述规则和数据模型；PLAN 改成四里程碑 37 项的自包含 TDD 执行入口；详细子计划继续作为逐步实现辅助。
- 后续门槛：必须由第二个全新 agent 只读根两文档复测通过，才能请求用户确认进入实现。

## 2026-07-15 Task 1.3 第二次陌生 agent 冷启动

- 隔离方式：第二个独立 agent 不继承本对话，只读修订后的 `SPEC.md` 与 `PLAN.md`，不允许读取子计划、联网或编辑。
- 推演任务：M2.4 认证 API 与 CSRF、M4.3 高德适配器。
- 结论：需先修订文档。
- 主要证据：哈希存储无法恢复 CSRF 明文；会话/Cookie/认证响应不够精确；Ruff 缺少确切命令；高德主机、端点参数、检索策略、provider 成功条件、去重、畸形 POI 和 fixture 契约不足，且详细计划使用了旧分页参数。
- 已采取修订：固定 24 小时 session、注册自动登录、认证 JSON/Cookie；采用 `/auth/me` 原子轮换 CSRF 和前端单次刷新重试；补充根计划验证命令；按当前高德官方 Web 服务契约写清 geocode、V5 POI、V3 distance 的参数、边界、单位和错误处理，并同步三份子计划。
- 后续门槛：必须由第三个全新 agent 只读根两文档复测通过，才能进入实现。

## 2026-07-15 Task 1.3 第三次陌生 agent 冷启动

- 隔离方式：第三个独立 agent 不继承本对话，只读 `SPEC.md` 与 `PLAN.md`，不读子计划、不联网、不编辑。
- 推演任务：M1.4 天气/距离/公平性/热度与排序，M3.3 双模式表单与权重。
- 结论：需先修订文档。
- 主要证据：根文档缺距离、公平性、热度、最终分、舍入与 tie-break 精确公式和函数签名；表单缺 props、默认值、隐藏字段、选择顺序、权重手柄、人数变化、错误文案、接入边界和固定 npm 命令。
- 已采取修订：将详细计划既有评分规则提升到根 SPEC/PLAN，并锁定 rank 热度与空 bonus；固定权重校验、舍入和排序；固定表单接口、默认值、字段文案、5% 相邻分配、序列化和验证命令；同步详细计划。
- 后续门槛：必须由第四个全新 agent 只读根两文档复测通过，才能进入实现。

## 2026-07-15 Task 1.3 第四次陌生 agent 冷启动

- 隔离方式：第四个独立 agent 只读 `SPEC.md` 与 `PLAN.md`，避开前三轮专项任务，不读子计划、不联网、不编辑。
- 推演任务：M1.2 领域模型，M4.4 QWeather 适配器。
- 结论：需先修订文档。
- 主要证据：领域模型命名、字段类型、枚举、null/extra/默认与全部响应类型不完整；QWeather 类/方法、Host、query/header、坐标、响应字段、日夜选择、错误和 fixture 均不足。
- 已采取修订：统一完整 Pydantic 模型与 `GroupAccessibilityScore`；根据 QWeather 当前官方文档固定 API KEY Header、账户 Host、七日请求/响应和错误；补 HTTP/预算/provider 签名并同步子计划。
- 后续门槛：必须由第五个全新 agent 只读根两文档复测通过，才能进入实现。

## 2026-07-15 Task 1.3 第五次陌生 agent 冷启动

- 隔离方式：第五个独立 agent 只读根 `SPEC.md` 与 `PLAN.md`，排除前四轮任务，不联网、不编辑。
- 推演任务：M1.1 Python/FastAPI 健康检查，M3.1 Vite 应用壳。
- 结论：需先修订文档。
- 主要证据：app factory 和 `.venv`/安装命令缺失；Python 包文件不全；Vite 构建入口/配置不全；M3.1 的“可操作首屏”与 M3.3 表单任务冲突。
- 已采取修订：固定完整后端初始化与 `create_app/app`；固定完整 Vite scaffold、scripts、壳接口与占位路由；把最终可操作首屏门槛放回 M3 里程碑。
- 后续门槛：必须由第六个全新 agent 继续抽查未覆盖任务并通过。

## 2026-07-15 Task 1.3 第六次陌生 agent 冷启动

- 隔离方式：第六个独立 agent 只读根文档，优先个人数据/交付，不联网、不编辑。
- 推演任务：M2.7 匿名分享，M4.8 单 Docker 镜像。
- 结论：需先修订文档。
- 主要证据：分享创建/公开响应和重复语义缺失；Docker 静态测试依赖未构建 dist，entrypoint/secret/端口/Compose/smoke 接口不完整。
- 已采取修订：固定重新生成分享、脱敏 snapshot 和完整文件边界；补 response weather；固定静态目录注入测试、entrypoint exit 78、secret 路径、容器/Compose 接口与 smoke 命令。
- 后续门槛：必须由第七个全新 agent 继续抽查并通过。

## 2026-07-16 Task 1.3 第七次陌生 agent 冷启动

- 隔离方式：第七个独立 agent 只读根 `SPEC.md` 与 `PLAN.md`，避开前六轮任务，不联网、不编辑。
- 推演任务：M2.1 SQLite/Alembic、M4.5 新鲜缓存与降级。
- 结论：需先修订文档。
- 主要证据：Alembic 自带 `alembic_version` 与“七张业务表”表述冲突；迁移文件、列/外键/索引和临时 URL 注入不足；缓存键、到期边界、候选五项顺序、天气/距离降级、错误与 notice 触发规则不足。
- 已采取修订：固定七张业务表加一张 Alembic 框架表；补完整 schema、UTC/JSON/FK 规则和迁移入口；固定 cache-first TTL、canonical key、五候选不回填、距离/天气处理与来源提示。

## 2026-07-16 Task 1.3 第八次陌生 agent 复核

- 隔离方式：第八个独立 agent 仍只读根文档，定点复核 M2.1 与 M4.5。
- 结论：M2.1 通过，M4.5 需继续修订。
- 主要证据：四类缓存装饰器和具体 params/payload 未完全固定；来源事件是否包含后来被排除的候选不明确。
- 已采取修订：固定 cache key 的五种调用场景、versioned payload、装饰器名称与 request-scoped `ProviderTrace`；检索类型由无序集合改为有序 tuple。

## 2026-07-16 Task 1.3 第九次陌生 agent 最终复核

- 隔离方式：第九个独立 agent 只审 M4.5，不扩展产品范围。
- 首次结论：需先修订文档；指出 CacheRepository/clock/装饰器签名、POI resolve 单对象 payload、ProviderEvent/Bundle 类型和超距后天气调用顺序仍差最后一层定义。
- 最终修订：补 `CacheEntry` 与仓储方法、四装饰器完整签名、`Destination` 单对象 envelope、ProviderEvent/Trace/Bundle/Runtime 类型；固定“距离或估算→硬过滤→天气”，超距候选零天气调用。
- 定点复测结论：`通过，可进入实现`。
- 规划自检：占位扫描无匹配；旧接口/旧文件名一致性扫描无匹配；`git diff --check` 退出 0，仅报告 Windows LF/CRLF 转换警告。
- 当前状态：规约与计划阶段完成，尚未开始产品代码；下一步按 roadmap 从核心后端 M1.1 使用 TDD 执行。

## 2026-07-16 M1 执行环境决策

- 用户批准开始 Subagent-Driven Development，并允许随时暂停/恢复。
- 规划基线已提交并推送到 GitHub `origin/main`；实现使用隔离分支 `feat/roambot-v1`。
- 本机未安装 Python 3.13，用户批准本地使用 Codex bundled Python 3.12.13；项目兼容 `>=3.12,<3.14`，Docker/CI 保持 Python 3.13。
- 用户离开期间跳过所有需要额外权限的提交、推送、联网安装和 Docker 操作，仅执行无需授权的编辑与本地验证，并记录待办。

## 2026-07-16 M1.1 Python 包与健康检查

- Subagent-Driven 状态：实现 Agent 按先测试后实现的顺序创建七个规定文件；未创建提交。
- 实现：`create_app()`、模块级 `app`、`GET /api/v1/health` 严格返回 `{"status":"ready"}`；pyproject 兼容 `>=3.12,<3.14`，Ruff target 修正为最低兼容版本 `py312`。
- 无网络验证：Python 文件语法/compile 检查与 TOML 解析通过；生成的 `__pycache__` 已清理。
- 独立审查：最终 spec compliance 与 task quality 均 Approved，无 Critical/Important/Minor 问题。
- 恢复验证：用户返回后已创建 `.venv` 并安装 `-e "./backend[dev]"`；新版 Starlette 测试客户端要求 `httpx2`，已将其补入开发依赖，同时保留运行时 provider 使用的 `httpx`。
- 验证结果：严格警告模式下完整后端测试 `1 passed`；`pip check` 报告无损坏依赖；`ruff check backend` 全部通过。M1.1 验证门槛通过，进入提交收尾。
- 提交与复审：M1.1 已作为独立提交 `ed0c315` 保存；新审查 Agent 复核后判定 spec compliant、task quality Approved，Critical/Important/Minor 均为零。

## 2026-07-16 M1.7/M1 核心后端验收准备

- M1.7 公共推荐 API 已保存为提交 `92600bb`（`feat: expose public recommendation API`）。
- 主控已运行严格完整后端测试：

  ```powershell
  .\.venv\Scripts\python.exe -W error -m pytest backend/tests -q
  ```

  结果为 `88 passed`。
- 主控已运行 Ruff：

  ```powershell
  .\.venv\Scripts\python.exe -m ruff check backend
  ```

  结果为 `All checks passed!`（Ruff clean）。
- 本地 Uvicorn/OpenAPI 后台检查曾在输出留存前被中断，因此不声称该次检查成功。
  主控随后以进程内 `TestClient` 完成检查：健康接口返回
  `200 {"status":"ready"}`，OpenAPI 包含 `/api/v1/health`、
  `/api/v1/place-evaluations`、`/api/v1/recommendations` 三个路径。
- 当前 M1 依赖 `MockProviderBundle.default()` 提供确定性 Mock providers；不需要高德、
  QWeather 或 LLM 真实凭据，也不证明真实 provider 连通。
- 独立审查首次发现两项 Important：`not_found` 未按 provider 调用来源映射，且同行
  地址失败字段总是误指向 `main_origin`。修复提交 `b7c2efb` 在服务调用边界保留
  错误来源和实际字段路径，并移除评价接口的重复 geocode；定点复审结论为
  `APPROVED`。
- 两项非阻断 Minor 留待最终 API 契约审查统一处理：框架生成的 404/405 尚未使用
  稳定错误 envelope，OpenAPI 尚未声明实际错误响应 schema。
- M1.8 最终 focused 验证命令：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q
  ```

  最终 focused 测试数：`92 passed`。同一里程碑质量门中 Ruff 返回
  `All checks passed!`，`git diff --check` 退出 0（仅有 Windows LF/CRLF
  工作区提示）。M1 核心后端退出条件通过；未调用网络或真实 provider。

## 2026-07-17 M2 账户、数据与加密凭据里程碑

- 持久化与安全基础提交 `f2e646f`：SQLAlchemy/Alembic、七张业务表、SQLite 外键、
  Argon2、不可预测 session/CSRF/share token 及哈希存储。
- 认证提交 `f37a5f0`：用户名/密码注册、登录、退出和 `/auth/me`；固定 24 小时
  HttpOnly 会话、CSRF 轮换与写操作校验；游客核心查询保持可用。
- 个人数据提交 `c4a150f`：收藏、成功查询历史、rerun、单删和清空；修复了用户拥有
  多个收藏时重复收藏会触发 `MultipleResultsFound` 的回归缺陷。
- 分享与缓存提交 `f3b8012`：32-byte 匿名分享 token 只存 SHA-256 哈希，公开快照
  使用深层白名单且不调用 provider；删除历史使链接失效。限时安全评审发现规范化
  起点标签可能残留在解释文字中，已通过先失败后通过的回归测试收集并按长度降序脱敏。
- 加密凭据库使用 Scrypt `n=32768,r=8,p=1` 派生 32-byte key，以 AES-256-GCM、
  固定 AAD 和原子替换保存三种凭据。Typer CLI 的 init/status/set/clear/reset 只接受
  隐藏输入；错误密码和畸形库统一失败；reset 精确确认且不删除 `roambot.db`。
- 新增依赖仅为 `cryptography 46.0.7` 与 `Typer 0.27.0`；`pip check` 返回
  `No broken requirements found.`。Windows 上 `chmod(0o600)` 仅为 best effort，
  不能替代本机账户权限和 ACL 管理。
- M2.9 TDD 证据：首轮因 `roambot.security.vault` 不存在而 collection RED；实现后
  凭据库与 CLI 聚焦测试 `8 passed`，Ruff 通过。任务级评审的安全/代码质量结论为
  `APPROVED`；其唯一范围意见来自主控预先完成的计划内 `pyproject.toml` 依赖修改，
  经核对不是产品缺陷，因此保留。
- 主控最终验证：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests -q -W error
  .\.venv\Scripts\python.exe -m ruff check backend
  .\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
  ```

  结果为 `156 passed`、`All checks passed!`；Alembic 在全新临时目录连续执行两次
  `upgrade head` 均退出 0。秘密扫描只命中根规约文档中的字段名，经人工确认无凭据值；
  排除 Markdown 后源码扫描返回 `SOURCE_SECRET_SCAN_CLEAN`。
- 全部自动验证使用 Mock providers、临时 SQLite、临时凭据库和假 key；没有真实网络
  调用、没有产生高德/QWeather/LLM 费用，也没有向 GitHub 推送。

## 2026-07-18 M3 响应式 WebUI 里程碑

- 完成游客推荐、单人/多人输入、默认/自定义权重、结果排序与解释；登录后支持收藏、
  历史快照、重新运行、删除和公开分享。范围保持为地点评估，不加入地图、导航或行程安排。
- 一次集中里程碑审查未发现 Critical 问题；指出的受保护路由认证、失效会话清理、
  收藏再评估预填、历史详情与删除确认、端到端验收覆盖五项 Important 缺口，已在一次
  TDD 修复波次中全部完成，同时补齐 Escape/焦点管理和密码显示切换。
- Playwright 覆盖桌面与移动端共 8 条关键旅程。人工检查 `1440x900`、`1024x768`、
  `390x844`、`360x800`，均无横向溢出、控件重叠或结果卡越界。
- Windows 一键验证命令：

  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
  ```

  最终结果为后端 `156 passed`、Ruff 通过；前端 Vitest `18 passed`、ESLint 和
  TypeScript 通过；Vite 生产构建成功；Playwright `8 passed`。`ExecutionPolicy
  Bypass` 仅作用于当前测试进程，没有修改系统策略。
- 本里程碑沿用现有前端依赖并下载 Playwright Chromium。测试使用 Mock provider、
  临时数据库和假 key，没有调用高德、QWeather 或 LLM，也没有产生 API 费用或推送 GitHub。

## 2026-07-19 M4.1-M4.7 Provider 接入与人工 Smoke 入口

- 已完成 mock/live 配置边界、请求预算与脱敏 HTTP 边界、高德地理编码/POI/距离、QWeather 七日天气、cache-first 与降级策略，以及单次有界 LLM 推荐理由。
- 新增 `roambot providers smoke`，固定使用苏州公共演示地点；完整运行上限为高德 3 次、QWeather 1 次、LLM 1 次，支持 `--only amap|qweather|llm` 和 `--skip-llm`，不自动重试。
- Windows 环境缺少 IANA `tzdata` 时 `ZoneInfo("Asia/Shanghai")` 会在请求前失败，已改为标准库固定 UTC+8；该用途只计算中国自然日，不需要新增依赖。
- M4.7 TDD：命令不存在时新增测试为 RED；实现后 6 条零网络 CLI 测试通过，覆盖固定调用顺序、provider 单独检查、跳过 LLM、隐藏主密码输入和失败输出脱敏。
- Provider/安全里程碑原计划的一次集中只读审查在有限等待窗口内未返回结果，已终止以避免继续消耗时间；未伪造审查结论。主控随后完成全量 Mock 验证与秘密扫描。
- 最终本地验证：`226 passed`、Ruff `All checks passed!`、`git diff --check` 退出 0、源码扫描 `SOURCE_SECRET_SCAN_CLEAN`。
- 尚未申请或录入真实 provider 凭据，未执行人工 smoke，未产生高德/QWeather/LLM 调用或费用；真实连通性与苏州坐标/天气合理性仍待用户明确批准后验证。

## 2026-07-19 M4.8 单镜像 Docker 分发

- `create_app` 支持注入 `frontend_dist`，API 路由优先；`/assets` 精确静态挂载，仅无文件后缀且非 `/api` 的 GET 路径回退到 React `index.html`。
- 新增生产 entrypoint：固定监听 `0.0.0.0:8000`，Mock 模式不读取 vault；Live 模式只从权限受限的 secret 文件或 TTY 隐藏提示读取主密码，非交互缺失时固定退出 78。
- 主密码文件只移除末尾 CR/LF，读取 byte buffer 后尽力清零；vault 只解锁一次，`create_app` 复制凭据后 entrypoint 清空本地字典。配置 repr 不展示主密码文件字段。
- Live provider 缓存使用 `SessionCacheStore`，每次缓存读写打开短生命周期 SQLAlchemy session/事务，避免并发请求共享非线程安全 Session。
- 三阶段镜像使用 Node 24 Alpine 构建前端、Python 3.13 slim 构建 wheel、Python 3.13 slim 非 root 用户运行；单镜像同时提供 `/api/v1` 和 SPA，持久数据目录为 `/data`。
- TDD 证据：静态服务、entrypoint、跨 session 缓存共 14 条定向测试通过；完整门槛为后端 `236 passed`、Ruff 通过、前端 Vitest `18 passed`、ESLint/TypeScript/生产构建通过、Playwright `8 passed`。
- 首次 Docker 构建因工具 10 分钟上限超时且未生成镜像；启动 Docker Desktop 后用 plain progress 重试成功。最终源码新鲜构建成功，临时 Mock 容器健康 `ready`，`/` 和 `/history` 为 200，Mock 推荐为 200 且 `source=demo`。
- 镜像历史与容器日志只含固定构建/启动命令和 HTTP 状态，未发现 key、主密码或请求 payload。容器 `roambot-check` 保持运行供用户测试，命名卷 `roambot-check-data` 保留。
