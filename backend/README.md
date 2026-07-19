# RoamBot 后端（M1 + M2）

> [!IMPORTANT]
> 当前推荐、天气、距离与解释仍使用确定性的 Mock providers。创建环境、迁移数据库、
> 运行测试、管理本地凭据库和启动 API 都不需要高德、QWeather 或 LLM 的真实凭据，
> 也不会产生真实 API 费用。真实 provider 接入和人工 smoke 属于 M4。

## 环境与安装

- Windows PowerShell
- Python 3.12 或 3.13

以下命令均在包含 `backend`、`README.md` 和 `AGENT_LOG.md` 的 **RoamBot 仓库根目录**
执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
```

## 数据库迁移

SQLite 数据目录默认为 `data`，可用非敏感环境变量 `ROAMBOT_DATA_DIR` 修改。首次启动
或迁移版本变化后执行：

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

迁移会创建账户、会话、地点、收藏、历史、分享和 provider 缓存七张业务表。SQLite
连接始终启用外键约束；请保留整个数据目录，而不是只复制单个临时文件。

## 启动与检查

```powershell
.\.venv\Scripts\python.exe -m uvicorn roambot.main:app --reload --host 127.0.0.1 --port 8000
```

在另一个 PowerShell 窗口检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health | ConvertTo-Json -Compress
```

核心推荐和指定地点评估允许游客直接调用。当前服务还提供本地用户名/密码注册、登录、
退出、收藏、历史和脱敏分享 API；这些个人数据操作由后端进行资源归属检查。

## 账户与个人数据语义

- 密码使用 Argon2 哈希，数据库不保存明文密码。
- 登录使用固定 24 小时的服务端会话；Cookie 名为 `roambot_session`，带 `HttpOnly`、
  `SameSite=Lax` 和 `Path=/`。生产部署再启用 `Secure`。
- 登录写操作需要响应中返回的 CSRF token，并通过 `X-CSRF-Token` 发送；数据库只保存
  session、CSRF 和分享 token 的 SHA-256 哈希。
- 收藏只保存地点引用，不冻结旧天气或旧评分；重新评估时需要新的查询输入。
- 历史只记录登录用户的成功查询，保存当时输入和结果快照；rerun 会产生新历史。
- 分享只公开固定白名单字段和脱敏快照，不重新调用 provider。重新创建会撤销旧链接；
  主动撤销、删除单条历史或清空历史都会使相关链接立即不可用，收藏不受影响。
- 当前不实现手机号、短信、验证码、邮箱、OAuth 或密码找回。

## 加密凭据 CLI

凭据库位于 `ROAMBOT_DATA_DIR/credentials.vault`。主密码和 API key 只通过隐藏终端输入，
不会作为命令参数或环境变量值传入：

```powershell
.\.venv\Scripts\roambot.exe credentials init
.\.venv\Scripts\roambot.exe credentials status
.\.venv\Scripts\roambot.exe credentials set amap
.\.venv\Scripts\roambot.exe credentials set qweather
.\.venv\Scripts\roambot.exe credentials set llm
.\.venv\Scripts\roambot.exe credentials clear amap
.\.venv\Scripts\roambot.exe credentials reset
```

`status` 只显示 configured/unconfigured，不回显 key。普通更新和清除需要当前主密码；忘记
主密码时只能输入精确确认词 `RESET-CREDENTIALS` 删除旧凭据库并重新录入。reset 不会
删除同目录的 `roambot.db`，但旧 key 仍应在供应商控制台吊销。凭据文件会请求限制性
权限；Windows 上 `chmod(0o600)` 不能替代正确的本机账户权限和 ACL 管理。

## 本地验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -W error
.\.venv\Scripts\python.exe -m ruff check backend
git diff --check
```

以上自动测试全部使用临时数据库、临时凭据库、假 key 和 Mock providers，不执行外部
网络 I/O，也不证明真实高德、QWeather 或 LLM 服务已连通。

## 真实 Provider 人工 Smoke

自动测试和 CI 始终使用 Mock providers。只有下面这条人工命令可以访问真实服务；运行前必须先明确确认，因为完整检查最多消耗 5 次调用：高德 3 次、QWeather 1 次、LLM 1 次。命令不会自动重试，也不会输出 key、主密码、请求 URL、请求头、原始响应、私人地址或 LLM prompt。

先配置非敏感运行参数。`ROAMBOT_QWEATHER_API_HOST` 必须填写和风天气控制台分配的账户专属 API Host；示例值不可直接使用：

```powershell
$env:ROAMBOT_PROVIDER_MODE = "live"
$env:ROAMBOT_DEMO_MODE = "false"
$env:ROAMBOT_QWEATHER_API_HOST = "https://YOUR-HOST.qweatherapi.com"
$env:ROAMBOT_LLM_BASE_URL = "https://YOUR-SCHOOL-API-HOST"
$env:ROAMBOT_LLM_MODEL = "YOUR-MODEL-NAME"
```

API key 和主密码不得写入环境变量、`.env`、命令参数或聊天。使用已有隐藏输入命令录入：

```powershell
.\.venv\Scripts\roambot.exe credentials status
.\.venv\Scripts\roambot.exe credentials set amap
.\.venv\Scripts\roambot.exe credentials set qweather
.\.venv\Scripts\roambot.exe credentials set llm
```

可先逐个验证服务，或跳过可能计费的 LLM：

```powershell
.\.venv\Scripts\roambot.exe providers smoke --only amap
.\.venv\Scripts\roambot.exe providers smoke --only qweather
.\.venv\Scripts\roambot.exe providers smoke --only llm
.\.venv\Scripts\roambot.exe providers smoke --skip-llm
.\.venv\Scripts\roambot.exe providers smoke
```

命令只使用“苏州站”和“金鸡湖景区”等公共演示地点，输出仅包含 provider 成功/失败状态、固定调用次数、缓存状态、候选数和生成时间。未获得明确的真实调用许可前，不要运行该命令。
