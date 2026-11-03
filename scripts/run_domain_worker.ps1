$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location -LiteralPath $repoRoot
try {
    uv run python -m opinion_gateway.domain_worker --root .opinion-assets
} finally {
    Pop-Location
}
