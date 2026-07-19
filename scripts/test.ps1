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

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

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
    Invoke-NativeStep 'Browser journeys' $node @('node_modules/@playwright/test/cli.js', 'test')
} finally {
    Pop-Location
}
