#!/usr/bin/env bash
set -euo pipefail

curl \
  -fsSL \
  --retry 8 \
  --retry-all-errors \
  --retry-delay 2 \
  --max-time 300 \
  https://cli.kiro.dev/install |
  bash

for binary in /root/.local/bin/kiro-cli{,-chat,-term}; do
  if [[ -x "${binary}" ]]; then
    install -m 0755 "${binary}" "/usr/local/bin/$(basename "${binary}")"
  fi
done

# Remove root-home artifacts left by the installer; the image uses /usr/local/bin.
rm -f /root/.local/bin/kiro-cli{,-chat,-term}

if ! command -v kiro-cli >/dev/null 2>&1; then
  echo "[install_kiro] 'kiro-cli' executable not found after installation." >&2
  exit 1
fi
