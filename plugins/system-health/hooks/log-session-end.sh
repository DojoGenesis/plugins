#!/usr/bin/env bash
# log-session-end.sh — fires on SessionEnd; appends a timestamped session close entry.
# ADVISORY ONLY — always exits 0, never blocks.

set -euo pipefail

INPUT=$(cat)

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
session_id = data.get('session_id', 'unknown')[:12]
reason = data.get('reason', '')
print(session_id)
print(reason)
" "$INPUT" 2>/dev/null || printf "unknown\n")

SESSION_ID=$(echo "$PARSED" | sed -n '1p')
REASON=$(echo "$PARSED" | sed -n '2p')

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ -n "${REASON}" ]; then
  echo "${TIMESTAMP} [${SESSION_ID}] session-ended reason=${REASON}" >> "${LOG_DIR}/sessions.log"
else
  echo "${TIMESTAMP} [${SESSION_ID}] session-ended" >> "${LOG_DIR}/sessions.log"
fi

exit 0
