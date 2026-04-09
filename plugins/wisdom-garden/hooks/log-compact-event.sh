#!/usr/bin/env bash
# log-compact-event.sh — fires on PostCompact; appends a timestamped entry to compress-queue.log

set -euo pipefail

INPUT=$(cat)

SESSION_ID=$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
print(data.get('session_id', 'unknown')[:12])
" "$INPUT" 2>/dev/null || echo "unknown")

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} session=${SESSION_ID} context-compacted" >> "${LOG_DIR}/compress-queue.log"
