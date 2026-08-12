# RoamBot 当前项目交接

> 最后核对：2026-08-12（Asia/Shanghai）。这是跨设备继续工作的当前入口，取代 `GPT_HANDOFF_2026-08-03.md` 中已经过时的状态。代码、GitHub 和实际部署状态始终优先于本文。

## 1. 新电脑快速接手

本交接目前位于 `docs/cross-device-handoff` 分支，尚未合并到 `main`。在新电脑上执行：

```powershell
git clone https://github.com/TheOwl060218/RoamBot.git
Set-Location RoamBot
git switch --track origin/docs/cross-device-handoff
```

若该分支以后已经合并，则改为：

```powershell
git switch main
git pull --ff-only
```

新建 Codex 任务后可直接发送：

```text
请先读取仓库根目录 AGENTS.md 和 docs/PROJECT_HANDOFF.md，再核对当前 Git 状态。
这是 RoamBot 暑期项目的最终收尾，不要重新开发或重复排查已确认问题。
剩余工作只按交接文档推进；不得读取、索要或记录任何秘密值。
```

这能恢复完成项目所需的事实和约束，但不会恢复旧任务中的每句对话、浏览器登录态或未提交的本地文件。

## 2. 项目与功能边界

RoamBot 是 FastAPI + React/Vite 的天气感知风景出行推荐 Web 应用，支持：

- 游客推荐查询和指定地点评估；
- 本地账户注册、登录、收藏、历史和匿名只读分享；
- 主出发地加最多两个同行人出发地；
- 天气、驾车距离、地点评分、偏好和多人公平性综合排序；
- 高德、QWeather、OpenAI-compatible LLM，以及零真实调用的 Mock/demo 模式；
- Docker、GitHub Actions、GitLab CI 配置和 Railway 公网部署；
- 桌面端与手机端响应式界面。

V1 不做地图展示、导航、交通预订、逐日行程安排、短信验证、第三方登录或密码找回。此前大量前后端问题已经逐项验收，没有新的可复现证据时不要重新设计或重复调试。

## 3. 当前已验证状态

### Git 与 PR

- GitHub：`https://github.com/TheOwl060218/RoamBot`
- 生产代码基线：`main`，提交 `2a3cd3665d9f20d8c2bd7c5e7d7db109b6407e9c`（`merge: refresh RoamBot favicon cache key`）。
- [PR #1](https://github.com/TheOwl060218/RoamBot/pull/1)：`feat/roambot-v1` -> `main`，已合并为 `12e061f`，补齐正式功能交付流程证据。
- [PR #2](https://github.com/TheOwl060218/RoamBot/pull/2)：`feat/favicon` -> `main`，已合并为 `f4ee5eb`，加入简洁指南针 favicon。
- [PR #3](https://github.com/TheOwl060218/RoamBot/pull/3)：`fix/serve-favicon` -> `main`，已合并为 `38a1104`，由生产 FastAPI 显式提供 `/favicon.svg`。
- [PR #4](https://github.com/TheOwl060218/RoamBot/pull/4)：`fix/favicon-cache-bust` -> `main`，已合并为 `2a3cd36`，使用 `/favicon.svg?v=2` 刷新浏览器缓存。
- 上述分支未在本交接中删除；本分支也不得自动合并。

### CI 与本地验证

- 最新生产基线对应 GitHub Actions [run 31598691090](https://github.com/TheOwl060218/RoamBot/actions/runs/31598691090)，状态为 `completed/success`；`unit-test` 和 `docker-build` 均成功。
- favicon 最终修复前的聚焦验证：前端 15 个测试文件、53 个测试通过，Vite 生产构建成功。
- 生产静态路由修复前的后端验证：289 个 pytest 通过，Ruff 通过。
- 这些是各次变更对应的真实记录，不应改写成在本交接分支上重新运行过整套测试。
- 自动测试使用 Mock/demo，不调用真实高德、QWeather 或 LLM。

### Railway

- 公网 WebUI：[https://roambot-production.up.railway.app](https://roambot-production.up.railway.app)
- Railway production 已改为监听 `main`，当前为单副本，区域 EU West（Amsterdam）。
- 500 MB 持久化卷挂载到 `/data`，保存 SQLite 数据库与加密凭据库。
- 生产页面与 `/favicon.svg?v=2` 最终均返回 200，favicon MIME 类型为 `image/svg+xml`。
- 用户已在 Railway 中配置 Live 变量。秘密值不在仓库、文档、聊天和测试日志中。
- 一次真实公网推荐曾观测约 29 秒；外部 LLM 也曾正常降级到缓存或本地模板，因此不要承诺第三方服务始终快速或可用。

## 4. 已解决但容易误判的问题

- Railway 最初仍从旧功能分支部署，后来已经切换到 `main`。看到旧提交标题时应先核对部署源和提交，而不是重复调试业务功能。
- favicon 文件仅存在于 Vite 源码时，生产 FastAPI 没有自动提供根路径资源；PR #3 增加生产路由，PR #4 增加缓存版本参数。最终公网已显示新图标。
- 历史上发生过部署版本、浏览器缓存和 LLM 降级造成的本地/线上差异；这些均已完成定点修复和验收，不应在没有新证据时循环检查。
- `docs/GPT_HANDOFF_2026-08-03.md` 记录的是功能分支尚未部署、Task 12 尚未完成的旧快照，只能用于追溯过程。

## 5. 真正剩余工作

1. 学生本人完成 `REFLECTION.md`，正文 1500-2500 个中文字，写真实经历、判断和方法论变化。
2. AI 只能整理学生主动提供的素材、检查结构和语病，不能生成可直接冒充个人经历提交的反思正文。
3. 学生核对课程要求后，提交最终仓库地址、公网 WebUI 地址、NJU Git 地址（若课程要求）及其他材料。
4. 提交前由学生本人完成最后的人工验收、脱敏截图选择和材料确认。

除上述事项外，功能实现、正式 PR、最新 CI、Railway 部署和 favicon 收尾均已完成。不要把课程平台提交或个人反思写成已完成。

## 6. 安全与协作约束

- 不上传整段聊天记录、私人偏好文件、浏览器会话、Cookie、详细个人地址或未脱敏截图。
- 不把 API key、主密码或 token 写进 Git、命令行参数、文档、截图和对话。
- API 凭据继续由项目既有加密凭据库与 Railway secret 管理，不重构该机制。
- 文档收尾不重复整套测试；只有功能代码变化或明确可复现问题才运行相应的最小验证。
- 不创建子智能体，不重新讨论已经确定的产品与界面选项。
- 汇报时区分“当前验证事实”“历史记录”和“尚待学生完成”。

## 7. 事实来源顺序

发生冲突时按以下顺序判断：

1. 当前 Git 提交、代码和实际 GitHub/Railway 状态；
2. 本文件与 `TASKS.md`；
3. `README.md`、`AGENT_LOG.md`、`docs/evidence/verification.md`；
4. 带日期的旧交接与旧测试段落，它们只代表当时快照。

状态发生变化后，应在同一文档分支更新本文件和相应证据。不要依赖无限增长的聊天上下文保存项目事实。
