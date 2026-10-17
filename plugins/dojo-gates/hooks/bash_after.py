#!/usr/bin/env python3
"""dojo-gates: PostToolUse(Bash) and PostToolUseFailure(Bash) entry point.

config-first   output that shows a configuration boundary failure (an
               authorization error, a refused connection, a missing command or
               path) reported by a program this command ran: add context once
               per session per pattern.
empty-probe    a search or probe command that printed nothing: add context
               once per session.

config-first reads a line only when it has the shape of a program reporting its
own failure (`bash: foo: command not found`, `cat: x: No such file or
directory`, `HTTP/1.1 401 Unauthorized`, `connect ECONNREFUSED ...`). Text that
only mentions those words is data: a file, a log or source code being printed.
Three failures are not configuration either: `ls`, `stat` or `test` answering an
existence question, a missing path that follows a code error in the same output
(the code died before it made the file), and a "command" whose name has spaces
in it (an unsplit variable).

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
# a line that quotes these words as code or prose: a regex, a quoted string
_CODEISH = re.compile(
    r"re\.compile|\(\?:|\\b|401\|403|403\|401|ECONNREFUSED\||\|connection refused"
    r"|['\"`](?:ECONNREFUSED|connection refused|command not found|No such file or directory)['\"`]",
    re.IGNORECASE,
)

# the shell's own "command not found" line: zsh, bash or sh, dash
_NOCMD_SHAPES = (
    re.compile(r"^(?P<who>[^\s:]+)(?::\d+)?: command not found: (?P<name>.+?)\s*$"),
    re.compile(r"^(?P<who>[^\s:]+)(?::\s*line\s+\d+)?: (?P<name>[^:]+?): command not found\s*$"),
    re.compile(r"^(?P<who>[^\s:]+): \d+: (?P<name>[^:]+?): not found\s*$"),
)
# a program reporting a path it could not open
_NOFILE_SHAPES = (
    re.compile(r"^(?P<who>\S*python[\d.]*): can't open file '[^']*': \[Errno 2\] No such file or directory"),
    re.compile(r"^(?P<who>FileNotFoundError|IOError|OSError): \[Errno 2\] No such file or directory"),
    re.compile(r"(?P<who>ENOENT): no such file or directory\b"),
    re.compile(r"(?:^|\s)(?P<who>fatal|error|warning): .*No such file or directory\s*$", re.IGNORECASE),
    re.compile(r"^(?P<who>[^\s:]+)(?::\s*line\s+\d+)?(?::\s*[\w.-]+)?: .+?: No such file or directory\s*$"),
    re.compile(r"^(?P<who>[^\s:]+)(?::\d+)?: no such file or directory: \S.*$"),
)
# a code error: a missing path printed after one is a consequence, not configuration
_CODE_ERROR = re.compile(
    r"^(?:\w+\.)*(?:NameError|SyntaxError|IndentationError|TabError|TypeError|AttributeError|KeyError"
    r"|IndexError|ValueError|UnboundLocalError|ZeroDivisionError|AssertionError|RecursionError"
    r"|NotImplementedError|JSONDecodeError|ReferenceError|RangeError)\b"
    r"|^(?:Uncaught )?(?:ReferenceError|TypeError|SyntaxError): "
    r"|^panic: |^error\[E\d+\]"
    r"|: syntax error near unexpected token|: parse error near |: bad substitution\s*$|: unbound variable\s*$"
)
_SHELL_NAMES = frozenset(
    ["sh", "bash", "zsh", "dash", "ksh", "fish", "(eval)", "env", "xargs", "nohup", "exec", "sudo",
     "command", "time", "nice", "timeout", "gtimeout", "cd", "source", ".", "pushd"]
)
# programs whose "No such file" answers an existence question
_EXISTENCE_PROBES = frozenset(["ls", "stat", "file", "realpath", "readlink", "test", "[", "[[", "which", "type",
                               "whereis"])
# programs that only read, print or move around: a 401 or a refused connection in their output is data
_INERT = frozenset(
    ["cat", "bat", "batcat", "head", "tail", "less", "more", "nl", "tac", "sed", "awk", "gawk", "grep", "egrep",
     "fgrep", "rg", "ag", "ack", "jq", "yq", "wc", "sort", "uniq", "cut", "tr", "column", "fold", "fmt", "paste",
     "echo", "printf", "print", "ls", "find", "fd", "tree", "stat", "file", "basename", "dirname", "realpath",
     "readlink", "date", "true", "false", ":", "cd", "pushd", "popd", "export", "set", "unset", "test", "[", "[[",
     "sleep", "which", "type", "hash", "xxd", "od", "hexdump", "strings", "pwd", "whoami", "id", "uname",
     "printenv", "diff", "cmp", "md5", "shasum", "sha256sum", "base64", "iconv", "xargs", "tee", "mkdir", "touch",
     "rm", "cp", "mv", "ln", "chmod", "du", "df", "plutil", "defaults", "mdls", "sips", "open",
     # shell syntax and builtins
     "for", "select", "case", "esac", "in", "function", "read", "local", "declare", "typeset", "readonly",
     "return", "exit", "shift", "wait", "trap", "umask", "alias", "let", "getopts"]
)
_GIT_LOCAL = frozenset(["log", "show", "diff", "grep", "blame", "status", "ls-files", "rev-parse", "branch",
                        "tag", "config", "cat-file", "rev-list", "shortlog", "describe", "worktree", "stash",
                        "add", "commit", "reset", "checkout", "switch", "restore", "mv", "rm", "init"])
_PY_RUNNERS = re.compile(r"^(?:python[\d.]*|pytest|py\.test|uv|poetry|pipenv|pip[\d.]*|ipython|.*\.py)$")

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

_PROBE_VERBS = frozenset(["grep", "egrep", "fgrep", "rg", "find", "fd", "ls", "jq"])
_REDIR = re.compile(r"^(\d*)(&?>>?)(&\d*-?)?$")


def _clip(text):
    if len(text) <= 2 * _EDGE:
        return text
    return text[:_EDGE] + "\n" + text[-_EDGE:]


def _programs(segs):
    """(base names of the programs this command runs, True when one of them does more than read, print or
    move files: a network client, a server, a test runner, a script)."""
    from _shell import base, git_of, unwrap

    progs = set()
    active = False
    for seg in segs:
        w = unwrap(seg.words)
        if not w:
            continue
        b = base(w[0].text)
        progs.add(b)
        if b == "git":
            g = git_of(seg)
            if not g or g[0] not in _GIT_LOCAL:
                active = True
        elif b not in _INERT:
            active = True
    return progs, active


def _loop_programs(segs):
    """First words of the values a `for x in ...` loop iterates over: `for c in "melt --version" jq` tries
    melt and jq on purpose, so a missing one answers the question it asked."""
    from _shell import base

    out = set()
    for seg in segs:
        w = [x.text for x in seg.words]
        if len(w) >= 3 and w[0] == "for" and w[2] == "in":
            for v in w[3:]:
                parts = v.split()
                if parts:
                    out.add(base(parts[0]))
    return out


def _missing_command(line, progs, tried=frozenset()):
    """True for the shell's own "command not found" line about a real program name."""
    for rx in _NOCMD_SHAPES:
        m = rx.match(line)
        if not m:
            continue
        who = os.path.basename(m.group("who").lstrip("-"))
        name = m.group("name").strip("'\"`")
        if not name or re.search(r"\s", name) or name.startswith("$") or "=" in name:
            return False  # an unsplit variable or an assignment, not a missing program
        if os.path.basename(name) in tried:
            return False  # a loop trying candidates on purpose
        return who in _SHELL_NAMES or who in progs
    return False


def _missing_path(line, progs, active):
    """True for a program this command ran reporting a path it needed and could not open."""
    for rx in _NOFILE_SHAPES:
        m = rx.match(line) if rx.pattern.startswith("^") else rx.search(line)
        if not m:
            continue
        who = os.path.basename(m.group("who").lstrip("-"))
        if who.lower() in ("fatal", "error", "warning"):
            who = who.lower()
        if who in _EXISTENCE_PROBES:
            return False  # `ls x` answering whether x exists
        if who in _SHELL_NAMES:
            return True
        if who in ("FileNotFoundError", "IOError", "OSError"):
            return any(_PY_RUNNERS.match(p) for p in progs)
        if who in ("fatal", "error", "warning"):
            return active or "git" in progs  # git reports its own path failures this way, even status
        if who == "ENOENT":
            return active
        return who in progs
    return False


def _config_hits(text, segs):
    """Which configuration-boundary kinds the output shows, read line by line.

    When the command was a test, build or lint run, an authorization number on an
    assertion line is the code under test talking, not a credential problem. A
    command that only reads and prints (cat, grep, sed, jq, git log ...) shows
    data: a 401 or a refused connection in its output is not its own failure.
    """
    progs, active = _programs(segs)
    tried = _loop_programs(segs)
    check_run = _has_check(segs)
    hits = []
    after_code_error = False
    for line in _clip(text).splitlines():
        s = line.strip()
        if not s:
            continue
        if _CODE_ERROR.search(s):
            after_code_error = True
            continue
        if "cmd" not in hits and _missing_command(s, progs, tried):
            hits.append("cmd")
        if "path" not in hits and not after_code_error and _missing_path(s, progs, active):
            hits.append("path")
        if not active or _CODEISH.search(s):
            continue
        if "auth" not in hits and _LINE_AUTH.search(s) and not (check_run and _ASSERTISH.search(s)):
            hits.append("auth")
        if "conn" not in hits and _CONN.search(s):
            hits.append("conn")
    return hits


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

    if not killed("config-first"):
        for key in _config_hits(scan_text, segs):
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
