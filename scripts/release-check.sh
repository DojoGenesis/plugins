#!/usr/bin/env bash
# release-check.sh: run every release gate for the Dojo suite and print one table.
#
# Usage: release-check.sh [--only STEP[,STEP]] [--plugin NAME]... [--no-mods] [--repo PATH] [-h]
#
# Steps (stable ids; per-plugin steps are written step:plugin and --only takes either form):
#   lint        suite_lint.py over the suite plugins
#   denylist    suite_denylist.py over the public files (never with --allow-missing)
#   unittest    each plugin's tests (python3.9; a run of 0 tests is a failure; a run with
#               skipped tests is a WARN that shows the skip count, and one where more
#               than 25% of the tests skipped is a FAIL)
#   validate    claude plugin validate --strict per plugin (output that is not JSON is
#               never a pass: ERROR when claude exited 0, FAIL when it exited non-zero)
#   mod         claude plugin test, only for plugins with hooks/register.ts
#   self-test   this tooling's own tests, under python3.9
#   face-parity scripts/face-parity.py
#   plugin-lint scripts/plugin-lint.py (exit 1 means warnings only and is shown as WARN-OK)
#
# Row status: PASS, WARN (the check passed but part of it did not run, such as skipped
# tests), WARN-OK (known baseline warnings), FAIL (a check ran and failed), ERROR (a
# check could not run), SKIP (not applicable). Exit 0 only when no row is FAIL or ERROR.
#
# The default plugin set is the eight suite plugins plus dojo-suite, a dependency-only
# plugin: it has no tests and no mod, so those rows are SKIP; it still gets validate.
#
# Environment: CLAUDE_BIN (default: a 2.1.286 install under the user's Claude app
# support folder, else `claude` on PATH; must be 2.1.286 or newer for validate and
# mod rows), DOJO_DENYLIST and DOJO_INTERNAL_REFS (the two local lists the denylist step
# reads), DOJO_PY39 (default /usr/bin/python3). Workflow tests need node on PATH; a
# cleared PATH skips them, which shows up as a WARN or FAIL on the unittest row.
#
# It never runs `claude plugin eval`, never touches git, and never deploys.
# Written for bash 3.2 (macOS /bin/bash): no associative arrays, mapfile or ${x,,}.
# Exit codes are captured into variables; no check is ever piped into another command.

set -u

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 2
REPO=$(cd "$SCRIPT_DIR/.." && pwd) || exit 2
SUITE_NAMES="dojo-protocol dojo-gates dojo-router dojo-meter dojo-verify dojo-flow dojo-doctor dojo-settle"
META_PLUGIN="dojo-suite"

ONLY=""
NO_MODS=0
NPLUG=0
PLUGINS=()
PLUGIN_RE='^dojo-[a-z0-9-]+$'

add_plugin() {
  if ! [[ "$1" =~ $PLUGIN_RE ]]; then
    echo "release-check: bad plugin name: must look like dojo-name" >&2
    exit 2
  fi
  PLUGINS[NPLUG]="$1"
  NPLUG=$((NPLUG + 1))
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --only) shift; [ $# -gt 0 ] || { echo "release-check: --only needs a value" >&2; exit 2; }; ONLY="$1" ;;
    --only=*) ONLY="${1#--only=}" ;;
    --plugin) shift; [ $# -gt 0 ] || { echo "release-check: --plugin needs a value" >&2; exit 2; }; add_plugin "$1" ;;
    --plugin=*) add_plugin "${1#--plugin=}" ;;
    --no-mods) NO_MODS=1 ;;
    --repo) shift; [ $# -gt 0 ] || { echo "release-check: --repo needs a value" >&2; exit 2; }
            REPO=$(cd "$1" 2>/dev/null && pwd) || { echo "release-check: no such repo directory" >&2; exit 2; } ;;
    --repo=*) REPO=$(cd "${1#--repo=}" 2>/dev/null && pwd) || { echo "release-check: no such repo directory" >&2; exit 2; } ;;
    *) echo "release-check: unknown argument (try -h)" >&2; exit 2 ;;
  esac
  shift
done

EXPLICIT=$NPLUG
if [ "$NPLUG" -eq 0 ]; then
  for n in $SUITE_NAMES $META_PLUGIN; do add_plugin "$n"; done
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/release-check.XXXXXX") || exit 2
trap 'rm -rf "$TMP"' EXIT

ROW_NAME=()
ROW_STATUS=()
ROW_DETAIL=()
NROWS=0

add_row() {
  ROW_NAME[NROWS]="$1"
  ROW_STATUS[NROWS]="$2"
  ROW_DETAIL[NROWS]="$3"
  NROWS=$((NROWS + 1))
}

want() {
  [ -z "$ONLY" ] && return 0
  local base="${1%%:*}" item
  local IFS=,
  for item in $ONLY; do
    if [ "$item" = "$1" ] || [ "$item" = "$base" ]; then return 0; fi
  done
  return 1
}

tail_of() {
  local x
  x=$(grep -Ev '^[[:space:]=-]*$' "$1" 2>/dev/null | tail -n 1)
  printf '%s' "${x:0:110}"
}

# run_in DIR LOG cmd args...   (sets RC; stdout and stderr both go to LOG; no pipes)
run_in() {
  local dir="$1" log="$2"
  shift 2
  ( cd "$dir" && "$@" ) >"$log" 2>&1
  RC=$?
}

# parse_ran LOG: sets RAN (number or empty) and SKIPPED
parse_ran() {
  RAN=""
  SKIPPED=0
  local line re1='^Ran ([0-9]+) test' re2='skipped=([0-9]+)'
  line=$(grep -E '^Ran [0-9]+ test' "$1" 2>/dev/null | tail -n 1)
  if [[ "$line" =~ $re1 ]]; then RAN="${BASH_REMATCH[1]}"; fi
  line=$(grep -E 'skipped=[0-9]+' "$1" 2>/dev/null | tail -n 1)
  if [[ "$line" =~ $re2 ]]; then SKIPPED="${BASH_REMATCH[1]}"; fi
}

# unittest_row ROW LOG: classify a finished unittest run (RC, RAN, SKIPPED already set).
# A skipped test is not evidence, so a run with skips is never a plain PASS.
unittest_row() {
  local row="$1" log="$2"
  if [ "$RC" -ne 0 ]; then
    add_row "$row" FAIL "exit $RC: $(tail_of "$log")"
  elif [ -z "$RAN" ] || [ "$RAN" -eq 0 ]; then
    add_row "$row" FAIL "ran 0 tests (an empty run is not a pass)"
  elif [ "$SKIPPED" -gt 0 ] && [ $((SKIPPED * 4)) -gt "$RAN" ]; then
    add_row "$row" FAIL "$RAN tests, $SKIPPED skipped (over 25% skipped)"
  elif [ "$SKIPPED" -gt 0 ]; then
    add_row "$row" WARN "$RAN tests, $SKIPPED skipped"
  else
    add_row "$row" PASS "$RAN tests, 0 skipped"
  fi
}

# ---------------------------------------------------------------- preflight

PY39="${DOJO_PY39:-/usr/bin/python3}"
PY39_OK=1
if [ ! -x "$PY39" ]; then PY39_OK=0; fi
PYCI=$(command -v python3 2>/dev/null || true)
PYCI_OK=1
if [ -z "$PYCI" ]; then PYCI_OK=0; fi

CLAUDE_BIN="${CLAUDE_BIN:-}"
if [ -z "$CLAUDE_BIN" ]; then
  for c in "${HOME:-}/Library/Application Support/Claude/claude-code/2.1.286/"*"/claude.app/Contents/MacOS/claude"; do
    if [ -x "$c" ]; then CLAUDE_BIN="$c"; break; fi
  done
fi
if [ -z "$CLAUDE_BIN" ]; then
  CLAUDE_BIN=$(command -v claude 2>/dev/null || true)
fi

CLAUDE_REASON=""
CLAUDE_VERSION=""
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
  CLAUDE_REASON="claude binary not found (set CLAUDE_BIN)"
else
  vout=$("$CLAUDE_BIN" --version 2>&1)
  vre='([0-9]+)\.([0-9]+)\.([0-9]+)'
  if [[ "$vout" =~ $vre ]]; then
    CLAUDE_VERSION="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
    vnum=$(( BASH_REMATCH[1] * 1000000 + BASH_REMATCH[2] * 1000 + BASH_REMATCH[3] ))
    if [ "$vnum" -lt 2001286 ]; then
      CLAUDE_REASON="claude $CLAUDE_VERSION is older than 2.1.286"
    fi
  else
    CLAUDE_REASON="could not read the claude version"
  fi
fi

# ------------------------------------------------------------------- steps

step_lint() {
  want lint || return 0
  if [ "$PY39_OK" != 1 ]; then add_row lint ERROR "python 3.9 interpreter not found (set DOJO_PY39)"; return 0; fi
  if [ ! -f "$SCRIPT_DIR/suite_lint.py" ]; then add_row lint ERROR "suite_lint.py not found"; return 0; fi
  local args=(--repo "$REPO") i
  if [ "$EXPLICIT" -gt 0 ]; then
    for ((i = 0; i < NPLUG; i++)); do args[${#args[@]}]="${PLUGINS[$i]}"; done
  fi
  run_in "$REPO" "$TMP/lint.log" env PYTHONDONTWRITEBYTECODE=1 "$PY39" "$SCRIPT_DIR/suite_lint.py" "${args[@]}"
  # a clean exit with no summary line means the tool did not do its job
  if [ "$RC" -le 1 ] && ! grep -q '^suite-lint:' "$TMP/lint.log" 2>/dev/null; then
    add_row lint ERROR "exit $RC but no 'suite-lint:' summary line in the output"
    return 0
  fi
  case "$RC" in
    0) add_row lint PASS "$(tail_of "$TMP/lint.log")" ;;
    1) add_row lint FAIL "$(tail_of "$TMP/lint.log")" ;;
    *) add_row lint ERROR "exit $RC: $(tail_of "$TMP/lint.log")" ;;
  esac
}

step_denylist() {
  want denylist || return 0
  if [ "$PY39_OK" != 1 ]; then add_row denylist ERROR "python 3.9 interpreter not found (set DOJO_PY39)"; return 0; fi
  if [ ! -f "$SCRIPT_DIR/suite_denylist.py" ]; then add_row denylist ERROR "suite_denylist.py not found"; return 0; fi
  local paths=() missing="" p d
  for p in README.md llms.txt .claude-plugin/marketplace.json; do
    if [ -e "$REPO/$p" ]; then paths[${#paths[@]}]="$p"; else missing="$missing $p"; fi
  done
  local found=0
  for d in "$REPO"/plugins/dojo-*; do
    if [ -d "$d" ]; then paths[${#paths[@]}]="plugins/$(basename "$d")"; found=1; fi
  done
  if [ "$found" = 0 ]; then missing="$missing plugins/dojo-*"; fi
  for p in scripts/suite_lint.py scripts/suite_denylist.py scripts/release-check.sh scripts/README-release.md scripts/tests_suite CHANGELOG.md STATUS.md; do
    if [ -e "$REPO/$p" ]; then paths[${#paths[@]}]="$p"; fi
  done
  if [ -n "$missing" ]; then
    add_row denylist ERROR "path missing from disk:$missing"
    return 0
  fi
  run_in "$REPO" "$TMP/denylist.log" env PYTHONDONTWRITEBYTECODE=1 "$PY39" "$SCRIPT_DIR/suite_denylist.py" "${paths[@]}"
  # a clean exit without the control line means the scanner never proved it can see a hit
  if [ "$RC" -le 1 ] && ! grep -q 'control ok' "$TMP/denylist.log" 2>/dev/null; then
    add_row denylist ERROR "exit $RC but no 'control ok' line in the output"
    return 0
  fi
  case "$RC" in
    0) add_row denylist PASS "$(tail_of "$TMP/denylist.log")" ;;
    1) add_row denylist FAIL "$(tail_of "$TMP/denylist.log")" ;;
    *) add_row denylist ERROR "exit $RC: $(tail_of "$TMP/denylist.log")" ;;
  esac
}

step_unittest() {
  local p="$1" dir="$REPO/plugins/$1"
  want "unittest:$p" || return 0
  if [ "$p" = "$META_PLUGIN" ] && [ ! -d "$dir/tests" ]; then add_row "unittest:$p" SKIP "dependency-only plugin, no tests"; return 0; fi
  if [ "$PY39_OK" != 1 ]; then add_row "unittest:$p" ERROR "python 3.9 interpreter not found (set DOJO_PY39)"; return 0; fi
  if [ ! -d "$dir/tests" ]; then add_row "unittest:$p" FAIL "no tests/ directory"; return 0; fi
  local log="$TMP/unittest-$p.log"
  run_in "$dir" "$log" env PYTHONDONTWRITEBYTECODE=1 "$PY39" -m unittest discover -s tests
  parse_ran "$log"
  unittest_row "unittest:$p" "$log"
}

step_validate() {
  local p="$1" dir="$REPO/plugins/$1"
  want "validate:$p" || return 0
  if [ -n "$CLAUDE_REASON" ]; then add_row "validate:$p" ERROR "$CLAUDE_REASON"; return 0; fi
  local log="$TMP/validate-$p.json"
  ( cd "$REPO" && "$CLAUDE_BIN" plugin validate --strict --json "$dir" ) >"$log" 2>"$TMP/validate-$p.err"
  RC=$?
  # summary is "<success> <errors> <warnings>", or "unparsed" when the output is not the
  # JSON document the check expects; an unreadable result is never a pass
  local summary="unparsed" reason="output was not JSON"
  if [ "$PY39_OK" = 1 ]; then
    summary=$("$PY39" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("unparsed")
    sys.exit(0)
if not isinstance(d, dict) or not isinstance(d.get("success"), bool):
    print("unparsed")
    sys.exit(0)
m = d.get("manifest") or {}
def n(x):
    return len(x) if isinstance(x, (list, tuple)) else (x if isinstance(x, int) else 0)
print("%s %d %d" % (d.get("success"), n(m.get("errors")), n(m.get("warnings"))))
' "$log" 2>/dev/null)
    [ -n "$summary" ] || summary="unparsed"
  else
    reason="python 3.9 not found, so the output could not be read"
  fi
  local ok="" e="" w="" detail
  if [ "$summary" = "unparsed" ]; then
    detail="exit $RC, $reason: $(tail_of "$TMP/validate-$p.err")"
    if [ "$RC" -ne 0 ]; then
      add_row "validate:$p" FAIL "$detail"
    else
      add_row "validate:$p" ERROR "$detail"
    fi
    return 0
  fi
  read -r ok e w <<<"$summary"
  detail="$e errors, $w warnings"
  if [ "$RC" -ne 0 ]; then
    add_row "validate:$p" FAIL "exit $RC; $detail"
  elif [ "$ok" != "True" ] || [ "$e" -ne 0 ]; then
    add_row "validate:$p" FAIL "$detail"
  else
    add_row "validate:$p" PASS "$detail"
  fi
}

step_mod() {
  local p="$1" dir="$REPO/plugins/$1"
  want "mod:$p" || return 0
  if [ "$NO_MODS" = 1 ]; then add_row "mod:$p" SKIP "--no-mods"; return 0; fi
  if [ ! -f "$dir/hooks/register.ts" ]; then add_row "mod:$p" SKIP "no hooks/register.ts"; return 0; fi
  if [ -n "$CLAUDE_REASON" ]; then add_row "mod:$p" ERROR "$CLAUDE_REASON"; return 0; fi
  local log="$TMP/mod-$p.log"
  ( cd "$REPO" && env CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 "$CLAUDE_BIN" plugin test "$dir" ) >"$log" 2>&1
  RC=$?
  if grep -q 'hooks modules are turned off' "$log" 2>/dev/null; then
    add_row "mod:$p" ERROR "function hooks are off in this process"
    return 0
  fi
  parse_ran "$log"
  if [ "$RC" -ne 0 ]; then
    add_row "mod:$p" FAIL "exit $RC: $(tail_of "$log")"
  elif [ -z "$RAN" ] || [ "$RAN" -eq 0 ]; then
    add_row "mod:$p" FAIL "no tests ran (an empty run is not a pass)"
  elif ! grep -Eq '^[[:space:]]*0 fail' "$log" 2>/dev/null; then
    add_row "mod:$p" FAIL "output has no '0 fail' line"
  else
    add_row "mod:$p" PASS "$RAN tests"
  fi
}

step_self_test() {
  want self-test || return 0
  if [ "$PY39_OK" != 1 ]; then add_row self-test ERROR "python 3.9 interpreter not found (set DOJO_PY39)"; return 0; fi
  if [ ! -d "$SCRIPT_DIR/tests_suite" ]; then add_row self-test FAIL "scripts/tests_suite not found"; return 0; fi
  local log="$TMP/self-test.log"
  run_in "$SCRIPT_DIR" "$log" env PYTHONDONTWRITEBYTECODE=1 "$PY39" -m unittest discover -s tests_suite -t .
  parse_ran "$log"
  unittest_row self-test "$log"
}

step_legacy() {
  local id="$1" file="$2"
  want "$id" || return 0
  if [ "$PYCI_OK" != 1 ]; then add_row "$id" ERROR "python3 not on PATH"; return 0; fi
  if [ ! -f "$REPO/$file" ]; then add_row "$id" ERROR "$file not found"; return 0; fi
  local log="$TMP/$id.log"
  run_in "$REPO" "$log" env PYTHONDONTWRITEBYTECODE=1 "$PYCI" "$file"
  case "$id:$RC" in
    *:0) add_row "$id" PASS "$(tail_of "$log")" ;;
    plugin-lint:1) add_row "$id" WARN-OK "warnings only (known quarantine baseline): $(tail_of "$log")" ;;
    plugin-lint:2) add_row "$id" FAIL "$(tail_of "$log")" ;;
    face-parity:1) add_row "$id" FAIL "$(tail_of "$log")" ;;
    *) add_row "$id" ERROR "exit $RC: $(tail_of "$log")" ;;
  esac
}

# --------------------------------------------------------------------- run

step_lint
step_denylist
for ((i = 0; i < NPLUG; i++)); do
  p="${PLUGINS[$i]}"
  if [ ! -d "$REPO/plugins/$p" ]; then
    if want "unittest:$p" || want "validate:$p" || want "mod:$p"; then
      add_row "plugin:$p" ERROR "directory not found under plugins/"
    fi
    continue
  fi
  step_unittest "$p"
  step_validate "$p"
  step_mod "$p"
done
step_self_test
step_legacy face-parity scripts/face-parity.py
step_legacy plugin-lint scripts/plugin-lint.py

# ------------------------------------------------------------------ report

width=4
for ((i = 0; i < NROWS; i++)); do
  l=${#ROW_NAME[$i]}
  if [ "$l" -gt "$width" ]; then width=$l; fi
done

if [ -n "$CLAUDE_VERSION" ]; then echo "claude: $CLAUDE_VERSION"; fi
printf '%-*s  %-7s  %s\n' "$width" STEP STATUS DETAIL
fails=0; errors=0; warnok=0; warns=0
for ((i = 0; i < NROWS; i++)); do
  printf '%-*s  %-7s  %s\n' "$width" "${ROW_NAME[$i]}" "${ROW_STATUS[$i]}" "${ROW_DETAIL[$i]}"
  case "${ROW_STATUS[$i]}" in
    FAIL) fails=$((fails + 1)) ;;
    ERROR) errors=$((errors + 1)) ;;
    WARN-OK) warnok=$((warnok + 1)) ;;
    WARN) warns=$((warns + 1)) ;;
  esac
done

if [ "$NROWS" -eq 0 ]; then
  echo "OVERALL: FAIL (no steps ran; check --only)"
  exit 1
fi
if [ "$fails" -eq 0 ] && [ "$errors" -eq 0 ]; then
  echo "OVERALL: PASS ($fails fail, $errors error, $warnok warn-ok, $warns warn)"
  exit 0
fi
echo "OVERALL: FAIL ($fails fail, $errors error, $warnok warn-ok, $warns warn)"
exit 1
