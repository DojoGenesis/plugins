"""The PreToolUse(Bash) guards of dojo-gates.

Each guard is a function(ctx) -> None | ("deny"|"warn", message). They are
regex-and-token checks over the command text, not a shell parser; see the
`gates` skill for the honest limits. No guard makes a network or model call.
Git is only run (read-only, <= 3 s in total) when the command itself contains
a history-rewriting verb.
"""
import fnmatch
import os
import re
import sys
import time

from _common import message, override
from _shell import (
    base,
    git_of,
    unwrap,
    verb,
)

# Where a hook's PATH may differ from the Bash tool's shell PATH. Tests patch it.
FALLBACK_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/opt/homebrew/opt/coreutils/libexec/gnubin",
)


class Ctx(object):
    def __init__(self, cmd, segs, payload):
        self.cmd = cmd
        self.segs = segs
        self.payload = payload

    def start_cwd(self):
        c = self.payload.get("cwd") if isinstance(self.payload, dict) else None
        if isinstance(c, str) and c and os.path.isdir(c):
            return c
        try:
            return os.getcwd()
        except Exception:
            return None


# --------------------------------------------------------------------------------
# staging
# --------------------------------------------------------------------------------

_COMMIT_SHORT_VALUE = frozenset("mFCct")
_COMMIT_LONG_VALUE = (
    "message",
    "file",
    "author",
    "date",
    "template",
    "reuse-message",
    "reedit-message",
    "fixup",
    "squash",
    "cleanup",
    "trailer",
    "pathspec-from-file",
)


_WHOLE_TREE = (".", "./", ":/", ":/.", ":(top)", ":(top).", ":(top)/", ":(top)/.")


def parse_add(rest):
    """True when `git add` arguments stage everything: -A, --all, `.`, `:/`."""
    after_dd = False
    for w in rest:
        t = w.text
        if after_dd:
            if t in _WHOLE_TREE:
                return True
            continue
        if t == "--":
            after_dd = True
            continue
        if t.startswith("--"):
            name = t[2:].split("=")[0]
            if name == "no-ignore-removal":
                return True
            if name and "all".startswith(name):  # git accepts any unambiguous prefix
                return True
            continue
        if t.startswith("-") and len(t) > 1:
            if "A" in t[1:]:
                return True
            continue
        if t in _WHOLE_TREE:
            return True
    return False


def parse_commit(rest):
    """Returns (all, amend) for `git commit` arguments."""
    all_flag = False
    amend = False
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i].text
        i += 1
        if t == "--":
            break
        if t.startswith("--"):
            name, eq, _ = t[2:].partition("=")
            if name == "all":
                all_flag = True
            elif len(name) >= 2 and name.startswith("am") and "amend".startswith(name):
                amend = True
            elif not eq and len(name) >= 3 and any(v.startswith(name) for v in _COMMIT_LONG_VALUE):
                i += 1
        elif t.startswith("-") and len(t) > 1:
            j = 1
            while j < len(t):
                ch = t[j]
                if ch == "a":
                    all_flag = True
                if ch in _COMMIT_SHORT_VALUE:
                    if j == len(t) - 1:
                        i += 1
                    break
                j += 1
    return all_flag, amend


def staging(ctx):
    for seg in ctx.segs:
        g = git_of(seg)
        if not g:
            continue
        sub, rest = g[0], g[1]
        hit = None
        if sub in ("add", "stage") and parse_add(rest):
            hit = "`git add -A`, `git add --all`, `git add .` (and `git stage`, its synonym)"
        elif sub == "commit" and parse_commit(rest)[0]:
            hit = "`git commit -a`"
        if hit:
            return (
                "deny",
                message(
                    "staging",
                    "%s stage everything in the tree, including files you didn't mean to ship" % hit,
                    "Stage explicit paths (`git add path/a path/b`), check `git status`, then commit. "
                    + override("staging"),
                ),
            )
    return None


# --------------------------------------------------------------------------------
# pushed-rewrite
# --------------------------------------------------------------------------------

_GIT_BUDGET = 3.0
_REBASE_EXEMPT = frozenset(
    ["--abort", "--quit", "--continue", "--skip", "--edit-todo", "--show-current-patch"]
)


class _Git(object):
    """Read-only git runner with one overall time budget. None on any failure."""

    def __init__(self):
        self.t0 = time.monotonic()

    def run(self, args, cwd):
        left = _GIT_BUDGET - (time.monotonic() - self.t0)
        if left < 0.1:
            return None
        try:
            import signal
            import subprocess

            env = dict(os.environ)
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_OPTIONAL_LOCKS"] = "0"
            env["LC_ALL"] = "C"
            p = subprocess.Popen(
                ["git"] + list(args),
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                out, _ = p.communicate(timeout=min(left, 2.0))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    p.kill()
                try:
                    p.communicate(timeout=0.3)
                except Exception:
                    pass
                return None
            return p.returncode, out.decode("utf-8", "replace").strip()
        except Exception:
            return None


def _head_pushed(g, cwd, rev="HEAD"):
    """True/False: is `rev` contained in any remote-tracking branch? None = unknown."""
    r = g.run(
        ["for-each-ref", "--count=1", "--contains", rev, "--format=%(refname)", "refs/remotes"],
        cwd,
    )
    if r is None or r[0] != 0:
        return None
    return bool(r[1])


def _count(g, cwd, args):
    r = g.run(["rev-list", "--count"] + args, cwd)
    if r is None or r[0] != 0:
        return None
    try:
        return int(r[1])
    except ValueError:
        return None


def _range_has_pushed(g, cwd, base_rev, tip):
    """Does base..tip (or all of tip when base_rev is None) hold a pushed commit?"""
    spec = [tip] if base_rev is None else ["%s..%s" % (base_rev, tip)]
    total = _count(g, cwd, spec)
    unpushed = _count(g, cwd, spec + ["--not", "--remotes"])
    if total is None or unpushed is None:
        return None
    return unpushed < total


def parse_rebase(rest):
    """Returns (positional args, root) or None for the in-flight controls."""
    pos = []
    root = False
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i].text
        i += 1
        if t in _REBASE_EXEMPT:
            return None
        if t == "--":
            pos.extend(w.text for w in rest[i:])
            break
        if t.startswith("--"):
            name, eq, _ = t[2:].partition("=")
            if name == "root":
                root = True
            elif name in ("onto", "exec", "strategy", "strategy-option") and not eq:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            if len(t) == 2 and t[1] in "xsX":
                i += 1
        else:
            pos.append(t)
    return pos, root


def parse_reset_hard(rest):
    """The first ref given to `git reset --hard <ref>`, "" for none, None when
    the command isn't a --hard reset."""
    hard = False
    ref = ""
    for w in rest:
        t = w.text
        if t == "--":
            break
        if t.startswith("--"):
            name = t[2:].split("=")[0]
            # git takes any unambiguous prefix of a long option, down to `--h`
            if name and "hard".startswith(name):
                hard = True
        elif t.startswith("-") and len(t) > 1:
            continue
        elif not ref:
            ref = t
    return ref if hard else None


def parse_push(rest):
    """Returns (force, positional) for `git push` arguments."""
    force = False
    pos = []
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i].text
        i += 1
        if t == "--":
            pos.extend(w.text for w in rest[i:])
            break
        if t.startswith("--"):
            name, eq, _ = t[2:].partition("=")
            if (
                name == "force"
                or name.startswith("force-with-lease")
                or name.startswith("force-if-includes")
                or (len(name) >= 3 and "force".startswith(name))
            ):
                force = True
            elif name in ("repo", "receive-pack", "exec", "push-option") and not eq:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            j = 1
            while j < len(t):
                ch = t[j]
                if ch == "f":
                    force = True
                if ch == "o":
                    if j == len(t) - 1:
                        i += 1
                    break
                j += 1
        else:
            pos.append(t)
    if any(p.startswith("+") for p in pos[1:]):
        force = True
    return force, pos


def _resolve_dir(cur, target):
    if cur is None or not target or "$" in target or "`" in target or target in ("-",):
        return None
    t = os.path.expanduser(target)
    p = t if os.path.isabs(t) else os.path.join(cur, t)
    return os.path.normpath(p)


def _push_check(g, cwd, pos):
    """Return True when a force push would drop commits the remote has."""
    cur = None
    r = g.run(["symbolic-ref", "-q", "--short", "HEAD"], cwd)
    if r and r[0] == 0 and r[1]:
        cur = r[1]

    def cfg(key):
        rr = g.run(["config", "--get", key], cwd)
        return rr[1] if rr and rr[0] == 0 and rr[1] else None

    if pos:
        remote = pos[0]
        specs = pos[1:]
    else:
        remote = (cur and (cfg("branch.%s.pushRemote" % cur) or cfg("branch.%s.remote" % cur))) or "origin"
        specs = []
    if not specs:
        if not cur:
            return False
        merge = cfg("branch.%s.merge" % cur)
        dst = merge[len("refs/heads/"):] if merge and merge.startswith("refs/heads/") else cur
        specs = ["%s:%s" % (cur, dst)]
    for spec in specs:
        s = spec.lstrip("+")
        if ":" in s:
            src, dst = s.split(":", 1)
        else:
            src, dst = s, s
        if not src or not dst:
            continue
        if src == "HEAD" and dst == "HEAD":
            if not cur:
                continue
            dst = cur
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/"):]
        remote_ref = "refs/remotes/%s/%s" % (remote, dst)
        rv = g.run(["rev-parse", "--verify", "-q", remote_ref], cwd)
        if rv is None or rv[0] != 0:
            continue
        anc = g.run(["merge-base", "--is-ancestor", remote_ref, src], cwd)
        if anc is not None and anc[0] == 1:
            return True
    return False


def pushed_rewrite(ctx):
    start = ctx.start_cwd()
    cur = start
    stack = []
    groups = []  # the working directory to return to when a `( ... )` group ends
    closing = 0
    g = None
    for seg in ctx.segs:
        if not seg.nested:
            for _ in range(closing):
                if groups:
                    cur = groups.pop()
            closing = seg.closes
            for _ in range(seg.opens):
                groups.append(cur)
        v = verb(seg)
        if not seg.nested and v in ("cd", "pushd", "popd"):
            args = [
                w.text
                for w in unwrap(seg.words)[1:]
                if not w.text.startswith("-") and not w.text.startswith("+")
            ]
            if v == "popd":
                cur = stack.pop() if stack else None
                continue
            if v == "pushd":
                stack.append(cur)
            cur = _resolve_dir(cur, args[0]) if args else None
            continue
        gi = git_of(seg)
        if not gi:
            continue
        sub, rest, dirs, ambient = gi
        if sub not in ("commit", "rebase", "reset", "push"):
            continue
        action = None
        if sub == "commit" and parse_commit(rest)[1]:
            action = ("amend", None)
        elif sub == "rebase":
            pr = parse_rebase(rest)
            if pr is not None:
                action = ("rebase", pr)
        elif sub == "reset":
            ref = parse_reset_hard(rest)
            if ref and ref != "HEAD":
                action = ("reset", ref)
        elif sub == "push":
            force, pos = parse_push(rest)
            if force:
                action = ("push", pos)
        if action is None:
            continue
        # where would git run?
        where = start if seg.nested else cur
        for d in dirs:
            where = _resolve_dir(where, d)
        if ambient:
            # --git-dir/--work-tree/GIT_DIR/GIT_WORK_TREE name the repository: ask that one
            kinds = dict(ambient)
            hint = kinds.get("git-dir") or kinds.get("work-tree")
            where = _resolve_dir(where, hint) if hint else None
        if where is None or not os.path.isdir(where):
            continue
        if g is None:
            g = _Git()
        kind, arg = action
        bad = None
        if kind == "amend":
            if _head_pushed(g, where):
                bad = (
                    "`git commit --amend` rewrites a commit that is already on a remote branch, "
                    "so the next push would need a force",
                    "Make a new commit instead (`git commit -m ...`), or `git revert` the old one.",
                )
        elif kind == "rebase":
            pos, root = arg
            tip = pos[1] if len(pos) > 1 else "HEAD"
            pushed = _head_pushed(g, where, tip)
            if pushed is None:
                continue
            if not pushed:
                if root:
                    pushed = _range_has_pushed(g, where, None, tip)
                else:
                    if pos:
                        base_rev = pos[0]
                    else:
                        rv = g.run(["rev-parse", "--verify", "-q", "@{upstream}"], where)
                        if rv is None or rv[0] != 0:
                            continue
                        base_rev = "@{upstream}"
                    pushed = _range_has_pushed(g, where, base_rev, tip)
            if pushed:
                bad = (
                    "`git rebase` would rewrite commits that are already on a remote branch",
                    "Merge instead, or put new work on a new commit. "
                    "`git rebase --abort` / `--continue` are always allowed.",
                )
        elif kind == "reset":
            pushed = _head_pushed(g, where)
            if pushed:
                full = g.run(["rev-parse", "--symbolic-full-name", arg], where)
                remote_ref = bool(full and full[0] == 0 and full[1].startswith("refs/remotes/"))
                same = False
                a = g.run(["rev-parse", "--verify", "-q", arg + "^{commit}"], where)
                b = g.run(["rev-parse", "--verify", "-q", "HEAD"], where)
                if a and b and a[0] == 0 and b[0] == 0 and a[1] == b[1]:
                    same = True
                if not remote_ref and not same:
                    bad = (
                        "`git reset --hard <ref>` would move this branch off commits that are already "
                        "on a remote branch",
                        "To match the remote on purpose, reset to its tracking ref "
                        "(`git reset --hard origin/<branch>`), which stays allowed.",
                    )
        elif kind == "push":
            if _push_check(g, where, arg):
                bad = (
                    "a forced push here would drop commits the remote already has "
                    "(its branch is not an ancestor of what you're pushing)",
                    "Fetch and integrate first, or ask the person before overwriting a remote branch.",
                )
        if bad:
            return ("deny", message("pushed-rewrite", bad[0], bad[1] + " " + override("pushed-rewrite")))
    return None


# --------------------------------------------------------------------------------
# secret-print
# --------------------------------------------------------------------------------

_EXPAND = re.compile(
    r"\$(?:\{!?([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*))"
)
_OUTPUT_VERBS = frozenset(["echo", "printf", "print"])
_READERS = frozenset(["cat", "bat", "batcat", "less", "more", "head", "tail", "nl", "tac"])
_GREPS = frozenset(["grep", "egrep", "fgrep", "rg", "ag", "ack"])
# programs that write what they read on stdin back out, so a secret fed to them is printed
_STDIN_PRINTERS = frozenset(
    list(_READERS)
    + list(_GREPS)
    + ["tee", "sed", "awk", "gawk", "tr", "cut", "sort", "uniq", "base64", "xxd", "od", "hexdump",
       "rev", "fold", "fmt", "jq", "yq", "node", "perl", "ruby", "bash", "sh", "zsh", "dash", "ksh"]
)
_ENVFILE = re.compile(r"^\.env(\.[^/]+|rc)?$")
_ENV_SAFE = (".example", ".sample", ".template", ".dist")
# names a glob such as `.env*`, `.e?v` or `.*` could expand to
_ENV_CANDIDATES = (
    ".env", ".envrc", ".env.local", ".env.development", ".env.production", ".env.staging",
    ".env.test", ".env.prod", ".env.dev",
)
_GLOB_CHARS = "*?["


# words that end in KEY without being a key
_BENIGN_KEY = ("MONKEY", "DONKEY", "TURKEY", "HOCKEY", "JOCKEY", "WHISKEY")
# the last segment of a secret-shaped name
_SECRET_NOUNS = frozenset([
    "TOKEN", "SECRET", "PASSWORD", "PASSWD", "KEY", "AUTH", "CREDENTIALS", "CREDENTIAL", "PAT",
    "SECRETS", "PASSWORDS",
])
# one-word compounds (`GITHUBTOKEN`, `MASTERKEY`, `PGPASSWORD`): the segment ends in a noun
_COMPOUND_ENDS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIALS", "KEY")
_PLURAL_KEYS = frozenset(["APIKEYS", "ACCESSKEYS", "SECRETKEYS", "PRIVATEKEYS"])
# a name that ends in one of these describes a secret (where it lives, how long it lasts, how many
# there are) and is not the secret itself
_META_SUFFIXES = frozenset([
    "PATH", "FILE", "DIR", "LIMIT", "COUNT", "SIZE", "LEN", "TTL", "NAME", "ID", "URL", "HOST",
    "PORT", "TYPE", "ENV", "MAX", "MIN", "LENGTH", "FILENAME", "DIRECTORY", "TIMEOUT", "VERSION",
    "FORMAT", "EXPIRY", "PREFIX",
])
_META_PREFIXES = frozenset(["MAX", "MIN", "NUM"])
# trailing words that only say the variable holds the value (`SECRET_KEY_BASE`, `API_TOKEN_VALUE`)
_VALUE_WORDS = frozenset(["VALUE", "BASE", "DATA", "CONTENT", "CONTENTS", "STRING", "TEXT", "B64", "BASE64"])


def is_secret_name(name):
    """A variable name counts as a secret when it ends in a secret noun (TOKEN, SECRET, PASSWORD,
    API_KEY, ..., KEY as the last segment) and is not a description of one: not followed by a
    metadata suffix (`_PATH`, `_LIMIT`, `_COUNT`, `_TTL`, `_ID`, ...), not prefixed `MAX_`, `MIN_`
    or `NUM_`, and not a public key."""
    up = re.sub(r"[0-9]+$", "", name.upper())
    segs = [x for x in up.split("_") if x]
    if not segs:
        return False
    if len(segs) > 1 and segs[0] in _META_PREFIXES:
        return False
    if segs[-1] in _META_SUFFIXES:
        return False
    while len(segs) > 1 and segs[-1] in _VALUE_WORDS:
        segs.pop()
    last = segs[-1]
    if last in _META_SUFFIXES:
        return False
    if last in _PLURAL_KEYS:
        return True
    if last in _SECRET_NOUNS or any(last.endswith(e) for e in _COMPOUND_ENDS):
        if last.endswith("KEY"):
            if last in _BENIGN_KEY:
                return False
            if last == "PUBLICKEY" or (last == "KEY" and len(segs) > 1 and segs[-2] == "PUBLIC"):
                return False
        return True
    return False


_HERESTRING = re.compile(r"^\d*<<<$")


def _plain_args(words):
    """The segment's words without the text of a here-string."""
    out = []
    skip = False
    for x in words:
        if skip:
            skip = False
            continue
        if _HERESTRING.match(x.text):
            skip = True
            continue
        out.append(x)
    return out


def _secret_expansion(live):
    """True when `live` expands a secret-shaped variable to its value."""
    for m in _EXPAND.finditer(live):
        name = m.group(1) or m.group(3)
        rest = m.group(2) or ""
        if not is_secret_name(name):
            continue
        if m.group(1) and (rest.startswith("+") or rest.startswith(":+")):
            continue  # ${NAME:+word} yields the word, not the value
        return True
    return False


def _stdin_secret(seg):
    """True when a here-string or an expanding heredoc feeds this command a secret's value."""
    if _secret_expansion(seg.stdin):
        return True
    ws = seg.words
    for k, x in enumerate(ws):
        if _HERESTRING.match(x.text) and k + 1 < len(ws) and _secret_expansion(ws[k + 1].live):
            return True
    return False


def _is_envfile(arg):
    b = base(arg).lower()
    if b.startswith(".") and any(ch in b for ch in _GLOB_CHARS):
        # a glob: a name that starts like a secrets file (`.env*`, `.env?`), or any pattern
        # that would expand to one (`.e?v`, `.*`)
        if b.rstrip("*?").endswith(_ENV_SAFE):
            return False  # `.env.example*` and the like
        if b.startswith(".env"):
            return True
        return any(fnmatch.fnmatchcase(c, b) for c in _ENV_CANDIDATES)
    if not _ENVFILE.match(b):
        return False
    return not b.endswith(_ENV_SAFE)


def _env_has_command(args):
    i = 0
    n = len(args)
    while i < n:
        t = args[i].text
        if t == "--":
            i += 1
            continue
        if t.startswith("-") and len(t) > 1:
            i += 1
            if t in ("-u", "-C", "-S", "--unset", "--chdir") and i < n:
                i += 1
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\+?=", t):
            i += 1
            continue
        return True
    return False


def _quiet_grep(args):
    for w in args:
        t = w.text
        if t == "--":
            break
        if t.startswith("--"):
            if t[2:].split("=")[0] in ("quiet", "silent", "count", "files-with-matches", "files-without-match"):
                return True
        elif t.startswith("-") and len(t) > 1:
            if any(ch in "qclL" for ch in t[1:]):
                return True
    return False


def secret_print(ctx):
    why = "would print a secret into the conversation"
    how = (
        "Check that it's set without showing it: `[ -n \"$NAME\" ] && echo set`. "
        + override("secret-print")
    )
    for seg in ctx.segs:
        if not seg.words:
            continue
        w = unwrap(seg.words, stop_at=("env",))
        if not w:
            continue
        b = base(w[0].text)
        # the ${NAME:+..}${NAME:-..} idiom run as a command: the shell prints the value
        if _secret_expansion(w[0].live):
            return ("deny", message("secret-print", "expanding a secret-shaped variable as a command makes the shell echo its value", how))
        # a secret on stdin, handed to a program that writes its input back out
        if b in _STDIN_PRINTERS or b.startswith("python") or any(base(x.text) == "xargs" for x in seg.words):
            if _stdin_secret(seg) and not (b in _GREPS and _quiet_grep(w[1:])):
                return ("deny", message("secret-print", "`%s` would write a secret fed to it on stdin back out, into the conversation" % b, how))
        if b in _OUTPUT_VERBS:
            if any(_secret_expansion(x.live) for x in w[1:]):
                # a file or a clipboard is no exception: the next command reads it back
                return (
                    "deny",
                    message(
                        "secret-print",
                        "`%s` of a secret-shaped variable %s, wherever its output is sent" % (b, why),
                        how + " To hand it to another program, feed it on stdin (`prog <<< \"$NAME\"`).",
                    ),
                )
            continue
        if b == "printenv":
            names = [x.text for x in w[1:] if not x.text.startswith("-")]
            if not names or any(is_secret_name(x) for x in names):
                return ("deny", message("secret-print", "`printenv` with no name, or with a secret-shaped one, %s" % why, how))
            continue
        if b == "env":
            if not _env_has_command(w[1:]):
                return ("deny", message("secret-print", "`env` on its own lists every variable, secrets included", "Name the one you need (`printenv PATH`). " + override("secret-print")))
            continue
        if b in _READERS:
            for x in _plain_args(seg.words):
                if not x.text.startswith("-") and _is_envfile(x.text):
                    return ("deny", message("secret-print", "reading a .env file %s" % why, "Read the `.env.example` instead, or check one variable with `[ -n \"$NAME\" ] && echo set`. " + override("secret-print")))
            continue
        if b in _GREPS:
            files = [x for x in _plain_args(seg.words) if not x.text.startswith("-") and _is_envfile(x.text)]
            if files and not _quiet_grep(w[1:]):
                return ("deny", message("secret-print", "searching a .env file prints the matching line, value included", "Use `grep -q` or `grep -c` to test for presence. " + override("secret-print")))
    return None


# --------------------------------------------------------------------------------
# token-url
# --------------------------------------------------------------------------------

_TOKEN_PATTERNS = (
    ("a GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("a GitHub token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("a GitLab token", re.compile(r"glpat-[A-Za-z0-9_-]{20,}")),
    ("an API key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")),
    ("a Slack token", re.compile(r"xox[bpaors]-[A-Za-z0-9-]{10,}")),
    ("a cloud access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("a password in a URL", re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
)
_TOKEN_VERBS = frozenset(["git", "curl", "gh", "wget"])


def token_url(ctx):
    for seg in ctx.segs:
        w = unwrap(seg.words)
        if not w or base(w[0].text) not in _TOKEN_VERBS:
            continue
        blobs = []
        for x in seg.words:  # the whole segment: a VAR=token prefix lands in history too
            blobs.append(x.raw)
            blobs.append(x.text)
        blobs.append(" ".join(x.text for x in seg.words))
        for kind, rx in _TOKEN_PATTERNS:
            for blob in blobs:
                if rx.search(blob):
                    return (
                        "deny",
                        message(
                            "token-url",
                            "this command carries %s in its arguments, which lands in shell history, "
                            ".git/config and the transcript" % kind,
                            "Pass it by reference instead: a credential helper, `gh auth`, `curl -H "
                            "\"Authorization: Bearer $VAR\"` from an environment variable, or an SSH remote. "
                            + override("token-url"),
                        ),
                    )
    return None


# --------------------------------------------------------------------------------
# mac-timeout
# --------------------------------------------------------------------------------

def _which(name):
    dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    for d in dirs + list(FALLBACK_DIRS):
        p = os.path.join(d, name)
        try:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return True
        except Exception:
            continue
    return False


def mac_timeout(ctx):
    if sys.platform != "darwin":
        return None
    for seg in ctx.segs:
        w = unwrap(seg.words, stop_at=("timeout", "gtimeout"))
        if not w:
            continue
        b = base(w[0].text)
        if b not in ("timeout", "gtimeout"):
            continue
        if _which(b):
            continue
        if b == "timeout" and _which("gtimeout"):
            return (
                "deny",
                message(
                    "mac-timeout",
                    "`timeout` isn't installed on macOS, so this would fail before your command ran",
                    "Use `gtimeout` (it is installed) with the same arguments. " + override("mac-timeout"),
                ),
            )
        return (
            "deny",
            message(
                "mac-timeout",
                "`%s` isn't installed on macOS, so this would fail before your command ran "
                "(and a probe wrapped in it prints nothing)" % b,
                "Use the Bash tool's own timeout parameter; or install coreutils (`brew install coreutils`) "
                "and call `gtimeout`; or use `perl -e 'alarm shift; exec @ARGV' 5 cmd`. "
                + override("mac-timeout"),
            ),
        )
    return None


# --------------------------------------------------------------------------------
# masked-exit
# --------------------------------------------------------------------------------

_MASKERS = frozenset(["tail", "head", "grep", "egrep", "fgrep", "tee"])
_PY_MODS = frozenset(["pytest", "unittest", "ruff", "mypy", "pyright", "flake8", "pylint", "nose2"])
_DIRECT_CHECKS = frozenset(
    [
        "pytest", "py.test", "vitest", "jest", "tox", "nox", "ruff", "eslint", "tsc", "mypy",
        "pyright", "golangci-lint", "shellcheck", "flake8", "pylint", "mvn", "gradle", "gradlew",
        "xcodebuild", "rspec", "phpunit", "clippy-driver",
    ]
)
_SUBCHECKS = {
    "go": ("test", "build", "vet"),
    "cargo": ("test", "build", "clippy", "check", "nextest"),
    "swift": ("test", "build"),
    "deno": ("test", "lint", "check"),
    "dotnet": ("test", "build"),
}
_JS_PM = frozenset(["npm", "pnpm", "yarn", "bun"])
_SCRIPT_NAME = re.compile(r"test|build|lint|check")
_RUNNER_PAIRS = frozenset(
    [("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("pnpm", "exec"), ("pnpm", "dlx"), ("npm", "exec")]
)


def _nonopt(words):
    return [w.text for w in words if not w.text.startswith("-")]


def is_check_command(words):
    """Does this stage look like a test, build or lint command?"""
    w = unwrap(words)
    for _ in range(4):
        if not w:
            return False
        b = base(w[0].text)
        if b in ("npx", "bunx"):
            w = [x for x in w[1:] if x.text not in ("-y", "--yes")]
            continue
        if len(w) > 1 and (b, w[1].text) in _RUNNER_PAIRS:
            w = w[2:]
            continue
        break
    if not w:
        return False
    b = base(w[0].text)
    args = _nonopt(w[1:])
    if b in _DIRECT_CHECKS:
        return True
    if b.startswith("python") or b == "py":
        for i, x in enumerate(w):
            if x.text == "-m" and i + 1 < len(w):
                return w[i + 1].text in _PY_MODS
        return False
    if b in _SUBCHECKS:
        return bool(args) and args[0] in _SUBCHECKS[b]
    if b in _JS_PM:
        if not args:
            return False
        if args[0] in ("run", "run-script"):
            return len(args) > 1 and bool(_SCRIPT_NAME.search(args[1]))
        return bool(_SCRIPT_NAME.search(args[0]))
    if b in ("make", "just"):
        return bool(args) and bool(_SCRIPT_NAME.search(args[0]))
    return False


def _is_git_ship(seg):
    g = git_of(seg)
    return bool(g) and g[0] in ("commit", "push")


def masked_exit(ctx):
    if "pipefail" in ctx.cmd or "PIPESTATUS" in ctx.cmd:
        return None
    segs = [s for s in ctx.segs if not s.nested]
    n = len(segs)
    for i in range(n):
        end = segs[i]
        if end.op_before not in ("|", "|&") or end.op_after != "&&":
            continue
        start = i
        while start > 0 and segs[start].op_before in ("|", "|&"):
            start -= 1
        if not is_check_command(segs[start].words):
            continue
        if not any(verb(s) in _MASKERS for s in segs[start + 1:i + 1]):
            continue
        k = i + 1
        while k < n:
            if _is_git_ship(segs[k]):
                first = verb(segs[start]) or "the check"
                return (
                    "warn",
                    message(
                        "masked-exit",
                        "`%s` is piped into `%s` and then `&& git commit/push`: the pipe replaces the check's "
                        "exit code with the last command's, so the commit or push runs even when the check fails"
                        % (first, verb(segs[i])),
                        "Run the check on its own and read its result first, or add `set -o pipefail`. "
                        + override("masked-exit"),
                    ),
                )
            if segs[k].op_after != "&&":
                break
            k += 1
    return None


GUARDS = (
    ("staging", staging),
    ("pushed-rewrite", pushed_rewrite),
    ("secret-print", secret_print),
    ("token-url", token_url),
    ("mac-timeout", mac_timeout),
    ("masked-exit", masked_exit),
)
