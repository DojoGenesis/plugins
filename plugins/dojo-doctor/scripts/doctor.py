#!/usr/bin/env python3
"""dojo-doctor: a read-only check of the hooks and settings that fail or cost you silently.

Six sections, each reported as ok / problem / could not check:
  interpreters  every hook command: is the program there, under a bare PATH and under yours?
  failures      hook errors recorded in recent transcripts
  injection     context bytes that hooks inject, where the transcript recorded it
  weight        always-on description weight per plugin (an estimate: characters / 4)
  flag          are function hooks (mods) on or off, and which sources say so
  python        is python3 there, and is it new enough?

It never runs a hook command and never writes anything. It reads settings files,
plugin hook files and transcript files, and prints a report.

One module, standard library only, Python 3.9 compatible.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import calendar
import glob
import json
import os
import re
import shlex
import signal
import stat
import subprocess
import time
from collections import Counter

VERSION = "0.1.0"
TESTED_WITH = "2.1.286"
MINIMAL_PATH = "/usr/bin:/bin"
SECTION_IDS = ["interpreters", "failures", "injection", "weight", "flag", "python"]
SECTION_TITLES = {
    "interpreters": "interpreters",
    "failures": "hook failures",
    "injection": "injection weight",
    "weight": "always-on weight",
    "flag": "function hooks flag",
    "python": "python3",
}
FLAG_ENV = "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"
FLAG_CACHE_KEY = "tengu_plugin_hooks_modules"
ENTRY_CAP = 1536  # skillListingMaxDescChars default, as of Claude Code 2.1.286
DEFAULT_WINDOW_TOKENS = 200000
DEFAULT_LISTING_FRACTION = 0.01
FALLBACK_DESC_CAP = 100
DEFAULT_INJECT_BYTES = 10000
ROW_LIMIT = 10
EXCERPT_LIMIT = 120
MAX_JSON_BYTES = 64 * 1024 * 1024
LINE_CAP = 1 << 20  # longest transcript line that is read into memory
IS_MAC = hasattr(os, "uname") and os.uname().sysname == "Darwin"

ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
VAR_LEFT_RE = re.compile(r"\$[A-Za-z_{]")
ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]"
)
CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
TS_RE = re.compile(
    r"^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|[+-]\d\d:?\d\d)?"
)

REDACTIONS = [
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/\s:@]+:[^/\s@]*@"), r"\1<redacted>@"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=\-]+"), r"\1 <redacted>"),
    (re.compile(r"(?i)(authorization\s*:\s*basic)\s+\S+"), r"\1 <redacted>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{6,}"), "<redacted>"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{6,}"), "<redacted>"),
    (re.compile(r"\bglpat-[A-Za-z0-9_\-]{6,}"), "<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"), "<redacted>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{6,}"), "<redacted>"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), "<redacted>"),
    (
        re.compile(r"(?i)(--?[a-z][a-z\-]*(?:token|key|secret|password|passwd)[a-z\-]*)(=|\s+)\S+"),
        r"\1\2<redacted>",
    ),
    (
        re.compile(r"(?i)\b([A-Za-z0-9_.\-]*(?:token|key|secret|password|passwd)[A-Za-z0-9_.\-]*)=\S+"),
        r"\1=<redacted>",
    ),
    (re.compile(r"(^|\s)([A-Za-z_][A-Za-z0-9_]*)=\S+"), r"\1\2=<redacted>"),
]

KEYWORDS = set(
    "if then else elif fi for while until do done case esac in select function { } ! [[ ]] coproc".split()
)
BUILTINS = set(
    "cd export set unset echo printf test [ true false exit return source . read eval trap umask "
    "ulimit wait shift alias unalias type pwd : local declare typeset let getopts hash jobs fg bg "
    "kill break continue".split()
)
WRAPPERS = set("env exec command nohup time nice sudo timeout gtimeout".split())
UNRESOLVED_OK_WRAPPERS = set(["exec", "command", "time"])  # shell words, nothing to look up
SHELL_NAMES = set("sh bash zsh dash ksh".split())
PYTHON_RE = re.compile(r"^python(\d+(\.\d+)*)?$")
NODE_NAMES = set("node nodejs deno bun tsx ts-node".split())


class ArgError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)

    def exit(self, status=0, message=None):
        raise ArgError(message or "exit")


# --------------------------------------------------------------------------- text hygiene


class Ctx(object):
    """Everything a section needs. Built once in main(); never mutated by sections."""


def clean(ctx, text, limit=EXCERPT_LIMIT):
    """Strip escapes and control characters, redact secrets, shorten the home path, truncate."""
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    text = ANSI_RE.sub("", text)
    text = CTRL_RE.sub(" ", text)
    for rx, repl in REDACTIONS:
        text = rx.sub(repl, text)
    home = getattr(ctx, "home", "") or ""
    if len(home) > 1:
        text = text.replace(home, "~")
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text


def tilde(ctx, path):
    home = getattr(ctx, "home", "") or ""
    if len(home) > 1 and isinstance(path, str) and (path == home or path.startswith(home + os.sep)):
        return "~" + path[len(home):]
    return path


def est_tokens(nbytes):
    return int(nbytes / 4.0 + 0.5)


def fmt_int(n):
    return "{:,}".format(int(n))


def fmt_day(epoch):
    return time.strftime("%Y-%m-%d", time.gmtime(epoch))


# --------------------------------------------------------------------------- report model


class Section(object):
    def __init__(self, sid):
        self.id = sid
        self.items = []  # dicts: level problem|could|note, id, text, fix
        self.lines = []  # preformatted text lines
        self.data = {}
        self.summary = ""
        self.forced = None

    def add(self, level, fid, text, fix=None):
        self.items.append({"level": level, "id": fid, "text": text, "fix": fix})

    def count(self, level):
        return len([i for i in self.items if i["level"] == level])

    @property
    def status(self):
        if self.forced:
            return self.forced
        if self.count("problem"):
            return "problem"
        if self.count("could"):
            return "could_not_check"
        return "ok"


# --------------------------------------------------------------------------- file helpers


def open_regular(path):
    """Open `path` for binary reading, but only when it is a regular file.

    A FIFO would block the open or the read forever and a device (such as /dev/zero) never ends,
    so the open is non-blocking and the type is checked on the open descriptor itself (no gap
    between a stat and the open). Anything else raises OSError.
    """
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOCTTY", 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file: %r" % (path,))
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def read_bounded(path, limit):
    """Return up to `limit` bytes of a regular file, or None when the file is not a regular file
    or cannot be read. Never reads more than limit + 1 bytes."""
    try:
        with open_regular(path) as fh:
            return fh.read(limit)
    except (OSError, ValueError):
        return None


def read_json(path):
    """Return (data, err). err is None, 'missing', 'unreadable' or 'invalid'.

    A path that is not a regular file (FIFO, device, folder) or is larger than MAX_JSON_BYTES is
    'unreadable'. The type is checked on the open descriptor and the read is size-bounded."""
    try:
        if not os.path.exists(path):
            return None, "missing"
        with open_regular(path) as fh:
            raw = fh.read(MAX_JSON_BYTES + 1)
    except (OSError, ValueError):
        return None, "unreadable"
    if len(raw) > MAX_JSON_BYTES:
        return None, "unreadable"
    try:
        return json.loads(raw.decode("utf-8", "replace")), None
    except (ValueError, RecursionError, MemoryError):  # deeply nested JSON is "invalid", not a crash
        return None, "invalid"


def which(name, path_string):
    """Hand-written lookup: first executable regular file named `name` on `path_string`."""
    if not name or "/" in name:
        return None
    for d in (path_string or "").split(":"):
        if not d:
            continue
        p = os.path.join(d, name)
        try:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        except OSError:
            continue
    return None


def real(path):
    try:
        return os.path.realpath(path)
    except OSError:
        return path


def parse_ts(value):
    """ISO timestamp -> epoch seconds, or None. Handles Z, offsets and fractions on Python 3.9."""
    if not isinstance(value, str):
        return None
    m = TS_RE.match(value)
    if not m:
        return None
    try:
        y, mo, d, h, mi, s = [int(x) for x in m.groups()[:6]]
        epoch = calendar.timegm((y, mo, d, h, mi, s))
    except (ValueError, OverflowError):
        return None
    tz = m.group(7)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        epoch -= sign * (int(digits[:2]) * 3600 + int(digits[2:4]) * 60)
    return epoch


def to_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.match(r"^\s*-?\d+\s*$", value):
        return int(value)
    return None


# --------------------------------------------------------------------------- configuration


class Config(object):
    """Settings, enabled plugins and the hook commands they define."""

    def __init__(self):
        self.settings = {}  # scope -> dict
        self.scope_env = {}  # scope -> {str: str}
        self.env = {}  # merged settings env
        self.errors = []  # (label, err)
        self.files_ok = 0
        self.plugins = []  # dicts
        self.records = []  # hook command records
        self.issues = []  # (level, id, text, fix) found while loading
        self.invisible_note = True
        self.config_dir_exists = False


def load_config(ctx):
    cfg = Config()
    cfg.config_dir_exists = os.path.isdir(ctx.config_dir)
    scopes = [
        ("user", os.path.join(ctx.config_dir, "settings.json")),
        ("project", os.path.join(ctx.project, ".claude", "settings.json")),
        ("local", os.path.join(ctx.project, ".claude", "settings.local.json")),
    ]
    for scope, path in scopes:
        data, err = read_json(path)
        label = "%s settings" % scope
        if err == "missing":
            cfg.scope_env[scope] = {}
            continue
        if err or not isinstance(data, dict):
            cfg.errors.append((label, err or "invalid"))
            cfg.scope_env[scope] = {}
            continue
        cfg.files_ok += 1
        cfg.settings[scope] = data
        env = data.get("env")
        scoped = {}
        if isinstance(env, dict):
            for k, v in env.items():
                if isinstance(k, str) and isinstance(v, (str, int, float, bool)):
                    scoped[k] = str(v)
        cfg.scope_env[scope] = scoped
    for scope in ("user", "project", "local"):
        cfg.env.update(cfg.scope_env.get(scope, {}))

    resolve_plugins(ctx, cfg)

    # settings hooks
    for scope in ("user", "project", "local"):
        data = cfg.settings.get(scope)
        if not data:
            continue
        hooks = data.get("hooks")
        if hooks is None:
            continue
        path = {
            "user": os.path.join(ctx.config_dir, "settings.json"),
            "project": os.path.join(ctx.project, ".claude", "settings.json"),
            "local": os.path.join(ctx.project, ".claude", "settings.local.json"),
        }[scope]
        owner = {"kind": "settings", "name": "%s settings" % scope, "root": None, "file": path}
        if not isinstance(hooks, dict):
            cfg.errors.append(("%s settings hooks" % scope, "invalid"))
            continue
        collect_event_map(hooks, owner, cfg.records)
    return cfg


def collect_event_map(emap, owner, out):
    for event, groups in emap.items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            if not isinstance(g, dict):
                continue
            hs = g.get("hooks")
            if not isinstance(hs, list):
                continue
            for h in hs:
                if not isinstance(h, dict):
                    continue
                if h.get("type", "command") != "command":
                    continue  # prompt, agent, http, mcp_tool hooks have no command to check
                cmd = h.get("command")
                if not isinstance(cmd, str) or not cmd.strip():
                    continue
                args = h.get("args")
                if not (isinstance(args, list) and all(isinstance(a, str) for a in args)):
                    args = None
                status = h.get("statusMessage")
                out.append(
                    {
                        "event": event if isinstance(event, str) else "?",
                        "command": cmd,
                        "args": args,
                        "shell": h.get("shell") if isinstance(h.get("shell"), str) else None,
                        "status": status if isinstance(status, str) and status else None,
                        "owner": owner["name"],
                        "kind": owner["kind"],
                        "root": owner["root"],
                        "file": owner["file"],
                    }
                )


def event_map_of(obj):
    """A hooks file holds {"hooks": {...}}; accept a bare event map too."""
    if not isinstance(obj, dict):
        return None
    hooks = obj.get("hooks")
    if isinstance(hooks, dict):
        return hooks
    if obj and all(isinstance(v, list) for v in obj.values()) and "modules" not in obj:
        return obj
    return None


def resolve_plugins(ctx, cfg):
    enabled = {}
    for scope in ("user", "project", "local"):
        data = cfg.settings.get(scope) or {}
        ep = data.get("enabledPlugins")
        if isinstance(ep, dict):
            for key, val in ep.items():
                if isinstance(key, str):
                    enabled[key] = (val, scope)
    installed, err = read_json(os.path.join(ctx.config_dir, "plugins", "installed_plugins.json"))
    inst_map = {}
    if err == "missing":
        if any(v[0] is True for v in enabled.values()):
            cfg.errors.append(("installed_plugins.json", "missing"))
    elif err or not isinstance(installed, dict) or not isinstance(installed.get("plugins"), dict):
        cfg.errors.append(("installed_plugins.json", err or "invalid"))
    else:
        inst_map = installed["plugins"]

    project_real = real(ctx.project)
    rank = {"local": 3, "project": 2, "user": 1, "managed": 0}
    seen_roots = set()
    for key in sorted(enabled):
        val, scope = enabled[key]
        if val is not True:
            continue
        name = key.split("@")[0]
        entries = inst_map.get(key)
        best = None
        if isinstance(entries, list):
            for e in entries:
                if not isinstance(e, dict):
                    continue
                escope = e.get("scope", "user")
                if escope in ("project", "local"):
                    pp = e.get("projectPath")
                    if not (isinstance(pp, str) and real(pp) == project_real):
                        continue
                if best is None or rank.get(escope, 0) >= rank.get(best.get("scope", "user"), 0):
                    best = e
        if best is None:
            if inst_map or not any(l == "installed_plugins.json" for l, _ in cfg.errors):
                cfg.issues.append(
                    (
                        "note",
                        "plugin-not-installed",
                        "%s is enabled in %s settings but has no install record for this project; not checked"
                        % (clean(ctx, name, 60), scope),
                        None,
                    )
                )
            continue
        ip = best.get("installPath")
        if not isinstance(ip, str) or not os.path.isdir(os.path.expanduser(ip) if ip.startswith("~") else ip):
            cfg.issues.append(
                (
                    "problem",
                    "plugin-path-missing",
                    "%s is enabled but its install folder is missing (%s); it will not load"
                    % (clean(ctx, name, 60), clean(ctx, tilde(ctx, ip) if isinstance(ip, str) else "no path", 80)),
                    "reinstall it with /plugin install, or turn it off in enabledPlugins",
                )
            )
            continue
        root = ip
        if real(root) in seen_roots:
            continue
        seen_roots.add(real(root))
        add_plugin(ctx, cfg, name, root, "installed")

    # claude.ai synced plugins
    for d in sorted(glob.glob(os.path.join(ctx.config_dir, "plugins", "synced", "*", "*"))):
        if os.path.isdir(d) and real(d) not in seen_roots:
            seen_roots.add(real(d))
            parts = os.path.relpath(d, os.path.join(ctx.config_dir, "plugins", "synced")).split(os.sep)
            short = "/".join(x[:8] if len(x) > 24 else x for x in parts)
            add_plugin(ctx, cfg, "synced " + short, d, "synced")

    # CLAUDE_CODE_PLUGIN_DIRS
    pd = ctx.environ.get("CLAUDE_CODE_PLUGIN_DIRS")
    if pd:
        for d in pd.split(os.pathsep):
            d = d.strip()
            if d and os.path.isdir(d) and real(d) not in seen_roots:
                seen_roots.add(real(d))
                add_plugin(ctx, cfg, "plugin dir " + os.path.basename(d.rstrip("/")), d, "plugin dirs (env)")


def add_plugin(ctx, cfg, name, root, source):
    plugin = {
        "name": name,
        "root": root,
        "source": source,
        "modules": [],  # (spec, hooks_file)
        "hooks_files": [],
        "register": [],
    }
    owner = {"kind": "plugin", "name": name, "root": root, "file": None}
    seen_files = set()

    def load_hooks_file(path, label):
        rp = real(path)
        if rp in seen_files:
            return
        seen_files.add(rp)
        data, err = read_json(path)
        if err == "missing":
            return
        if err or not isinstance(data, dict):
            cfg.errors.append(("%s %s" % (name, label), err or "invalid"))
            return
        plugin["hooks_files"].append(path)
        o = dict(owner)
        o["file"] = path
        emap = event_map_of(data)
        if emap is not None:
            collect_event_map(emap, o, cfg.records)
        mods = data.get("modules")
        if isinstance(mods, list):
            for m in mods:
                if isinstance(m, str):
                    plugin["modules"].append((m, path))

    load_hooks_file(os.path.join(root, "hooks", "hooks.json"), "hooks/hooks.json")

    manifest_path = os.path.join(root, ".claude-plugin", "plugin.json")
    manifest, err = read_json(manifest_path)
    if err and err != "missing":
        cfg.errors.append(("%s plugin.json" % name, err))
    elif isinstance(manifest, dict) and "hooks" in manifest:
        spec = manifest["hooks"]
        specs = spec if isinstance(spec, list) else [spec]
        for s in specs:
            if isinstance(s, str):
                target = os.path.normpath(os.path.join(root, s))
                inside = real(target) == real(root) or real(target).startswith(real(root) + os.sep)
                if not inside:
                    cfg.issues.append(
                        (
                            "problem",
                            "interp-manifest",
                            "%s: plugin.json hooks path %s points outside the plugin folder; it will not load"
                            % (clean(ctx, name, 60), clean(ctx, s, 80)),
                            "point hooks at a file inside the plugin, such as ./hooks/hooks.json",
                        )
                    )
                elif not os.path.isfile(target):
                    cfg.issues.append(
                        (
                            "problem",
                            "interp-manifest",
                            "%s: plugin.json hooks path %s does not exist; it will not load"
                            % (clean(ctx, name, 60), clean(ctx, s, 80)),
                            "create the file or fix the path in plugin.json",
                        )
                    )
                else:
                    load_hooks_file(target, s)
            elif isinstance(s, dict):
                o = dict(owner)
                o["file"] = manifest_path
                emap = event_map_of(s)
                if emap is not None:
                    collect_event_map(emap, o, cfg.records)
                mods = s.get("modules")
                if isinstance(mods, list):
                    for m in mods:
                        if isinstance(m, str):
                            plugin["modules"].append((m, manifest_path))
    for cand in (os.path.join(root, "hooks", "register.ts"), os.path.join(root, "register.ts")):
        if os.path.isfile(cand):
            plugin["register"].append(cand)
    cfg.plugins.append(plugin)


# --------------------------------------------------------------------------- command analysis


class Analyzer(object):
    """Judges the first token of each simple command. Never runs anything."""

    def __init__(self, ctx, cfg):
        self.ctx = ctx
        self.cfg = cfg

    # -- public
    def analyze(self, rec):
        """Return (findings, skipped_flag). findings: dicts id/level/reason/fix."""
        self.rec = rec
        self.findings = []
        self.skipped = False
        self.judged = False
        shell = (rec.get("shell") or "").lower()
        if shell in ("powershell", "pwsh"):
            return [], True, False
        try:
            if rec.get("args") is not None:
                self.judge_argv([rec["command"]] + list(rec["args"]), 0)
            else:
                self.judge_string(rec["command"], 0)
        except Exception:
            self.skipped = True
        return self.findings, self.skipped, self.judged

    # -- helpers
    def find(self, fid, level, reason, fix=None):
        self.findings.append({"id": fid, "level": level, "reason": reason, "fix": fix})

    def expand(self, s):
        """Expand the variables a hook command can rely on. Returns None when it cannot."""
        rec = self.rec
        ctx = self.ctx
        env = self.cfg.env
        out = s
        if out.startswith("~/") or out == "~":
            out = ctx.home + out[1:]

        def sub(m):
            name = m.group(1) or m.group(2)
            if name == "CLAUDE_PLUGIN_ROOT":
                return rec.get("root") or m.group(0)
            if name == "CLAUDE_PROJECT_DIR":
                return ctx.project
            if name == "HOME":
                return ctx.home
            if name in env:
                return env[name]
            return m.group(0)

        out = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", sub, out)
        if VAR_LEFT_RE.search(out):
            return None
        return out

    def show_path(self, p):
        root = self.rec.get("root")
        if root and (p == root or p.startswith(root + os.sep)):
            shown = "${CLAUDE_PLUGIN_ROOT}" + p[len(root):]
        else:
            shown = tilde(self.ctx, p)
        shown = clean(self.ctx, shown, 400)
        if len(shown) > 90:
            shown = "\u2026" + shown[-89:]
        return shown

    def shebang_check(self, path, display):
        head = read_bounded(path, 128)
        if head is None or not head.startswith(b"#!"):
            return
        line = head[2:].split(b"\n", 1)[0].decode("utf-8", "replace").strip()
        parts = line.split()
        if not parts:
            return
        prog, rest = parts[0], parts[1:]
        if os.path.basename(prog) == "env":
            j = 0
            while j < len(rest) and (rest[j].startswith("-") or ASSIGN_RE.match(rest[j])):
                j += 1
            if j >= len(rest):
                return
            name = rest[j]
            if name == "python":
                self.find(
                    "interp-bare-python",
                    "problem",
                    "script %s starts with a shebang that asks for bare python" % display,
                    "change the first line to #!/usr/bin/env python3",
                )
            else:
                self.bare_program(name, "shebang of %s" % display)
        else:
            if os.path.basename(prog) == "python":
                self.find(
                    "interp-bare-python",
                    "problem",
                    "script %s starts with a shebang that asks for bare python" % display,
                    "change the first line to #!/usr/bin/env python3",
                )
            elif not os.path.exists(prog):
                self.find(
                    "interp-missing",
                    "problem",
                    "script %s names an interpreter that is missing: %s" % (display, clean(self.ctx, prog, 60)),
                    "fix the shebang line, or call the script through an interpreter that exists",
                )

    def bare_program(self, name, where):
        """A program named without a path: resolve under the bare PATH and under the current PATH."""
        ctx = self.ctx
        if name == "python":
            self.find(
                "interp-bare-python",
                "problem",
                "bare `python` in %s; stock macOS has no `python`, and version-manager shims only work in your shell" % where,
                "use python3 (python3 hooks/nudge.py)",
            )
            return
        low = which(name, ctx.minimal_path)
        cur = which(name, ctx.path)
        if low:
            return
        if cur:
            self.find(
                "interp-needs-path",
                "note",
                "`%s` in %s is found only on your shell PATH (%s); it fails if Claude Code is launched from the Dock or a scheduler"
                % (clean(ctx, name, 40), where, clean(ctx, tilde(ctx, cur), 60)),
                "give the full path in the hook command, or start Claude Code from a terminal",
            )
            return
        self.find(
            "interp-missing",
            "problem",
            "`%s` in %s is not on %s or on your current PATH" % (clean(ctx, name, 40), where, MINIMAL_PATH),
            "install it, or give the full path in the hook command",
        )

    def path_program(self, prog, where, as_script):
        """A program or script given as a path. as_script=True: passed to an interpreter (no exec bit needed)."""
        ctx = self.ctx
        p = os.path.expanduser(prog) if prog.startswith("~") else prog
        relative = not os.path.isabs(p)
        if relative:
            p = os.path.normpath(os.path.join(ctx.project, p))
        shown = self.show_path(p)
        if not os.path.exists(p):
            if relative:
                self.skipped = True  # depends on the working directory the hook runs in
                return
            self.find(
                "interp-missing-script",
                "problem",
                "script is missing: %s" % shown,
                "restore the file or fix the path in the hook command",
            )
            return
        if os.path.isdir(p):
            self.find("interp-missing-script", "problem", "%s is a folder, not a program" % shown, "point at the script inside it")
            return
        if not os.path.isfile(p):
            self.find(
                "interp-missing-script",
                "problem",
                "%s is not a regular file (a pipe or device), so it cannot run as a hook script" % shown,
                "replace it with the script itself",
            )
            return
        self.judged = True
        if as_script:
            return
        if not os.access(p, os.X_OK):
            self.find(
                "interp-not-exec",
                "problem",
                "%s is not executable; the shell will answer 126 Permission denied" % shown,
                "chmod +x that file, or run it through bash or python3 explicitly",
            )
            return
        self.shebang_check(p, shown)

    # -- parsing
    def judge_string(self, text, depth):
        if "$(" in text or "`" in text:
            self.skipped = True  # command substitution: the shell decides the program, so do not guess
            return
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        try:
            toks = list(lex)
        except ValueError:
            self.skipped = True
            return
        segments = []
        cur = []
        i = 0
        while i < len(toks):
            t = toks[i]
            if t and all(c in "();<>|&" for c in t):
                if "<" in t or ">" in t:
                    if cur and cur[-1].isdigit():
                        cur.pop()  # a file descriptor number such as the 2 in 2>/dev/null
                    i += 2 if i + 1 < len(toks) else 1  # redirect: skip its target
                    continue
                if cur:
                    segments.append(cur)
                cur = []
            else:
                cur.append(t)
            i += 1
        if cur:
            segments.append(cur)
        for seg in segments:
            self.judge_argv(seg, depth)

    def strip_prefix(self, toks):
        changed = True
        while changed and toks:
            changed = False
            while toks and ASSIGN_RE.match(toks[0]):
                toks = toks[1:]
                changed = True
            while toks and toks[0] in KEYWORDS:
                toks = toks[1:]
                changed = True
        return toks

    def unwrap(self, toks):
        """toks[0] is a wrapper. Return (rest_tokens or None)."""
        w = os.path.basename(toks[0])
        n = len(toks)
        i = 1
        if w == "env":
            while i < n and (toks[i].startswith("-") or ASSIGN_RE.match(toks[i])):
                i += 2 if toks[i] in ("-u", "--unset", "-C", "--chdir", "-S") else 1
        elif w == "exec":
            while i < n and toks[i].startswith("-"):
                i += 2 if toks[i] == "-a" else 1
        elif w == "command":
            while i < n and toks[i].startswith("-"):
                if toks[i] in ("-v", "-V"):
                    return None
                i += 1
        elif w == "time":
            while i < n and toks[i] == "-p":
                i += 1
        elif w == "nice":
            if i < n and toks[i] == "-n":
                i += 2
            elif i < n and re.match(r"^-\d+$", toks[i]):
                i += 1
        elif w == "sudo":
            while i < n and toks[i].startswith("-") and toks[i] != "--":
                i += 2 if toks[i] in ("-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U") else 1
            while i < n and ASSIGN_RE.match(toks[i]):
                i += 1
        elif w in ("timeout", "gtimeout"):
            while i < n and toks[i].startswith("-"):
                i += 2 if toks[i] in ("-k", "-s", "--kill-after", "--signal") else 1
            i += 1  # the duration
        return toks[i:]

    def judge_argv(self, toks, depth):
        toks = self.strip_prefix(list(toks))
        if not toks:
            return
        guard = 0
        while toks and os.path.basename(toks[0]) in WRAPPERS and guard < 6:
            guard += 1
            wname = os.path.basename(toks[0])
            if wname not in UNRESOLVED_OK_WRAPPERS:
                self.check_program(toks[0])
            rest = self.unwrap(toks)
            if rest is None:
                return
            toks = self.strip_prefix(rest)
        if not toks:
            return
        prog = toks[0]
        args = toks[1:]
        if prog in BUILTINS or prog in KEYWORDS:
            return
        if not self.check_program(prog):
            return
        self.check_script_args(os.path.basename(prog), args, depth)

    def check_program(self, prog):
        """Judge one program token. Returns True when its arguments are worth looking at."""
        expanded = self.expand(prog)
        if expanded is None or expanded.startswith("$") or "`" in expanded:
            self.skipped = True
            return False
        if expanded in BUILTINS or expanded in KEYWORDS:
            return False
        if "/" in expanded or expanded.startswith("~"):
            self.path_program(expanded, "hook command", False)
        else:
            self.judged = True
            self.bare_program(expanded, "hook command")
        return True

    def check_script_args(self, bn, args, depth):
        family = None
        if bn in SHELL_NAMES:
            family = "shell"
        elif PYTHON_RE.match(bn):
            family = "python"
        elif bn in NODE_NAMES:
            family = "node"
        if not family:
            return
        script = None
        i = 0
        n = len(args)
        while i < n:
            a = args[i]
            if family == "shell":
                if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
                    if i + 1 < n and depth < 1:
                        self.judge_string(args[i + 1], depth + 1)
                    return
                if a in ("-o", "+o", "--rcfile", "--init-file"):
                    i += 2
                    continue
                if a.startswith("-") or a.startswith("+"):
                    i += 1
                    continue
            elif family == "python":
                if a in ("-m", "-c"):
                    return
                if a in ("-W", "-X"):
                    i += 2
                    continue
                if a.startswith("-") and a != "-":
                    i += 1
                    continue
            else:
                if a in ("-e", "-p", "--eval", "--print"):
                    return
                if a in ("-r", "--require", "--import", "--loader", "--experimental-loader"):
                    i += 2
                    continue
                if a.startswith("-") and a != "-":
                    i += 1
                    continue
            script = a
            break
        if script is None or script == "-":
            return
        expanded = self.expand(script)
        if expanded is None or expanded.startswith("$") or "`" in expanded:
            self.skipped = True
            return
        self.path_program(expanded, "hook command", True)


def run_interpreters(ctx, cfg):
    sec = Section("interpreters")
    analyzer = Analyzer(ctx, cfg)
    grouped = {}
    order = []
    checked = 0
    judged = 0
    skipped = 0
    for rec in cfg.records:
        findings, skip, did = analyzer.analyze(rec)
        checked += 1
        if skip:
            skipped += 1
        if did:
            judged += 1
        cmd = clean(ctx, rec["command"], 100)
        for f in findings:
            key = (f["id"], f["level"], rec["owner"], f["reason"])
            if key not in grouped:
                grouped[key] = {"f": f, "events": set(), "owner": rec["owner"], "cmds": []}
                order.append(key)
            grouped[key]["events"].add(rec["event"])
            if cmd not in grouped[key]["cmds"]:
                grouped[key]["cmds"].append(cmd)
    for level, fid, text, fix in cfg.issues:
        sec.add(level, fid, text, fix)
    for key in order:
        g = grouped[key]
        f = g["f"]
        events = ",".join(sorted(clean(ctx, e, 24) for e in g["events"]))
        more = " (+%d more hook commands)" % (len(g["cmds"]) - 1) if len(g["cmds"]) > 1 else ""
        text = "%s [%s]: %s -- command: %s%s" % (clean(ctx, g["owner"], 60), events, f["reason"], g["cmds"][0], more)
        sec.add(f["level"], f["id"], text, f["fix"])
    for label, err in cfg.errors:
        sec.add("could", "could-not-read", "could not read %s (%s)" % (clean(ctx, label, 80), err), None)
    if skipped:
        sec.add(
            "could",
            "could-not-check-commands",
            "could not check %d of %d hook commands (unresolved variable, unbalanced quote or non-POSIX shell)"
            % (skipped, checked),
            None,
        )
    if not cfg.config_dir_exists:
        sec.add("could", "no-config-dir", "no config folder at %s" % clean(ctx, tilde(ctx, ctx.config_dir), 80), None)
    sec.data = {"hook_commands": checked, "judged": judged, "could_not_check": skipped, "plugins_scanned": len(cfg.plugins)}
    sec.summary = "%d hook commands (plugins scanned: %d, settings files read: %d); %d judged, %d could not be checked" % (
        checked,
        len(cfg.plugins),
        len(cfg.settings),
        judged,
        skipped,
    )
    if not sec.count("problem"):
        if checked == 0 and sec.count("could"):
            sec.forced = "could_not_check"
        elif checked > 0 and judged == 0 and skipped:
            sec.forced = "could_not_check"
        elif cfg.errors:
            sec.forced = "could_not_check"
        elif skipped:
            sec.forced = "could_not_check"  # the header must match the "could not check" count in the summary
        else:
            sec.forced = "ok"
    sec.lines.append(
        "Sources not visible to this check: plugins loaded with --plugin-dir and managed (organisation) plugins or settings."
    )
    return sec


# --------------------------------------------------------------------------- transcripts (failures + injection)


class Scan(object):
    def __init__(self):
        self.missing = False
        self.files_window = 0
        self.files_scanned = 0
        self.bytes_scanned = 0
        self.stopped = None
        self.records = 0
        self.bad_ts = 0
        self.blocking = Counter()
        self.fail = {}  # label -> group
        self.timeouts = {}
        self.async_fail = {}  # event -> group
        self.event_inject = {}  # event -> group
        self.hook_inject = {}  # (event,label) -> group


def new_group():
    return {
        "count": 0,
        "sessions": set(),
        "last": 0,
        "exits": Counter(),
        "causes": Counter(),
        "events": Counter(),
        "stderr": None,
    }


def classify(exit_code, stderr):
    s = stderr or ""
    if exit_code == 126 or "Permission denied" in s:
        return "not executable"
    if "command not found" in s:
        return "interpreter missing"
    if "can't open file" in s or "No such file or directory" in s:
        return "missing script"
    if exit_code == 127:
        return "interpreter missing"
    return "hook's own error"


def first_line(stderr):
    if not isinstance(stderr, str):
        return None
    s = stderr.replace("Failed with non-blocking status code: ", "", 1)
    for ln in s.splitlines():
        if ln.strip():
            return ln.strip()
    return None


def event_of(att):
    ev = att.get("hookEvent")
    if not (isinstance(ev, str) and ev):
        hn = att.get("hookName")
        ev = hn.split(":")[0] if isinstance(hn, str) and hn else ""
    if not re.match(r"^[A-Za-z]{2,30}$", ev or ""):
        return "(other)"
    return ev


def injection_text(stdout, event):
    if not isinstance(stdout, str):
        return None
    s = stdout.strip()
    if not s:
        return None
    if s[0] in "{[":
        try:
            j = json.loads(s)
        except (ValueError, RecursionError, MemoryError):
            return None
        if isinstance(j, dict):
            hso = j.get("hookSpecificOutput")
            if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
                return hso["additionalContext"]
        return None
    if event in ("SessionStart", "UserPromptSubmit"):
        return stdout
    return None


def add_inject(table, key, session, nbytes):
    g = table.get(key)
    if g is None:
        g = {"runs": 0, "sessions": {}, "max": 0, "total": 0}
        table[key] = g
    g["runs"] += 1
    g["total"] += nbytes
    g["max"] = max(g["max"], nbytes)
    g["sessions"][session] = g["sessions"].get(session, 0) + nbytes


def scan_transcripts(ctx):
    scan = Scan()
    root = os.path.join(ctx.config_dir, "projects")
    if not os.path.isdir(root):
        scan.missing = True
        return scan
    cutoff = ctx.now - ctx.days * 86400.0
    found = []
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - base_depth >= 4:
            dirnames[:] = []
        for fn in filenames:
            if not fn.endswith(".jsonl"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue  # a FIFO or device would block the read
            if st.st_mtime >= cutoff:
                found.append((st.st_mtime, st.st_size, p))
    found.sort(reverse=True)
    scan.files_window = len(found)
    seen = set()
    max_bytes = int(ctx.max_mb * 1024 * 1024)
    for mtime, size, path in found:
        if time.monotonic() > ctx.deadline:
            scan.stopped = "time"
            break
        if scan.files_scanned and scan.bytes_scanned + size > max_bytes:
            scan.stopped = "bytes"
            break
        if not scan.files_scanned and size > max_bytes:
            scan.stopped = "bytes"
            break
        fallback_session = os.path.splitext(os.path.basename(path))[0]
        try:
            fh = open_regular(path)
        except OSError:
            continue
        scan.files_scanned += 1
        with fh:
            while True:
                if time.monotonic() > ctx.deadline:
                    scan.stopped = "time"
                    break
                line = fh.readline(LINE_CAP)
                if not line:
                    break
                scan.bytes_scanned += len(line)
                if len(line) >= LINE_CAP and not line.endswith(b"\n"):
                    # over-long line: drop the rest of it without keeping it in memory
                    while not scan.stopped:
                        if time.monotonic() > ctx.deadline:
                            scan.stopped = "time"
                            break
                        rest = fh.readline(LINE_CAP)
                        scan.bytes_scanned += len(rest)
                        if not rest or rest.endswith(b"\n"):
                            break
                    if scan.stopped:
                        break
                    continue
                if b'"hook_' not in line and b"async_hook_response" not in line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, RecursionError, MemoryError):
                    continue  # one unparseable or absurdly nested line must not sink the scan
                if isinstance(obj, dict):
                    scan_record(ctx, scan, obj, seen, cutoff, fallback_session)
        if scan.stopped:
            break
    return scan


def scan_record(ctx, scan, obj, seen, cutoff, fallback_session):
    att = obj.get("attachment")
    if obj.get("type") == "attachment" and isinstance(att, dict):
        atype = att.get("type")
    elif obj.get("type") == "async_hook_response":
        att = obj
        atype = "async_hook_response"
    else:
        return
    if atype not in (
        "hook_success",
        "hook_non_blocking_error",
        "hook_cancelled",
        "hook_blocking_error",
        "hook_additional_context",
        "async_hook_response",
    ):
        return
    uid = obj.get("uuid")
    if isinstance(uid, str) and uid:
        if uid in seen:
            return
        seen.add(uid)
    ts = parse_ts(obj.get("timestamp"))
    if ts is None:
        scan.bad_ts += 1
    elif ts < cutoff:
        return
    scan.records += 1
    sid = obj.get("sessionId")
    session = sid if isinstance(sid, str) and sid else fallback_session
    event = event_of(att)
    label = att.get("command") if isinstance(att.get("command"), str) and att.get("command") else "(unlabelled)"

    if atype == "hook_blocking_error":
        scan.blocking[event] += 1
        return
    if atype == "hook_non_blocking_error":
        code = to_int(att.get("exitCode"))
        stderr = att.get("stderr")
        g = scan.fail.setdefault(label, new_group())
        g["count"] += 1
        g["sessions"].add(session)
        g["last"] = max(g["last"], ts or 0)
        g["exits"][code if code is not None else "?"] += 1
        g["causes"][classify(code, stderr if isinstance(stderr, str) else "")] += 1
        g["events"][event] += 1
        if g["stderr"] is None:
            g["stderr"] = first_line(stderr)
        return
    if atype == "hook_cancelled":
        if att.get("timedOut") is True or str(att.get("timedOut")).lower() == "true":
            g = scan.timeouts.setdefault(label, new_group())
            g["count"] += 1
            g["sessions"].add(session)
            g["last"] = max(g["last"], ts or 0)
            g["events"][event] += 1
            tm = to_int(att.get("timeoutMs"))
            if tm is not None:
                g["exits"][tm] += 1
        return
    if atype == "async_hook_response":
        code = to_int(att.get("exitCode"))
        if code in (None, 0):
            return
        g = scan.async_fail.setdefault(event, new_group())
        g["count"] += 1
        g["sessions"].add(session)
        g["last"] = max(g["last"], ts or 0)
        g["exits"][code] += 1
        if g["stderr"] is None:
            g["stderr"] = first_line(att.get("stderr"))
        return
    if atype == "hook_additional_context":
        content = att.get("content")
        parts = content if isinstance(content, list) else ([content] if isinstance(content, str) else [])
        nbytes = sum(len(c.encode("utf-8", "replace")) for c in parts if isinstance(c, str))
        add_inject(scan.event_inject, event, session, nbytes)
        return
    if atype == "hook_success":
        text = injection_text(att.get("stdout"), event)
        if text:
            add_inject(scan.hook_inject, (event, label), session, len(text.encode("utf-8", "replace")))
        return


def coverage_line(ctx, scan):
    mb = scan.bytes_scanned / (1024.0 * 1024.0)
    line = "scanned %d of %d transcript files from the last %d days (%.1f MB)" % (
        scan.files_scanned,
        scan.files_window,
        ctx.days,
        mb,
    )
    if scan.stopped == "time":
        line += "; stopped at the time budget, so counts are partial"
    elif scan.stopped == "bytes":
        line += "; stopped at the size budget, so counts are partial"
    elif scan.files_scanned < scan.files_window:
        line += "; partial"
    if scan.bad_ts:
        line += "; %d records had unreadable timestamps and were kept" % scan.bad_ts
    return line


def attribute(ctx, cfg, label):
    owners = []
    for rec in cfg.records:
        cands = [rec["command"]]
        if rec["status"]:
            cands.append(rec["status"])
        if rec["args"]:
            cands.append(" ".join([rec["command"]] + rec["args"]))
        if label in cands:
            owners.append(rec)
    names = sorted(set(r["owner"] for r in owners))
    return owners, names


def file_mtime(path):
    try:
        return os.stat(path).st_mtime if path else None
    except OSError:
        return None


def scan_status_common(ctx, cfg, scan, sec):
    """Shared 'could not check' logic for the two transcript sections. Returns True when usable."""
    if scan.missing:
        sec.add(
            "could",
            "no-transcripts",
            "no transcript folder at %s" % clean(ctx, tilde(ctx, os.path.join(ctx.config_dir, "projects")), 80),
            None,
        )
        return False
    if scan.files_scanned == 0:
        if scan.stopped == "time":
            why = "stopped at the time budget before any file was read"
        elif scan.stopped == "bytes":
            why = "stopped at the size budget before any file was read"
        else:
            why = "no transcript files changed in the last %d days" % ctx.days
        sec.add("could", "no-transcripts", "nothing scanned: %s" % why, None)
        return False
    if scan.records == 0 and cfg.records:
        sec.add(
            "could",
            "no-hook-records",
            "scanned %d files and saw no hook records of any kind although %d hook commands are configured; "
            "either no hook ran in this window or the transcript format changed. Silence is not a clean bill."
            % (scan.files_scanned, len(cfg.records)),
            None,
        )
        return False
    if scan.stopped:
        sec.add(
            "could",
            "scan-partial",
            "partial scan: read %d of %d transcript files and stopped at the %s budget; "
            "anything not found in the part that was read is not ruled out"
            % (scan.files_scanned, scan.files_window, "time" if scan.stopped == "time" else "size"),
            "narrow the window (--days 2) so the whole scan fits, then re-run",
        )
    return True


def run_failures(ctx, cfg, scan):
    sec = Section("failures")
    if not scan_status_common(ctx, cfg, scan, sec):
        sec.summary = "no usable transcript data"
        sec.lines.append(coverage_line(ctx, scan) if not scan.missing else "transcripts not found")
        return sec
    sec.lines.append("Coverage: " + coverage_line(ctx, scan))
    rows = []
    for label, g in scan.fail.items():
        owners, names = attribute(ctx, cfg, label)
        rows.append((g["count"], label, g, owners, names, "failure"))
    for label, g in scan.timeouts.items():
        owners, names = attribute(ctx, cfg, label)
        rows.append((g["count"], label, g, owners, names, "timeout"))
    rows.sort(key=lambda r: (-r[0], r[1]))
    data = []
    for count, label, g, owners, names, kind in rows:
        shown = clean(ctx, label, 100)
        if not owners:
            attribution = "no longer configured (may be fixed)"
            level = "note"
        elif len(names) > 1:
            attribution = "ambiguous: " + ", ".join(clean(ctx, n, 50) for n in names)
            level = "problem"
        else:
            attribution = names[0]
            level = "problem"
        extra = ""
        if owners and level == "problem":
            newer = [
                r["file"] for r in owners if file_mtime(r["file"]) and file_mtime(r["file"]) > g["last"] > 0
            ]
            if newer:
                extra = "; config changed since last failure, re-run to confirm"
        if kind == "failure":
            cause = ", ".join("%s x%d" % (c, n) for c, n in g["causes"].most_common(3))
            exits = ", ".join("exit %s x%d" % (c, n) for c, n in g["exits"].most_common(3))
            ex = clean(ctx, g["stderr"], EXCERPT_LIMIT) if g["stderr"] else ""
            text = "%s: %s -- %d errors in %d sessions, last %s; %s; %s" % (
                shown,
                clean(ctx, attribution, 100),
                count,
                len(g["sessions"]),
                fmt_day(g["last"]) if g["last"] else "unknown",
                cause,
                exits,
            )
            if ex:
                text += '; stderr (quoted data): "%s"' % ex
            text += extra
            fid = "hook-failing"
            if "interpreter missing" in g["causes"]:
                fix = "run the command by hand in a bare shell (env -i PATH=/usr/bin:/bin); a bare python becomes python3"
            elif "not executable" in g["causes"]:
                fix = "chmod +x the script, or call it through bash or python3"
            elif "missing script" in g["causes"]:
                fix = "restore the script or fix the path in the hook command"
            else:
                fix = "run the hook command by hand with a sample payload and read its stderr"
        else:
            text = "%s: %s -- timed out %d times in %d sessions, last %s%s" % (
                shown,
                clean(ctx, attribution, 100),
                count,
                len(g["sessions"]),
                fmt_day(g["last"]) if g["last"] else "unknown",
                extra,
            )
            fid = "hook-timeout"
            fix = "make the hook faster or raise its timeout; slow hooks delay every turn they run on"
        if level == "problem":
            sec.add("problem", fid, text, fix)
        else:
            sec.add("note", fid, text, None)
        data.append(
            {"label": shown, "kind": kind, "count": count, "sessions": len(g["sessions"]), "attribution": attribution}
        )
    for event, g in sorted(scan.async_fail.items()):
        text = (
            "async hook (not attributable to one command), event %s: %d non-zero results in %d sessions, last %s; exit %s%s"
            % (
                clean(ctx, event, 30),
                g["count"],
                len(g["sessions"]),
                fmt_day(g["last"]) if g["last"] else "unknown",
                ", ".join(str(c) for c, _ in g["exits"].most_common(3)),
                (' ; stderr (quoted data): "%s"' % clean(ctx, g["stderr"])) if g["stderr"] else "; empty stderr",
            )
        )
        sec.add("problem", "hook-failing-async", text, "find the async hook for this event and run it by hand with a sample payload")
        data.append({"label": "async:" + event, "kind": "async", "count": g["count"], "sessions": len(g["sessions"])})
    blocked = sum(scan.blocking.values())
    if blocked:
        sec.lines.append(
            "%d deliberate blocks (hook_blocking_error) are not counted as failures: a guard doing its job." % blocked
        )
    if not (scan.fail or scan.timeouts or scan.async_fail):
        sec.lines.append("No hook errors, timeouts or failed async hooks among %d hook records." % scan.records)
    sec.data = {"failure_groups": data, "hook_records": scan.records, "blocking_errors": blocked}
    sec.summary = "%d failing hook commands or events in the last %d days" % (len(data), ctx.days)
    return sec


def run_injection(ctx, cfg, scan):
    sec = Section("injection")
    if not scan_status_common(ctx, cfg, scan, sec):
        sec.summary = "no usable transcript data"
        sec.lines.append(coverage_line(ctx, scan) if not scan.missing else "transcripts not found")
        return sec
    sec.lines.append("Coverage: " + coverage_line(ctx, scan))
    sec.lines.append(
        "Bytes are utf-8 sizes of injected context where the transcript recorded it; tokens are an estimate (bytes / 4)."
    )
    if not scan.event_inject:
        sec.lines.append("No injected context was recorded in this window.")
    per_hook_events = set(e for (e, _l) in scan.hook_inject)
    events = []
    for event, g in sorted(scan.event_inject.items(), key=lambda kv: -kv[1]["total"]):
        per_session = list(g["sessions"].values())
        mean_ps = sum(per_session) / float(len(per_session)) if per_session else 0
        max_ps = max(per_session) if per_session else 0
        mean_run = g["total"] / float(g["runs"]) if g["runs"] else 0
        hook_note = "per hook below" if event in per_hook_events else "per hook: not recorded"
        sec.lines.append(
            "  %s: %s runs in %d sessions; mean %s B per session (est. %s tokens), max %s B; mean %s B per run, max %s B; %s"
            % (
                clean(ctx, event, 30),
                fmt_int(g["runs"]),
                len(per_session),
                fmt_int(int(mean_ps + 0.5)),
                fmt_int(est_tokens(mean_ps)),
                fmt_int(max_ps),
                fmt_int(int(mean_run + 0.5)),
                fmt_int(g["max"]),
                hook_note,
            )
        )
        events.append(
            {
                "event": event,
                "runs": g["runs"],
                "sessions": len(per_session),
                "mean_bytes_per_session": mean_ps,
                "max_bytes_per_session": max_ps,
                "est_tokens_mean_per_session": est_tokens(mean_ps),
            }
        )
        if mean_ps >= ctx.inject_bytes:
            sec.add(
                "problem",
                "inject-heavy",
                "%s injects a mean of %s B per session (est. %s tokens), at or over the %s B flag line"
                % (clean(ctx, event, 30), fmt_int(int(mean_ps + 0.5)), fmt_int(est_tokens(mean_ps)), fmt_int(ctx.inject_bytes)),
                "trim what the hook prints, or have it print a pointer to a file the model reads only when needed",
            )
    hooks = []
    for (event, label), g in sorted(scan.hook_inject.items(), key=lambda kv: -kv[1]["total"]):
        per_session = list(g["sessions"].values())
        mean_run = g["total"] / float(g["runs"])
        hooks.append({"event": event, "label": clean(ctx, label, 100), "runs": g["runs"], "mean_bytes_per_run": mean_run})
    if hooks:
        sec.lines.append("  Per hook (from hook_success records, which exist only for some runs):")
        shown = hooks if ctx.show_all else hooks[:ROW_LIMIT]
        for h in shown:
            sec.lines.append(
                "    %s / %s: %s runs, mean %s B per run (est. %s tokens)"
                % (
                    clean(ctx, h["event"], 30),
                    h["label"],
                    fmt_int(h["runs"]),
                    fmt_int(int(h["mean_bytes_per_run"] + 0.5)),
                    fmt_int(est_tokens(h["mean_bytes_per_run"])),
                )
            )
        if len(hooks) > len(shown):
            sec.lines.append("    ... %d more (use --all)" % (len(hooks) - len(shown)))
    sec.data = {"events": events, "hooks": hooks}
    sec.summary = "%d events with recorded injections; %d hooks attributable" % (len(events), len(hooks))
    return sec


# --------------------------------------------------------------------------- always-on weight


def _scalar(val, cont):
    v = val.strip()
    if v[:1] in (">", "|") and re.match(r"^[>|][+\-0-9]*$", v):
        body = [l for l in cont]
        if v[0] == ">":
            paras = []
            cur = []
            for l in body:
                if l.strip() == "":
                    if cur:
                        paras.append(" ".join(cur))
                        cur = []
                else:
                    cur.append(l.strip())
            if cur:
                paras.append(" ".join(cur))
            return "\n".join(paras).strip()
        indents = [len(l) - len(l.lstrip()) for l in body if l.strip()]
        cut = min(indents) if indents else 0
        return "\n".join(l[cut:] if l.strip() else "" for l in body).strip()
    if v[:1] in ('"', "'"):
        q = v[0]
        s = v
        extra = [l.strip() for l in cont if l.strip()]
        if v.count(q) < 2 or (len(v) > 1 and v.rstrip()[-1] != q):
            s = " ".join([v] + extra)
        end = s.rfind(q)
        inner = s[1:end] if end > 0 else s[1:]
        if q == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
        else:
            inner = inner.replace("''", "'")
        return inner
    extra = [l.strip() for l in cont if l.strip()]
    return " ".join([v] + extra).strip() if v or extra else ""


def parse_frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    fm = {}
    i = 0
    while i < len(fm_lines):
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", fm_lines[i])
        i += 1
        if not m:
            continue
        cont = []
        while i < len(fm_lines) and (fm_lines[i].strip() == "" or fm_lines[i][:1] in (" ", "\t")):
            cont.append(fm_lines[i])
            i += 1
        fm[m.group(1)] = _scalar(m.group(2).rstrip(), cont)
    return fm, body


def entry_info(path, kind, display_name, cap=ENTRY_CAP):
    data = read_bounded(path, 256 * 1024)
    if data is None:
        return None
    raw = data.decode("utf-8", "replace")
    fm, body = parse_frontmatter(raw)
    name_only = str(fm.get("disable-model-invocation", "")).strip().lower() == "true" and kind != "agent"
    desc = fm.get("description") if isinstance(fm.get("description"), str) else ""
    when = fm.get("when_to_use") if isinstance(fm.get("when_to_use"), str) else ""
    note = None
    if not desc.strip():
        if kind == "agent":
            text = ""
            note = "no description"
        else:
            first = ""
            for ln in body.split("\n"):
                if ln.strip():
                    first = re.sub(r"^#+\s*", "", ln.strip())
                    break
            text = first[:FALLBACK_DESC_CAP]
            note = "no description; first body line used"
    else:
        text = desc.strip()
        if when.strip():
            text = text + " - " + when.strip()
    raw_len = len(text)
    counted = 0 if name_only else min(raw_len, cap)
    return {
        "kind": kind,
        "name": display_name,
        "raw": raw_len,
        "counted": counted,
        "cut": (not name_only) and raw_len > cap,
        "name_only": name_only,
        "note": note,
    }


def weight_row(label, root_dirs, prefix, kind="plugin", cap=ENTRY_CAP):
    """root_dirs: {'skills': dir, 'agents': dir, 'commands': dir}. prefix: plugin name for listing names."""
    entries = []
    unreadable = []
    sk = root_dirs.get("skills")
    if sk and os.path.isdir(sk):
        for d in sorted(os.listdir(sk)):
            p = os.path.join(sk, d, "SKILL.md")
            if os.path.lexists(p):  # a FIFO/device SKILL.md lands in the "not counted" notes, not silently dropped
                e = entry_info(p, "skill", (prefix + ":" if prefix else "") + d, cap)
                if e:
                    entries.append(e)
                else:
                    unreadable.append((prefix + ":" if prefix else "") + d)
    ag = root_dirs.get("agents")
    if ag and os.path.isdir(ag):
        for dirpath, dirnames, filenames in os.walk(ag):
            if dirpath.count(os.sep) - ag.count(os.sep) >= 2:
                dirnames[:] = []
            for fn in sorted(filenames):
                if fn.endswith(".md"):
                    e = entry_info(os.path.join(dirpath, fn), "agent", fn[:-3], cap)
                    if e:
                        entries.append(e)
                    else:
                        unreadable.append(fn[:-3])
    cm = root_dirs.get("commands")
    if cm and os.path.isdir(cm):
        for dirpath, dirnames, filenames in os.walk(cm):
            if dirpath.count(os.sep) - cm.count(os.sep) >= 3:
                dirnames[:] = []
            for fn in sorted(filenames):
                if fn.endswith(".md"):
                    rel = os.path.relpath(os.path.join(dirpath, fn), cm)[:-3].replace(os.sep, ":")
                    e = entry_info(os.path.join(dirpath, fn), "command", (prefix + ":" if prefix else "") + rel, cap)
                    if e:
                        entries.append(e)
                    else:
                        unreadable.append((prefix + ":" if prefix else "") + rel)
    chars = sum(e["counted"] for e in entries)
    listing = sum(len(e["name"]) + 4 + e["counted"] for e in entries if e["kind"] in ("skill", "command"))
    return {
        "label": label,
        "kind": kind,
        "skills": len([e for e in entries if e["kind"] == "skill"]),
        "agents": len([e for e in entries if e["kind"] == "agent"]),
        "commands": len([e for e in entries if e["kind"] == "command"]),
        "chars": chars,
        "listing": listing,
        "cut": [e["name"] for e in entries if e["cut"]],
        "notes": sorted(
            set("%s (%s)" % (e["name"], e["note"]) for e in entries if e["note"])
            | set("%s (not counted: not a regular file or unreadable)" % n for n in unreadable)
        ),
        "name_only": [e["name"] for e in entries if e["name_only"]],
    }


def resolve_listing_budget(ctx, cfg):
    """Settings override the defaults: settings env applies on top of the process env, and
    skillListingBudgetFraction comes from the merged settings (local over project over user)."""
    ctx.entry_cap = ENTRY_CAP
    for scope in ("local", "project", "user"):
        cap = (cfg.settings.get(scope) or {}).get("skillListingMaxDescChars")
        if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
            ctx.entry_cap = cap
            break
    if ctx.listing_budget_source == "flag":
        return
    raw = cfg.env.get("SLASH_COMMAND_TOOL_CHAR_BUDGET")
    if raw is not None and re.match(r"^\d+$", raw.strip()) and int(raw) > 0:
        ctx.listing_budget = int(raw)
        ctx.listing_budget_source = "settings-env"
        return
    if ctx.listing_budget_source == "env":
        return
    for scope in ("local", "project", "user"):
        data = cfg.settings.get(scope) or {}
        frac = data.get("skillListingBudgetFraction")
        if isinstance(frac, (int, float)) and not isinstance(frac, bool) and 0 < frac <= 1:
            ctx.listing_fraction = frac
            ctx.listing_budget = int(DEFAULT_WINDOW_TOKENS * 4 * frac)
            ctx.listing_budget_source = "settings"
            return


def short_tail(text, width):
    return text if len(text) <= width else "\u2026" + text[-(width - 1):]


def run_weight(ctx, cfg):
    sec = Section("weight")
    if not cfg.config_dir_exists:
        sec.add("could", "no-config-dir", "no config folder at %s" % clean(ctx, tilde(ctx, ctx.config_dir), 80), None)
        sec.summary = "no config folder"
        return sec
    resolve_listing_budget(ctx, cfg)
    cap = getattr(ctx, "entry_cap", ENTRY_CAP)
    rows = []
    for p in cfg.plugins:
        r = weight_row(
            clean(ctx, p["name"], 50),
            {"skills": os.path.join(p["root"], "skills"), "agents": os.path.join(p["root"], "agents"), "commands": os.path.join(p["root"], "commands")},
            p["name"].split()[-1].split("/")[-1],
            cap=cap,
        )
        rows.append(r)
    rows.append(
        weight_row(
            "user (%s)" % short_tail(clean(ctx, tilde(ctx, ctx.config_dir), 400), 40),
            {
                "skills": os.path.join(ctx.config_dir, "skills"),
                "agents": os.path.join(ctx.config_dir, "agents"),
                "commands": os.path.join(ctx.config_dir, "commands"),
            },
            "",
            "user",
            cap,
        )
    )
    proj_dot = os.path.join(ctx.project, ".claude")
    if real(proj_dot) != real(ctx.config_dir):
        rows.append(
            weight_row(
                "project (.claude)",
                {
                    "skills": os.path.join(proj_dot, "skills"),
                    "agents": os.path.join(proj_dot, "agents"),
                    "commands": os.path.join(proj_dot, "commands"),
                },
                "",
                "project",
                cap,
            )
        )
    rows = [r for r in rows if r["kind"] == "plugin" or r["skills"] or r["agents"] or r["commands"]]
    rows.sort(key=lambda r: (-r["chars"], r["label"]))
    total_chars = sum(r["chars"] for r in rows)
    total_listing = sum(r["listing"] for r in rows)
    sec.lines.append(
        "Per source: description characters of skills, agents and commands that are always in context; est. tokens = characters / 4 (estimate)."
    )
    sec.lines.append("  %-34s %6s %6s %5s %8s %10s" % ("source", "skills", "agents", "cmds", "chars", "est.tokens"))
    shown = rows if ctx.show_all else rows[:ROW_LIMIT]
    for r in shown:
        sec.lines.append(
            "  %-34s %6d %6d %5d %8s %10s"
            % (r["label"][:34], r["skills"], r["agents"], r["commands"], fmt_int(r["chars"]), fmt_int(est_tokens(r["chars"])))
        )
    if len(rows) > len(shown):
        sec.lines.append("  ... %d more sources (use --all)" % (len(rows) - len(shown)))
    sec.lines.append(
        "  %-34s %6d %6d %5d %8s %10s"
        % (
            "total",
            sum(r["skills"] for r in rows),
            sum(r["agents"] for r in rows),
            sum(r["commands"] for r in rows),
            fmt_int(total_chars),
            fmt_int(est_tokens(total_chars)),
        )
    )
    cut = [(r["label"], n) for r in rows for n in r["cut"]]
    if cut:
        sec.lines.append(
            "  cut: %d entries longer than %s characters are shortened in the listing: %s"
            % (len(cut), fmt_int(cap), ", ".join("%s/%s" % (a, clean(ctx, b, 30)) for a, b in cut[:5]))
        )
    nameonly = [(r["label"], n) for r in rows for n in r["name_only"]]
    if nameonly:
        sec.lines.append("  %d entries are name-only (disable-model-invocation) and count 0." % len(nameonly))
    noted = [x for r in rows for x in r["notes"]]
    if noted:
        sec.lines.append("  notes: " + "; ".join(clean(ctx, x, 70) for x in noted[:4]))
    budget = ctx.listing_budget
    budget_src = "derived: %s-token window x 4 x %s; a 1M-context window gets a larger budget" % (
        fmt_int(DEFAULT_WINDOW_TOKENS),
        ctx.listing_fraction,
    )
    if ctx.listing_budget_source == "env":
        budget_src = "from SLASH_COMMAND_TOOL_CHAR_BUDGET"
    elif ctx.listing_budget_source == "settings-env":
        budget_src = "from SLASH_COMMAND_TOOL_CHAR_BUDGET in settings env"
    elif ctx.listing_budget_source == "flag":
        budget_src = "from --listing-budget"
    elif ctx.listing_budget_source == "settings":
        budget_src = "derived: %s-token window x 4 x %s from skillListingBudgetFraction in settings; a 1M-context window gets a larger budget" % (
            fmt_int(DEFAULT_WINDOW_TOKENS),
            ctx.listing_fraction,
        )
    sec.lines.append(
        "  Skill and command listing: %s characters against a budget of %s (%s; as of Claude Code %s). "
        "Excludes bundled and claude.ai skills."
        % (fmt_int(total_listing), fmt_int(budget), budget_src, TESTED_WITH)
    )
    if total_listing > budget:
        top = ", ".join("%s (%s)" % (r["label"], fmt_int(r["listing"])) for r in sorted(rows, key=lambda r: -r["listing"])[:3])
        sec.add(
            "problem",
            "weight-heavy",
            "the skill and command listing is %s characters, over the %s budget; Claude Code cuts lower-priority entries to name-only. Heaviest: %s"
            % (fmt_int(total_listing), fmt_int(budget), top),
            "shorten the descriptions of the heaviest plugins or turn off plugins you do not use",
        )
    sec.data = {
        "rows": [{k: r[k] for k in ("label", "skills", "agents", "commands", "chars", "listing")} for r in rows],
        "total_chars": total_chars,
        "estimated_tokens": est_tokens(total_chars),
        "listing_chars": total_listing,
        "listing_budget": budget,
    }
    sec.summary = "%s description characters across %d sources (est. %s tokens)" % (
        fmt_int(total_chars),
        len(rows),
        fmt_int(est_tokens(total_chars)),
    )
    return sec


# --------------------------------------------------------------------------- function hooks flag


def parse_bool(raw):
    if not isinstance(raw, str):
        return "bad"
    s = raw.strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return "bad"


def run_flag(ctx, cfg):
    sec = Section("flag")
    sources = []  # (label, display, verdict)
    decided = None  # (verdict, label)
    unclear = False

    def consider(label, raw):
        nonlocal decided, unclear
        v = parse_bool(raw)
        shown = clean(ctx, raw, 20)
        sources.append((label, shown, v))
        if decided is None and not unclear:
            if v == "bad":
                unclear = True
                sec.add(
                    "could",
                    "flag-unrecognised",
                    "%s is set to %r, which is not one of 1/true/yes/on or 0/false/no/off" % (label, shown),
                    "set it to 1 to turn function hooks on, or 0 to turn them off",
                )
            else:
                decided = (v, label)

    # Claude Code applies settings env on top of the process env at startup, so settings win.
    for scope in ("local", "project", "user"):
        env = cfg.scope_env.get(scope, {})
        if FLAG_ENV in env:
            consider("%s settings env" % scope, env[FLAG_ENV])
    if FLAG_ENV in ctx.environ:
        consider("this shell's environment", ctx.environ[FLAG_ENV])

    cache_val = "missing"
    cdata, cerr = read_json(ctx.global_config)
    cache_state = None
    if cerr:
        cache_state = "could not read %s (%s)" % (clean(ctx, tilde(ctx, ctx.global_config), 60), cerr)
    elif isinstance(cdata, dict):
        feats = cdata.get("cachedGrowthBookFeatures")
        if isinstance(feats, dict) and FLAG_CACHE_KEY in feats:
            val = feats[FLAG_CACHE_KEY]
            if isinstance(val, bool):
                cache_val = val
            else:
                cache_state = "cache holds a non-boolean value for %s" % FLAG_CACHE_KEY
    else:
        cache_state = "could not read %s (invalid)" % clean(ctx, tilde(ctx, ctx.global_config), 60)
    if cache_val is True or cache_val is False:
        sources.append(("growth cache", "true" if cache_val else "false", cache_val))
    elif cache_state is None:
        sources.append(("growth cache", "no entry", None))

    verdict = None
    where = None
    if decided is not None:
        verdict, where = decided
    elif not unclear:
        if cache_val is True or cache_val is False:
            verdict, where = cache_val, "growth cache (may lag the server)"
        elif cache_state is None:
            verdict, where = True, "default: no entry in the cache; the cache may lag"
        else:
            verdict, where = True, "default; the cache could not be read"
            sec.add("could", "flag-cache-unreadable", cache_state, "start Claude Code once so it writes its config, or set %s=1 yourself" % FLAG_ENV)

    word = {True: "ON", False: "OFF", None: "unknown"}[verdict]
    sec.lines.append("Function hooks (mods): %s -- %s" % (
        word,
        where or ("a source holds a value that is not recognised (see below)" if unclear else "no source could be read"),
    ))
    if len(set(str(s[2]) for s in sources if s[2] in (True, False))) > 1:
        sec.lines.append("Sources disagree; the first defined source above wins:")
    for label, shown, v in sources:
        sec.lines.append("  %-24s %s" % (label, shown))

    # settings that switch hooks off
    configured = len(cfg.records)
    for scope in ("user", "project", "local"):
        data = cfg.settings.get(scope) or {}
        if data.get("disableAllHooks") is True:
            if configured:
                sec.add(
                    "problem",
                    "flag-disabled-all-hooks",
                    "%s settings set disableAllHooks: true, so none of the %d configured hooks run, and mods stay off" % (scope, configured),
                    "remove disableAllHooks from that settings file (or set it to false)",
                )
            else:
                sec.lines.append("%s settings set disableAllHooks: true (no hooks are configured)." % scope)
            verdict = False if verdict is not None else verdict
        if data.get("allowManagedHooksOnly") is True:
            sec.lines.append("%s settings set allowManagedHooksOnly: true; plugin mods do not load under it." % scope)
            verdict = False if verdict is not None else verdict

    # module-shipping plugins
    shippers = []
    for p in cfg.plugins:
        listed = []
        for spec, hfile in p["modules"]:
            base_a = os.path.normpath(os.path.join(os.path.dirname(hfile), spec))
            base_b = os.path.normpath(os.path.join(p["root"], spec))
            if os.path.exists(base_a):
                listed.append(real(base_a))
            elif os.path.exists(base_b):
                listed.append(real(base_b))
            else:
                sec.add(
                    "problem",
                    "flag-module-missing",
                    "%s lists module %s in its hooks file, but the file is missing" % (clean(ctx, p["name"], 50), clean(ctx, spec, 60)),
                    "create the module file or remove it from modules",
                )
        orphans = [r for r in p["register"] if real(r) not in listed]
        if p["register"] and orphans:
            sec.add(
                "problem",
                "flag-register-orphan",
                "%s ships %s but no hooks file lists it under modules, so it will never load"
                % (clean(ctx, p["name"], 50), clean(ctx, os.path.relpath(orphans[0], p["root"]), 60)),
                'add "modules": ["./register.ts"] to the plugin hooks file',
            )
        if p["modules"] or p["register"]:
            shippers.append(p["name"])
    if shippers:
        names = ", ".join(clean(ctx, n, 40) for n in shippers[:6])
        if verdict is False:
            sec.add(
                "problem",
                "flag-off-mods-shipped",
                "function hooks are off, so the mods in %s are inert (their classic hooks still run)" % names,
                "export %s=1 (or add it under env in ~/.claude/settings.json) and restart Claude Code" % FLAG_ENV,
            )
        elif verdict is True:
            sec.lines.append("Enabled plugins that ship mods: %s." % names)
        else:
            sec.add("could", "flag-unknown", "enabled plugins ship mods (%s) but the flag state is unknown" % names, None)
    else:
        sec.lines.append(
            "No enabled plugin ships a mod, so the flag changes nothing today."
            if verdict is False
            else "No enabled plugin ships a mod."
        )
    sec.data = {
        "verdict": None if verdict is None else bool(verdict),
        "source": where,
        "sources": [{"source": l, "value": s} for l, s, _v in sources],
        "mod_plugins": shippers,
    }
    sec.summary = "function hooks %s" % word.lower()
    return sec


# --------------------------------------------------------------------------- python3


def dev_tools_present():
    if os.path.exists("/Library/Developer/CommandLineTools/usr/bin/python3"):
        return True
    return bool(glob.glob("/Applications/Xcode*.app/Contents/Developer/usr/bin/python3"))


def probe_python(path, ctx, seconds):
    """Run `<path> --version` with a hard timeout. Returns (version tuple or None, problem text or None)."""
    env = {"PATH": ctx.minimal_path, "HOME": ctx.home or "/"}
    try:
        proc = subprocess.Popen(
            [path, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        return None, "could not start: %s" % clean(ctx, str(exc), 80)
    try:
        out, err = proc.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        return None, "timeout"
    text = (out or b"").decode("utf-8", "replace") + (err or b"").decode("utf-8", "replace")
    m = re.search(r"Python\s+(\d+)\.(\d+)(?:\.(\d+))?", text)
    if proc.returncode == 0 and m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)), None
    return None, "exited %s: %s" % (proc.returncode, clean(ctx, text, EXCERPT_LIMIT) or "no output")


def run_python(ctx, cfg):
    sec = Section("python")
    rv = sys.version_info
    sec.lines.append("Running interpreter: Python %d.%d.%d (%s)" % (rv[0], rv[1], rv[2], clean(ctx, tilde(ctx, sys.executable or "?"), 70)))
    low = which("python3", ctx.minimal_path)
    cur = which("python3", ctx.path)
    sec.lines.append(
        "python3 under %s: %s; under your current PATH: %s"
        % (
            ctx.minimal_path,
            clean(ctx, tilde(ctx, low), 60) if low else "not found",
            clean(ctx, tilde(ctx, cur), 60) if cur else "not found",
        )
    )
    version = None
    if (rv[0], rv[1]) < (3, 9):
        sec.add("problem", "python-old", "the interpreter running this check is Python %d.%d; hooks need 3.9 or newer" % (rv[0], rv[1]), "install a newer python3")
    if not low and not cur:
        sec.add(
            "problem",
            "python-missing",
            "python3 is on neither %s nor your current PATH; every hook that calls python3 fails with 127" % ctx.minimal_path,
            "install python3, or give hooks the full path to it",
        )
    elif not low:
        sec.add(
            "note",
            "python-needs-path",
            "python3 is found only on your shell PATH; hooks fail if Claude Code is launched from the Dock or a scheduler",
            "start Claude Code from a terminal, or install python3 where %s can see it" % ctx.minimal_path,
        )
    if low:
        same = False
        try:
            same = bool(sys.executable) and real(low) == real(sys.executable)
        except Exception:
            same = False
        if same:
            version = (rv[0], rv[1], rv[2])
        elif ctx.no_exec:
            sec.add("could", "python-not-probed", "did not run `%s --version` (--no-exec); its version is unknown" % clean(ctx, tilde(ctx, low), 60), None)
        elif IS_MAC and low == "/usr/bin/python3" and not dev_tools_present():
            sec.add(
                "problem",
                "python-stub",
                "/usr/bin/python3 is the developer-tools stub and the tools are not installed; running it opens an install prompt, so it was not run",
                "install the command line developer tools, or put a real python3 on %s" % ctx.minimal_path,
            )
        else:
            remaining = ctx.deadline - time.monotonic()
            if remaining < 0.2:
                sec.add("could", "python-not-probed", "no time left to run `python3 --version`", None)
            else:
                seconds = min(2.0, max(0.3, remaining * 0.4))
                version, why = probe_python(low, ctx, seconds)
                if why == "timeout":
                    sec.add("could", "python-probe-timeout", "`%s --version` did not answer within %.1f s and was stopped" % (clean(ctx, tilde(ctx, low), 60), seconds), None)
                elif why:
                    sec.add(
                        "problem",
                        "python-broken",
                        "`%s --version` failed (%s); hooks that call python3 would fail the same way" % (clean(ctx, tilde(ctx, low), 60), why),
                        "reinstall python3 or repair the shim, then re-run this check",
                    )
    if version is not None:
        sec.lines.append("python3 under %s reports %d.%d.%d" % (ctx.minimal_path, version[0], version[1], version[2]))
        if (version[0], version[1]) < (3, 9):
            sec.add(
                "problem",
                "python-old",
                "python3 under %s is %d.%d; suite hooks need 3.9 or newer" % (ctx.minimal_path, version[0], version[1]),
                "install a newer python3 and put it where %s can see it" % ctx.minimal_path,
            )
    sec.data = {"running": "%d.%d.%d" % (rv[0], rv[1], rv[2]), "minimal_path_python3": bool(low), "current_path_python3": bool(cur), "version": version and "%d.%d.%d" % version}
    sec.summary = "python3 %s" % ("%d.%d.%d" % version if version else "version not determined")
    return sec


# --------------------------------------------------------------------------- driver


def parse_args(argv):
    p = _Parser(prog="doctor.py", add_help=False, allow_abbrev=False)
    p.add_argument("--home")
    p.add_argument("--config-dir", dest="config_dir")
    p.add_argument("--project")
    p.add_argument("--days")
    p.add_argument("--section")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-exec", dest="no_exec", action="store_true")
    p.add_argument("--path")
    p.add_argument("--minimal-path", dest="minimal_path")
    p.add_argument("--time-budget", dest="time_budget")
    p.add_argument("--max-mb", dest="max_mb")
    p.add_argument("--listing-budget", dest="listing_budget")
    p.add_argument("--inject-bytes", dest="inject_bytes")
    return p.parse_known_args(argv)


def build_ctx(args, extra, environ, notes):
    ctx = Ctx()
    ctx.environ = environ
    ctx.show_all = bool(args.all)
    ctx.limit = ROW_LIMIT
    ctx.no_exec = bool(args.no_exec)
    ctx.strict = bool(args.strict)
    ctx.as_json = bool(args.json)
    if args.config_dir:
        ctx.config_dir = os.path.abspath(os.path.expanduser(args.config_dir))
        ctx.global_config = os.path.join(ctx.config_dir, ".claude.json")
        ctx.home = environ.get("HOME") or os.path.expanduser("~")
    elif args.home:
        ctx.home = os.path.abspath(os.path.expanduser(args.home))
        ctx.config_dir = os.path.join(ctx.home, ".claude")
        ctx.global_config = os.path.join(ctx.home, ".claude.json")
    elif environ.get("CLAUDE_CONFIG_DIR"):
        ctx.config_dir = os.path.abspath(os.path.expanduser(environ["CLAUDE_CONFIG_DIR"]))
        ctx.global_config = os.path.join(ctx.config_dir, ".claude.json")
        ctx.home = environ.get("HOME") or os.path.expanduser("~")
    else:
        ctx.home = environ.get("HOME") or os.path.expanduser("~")
        ctx.config_dir = os.path.join(ctx.home, ".claude")
        ctx.global_config = os.path.join(ctx.home, ".claude.json")
    ctx.project = os.path.abspath(
        os.path.expanduser(args.project or environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    )
    ctx.path = args.path if args.path is not None else environ.get("PATH", "")
    ctx.minimal_path = args.minimal_path if args.minimal_path is not None else MINIMAL_PATH
    ctx.now = time.time()

    def num(raw, default, low, high, name, cast):
        if raw is None:
            return default
        try:
            v = cast(raw)
        except (TypeError, ValueError):
            notes.append("%s %r is not a number; using %s" % (name, clean(ctx, raw, 20), default))
            return default
        if v < low or v > high:
            notes.append("%s %s is outside %s..%s; using %s" % (name, v, low, high, default))
            return default
        return v

    ctx.days = num(args.days, 7, 1, 90, "--days", int)
    budget = num(args.time_budget, 8.5, 0.2, 60.0, "--time-budget", float)
    ctx.max_mb = num(args.max_mb, 2048.0, 1.0, 16384.0, "--max-mb", float)
    ctx.inject_bytes = num(args.inject_bytes, DEFAULT_INJECT_BYTES, 1, 10 ** 9, "--inject-bytes", int)
    ctx.deadline = time.monotonic() + budget
    ctx.time_budget = budget

    ctx.listing_fraction = DEFAULT_LISTING_FRACTION
    ctx.listing_budget_source = "derived"
    if args.listing_budget is not None:
        ctx.listing_budget = num(args.listing_budget, int(DEFAULT_WINDOW_TOKENS * 4 * DEFAULT_LISTING_FRACTION), 1, 10 ** 9, "--listing-budget", int)
        ctx.listing_budget_source = "flag"
    elif re.match(r"^\d+$", environ.get("SLASH_COMMAND_TOOL_CHAR_BUDGET", "")):
        ctx.listing_budget = int(environ["SLASH_COMMAND_TOOL_CHAR_BUDGET"])
        ctx.listing_budget_source = "env"
    else:
        ctx.listing_budget = int(DEFAULT_WINDOW_TOKENS * 4 * ctx.listing_fraction)

    wanted = list(SECTION_IDS)
    if args.section:
        asked = [s.strip().lower() for s in args.section.split(",") if s.strip()]
        good = [s for s in asked if s in SECTION_IDS]
        bad = [s for s in asked if s not in SECTION_IDS]
        if bad:
            notes.append(
                "unknown section %s ignored (known: %s)" % (", ".join(clean(ctx, b, 20) for b in bad), ", ".join(SECTION_IDS))
            )
        if good:
            wanted = [s for s in SECTION_IDS if s in good]
    ctx.wanted = wanted
    if extra:
        notes.append("ignored arguments: " + clean(ctx, " ".join(extra), 100))
    return ctx


def safe(ctx, sid, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # a broken section must not hide the others
        sec = Section(sid)
        sec.add("could", "internal-error", "could not check: internal error (%s)" % type(exc).__name__, None)
        sec.summary = "internal error"
        return sec


def run_all(ctx):
    results = {}
    try:
        cfg = load_config(ctx)
        config_failed = None
    except Exception as exc:  # RecursionError and friends: one failed load must not take every section down
        cfg = Config()
        config_failed = type(exc).__name__
    if config_failed:
        for sid in ctx.wanted:
            if sid == "python":
                continue  # needs no config: it still runs below
            s = Section(sid)
            s.add("could", "internal-error", "could not check: internal error loading configuration (%s)" % config_failed, None)
            s.summary = "internal error"
            results[sid] = s
        if "python" in ctx.wanted:
            results["python"] = safe(ctx, "python", run_python, ctx, cfg)
        return results, cfg
    # quick sections first; the transcript scan gets whatever time is left
    if "flag" in ctx.wanted:
        results["flag"] = safe(ctx, "flag", run_flag, ctx, cfg)
    if "python" in ctx.wanted:
        results["python"] = safe(ctx, "python", run_python, ctx, cfg)
    if "interpreters" in ctx.wanted:
        results["interpreters"] = safe(ctx, "interpreters", run_interpreters, ctx, cfg)
    if "weight" in ctx.wanted:
        results["weight"] = safe(ctx, "weight", run_weight, ctx, cfg)
    if "failures" in ctx.wanted or "injection" in ctx.wanted:
        try:
            scan = scan_transcripts(ctx)
            scan_err = None
        except Exception as exc:
            scan = None
            scan_err = type(exc).__name__
        for sid, fn in (("failures", run_failures), ("injection", run_injection)):
            if sid not in ctx.wanted:
                continue
            if scan is None:
                s = Section(sid)
                s.add("could", "internal-error", "could not check: internal error (%s)" % scan_err, None)
                s.summary = "internal error"
                results[sid] = s
            else:
                results[sid] = safe(ctx, sid, fn, ctx, cfg, scan)
    return results, cfg


LEVEL_ORDER = {"problem": 0, "could": 1, "note": 2}
STATUS_WORD = {"ok": "OK", "problem": "PROBLEM", "could_not_check": "COULD NOT CHECK"}
STATUS_JSON = {"ok": "ok", "problem": "problem", "could_not_check": "could not check"}


def render_text(ctx, results, notes):
    problems = sum(s.count("problem") for s in results.values())
    could = sum(s.count("could") for s in results.values())
    out = []
    out.append("dojo-doctor %s: read-only check; nothing was run, nothing was changed" % VERSION)
    out.append("config: %s | project: %s | window: %d days" % (tilde(ctx, ctx.config_dir), clean(ctx, tilde(ctx, ctx.project), 60), ctx.days))
    for n in notes:
        out.append("note: " + n)
    out.append("Summary: %d problems, %d could not check" % (problems, could))
    for i, sid in enumerate(SECTION_IDS, 1):
        sec = results.get(sid)
        if sec is None:
            continue
        out.append("")
        out.append("%d. %s: %s" % (i, SECTION_TITLES[sid], STATUS_WORD[sec.status]))
        if sec.summary:
            out.append("   " + sec.summary)
        for ln in sec.lines:
            out.append("   " + ln)
        items = sorted(sec.items, key=lambda it: LEVEL_ORDER[it["level"]])
        shown = items if ctx.show_all else items[: ctx.limit]
        for it in shown:
            tag = {"problem": "PROBLEM", "could": "could not check", "note": "note"}[it["level"]]
            out.append("   - [%s] %s: %s" % (tag, it["id"], it["text"]))
            if it["fix"]:
                out.append("       fix: %s" % it["fix"])
        if len(items) > len(shown):
            out.append("   ... %d more findings (use --all)" % (len(items) - len(shown)))
    out.append("")
    out.append(
        "Token figures are estimates (characters / 4). 'Could not check' means this run could not see, which is not the same as fine."
    )
    return "\n".join(out) + "\n"


def render_json(ctx, results, notes):
    problems = sum(s.count("problem") for s in results.values())
    could = sum(s.count("could") for s in results.values())
    doc = {
        "tool": "dojo-doctor",
        "version": VERSION,
        "read_only": True,
        "summary": {"problems": problems, "could_not_check": could},
        "notes": notes,
        "sections": {},
    }
    for sid in SECTION_IDS:
        sec = results.get(sid)
        if sec is None:
            continue
        doc["sections"][sid] = {
            "status": STATUS_JSON[sec.status],
            "summary": sec.summary,
            "lines": sec.lines,
            "items": sec.items,
            "data": sec.data,
        }
    return json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"


def main(argv=None, environ=None, out=None):
    out = out or sys.stdout
    argv = list(sys.argv[1:] if argv is None else argv)
    environ = dict(os.environ if environ is None else environ)
    notes = []
    strict = "--strict" in argv
    try:
        try:
            args, extra = parse_args(argv)
        except ArgError as exc:
            args, extra = parse_args([])
            notes.append("could not read arguments (%s); using defaults" % str(exc).strip()[:80])
        ctx = build_ctx(args, extra, environ, notes)
        results, _cfg = run_all(ctx)
        text = render_json(ctx, results, notes) if ctx.as_json else render_text(ctx, results, notes)
        out.write(text)
        out.flush()
        problems = sum(s.count("problem") for s in results.values())
        return 1 if (ctx.strict and problems) else 0
    except Exception as exc:
        out.write("dojo-doctor: could not check: internal error (%s)\n" % type(exc).__name__)
        out.flush()
        return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
