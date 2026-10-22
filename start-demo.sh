#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -f .venv/local-ready.txt ]; then
  python3 scripts/setup_local.py
fi
printf 'So Thu Chi AI Local: http://localhost:8000\n'
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
