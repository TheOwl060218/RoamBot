$ErrorActionPreference = 'Stop'

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host "==> $Label"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Test-TcpPortInUse {
    param([Parameter(Mandatory = $true)][int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        return $connect.Wait(300) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-ForHttpServer {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process
    )

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) {
            throw "$Name exited before becoming ready."
        }
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }
    throw "$Name did not become ready within 30 seconds."
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }
    if (-not $Process.HasExited) {
        & cmd.exe /d /c "taskkill /PID $($Process.Id) /T /F >nul 2>&1"
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    $Process.Dispose()
}

function Normalize-ProcessPathEnvironment {
    $pathEntries = @(
        [System.Environment]::GetEnvironmentVariables().GetEnumerator() |
            Where-Object { $_.Key -ieq 'Path' }
    )
    if ($pathEntries.Count -le 1) {
        return
    }

    $preferredEntry = $pathEntries | Where-Object { $_.Key -ceq 'Path' } | Select-Object -First 1
    if ($null -eq $preferredEntry) {
        $preferredEntry = $pathEntries[0]
    }
    [System.Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
    [System.Environment]::SetEnvironmentVariable('Path', [string]$preferredEntry.Value, 'Process')
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Normalize-ProcessPathEnvironment

if (-not $env:ROAMBOT_PROVIDER_MODE) {
    $env:ROAMBOT_PROVIDER_MODE = 'mock'
}
if (-not $env:ROAMBOT_DEMO_MODE) {
    $env:ROAMBOT_DEMO_MODE = 'true'
}
if ($env:ROAMBOT_PROVIDER_MODE -ne 'mock' -or $env:ROAMBOT_DEMO_MODE -ne 'true') {
    throw 'Automated tests require mock provider mode with demo data.'
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Python virtual environment not found. Create .venv and install backend dev dependencies first.'
}

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $node = $nodeCommand.Source
} else {
    $node = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (-not (Test-Path $node)) {
        throw 'Node.js was not found. Install Node.js 24 LTS or make node.exe available on PATH.'
    }
}

Invoke-NativeStep 'Backend tests' $python @('-m', 'pytest', 'backend/tests', '-q')
Invoke-NativeStep 'Backend lint' $python @('-m', 'ruff', 'check', 'backend/src', 'backend/tests')

Push-Location (Join-Path $root 'frontend')
try {
    Invoke-NativeStep 'Frontend tests' $node @('node_modules/vitest/vitest.mjs', 'run')
    Invoke-NativeStep 'Frontend lint' $node @('node_modules/eslint/bin/eslint.js', '.')
    Invoke-NativeStep 'Frontend type check' $node @('node_modules/typescript/bin/tsc', '-b')
    Invoke-NativeStep 'Frontend build' $node @('node_modules/vite/bin/vite.js', 'build')

    Write-Host '==> Browser journeys'
    $backendPort = if ($env:ROAMBOT_E2E_BACKEND_PORT) { [int]$env:ROAMBOT_E2E_BACKEND_PORT } else { 8010 }
    $frontendPort = if ($env:ROAMBOT_E2E_FRONTEND_PORT) { [int]$env:ROAMBOT_E2E_FRONTEND_PORT } else { 5183 }
    if (Test-TcpPortInUse $backendPort) {
        throw "Browser-test backend port $backendPort is already in use."
    }
    if (Test-TcpPortInUse $frontendPort) {
        throw "Browser-test frontend port $frontendPort is already in use."
    }

    $env:ROAMBOT_E2E_BACKEND_PORT = [string]$backendPort
    $env:ROAMBOT_E2E_FRONTEND_PORT = [string]$frontendPort
    $env:ROAMBOT_E2E_RUN_ID = [string]$PID
    $env:ROAMBOT_SECURE_COOKIES = 'false'
    $env:ROAMBOT_DATA_DIR = Join-Path $root ".playwright-data\$PID"
    $env:ROAMBOT_E2E_API_TARGET = "http://127.0.0.1:$backendPort"
    $env:PW_REUSE_SERVERS = '1'

    $backendProcess = $null
    $frontendProcess = $null
    $browserExitCode = 1
    try {
        $backendProcess = Start-Process -FilePath $python `
            -ArgumentList @('-m', 'uvicorn', 'roambot.main:app', '--app-dir', 'backend/src', '--host', '127.0.0.1', '--port', [string]$backendPort) `
            -WorkingDirectory $root -PassThru -WindowStyle Hidden
        Wait-ForHttpServer 'Browser-test backend' "http://127.0.0.1:$backendPort/api/v1/health" $backendProcess

        $frontendProcess = Start-Process -FilePath $node `
            -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', [string]$frontendPort) `
            -WorkingDirectory (Join-Path $root 'frontend') -PassThru -WindowStyle Hidden
        Wait-ForHttpServer 'Browser-test frontend' "http://127.0.0.1:$frontendPort" $frontendProcess

        & $node 'node_modules/@playwright/test/cli.js' 'test'
        $browserExitCode = $LASTEXITCODE
    } finally {
        Stop-ProcessTree $frontendProcess
        Stop-ProcessTree $backendProcess
    }
    if ($browserExitCode -ne 0) {
        exit $browserExitCode
    }
} finally {
    Pop-Location
}
