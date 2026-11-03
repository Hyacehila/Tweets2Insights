$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = $repoRoot
Push-Location -LiteralPath $repoRoot
try {
    uv run streamlit run intelligent_ui/app.py
} finally {
    Pop-Location
}
