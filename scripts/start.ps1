param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'apps\web\dist\index.html')) {
        & (Join-Path $PSScriptRoot 'setup.ps1')
    }
    if (Test-Path -LiteralPath '.env') {
        foreach ($line in Get-Content -LiteralPath '.env') {
            if ($line -match '^\s*(COC_API_TOKEN|WAR_DATA_DIR)\s*=\s*(.*)\s*$') {
                [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim().Trim('"').Trim("'"), 'Process')
            }
        }
    }
    Write-Host "War Workbench: http://127.0.0.1:$Port (Ctrl+C to stop)"
    & '.venv\Scripts\python.exe' -m backend.cli serve --port $Port
} finally { Pop-Location }
