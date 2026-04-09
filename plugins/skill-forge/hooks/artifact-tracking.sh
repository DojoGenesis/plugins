#!/usr/bin/env bash
# artifact-tracking.sh — fires on PostToolUse(Bash) when command matches "* skill package*".
# Appends a JSONL record to packaging-log.jsonl for artifact provenance tracking.
# ADVISORY ONLY — always exits 0, never blocks.

set -euo pipefail

INPUT=$(cat)

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
session_id = data.get('session_id', 'unknown')[:12]

tool_input = data.get('tool_input', {})
if isinstance(tool_input, dict):
    cmd = tool_input.get('command', '')
else:
    cmd = str(tool_input)

tool_result = str(data.get('tool_result', ''))

# Only proceed if command contains both 'skill' and 'package'
if 'skill' not in cmd and 'package' not in cmd:
    sys.exit(1)

cmd_truncated = cmd[:100].replace('\n', ' ').replace('\r', '')
result_snippet = tool_result[:200].replace('\n', ' ').replace('\r', '').replace('\"', '\\\\\"')

print(session_id)
print(cmd_truncated)
print(result_snippet)
" "$INPUT" 2>/dev/null || exit 0)

SESSION_ID=$(echo "$PARSED" | sed -n '1p')
CMD_TRUNCATED=$(echo "$PARSED" | sed -n '2p')
RESULT_SNIPPET=$(echo "$PARSED" | sed -n '3p')

# Exit cleanly if python script found no match (skill+package not both present)
if [ -z "${SESSION_ID}" ]; then
  exit 0
fi

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 -c "
import json, sys
record = {
    'timestamp': sys.argv[1],
    'session_id': sys.argv[2],
    'command': sys.argv[3],
    'result_snippet': sys.argv[4]
}
print(json.dumps(record))
" "${TIMESTAMP}" "${SESSION_ID}" "${CMD_TRUNCATED}" "${RESULT_SNIPPET}" >> "${LOG_DIR}/packaging-log.jsonl"

exit 0
