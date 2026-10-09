#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Environment missing. Run ./scripts/setup.sh once while online." >&2
  exit 1
fi
export HF_HUB_OFFLINE=1
exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
