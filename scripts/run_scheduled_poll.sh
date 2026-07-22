#!/bin/zsh

set -euo pipefail

REPO_ROOT="/Users/williamherridge/Documents/repos/cata-email-assistant"
LOG_DIR="$REPO_ROOT/data/processed/logs"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

exec "$REPO_ROOT/.venv/bin/python3" "$REPO_ROOT/scripts/run_scheduled_poll.py" >> "$LOG_DIR/scheduled_poll.log" 2>&1
