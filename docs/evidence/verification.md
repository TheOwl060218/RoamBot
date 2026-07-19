# RoamBot 验证证据

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

## 尚未宣称通过的外部验证

- 真实 provider smoke：未申请/录入凭据，已跳过；Mock 通过不证明真实服务连通。
- GitLab CI Lint/远程流水线：仓库只配置 GitHub remote，未运行 GitLab 远程 CI。
- 公网 WebUI：尚未选择并授权部署平台；本地 URL 不是公网交付地址。

本文件记录的远程 CI 已覆盖交付文档草稿与最新源码。公网部署和真实 provider 结果仍必须在实际完成后补充；不得把本地验证写成远程成功。
