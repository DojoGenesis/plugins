#!/usr/bin/env python3
"""hook_accuracy.py: measure how often the Dojo hooks are right, against fixtures with known answers.

Usage:
  hook_accuracy.py [--fixtures DIR] [--hooks-from DIR] [--only HOOK[,HOOK]] [--json] [--failures]

A fixture says what one hook should do with one input: fire, or stay silent. The fixtures live beside the plugin
they test, in plugins/<plugin>/fixtures/accuracy/*.json. The runner feeds each input to the real hook script the
way Claude Code does (a JSON payload on stdin, a fresh state directory per fixture, every kill switch cleared) and
records what the hook did. Nothing is mocked and nothing leaves the machine.

It prints one row per hook: the confusion counts, precision and recall with 95% Wilson intervals, and how many
borderline fixtures it saw. A borderline fixture is one whose right answer is arguable: it is run and reported,
but kept out of precision and recall.

  --fixtures DIR    repository root whose plugins/*/fixtures/accuracy/ are read (default: this repository)
  --hooks-from DIR  repository root whose hook scripts are run (default: the same as --fixtures). Point it at an
                    older checkout to measure the hooks before a change against the same fixtures.
  --only HOOKS      comma-separated hook ids (dojo-verify/stop, dojo-gates/config-first:path, ...) or prefixes
  --json            print the results as JSON instead of the table
  --failures        list every fixture whose verdict disagreed with its expectation

Fixture inputs, by hook:
  dojo-verify/stop          "turn": steps of the turn the Stop hook judges, after optional "history" steps.
                            A step is {"user": text}, {"say": text}, {"bash": cmd, "out": text, "error": bool,
                            "bg": bool}, {"edit": path}, {"write": path} or {"tool": name, "input": {...},
                            "out": text, "error": bool}. The last "say" is the final message.
  dojo-gates/config-first   "event" (PostToolUse or PostToolUseFailure), "command", "stdout", "stderr", "error";
                            "expect_kinds" lists the kinds that should fire (auth, conn, cmd, path), [] for none.
                            Each kind is scored as its own hook: dojo-gates/config-first:<kind>.
  dojo-gates/empty-probe    the same input as config-first; "expect" is fire or silent.
  dojo-gates/<guard>        a PreToolUse guard (staging, pushed-rewrite, secret-print, token-url, mac-timeout,
                            masked-exit, big-read): "command" (or "file_path" for big-read), optional "setup":
                            {"git": "pushed" | "unpushed"} builds a scratch repository to run in, and
                            {"file_kb": N} writes an N KB file for "file_path" to point at.
  Optional on every fixture: "borderline" (bool), "known_miss" (bool), "requires" ("darwin-no-timeout"), "class",
  "source", "note". A known miss is an error the hooks still make on purpose-written evidence: it counts in the table
  like any other result, but it does not fail the run, so the suite stays a gate for new disagreements.

Exit codes: 0 every fixture that is neither borderline nor a known miss got its expected verdict, 1 at least one did
not, 2 could not run.
Stdlib only; runs under Python 3.9.
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
KINDS = ("auth", "conn", "cmd", "path")
KIND_TEXT = {
    "an authorization failure": "auth",
    "a refused connection": "conn",
    "a missing command": "cmd",
    "a missing path": "path",
}
PRE_GUARDS = ("staging", "pushed-rewrite", "secret-print", "token-url", "mac-timeout", "masked-exit", "big-read")
HOOK_TIMEOUT = 20
SCRUB_ENV = ("DOJO_OFF", "DOJO_GATES_OFF", "DOJO_GATES_SKIP", "DOJO_VERIFY_OFF", "CLAUDE_PLUGIN_OPTION_MODE",
             "CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT")


class FixtureError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ loading


def load_fixtures(root):
    """[(file, fixture)] from plugins/*/fixtures/accuracy/*.json, sorted by hook then id."""
    out = []
    pattern = os.path.join(root, "plugins", "*", "fixtures", "accuracy", "*.json")
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        hook = data.get("hook")
        cases = data.get("cases")
        if not isinstance(hook, str) or not isinstance(cases, list):
            raise FixtureError("%s: needs a \"hook\" string and a \"cases\" list" % path)
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                raise FixtureError("%s: every case needs an \"id\"" % path)
            case = dict(case)
            case.setdefault("hook", hook)
            out.append((path, case))
    seen = set()
    for path, case in out:
        key = (case["hook"], case["id"])
        if key in seen:
            raise FixtureError("%s: duplicate fixture id %s for %s" % (path, case["id"], case["hook"]))
        seen.add(key)
    out.sort(key=lambda pc: (pc[1]["hook"], pc[1]["id"]))
    return out


# ------------------------------------------------------------------------------------------------ running


def _env(state_dir, extra=None):
    env = dict(os.environ)
    for k in SCRUB_ENV:
        env.pop(k, None)
    env["CLAUDE_PLUGIN_DATA"] = state_dir
    if extra:
        env.update(extra)
    return env


def _run(script, payload, env):
    if not os.path.isfile(script):
        raise FixtureError("hook script not found: %s" % script)
    proc = subprocess.run(
        [sys.executable, script],
        input=json.dumps(payload).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=HOOK_TIMEOUT,
    )
    text = proc.stdout.decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except ValueError:
        raise FixtureError("hook printed something that is not JSON: %r" % text[:200])
    return obj if isinstance(obj, dict) else {}


class _Transcript(object):
    """Claude Code transcript entries built from fixture steps."""

    def __init__(self):
        self.entries = []
        self.n = 0
        self.final = ""

    def _uuid(self):
        self.n += 1
        return "00000000-0000-4000-8000-%012d" % self.n

    def _add(self, entry):
        entry.setdefault("uuid", self._uuid())
        entry.setdefault("isSidechain", False)
        self.entries.append(entry)

    def step(self, s):
        if "user" in s:
            self._add({"type": "user", "message": {"role": "user", "content": s["user"]}})
        elif "say" in s:
            self._add({"type": "assistant", "message": {"role": "assistant",
                                                         "content": [{"type": "text", "text": s["say"]}]}})
            self.final = s["say"]
        elif "bash" in s:
            inp = {"command": s["bash"]}
            if s.get("bg"):
                inp["run_in_background"] = True
            self._tool("Bash", inp, s.get("out", ""), bool(s.get("error")))
        elif "edit" in s:
            self._tool("Edit", {"file_path": s["edit"], "old_string": "a", "new_string": "b"},
                       s.get("out", "The file %s has been updated." % s["edit"]), bool(s.get("error")))
        elif "write" in s:
            self._tool("Write", {"file_path": s["write"], "content": "x"},
                       s.get("out", "File created successfully at: %s" % s["write"]), bool(s.get("error")))
        elif "tool" in s:
            self._tool(s["tool"], s.get("input") or {}, s.get("out", ""), bool(s.get("error")))
        else:
            raise FixtureError("unknown step: %r" % (s,))

    def _tool(self, name, inp, out, error):
        tid = "toolu_fixture_%04d" % (self.n + 1)
        self._add({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        if error and name == "Bash" and not str(out).startswith("Exit code"):
            out = "Exit code 1\n" + str(out)
        self._add({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": out, "is_error": error}]},
            "toolUseResult": {"stdout": out if name == "Bash" else "", "stderr": "", "interrupted": False}})


def run_verify(case, hooks_root, tmp):
    t = _Transcript()
    for s in case.get("history", []):
        t.step(s)
    turn = case.get("turn")
    if not isinstance(turn, list) or not turn:
        raise FixtureError("%s: a dojo-verify/stop fixture needs \"turn\" steps" % case["id"])
    for s in turn:
        t.step(s)
    path = os.path.join(tmp, "transcript.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for e in t.entries:
            fh.write(json.dumps(e) + "\n")
    payload = {
        "hook_event_name": "Stop",
        "session_id": "fixture-" + re.sub(r"[^A-Za-z0-9_-]", "-", case["id"]),
        "transcript_path": path,
        "cwd": case.get("cwd", "/work/project"),
        "stop_hook_active": False,
        "last_assistant_message": t.final,
    }
    out = _run(os.path.join(hooks_root, "plugins", "dojo-verify", "hooks", "stop_evidence.py"), payload,
               _env(os.path.join(tmp, "state"), {"CLAUDE_PLUGIN_OPTION_MODE": "block"}))
    return {"dojo-verify/stop": out.get("decision") == "block"}


def _post_payload(case):
    event = case.get("event", "PostToolUse")
    payload = {
        "hook_event_name": event,
        "session_id": "fixture-" + re.sub(r"[^A-Za-z0-9_-]", "-", case["id"]),
        "cwd": case.get("cwd", "/work/project"),
        "tool_name": "Bash",
        "tool_input": {"command": case.get("command", "")},
    }
    if event == "PostToolUseFailure":
        payload["error"] = case.get("error", "Exit code 1")
    else:
        payload["tool_response"] = {"stdout": case.get("stdout", ""), "stderr": case.get("stderr", ""),
                                    "interrupted": False, "isImage": False}
    return payload


def run_post(case, hooks_root, tmp):
    out = _run(os.path.join(hooks_root, "plugins", "dojo-gates", "hooks", "bash_after.py"), _post_payload(case),
               _env(os.path.join(tmp, "state")))
    ctx = ((out.get("hookSpecificOutput") or {}).get("additionalContext")) or ""
    fired = {"dojo-gates/empty-probe": "dojo-gates: empty-probe" in ctx}
    kinds = set(KIND_TEXT[m] for m in re.findall(r"config-first \S+ that output looks like ([a-z ]+?), which", ctx)
                if m in KIND_TEXT)
    for k in KINDS:
        fired["dojo-gates/config-first:" + k] = k in kinds
    return fired


def _git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                   env=dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                            GIT_AUTHOR_NAME="f", GIT_AUTHOR_EMAIL="f@example.com",
                            GIT_COMMITTER_NAME="f", GIT_COMMITTER_EMAIL="f@example.com"))


def _setup(case, tmp):
    """(cwd, file_path) after building what the fixture's "setup" asks for."""
    setup = case.get("setup") or {}
    cwd = case.get("cwd", "/work/project")
    file_path = case.get("file_path")
    if setup.get("git"):
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        _git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("a\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-q", "-m", "one")
        if setup["git"] == "pushed":
            _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
            _git(repo, "config", "branch.main.remote", "origin")
            _git(repo, "config", "branch.main.merge", "refs/heads/main")
        cwd = repo
    if setup.get("file_kb") is not None:
        name = os.path.basename(file_path or "big.log")
        file_path = os.path.join(tmp, name)
        with open(file_path, "w") as fh:
            fh.write(("x" * 1023 + "\n") * int(setup["file_kb"]))
    return cwd, file_path


def run_pre(case, hooks_root, tmp):
    guard = case["hook"].split("/", 1)[1]
    cwd, file_path = _setup(case, tmp)
    sid = "fixture-" + re.sub(r"[^A-Za-z0-9_-]", "-", case["id"])
    if guard == "big-read":
        payload = {"hook_event_name": "PreToolUse", "session_id": sid, "cwd": cwd, "tool_name": "Read",
                   "tool_input": dict({"file_path": file_path}, **(case.get("read_args") or {}))}
        script = "read_guard.py"
    else:
        payload = {"hook_event_name": "PreToolUse", "session_id": sid, "cwd": cwd, "tool_name": "Bash",
                   "tool_input": {"command": case.get("command", "")}}
        script = "bash_guard.py"
    out = _run(os.path.join(hooks_root, "plugins", "dojo-gates", "hooks", script), payload,
               _env(os.path.join(tmp, "state")))
    hso = out.get("hookSpecificOutput") or {}
    text = (hso.get("permissionDecisionReason") or "") + "\n" + (hso.get("additionalContext") or "")
    ids = set(re.findall(r"dojo-gates: ([a-z-]+) —", text))
    return {"dojo-gates/" + g: g in ids for g in PRE_GUARDS}


def requirement_met(case):
    req = case.get("requires")
    if not req:
        return True
    if req == "darwin-no-timeout":
        return sys.platform == "darwin" and not shutil.which("timeout") and not shutil.which("gtimeout")
    return False


def expectations(case):
    """{hook id: True (should fire) / False (should stay silent)} for the hooks this fixture scores."""
    hook = case["hook"]
    if hook == "dojo-gates/config-first":
        want = case.get("expect_kinds")
        if not isinstance(want, list) or any(k not in KINDS for k in want):
            raise FixtureError("%s: expect_kinds must list kinds from %s" % (case["id"], ", ".join(KINDS)))
        return dict(("dojo-gates/config-first:" + k, k in want) for k in KINDS)
    exp = case.get("expect")
    if exp not in ("fire", "silent"):
        raise FixtureError("%s: expect must be \"fire\" or \"silent\"" % case["id"])
    return {hook: exp == "fire"}


def run_case(case, hooks_root):
    tmp = tempfile.mkdtemp(prefix="dojo-accuracy-")
    try:
        hook = case["hook"]
        if hook == "dojo-verify/stop":
            return run_verify(case, hooks_root, tmp)
        if hook in ("dojo-gates/config-first", "dojo-gates/empty-probe"):
            return run_post(case, hooks_root, tmp)
        if hook.startswith("dojo-gates/") and hook.split("/", 1)[1] in PRE_GUARDS:
            return run_pre(case, hooks_root, tmp)
        raise FixtureError("%s: unknown hook %s" % (case["id"], hook))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ scoring


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials, or None when n is 0."""
    if n == 0:
        return None
    p = float(k) / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2.0 * n)) / d
    h = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def evaluate(fixtures, hooks_root, only=None):
    """{"rows": [...], "results": [...]}: per-hook confusion counts and every fixture's outcome."""
    results = []
    for path, case in fixtures:
        exp = expectations(case)
        if only:
            exp = dict((h, v) for h, v in exp.items() if any(h == o or h.startswith(o) for o in only))
            if not exp:
                continue
        rec = {"id": case["id"], "file": os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(path)))))), "borderline": bool(case.get("borderline")),
            "class": case.get("class", ""), "known_miss": bool(case.get("known_miss")), "outcomes": {}}
        if not requirement_met(case):
            rec["skipped"] = case.get("requires")
            results.append(rec)
            continue
        fired = run_case(case, hooks_root)
        for h, want in sorted(exp.items()):
            rec["outcomes"][h] = {"expected": "fire" if want else "silent",
                                  "got": "fire" if fired.get(h) else "silent"}
        results.append(rec)
    rows = {}
    for rec in results:
        for h, o in rec["outcomes"].items():
            r = rows.setdefault(h, {"hook": h, "tp": 0, "fp": 0, "fn": 0, "tn": 0, "borderline": 0,
                                    "borderline_fired": 0, "fixtures": 0})
            r["fixtures"] += 1
            if rec["borderline"]:
                r["borderline"] += 1
                r["borderline_fired"] += o["got"] == "fire"
                continue
            key = ("tp" if o["got"] == "fire" else "fn") if o["expected"] == "fire" else \
                ("fp" if o["got"] == "fire" else "tn")
            r[key] += 1
    out_rows = []
    for h in sorted(rows):
        r = rows[h]
        r["precision"] = (float(r["tp"]) / (r["tp"] + r["fp"])) if (r["tp"] + r["fp"]) else None
        r["recall"] = (float(r["tp"]) / (r["tp"] + r["fn"])) if (r["tp"] + r["fn"]) else None
        r["precision_ci"] = wilson(r["tp"], r["tp"] + r["fp"])
        r["recall_ci"] = wilson(r["tp"], r["tp"] + r["fn"])
        out_rows.append(r)
    return {"rows": out_rows, "results": results}


def _pct(x, ci):
    if x is None:
        return "n/a"
    s = "%.0f%%" % (100 * x)
    if ci:
        s += " (%.0f-%.0f)" % (100 * ci[0], 100 * ci[1])
    return s


def table(report):
    lines = ["| hook | fixtures | TP | FP | FN | TN | precision (95% CI) | recall (95% CI) | borderline (fired) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lines.append("| %s | %d | %d | %d | %d | %d | %s | %s | %d (%d) |" % (
            r["hook"], r["fixtures"], r["tp"], r["fp"], r["fn"], r["tn"], _pct(r["precision"], r["precision_ci"]),
            _pct(r["recall"], r["recall_ci"]), r["borderline"], r["borderline_fired"]))
    return "\n".join(lines)


def failures(report, known=False):
    """Fixtures whose verdict disagreed with their expectation: new ones, or (known=True) the documented misses."""
    out = []
    for rec in report["results"]:
        if rec.get("skipped") or rec["borderline"] or rec.get("known_miss", False) is not known:
            continue
        for h, o in sorted(rec["outcomes"].items()):
            if o["expected"] != o["got"]:
                out.append("%s  %s  expected %s, got %s  (%s)" % (h, rec["id"], o["expected"], o["got"], rec["file"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--fixtures", default=DEFAULT_ROOT)
    ap.add_argument("--hooks-from", default=None)
    ap.add_argument("--only", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--failures", action="store_true")
    args = ap.parse_args(argv)
    try:
        fixtures = load_fixtures(os.path.abspath(args.fixtures))
        if not fixtures:
            print("hook_accuracy: no fixtures under %s" % args.fixtures, file=sys.stderr)
            return 2
        only = [o.strip() for o in args.only.split(",") if o.strip()]
        report = evaluate(fixtures, os.path.abspath(args.hooks_from or args.fixtures), only)
    except (FixtureError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print("hook_accuracy: could not run: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        print(table(report))
        skipped = sum(1 for r in report["results"] if r.get("skipped"))
        if skipped:
            print("\n%d fixture(s) skipped: their requirement does not hold on this machine." % skipped)
    bad = failures(report)
    if args.failures and not args.json:
        known = failures(report, known=True)
        if known:
            print("\nKnown misses (documented errors, counted above):")
            for line in known:
                print("  " + line)
        if bad:
            print("\nNew disagreements:")
            for line in bad:
                print("  " + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
