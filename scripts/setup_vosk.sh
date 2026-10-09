#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "First run ./scripts/setup.sh to prepare Booklat's environment." >&2
  exit 1
fi
uv pip install --python .venv/bin/python -r requirements-vosk.txt
.venv/bin/python scripts/download_vosk.py
echo "Vosk setup complete. Restart ./run.sh and select Vosk in Booklat."
