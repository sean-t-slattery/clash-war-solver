# Production bundle served by FastAPI is the default one-command local workflow.
# For hot reload, run the backend plus `pnpm --dir apps/web dev` in another terminal.
& (Join-Path $PSScriptRoot 'start.ps1')
