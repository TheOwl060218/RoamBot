# RoamBot 验证证据

## 2026-08-10 最终完整 Mock 门禁

- 命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`
- 模式：`ROAMBOT_PROVIDER_MODE=mock`、`ROAMBOT_DEMO_MODE=true`，未调用真实高德、QWeather 或 LLM 服务。
- 后端 pytest：`289 passed in 12.38s`。
- Ruff：全部通过。
- 前端 Vitest：14 个文件，`52 passed`。
- ESLint、TypeScript、Vite 生产构建：全部通过；Vite 共转换 1822 个模块。
- Playwright：桌面端与移动端共 `8 passed in 15.9s`。
- 完整脚本退出码：`0`，总耗时约 55.8 秒。

## 2026-08-09 当前工作树完整 Mock 门禁

- 分支：`feat/roambot-v1`。
- 模式：`ROAMBOT_PROVIDER_MODE=mock`、`ROAMBOT_DEMO_MODE=true`。
- 真实调用：0；没有读取真实高德、QWeather 或 LLM 凭据，也没有产生 provider 费用。
- 一键入口：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`。
- 浏览器测试由脚本在隔离端口 `8010/5183` 自动启动并关闭服务；完成后两端口均已释放。

| 检查 | 当前工作树结果 |
| --- | --- |
| 后端 pytest | `283 passed in 23.29s` |
| Ruff | `All checks passed!` |
| 前端 Vitest | 14 个文件，`52 passed` |
| ESLint | 退出 0 |
| TypeScript | 退出 0 |
| Vite 生产构建 | 退出 0；1822 modules transformed；JS 349.68 kB，CSS 32.36 kB |
| Playwright | 桌面/移动端共 `8 passed in 36.6s` |
| 测试服务清理 | `8010`、`5183` 均为 `FREE` |
| Docker 新鲜构建 | `roambot:closeout-20260809`，退出 0 |
| Docker Mock 冷启动 | 健康接口为 `ready`；首页与历史页均返回 200；推荐接口返回 demo 结果 |
| 临时容器清理 | `roambot-final-smoke` 已停止并由 `--rm` 删除；原 `roambot-closeout` 未改动 |
| `git diff --check` | 退出 0；仅有 Windows LF/CRLF 提示 |
| 秘密值与敏感文件扫描 | 未发现真实 key、token、凭据库或数据库进入工作树改动 |

本次结果覆盖当前未提交工作树，但还不是远程 CI 证据。Docker 构建与冷启动全程使用 Mock/demo，未读取真实 provider 凭据。提交与 push 后 CI 仍须完成并记录。

## 2026-07-23 推荐质量改进验证

- 分支：`feat/roambot-v1`
- 模式：后端自动测试、前端组件测试和浏览器验收均使用 Mock/demo Provider。
- 真实调用：0；本轮自动验证未读取凭据库，也未调用高德、QWeather 或 LLM。
- 范围：场景化天气建议、高德五分制评分、列表级类型覆盖、最多 7 个结果、事实型推荐理由、2 条一组的 LLM 润色、旧历史兼容，以及最小前端呈现。

| 命令或检查 | 实际结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest backend/tests -q -W error` | `269 passed in 10.97s` |
| `.\.venv\Scripts\python.exe -m ruff check backend` | `All checks passed!` |
| 完整 Vitest | 11 个文件，`28 passed` |
| ESLint | 退出 0 |
| TypeScript `tsc -b` | 退出 0 |
| Vite 生产构建 | 退出 0；1811 modules transformed |
| Playwright Mock 验收 | 桌面 4 + 移动端 4，`8 passed in 13.7s` |
| 高熵凭据值扫描 | `SECRET_VALUE_SCAN_CLEAN` |
| `docker build -t roambot:local .` | 退出 0；镜像 `sha256:3ad463b2b77e...`，80,906,558 bytes |

Playwright 因现有人工测试容器占用 `8000`，使用测试专用端口 `8010/5183`；受控服务器在 `try/finally` 中启动并关闭，未替换或中断现有容器。验收覆盖访客推荐、账户/收藏/历史主流程、匿名分享和响应式关系。

本轮保留的后续视觉工作包括：双栏纵向失衡、推荐卡信息密度、2 至 7 日天气卡片时间序列布局，以及状态颜色语义。当前只实现评分、状态、中文日期、自然语言天气提醒和统一来源说明所需的最小样式。

本轮源码尚未推送，因此下方既有 GitHub Actions 记录不覆盖这次改动；必须在后续明确推送并取得新的成功流水线后，才能宣称远程 CI 已验证本轮版本。正在 `127.0.0.1:8000` 运行的人工测试容器也仍是重建前版本。

## 验证范围

- 日期：2026-07-19（Asia/Shanghai）
- 分支：`feat/roambot-v1`
- 当前 CI 实现提交：GitLab/本地门禁 `6f0d240`；GitHub Actions `219437a`
- 模式：`ROAMBOT_PROVIDER_MODE=mock`、`ROAMBOT_DEMO_MODE=true`
- 网络边界：CI 测试容器以 `--network none` 运行；未配置或调用真实高德、QWeather、LLM。

## 环境

| 工具 | 版本 |
| --- | --- |
| Windows Git | 2.53.0.windows.2 |
| Docker Desktop client/server | 29.4.0 / 29.4.0 |
| 本地 Python | 3.12.13 |
| CI Python | 3.13 |
| Node.js | 24.14.0 |
| Playwright | 1.61.1 |

## 已执行验证

| 命令或检查 | 结果 |
| --- | --- |
| `docker build -f ci/Dockerfile -t roambot-ci:local .` | 退出 0 |
| `docker run --rm --network none ... roambot-ci:local` | 退出 0 |
| 后端 pytest 严格警告模式 | `238 passed` |
| Ruff | `All checks passed!` |
| Vitest | 9 files、`20 passed` |
| ESLint / TypeScript | 退出 0 |
| Vite 生产构建 | 退出 0 |
| Playwright | 桌面 4 + 移动端 4，`8 passed` |
| `git diff --check` | 退出 0；仅 Windows 行尾提示 |
| 高熵凭据值扫描 | `SECRET_VALUE_SCAN_CLEAN` |

## 远程 CI

- 2026-07-19 将 `feat/roambot-v1` 推送至 GitHub，提交为 `219437a849f65df40c5e9511536458174a527d96`。
- GitHub Actions 运行 [29687387752](https://github.com/TheOwl060218/RoamBot/actions/runs/29687387752) 状态为 `success`。
- `unit-test` job [88193989762](https://github.com/TheOwl060218/RoamBot/actions/runs/29687387752/job/88193989762) 通过；测试镜像以 `--network none` 运行。
- `docker-build` job [88194128137](https://github.com/TheOwl060218/RoamBot/actions/runs/29687387752/job/88194128137) 通过；生产镜像完成 Mock 冒烟检查并推送 commit SHA 标签至 GHCR。
- 未登录 registry 的本机执行 `docker manifest inspect ghcr.io/theowl060218/roambot:219437a849f65df40c5e9511536458174a527d96` 返回 manifest，确认该提交镜像可公开获取。
- 这次结果证明 `219437a` 所含源码、测试与构建流程通过；最终文档提交仍需触发并记录新的最后一次 CI。
- 交付文档与 Windows Mock 安全护栏提交 `1ad45cbf0ef57b871ccdb360e6752546804efb21` 后，GitHub Actions 运行 [29689474384](https://github.com/TheOwl060218/RoamBot/actions/runs/29689474384) 再次为 `success`：`unit-test` job [88199537762](https://github.com/TheOwl060218/RoamBot/actions/runs/29689474384/job/88199537762) 与 `docker-build` job [88199696957](https://github.com/TheOwl060218/RoamBot/actions/runs/29689474384/job/88199696957) 均通过。

Playwright 自动检查 `1440x900` 与 `390x844`；M3 人工布局检查还覆盖 `1024x768` 与 `360x800`。未保留含账户、详细出发地、token 或 Cookie 的截图作为提交证据。

## 镜像与运行检查

| 镜像 | ID | 大小 |
| --- | --- | --- |
| `roambot:local` | `sha256:3ad463b2b77eb13fd4206d2b7745aee7716ffb6d4f5122331d6776a3d843f51a` | 80,906,558 bytes |
| `roambot-ci:local` | `sha256:e15adc1b05dd3dc09944bbe0b6e9377e2de2f8d1241c682d5f0226d413cb5cfb` | 643,130,052 bytes |

本地容器 `roambot-check` 状态为 `running/healthy`，WebUI 位于 `http://127.0.0.1:8000`。2026-07-23 本轮镜像构建后，该容器仍运行旧镜像 `e0f48ab3389b`，尚未切换到新的 `roambot:local`；命名卷 `roambot-check-data` 将在后续容器替换时保留。

## 真实 Provider 人工检查

- 2026-07-23，用户在本机隐藏终端逐项批准并运行人工 smoke；真实凭据和主密码未进入聊天、源码或日志。
- 高德：用户报告 smoke 成功；精确脱敏调用计数未留存，因此不在证据中猜测。
- QWeather：`ok calls=1`，其余 provider 均为 `skipped calls=0`。
- 学校 OpenAI-compatible LLM：Base URL `https://njusehub.info/v1`，模型 `deepseek-v4-flash`，结果为 `ok calls=1`，其余 provider 均为 `skipped calls=0`。
- 上述结果只证明固定小样本在执行时连通；自动测试和 CI 仍强制 Mock/demo 模式并保持零真实调用。

## 2026-08-10 公网部署与 Live 回归

- Railway 公网地址为 `https://roambot-production.up.railway.app`，根页面与 `/api/v1/health` 均返回 200。
- 服务使用 Railway 托管数据卷，挂载到 `/data`，容量 500 MB，区域为 EU West（Amsterdam）；生产环境启用安全 Cookie。
- 公网 Live 检查确认认证、收藏、地址提示与推荐接口可访问；Railway Network Logs 中一次推荐请求返回 200，耗时约 29 秒。
- 公网回归发现并修复两项既有行为偏差：风景类型覆盖提交 `80449ec`，跨城市指定地点出发地提交 `1bd0649`。后者对应 GitHub Actions 运行 `31368741662`，状态为通过。
- 一次 LLM 请求曾降级到缓存与本地模板，因此这里只确认降级机制有效，不宣称外部 LLM 始终稳定。
- 真实凭据仅保存在 Railway secret 与加密凭据库中，没有写入仓库、文档或自动测试；自动门禁仍使用 Mock/demo，不产生真实 provider 调用。

## 尚未宣称通过的外部验证

- GitLab CI Lint/远程流水线：仓库只配置 GitHub remote，未运行 GitLab 远程 CI。
- NJU Git、课程平台提交与学生个人反思尚未完成，必须由学生本人处理。

## 2026-08-11 正式 PR 与最终 CI 证据

- PR：[https://github.com/TheOwl060218/RoamBot/pull/1](https://github.com/TheOwl060218/RoamBot/pull/1)。源分支 `feat/roambot-v1`，目标分支 `main`；核对时为 open、非 draft、未合并。
- PR 头提交：`6367c7d3d8e37dff290ef200eb7fda9b011129ab`。
- 按收尾要求仅查询一次该提交 checks，共返回 4 个完成且成功的 check run。GitHub Actions `31405568984` 与 `31412198356` 各包含 `unit-test` 和 `docker-build`；最新成功记录为 [run 31412198356](https://github.com/TheOwl060218/RoamBot/actions/runs/31412198356)。
- 本轮只做远程状态核对和文档事实更新，没有重复完整本地门禁，没有调用真实高德、QWeather 或 LLM，也没有合并 PR 或删除分支。
- 课程截图应显示 PR URL、open 状态、源/目标分支，以及 Checks 中两个 job 的 success；必须避开账户敏感信息、Cookie、详细地址和凭据。

## 2026-08-12 最终合并与生产基线

- 用户查看并确认各 PR checks 后明确同意合并。PR #1 已合并为 `12e061f`，PR #2 已合并为 `f4ee5eb`，PR #3 已合并为 `38a1104`，PR #4 已合并为 `2a3cd36`。
- 当前生产代码基线为 `main` 提交 `2a3cd3665d9f20d8c2bd7c5e7d7db109b6407e9c`。对应 GitHub Actions [run 31598691090](https://github.com/TheOwl060218/RoamBot/actions/runs/31598691090) 状态为 `completed/success`，`unit-test` 与 `docker-build` 均成功。
- Railway production 已从旧功能分支切换到 `main`。最终部署显示 `Deployment successful`；公网首页返回 200 并引用 `/favicon.svg?v=2`，该资源返回 200，Content-Type 为 `image/svg+xml`。
- favicon 最终修复过程中的聚焦本地记录为：前端 15 个测试文件、53 个测试通过，Vite 生产构建成功；生产静态路由修复的后端记录为 289 个测试通过、Ruff 通过。它们属于对应变更的验证证据，不代表本次纯文档交接重新运行了整套门禁。
- 当前仍未宣称完成的外部事项：学生本人 `REFLECTION.md` 正文、NJU Git（若课程要求）和课程平台最终提交。
