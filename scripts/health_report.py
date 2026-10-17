#!/usr/bin/env python3
"""health_report.py: a runtime health report for a Claude Code setup, built only from the open Dojo tools.

Usage:
  health_report.py [PATH ...] [--since DATE] [--until DATE] [--plugins-root DIR] [--out DIR] [--json]
                   [--no-doctor] [--no-accuracy] [--config-dir DIR] [--max-evidence N]

PATH is a transcript file or a folder of them (default: ~/.claude/projects). The report replays what happened in
those sessions through the suite's own detector code (the functions dojo-verify's and dojo-gates' hooks run, and
dojo-router's and dojo-tally's rules), and counts, per Dojo rule, how often each warning sign appeared. Beside each
count it puts that detector's precision and recall from the fixture suite (scripts/hook_accuracy.py), so a reader
knows how much to trust it, and every finding carries its evidence: the file, the line, a short masked excerpt.

Reproducible: the same transcripts and the same plugins tree give byte-identical output. Nothing depends on the
clock; "as of" is the newest entry read. The report lists every input with a sha256 digest of the lines it used.
The setup section comes from dojo-doctor and reflects this machine; --no-doctor leaves it out.

Read-only: it never runs a hook as a process, never writes outside --out, and sends nothing anywhere. Excerpts are
clipped and token-shaped strings are masked, but the report names session files and commands: treat it as private
until you choose to share it.

Exit codes: 0 report written, 2 could not run. Stdlib only; runs under Python 3.9.
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

VERSION = "0.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
EXCERPT = 160
BIG_READ_CHARS = 100000
DOCTOR_SECTIONS = "interpreters,weight,flag,python"

RULES = [
    (1, "Right model, every dispatch"),
    (2, "Scout before you touch"),
    (3, "Keep context small"),
    (4, "Contract before fan-out"),
    (5, "Done means verified"),
    (6, "Count returns, not dispatches"),
    (7, "Debug by disproof"),
    (8, "Config before code"),
    (9, "Silence is not a finding"),
    (10, "Irreversible needs a yes"),
]
NOT_AUTOMATED = {
    4: "Whether shared decisions were written before a fan-out needs a reader; the report counts fan-outs only.",
    7: "Whether a patch followed a stated cause and an on/off experiment needs a reader.",
}
IRREVERSIBLE = re.compile(
    r"\bgit\s+push\b|\bgh\s+pr\s+merge\b|\bgh\s+release\s+create\b|\bwrangler\s+(?:pages\s+)?deploy\b"
    r"|\bvercel\s+(?:--prod|deploy)\b|\bfly\s+deploy\b|\brailway\s+up\b|\bnpm\s+publish\b|\brm\s+-[a-zA-Z]*r[a-zA-Z]*f"
)
SEND_TOOL = re.compile(r"(?:send_message|send_draft|send_email|create_post|publish|deploy)", re.I)
MASKS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[bpaors]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    re.compile(r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY))=\S+"),
    re.compile(r"[A-Za-z0-9+_-]{40,}={0,2}"),
]


class ReportError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ helpers


def mask(text):
    out = text
    for rx in MASKS:
        out = rx.sub(lambda m: (m.group(1) + "=[masked]") if m.groups() and m.group(1) else "[masked]", out)
    return out


def excerpt(text):
    t = re.sub(r"\s+", " ", text or "").strip()
    t = mask(t)
    return t if len(t) <= EXCERPT else t[:EXCERPT - 3] + "..."


def load_module(path, name):
    if not os.path.isfile(path):
        raise ReportError("not found: %s" % path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plugin_version(root, plugin):
    try:
        with open(os.path.join(root, "plugins", plugin, ".claude-plugin", "plugin.json")) as fh:
            return json.load(fh).get("version")
    except (OSError, ValueError):
        return None


def tree_commit(root):
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=10)
        dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", "plugins", "scripts"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.decode().strip()
    if not sha:
        return None
    return sha + ("+local-changes" if dirty.stdout.strip() else "")


def find_transcripts(paths):
    files = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.isfile(p):
            files.append(os.path.abspath(p))
        elif os.path.isdir(p):
            files.extend(os.path.abspath(f) for f in glob.glob(os.path.join(p, "**", "*.jsonl"), recursive=True))
    return sorted(set(files))


def read_entries(path, since, until):
    """[(line number, entry)] whose timestamp falls in [since, until], and the sha256 of exactly those lines."""
    h = hashlib.sha256()
    out = []
    with open(path, "rb") as fh:
        for n, raw in enumerate(fh):
            try:
                e = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            ts = e.get("timestamp") if isinstance(e.get("timestamp"), str) else ""
            if (since or until) and not ts:
                continue  # with a window, only dated entries: a live session keeps appending undated ones
            if ts and ((since and ts[:10] < since) or (until and ts[:10] > until)):
                continue
            h.update(raw)
            out.append((n, e))
    return out, h.hexdigest()


def blocks(entry):
    msg = entry.get("message")
    c = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def result_text(block):
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and isinstance(x.get("text"), str))
    return ""


# ------------------------------------------------------------------------------------------------ detectors


class Detectors(object):
    """The suite's own detector code, imported from a plugins tree."""

    def __init__(self, root):
        hooks = os.path.join(root, "plugins", "dojo-gates", "hooks")
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        self.verify = load_module(os.path.join(root, "plugins", "dojo-verify", "hooks", "stop_evidence.py"),
                                  "dojo_health_stop_evidence")
        self.after = load_module(os.path.join(hooks, "bash_after.py"), "dojo_health_bash_after")
        self.guards = load_module(os.path.join(hooks, "_guards.py"), "_guards")
        self.shell = load_module(os.path.join(hooks, "_shell.py"), "_shell")
        router = os.path.join(root, "plugins", "dojo-router", "hooks")
        if router not in sys.path:
            sys.path.insert(0, router)
        self.router = load_module(os.path.join(router, "agent_model.py"), "dojo_health_agent_model")

    # dojo-gates, PostToolUse: the same inputs bash_after.main builds
    def post(self, cmd, is_error, text, stdout, stderr):
        segs = self.shell.all_segments(cmd)
        if is_error:
            m = re.match(r"\s*Exit code (\d+)\b(.*)$", text or "", re.S)
            rest = m.group(2).strip() if m else (text or "").strip()
            empty_all = bool(m) and m.group(1) == "1" and not rest
            scan = text or ""
        else:
            out = stdout if stdout is not None else re.sub(
                r"^\((?:Bash completed with no output|No output|No content)\)$", "", (text or "").strip())
            err = stderr or ""
            empty_all = not out.strip() and not err.strip()
            scan = out + "\n" + err
        kinds = self.after._config_hits(scan, segs)
        probe = False
        if empty_all:
            is_probe, quiet = self.after._is_probe(segs)
            probe = is_probe and not quiet
        return kinds, probe

    # dojo-gates, PreToolUse guards that judge the command text alone (no live git or PATH state)
    STATIC_GUARDS = ("staging", "secret-print", "token-url", "masked-exit")

    def pre(self, cmd, cwd):
        segs = self.shell.all_segments(cmd)
        ctx = self.guards.Ctx(cmd, segs, {"cwd": cwd})
        hits = []
        for gid, fn in self.guards.GUARDS:
            if gid not in self.STATIC_GUARDS:
                continue
            try:
                res = fn(ctx)
            except Exception:
                res = None
            if res:
                hits.append(gid)
        return hits

    # dojo-router: a dispatch that names no model and whose type doesn't pin one
    def unpinned(self, inp):
        r = self.router
        agent_type = inp.get("subagent_type")
        agent_type = (agent_type.strip() if isinstance(agent_type, str) else "") or "general-purpose"
        if ":" in agent_type or agent_type == "fork" or agent_type in r.PINNED_BUILTINS:
            return False
        model = inp.get("model")
        if isinstance(model, str) and r._is_pin(model):
            return False
        return agent_type in r.UNPINNED_BUILTINS


# ------------------------------------------------------------------------------------------------ the scan


class Session(object):
    def __init__(self, rel, subagent):
        self.rel = rel
        self.subagent = subagent
        self.uses = []          # tool_use blocks in order, in the current view (since the last compaction)
        self.use_line = {}
        self.results = {}
        self.bg_done = {}
        self.cache = {}
        self.reads = set()
        self.dispatch = {}      # tool_use id -> line, for Agent/Task calls
        self.dispatch_out = {}  # tool_use id -> 'returned' | 'failed'
        self.turn_text = None
        self.turn_line = None
        self.agents_per_message = {}


def scan(files, base, det, since, until):
    """(per-file input records, findings, counters)."""
    inputs = []
    findings = []
    c = {
        "turns_judged": 0, "turns_with_change": 0, "claims_unbacked": 0,
        "bash_results": 0, "config_first": 0, "empty_probe": 0, "probes_run": 0,
        "pre_static": 0, "pre_denied_recorded": 0,
        "dispatches": 0, "unpinned": 0, "returned": 0, "failed": 0, "silent": 0, "fan_outs": 0,
        "writes_unread": 0, "writes": 0, "big_reads": 0, "reads": 0,
        "irreversible": 0, "irreversible_sends": 0,
    }
    as_of = ""
    for path in files:
        rel = os.path.relpath(path, base) if base else path
        entries, digest = read_entries(path, since, until)
        if not entries:
            continue
        inputs.append({"file": rel, "lines": len(entries), "sha256": digest})
        s = Session(rel, "/subagents/" in path.replace(os.sep, "/"))
        cwd = None
        for n, e in entries:
            ts = e.get("timestamp") if isinstance(e.get("timestamp"), str) else ""
            if ts > as_of:
                as_of = ts
            if isinstance(e.get("cwd"), str):
                cwd = e["cwd"]
            if e.get("isSidechain") is True:
                continue
            if det.verify._is_compact(e):
                s.uses, s.cache = [], {}
                continue
            kind = e.get("type")
            if kind == "assistant":
                msg = e.get("message") if isinstance(e.get("message"), dict) else {}
                mid = msg.get("id") if isinstance(msg.get("id"), str) else "line-%d" % n
                for b in blocks(e):
                    if b.get("type") == "tool_use":
                        s.uses.append(b)
                        s.use_line[b.get("id")] = n
                        name = b.get("name")
                        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                        if name in ("Agent", "Task"):
                            s.agents_per_message[mid] = s.agents_per_message.get(mid, 0) + 1
                            c["dispatches"] += 1
                            s.dispatch[b.get("id")] = n
                            if det.unpinned(inp):
                                c["unpinned"] += 1
                                findings.append(_f(1, "dojo-router/unpinned", rel, n,
                                                   "%s dispatch with no model" % (inp.get("subagent_type") or "general-purpose")))
                        elif name == "Bash" and isinstance(inp.get("command"), str):
                            cmd = inp["command"]
                            if IRREVERSIBLE.search(cmd) and not _scratch_only(cmd):
                                c["irreversible"] += 1
                                findings.append(_f(10, "irreversible", rel, n, cmd))
                            for gid in det.pre(cmd, cwd):
                                c["pre_static"] += 1
                                findings.append(_f(10, "dojo-gates/" + gid, rel, n, cmd))
                        elif isinstance(name, str) and name.startswith("mcp__") and SEND_TOOL.search(name):
                            c["irreversible_sends"] += 1
                            findings.append(_f(10, "irreversible-send", rel, n, name))
                    elif b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip():
                        s.turn_text, s.turn_line = b["text"], n
            elif kind == "user":
                trs = [b for b in blocks(e) if b.get("type") == "tool_result" and isinstance(b.get("tool_use_id"), str)]
                if trs:
                    tur = e.get("toolUseResult") if isinstance(e.get("toolUseResult"), dict) else {}
                    for b in trs:
                        tid = b["tool_use_id"]
                        text = result_text(b)
                        s.results[tid] = {"error": bool(b.get("is_error")), "text": text, "interrupted":
                                          bool(tur.get("interrupted")) and len(trs) == 1}
                        _on_result(s, det, c, findings, tid, text, bool(b.get("is_error")), tur if len(trs) == 1 else {}, n)
                    continue
                text = det.verify._text_of(det.verify._content(e))
                if det.verify._origin_kind(e) == "task-notification" or text.lstrip().startswith("<task-notification"):
                    ids = re.findall(r"<tool-use-id>([^<]+)</tool-use-id>", text)
                    code = re.search(r"completed \(exit code (\d+)\)", text)
                    if ids and code:
                        s.bg_done[ids[0].strip()] = code.group(1) == "0"
                        s.cache.pop(ids[0].strip(), None)
                    continue
                if det.verify._is_prompt(e):
                    _end_turn(s, det, c, findings, cwd)
        _end_turn(s, det, c, findings, cwd)
        c["fan_outs"] += sum(1 for k in s.agents_per_message.values() if k >= 2)
        for tid in s.dispatch:
            out = s.dispatch_out.get(tid)
            if out is None:
                c["silent"] += 1
                findings.append(_f(6, "dojo-tally/silent", rel, s.dispatch[tid], "a dispatched agent never returned"))
    return inputs, findings, c, as_of


TEMP_PATH = re.compile(r"^(?:/tmp/|/private/tmp/|/var/folders/|/private/var/folders/|\$TMPDIR|\$\{TMPDIR\}|\$SCR|\$SP\b|\$S\b|\$T\b|\$D\b|\$TMP)")


def _scratch_only(cmd):
    """True when the only irreversible step is removing scratch paths (rm -rf under a temp folder)."""
    if re.search(r"\bgit\s+push\b|\bgh\s+pr\s+merge\b|\bgh\s+release\b|\bdeploy\b|\bpublish\b|\brailway\s+up\b", cmd):
        return False
    targets = []
    for m in re.finditer(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+([^;&|\n]+)", cmd):
        targets += [t.strip("'\"") for t in m.group(1).split() if not t.startswith("-")]
    return bool(targets) and all(TEMP_PATH.match(t) or "scratchpad" in t or t.startswith("$") for t in targets)


def _f(rule, detector, rel, line, text):
    key = "%s|%s|%s|%d" % (rule, detector, rel, line)
    return {"id": hashlib.sha1(key.encode()).hexdigest()[:12], "rule": rule, "detector": detector,
            "file": rel, "line": line + 1, "excerpt": excerpt(text)}


def _on_result(s, det, c, findings, tid, text, is_error, tur, n):
    use = None
    for u in reversed(s.uses):
        if u.get("id") == tid:
            use = u
            break
    if use is None:
        return
    name = use.get("name")
    inp = use.get("input") if isinstance(use.get("input"), dict) else {}
    if tid in s.dispatch:
        s.dispatch_out[tid] = "failed" if is_error else "returned"
        c["failed" if is_error else "returned"] += 1
        if is_error:
            findings.append(_f(6, "dojo-tally/failed", s.rel, n, text))
    if name == "Bash" and isinstance(inp.get("command"), str) and not inp.get("run_in_background"):
        c["bash_results"] += 1
        m = re.match(r"\s*PreTool(?:Use)?:Bash hook error: dojo-gates: ([a-z-]+)", text or "")
        if m:
            c["pre_denied_recorded"] += 1
            return
        kinds, probe = det.post(inp["command"], is_error, text, tur.get("stdout"), tur.get("stderr"))
        if kinds:
            c["config_first"] += 1
            findings.append(_f(8, "dojo-gates/config-first:" + "+".join(sorted(kinds)), s.rel, n, inp["command"]))
        segs = det.shell.all_segments(inp["command"])
        is_probe, _quiet = det.after._is_probe(segs)
        if is_probe:
            c["probes_run"] += 1
        if probe:
            c["empty_probe"] += 1
            findings.append(_f(9, "dojo-gates/empty-probe", s.rel, n, inp["command"]))
    elif name == "Read" and isinstance(inp.get("file_path"), str):
        c["reads"] += 1
        s.reads.add(inp["file_path"])
        if re.match(r"\s*PreTool(?:Use)?:Read hook error: dojo-gates: big-read", text or ""):
            c["big_reads"] += 1
            findings.append(_f(3, "dojo-gates/big-read (denied)", s.rel, n, inp["file_path"]))
        elif len(text or "") > BIG_READ_CHARS and inp.get("offset") is None and inp.get("limit") is None:
            c["big_reads"] += 1
            findings.append(_f(3, "large whole-file read", s.rel, n, "%s (%d chars)" % (inp["file_path"], len(text))))
    elif name == "Write" and isinstance(inp.get("file_path"), str) and not is_error:
        c["writes"] += 1
        if re.search(r"has been updated|updated successfully", text or "") and inp["file_path"] not in s.reads:
            c["writes_unread"] += 1
            findings.append(_f(2, "write over an unread file", s.rel, n, inp["file_path"]))


def _end_turn(s, det, c, findings, cwd):
    """A turn ended (a new prompt, or the end of the file): judge its final message as dojo-verify's Stop hook
    does, from the main thread's tool calls since the last compaction."""
    if s.subagent or s.turn_text is None:
        s.turn_text = None
        return
    det.verify._set_project_root(cwd)
    mutated = False
    evidence = False
    for use in reversed(s.uses):
        tid = use.get("id")
        if tid not in s.cache or (use.get("input") or {}).get("run_in_background") is True:
            s.cache[tid] = det.verify._use_events(use, s.results, s.bg_done)
        for ev in reversed(s.cache[tid]):
            if ev == "mut":
                mutated = True
                break
            evidence = True
        if mutated:
            break
    c["turns_judged"] += 1
    if mutated:
        c["turns_with_change"] += 1
    claim = det.verify.detect_claim(s.turn_text, mutated)
    if claim is not None and not evidence:
        c["claims_unbacked"] += 1
        findings.append(_f(5, "dojo-verify/stop", s.rel, s.turn_line, claim["sentence"]))
    s.turn_text = None


# ------------------------------------------------------------------------------------------------ report


ACCURACY_FOR = {
    3: ["dojo-gates/big-read"],
    5: ["dojo-verify/stop"],
    8: ["dojo-gates/config-first:auth", "dojo-gates/config-first:conn", "dojo-gates/config-first:cmd",
        "dojo-gates/config-first:path"],
    9: ["dojo-gates/empty-probe"],
    10: ["dojo-gates/staging", "dojo-gates/secret-print", "dojo-gates/masked-exit"],
}


def accuracy_rows(root):
    sys.path.insert(0, os.path.join(root, "scripts"))
    import hook_accuracy as HA
    rep = HA.evaluate(HA.load_fixtures(root), root)
    out = {}
    for r in rep["rows"]:
        out[r["hook"]] = {"tp": r["tp"], "fp": r["fp"], "fn": r["fn"], "tn": r["tn"],
                          "precision": _r(r["precision"]), "recall": _r(r["recall"]),
                          "precision_ci": [_r(x) for x in r["precision_ci"]] if r["precision_ci"] else None,
                          "recall_ci": [_r(x) for x in r["recall_ci"]] if r["recall_ci"] else None}
    return out


def _r(x):
    return None if x is None else round(x, 4)


def doctor_summary(root, config_dir):
    cmd = [sys.executable, os.path.join(root, "plugins", "dojo-doctor", "scripts", "doctor.py"), "--json",
           "--section", DOCTOR_SECTIONS]
    if config_dir:
        cmd += ["--config-dir", config_dir]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        data = json.loads(p.stdout.decode("utf-8", "replace") or "null")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"error": type(exc).__name__}
    if not isinstance(data, dict) or not isinstance(data.get("sections"), dict):
        return {"error": "unexpected dojo-doctor output"}
    keep = {}
    for sid, sec in sorted(data["sections"].items()):
        if isinstance(sec, dict):
            keep[sid] = {"status": sec.get("status"), "summary": sec.get("summary"),
                         "items": [mask(json.dumps(i, sort_keys=True))[:300] for i in (sec.get("items") or [])]}
    return {"tool": data.get("tool"), "version": data.get("version"), "summary": data.get("summary"),
            "sections": keep}


def build(paths, root, since=None, until=None, doctor=True, accuracy=True, config_dir=None, max_evidence=50,
          field_accuracy=None):
    files = find_transcripts(paths)
    if not files:
        raise ReportError("no transcript files under %s" % ", ".join(paths))
    base = os.path.commonpath(files) if len(files) > 1 else os.path.dirname(files[0])
    det = Detectors(root)
    inputs, findings, c, as_of = scan(files, base, det, since, until)
    findings.sort(key=lambda f: (f["rule"], f["detector"], f["file"], f["line"]))
    acc = accuracy_rows(root) if accuracy else None
    by_rule = {}
    for f in findings:
        by_rule.setdefault(f["rule"], []).append(f)
    counts = {
        1: ("unpinned dispatches", c["unpinned"], c["dispatches"], "dispatches"),
        2: ("writes over a file not read in the session", c["writes_unread"], c["writes"], "writes"),
        3: ("large whole-file reads", c["big_reads"], c["reads"], "reads"),
        4: ("fan-outs (two or more agents from one message)", c["fan_outs"], None, None),
        5: ("turns ending in a success claim with no check after the last change", c["claims_unbacked"],
            c["turns_with_change"], "turns with a change"),
        6: ("agents that never returned", c["silent"], c["dispatches"], "dispatches"),
        7: (None, None, None, None),
        8: ("commands that failed at a configuration boundary", c["config_first"], c["bash_results"], "command results"),
        9: ("probes that printed nothing", c["empty_probe"], c["probes_run"], "probes"),
        10: ("irreversible commands and sends (guards that would deny: %d; denials recorded: %d)"
             % (c["pre_static"], c["pre_denied_recorded"]), c["irreversible"] + c["irreversible_sends"], None, None),
    }
    rules = []
    for num, title in RULES:
        what, n, of, of_label = counts[num]
        row = {"rule": num, "title": title, "measure": what, "count": n, "of": of, "of_label": of_label,
               "evidence_total": len(by_rule.get(num, [])),
               "evidence": [f["id"] for f in by_rule.get(num, [])][:max_evidence]}
        if num in NOT_AUTOMATED:
            row["needs_a_reader"] = NOT_AUTOMATED[num]
        if acc is not None and num in ACCURACY_FOR:
            row["detector_accuracy"] = dict((h, acc[h]) for h in ACCURACY_FOR[num] if h in acc)
        if field_accuracy and num in ACCURACY_FOR:
            fa = dict((h, field_accuracy[h]) for h in ACCURACY_FOR[num] if h in field_accuracy)
            if fa:
                row["field_accuracy"] = fa
        rules.append(row)
    report = {
        "report": "dojo runtime health",
        "version": VERSION,
        "as_of": as_of,
        "window": {"since": since, "until": until},
        "tools": {p: plugin_version(root, p) for p in ("dojo-verify", "dojo-gates", "dojo-router", "dojo-doctor",
                                                        "dojo-tally")},
        "tree": tree_commit(root),
        "inputs": {"files": inputs, "count": len(inputs),
                   "digest": hashlib.sha256("".join(i["sha256"] for i in inputs).encode()).hexdigest()},
        "counters": c,
        "rules": rules,
        "accuracy_note": ("Detector accuracy is measured on the repository's fixture suite (scripts/hook_accuracy.py, "
                          "method in ACCURACY.md). Fixtures were written alongside the detectors, so these figures "
                          "are in-sample; treat every finding as a lead to confirm by reading, never as a verdict."),
    }
    if field_accuracy:
        report["field_accuracy_source"] = field_accuracy.get("_source", "supplied with --field-accuracy")
    if doctor:
        report["setup"] = doctor_summary(root, config_dir)
    return report, findings


def markdown(report):
    lines = ["# Dojo runtime health", ""]
    lines.append("As of %s, from %d transcript file(s) (input digest `%s`). Tools: %s. Tree: %s." % (
        report["as_of"] or "n/a", report["inputs"]["count"], report["inputs"]["digest"][:16],
        ", ".join("%s %s" % (k, v) for k, v in sorted(report["tools"].items()) if v), report["tree"] or "n/a"))
    lines += ["", "| rule | what was counted | count | of | evidence | detector precision / recall (fixtures) | field precision |",
              "|---|---|---|---|---|---|---|"]
    for r in report["rules"]:
        acc = r.get("detector_accuracy") or {}
        accs = "; ".join("%s %s / %s" % (h.split("/")[-1], _pct(a["precision"]), _pct(a["recall"]))
                         for h, a in sorted(acc.items()))
        what = r["measure"] or ("needs a reader: " + r.get("needs_a_reader", ""))
        of = ("%d %s" % (r["of"], r["of_label"])) if r.get("of") is not None else ""
        fa = r.get("field_accuracy") or {}
        fas = "; ".join("%s %s (n=%s)" % (h.split("/")[-1], _pct(a.get("precision")), a.get("n", "?"))
                        for h, a in sorted(fa.items()))
        lines.append("| %d. %s | %s | %s | %s | %d | %s | %s |" % (
            r["rule"], r["title"], what, "" if r["count"] is None else r["count"], of, r["evidence_total"], accs or "-",
            fas or "-"))
    lines += ["", report["accuracy_note"]]
    if report.get("field_accuracy_source"):
        lines += ["", "Field precision: " + report["field_accuracy_source"]]
    if "setup" in report:
        setup = report["setup"]
        lines += ["", "## Setup (dojo-doctor)", ""]
        if isinstance(setup, dict) and isinstance(setup.get("sections"), dict):
            for sid in sorted(setup["sections"]):
                sec = setup["sections"][sid]
                lines.append("- **%s**: %s, %s" % (sid, sec.get("status"), sec.get("summary")))
        else:
            lines.append("- %s" % json.dumps(setup, sort_keys=True)[:400])
    lines += ["", "Each counted finding is in evidence.jsonl with its file, line and a masked excerpt.", ""]
    return "\n".join(lines)


def _pct(x):
    return "n/a" if x is None else "%.0f%%" % (100 * x)


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("paths", nargs="*", default=["~/.claude/projects"])
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--plugins-root", default=DEFAULT_ROOT)
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-doctor", action="store_true")
    ap.add_argument("--no-accuracy", action="store_true")
    ap.add_argument("--config-dir")
    ap.add_argument("--max-evidence", type=int, default=50)
    ap.add_argument("--field-accuracy", help="JSON of {hook: {precision, n}} measured on real sessions, with an "
                                             "optional _source line; shown beside the fixture figures")
    a = ap.parse_args(argv)
    for d in (a.since, a.until):
        if d and not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            print("health_report: dates are YYYY-MM-DD", file=sys.stderr)
            return 2
    try:
        field = None
        if a.field_accuracy:
            with open(a.field_accuracy) as fh:
                field = json.load(fh)
        report, findings = build(a.paths, os.path.abspath(a.plugins_root), a.since, a.until, not a.no_doctor,
                                 not a.no_accuracy, a.config_dir, a.max_evidence, field)
    except ReportError as exc:
        print("health_report: could not run: %s" % exc, file=sys.stderr)
        return 2
    js = json.dumps(report, indent=1, sort_keys=True) + "\n"
    md = markdown(report)
    ev = "".join(json.dumps(f, sort_keys=True) + "\n" for f in findings)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for name, body in (("health.json", js), ("health.md", md), ("evidence.jsonl", ev)):
            with open(os.path.join(a.out, name), "w", encoding="utf-8") as fh:
                fh.write(body)
        print("health_report: wrote health.json, health.md and evidence.jsonl (%d findings) to %s" % (len(findings), a.out))
    else:
        sys.stdout.write(js if a.json else md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
