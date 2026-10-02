#!/usr/bin/env bash
# log-pdf-export.sh — fires on PostToolUse for mcp__* tools; logs PDF export events.
# Fails open: it exits 0 for every call that is not an export, and for any error.
# (Before 0.2.1 it exited 1 on every non-export call, because `set -e` fired on the
# parser's "not applicable" exit code before the check that was meant to handle it.)

INPUT=$(cat) || exit 0

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
tool_name = data.get('tool_name', '')

# Only proceed if tool_name contains 'export'
if 'export' not in tool_name.lower():
    sys.exit(1)

tool_input = data.get('tool_input', {})
if isinstance(tool_input, str):
    try:
        tool_input = json.loads(tool_input)
    except Exception:
        tool_input = {}

output_path = tool_input.get('output_path', tool_input.get('outputPath', tool_input.get('output', '(unknown)')))
input_file = tool_input.get('input_file', tool_input.get('inputFile', tool_input.get('source', tool_input.get('input', '(unknown)'))))

print(input_file)
print(output_path)
" "$INPUT" 2>/dev/null) || exit 0

[ -n "$PARSED" ] || exit 0

INPUT_FILE=$(echo "$PARSED" | sed -n '1p')
OUTPUT_PATH=$(echo "$PARSED" | sed -n '2p')

LOG_DIR="${CLAUDE_PLUGIN_DATA:-}"
[ -n "$LOG_DIR" ] || exit 0
mkdir -p "$LOG_DIR" 2>/dev/null || exit 0

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} exported: ${INPUT_FILE} → ${OUTPUT_PATH}" >> "${LOG_DIR}/exports.log" 2>/dev/null || true
exit 0
