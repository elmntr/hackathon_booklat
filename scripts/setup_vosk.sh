#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "First run ./scripts/setup.sh to prepare Booklat's environment." >&2
  exit 1
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "pip is missing from .venv. Run ./scripts/setup.sh first, then retry Vosk setup." >&2
  exit 1
fi
.venv/bin/python -m pip install -r requirements-vosk.txt
.venv/bin/python scripts/download_vosk.py
echo "Vosk setup complete. Restart ./run.sh and select Vosk in Booklat."
