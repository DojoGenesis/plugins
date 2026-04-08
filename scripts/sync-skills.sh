#!/usr/bin/env bash
# sync-skills.sh — Sync Tier 1 (canonical) skills to Tier 2 (distribution) bundles
# Usage: ./sync-skills.sh [--dry-run] [--report-only]
#
# Authority Model:
#   Tier 1 (canonical): dojo-genesis/skills/, claudeplugins/*/skills/
#   Tier 2 (distribution): AgenticGatewayByDojoGenesis/plugins/*/skills/,
#                           MCPByDojoGenesis/internal/skills/bundled/*/
#
# Compatible with bash 3.2+ (macOS default)
# See: AgenticStackOrchestration/docs/SKILLS_AUTHORITY.md
set -euo pipefail

# --- Configuration ---
BASE="/Users/alfonsomorales/ZenflowProjects"
CANONICAL_DOJO="$BASE/dojo-genesis/skills"
CANONICAL_PLUGINS="$BASE/claudeplugins"
GATEWAY="$BASE/AgenticGatewayByDojoGenesis/plugins"
MCP="$BASE/MCPByDojoGenesis/internal/skills/bundled"
REPORT_DIR="$BASE/AgenticStackOrchestration/docs/sync-reports"

DRY_RUN=false
REPORT_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --report-only) REPORT_ONLY=true; DRY_RUN=true ;;
    esac
done

mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/sync-$(date +%Y-%m-%d).md"

# Use a temp file as the canonical index (bash 3 compatible, no assoc arrays)
INDEX=$(mktemp /tmp/skill-index.XXXXXX)
trap "rm -f $INDEX" EXIT

echo "=== Skill Sync $(date -Iseconds) ==="
echo ""

# --- Counters (use temp files for subshell-safe counting) ---
COUNT_DIR=$(mktemp -d /tmp/skill-counts.XXXXXX)
trap "rm -rf $INDEX $COUNT_DIR" EXIT
echo 0 > "$COUNT_DIR/synced"
echo 0 > "$COUNT_DIR/skipped"
echo 0 > "$COUNT_DIR/backport"
echo 0 > "$COUNT_DIR/errors"

# --- Helper: hash a SKILL.md ---
skill_hash() {
    sed 's/[[:space:]]*$//' "$1" | md5 -q 2>/dev/null || md5sum "$1" | cut -d' ' -f1
}

# --- Helper: get line count ---
skill_lines() {
    wc -l < "$1" | tr -d ' '
}

# --- Helper: look up canonical path for a skill name ---
canonical_for() {
    local name="$1"
    grep "^${name}|" "$INDEX" 2>/dev/null | head -1 | cut -d'|' -f2 || true
}

# --- Helper: look up canonical plugin for a skill name ---
plugin_for() {
    local name="$1"
    grep "^${name}|" "$INDEX" 2>/dev/null | head -1 | cut -d'|' -f3 || true
}

# --- Helper: increment a counter ---
inc() {
    local f="$COUNT_DIR/$1"
    echo $(( $(cat "$f") + 1 )) > "$f"
}

# --- Helper: validate SKILL.md frontmatter ---
# Returns 0 if name:, description:, and triggers: are all present in YAML frontmatter.
# Returns 1 with error message on stderr if any are missing.
validate_skill() {
    local file="$1"
    local skill_name="$2"
    local missing=""

    # Extract YAML frontmatter (between first two --- lines)
    local frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/p' "$file" | head -50)

    if [ -z "$frontmatter" ]; then
        echo "  ERROR: $skill_name — no YAML frontmatter found" >&2
        return 1
    fi

    echo "$frontmatter" | grep -q "^name:" || missing="${missing}name "
    echo "$frontmatter" | grep -q "^description:" || missing="${missing}description "
    echo "$frontmatter" | grep -q "^triggers:" || missing="${missing}triggers "

    if [ -n "$missing" ]; then
        echo "  ERROR: $skill_name — missing required fields: ${missing}" >&2
        return 1
    fi
    return 0
}

# --- Build canonical skill index ---
echo "[1/4] Building canonical skill index..."

# Index claudeplugins (plugin-organized skills) — takes priority
for plugin_dir in "$CANONICAL_PLUGINS"/*/; do
    plugin_name=$(basename "$plugin_dir")
    skills_dir="$plugin_dir/skills"
    [ -d "$skills_dir" ] || continue
    for skill_dir in "$skills_dir"/*/; do
        [ -f "$skill_dir/SKILL.md" ] || continue
        skill_name=$(basename "$skill_dir")
        echo "${skill_name}|${skill_dir}SKILL.md|${plugin_name}" >> "$INDEX"
    done
done

# Index dojo-genesis (flat skills — only add if not already indexed)
for skill_dir in "$CANONICAL_DOJO"/*/; do
    [ -f "$skill_dir/SKILL.md" ] || continue
    skill_name=$(basename "$skill_dir")
    if ! grep -q "^${skill_name}|" "$INDEX"; then
        echo "${skill_name}|${skill_dir}SKILL.md|dojo-genesis" >> "$INDEX"
    fi
done

CANONICAL_COUNT=$(wc -l < "$INDEX" | tr -d ' ')
echo "  Indexed $CANONICAL_COUNT canonical skills"

# --- Start report ---
cat > "$REPORT" <<EOF
# Skill Sync Report

**Date:** $(date -Iseconds)
**Mode:** $([ "$DRY_RUN" = true ] && echo 'Dry Run' || echo 'Live')
**Canonical skills indexed:** $CANONICAL_COUNT

---

EOF

# --- Sync function ---
sync_to_target() {
    local target_base="$1"
    local target_label="$2"

    echo ""
    echo "  === $target_label ==="
    cat >> "$REPORT" <<EOF

## $target_label

| Skill | Plugin | Action | Canonical Lines | Target Lines | Hash Match |
|---|---|---|---|---|---|
EOF

    for plugin_dir in "$target_base"/*/; do
        plugin_name=$(basename "$plugin_dir")
        local skills_path=""

        if [ -d "$plugin_dir/skills" ]; then
            skills_path="$plugin_dir/skills"
        else
            skills_path="$plugin_dir"
        fi

        for skill_dir in "$skills_path"/*/; do
            [ -f "$skill_dir/SKILL.md" ] || continue
            skill_name=$(basename "$skill_dir")
            target_file="$skill_dir/SKILL.md"
            target_lines=$(skill_lines "$target_file")

            canonical_file=$(canonical_for "$skill_name")

            if [ -n "$canonical_file" ] && [ -f "$canonical_file" ]; then
                canonical_lines=$(skill_lines "$canonical_file")
                hash_canonical=$(skill_hash "$canonical_file")
                hash_target=$(skill_hash "$target_file")
                match="No"

                if [ "$hash_canonical" = "$hash_target" ]; then
                    action="In sync"
                    match="Yes"
                    inc skipped
                elif [ "$canonical_lines" -ge "$target_lines" ]; then
                    action="Sync from canonical"
                    if [ "$DRY_RUN" = false ]; then
                        # Validate canonical BEFORE copying
                        if ! validate_skill "$canonical_file" "$skill_name"; then
                            action="BLOCKED (canonical invalid)"
                            echo "    BLOCKED: $skill_name — canonical fails validation, skipping sync"
                            inc errors
                        else
                            # Backup target, copy, then validate result
                            cp "$target_file" "${target_file}.bak"
                            cp "$canonical_file" "$target_file"
                            if validate_skill "$target_file" "$skill_name"; then
                                rm -f "${target_file}.bak"
                                echo "    SYNC: $skill_name ($plugin_name) <- canonical [validated]"
                                inc synced
                            else
                                # Restore backup — sync produced invalid file
                                mv "${target_file}.bak" "$target_file"
                                action="REVERTED (post-copy validation failed)"
                                echo "    REVERTED: $skill_name — post-copy validation failed, restored original"
                                inc errors
                            fi
                        fi
                    else
                        echo "    [DRY] SYNC: $skill_name ($plugin_name) <- canonical"
                        inc synced
                    fi
                else
                    action="BACK-PORT CANDIDATE"
                    inc backport
                    echo "    WARN: $skill_name ($plugin_name) is $((target_lines - canonical_lines)) lines richer"
                fi

                echo "| $skill_name | $plugin_name | $action | $canonical_lines | $target_lines | $match |" >> "$REPORT"
            else
                echo "    NOTE: $skill_name ($plugin_name) — no canonical source"
                echo "| $skill_name | $plugin_name | No canonical | - | $target_lines | - |" >> "$REPORT"
            fi
        done
    done
}

# --- Execute sync ---
echo "[2/4] Scanning distribution targets..."

if [ -d "$GATEWAY" ]; then
    sync_to_target "$GATEWAY" "AgenticGatewayByDojoGenesis"
fi

if [ -d "$MCP" ]; then
    sync_to_target "$MCP" "MCPByDojoGenesis"
fi

# --- Back-port section ---
echo ""
echo "[3/5] Back-port candidates..."
BACKPORT_COUNT=$(cat "$COUNT_DIR/backport")
cat >> "$REPORT" <<EOF

---

## Back-Port Candidates

These distribution skills are richer than their canonical versions.
Review and back-port enhancements to Tier 1 before syncing.

EOF

if [ "$BACKPORT_COUNT" -eq 0 ]; then
    echo "*None found. All canonical versions are up-to-date or richer.*" >> "$REPORT"
fi

# --- Post-sync validation sweep ---
echo ""
echo "[4/5] Post-sync validation sweep..."
INVALID_COUNT=0

for target_base in "$GATEWAY" "$MCP"; do
    [ -d "$target_base" ] || continue
    for plugin_dir in "$target_base"/*/; do
        local_skills=""
        if [ -d "$plugin_dir/skills" ]; then
            local_skills="$plugin_dir/skills"
        else
            local_skills="$plugin_dir"
        fi
        for skill_dir in "$local_skills"/*/; do
            [ -f "$skill_dir/SKILL.md" ] || continue
            sname=$(basename "$skill_dir")
            if ! validate_skill "$skill_dir/SKILL.md" "$sname" 2>/dev/null; then
                echo "    INVALID: $sname in $(basename "$target_base")"
                INVALID_COUNT=$((INVALID_COUNT + 1))
            fi
        done
    done
done

if [ "$INVALID_COUNT" -eq 0 ]; then
    echo "  All distribution skills pass validation."
else
    echo "  WARNING: $INVALID_COUNT skills failed post-sync validation!"
    cat >> "$REPORT" <<EOF

## Post-Sync Validation

**$INVALID_COUNT skills failed frontmatter validation after sync.**
Run \`scripts/validate-skills.sh\` for details.

EOF
fi

# --- Summary ---
SYNCED_COUNT=$(cat "$COUNT_DIR/synced")
SKIPPED_COUNT=$(cat "$COUNT_DIR/skipped")
ERROR_COUNT=$(cat "$COUNT_DIR/errors")

echo ""
echo "[5/5] Summary"
echo ""
echo "  Canonical skills: $CANONICAL_COUNT"
echo "  Synced (Tier 1 -> Tier 2): $SYNCED_COUNT"
echo "  Already in sync: $SKIPPED_COUNT"
echo "  Back-port candidates: $BACKPORT_COUNT"
echo "  Errors: $ERROR_COUNT"
echo ""
echo "  Report: $REPORT"

cat >> "$REPORT" <<EOF

---

## Summary

| Metric | Count |
|---|---|
| Canonical skills indexed | $CANONICAL_COUNT |
| Synced (Tier 1 -> Tier 2) | $SYNCED_COUNT |
| Already in sync | $SKIPPED_COUNT |
| Back-port candidates | $BACKPORT_COUNT |
| Errors | $ERROR_COUNT |
EOF

echo ""
echo "=== Skill Sync Complete ==="
