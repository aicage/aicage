#!/usr/bin/env bash
set -euo pipefail

npm install -g @opencode/cli

install -d /usr/share/licenses/opencode
curl \
  -fsSL \
  --retry 8 \
  --retry-all-errors \
  --retry-delay 2 \
  --max-time 300 \
  https://raw.githubusercontent.com/anomalyco/opencode/dev/LICENSE \
  -o /usr/share/licenses/opencode/LICENSE
