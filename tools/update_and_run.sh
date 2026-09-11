#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Local edits exist. Commit or review them before updating. No changes were discarded."
  exit 1
fi
git pull --ff-only origin main
python -m pip install -r requirements.txt
# Run interactively: Ctrl+C before updating again, then run this command again.
python run_factory.py --host 0.0.0.0 --port 8000 --no-browser
