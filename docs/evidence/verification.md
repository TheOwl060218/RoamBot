# RoamBot 验证证据

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
| `roambot:local` | `sha256:622c6d52df4a96db1a6191365c3d30eb044c52c956c50cf1ffb1173e37a016ba` | 80,859,721 bytes |
| `roambot-ci:local` | `sha256:e15adc1b05dd3dc09944bbe0b6e9377e2de2f8d1241c682d5f0226d413cb5cfb` | 643,130,052 bytes |

本地修复版容器 `roambot-check` 状态为 `running/healthy`，`GET /api/v1/health` 返回 `{"status":"ready"}`，WebUI 位于 `http://127.0.0.1:8000`。命名卷 `roambot-check-data` 在容器替换时保留。

## 真实 Provider 人工检查

- 2026-07-23，用户在本机隐藏终端逐项批准并运行人工 smoke；真实凭据和主密码未进入聊天、源码或日志。
- 高德：用户报告 smoke 成功；精确脱敏调用计数未留存，因此不在证据中猜测。
- QWeather：`ok calls=1`，其余 provider 均为 `skipped calls=0`。
- 学校 OpenAI-compatible LLM：Base URL `https://njusehub.info/v1`，模型 `deepseek-v4-flash`，结果为 `ok calls=1`，其余 provider 均为 `skipped calls=0`。
- 上述结果只证明固定小样本在执行时连通；自动测试和 CI 仍强制 Mock/demo 模式并保持零真实调用。

## 尚未宣称通过的外部验证

- GitLab CI Lint/远程流水线：仓库只配置 GitHub remote，未运行 GitLab 远程 CI。
- 公网 WebUI：尚未选择并授权部署平台；本地 URL 不是公网交付地址。

本文件记录的远程 CI 已覆盖交付文档草稿与最新源码。公网部署和真实 provider 结果仍必须在实际完成后补充；不得把本地验证写成远程成功。
