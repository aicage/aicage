$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot

yamllint --config-file .github/linters/.yamllint .
pymarkdown --config .github/linters/.pymarkdown.json scan `
    --recurse `
    --exclude "**/.venv*/**" `
    --exclude "./aicage-custom-samples/" `
    --exclude "./aicage-image/" `
    --exclude "./aicage-image-base/" `
    --exclude "./aicage-image-util/" `
    .
ruff check .
pyright .

rg -n --glob "*.py" --glob "!src/*/_version.py" "__all__" src
if ($LASTEXITCODE -eq 0) {
    Write-Error "Found __all__ usage in src; remove it to satisfy visibility checks."
    exit 1
}
