#!/usr/bin/env bash
# batch-preflight.sh — fires on PreToolUse(Bash) when command matches "* batch-normalize*".
# Validates that batch-normalize inputs look sane before execution.
# ADVISORY ONLY — always exits 0, never blocks.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
tool_input = data.get('tool_input', {})
if isinstance(tool_input, dict):
    cmd = tool_input.get('command', '')
else:
    cmd = str(tool_input)
print(cmd)
" "$INPUT" 2>/dev/null || echo "")

# Only act on batch-normalize or normalize commands
if ! echo "${COMMAND}" | grep -qE "(batch-normalize|normalize)"; then
  exit 0
fi

# Check if the CoworkPluginsByDojoGenesis directory exists (canonical plugins dir)
PLUGINS_DIR="${CLAUDE_PROJECT_DIR}/CoworkPluginsByDojoGenesis"
if [ -d "${PLUGINS_DIR}" ]; then
  echo "Preflight: batch-normalize inputs look valid (plugins dir found at ${PLUGINS_DIR})"
else
  # Try the project dir itself as a fallback (may already be inside CoworkPluginsByDojoGenesis)
  if [ -d "${CLAUDE_PROJECT_DIR}/plugins" ]; then
    echo "Preflight: batch-normalize inputs look valid (plugins dir found at ${CLAUDE_PROJECT_DIR}/plugins)"
  else
    echo "Preflight warning: could not locate plugins directory at ${PLUGINS_DIR} or ${CLAUDE_PROJECT_DIR}/plugins — verify source paths before proceeding"
  fi
fi

# Check if command references any explicit path that does not exist
REFERENCED_PATH=$(python3 -c "
import re, sys
cmd = sys.argv[1]
# Look for path-like tokens (anything starting with / or ~/ or ./)
matches = re.findall(r'(?:^|\s)((?:/|~/|\./)[\w/._-]+)', cmd)
print(matches[0] if matches else '')
" "${COMMAND}" 2>/dev/null || echo "")

if [ -n "${REFERENCED_PATH}" ] && [ ! -e "${REFERENCED_PATH}" ]; then
  echo "Preflight warning: referenced path '${REFERENCED_PATH}' does not exist — confirm path before running batch-normalize"
fi

exit 0
