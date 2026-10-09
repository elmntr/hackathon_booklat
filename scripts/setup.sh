#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. On Arch Linux, install it with: sudo pacman -S uv" >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  uv venv .venv
fi
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python scripts/download_model.py
echo "Setup complete. Run ./run.sh"
