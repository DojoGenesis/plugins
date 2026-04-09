#!/usr/bin/env bash
# index-handoff.sh — fires on PostToolUse(Write) when a file matching **/handoffs/*.md is written.
# Appends a timestamped entry to ${CLAUDE_PLUGIN_DATA}/handoff-index.log and echoes confirmation.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
tool_input = data.get('tool_input', {})
print(tool_input.get('file_path', 'unknown'))
" "$INPUT" 2>/dev/null || echo "unknown")

SESSION_ID=$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
print(data.get('session_id', 'unknown')[:12])
" "$INPUT" 2>/dev/null || echo "unknown")

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} [${SESSION_ID}] handoff-written: ${FILE_PATH}" >> "${LOG_DIR}/handoff-index.log"

echo "Handoff indexed: ${FILE_PATH}"

exit 0
