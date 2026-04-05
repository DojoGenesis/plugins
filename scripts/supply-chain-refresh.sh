#!/usr/bin/env bash
# supply-chain-refresh.sh — Weekly supply chain refresh pipeline
# Usage: ./supply-chain-refresh.sh [staging-dir] [cas-db-path]
set -euo pipefail

STAGING="${1:-/tmp/dojo-supply-chain/staging}"
CAS_DB="${2:-/tmp/dojo-supply-chain/dojo-skills.db}"
REPOS_DIR="/tmp/dojo-supply-chain/repos"
REPORT_DIR="/tmp/dojo-supply-chain/reports"
DOJO="/Users/alfonsomorales/ZenflowProjects/AgenticGatewayByDojoGenesis/bin/dojo"
NORMALIZE="/Users/alfonsomorales/ZenflowProjects/CoworkPluginsByDojoGenesis/scripts/normalize-skill.sh"

echo "=== Supply Chain Refresh $(date -Iseconds) ==="

# Step 1: Pull latest from all repos
echo "[1/5] Pulling latest from repos..."
for repo_dir in "$REPOS_DIR"/*/; do
    repo_name=$(basename "$repo_dir")
    if [ -d "$repo_dir/.git" ]; then
        echo "  Pulling $repo_name..."
        (cd "$repo_dir" && git pull --ff-only 2>/dev/null) || echo "  WARN: pull failed for $repo_name"
        sleep 1  # rate limit
    fi
done

# Step 2: Scan for SKILL.md files
echo "[2/5] Scanning for skills..."
SKILL_COUNT=$(find "$REPOS_DIR" -name "SKILL.md" | wc -l | tr -d ' ')
echo "  Found $SKILL_COUNT SKILL.md files"

# Step 3: Normalize all
echo "[3/5] Normalizing skills..."
NORMALIZED=0
FAILED=0
find "$REPOS_DIR" -name "SKILL.md" | while read f; do
    rel=$(echo "$f" | sed "s|$REPOS_DIR/||")
    repo=$(echo "$rel" | cut -d/ -f1)
    skill_name=$(basename "$(dirname "$f")")
    if [ "$skill_name" = "." ] || [ "$skill_name" = "repos" ]; then
        skill_name=$(echo "$rel" | tr '/' '-' | sed 's/-SKILL.md//')
    fi
    outdir="$STAGING/$repo/$skill_name"
    outfile="$outdir/SKILL.md"

    if head -1 "$f" | grep -q '^---'; then
        if grep -q '^name:' "$f" && grep -q '^description:' "$f"; then
            "$NORMALIZE" "$f" "$outfile" 2>/dev/null && NORMALIZED=$((NORMALIZED + 1)) || FAILED=$((FAILED + 1))
        fi
    fi
done
echo "  Normalized: $SKILL_COUNT skills"

# Step 4: Package into CAS
echo "[4/5] Packaging into CAS..."
export DOJO_CAS_PATH="$CAS_DB"
$DOJO skill package-all "$STAGING" 2>&1 | tail -1

# Step 5: Report
echo "[5/5] Generating report..."
PACKAGED=$($DOJO skill list 2>&1 | wc -l | tr -d ' ')
echo ""
echo "=== Supply Chain Refresh Complete ==="
echo "  Repos scanned: $(ls -d "$REPOS_DIR"/*/ 2>/dev/null | wc -l | tr -d ' ')"
echo "  Skills found: $SKILL_COUNT"
echo "  Skills in CAS: $PACKAGED"
echo "  Timestamp: $(date -Iseconds)"
