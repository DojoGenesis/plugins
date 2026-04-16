#!/usr/bin/env bash
# validate-skills.sh — Validate all SKILL.md files in the plugins directory.
# First-party skills (non-community): require name, model, description, category.
# Community skills: require name and description only.
# Exit 0 if all skills pass, exit 1 if any fail.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"
COMMUNITY_DIR="$PLUGINS_DIR/community-skills"

fp_pass=0
fp_fail=0
cm_pass=0
cm_fail=0
errors=()

while IFS= read -r skill_file; do
  skill_rel="${skill_file#$REPO_ROOT/}"
  missing=()

  # Extract frontmatter block between first pair of ---
  frontmatter=$(awk '/^---/{f++; if(f==2) exit} f==1{print}' "$skill_file")

  is_community=false
  if [[ "$skill_file" == "$COMMUNITY_DIR"* ]]; then
    is_community=true
  fi

  if $is_community; then
    required_fields=(name description)
  else
    required_fields=(name model description category)
  fi

  for field in "${required_fields[@]}"; do
    if ! echo "$frontmatter" | grep -qE "^${field}[[:space:]]*:"; then
      missing+=("$field")
    fi
  done

  if [ ${#missing[@]} -eq 0 ]; then
    if $is_community; then cm_pass=$(( cm_pass + 1 )); else fp_pass=$(( fp_pass + 1 )); fi
  else
    if $is_community; then cm_fail=$(( cm_fail + 1 )); else fp_fail=$(( fp_fail + 1 )); fi
    errors+=("FAIL: $skill_rel — missing: ${missing[*]}")
  fi
done < <(find "$PLUGINS_DIR" -name "SKILL.md" | sort)

total_fp=$(( fp_pass + fp_fail ))
total_cm=$(( cm_pass + cm_fail ))

echo "=== Skill Validation ==="
echo "First-party : $fp_pass/$total_fp passed"
echo "Community   : $cm_pass/$total_cm passed"
echo ""

if [ ${#errors[@]} -gt 0 ]; then
  echo "Errors:"
  for e in "${errors[@]}"; do
    echo "  $e"
  done
  echo ""
  total_fail=$(( fp_fail + cm_fail ))
  echo "RESULT: $total_fail skill(s) failed validation"
  exit 1
else
  total_pass=$(( fp_pass + cm_pass ))
  echo "RESULT: All $total_pass skills passed"
  exit 0
fi
