$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location -LiteralPath $repoRoot
try {
    uv run --project backend python -m src.tools.worker
} finally {
    Pop-Location
}
