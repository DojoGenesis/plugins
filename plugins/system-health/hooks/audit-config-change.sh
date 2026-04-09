#!/usr/bin/env bash
# audit-config-change.sh — fires on ConfigChange; logs config mutations with policy warnings.
# ADVISORY ONLY — always exits 0, never blocks.

set -euo pipefail

INPUT=$(cat)

PARSED=$(python3 -c "
import json, sys

data = json.loads(sys.argv[1])
session_id = data.get('session_id', 'unknown')[:12]
hook_event = data.get('hook_event_name', 'ConfigChange')
source = data.get('source', data.get('change_type', 'unknown'))
print(session_id)
print(hook_event)
print(source)
" "$INPUT" 2>/dev/null || printf "unknown\nConfigChange\nunknown")

SESSION_ID=$(echo "$PARSED" | sed -n '1p')
HOOK_EVENT=$(echo "$PARSED" | sed -n '2p')
SOURCE=$(echo "$PARSED" | sed -n '3p')

LOG_DIR="${CLAUDE_PLUGIN_DATA}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "${TIMESTAMP} [${SESSION_ID}] config-changed source=${SOURCE}" >> "${LOG_DIR}/config-audit.log"

# If source contains "policy", emit a prominent warning to stderr
if echo "${SOURCE}" | grep -qi "policy"; then
  echo "WARNING: Policy-related config change detected (source=${SOURCE}, session=${SESSION_ID}). Review ${LOG_DIR}/config-audit.log." >&2
fi

exit 0
