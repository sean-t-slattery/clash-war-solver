param([string]$Python = "", [string]$Pnpm = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not $Python) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = 'py' }
        else { $Python = 'python' }
    }
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        if ($Python -eq 'py') { & $Python -3.12 -m venv .venv }
        else { & $Python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed. Install Python 3.12 or pass -Python.' }
    }
    & '.venv\Scripts\python.exe' -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ is required"'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required' }
    & '.venv\Scripts\python.exe' -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    if (-not $Pnpm) {
        $bundledPnpm = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd'
        if (Get-Command pnpm -ErrorAction SilentlyContinue) { $Pnpm = 'pnpm' }
        elseif (Test-Path -LiteralPath $bundledPnpm) { $Pnpm = $bundledPnpm }
        else { throw 'Install Node.js 22+ and pnpm 10+ or pass -Pnpm.' }
    }
    Push-Location 'apps\web'
    try {
        & $Pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
        & $Pnpm build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed' }
    } finally { Pop-Location }
    & '.venv\Scripts\python.exe' -m backend.cli init
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed' }
    Write-Host 'Setup complete. Run .\scripts\start.ps1 and open http://127.0.0.1:8000'
} finally { Pop-Location }
