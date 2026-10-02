#!/usr/bin/env python3
"""dojo-gates: PostToolUse(Bash) and PostToolUseFailure(Bash) entry point.

config-first   output that looks like a configuration boundary failure (an
               authorization error, a refused connection, a missing command or
               path): add context once per session per pattern.
empty-probe    a search or probe command that printed nothing: add context
               once per session.

A Bash command that exits non-zero normally arrives as PostToolUseFailure with
an `error` string ("Exit code N" plus its output), except commands Claude Code
treats as clean at exit 1 (grep, rg, find, diff, test), which arrive as
PostToolUse. Both shapes are handled. Fails open.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_EDGE = 64 * 1024

# 401/403 only counts next to an HTTP marker, not beside any word on the line
_LINE_AUTH = re.compile(
    r"\bHTTP(?:/[\d.]+)?\s+(?:401|403)\b"
    r"|\b(?:status|response)(?: code)?[\"']?\s*[:=]\s*[\"']?(?:401|403)\b"
    r"|\berror:?\s+(?:code\s+)?(?:401|403)\b"
    r"|\b(?:401|403)\s+(?:unauthori[sz]ed|forbidden)\b"
    r"|\b(?:unauthori[sz]ed|forbidden)\W{1,4}(?:401|403)\b",
    re.I,
)
# a test runner printing `AssertionError: status: 403 != 200` is reporting the code under test
_ASSERTISH = re.compile(
    r"assert|expected|received|!=|==|\btoBe\b|\btoEqual\b", re.I
)
_CONN = re.compile(r"ECONNREFUSED|connection refused", re.I)
_NOCMD = re.compile(r"command not found")
_NOFILE = re.compile(r"No such file or directory")

_CONFIG_TEXT = {
    "auth": (
        "an authorization failure",
        "is the token or key set, current and allowed to do this? Check the environment and the "
        "credential's scope",
    ),
    "conn": (
        "a refused connection",
        "is the service running, and are the host, port and URL right? Check the environment and "
        "config the client reads",
    ),
    "cmd": (
        "a missing command",
        "is it installed, and is it on the PATH this shell uses? Check the environment before the code",
    ),
    "path": (
        "a missing path",
        "is the working directory right, and does the path exist as written? Check the config and "
        "environment that produce it",
    ),
}

_READ_VERBS = frozenset(
    ["grep", "rg", "ag", "ack", "egrep", "fgrep", "cat", "bat", "head", "tail", "less", "sed", "awk", "jq"]
)
_PROBE_VERBS = frozenset(["grep", "egrep", "fgrep", "rg", "find", "fd", "ls", "jq"])
_REDIR = re.compile(r"^(\d*)(&?>>?)(&\d*-?)?$")


def _clip(text):
    if len(text) <= 2 * _EDGE:
        return text
    return text[:_EDGE] + "\n" + text[-_EDGE:]


def _config_hits(text, check_run=False):
    """Which configuration-boundary kinds the output shows. When the command was
    a test, build or lint run, an authorization number on an assertion line is
    the code under test talking, not a credential problem."""
    hits = []
    for line in _clip(text).splitlines():
        if "auth" not in hits and _LINE_AUTH.search(line):
            if not (check_run and _ASSERTISH.search(line)):
                hits.append("auth")
        if "conn" not in hits and _CONN.search(line):
            hits.append("conn")
        if "cmd" not in hits and _NOCMD.search(line):
            hits.append("cmd")
        if "path" not in hits and _NOFILE.search(line):
            hits.append("path")
    return hits


def _first_is_reader(segs):
    from _shell import git_of, verb

    for seg in segs:
        if seg.nested:
            continue
        v = verb(seg)
        if not v:
            continue
        if v in _READ_VERBS:
            return True
        if v == "git":
            g = git_of(seg)
            if g and g[0] in ("grep", "log", "show", "diff"):
                return True
        return False
    return False


def _has_check(segs):
    from _guards import is_check_command

    return any(is_check_command(seg.words) for seg in segs if not seg.nested and seg.words)


def _is_probe(segs):
    """(is a probe, is quiet or redirected away)."""
    from _shell import base, unwrap

    probe = False
    for seg in segs:
        if seg.nested:
            continue
        w = unwrap(seg.words)
        if not w:
            continue
        b = base(w[0].text)
        silent_probe = False
        if b in _PROBE_VERBS:
            probe = True
            if b in ("grep", "egrep", "fgrep", "rg"):
                for x in w[1:]:
                    t = x.text
                    if t == "--":
                        break
                    if t in ("--quiet", "--silent"):
                        silent_probe = True
                    elif t.startswith("-") and not t.startswith("--") and "q" in t[1:]:
                        silent_probe = True
        elif b == "curl":
            for x in w[1:]:
                t = x.text
                short = t.startswith("-") and not t.startswith("--")
                if t == "--silent" or (short and "s" in t[1:]):
                    probe = True
                if t in ("--output", "--remote-name") or (short and ("o" in t[1:] or "O" in t[1:])):
                    silent_probe = True  # the body goes to a file, so empty stdout is expected
        if silent_probe:
            return True, True
        for x in seg.words:
            m = _REDIR.match(x.text)
            if m and (m.group(1) in ("", "1") or m.group(2).startswith("&")) and m.group(3) != "&1":
                return probe, True
    return probe, False


def main():
    from _common import killed, once, post_context, read_payload, session_of

    if killed():
        return
    payload = read_payload()
    if payload is None:
        return
    name = payload.get("tool_name")
    if name is not None and name != "Bash":
        return
    event = payload.get("hook_event_name")
    if event not in ("PostToolUse", "PostToolUseFailure"):
        return
    ti = payload.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str) or not cmd.strip():
        return
    if len(cmd) > 512 * 1024:
        cmd = cmd[:128 * 1024] + "\n" + cmd[-128 * 1024:]
    background = isinstance(ti, dict) and bool(ti.get("run_in_background"))

    out_text = ""
    err_text = ""
    exit1_clean = False
    if event == "PostToolUse":
        tr = payload.get("tool_response")
        if not isinstance(tr, dict):
            return
        if tr.get("interrupted") or tr.get("backgroundTaskId") or background:
            return
        so = tr.get("stdout")
        se = tr.get("stderr")
        out_text = so if isinstance(so, str) else ""
        err_text = se if isinstance(se, str) else ""
        empty_all = not out_text.strip() and not err_text.strip()
        scan_text = out_text + "\n" + err_text
    else:
        if payload.get("is_interrupt") or background:
            return
        error = payload.get("error")
        if not isinstance(error, str):
            return
        m = re.match(r"\s*Exit code (\d+)\b(.*)$", error, re.S)
        rest = m.group(2).strip() if m else error.strip()
        exit1_clean = bool(m) and m.group(1) == "1" and not rest
        empty_all = exit1_clean
        scan_text = error

    from _shell import all_segments

    segs = all_segments(cmd)
    sid = session_of(payload)
    notes = []

    if not killed("config-first") and not _first_is_reader(segs):
        for key in _config_hits(scan_text, _has_check(segs)):
            if once(sid, "config-first:" + key):
                what, check = _CONFIG_TEXT[key]
                notes.append(
                    "dojo-gates: config-first — that output looks like %s, which usually points at "
                    "configuration rather than code: %s. Check env, settings and credentials before "
                    "reading logic. Shown once per session." % (what, check)
                )

    if not killed("empty-probe") and empty_all:
        probe, quiet = _is_probe(segs)
        if probe and not quiet and once(sid, "empty-probe"):
            notes.append(
                "dojo-gates: empty-probe — that search printed nothing. Empty output isn't evidence: prove "
                "the probe can see a known positive (run it against something you know matches) before you "
                "trust the negative. Shown once per session."
            )

    if notes:
        post_context(event, "\n".join(notes))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
