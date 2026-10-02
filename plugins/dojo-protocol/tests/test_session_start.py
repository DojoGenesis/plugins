"""Tests for the dojo-protocol plugin.

Run: cd plugins/dojo-protocol && python3 -m unittest discover -s tests -v

Hook tests feed hand-written JSON payloads to hooks/session_start.py in a
subprocess and assert on stdout and the exit code. Nothing here imports the
hook, and no expected value is produced by the code under test.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(PLUGIN, "hooks", "session_start.py")
PROTOCOL = os.path.join(PLUGIN, "PROTOCOL.md")
SYSTEM_PYTHON = "/usr/bin/python3"

# sha256 of the frozen protocol text (PROTOCOL.md must equal it exactly).
PROTOCOL_SHA256 = "5ac5703ed8869ec417e4499ac6859fdf16ee732e6e7d45c46fa94afa4b64dc62"
PROTOCOL_LAST_LINE = "A project's ./DOJO.md replaces this text. DOJO_PROTOCOL_OFF=1 turns it off."
PROMISE = (
    "The Dojo Protocol for Claude Code: ten rules at session start, a "
    "scout→contract→build→verify spine, and role agents pinned to the right model."
)
CAP_UNITS = 8000
SOURCES = ("startup", "resume", "clear", "compact", "fork")

CLUSTER_IDS = {
    "scout-position", "specify-commission", "dispatch-coordinate", "remember-continue",
    "seed-lifecycle", "system-prompt-intel", "repo-docs-health", "agent-telemetry",
    "learn-research", "understand-codebase", "forge", "govern-publish",
}
GRADER_KEYS = {
    "regex": {"type", "name", "target", "pattern", "flags", "match", "weight", "arm"},
    "tool_order": {"type", "name", "before", "after", "weight", "arm"},
    "tool_used": {"type", "name", "tool", "input_match", "min", "max", "weight", "arm"},
    "file_exists": {"type", "name", "path", "exists", "weight", "arm"},
    "llm": {"type", "name", "criteria", "focus", "weight", "arm"},
    "baseline": {"type", "name", "baseline_file", "criteria", "weight", "arm"},
}
# Required keys per grader type (the rest are optional).
GRADER_REQUIRED = {
    "regex": {"name", "pattern"},
    "tool_order": {"name", "before", "after"},
    "tool_used": {"name", "tool"},
    "file_exists": {"name", "path"},
    "llm": {"name", "criteria"},
    "baseline": {"name", "baseline_file", "criteria"},
}

EXPECTED_AGENTS = {
    "scout": ("haiku", "low", ["Read", "Glob", "Grep"], "15"),
    "builder": ("sonnet", "medium", ["Read", "Edit", "Write", "Bash", "Glob", "Grep"], "40"),
    "reviewer": ("sonnet", "medium", ["Read", "Glob", "Grep", "Bash"], "25"),
    "judge": ("opus", "xhigh", ["Read", "Glob", "Grep", "Bash"], "25"),
}
EXPECTED_SKILLS = {"protocol", "scout-first", "contract", "refute", "delegate"}
EXPECTED_EVALS = {"scout-before-edit", "cites-file-line", "no-edit-when-told", "trivial-fix-stays-inline"}

# Public vocabulary rules for shipped text (internal names are checked by the
# repo's denylist scanner, never listed here).
# The patterns are assembled from fragments so that this file does not itself
# contain the words it forbids; a repo-wide copy lint can then scan tests/ too.
LOWCOST_ROOT = "chea" + "p"
BANNED_PATTERNS = [
    "eco" + "system", "plat" + "form", "optimi" + r"[sz]\w*", "lever" + r"ag\w*", "power" + "ful",
    "super" + r"charg\w*", "seam" + r"less\w*", "works out of the " + "box",
    r"\b" + LOWCOST_ROOT + r"(er)?\b", r"\bsav" + r"ings?\b",
    r"\d+\s*%\s*(fewer|less|" + LOWCOST_ROOT + r"er|faster)", r"save\w*\s+\d+\s*%",
]
GENERIC_LEAK_PATTERNS = [
    r"/(?:Users|home)/[A-Za-z]",
    r"\b(?!UTF|SHA|ISO)[A-Z]{2,4}-\d+\b",
]


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def parse_frontmatter(path):
    """Strict key: value frontmatter. Fails on any line that is not one."""
    lines = read(path).splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError("%s: no frontmatter" % path)
    out = {}
    for i, line in enumerate(lines[1:], 2):
        if line == "---":
            body = "\n".join(lines[i:])
            return out, body
        m = re.match(r"^([A-Za-z][\w-]*): (.*)$", line)
        if not m:
            raise AssertionError("%s:%d: not a key: value line: %r" % (path, i, line))
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif ": " in value or value.startswith(("'", '"')):
            raise AssertionError("%s:%d: unquoted value needs quotes: %r" % (path, i, value))
        if m.group(1) in out:
            raise AssertionError("%s:%d: duplicate key" % (path, i))
        out[m.group(1)] = value
    raise AssertionError("%s: frontmatter never closed" % path)


def shipped_text_files(include_tests=False):
    for root, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        if not include_tests and os.path.relpath(root, PLUGIN).split(os.sep)[0] == "tests":
            dirs[:] = []
            continue
        for name in files:
            if name.endswith((".md", ".json", ".yaml", ".yml", ".py", ".txt")):
                yield os.path.join(root, name)


def u16(text):
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


class HookCase(unittest.TestCase):
    """Base class with helpers to run the hook in a subprocess."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="dojo-protocol-test-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.proj = os.path.join(self._tmp, "proj")
        os.mkdir(self.proj)
        self.home = os.path.join(self._tmp, "home")
        os.mkdir(self.home)

    def env(self, plugin_root=PLUGIN, **extra):
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": self.home,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if plugin_root is not None:
            env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def run_hook(self, stdin, env=None, python=None, timeout=10, cwd=None):
        if isinstance(stdin, (dict, list)):
            stdin = json.dumps(stdin)
        if isinstance(stdin, str):
            stdin = stdin.encode("utf-8")
        proc = subprocess.run(
            [python or sys.executable, HOOK],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env if env is not None else self.env(),
            cwd=cwd or self._tmp,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def payload(self, cwd=None, source="startup", **extra):
        data = {
            "session_id": "test-session-1",
            "transcript_path": os.path.join(self._tmp, "t.jsonl"),
            "cwd": self.proj if cwd is None else cwd,
            "hook_event_name": "SessionStart",
            "source": source,
        }
        data.update(extra)
        return data

    def write_dojo(self, content, name="DOJO.md"):
        path = os.path.join(self.proj, name)
        mode = "wb" if isinstance(content, bytes) else "w"
        kwargs = {} if isinstance(content, bytes) else {"encoding": "utf-8"}
        with open(path, mode, **kwargs) as handle:
            handle.write(content)
        return path

    def parsed(self, stdout):
        text = stdout.decode("ascii")
        self.assertTrue(text.endswith("\n"), "output must end with a newline")
        self.assertEqual(text.count("\n"), 1, "output must be exactly one line")
        return json.loads(text)

    def context_of(self, stdout):
        return self.parsed(stdout)["hookSpecificOutput"]["additionalContext"]

    def assert_protocol(self, stdout):
        data = self.parsed(stdout)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertEqual(data["hookSpecificOutput"]["additionalContext"], read(PROTOCOL))
        self.assertNotIn("systemMessage", data)

    def assert_silent(self, result):
        code, out, _err = result
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")


class TestInjection(HookCase):
    def test_injects_protocol_exact(self):
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_deterministic_across_sources(self):
        seen = set()
        for source in SOURCES:
            for _ in range(2):
                code, out, _ = self.run_hook(self.payload(source=source))
                self.assertEqual(code, 0, source)
                self.assert_protocol(out)
                seen.add(self.context_of(out))
        self.assertEqual(len(seen), 1)

    def test_protocol_md_canonical(self):
        with open(PROTOCOL, "rb") as handle:
            raw = handle.read()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PROTOCOL_SHA256)
        text = raw.decode("utf-8")
        self.assertLessEqual(len(text), 2600)
        self.assertTrue(text.endswith("\n"))
        numbers = [int(m.group(1)) for m in re.finditer(r"^(\d+)\. ", text, re.M)]
        self.assertEqual(numbers, list(range(1, 11)))
        self.assertEqual(text.rstrip("\n").splitlines()[-1], PROTOCOL_LAST_LINE)

    def test_dojo_md_replaces(self):
        self.write_dojo("MY RULES\n")
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        data = self.parsed(out)
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertTrue(context.startswith("Project protocol from ./DOJO.md"))
        self.assertIn("MY RULES", context)
        self.assertNotIn("Right model, every dispatch", context)
        self.assertTrue(data["systemMessage"].startswith("dojo-protocol: "))
        self.assertIn("DOJO.md", data["systemMessage"])

    def test_dojo_md_output_is_deterministic(self):
        self.write_dojo("MY RULES\n")
        first = self.run_hook(self.payload(source="startup"))[1]
        second = self.run_hook(self.payload(source="startup"))[1]
        self.assertEqual(first, second)

    def test_lowercase_dojo_md_is_not_picked_up(self):
        # The name must be exactly DOJO.md, also on a case-insensitive filesystem.
        self.write_dojo("LOWERCASE RULES\n", name="dojo.md")
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        data = self.parsed(out)
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("LOWERCASE RULES", context)
        self.assertIn("Right model, every dispatch", context)
        self.assertNotIn("systemMessage", data)

    def test_mixed_case_dojo_md_names_are_not_picked_up(self):
        for index, name in enumerate(("Dojo.md", "DOJO.MD", "dojo.MD")):
            with self.subTest(name):
                sub = os.path.join(self.proj, "case%d" % index)
                os.mkdir(sub)
                with open(os.path.join(sub, name), "w") as handle:
                    handle.write("WRONG NAME\n")
                code, out, _ = self.run_hook(self.payload(cwd=sub))
                self.assertEqual(code, 0)
                context = self.context_of(out)
                self.assertNotIn("WRONG NAME", context)
                self.assertIn("Right model, every dispatch", context)

    def test_exact_dojo_md_still_wins_beside_a_lowercase_file(self):
        self.write_dojo("EXACT RULES\n")
        self.write_dojo("other\n", name="dojo-notes.md")
        _code, out, _ = self.run_hook(self.payload())
        self.assertIn("EXACT RULES", self.context_of(out))

    def test_dojo_md_notice_only_at_startup_but_context_always(self):
        self.write_dojo("MY RULES\n")
        reference = None
        for source in SOURCES:
            with self.subTest(source):
                code, out, _ = self.run_hook(self.payload(source=source))
                self.assertEqual(code, 0)
                data = self.parsed(out)
                context = data["hookSpecificOutput"]["additionalContext"]
                self.assertIn("MY RULES", context)
                reference = reference or context
                self.assertEqual(context, reference)
                self.assertEqual("systemMessage" in data, source == "startup")
        payload = self.payload()
        del payload["source"]
        self.assertIn("systemMessage", self.parsed(self.run_hook(payload)[1]))

    def test_dojo_md_cut_notice_also_only_at_startup(self):
        self.write_dojo("a" * 20000)
        data = self.parsed(self.run_hook(self.payload(source="compact"))[1])
        self.assertNotIn("systemMessage", data)
        self.assertIn("was cut here at the size cap", data["hookSpecificOutput"]["additionalContext"])

    def test_dojo_md_cap_utf16(self):
        for label, unit in (("ascii", "a"), ("emoji", "\U0001F600")):
            with self.subTest(label):
                chars = 1000000 if unit == "a" else 250000
                self.write_dojo((unit * chars) + "\n")
                started = time.time()
                code, out, _ = self.run_hook(self.payload(), timeout=10)
                self.assertLess(time.time() - started, 5)
                self.assertEqual(code, 0)
                data = self.parsed(out)
                context = data["hookSpecificOutput"]["additionalContext"]
                self.assertLessEqual(u16(context), CAP_UNITS)
                self.assertGreater(u16(context), CAP_UNITS - 400)
                self.assertIn("was cut here at the size cap", context)
                self.assertIn("cut at", data["systemMessage"])
                self.assertEqual(out, self.run_hook(self.payload())[1])

    def test_dojo_md_just_under_cap_is_not_cut(self):
        self.write_dojo("x" * 7000)
        _code, out, _ = self.run_hook(self.payload())
        data = self.parsed(out)
        self.assertNotIn("size cap", data["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("cut at", data["systemMessage"])

    def test_dojo_md_symlink_outside_root_is_refused(self):
        outside = os.path.join(self._tmp, "outside-secret.txt")
        with open(outside, "w") as handle:
            handle.write("SECRET-CANARY-VALUE\n")
        os.symlink(outside, os.path.join(self.proj, "DOJO.md"))
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        self.assertNotIn(b"SECRET-CANARY-VALUE", out)
        self.assert_protocol(out)

    def test_dojo_md_symlink_inside_root_is_accepted(self):
        # Decision: a symlink whose real path stays inside the project root is used.
        self.write_dojo("INSIDE RULES\n", name="rules.md")
        os.symlink("rules.md", os.path.join(self.proj, "DOJO.md"))
        _code, out, _ = self.run_hook(self.payload())
        self.assertIn("INSIDE RULES", self.context_of(out))

    def test_dojo_md_fifo_does_not_hang(self):
        os.mkfifo(os.path.join(self.proj, "DOJO.md"))
        started = time.time()
        code, out, _ = self.run_hook(self.payload(), timeout=5)
        self.assertLess(time.time() - started, 5)
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_regular_file_guard_refuses_a_non_regular_descriptor(self):
        # Defense in depth. A device or FIFO cannot be reached through an in-root path
        # in a test, so the descriptor's mode is faked: a file that is regular on disk
        # but reports as a FIFO must be refused, and a regular mode must be read.
        spec = importlib.util.spec_from_file_location("dojo_session_start_under_test", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        self.write_dojo("REAL RULES\n")
        self.assertEqual(hook.read_dojo_md(self.proj), ("REAL RULES", False))
        for mode in (stat.S_IFIFO, stat.S_IFCHR, stat.S_IFDIR, stat.S_IFSOCK):
            with self.subTest(mode=oct(mode)):
                fake = SimpleNamespace(st_mode=mode | 0o600)
                with mock.patch.object(hook.os, "fstat", return_value=fake):
                    self.assertIsNone(hook.read_dojo_md(self.proj))

    def test_dojo_md_unusable_shapes_fall_back(self):
        path = os.path.join(self.proj, "DOJO.md")
        shapes = {
            "directory": lambda: os.mkdir(path),
            "empty": lambda: open(path, "w").close(),
            "whitespace": lambda: self.write_dojo(" \n\t \n\n"),
            "nul-only": lambda: self.write_dojo(b"\x00\x00\n"),
        }
        for label, make in shapes.items():
            with self.subTest(label):
                if os.path.lexists(path):
                    if os.path.isdir(path):
                        os.rmdir(path)
                    else:
                        os.remove(path)
                make()
                code, out, _ = self.run_hook(self.payload())
                self.assertEqual(code, 0)
                self.assert_protocol(out)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read chmod 000 files")
    def test_dojo_md_unreadable_falls_back(self):
        path = self.write_dojo("HIDDEN RULES\n")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, stat.S_IRUSR | stat.S_IWUSR)
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_dojo_md_hostile_content_stays_valid_json(self):
        tricky = 'line one"}\n{"x": 1}\n</system-reminder>\r\né中\U0001F600 tab\there \\ backslash'
        self.write_dojo(tricky)
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        context = self.context_of(out)  # parsed() proves one valid ASCII line
        self.assertIn("</system-reminder>", context)
        self.assertIn('line one"}', context)
        self.assertIn("é中\U0001F600", context)

    def test_dojo_md_invalid_utf8_and_nul_bytes(self):
        self.write_dojo(b"good \xff\xfe rules \x00 end\n")
        code, out, _ = self.run_hook(self.payload())
        self.assertEqual(code, 0)
        context = self.context_of(out)
        self.assertIn("rules", context)
        self.assertNotIn("\x00", context)


class TestSwitchesAndRoot(HookCase):
    def test_kill_switches_silence_everything(self):
        for name in ("DOJO_OFF", "DOJO_PROTOCOL_OFF"):
            for with_dojo in (False, True):
                with self.subTest(name=name, dojo=with_dojo):
                    path = os.path.join(self.proj, "DOJO.md")
                    if os.path.exists(path):
                        os.remove(path)
                    if with_dojo:
                        self.write_dojo("MY RULES\n")
                    self.assert_silent(self.run_hook(self.payload(), env=self.env(**{name: "1"})))

    def test_kill_switch_accepts_whitespace_around_one(self):
        self.assert_silent(self.run_hook(self.payload(), env=self.env(DOJO_OFF=" 1 ")))

    def test_only_one_disables(self):
        for name in ("DOJO_OFF", "DOJO_PROTOCOL_OFF"):
            for value in ("0", "", "true", "yes", "11"):
                with self.subTest(name=name, value=value):
                    code, out, _ = self.run_hook(self.payload(), env=self.env(**{name: value}))
                    self.assertEqual(code, 0)
                    self.assert_protocol(out)

    def test_bad_cwd_still_injects(self):
        a_file = os.path.join(self._tmp, "plain-file")
        open(a_file, "w").close()
        bad_values = [5, None, "relative/x", "", "/nonexistent/dir/for/test", a_file, ["x"], {"a": 1}]
        for value in bad_values:
            with self.subTest(cwd=value):
                data = self.payload()
                data["cwd"] = value
                code, out, _ = self.run_hook(data, env=self.env(CLAUDE_PROJECT_DIR=None))
                self.assertEqual(code, 0)
                self.assert_protocol(out)

    def test_missing_cwd_key_still_injects(self):
        data = self.payload()
        del data["cwd"]
        code, out, _ = self.run_hook(data, env=self.env(CLAUDE_PROJECT_DIR=None))
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_cwd_missing_uses_project_dir_env(self):
        self.write_dojo("ENV PROJECT RULES\n")
        data = self.payload()
        del data["cwd"]
        _code, out, _ = self.run_hook(data, env=self.env(CLAUDE_PROJECT_DIR=self.proj))
        self.assertIn("ENV PROJECT RULES", self.context_of(out))

    def test_bad_cwd_falls_back_to_project_dir_env(self):
        self.write_dojo("ENV PROJECT RULES\n")
        _code, out, _ = self.run_hook(self.payload(cwd="relative/x"), env=self.env(CLAUDE_PROJECT_DIR=self.proj))
        self.assertIn("ENV PROJECT RULES", self.context_of(out))

    def test_relative_cwd_is_never_used_as_a_root(self):
        # "." is a directory and would resolve against the hook's own cwd, which
        # holds a DOJO.md here. It must be ignored: protocol, or the env root.
        hook_cwd = os.path.join(self._tmp, "hook-cwd")
        os.mkdir(hook_cwd)
        with open(os.path.join(hook_cwd, "DOJO.md"), "w") as handle:
            handle.write("RELATIVE CWD RULES\n")
        for value in (".", "./", "hook-cwd", ".."):
            with self.subTest(cwd=value):
                code, out, _ = self.run_hook(
                    self.payload(cwd=value), env=self.env(CLAUDE_PROJECT_DIR=None), cwd=hook_cwd)
                self.assertEqual(code, 0)
                self.assert_protocol(out)
        self.write_dojo("ENV ROOT RULES\n")
        _code, out, _ = self.run_hook(
            self.payload(cwd="."), env=self.env(CLAUDE_PROJECT_DIR=self.proj), cwd=hook_cwd)
        context = self.context_of(out)
        self.assertIn("ENV ROOT RULES", context)
        self.assertNotIn("RELATIVE CWD RULES", context)

    def test_payload_cwd_wins_over_project_dir_env(self):
        other = os.path.join(self._tmp, "other")
        os.mkdir(other)
        with open(os.path.join(other, "DOJO.md"), "w") as handle:
            handle.write("OTHER RULES\n")
        self.write_dojo("PAYLOAD RULES\n")
        _code, out, _ = self.run_hook(self.payload(), env=self.env(CLAUDE_PROJECT_DIR=other))
        context = self.context_of(out)
        self.assertIn("PAYLOAD RULES", context)
        self.assertNotIn("OTHER RULES", context)

    def test_valid_cwd_without_dojo_md_ignores_env_dojo_md(self):
        other = os.path.join(self._tmp, "other")
        os.mkdir(other)
        with open(os.path.join(other, "DOJO.md"), "w") as handle:
            handle.write("OTHER RULES\n")
        code, out, _ = self.run_hook(self.payload(), env=self.env(CLAUDE_PROJECT_DIR=other))
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_does_not_walk_up_to_parent_dojo_md(self):
        with open(os.path.join(self.proj, "DOJO.md"), "w") as handle:
            handle.write("ROOT RULES\n")
        sub = os.path.join(self.proj, "sub")
        os.mkdir(sub)
        code, out, _ = self.run_hook(self.payload(cwd=sub))
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_hook_does_not_write_into_the_project(self):
        self.write_dojo("MY RULES\n")
        before = sorted(os.listdir(self.proj))
        self.run_hook(self.payload())
        self.assertEqual(sorted(os.listdir(self.proj)), before)


class TestFailOpen(HookCase):
    def test_unparseable_input_is_silent(self):
        for label, raw in (
            ("not json", b"not json"),
            ("empty", b""),
            ("array", b"[]"),
            ("null", b"null"),
            ("number", b"42"),
            ("string", b'"hello"'),
            ("non-utf8", b"\xff\xfe\x00{"),
            ("truncated", b'{"cwd": "/tm'),
        ):
            with self.subTest(label):
                code, out, err = self.run_hook(raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, b"")
                self.assertNotIn(b"Traceback", err)

    def test_empty_object_still_injects(self):
        code, out, _ = self.run_hook(b"{}", env=self.env(CLAUDE_PROJECT_DIR=None))
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_missing_protocol_file_is_silent(self):
        empty = os.path.join(self._tmp, "empty-root")
        os.mkdir(empty)
        self.assert_silent(self.run_hook(self.payload(), env=self.env(plugin_root=empty)))

    def test_empty_protocol_file_is_silent(self):
        root = os.path.join(self._tmp, "blank-root")
        os.mkdir(root)
        with open(os.path.join(root, "PROTOCOL.md"), "w") as handle:
            handle.write("  \n")
        self.assert_silent(self.run_hook(self.payload(), env=self.env(plugin_root=root)))

    def test_unset_plugin_root_falls_back_to_file_location(self):
        code, out, _ = self.run_hook(self.payload(), env=self.env(plugin_root=None))
        self.assertEqual(code, 0)
        self.assert_protocol(out)

    def test_missing_protocol_file_still_uses_dojo_md(self):
        empty = os.path.join(self._tmp, "empty-root")
        os.mkdir(empty)
        self.write_dojo("MY RULES\n")
        _code, out, _ = self.run_hook(self.payload(), env=self.env(plugin_root=empty))
        self.assertIn("MY RULES", self.context_of(out))


@unittest.skipUnless(os.path.exists(SYSTEM_PYTHON), "no system python3")
class TestSystemPython(HookCase):
    def test_env_i_system_python_matches(self):
        self.write_dojo("café 中文 \U0001F600 rules\n")
        payload = json.dumps(self.payload()).encode("utf-8")
        clean = subprocess.run(
            ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "HOME=" + self.home, SYSTEM_PYTHON, HOOK],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self._tmp, timeout=15,
        )
        self.assertEqual(clean.returncode, 0, clean.stderr)
        clean.stdout.decode("ascii")  # pure ASCII on any locale
        reference = self.run_hook(payload)  # whatever python3 is first on PATH
        self.assertEqual(reference[0], 0)
        self.assertEqual(clean.stdout, reference[1])
        self.assertIn("café 中文 \U0001F600", self.context_of(clean.stdout))

    def test_env_i_system_python_plain_protocol(self):
        payload = json.dumps(self.payload()).encode("utf-8")
        clean = subprocess.run(
            ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "HOME=" + self.home, SYSTEM_PYTHON, HOOK],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self._tmp, timeout=15,
        )
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assert_protocol(clean.stdout)

    def test_python_compiles_under_system_python(self):
        files = [p for p in shipped_text_files(include_tests=True) if p.endswith(".py")]
        self.assertTrue(files)
        out_dir = tempfile.mkdtemp(prefix="dojo-protocol-pyc-")
        self.addCleanup(shutil.rmtree, out_dir, True)
        code = "import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)"
        for i, path in enumerate(files):
            proc = subprocess.run(
                [SYSTEM_PYTHON, "-c", code, path, os.path.join(out_dir, "%d.pyc" % i)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            )
            self.assertEqual(proc.returncode, 0, "%s: %s" % (path, proc.stderr.decode()))


class TestManifestAndComponents(unittest.TestCase):
    def test_plugin_json(self):
        data = json.loads(read(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
        self.assertEqual(data["name"], "dojo-protocol")
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual(data["description"], PROMISE)
        self.assertLessEqual(len(data["description"]), 200)
        self.assertEqual(data["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(data["homepage"], "https://dojogenesis.com/suite#dojo-protocol")
        self.assertEqual(data["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(data["license"], "Apache-2.0")
        self.assertTrue(data["keywords"])
        self.assertNotIn("userConfig", data)
        self.assertNotIn("modules", data)
        self.assertTrue(os.path.isdir(os.path.join(PLUGIN, data["experimental"]["evals"])))

    def test_hooks_json_shape(self):
        data = json.loads(read(os.path.join(PLUGIN, "hooks", "hooks.json")))
        self.assertNotIn("modules", data)
        self.assertEqual(list(data["hooks"].keys()), ["SessionStart"])
        groups = data["hooks"]["SessionStart"]
        self.assertEqual(len(groups), 1)
        self.assertNotIn("matcher", groups[0])
        self.assertEqual(len(groups[0]["hooks"]), 1)
        entry = groups[0]["hooks"][0]
        self.assertEqual(entry["type"], "command")
        self.assertEqual(entry["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"')
        self.assertIsInstance(entry["timeout"], int)
        self.assertLessEqual(entry["timeout"], 10)
        self.assertTrue(os.path.isfile(HOOK))
        self.assertNotRegex(entry["command"], r"^python\s")

    def test_agents_frontmatter(self):
        agents_dir = os.path.join(PLUGIN, "agents")
        self.assertEqual(sorted(os.listdir(agents_dir)), sorted(n + ".md" for n in EXPECTED_AGENTS))
        for name, (model, effort, tools, turns) in EXPECTED_AGENTS.items():
            with self.subTest(name):
                path = os.path.join(agents_dir, name + ".md")
                fm, body = parse_frontmatter(path)
                self.assertEqual(fm["name"], name)
                self.assertEqual(fm["model"], model)
                self.assertIn(fm["model"], ("haiku", "sonnet", "opus"))
                self.assertEqual(fm["effort"], effort)
                self.assertEqual([t.strip() for t in fm["tools"].split(",")], tools)
                self.assertEqual(fm["maxTurns"], turns)
                self.assertLessEqual(len(fm["description"]), 200)
                self.assertTrue(body.strip())
                if name == "scout":
                    for forbidden in ("Edit", "Write", "Bash"):
                        self.assertNotIn(forbidden, tools)
                if name in ("reviewer", "judge"):
                    self.assertIn("no defects found", body)

    def test_agent_bodies_carry_their_own_rules(self):
        # Subagents never receive the session-start text.
        for name in EXPECTED_AGENTS:
            _fm, body = parse_frontmatter(os.path.join(PLUGIN, "agents", name + ".md"))
            self.assertNotIn("follow the Dojo Protocol", body)
        _fm, builder = parse_frontmatter(os.path.join(PLUGIN, "agents", "builder.md"))
        for needle in ("done-check", "exit code", "git add"):
            self.assertIn(needle, builder)
        _fm, scout = parse_frontmatter(os.path.join(PLUGIN, "agents", "scout.md"))
        self.assertIn("path:line", scout)
        self.assertIn("not found", scout)

    def test_skills_and_budget(self):
        skills_dir = os.path.join(PLUGIN, "skills")
        self.assertEqual(set(os.listdir(skills_dir)), EXPECTED_SKILLS)
        self.assertLessEqual(len(EXPECTED_SKILLS), 5)
        verbs = {"Use", "Write", "Review", "Search", "Brief", "Apply", "Map", "Find", "Run", "Settle"}
        total = 0
        for name in EXPECTED_SKILLS:
            with self.subTest(name):
                path = os.path.join(skills_dir, name, "SKILL.md")
                fm, body = parse_frontmatter(path)
                self.assertEqual(fm["name"], name)
                self.assertLessEqual(len(fm["description"]), 250)
                self.assertTrue(fm["description"].startswith("Use when") or fm["description"].split()[0] in verbs)
                self.assertIn(fm["category"], CLUSTER_IDS)
                self.assertLessEqual(len(read(path).encode("utf-8")), 6 * 1024)
                total += len(fm["description"])
        for name in EXPECTED_AGENTS:
            fm, _body = parse_frontmatter(os.path.join(PLUGIN, "agents", name + ".md"))
            total += len(fm["description"])
        self.assertLess(total, 1000)
        self.assertLessEqual(total, 900, "always-on description weight target is <= 900 (got %d)" % total)
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "commands")))

    def test_skill_reference_files_exist(self):
        for rel in ("skills/contract/contract-template.md", "skills/delegate/brief-template.md"):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, rel)), rel)
            self.assertLessEqual(len(read(os.path.join(PLUGIN, rel)).encode("utf-8")), 6 * 1024)

    def test_no_protocol_copy(self):
        long_lines = [l.strip() for l in read(PROTOCOL).splitlines() if len(l.strip()) > 40]
        self.assertGreater(len(long_lines), 5)
        for path in shipped_text_files():
            if os.path.abspath(path) == PROTOCOL:
                continue
            text = read(path)
            for line in long_lines:
                self.assertNotIn(line, text, "%s copies a PROTOCOL.md line" % os.path.relpath(path, PLUGIN))

    def test_skills_do_not_depend_on_unlisted_files(self):
        pattern = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)")
        docs = [os.path.join(PLUGIN, "README.md"), os.path.join(PLUGIN, "output-styles", "status-and-path.md")]
        for root, _dirs, files in os.walk(os.path.join(PLUGIN, "skills")):
            docs += [os.path.join(root, f) for f in files if f.endswith(".md")]
        for path in docs:
            for rel in pattern.findall(read(path)):
                rel = rel.rstrip(".")
                self.assertTrue(os.path.exists(os.path.join(PLUGIN, rel)), "%s -> %s" % (path, rel))

    def test_relative_markdown_links_resolve(self):
        link = re.compile(r"\]\((?!https?:|#|mailto:)([^)\s#]+)")
        for path in (os.path.join(PLUGIN, "README.md"),):
            for rel in link.findall(read(path)):
                self.assertTrue(os.path.exists(os.path.join(os.path.dirname(path), rel)), rel)

    def test_output_style(self):
        fm, body = parse_frontmatter(os.path.join(PLUGIN, "output-styles", "status-and-path.md"))
        self.assertEqual(fm["name"], "status-and-path")
        self.assertEqual(fm["keep-coding-instructions"], "true")
        self.assertNotIn("force-for-plugin", fm)
        self.assertTrue(body.strip())

    def test_public_vocabulary_and_generic_leaks(self):
        banned = [re.compile(p, re.I) for p in BANNED_PATTERNS]
        leaks = [re.compile(p) for p in GENERIC_LEAK_PATTERNS]
        checked = 0
        for path in shipped_text_files():
            text = read(path)
            checked += 1
            for rx in banned:
                m = rx.search(text)
                self.assertIsNone(m, "%s: banned vocabulary %r" % (os.path.relpath(path, PLUGIN), rx.pattern))
            for rx in leaks:
                m = rx.search(text)
                self.assertIsNone(m, "%s: leak pattern %r" % (os.path.relpath(path, PLUGIN), rx.pattern))
        self.assertGreater(checked, 15)

    def test_superlative_stays_confined_to_the_frozen_protocol_text(self):
        # Rule 7 of the frozen text uses the superlative of the banned word, in the
        # sense of effort, not price. The banned-word pattern uses a word boundary
        # and does not match it. Keep it out of every other shipped file.
        for path in shipped_text_files():
            if os.path.abspath(path) == PROTOCOL:
                continue
            self.assertNotIn(LOWCOST_ROOT + "est", read(path).lower(), os.path.relpath(path, PLUGIN))

    def test_tests_directory_is_clean_of_banned_vocabulary(self):
        banned = [re.compile(p, re.I) for p in BANNED_PATTERNS]
        for path in shipped_text_files(include_tests=True):
            if os.path.abspath(path) == PROTOCOL:
                continue
            text = read(path)
            for rx in banned:
                self.assertIsNone(rx.search(text), "%s: %r" % (os.path.relpath(path, PLUGIN), rx.pattern))

    def test_readme_makes_no_unproven_size_number(self):
        readme = read(os.path.join(PLUGIN, "README.md"))
        self.assertNotIn("10,000", readme)
        self.assertNotIn("10000", read(HOOK))
        self.assertNotIn("10,000", read(HOOK))
        # The only size number the README states is the cap the tests prove.
        self.assertIn("8,000 characters", readme)

    def test_docs_name_agents_by_qualified_id(self):
        ids = "scout|builder|reviewer|judge"
        # Backticked, double- or single-quoted bare ids, and subagent_type values.
        bare = re.compile(
            r"(`|\"|')(%s)\1|subagent_type\W+(%s)\b" % (ids, ids)
        )
        paths = [os.path.join(PLUGIN, "README.md")]
        for root, _dirs, files in os.walk(os.path.join(PLUGIN, "skills")):
            paths += [os.path.join(root, f) for f in files if f.endswith(".md")]
        paths.append(os.path.join(PLUGIN, "output-styles", "status-and-path.md"))
        for path in paths:
            with self.subTest(os.path.relpath(path, PLUGIN)):
                self.assertIsNone(bare.search(read(path)), "bare agent id in %s" % path)
        readme = read(os.path.join(PLUGIN, "README.md"))
        for name in EXPECTED_AGENTS:
            self.assertIn("`dojo-protocol:%s`" % name, readme)
        brief = read(os.path.join(PLUGIN, "skills", "delegate", "brief-template.md"))
        for name in EXPECTED_AGENTS:
            self.assertIn("dojo-protocol:%s" % name, brief)

    def test_qualified_id_pattern_catches_each_bare_form(self):
        ids = "scout|builder|reviewer|judge"
        bare = re.compile(r"(`|\"|')(%s)\1|subagent_type\W+(%s)\b" % (ids, ids))
        for text in (
            "`scout`",
            '"reviewer"',
            "'judge'",
            'subagent_type "reviewer"',
            "subagent_type: builder",
            "subagent_type='scout'",
            'subagent_type = "judge"',
        ):
            with self.subTest(text):
                self.assertIsNotNone(bare.search(text))
        for text in (
            "`dojo-protocol:scout`",
            'subagent_type "dojo-protocol:reviewer"',
            "the scout agent role",
        ):
            with self.subTest(text):
                self.assertIsNone(bare.search(text))

    def test_refute_skill_replaces_the_old_review_skill(self):
        fm, body = parse_frontmatter(os.path.join(PLUGIN, "skills", "refute", "SKILL.md"))
        self.assertEqual(fm["name"], "refute")
        self.assertIn("no defects found", body)
        self.assertIn("`refute`", read(os.path.join(PLUGIN, "skills", "protocol", "SKILL.md")))
        self.assertIn("`refute`", read(os.path.join(PLUGIN, "README.md")))
        old = "adversarial" + "-review"
        for path in shipped_text_files(include_tests=True):
            self.assertNotIn(old, read(path), os.path.relpath(path, PLUGIN))

    def test_readme_counts_match_disk(self):
        readme = read(os.path.join(PLUGIN, "README.md"))
        counts = {
            "Agents": len([f for f in os.listdir(os.path.join(PLUGIN, "agents")) if f.endswith(".md")]),
            "Skills": len(os.listdir(os.path.join(PLUGIN, "skills"))),
            "Output style": len(os.listdir(os.path.join(PLUGIN, "output-styles"))),
            "Eval scaffolds": len(os.listdir(os.path.join(PLUGIN, "evals"))),
        }
        for label, count in counts.items():
            m = re.search(r"^\| %s \| (\d+) \|" % re.escape(label), readme, re.M)
            self.assertIsNotNone(m, label)
            self.assertEqual(int(m.group(1)), count, label)
        self.assertIn("Tested with Claude Code 2.1.286", readme)
        self.assertIn("PROTOCOL.md", readme)


class TestEvalScaffolds(unittest.TestCase):
    def load_case(self, name):
        path = os.path.join(PLUGIN, "evals", name, "case.yaml")
        text = "".join(line for line in read(path).splitlines(True) if not line.startswith("#"))
        return json.loads(text)

    def test_cases_present(self):
        self.assertEqual(set(os.listdir(os.path.join(PLUGIN, "evals"))), EXPECTED_EVALS)

    def test_cases_match_the_strict_schema(self):
        for name in sorted(EXPECTED_EVALS):
            with self.subTest(name):
                case = self.load_case(name)
                self.assertIsInstance(case["schema_version"], str)
                self.assertEqual(case["name"], name)
                self.assertLessEqual(case.get("runs", 3), 50)
                self.assertTrue(case["execution"]["prompt"].strip())
                self.assertLessEqual(case["execution"].get("max_turns", 10), 200)
                self.assertLessEqual(case["execution"].get("timeout_seconds", 300), 3600)
                self.assertNotIn(LOWCOST_ROOT, json.dumps(case).lower())
                allowed_exec = {"prompt", "max_turns", "timeout_seconds", "model", "allowed_tools",
                                "artifact_publish", "growthbook_overrides", "append_system_prompt", "env"}
                self.assertTrue(set(case["execution"]) <= allowed_exec)
                self.assertTrue(set(case.get("context", {})) <= {"scaffold_script", "history_file", "add_dirs"})
                self.assertGreaterEqual(len(case["graders"]), 1)
                names = [g["name"] for g in case["graders"]]
                self.assertEqual(len(names), len(set(names)), "duplicate grader names")
                for grader in case["graders"]:
                    kind = grader["type"]
                    self.assertIn(kind, GRADER_KEYS)
                    self.assertTrue(set(grader) <= GRADER_KEYS[kind], "%s: unknown keys %s" % (
                        grader["name"], set(grader) - GRADER_KEYS[kind]))
                    self.assertTrue((GRADER_REQUIRED[kind] | {"type"}) <= set(grader), grader["name"])
                    if kind == "regex":
                        re.compile(grader["pattern"])
                    if kind == "tool_used":
                        self.assertTrue(isinstance(grader.get("min", 1), int) and isinstance(grader.get("max", 0), int))

    def test_scaffold_script_present_where_a_fixture_is_needed(self):
        for name in ("cites-file-line", "no-edit-when-told", "trivial-fix-stays-inline"):
            script = self.load_case(name)["context"].get("scaffold_script", "")
            self.assertIn("src/client.py", script, name)
        wide = self.load_case("scout-before-edit")["context"].get("scaffold_script", "")
        for path in ("src/net/config.py", "src/net/client.py", "src/jobs/worker.py", "tests/test_client.py",
                     "docs/usage.md"):
            self.assertIn(path, wide)

    def fixture_files(self, name):
        script = self.load_case(name)["context"].get("scaffold_script", "")
        return set(re.findall(r"> (\S+)", script))

    def test_cases_do_not_contradict_each_other(self):
        # A run that follows the protocol must be able to pass every case. A case that
        # requires a subagent and a case that forbids one may not share a task size.
        needs_agent, forbids_agent = [], []
        for name in sorted(EXPECTED_EVALS):
            for grader in self.load_case(name)["graders"]:
                if grader["type"] == "tool_used" and grader["tool"] == "Agent":
                    if grader.get("min", 1) >= 1:
                        needs_agent.append(name)
                    if grader.get("max") == 0:
                        forbids_agent.append(name)
        self.assertEqual(needs_agent, ["scout-before-edit"])
        self.assertEqual(forbids_agent, ["trivial-fix-stays-inline"])
        wide, small = self.fixture_files("scout-before-edit"), self.fixture_files("trivial-fix-stays-inline")
        self.assertGreaterEqual(len(wide), 6)
        self.assertLessEqual(len(small), 2)
        self.assertNotEqual(
            self.load_case("scout-before-edit")["execution"]["prompt"],
            self.load_case("trivial-fix-stays-inline")["execution"]["prompt"],
        )
        # The scout case asks for edits in at least three files; the small case, one.
        graders = " ".join(g.get("criteria", "") for g in self.load_case("scout-before-edit")["graders"])
        for path in ("src/net/config.py", "tests/test_client.py", "tests/test_worker.py", "docs/usage.md"):
            self.assertIn(path, graders)
        self.assertIn("src/client.py", self.load_case("trivial-fix-stays-inline")["execution"]["prompt"])

    def test_header_comment_names_only_the_gated_tools_the_case_allows(self):
        for name in sorted(EXPECTED_EVALS):
            path = os.path.join(PLUGIN, "evals", name, "case.yaml")
            header = " ".join(line for line in read(path).splitlines() if line.startswith("#"))
            allowed = self.load_case(name)["execution"]["allowed_tools"]
            with self.subTest(name):
                self.assertEqual("--allow-tools Edit Write" in header, "Write" in allowed)
                if "Edit" not in allowed:
                    self.assertNotIn("--allow-tools", header)

    def test_every_tool_used_grader_can_pass(self):
        # The eval runner grades tool_used as count >= (min, default 1) and
        # count <= (max, default unbounded). A grader whose range is empty
        # fails in every run, whatever the model does.
        seen = 0
        for name in sorted(EXPECTED_EVALS):
            for grader in self.load_case(name)["graders"]:
                if grader["type"] != "tool_used":
                    continue
                seen += 1
                lo = grader.get("min", 1)
                hi = grader.get("max", float("inf"))
                with self.subTest("%s/%s" % (name, grader["name"])):
                    self.assertLessEqual(lo, hi, "pass range %s..%s is empty" % (lo, hi))
        self.assertGreaterEqual(seen, 4)

    def test_must_not_call_graders_pass_on_zero_calls_in_both_arms(self):
        # A "must not call" check needs min 0, max 0 and arm both (the runner's
        # default min is 1, and without arm both only one arm is graded).
        found = []
        for name in sorted(EXPECTED_EVALS):
            for grader in self.load_case(name)["graders"]:
                if grader["type"] == "tool_used" and grader.get("max") == 0:
                    found.append("%s/%s" % (name, grader["name"]))
                    with self.subTest(found[-1]):
                        self.assertEqual(grader.get("min"), 0)
                        self.assertEqual(grader.get("arm"), "both")
        self.assertEqual(sorted(found), [
            "no-edit-when-told/no-edit-calls",
            "no-edit-when-told/no-write-calls",
            "trivial-fix-stays-inline/no-subagent",
        ])

    def test_scout_before_edit_graders(self):
        case = self.load_case("scout-before-edit")
        self.assertNotIn("one-line", case["description"])
        self.assertIn("wide question", case["description"])
        used = [g for g in case["graders"] if g["type"] == "tool_used"][0]
        self.assertEqual(used["tool"], "Agent")
        self.assertEqual(used["input_match"], "dojo-protocol:scout")
        self.assertGreaterEqual(used["min"], 1)
        order = [g for g in case["graders"] if g["type"] == "tool_order"][0]
        self.assertEqual(order["before"]["tool"], "Agent")
        self.assertEqual(order["after"]["tool"], "Edit")
        self.assertIn("Edit", case["execution"]["allowed_tools"])

    def test_cites_file_line_graders(self):
        case = self.load_case("cites-file-line")
        rx = [g for g in case["graders"] if g["type"] == "regex"][0]
        self.assertEqual(rx["target"], "last_message")
        pattern = re.compile(rx["pattern"])
        self.assertTrue(pattern.search("src/client.py:1"))
        self.assertIsNone(pattern.search("it is defined in the client module"))
        self.assertTrue([g for g in case["graders"] if g["type"] == "llm"])

    def test_no_edit_when_told_can_actually_fail(self):
        case = self.load_case("no-edit-when-told")
        allowed = case["execution"]["allowed_tools"]
        self.assertIn("Edit", allowed)
        self.assertIn("Write", allowed)
        by_tool = {g["tool"]: g for g in case["graders"] if g["type"] == "tool_used"}
        for tool in ("Edit", "Write"):
            self.assertEqual(by_tool[tool].get("min"), 0)
            self.assertEqual(by_tool[tool].get("max"), 0)
            self.assertEqual(by_tool[tool].get("arm"), "both")
        self.assertIn("do not edit", case["execution"]["prompt"].lower())

    def test_trivial_fix_stays_inline_graders(self):
        case = self.load_case("trivial-fix-stays-inline")
        agent = [g for g in case["graders"] if g["type"] == "tool_used" and g["tool"] == "Agent"][0]
        self.assertEqual(agent["min"], 0)
        self.assertEqual(agent["max"], 0)
        self.assertEqual(agent["arm"], "both")
        self.assertIn("Agent", case["execution"]["allowed_tools"])


if __name__ == "__main__":
    unittest.main()
