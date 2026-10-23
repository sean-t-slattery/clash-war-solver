$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & '.venv\Scripts\python.exe' -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed' }
    Push-Location 'apps\web'
    try {
        & node 'node_modules\typescript\bin\tsc' -b
        if ($LASTEXITCODE -ne 0) { throw 'TypeScript validation failed' }
        & node 'node_modules\vite\bin\vite.js' build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
} finally { Pop-Location }
