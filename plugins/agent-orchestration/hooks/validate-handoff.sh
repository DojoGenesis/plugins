#!/usr/bin/env bash
# validate-handoff.sh — fires on SubagentStop; checks that a handoff package was written.
# ADVISORY ONLY — always exits 0, never blocks. Logs to ${CLAUDE_PLUGIN_DATA}/subagent-stops.log.

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
HANDOFFS_DIR="${CLAUDE_PROJECT_DIR}/handoffs"
LOG_STATUS="no-handoffs-dir"

if [ ! -d "${HANDOFFS_DIR}" ]; then
  # No handoffs directory at all — project may not use handoff-protocol
  echo "${TIMESTAMP} session=${SESSION_ID} status=no-handoffs-dir" >> "${LOG_DIR}/subagent-stops.log"
  exit 0
fi

# Check for any .md file modified in the last 10 minutes
RECENT=$(find "${HANDOFFS_DIR}" -name "*.md" -newer /tmp -newer "${HANDOFFS_DIR}" -mmin -10 2>/dev/null | head -1 || true)

# Fallback: use find with -mmin directly (more portable)
RECENT=$(find "${HANDOFFS_DIR}" -name "*.md" -mmin -10 2>/dev/null | head -1 || true)

if [ -n "${RECENT}" ]; then
  LOG_STATUS="handoff-found"
  echo "${TIMESTAMP} session=${SESSION_ID} status=handoff-found file=${RECENT}" >> "${LOG_DIR}/subagent-stops.log"
else
  LOG_STATUS="handoff-missing"
  echo "Warning: SubagentStop fired but no recent handoff package found in ${HANDOFFS_DIR} — consider writing a handoff package using the handoff-protocol skill." >&2
  echo "${TIMESTAMP} session=${SESSION_ID} status=handoff-missing" >> "${LOG_DIR}/subagent-stops.log"
fi

exit 0
