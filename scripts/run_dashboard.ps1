$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

# Ensure the project root is on PYTHONPATH so "dashboard" can be imported in Streamlit pages.
$env:PYTHONPATH = $repoRoot

Push-Location -LiteralPath $repoRoot
try {
    uv run streamlit run intelligent_ui/app.py
} finally {
    Pop-Location
}
