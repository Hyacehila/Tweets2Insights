$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location -LiteralPath $repoRoot
try {
    uv run --project backend python scripts/dev.py start
} finally {
    Pop-Location
}
