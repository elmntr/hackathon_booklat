#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -m venv .venv; then
    echo "Could not create .venv. On Linux Mint, run: sudo apt install python3 python3-venv python3-pip" >&2
    exit 1
  fi
fi
if ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "Booklat needs Python 3.10 or newer. Recreate .venv with a supported Python version." >&2
  exit 1
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  if ! .venv/bin/python -m ensurepip --upgrade; then
    echo "Could not prepare pip. On Linux Mint, install python3-venv and rerun setup." >&2
    exit 1
  fi
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/download_model.py
echo "Setup complete. Run ./run.sh"
