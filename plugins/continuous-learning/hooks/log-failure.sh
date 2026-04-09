#!/usr/bin/env bash
# log-failure.sh — fires on PostToolUseFailure; appends error snippet to failures.log

set -euo pipefail

INPUT=$(cat)

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
session_id = data.get('session_id', 'unknown')[:12]
tool_name = data.get('tool_name', 'unknown')
tool_result = str(data.get('tool_result', ''))[:300]
# Collapse newlines for single-line log entry
tool_result = tool_result.replace('\n', ' ').replace('\r', '')
print(session_id)
print(tool_name)
print(tool_result)
" "$INPUT" 2>/dev/null || printf "unknown\nunknown\n(parse error)")

SESSION_ID=$(echo "$PARSED" | sed -n '1p')
TOOL_NAME=$(echo "$PARSED" | sed -n '2p')
ERROR_SNIPPET=$(echo "$PARSED" | sed -n '3p')

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} [${SESSION_ID}] ${TOOL_NAME}: ${ERROR_SNIPPET}" >> "${LOG_DIR}/failures.log"
