# RoamBot M1 核心后端

> [!IMPORTANT]
> 当前 M1 只使用确定性的 Mock providers。创建环境、运行测试和启动本地 API
> 都不需要高德、QWeather 或 LLM 的真实凭据。本里程碑的测试与本地检查也不证明
> 任何真实 provider 已连通。

## 环境要求

- Windows PowerShell
- Python 3.12 或 3.13

以下命令均在 **RoamBot 仓库根目录**执行，即同时包含 `backend`、`README.md`
和 `AGENT_LOG.md` 的目录。不要先切换到 `backend`。

## 创建与安装环境

以下示例使用 Python 3.12；使用 Python 3.13 时将第一条命令中的版本改为
`-3.13`。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
```

## 运行 M1 focused 测试

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q
```

该命令使用仓库内的确定性 Mock providers，不执行网络 I/O。

## 运行 Ruff

```powershell
.\.venv\Scripts\python.exe -m ruff check backend
```

## 启动本地 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn roambot.main:app --reload --host 127.0.0.1 --port 8000
```

保持该 PowerShell 窗口运行。在另一个位于仓库根目录的 PowerShell 窗口中，
可以检查健康接口：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health | ConvertTo-Json -Compress
```

也可以读取本地 OpenAPI 并列出路径：

```powershell
$openapi = Invoke-RestMethod http://127.0.0.1:8000/openapi.json
$openapi.paths.PSObject.Properties.Name | Sort-Object
```

当前 M1 应列出以下三个路径：

```text
/api/v1/health
/api/v1/place-evaluations
/api/v1/recommendations
```

以上检查仍然只覆盖 Mock-backed 本地应用，不代表高德、QWeather 或 LLM
真实 provider 的凭据有效或服务可达。
