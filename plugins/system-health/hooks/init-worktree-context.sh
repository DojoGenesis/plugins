#!/usr/bin/env bash
# init-worktree-context.sh — fires on WorktreeCreate; logs the new worktree path.
# ADVISORY ONLY — always exits 0, never blocks.

set -euo pipefail

INPUT=$(cat)

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
session_id = data.get('session_id', 'unknown')[:12]

# Worktree path may appear in tool_input as a path, directory, or worktree field
tool_input = data.get('tool_input', {})
if isinstance(tool_input, dict):
    worktree_path = (
        tool_input.get('path')
        or tool_input.get('worktree')
        or tool_input.get('directory')
        or tool_input.get('command', '')
    )
else:
    worktree_path = str(tool_input)

worktree_path = str(worktree_path).strip() or 'unknown'
print(session_id)
print(worktree_path)
" "$INPUT" 2>/dev/null || printf "unknown\nunknown")

SESSION_ID=$(echo "$PARSED" | sed -n '1p')
WORKTREE_PATH=$(echo "$PARSED" | sed -n '2p')

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} [${SESSION_ID}] worktree-created path=${WORKTREE_PATH}" >> "${LOG_DIR}/worktree-events.log"

exit 0
