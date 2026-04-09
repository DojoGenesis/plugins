#!/usr/bin/env bash
# check-track-ownership.sh — fires on PreToolUse(Write|Edit); warns if a file belongs to a
# different parallel track. ADVISORY ONLY — always exits 0, never blocks.
# No-op if ${CLAUDE_PROJECT_DIR}/.parallel-tracks/manifest.json does not exist.

set -euo pipefail

INPUT=$(cat)

MANIFEST="${CLAUDE_PROJECT_DIR}/.parallel-tracks/manifest.json"

if [ ! -f "${MANIFEST}" ]; then
  # No parallel tracks in progress — nothing to check
  exit 0
fi

python3 - "$INPUT" "$MANIFEST" <<'PYEOF'
import json, sys, os

raw_input = sys.argv[1]
manifest_path = sys.argv[2]

try:
    data = json.loads(raw_input)
except Exception:
    sys.exit(0)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Write uses file_path; Edit uses path
if tool_name == "Write":
    target_file = tool_input.get("file_path", "")
elif tool_name == "Edit":
    target_file = tool_input.get("path", "")
else:
    target_file = tool_input.get("file_path", tool_input.get("path", ""))

if not target_file:
    sys.exit(0)

try:
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
except Exception:
    sys.exit(0)

# Expected format: {"tracks": {"track-a": {"files": ["src/...", ...]}, "track-b": {...}}}
tracks = manifest.get("tracks", {})
if not tracks:
    sys.exit(0)

owning_track = None
for track_name, track_data in tracks.items():
    owned_files = track_data.get("files", [])
    for owned_path in owned_files:
        # Match if the target file starts with the owned prefix or equals it exactly
        if target_file == owned_path or target_file.startswith(owned_path.rstrip("/") + "/"):
            owning_track = track_name
            break
    if owning_track:
        break

if owning_track is None:
    # File not claimed by any track — no conflict
    sys.exit(0)

# We have no reliable way to know "which track" the current agent is, so we surface
# ownership info whenever a file is owned by any track.
print(f"⚠ Track ownership: {target_file} is assigned to {owning_track}. Coordinate before modifying.")

sys.exit(0)
PYEOF

exit 0
