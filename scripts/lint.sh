#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

# YAML
yamllint --config-file .github/linters/.yamllint .

# Markdown
pymarkdown \
  --config .github/linters/.pymarkdown.json scan \
  --recurse \
  --exclude '**/.venv*/**' \
  .

# ruff (Python)
ruff check .

# pyright (Python)
pyright .

# mypy (Python)
mypy --config-file .github/linters/.mypy.ini .

# Ignore generated version metadata from setuptools-scm.
if rg_output=$(rg -n --glob '*.py' --glob '!src/*/_version.py' '__all__' src); then
  printf '%s\n' "$rg_output"
  echo "Found __all__ usage in src; remove it to satisfy visibility checks."
  exit 1
else
  rg_status=$?
  if [[ $rg_status -ne 1 ]]; then
    exit $rg_status
  fi
fi

# Shellcheck
mapfile -t shell_scripts < <(find . -type f -name '*.sh' -not -path './.venv*/*' | sort)

if [[ ${#shell_scripts[@]} -gt 0 ]]; then
  echo "Validate shell scripts with bash -n"
  for script in "${shell_scripts[@]}"; do
    bash -n "${script}"
  done

  echo "Run shellcheck"
  shellcheck -x "${shell_scripts[@]}"
fi

echo "Validate PowerShell scripts with PowerShell"
docker run --rm \
  --mount "type=bind,src=$repo_root,dst=/workspace,readonly" \
  mcr.microsoft.com/powershell:latest \
  pwsh -NoProfile -Command '
    $scripts = Get-ChildItem -Path /workspace -Recurse -Force -File -Filter *.ps1 |
      Where-Object { $_.FullName -notlike "/workspace/.venv*/*" }
    foreach ($script in $scripts) {
      $tokens = $null
      $errors = $null
      [System.Management.Automation.Language.Parser]::ParseFile(
        $script.FullName, [ref]$tokens, [ref]$errors
      ) | Out-Null
      if ($errors.Count) {
        $errors | Format-List | Out-String | Write-Error
        exit 1
      }
    }
  '

# flake8
flake8 --config .github/linters/.flake8 .

# pylint (Python)
# find all .venv* folders and pass them as comma separated list to pylint --ignore
venv_directories=$(printf '%s\n' .venv*/ | sed -E 's#/$##' | paste -sd, -)
PYTHONPATH=src pylint --rcfile=.github/linters/.pylintrc --ignore="$venv_directories" .

# bandit
bandit --quiet -c .github/linters/.bandit.yml -r src scripts 2>/dev/null
