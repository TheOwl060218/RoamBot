# RoamBot

RoamBot 是一个支持单人和多人汇合的天气感知风景出行推荐 Web 应用。用户给出出发地、日期、最大距离和风景偏好后，系统综合天气、距离、多人公平性、热度与偏好覆盖度，返回可解释的地点排序；也可以直接评估一个指定地点是否值得去。

## 功能

- 游客可使用推荐与指定地点评估，无需注册。
- 支持主出发地和最多两个同行人出发地，以距离方差衡量汇合公平性。
- 展示地点距离、每日天气、分项评分、总分和推荐理由。
- 用户可选择默认权重或自定义天气、距离、公平性和热度权重。
- 本地账户支持注册、登录、退出、收藏、历史快照、重新查询和匿名只读分享。
- Mock 模式提供确定性的苏州演示数据；Live 模式可接入高德、QWeather 和 OpenAI-compatible LLM。

RoamBot 不是导航或行程规划工具。V1 不显示地图、不绘制路线，也不提供导航、交通预订或逐日行程安排。

## 安装与运行

前置条件：Git 与 Docker Desktop。以下命令在仓库根目录执行，不需要 API key，也不会消耗 provider 配额。

```powershell
git clone --branch feat/roambot-v1 https://github.com/TheOwl060218/RoamBot.git
Set-Location RoamBot
```

```powershell
docker build -t roambot:local .
docker run --rm -p 8000:8000 -v roambot-data:/data -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true roambot:local
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。也可以使用 Compose：

```powershell
docker compose up --build roambot
```

`roambot-data` 保存 SQLite 数据与加密凭据库，重建容器不会删除该卷。停止服务可按 `Ctrl+C`；Compose 用户可运行 `docker compose down`，不要附加 `--volumes`，除非确实要永久删除数据。

## 分发

CI 已将提交 `219437a` 对应的 Linux/amd64 镜像发布到公开 GHCR。无需克隆源码即可运行固定版本：

```powershell
docker pull ghcr.io/theowl060218/roambot:219437a849f65df40c5e9511536458174a527d96
docker run --rm -p 8000:8000 -v roambot-data:/data -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true ghcr.io/theowl060218/roambot:219437a849f65df40c5e9511536458174a527d96
```

公开镜像使用提交 SHA 标签保证可复现；当前功能分支不发布 `latest`，合并到默认分支后 CI 才会同时发布 `latest`。目标机器上的真实 key 仍必须按“凭据安全”一节通过隐藏 CLI 写入其数据卷，不能构建进镜像或作为命令参数传入。

## 本地开发

需要 Python 3.12 或 3.13、Node.js 24 LTS。Windows PowerShell 初始化：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location frontend
npm ci
npx playwright install chromium
Set-Location ..
```

分别启动后端与前端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn roambot.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev
```

开发页面位于 `http://127.0.0.1:5173`，Vite 将 `/api` 代理到后端。生产镜像则由 FastAPI 在同一个 `8000` 端口提供 API 与构建后的 React 页面。

## 数据与迁移

本地默认数据目录为 `data`，可通过非敏感变量 `ROAMBOT_DATA_DIR` 修改。升级数据库：

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

备份前应停止写入，然后备份整个数据目录或 Docker 命名卷。主机目录可直接复制；命名卷可导出：

```powershell
docker run --rm -v roambot-data:/data -v "${PWD}:/backup" alpine tar czf /backup/roambot-data-backup.tar.gz -C /data .
```

## 凭据安全

真实高德、QWeather 和 LLM key 保存在 `ROAMBOT_DATA_DIR/credentials.vault`，由主密码经 Scrypt 派生密钥并使用 AES-256-GCM 加密。key 不进入源码、Git、`.env`、日志、浏览器、Docker 镜像、CI 变量或聊天。

本地 CLI 使用隐藏输入：

```powershell
.\.venv\Scripts\roambot.exe credentials init
.\.venv\Scripts\roambot.exe credentials status
.\.venv\Scripts\roambot.exe credentials set amap
.\.venv\Scripts\roambot.exe credentials set qweather
.\.venv\Scripts\roambot.exe credentials set llm
.\.venv\Scripts\roambot.exe credentials clear amap
.\.venv\Scripts\roambot.exe credentials reset
```

Docker 命名卷可通过同一个 CLI 管理：

```powershell
docker run --rm -it -v roambot-data:/data --entrypoint roambot roambot:local credentials init
docker run --rm -it -v roambot-data:/data --entrypoint roambot roambot:local credentials status
```

`status` 只显示是否已配置，不显示 key。忘记主密码后无法恢复原来的 API key；`reset` 只删除加密凭据库，不删除 `roambot.db`，之后必须重新录入并在供应商控制台吊销旧 key。能执行 reset 的人已经拥有本机文件系统或 Docker 主机权限；reset 不会让他得到原 key，但他可以配置自己的 key，因此操作系统账户、Docker 权限和主机访问控制仍然重要。

## Live 模式

先用隐藏 CLI 将 key 写入与服务相同的数据目录，再设置这些非敏感参数：

```powershell
$env:ROAMBOT_PROVIDER_MODE = "live"
$env:ROAMBOT_DEMO_MODE = "false"
$env:ROAMBOT_QWEATHER_API_HOST = "https://YOUR-ACCOUNT-HOST.qweatherapi.com"
$env:ROAMBOT_LLM_BASE_URL = "https://YOUR-SCHOOL-API-HOST"
$env:ROAMBOT_LLM_MODEL = "YOUR-MODEL-NAME"
```

交互式容器会在 TTY 中隐藏询问主密码。无人值守 Compose 使用 `ROAMBOT_MASTER_PASSWORD_FILE_SOURCE` 指向仓库外、权限受限的主密码文件；不要把该文件提交到 Git。

人工连通性检查命令为 `roambot providers smoke`。完整运行最多调用高德 3 次、QWeather 1 次、LLM 1 次，不自动重试；也可以使用 `--only amap|qweather|llm` 或 `--skip-llm`。执行前应明确确认可能消耗配额。当前仓库未保存真实凭据，最终证据会如实标注是否执行过真实 smoke。

## 缓存与降级

- 地理编码缓存 30 天，POI 检索缓存 7 天，距离缓存 1 天，天气缓存 1 小时。
- Live 模式优先使用未过期缓存；损坏或类型不符的缓存会被删除。
- 苏州演示场景可在地点服务不可用时使用内置演示数据；其他地区会明确返回 provider 不可用。
- 距离服务失败时可显示直线距离估算；天气覆盖不足的候选会被排除。
- LLM 只生成理由，不能修改地点、天气、分数或排序；失败时使用确定性模板理由。

## 测试与 CI

Windows 一键测试：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

浏览器旅程会临时监听本机 `8000` 和 `5173`，运行前需保证这两个端口空闲；Docker 版完整门禁不占用宿主机端口。

Linux/CI：

```bash
./scripts/test.sh
```

测试覆盖 pytest、Ruff、Vitest、ESLint、TypeScript、Vite 构建及桌面/移动端 Playwright。自动测试强制 Mock/demo 模式，后端还会拦截所有非回环 socket；因此自动测试不会调用高德、QWeather 或 LLM，也不会消耗 provider 配额。

`.gitlab-ci.yml` 提供作业要求的 `unit-test` 与生产镜像构建/推送；`.github/workflows/ci.yml` 让当前 GitHub 远程在 push/PR 时运行同一套断网测试并构建镜像。远程流水线结果只能在实际 push 后记录，不能由本地结果代替。

## 安全边界

- 密码使用 Argon2 哈希；会话与 CSRF token 只以 SHA-256 哈希落库。
- 会话 Cookie 为 `HttpOnly`、`SameSite=Lax`；生产 HTTPS 部署应启用 `ROAMBOT_SECURE_COOKIES=true`。
- 公开分享仅包含脱敏白名单快照，不包含账户、详细出发地、Cookie 或 provider 凭据。
- 所有 provider 调用都有超时、每请求预算、脱敏错误与无自动重试边界。
- V1 不提供手机号、短信、验证码、邮箱、OAuth、密码找回或账户注销。

## 目录结构

```text
backend/                 FastAPI、领域服务、provider、SQLite/Alembic 与 pytest
frontend/                React/Vite WebUI、Vitest 与 Playwright
ci/Dockerfile            可复现的断网测试镜像
docs/                    设计、分步计划与验证证据
scripts/                 Windows/Linux 一键测试入口
.gitlab-ci.yml            GitLab 测试、构建与 registry 推送
.github/workflows/ci.yml  GitHub push/PR 流水线
Dockerfile               前端构建 + 后端 wheel + 非 root 生产镜像
docker-compose.yml        Mock 默认服务与显式 Live profile
SPEC.md / PLAN.md         规约与根实现计划
SPEC_PROCESS.md           规约迭代与陌生 agent 冷启动证据
AGENT_LOG.md              实现过程、人工干预与验证记录
REFLECTION.md             学生本人完成的课程反思
```

## 已知限制

- 当前只在 Windows 11 + Docker Desktop Linux containers 上完成本地验收。
- 真实 provider 的可用性、价格、配额和数据质量由供应商决定；Mock 通过不等于真实服务已连通。
- SQLite 适合本项目的单实例规模，不支持多副本同时写入同一文件。
- 当前未提供公网部署 URL；本地 WebUI 是开发与验收入口，公网部署需要单独的平台账号与密钥配置。
- 微信小程序、地图、导航、行程安排与密码恢复均不在 V1 范围内。

## 第三方组件

主要运行时组件包括 React、TanStack Query、Lucide、FastAPI、Pydantic、SQLAlchemy、Alembic、HTTPX、Argon2、cryptography、Typer 和 Uvicorn；开发测试使用 Vite、TypeScript、Vitest、Playwright、pytest 与 Ruff。精确版本及传递依赖见 `frontend/package-lock.json` 与 `backend/pyproject.toml`。项目未复制第三方源码，使用与分发时应遵守各包随附许可证。
