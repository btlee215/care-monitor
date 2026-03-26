#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "=== Run started at $TIMESTAMP ===" >> logs/monitor.log

/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 monitor.py --config config.yaml >> logs/monitor.log 2>&1

echo "=== Run finished at $(date '+%Y-%m-%d %H:%M:%S') ===" >> logs/monitor.log
