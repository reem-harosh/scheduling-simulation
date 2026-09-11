#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "$(git status --porcelain --untracked-files=no)" ] && [ "$(git branch --show-current)" = main ]; then
  git pull --ff-only origin main
  python -m pip install -r requirements.txt
else
  echo "Preserving local edits or non-main branch; automatic update skipped."
fi
# flock ensures one server per checkout without killing unrelated processes.
nohup flock -n .simulation-server.lock python run_factory.py --host 0.0.0.0 --port 8000 --no-browser > /tmp/scheduling-simulation.log 2>&1 < /dev/null &
