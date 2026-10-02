"""Tests for suite_lint.py. Run: python3 -m unittest discover -s tests_suite -t .  (from scripts/)"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from . import _helpers as H
except ImportError:  # discovered with tests_suite as the top-level directory
    import _helpers as H

import suite_lint as SL

DELETE = H.DELETE


def _py39_is_old():
    try:
        out = subprocess.run([H.PY39, "-c", "import sys; print(sys.version_info[1])"], stdout=subprocess.PIPE).stdout
        return int(out.strip()) < 10
    except Exception:
        return False


PY39_OLD = _py39_is_old()


def fm(**kw):
    """Frontmatter text from keyword fields; DELETE omits a field."""
    lines = ["---"]
    for k, v in kw.items():
        if v is DELETE:
            continue
        lines.append("%s: %s" % (k.replace("_", "-") if k == "allowed_tools" else k, v))
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# A clean plugin
# ---------------------------------------------------------------------------

class TestGoodPlugin(H.Base):
    def test_clean_fixture_exits_zero(self):
        r = self.lint_plugin()
        self.assertEqual(r.rc, 0, r.out)
        self.assertEqual(r.lines[-1].split(": ", 1)[1].split(", ")[2], "0 error(s)")
        self.assertEqual(len(r.lines), 1, r.out)
        self.assertEqual(self.no_pycache(), [])

    def test_clean_suite_named_fixture(self):
        r = self.lint_plugin("dojo-gates")
        self.assertEqual(r.rc, 0, r.out)

    def test_warnings_never_change_the_exit_code(self):
        hooks = H.good_hooks()
        hooks["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 30
        skill = fm(name="lab", description="Use when a guard denies a command.", model="opus") + "\nbody\n"
        r = self.lint_plugin(overrides={"hooks/hooks.json": json.dumps(hooks), "skills/lab/SKILL.md": skill})
        self.assertEqual(r.rc, 0, r.out)
        self.assertTrue(r.has("hook", sev="warning", text="timeout"), r.out)
        self.assertTrue(r.has("skill", sev="warning", text="opus"), r.out)
        self.assertIn("2 warning(s)", r.out)


# ---------------------------------------------------------------------------
# plugin.json
# ---------------------------------------------------------------------------

class TestManifest(H.Base):
    def test_each_required_field(self):
        for field in ("name", "version", "description", "author", "license", "homepage", "repository", "keywords"):
            with self.subTest(field=field):
                r = self.lint_plugin(manifest={field: DELETE})
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("manifest", text="missing required field: " + field), r.out)

    def test_semver(self):
        for bad in ("1.0", "v1.0.0", "1.0.0-beta", "1.0.0.0", ""):
            with self.subTest(version=bad):
                r = self.lint_plugin(manifest={"version": bad})
                self.assertTrue(r.has("manifest", text="MAJOR.MINOR.PATCH"), r.out)
        r = self.lint_plugin(manifest={"version": "10.20.30"})
        self.assertEqual(r.rc, 0, r.out)

    def test_description_length(self):
        r = self.lint_plugin(manifest={"description": "d" * 200})
        self.assertEqual(r.rc, 0, r.out)
        r = self.lint_plugin(manifest={"description": "d" * 201})
        self.assertTrue(r.has("manifest", text="201 chars"), r.out)

    def test_name_must_match_directory(self):
        r = self.lint_plugin(manifest={"name": "dojo-other"})
        self.assertTrue(r.has("manifest", text="does not match the directory"), r.out)

    def test_author_shapes(self):
        r = self.lint_plugin(manifest={"author": "Someone"})
        self.assertTrue(r.has("manifest", text="author must be"), r.out)
        r = self.lint_plugin(manifest={"author": {"name": "Dojo Genesis"}})
        self.assertTrue(r.has("manifest", text="author.email"), r.out)
        r = self.lint_plugin(manifest={"author": {"name": "Someone", "email": "a@b.co"}})
        self.assertTrue(r.has("manifest", text="author.name"), r.out)

    def test_exact_contract_values(self):
        cases = [
            ({"homepage": "https://dojogenesis.com/suite#other"}, "homepage must be"),
            ({"repository": "https://example.com/x"}, "repository must be"),
            ({"license": "MIT"}, "license must be"),
            ({"keywords": []}, "keywords must be"),
            ({"keywords": "a,b"}, "keywords must be a list"),
        ]
        for patch, text in cases:
            with self.subTest(patch=patch):
                r = self.lint_plugin(manifest=patch)
                self.assertTrue(r.has("manifest", text=text), r.out)

    def test_suite_promise_is_verbatim(self):
        r = self.lint_plugin("dojo-gates", manifest={"description": "Something else entirely."})
        self.assertTrue(r.has("manifest", text="frozen promise"), r.out)

    def test_hooks_key_pointing_at_default_file_warns(self):
        r = self.lint_plugin(manifest={"hooks": "./hooks/hooks.json"})
        self.assertEqual(r.rc, 0, r.out)
        self.assertTrue(r.has("manifest", sev="warning", text="loads by default"), r.out)

    def test_malformed_and_missing_manifest_do_not_crash(self):
        r = self.lint_plugin(overrides={".claude-plugin/plugin.json": "{"})
        self.assertEqual(r.rc, 1, r.out)
        self.assertNotIn("Traceback", r.err)
        self.assertTrue(r.has("manifest", text="not valid JSON"), r.out)
        r = self.lint_plugin(overrides={".claude-plugin/plugin.json": DELETE})
        self.assertTrue(r.has("manifest", text="missing or unreadable"), r.out)

    def test_userconfig(self):
        base = {"title": "T", "description": "D"}
        cases = [
            ({"k": dict(base, type="integer")}, "type must be one of"),
            ({"k": dict(base, type="number", options=["a"])}, "options is only valid"),
            ({"k": dict(base, type="string", min=1)}, "min is only valid"),
            ({"k": dict(base, type="string", max=1)}, "max is only valid"),
            ({"k": dict(base, type="boolean", default="yes")}, "default does not match"),
            ({"k": dict(base, type="number", default=True)}, "default does not match"),
            ({"k": dict(base, type="string", options=["a", "b"], default="c")}, "default is not one of options"),
            ({"Bad-Key": dict(base, type="string")}, "key must match"),
            ({"k": {"type": "string", "description": "D"}}, "missing title"),
        ]
        for uc, text in cases:
            with self.subTest(text=text):
                r = self.lint_plugin(manifest={"userConfig": uc})
                self.assertTrue(r.has("userconfig", text=text), r.out)
        ok = {"k": dict(base, type="number", min=0, max=5, default=2), "flag": dict(base, type="boolean")}
        self.assertEqual(self.lint_plugin(manifest={"userConfig": ok}).rc, 0)


# ---------------------------------------------------------------------------
# Frontmatter parser (unit level)
# ---------------------------------------------------------------------------

class TestFrontmatter(unittest.TestCase):
    def parse(self, text):
        raw = text if isinstance(text, bytes) else text.encode("utf-8")
        return SL.parse_frontmatter(raw)

    def test_plain_quoted_and_lists(self):
        f, e, body, _ = self.parse('---\na: plain value\nb: "quoted: with colon"\nc: \'it\'\'s\'\nd: [Read, Grep]\ne: [Read, Bash(git:*), mcp__x__y]\nf:\n---\nbody\n')
        self.assertEqual(e, [])
        self.assertEqual(f["a"][0], "plain value")
        self.assertEqual(f["b"][0], "quoted: with colon")
        self.assertEqual(f["c"][0], "it's")
        self.assertEqual(f["d"][0], ["Read", "Grep"])
        self.assertEqual(f["e"][0], ["Read", "Bash(git:*)", "mcp__x__y"])
        self.assertEqual(f["f"][0], "")
        self.assertEqual(body, "body\n")

    def test_double_quote_escapes(self):
        f, e, _b, _ = self.parse('---\na: "x\\"y\\\\z\\u00e9"\n---\n')
        self.assertEqual(e, [])
        self.assertEqual(f["a"][0], 'x"y\\z\u00e9')

    def test_unquoted_colon_space_is_an_error_but_quoted_passes(self):
        _f, e, _b, _ = self.parse("---\ndescription: Use when: you need X\n---\n")
        self.assertEqual(len(e), 1)
        self.assertIn("quote", e[0][1])
        f, e, _b, _ = self.parse('---\ndescription: "Use when: you need X"\n---\n')
        self.assertEqual(e, [])

    def test_inline_comment_is_stripped(self):
        f, e, _b, _ = self.parse("---\nmodel: haiku # pinned\n---\n")
        self.assertEqual(e, [])
        self.assertEqual(f["model"][0], "haiku")

    def test_block_scalars_and_lists_error(self):
        for text in ("a: >\n  folded\n", "a: |\n  literal\n", "a: >-\n  folded\n", "tools:\n  - Read\n  - Grep\n", "a: x\n  continued\n"):
            with self.subTest(text=text):
                _f, e, _b, _ = self.parse("---\n" + text + "---\n")
                self.assertTrue(e, text)

    def test_duplicate_key(self):
        _f, e, _b, _ = self.parse("---\nmodel: haiku\nmodel: opus\n---\n")
        self.assertTrue(any("duplicate" in m for _l, m in e))

    def test_bom_and_crlf(self):
        f, e, body, _ = self.parse(b"\xef\xbb\xbf---\r\nname: x\r\ndescription: y\r\n---\r\nbody\r\n")
        self.assertEqual(e, [])
        self.assertEqual(f["name"][0], "x")
        self.assertEqual(body, "body\r\n")

    def test_structure_errors(self):
        for raw, text in ((b"", "empty"), (b"# not frontmatter\n", "must start"), (b"---\na: b\n", "no closing"), (b"\xff\xfe\x00", "UTF-8")):
            with self.subTest(text=text):
                _f, e, _b, _ = self.parse(raw)
                self.assertTrue(any(text in m for _l, m in e), e)

    def test_quote_errors(self):
        for line in ('a: "unclosed', "a: 'unclosed", 'a: "x" tail', "a: [x, y", "a: {x: 1}", "a: `code`", "a: *"):
            with self.subTest(line=line):
                _f, e, _b, _ = self.parse("---\n%s\n---\n" % line)
                self.assertTrue(e, line)

    def test_bad_key_line(self):
        _f, e, _b, _ = self.parse("---\nnot a key value\n---\n")
        self.assertTrue(e)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

class TestSkills(H.Base):
    def skill_run(self, text, dirname="lab"):
        return self.lint_plugin(overrides={"skills/lab/SKILL.md": DELETE, "skills/%s/SKILL.md" % dirname: text})

    def test_description_length(self):
        for n, ok in ((250, True), (251, False)):
            with self.subTest(n=n):
                desc = "Use when " + "x" * (n - 9)
                r = self.skill_run(fm(name="lab", description=desc) + "\nb\n")
                if ok:
                    self.assertEqual(r.rc, 0, r.out)
                else:
                    self.assertTrue(r.has("skill", text="251 chars"), r.out)

    def test_multibyte_description_counts_characters(self):
        desc = "Use when " + "\u00e9" * 241
        r = self.skill_run(fm(name="lab", description=desc) + "\nb\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_description_start(self):
        good = ["Use when a guard denies it.", "Write the contract file.", "Check one claim."]
        bad = ["The guard list.", "A guard list.", "This explains guards.", "`gates` explains guards.", "dojo-lab explains guards.", "Dojo guards explained.", "When a guard denies it."]
        for d in good:
            with self.subTest(good=d):
                r = self.skill_run(fm(name="lab", description='"%s"' % d) + "\nb\n")
                self.assertEqual(r.rc, 0, r.out)
        for d in bad:
            with self.subTest(bad=d):
                r = self.skill_run(fm(name="lab", description='"%s"' % d) + "\nb\n")
                self.assertTrue(r.has("skill", text="must start with a verb"), r.out)

    def test_body_size_in_bytes(self):
        head = fm(name="lab", description="Use when a guard denies it.")
        r = self.skill_run(head + "a" * 6143 + "\n")
        self.assertEqual(r.rc, 0, r.out)
        r = self.skill_run(head + "a" * 6144 + "\n")
        self.assertTrue(r.has("skill", text="6145 bytes"), r.out)
        r = self.skill_run(head + "\u00e9" * 3073)  # 6146 bytes, 3073 characters
        self.assertTrue(r.has("skill", text="6146 bytes"), r.out)

    def test_name_and_model(self):
        r = self.skill_run(fm(name="other", description="Use when a guard denies it.") + "\nb\n")
        self.assertTrue(r.has("skill", text="does not match the directory"), r.out)
        r = self.skill_run(fm(name="lab", description="Use when a guard denies it.", model="gpt9") + "\nb\n")
        self.assertTrue(r.has("skill", sev="error", text="model must be"), r.out)
        r = self.skill_run(fm(name="lab", description="Use when a guard denies it.", model="inherit") + "\nb\n")
        self.assertEqual(r.rc, 0, r.out)
        r = self.skill_run(fm(name="lab", description="Use when a guard denies it.", model="opus") + "\nb\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_extra_keys_are_allowed(self):
        r = self.skill_run(fm(name="lab", description="Use when a guard denies it.", category="coding") + "\nb\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_missing_frontmatter(self):
        r = self.skill_run("# no frontmatter\n")
        self.assertTrue(r.has("frontmatter", text="must start with ---"), r.out)

    def test_unquoted_colon_in_description_is_reported_once(self):
        r = self.skill_run("---\nname: lab\ndescription: Use when: you need X\n---\nb\n")
        self.assertTrue(r.has("frontmatter", line=3, text="quote"), r.out)
        self.assertFalse(r.has("skill", text="missing description"), r.out)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def agent_text(**over):
    f = dict(name="checker", description="Check one claim.", model="haiku", effort="low", tools="Read, Glob, Grep", maxTurns="10")
    f.update(over)
    return fm(**f) + "\nbody\n"


class TestAgents(H.Base):
    def run_agent(self, text, name="checker"):
        return self.lint_plugin(overrides={"agents/checker.md": DELETE, "agents/%s.md" % name: text})

    def test_good(self):
        self.assertEqual(self.run_agent(agent_text()).rc, 0)

    def test_model(self):
        for model, ok in (("opus", True), ("inherit", True), ("sonnet", True), ("Haiku", False), ("gpt9", False), ("claude-sonnet-5-5", False)):
            with self.subTest(model=model):
                r = self.run_agent(agent_text(model=model))
                self.assertEqual(r.rc == 0, ok, r.out)
        r = self.run_agent(agent_text(model=DELETE))
        self.assertTrue(r.has("agent", text="missing model"), r.out)

    def test_effort(self):
        self.assertEqual(self.run_agent(agent_text(effort="xhigh")).rc, 0)
        self.assertTrue(self.run_agent(agent_text(effort="ultra")).has("agent", text="effort must be"))
        self.assertTrue(self.run_agent(agent_text(effort=DELETE)).has("agent", text="missing effort"))

    def test_tools(self):
        cases = [
            ("*", False), ("Read Glob Grep", False), ("", False), ("All", False),
            ("Read, Bash(git:*), mcp__x__y", True), ("[Read, Grep]", True), ("Read", True),
        ]
        for tools, ok in cases:
            with self.subTest(tools=tools):
                text = agent_text(tools='"%s"' % tools if tools == "*" else tools)
                r = self.run_agent(text)
                self.assertEqual(r.rc == 0, ok, r.out)
        self.assertTrue(self.run_agent(agent_text(tools=DELETE)).has("agent", text="missing tools"))

    def test_max_turns(self):
        for v, ok in (("12", True), ("12a", False), ("0", False), ("-3", False)):
            with self.subTest(v=v):
                self.assertEqual(self.run_agent(agent_text(maxTurns=v)).rc == 0, ok)
        self.assertTrue(self.run_agent(agent_text(maxTurns=DELETE)).has("agent", text="missing maxTurns"))

    def test_name_must_match_file_stem(self):
        r = self.run_agent(agent_text(name="other"))
        self.assertTrue(r.has("agent", text="does not match the file name"), r.out)

    def test_description_length(self):
        self.assertEqual(self.run_agent(agent_text(description="Check " + "x" * 194)).rc, 0)
        r = self.run_agent(agent_text(description="Check " + "x" * 195))
        self.assertTrue(r.has("agent", text="201 chars"), r.out)


# ---------------------------------------------------------------------------
# Commands, output styles, budget
# ---------------------------------------------------------------------------

class TestCommandsAndStyles(H.Base):
    def run_cmd(self, text):
        return self.lint_plugin(overrides={"commands/status.md": text})

    def test_command_rules(self):
        self.assertEqual(self.run_cmd(fm(description="Show it.", allowed_tools="Read")).rc, 0)
        r = self.run_cmd(fm(allowed_tools="Read") + "First line of the body.\n")
        self.assertTrue(r.has("command", text="missing description"), r.out)
        r = self.run_cmd(fm(description="Show it."))
        self.assertTrue(r.has("command", text="missing allowed-tools"), r.out)
        r = self.run_cmd(fm(description="Show " + "x" * 196, allowed_tools="Read"))
        self.assertTrue(r.has("command", text="201 chars"), r.out)
        r = self.run_cmd(fm(description="Show " + "x" * 195, allowed_tools="Read"))
        self.assertEqual(r.rc, 0, r.out)

    def test_output_style_needs_name_and_description(self):
        r = self.lint_plugin(overrides={"output-styles/s.md": fm(name="s", description="A style.") + "x\n"})
        self.assertEqual(r.rc, 0, r.out)
        r = self.lint_plugin(overrides={"output-styles/s.md": fm(description="A style.") + "x\n"})
        self.assertTrue(r.has("outputstyle", text="missing name"), r.out)

    def test_evals_need_a_case_file(self):
        r = self.lint_plugin(overrides={"evals/second/case.yaml": ""})
        self.assertTrue(r.has("evals", text="missing or empty"), r.out)
        r = self.lint_plugin(overrides={"evals/third/notes.txt": "x"})
        self.assertTrue(r.has("evals", path="evals/third"), r.out)


class TestBudget(H.Base):
    def budget_run(self, last):
        ov = {"skills/lab/SKILL.md": DELETE, "agents/checker.md": DELETE, "commands/status.md": DELETE}
        for n in ("lab", "s2", "s3"):
            ov["skills/%s/SKILL.md" % n] = fm(name=n, description="Use when " + "x" * 241) + "\nb\n"
        ov["skills/s4/SKILL.md"] = fm(name="s4", description="Use when " + "x" * (last - 9)) + "\nb\n"
        ov["agents/checker.md"] = agent_text(description="Check " + "x" * 94)
        ov["commands/status.md"] = fm(description="Show " + "x" * 95, allowed_tools="Read") + "\n"
        return self.lint_plugin(overrides=ov)

    def test_999_passes_1000_fails(self):
        r = self.budget_run(49)
        self.assertEqual(r.rc, 0, r.out)
        r = self.budget_run(50)
        self.assertTrue(r.has("budget", text="1000 chars"), r.out)
        self.assertTrue(r.has("budget", text="largest"), r.out)

    def test_suite_total_warns_but_does_not_fail(self):
        ov = {"skills/s%d/SKILL.md" % i: fm(name="s%d" % i, description="Use when " + "x" * 241) + "\nb\n" for i in range(50)}
        r = self.lint_plugin(overrides=ov)
        self.assertTrue(r.has("budget", sev="warning", text="tokens"), r.out)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

class TestHookCommands(unittest.TestCase):
    def test_accepted(self):
        for cmd in (
            'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"',
            'python3 $CLAUDE_PLUGIN_ROOT/hooks/x.py',
            'python3 -u "${CLAUDE_PLUGIN_ROOT}/hooks/x.py" 2>&1',
            'python3 -W ignore "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/h.sh" banner || true',
            'bash "${CLAUDE_PLUGIN_ROOT}/hooks/h.sh"',
            'node "${CLAUDE_PLUGIN_ROOT}/hooks/h.js"',
            'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py" && python3 "${CLAUDE_PLUGIN_ROOT}/hooks/y.py"',
            'python3 -c "print(1)"',
            'python3 -m json.tool',
            "bash -c 'echo hi'",
            'bash -lc "echo hi"',
            'node -e "1"',
        ):
            with self.subTest(cmd=cmd):
                self.assertEqual(SL.command_problems(cmd), [])

    def test_script_paths_must_start_with_the_plugin_root(self):
        for cmd in (
            "python3 hooks/session_start.py",
            "python3 ./hooks/x.py",
            "python3 /opt/tools/x.py",
            "python3 x.py 2>&1",
            "python3 -u hooks/x.py",
            "python3 -W ignore hooks/x.py",
            "sh hooks/h.sh",
            "bash ../x.sh",
            "node hooks/h.js",
            'python3 "${CLAUDE_PLUGIN_ROOTX}/x.py"',
            'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py" && python3 y.py',
        ):
            with self.subTest(cmd=cmd):
                probs = SL.command_problems(cmd)
                self.assertTrue(any("must start with ${CLAUDE_PLUGIN_ROOT}/" in p for p in probs), (cmd, probs))

    def test_rejected(self):
        for cmd in (
            "python x.py", "/usr/bin/python x.py", "python3.11 x.py", "env python3 x.py", "FOO=1 python3 x.py",
            'bash -c "python x.py"', 'cd "${CLAUDE_PLUGIN_ROOT}" && python x.py', 'cd "${CLAUDE_PLUGIN_ROOT}" && python3 "${CLAUDE_PLUGIN_ROOT}/x.py"',
            'python3 "unclosed', "", "uv run x.py", 'python3 "${CLAUDE_PLUGIN_ROOT}/x.py" | python y.py',
        ):
            with self.subTest(cmd=cmd):
                self.assertTrue(SL.command_problems(cmd), cmd)

    def test_unbalanced_quote_does_not_raise(self):
        self.assertEqual(SL.command_problems("python3 'x")[-1], "unbalanced quote in the command")


class TestHooksFile(H.Base):
    def hooks_run(self, data, extra=None):
        ov = {"hooks/hooks.json": data if isinstance(data, str) else json.dumps(data)}
        ov.update(extra or {})
        return self.lint_plugin(overrides=ov)

    def one(self, hook, event="PreToolUse"):
        return {"hooks": {event: [{"hooks": [hook]}]}}

    def test_bare_python_in_file(self):
        r = self.hooks_run(self.one({"type": "command", "command": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"'}))
        self.assertTrue(r.has("hook", text="bare 'python'"), r.out)

    def test_relative_script_path_in_file(self):
        r = self.hooks_run(self.one({"type": "command", "command": "python3 hooks/guard.py"}))
        self.assertEqual(r.rc, 1, r.out)
        self.assertTrue(r.has("hook", path="hooks/hooks.json", text="must start with ${CLAUDE_PLUGIN_ROOT}/"), r.out)

    def test_hook_types(self):
        for t in ("prompt", "agent", "http"):
            with self.subTest(t=t):
                r = self.hooks_run(self.one({"type": t, "prompt": "x"}))
                self.assertTrue(r.has("hook", text="must be 'command'"), r.out)

    def test_malformed_json_is_an_error_not_a_crash(self):
        r = self.hooks_run("{ not json")
        self.assertEqual(r.rc, 1)
        self.assertNotIn("Traceback", r.err)
        self.assertTrue(r.has("hook", text="not valid JSON"), r.out)

    def test_unknown_event_warns(self):
        r = self.hooks_run(self.one({"type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"'}, "SomeFutureEvent"))
        self.assertEqual(r.rc, 0, r.out)
        self.assertTrue(r.has("hook", sev="warning", text="SomeFutureEvent"), r.out)

    def test_known_events_do_not_warn(self):
        for event in ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "InstructionsLoaded", "Stop"):
            with self.subTest(event=event):
                r = self.hooks_run(self.one({"type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"'}, event))
                self.assertEqual(r.rc, 0, r.out)
                self.assertFalse(r.has("hook"), r.out)

    def test_modules(self):
        data = H.good_hooks()
        data["modules"] = ["./register.ts"]
        r = self.hooks_run(data)
        self.assertTrue(r.has("hook", text="module does not exist"), r.out)
        r = self.hooks_run(data, {"hooks/register.ts": "export default function () {}\n"})
        self.assertFalse(r.has("hook"), r.out)
        # register.ts on disk but not listed
        r = self.hooks_run(H.good_hooks(), {"hooks/register.ts": "export default function () {}\n"})
        self.assertTrue(r.has("hook", text="does not list it in modules"), r.out)
        # module path escaping the plugin
        data["modules"] = ["../../x.ts"]
        r = self.hooks_run(data)
        self.assertTrue(r.has("hook", text="leaves the plugin"), r.out)


class TestPluginRootRefs(H.Base):
    def refs(self, rel, text, **kw):
        return self.lint_plugin(overrides={rel: text}, **kw)

    def test_missing_file_in_each_place(self):
        ref = "${CLAUDE_PLUGIN_ROOT}/scripts/missing.py"
        places = {
            "README.md": "# t\n\nsee %s here\n" % ref,
            "skills/lab/SKILL.md": fm(name="lab", description="Use when a guard denies it.") + "\nRun %s\n" % ref,
            "commands/status.md": fm(description="Show it.", allowed_tools="Read") + "\nRun %s\n" % ref,
        }
        for rel, text in places.items():
            with self.subTest(rel=rel):
                r = self.refs(rel, text)
                self.assertTrue(r.has("plugin-root", path=rel, text="does not exist"), r.out)
        hooks = H.good_hooks()
        hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/missing.py"'
        r = self.refs("hooks/hooks.json", json.dumps(hooks, indent=2))
        self.assertTrue(r.has("plugin-root", path="hooks/hooks.json", text="does not exist"), r.out)

    def test_error_carries_the_line_number(self):
        r = self.refs("README.md", "# t\n\n\nline four ${CLAUDE_PLUGIN_ROOT}/nope.py\n")
        self.assertTrue(r.has("plugin-root", path="README.md", line=4), r.out)

    def test_unbraced_form_is_checked(self):
        r = self.refs("README.md", "# t\n\n$CLAUDE_PLUGIN_ROOT/nope.py\n")
        self.assertTrue(r.has("plugin-root", text="does not exist"), r.out)

    def test_escape_and_placeholder(self):
        r = self.refs("README.md", "# t\n\n${CLAUDE_PLUGIN_ROOT}/../other/x.py\n")
        self.assertTrue(r.has("plugin-root", text="leaves the plugin root"), r.out)
        r = self.refs("README.md", "# t\n\n${CLAUDE_PLUGIN_ROOT}/workflows/<file>.js\n")
        self.assertTrue(r.has("plugin-root", text="placeholder"), r.out)

    def test_trailing_punctuation_is_stripped(self):
        text = "# t\n\nRun ${CLAUDE_PLUGIN_ROOT}/hooks/guard.py.\n(${CLAUDE_PLUGIN_ROOT}/hooks/guard.py)\n'${CLAUDE_PLUGIN_ROOT}/hooks/guard.py'})\nSee ${CLAUDE_PLUGIN_ROOT}/hooks/guard.py, then ${CLAUDE_PLUGIN_ROOT}/hooks/guard.py:\n"
        r = self.refs("README.md", text)
        self.assertEqual(r.rc, 0, r.out)

    def test_references_under_tests_are_not_scanned(self):
        r = self.refs("tests/notes.md", "${CLAUDE_PLUGIN_ROOT}/nope.py\n")
        self.assertEqual(r.rc, 0, r.out)


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

META = "export const meta = {name:'wf', description:'d', phases:['a']}\n"


class TestWorkflows(unittest.TestCase):
    def wf(self, code, meta=True, stem="wf"):
        d = tempfile.mkdtemp(prefix="suite-wf-")
        self.addCleanup(shutil.rmtree, d, True)
        root = Path(d) / "dojo-wf"
        (root / "workflows").mkdir(parents=True)
        (root / "workflows" / (stem + ".js")).write_text((META if meta else "") + code)
        rep = SL.Report()
        SL.check_workflows("dojo-wf", root, SL.walk_plugin(root), rep)
        return [(it[2], it[5]) for it in rep.items if it[3] == "workflow"]

    def assertOk(self, code, **kw):
        self.assertEqual(self.wf(code, **kw), [], code)

    def assertOne(self, code, text, line=None, **kw):
        res = self.wf(code, **kw)
        self.assertEqual(len(res), 1, (code, res))
        self.assertIn(text, res[0][1])
        if line is not None:
            self.assertEqual(res[0][0], line)

    def test_model_present(self):
        self.assertOk("await agent('p', { model: 'haiku' })\n")
        self.assertOk("await agent('p', { 'model': 'haiku' })\n")
        self.assertOk("const model = 'haiku'\nawait agent('p', { model })\n")
        self.assertOk("await agent('p', { label: 'a', model: models.scout, effort: 'low' })\n")
        self.assertOk("await agent ('p', { model: 'haiku' })\n")
        self.assertOk("await agent(\n  `prompt ${x}`,\n  { label: 'a',\n    model: 'sonnet' },\n)\n")

    def test_model_absent_reports_the_call_line(self):
        self.assertOne("\nawait agent('p', { label: 'x' })\n", "does not set model", line=3)
        self.assertOne("await agent('p')\n", "no options object", line=2)
        self.assertOne("await agent(\n  'p',\n  { label: 'x' },\n)\n", "does not set model", line=2)

    def test_model_must_be_a_depth_one_key_of_the_options(self):
        self.assertOne("await agent(\"model: 'haiku'\", { label: 'x' })\n", "does not set model")
        self.assertOne("await agent('p', { schema: { model: 'x' } })\n", "does not set model")
        self.assertOne("await agent('p', { label: 'x' /* model: 'haiku' */ })\n", "does not set model")
        self.assertOne("await agent('p', { label: 'x' // model: 'haiku'\n})\n", "does not set model")

    def test_bad_model_values(self):
        for v in ("undefined", "null", "''", '""'):
            with self.subTest(v=v):
                self.assertOne("await agent('p', { model: %s })\n" % v, "model")

    def test_options_not_statically_visible(self):
        self.assertOne("await agent(p, opts)\n", "not statically visible")
        self.assertOne("await agent('p', { ...base })\n", "not statically visible")
        self.assertOk("await agent('p', { ...base, model: 'haiku' })\n")

    def test_not_agent_calls(self):
        self.assertOk("subagent('p')\nx.agent('p')\nconst agent2 = (a) => a\nagent2('p')\n")

    def test_strings_and_comments_are_ignored(self):
        self.assertOk("const s = \"agent('p')\"\n// agent('q')\n/* agent('r') */\nconst t = `agent('p')`\n")

    def test_regex_literal_does_not_desync_the_scanner(self):
        self.assertOk("const r = /\"/g\nconst q = /\\(/\nawait agent('p', { model: 'haiku' })\n")
        self.assertOne("const r = /\"/g\nawait agent('p', {})\n", "does not set model", line=3)
        self.assertOk("const a = 4 / 2, b = 8 / 4\nawait agent('p', { model: 'haiku' })\n")

    def test_agent_inside_template_substitution_counts(self):
        self.assertOne("const s = `x ${await agent('p', {})} y`\n", "does not set model")
        self.assertOk("const s = `x ${await agent('p', { model: 'haiku' })} y`\n")
        self.assertOne("const s = `a ${`b ${agent('p')}`} c`\n", "no options object")

    def test_banned_calls(self):
        for code in ("const t = Date.now()\n", "const r = Math.random()\n", "const d = new Date()\n", "const d = new Date( )\n", "const d = new Date\n"):
            with self.subTest(code=code):
                self.assertEqual(len(self.wf(code)), 1, code)
        self.assertOk("const d = new Date(x)\n")
        self.assertOk("const p = 'Date.now() and Math.random()'\n")
        self.assertOk("// new Date()\n")

    def test_meta_rules(self):
        self.assertOne("const x = 1\n", "missing `export const meta", meta=False)
        self.assertOne("export const meta = { name: `wf${x}`, description: 'd', phases: ['a'] }\n", "pure literal", meta=False)
        self.assertOne("export const meta = { name: String('wf'), description: 'd', phases: ['a'] }\n", "pure literal", meta=False)
        self.assertOne("export const meta = { name: other, description: 'd', phases: ['a'] }\n", "pure literal", meta=False)
        self.assertOne("export const meta = { name: 'nope', description: 'd', phases: ['a'] }\n", "does not match the file name", meta=False)
        self.assertOne("export const meta = { name: 'wf', phases: ['a'] }\n", "missing description", meta=False)
        self.assertOne("export const meta = { name: 'wf', description: 'd' }\n", "missing phases", meta=False)
        self.assertOk("export const meta = { name: 'wf', description: 'd', whenToUse: 'x', phases: ['a', 'b'] }\n", meta=False)


class TestWorkflowThroughTheCli(H.Base):
    def test_bad_workflow_makes_the_run_dirty(self):
        r = self.lint_plugin(overrides={"workflows/demo.js": H.WORKFLOW + "await agent('x', { label: 'y' })\n"})
        self.assertEqual(r.rc, 1, r.out)
        self.assertTrue(r.has("workflow", path="workflows/demo.js", line=7, text="does not set model"), r.out)


# ---------------------------------------------------------------------------
# Python 3.9
# ---------------------------------------------------------------------------

class TestPy39(H.Base):
    def py(self, code, **kw):
        return self.lint_plugin(overrides={"scripts/m.py": code}, **kw)

    @unittest.skipUnless(PY39_OLD, "the 3.9 interpreter is not 3.9 on this host")
    def test_match_statement_fails_to_compile(self):
        r = self.py("x = 1\nmatch x:\n    case 1:\n        pass\n")
        self.assertTrue(r.has("py39-compile", path="scripts/m.py"), r.out)

    def test_pep604_annotation(self):
        r = self.py("def f(x: int | None):\n    return x\n")
        self.assertTrue(r.has("py39-pep604", line=1), r.out)
        r = self.py("def f(x) -> int | None:\n    return x\n")
        self.assertTrue(r.has("py39-pep604", line=1), r.out)
        r = self.py("v: int | None = None\n")
        self.assertTrue(r.has("py39-pep604", line=1), r.out)

    def test_pep604_passes_with_future_import(self):
        r = self.py("from __future__ import annotations\n\n\ndef f(x: int | None):\n    return x\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_ordinary_bitor_passes(self):
        r = self.py("a = 1\nb = 2\nc = a | b\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_isinstance_union_fails(self):
        r = self.py("x = 1\nok = isinstance(x, int | str)\n")
        self.assertTrue(r.has("py39-pep604", line=2), r.out)
        r = self.py("x = 1\nok = isinstance(x, (int, str))\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_runtime_union_outside_annotations(self):
        for code in ("X = int | None\n", "Y = None | str\n", "Z = list[int] | None\n", "W = int | str\n"):
            with self.subTest(code=code):
                r = self.py(code)
                self.assertTrue(r.has("py39-pep604", line=1, text="between types"), r.out)
        # a future import excuses annotations, never runtime values
        r = self.py("from __future__ import annotations\n\n\ndef f(x: int | None):\n    return x\n\n\nX = int | None\n")
        self.assertFalse(r.has("py39-pep604", line=4), r.out)
        self.assertTrue(r.has("py39-pep604", line=8), r.out)

    def test_ordinary_bitor_on_values_is_fine(self):
        r = self.py("flags = 1 | 2\nmask = flags | 0xFF\nname = flags | mask\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_python_310_apis(self):
        cases = [
            ("import itertools\nitertools.pairwise([1, 2])\n", 2),
            ("zip([1], [2], strict=True)\n", 1),
            ("n = 5\nn.bit_count()\n", 2),
            ("from dataclasses import dataclass\n\n\n@dataclass(slots=True)\nclass A:\n    x: int = 0\n", 4),
            ("async def f(it):\n    return await anext(it)\n", 2),
        ]
        for code, line in cases:
            with self.subTest(code=code):
                r = self.py(code)
                self.assertTrue(r.has("py39-api", line=line, text="3.10") or r.has("py39-api", line=line, text="does not exist"), r.out)
        r = self.py("import itertools\nfor a, b in zip([1], [2]):\n    print(a, b, itertools.chain)\n")
        self.assertEqual(r.rc, 0, r.out)

    @unittest.skipUnless(PY39_OLD, "the 3.9 interpreter is not 3.9 on this host")
    def test_names_missing_on_this_interpreter(self):
        r = self.py("from itertools import pairwise\n")
        self.assertTrue(r.has("py39-api", line=1, text="itertools.pairwise"), r.out)
        r = self.py("from typing import TypeAlias\n")
        self.assertTrue(r.has("py39-api", line=1, text="typing.TypeAlias"), r.out)
        r = self.py("import sys\nnames = sys.stdlib_module_names\n")
        self.assertTrue(r.has("py39-api", line=2, text="stdlib_module_names"), r.out)
        # a hasattr guard on the same name is accepted
        r = self.py("import sys\nnames = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else None\n")
        self.assertEqual(r.rc, 0, r.out)
        r = self.py("from itertools import chain\nfrom typing import Optional\nimport os\nprint(os.path.sep, chain, Optional)\n")
        self.assertEqual(r.rc, 0, r.out)

    def test_syntax_error_reports_line(self):
        r = self.py("x = 1\ndef broken(:\n    pass\n")
        self.assertTrue(r.has("py39-compile", line=2), r.out)

    def test_no_bytecode_is_written(self):
        r = self.py("x = 1\n")
        self.assertEqual(r.rc, 0, r.out)
        self.assertEqual(self.no_pycache(), [])

    def test_missing_interpreter_exits_two(self):
        self.plugin()
        r = self.lint("dojo-lab", env={"DOJO_PY39": os.path.join(self.home, "no-such-python")})
        self.assertEqual(r.rc, 2, r.out + r.err)

    def test_skip_py39_does_not_need_the_interpreter(self):
        self.plugin()
        r = self.lint("dojo-lab", "--skip", "py39", env={"DOJO_PY39": os.path.join(self.home, "no-such-python")})
        self.assertEqual(r.rc, 0, r.out + r.err)

    def test_pycache_in_plugin_is_junk(self):
        r = self.lint_plugin(overrides={"hooks/__pycache__/guard.cpython-39.pyc": b"\x00\x01"})
        self.assertTrue(r.has("junk"), r.out)


# ---------------------------------------------------------------------------
# Internal references and voice
# ---------------------------------------------------------------------------

class TestInternalRefs(H.Base):
    """The linter knows only the generic shape of a machine-specific home path. Private
    names live in local-only lists that suite_denylist.py reads."""

    def doc(self, text, rel="README.md"):
        return self.lint_plugin(overrides={rel: "# t\n\n" + text + "\n"})

    def test_home_paths_are_flagged_with_file_and_line(self):
        cases = {
            "macOS": H.OP_PATH,
            "Linux": H.OP_PATH_LINUX,
            "Windows": H.OP_PATH_WIN,
            "in a sentence": "run it from " + H.OP_PATH + " now",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                r = self.doc(text)
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("internal-ref", path="README.md", line=3), r.out)
                self.assertNotIn(text, r.out)  # the match itself is never echoed

    def test_near_misses_are_not_flagged(self):
        for text in (
            "edit ~/.claude/settings.json",
            "default list at ~/.config/dojo/stealth-denylist.txt",
            "see " + H.frag("/ho", "me/user/project"),
            "see " + H.frag("/ho", "me/tester/proj"),
            "see " + H.frag("/Us", "ers/<name>/proj"),
            H.frag("/Us", "ers/Shared/x"),
            "a relative path like src" + H.frag("/ho", "me/jdoe1/") + "x",
            "DNS-01 challenge and TLS-12",
        ):
            with self.subTest(text=text):
                r = self.doc(text)
                self.assertEqual(r.rc, 0, r.out)

    def test_hit_inside_tests_is_flagged(self):
        r = self.lint_plugin(overrides={"tests/test_x.py": "# " + H.OP_PATH + "\n"})
        self.assertTrue(r.has("internal-ref", path="tests/test_x.py", line=1), r.out)

    def test_hit_in_a_script_is_flagged(self):
        r = self.lint_plugin(overrides={"scripts/a.py": "x = 1\nPATH = '%s'\n" % H.OP_PATH})
        self.assertTrue(r.has("internal-ref", path="scripts/a.py", line=2), r.out)

    def test_the_linter_carries_no_private_name_list(self):
        # every pattern in the rule is a home-directory shape; there is no list of names to leak
        self.assertEqual(len(SL.INTERNAL_PATTERNS), 2)
        for label, _rx in SL.INTERNAL_PATTERNS:
            self.assertIn("home directory", label)

    def test_there_is_no_allow_marker(self):
        r = self.doc("<!-- suite-lint: allow --> " + H.OP_PATH)
        self.assertTrue(r.has("internal-ref", line=3), r.out)
        r = self.lint_plugin(overrides={"scripts/a.py": "x = '%s'  # allow suite-lint noqa\n" % H.OP_PATH})
        self.assertTrue(r.has("internal-ref", path="scripts/a.py"), r.out)

    def test_skip_flag_is_the_only_switch(self):
        self.plugin(overrides={"README.md": "# t\n\n%s\n" % H.OP_PATH})
        self.assertEqual(self.lint("dojo-lab", "--skip", "internal-ref").rc, 0)


class TestVoice(H.Base):
    BANNED = [
        "ecosystem", "platform", "optimize", "optimise", "optimization", "leverage", "leveraging", "powerful",
        "supercharge", "supercharged", "seamless", "seamlessly", "works out of the box", "cheap", "cheaper",
        "save 40%", "saves up to 30%", "saving 10 %", "30% fewer tokens", "20% less", "50% savings",
        "3x faster", "2.5 x cheaper", "4\u00d7 fewer calls", "half the tokens", "half the cost",
    ]

    def test_each_banned_phrase_in_readme(self):
        text = "# t\n\n" + "\n".join("It is %s here." % w for w in self.BANNED) + "\n"
        r = self.lint_plugin(overrides={"README.md": text})
        self.assertEqual(r.rc, 1, r.out)
        for i, w in enumerate(self.BANNED):
            with self.subTest(word=w):
                self.assertTrue(r.has("voice", path="README.md", line=3 + i), r.out)

    def test_each_scanned_location(self):
        bad = "A powerful way.\n"
        places = {
            "skills/lab/SKILL.md": fm(name="lab", description="Use when a guard denies it.") + "\n" + bad,
            "PROTOCOL.md": "# p\n\n" + bad,
            "templates/x.md": bad,
            "output-styles/s.md": fm(name="s", description="A style.") + bad,
            "agents/checker.md": agent_text() + bad,
        }
        for rel, text in places.items():
            with self.subTest(rel=rel):
                r = self.lint_plugin(overrides={rel: text})
                self.assertTrue(r.has("voice", path=rel), r.out)
        r = self.lint_plugin(manifest={"description": "A powerful guard set."})
        self.assertTrue(r.has("voice", path="plugin.json"), r.out)
        r = self.lint_plugin(manifest={"keywords": ["seamless"]})
        self.assertTrue(r.has("voice", path="plugin.json"), r.out)

    def test_not_flagged(self):
        text = "# t\n\nRun the cheapest experiment. A platformer game. Use sys.platform. 40 percent of 50.\n"
        r = self.lint_plugin(overrides={"README.md": text, "scripts/p.py": "import sys\nprint(sys.platform)  # platform check, optimize later\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_tests_and_evals_are_excluded(self):
        r = self.lint_plugin(overrides={"tests/notes.md": "powerful\n", "evals/first/notes.md": "seamless\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_skip_voice(self):
        self.plugin(overrides={"README.md": "# t\n\npowerful\n"})
        self.assertEqual(self.lint("dojo-lab").rc, 1)
        self.assertEqual(self.lint("dojo-lab", "--skip", "voice").rc, 0)

    def test_no_in_file_marker(self):
        r = self.lint_plugin(overrides={"README.md": "# t\n\n<!-- suite-lint: allow --> powerful\n"})
        self.assertTrue(r.has("voice", line=3), r.out)


# ---------------------------------------------------------------------------
# Mechanism rules
# ---------------------------------------------------------------------------

class TestMechanism(H.Base):
    def test_kill_switch_names_are_required(self):
        r = self.lint_plugin(overrides={"hooks/guard.py": "import sys\n"})
        self.assertTrue(r.has("kill-switch", text="DOJO_OFF"), r.out)
        self.assertTrue(r.has("kill-switch", text="DOJO_LAB_OFF"), r.out)

    def test_a_comment_or_docstring_is_not_a_kill_switch(self):
        for code in (
            "import sys\n# DOJO_OFF DOJO_LAB_OFF\n",
            '"""Honors DOJO_OFF and DOJO_LAB_OFF."""\nimport sys\n',
            'def main():\n    """DOJO_OFF DOJO_LAB_OFF"""\n    return 0\n',
        ):
            with self.subTest(code=code):
                r = self.lint_plugin(overrides={"hooks/guard.py": code})
                self.assertTrue(r.has("kill-switch", text="DOJO_OFF"), r.out)
                self.assertTrue(r.has("kill-switch", text="DOJO_LAB_OFF"), r.out)

    def test_plugin_specific_switch_may_live_in_a_shared_helper(self):
        r = self.lint_plugin(overrides={
            "hooks/guard.py": "import sys\nOFF = 'DOJO_OFF'\n",
            "hooks/_common.py": "NAME = 'DOJO_LAB_OFF'\n",
        })
        self.assertEqual(r.rc, 0, r.out)

    def test_hyphenated_plugin_name_maps_to_an_underscore_switch(self):
        r = self.lint_plugin("dojo-two-words", overrides={"hooks/guard.py": "NAMES = ('DOJO_OFF', 'DOJO_TWO_WORDS_OFF')\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_a_hook_that_does_not_parse_falls_back_to_a_text_search(self):
        r = self.lint_plugin(overrides={"hooks/guard.py": "DOJO_OFF DOJO_LAB_OFF def broken(:\n"})
        self.assertFalse(r.has("kill-switch"), r.out)
        self.assertTrue(r.has("py39-compile"), r.out)

    def test_dynamic_import_in_a_hook(self):
        code = H.HOOK_PY.replace("{UP}", "LAB") + "mod = __import__('json')\n"
        r = self.lint_plugin(overrides={"hooks/guard.py": code})
        self.assertTrue(r.has("hook-no-network", path="hooks/guard.py", line=6, text="__import__"), r.out)

    def test_hooks_must_not_use_the_network(self):
        for line in ("import urllib.request", "from urllib import request", "import os, socket", "import http.client as h", "import requests", "from socket import socket"):
            with self.subTest(line=line):
                r = self.lint_plugin(overrides={"hooks/guard.py": H.HOOK_PY.replace("{UP}", "LAB") + line + "\n"})
                self.assertTrue(r.has("hook-no-network", path="hooks/guard.py", line=6), r.out)
        r = self.lint_plugin(overrides={"hooks/guard.py": H.HOOK_PY.replace("{UP}", "LAB") + "import json, subprocess\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_mod_needs_a_boolean_switch(self):
        hooks = H.good_hooks()
        hooks["modules"] = ["./register.ts"]
        ov = {"hooks/hooks.json": json.dumps(hooks), "hooks/register.ts": "export default function () {}\n"}
        r = self.lint_plugin(overrides=ov, manifest={"userConfig": {"mode": {"type": "string", "title": "M", "description": "D"}}})
        self.assertTrue(r.has("mod", text="boolean userConfig"), r.out)
        r = self.lint_plugin(overrides=ov)
        self.assertFalse(r.has("mod"), r.out)

    def test_ds_store_is_junk(self):
        r = self.lint_plugin(overrides={"skills/.DS_Store": b"\x00"})
        self.assertTrue(r.has("junk", path=".DS_Store"), r.out)


# ---------------------------------------------------------------------------
# Hooks declared in plugin.json
# ---------------------------------------------------------------------------

GOOD_CMD = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"'


def hook_cfg(command, event="PreToolUse", wrapped=True, **extra):
    groups = {event: [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]}
    if not wrapped:
        return groups
    d = {"hooks": groups}
    d.update(extra)
    return d


class TestManifestHooks(H.Base):
    MREL = ".claude-plugin/plugin.json"

    def run_with(self, hooks_value, overrides=None):
        return self.lint_plugin(manifest={"hooks": hooks_value}, overrides=overrides)

    def test_inline_hook_with_bare_python_and_relative_path_is_flagged(self):
        for wrapped in (True, False):
            with self.subTest(wrapped=wrapped):
                r = self.run_with(hook_cfg("python hooks/guard.py", wrapped=wrapped))
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("hook", path="plugin.json", text="bare 'python'"), r.out)
                self.assertTrue(r.has("hook", path="plugin.json", text="command must start with python3"), r.out)

    def test_inline_hook_with_a_relative_script_path_is_flagged(self):
        r = self.run_with(hook_cfg("python3 hooks/guard.py"))
        self.assertTrue(r.has("hook", path="plugin.json", text="must start with ${CLAUDE_PLUGIN_ROOT}/"), r.out)
        ov = {"hooks/extra.json": json.dumps(hook_cfg("python3 hooks/guard.py"))}
        r = self.run_with("./hooks/extra.json", ov)
        self.assertTrue(r.has("hook", path="hooks/extra.json", text="must start with ${CLAUDE_PLUGIN_ROOT}/"), r.out)

    def test_inline_hook_that_follows_the_rules_is_clean(self):
        for wrapped in (True, False):
            with self.subTest(wrapped=wrapped):
                r = self.run_with(hook_cfg(GOOD_CMD, "PostToolUse", wrapped=wrapped))
                self.assertEqual(r.rc, 0, r.out)

    def test_inline_hook_type_timeout_and_event_rules(self):
        r = self.run_with({"hooks": {"PreToolUse": [{"hooks": [{"type": "prompt", "prompt": "x"}]}]}})
        self.assertTrue(r.has("hook", path="plugin.json", text="must be 'command'"), r.out)
        r = self.run_with({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": GOOD_CMD, "timeout": 60}]}]}})
        self.assertTrue(r.has("hook", path="plugin.json", sev="warning", text="timeout 60"), r.out)
        r = self.run_with(hook_cfg(GOOD_CMD, "SomeFutureEvent"))
        self.assertTrue(r.has("hook", path="plugin.json", sev="warning", text="SomeFutureEvent"), r.out)
        r = self.run_with({"hooks": {"PreToolUse": "nope"}})
        self.assertTrue(r.has("hook", path="plugin.json", text="expected a list of matcher groups"), r.out)

    def test_inline_hook_pointing_at_a_missing_script_is_flagged(self):
        r = self.run_with(hook_cfg('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/nope.py"'))
        self.assertTrue(r.has("plugin-root", path="plugin.json", text="does not exist"), r.out)

    def test_inline_hooks_must_be_an_object_path_or_list(self):
        r = self.run_with(5)
        self.assertTrue(r.has("hook", path="plugin.json", text="inline object, a path, or a list"), r.out)

    def test_hooks_file_other_than_the_default_gets_the_same_rules(self):
        for wrapped in (True, False):
            with self.subTest(wrapped=wrapped):
                ov = {"hooks/extra.json": json.dumps(hook_cfg("python hooks/guard.py", wrapped=wrapped))}
                r = self.run_with("./hooks/extra.json", ov)
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("hook", path="hooks/extra.json", text="bare 'python'"), r.out)
                self.assertTrue(r.has("hook", path="hooks/extra.json", text="command must start with python3"), r.out)

    def test_hooks_file_that_follows_the_rules_is_clean(self):
        ov = {"hooks/extra.json": json.dumps(hook_cfg(GOOD_CMD, "PostToolUseFailure"))}
        r = self.run_with("./hooks/extra.json", ov)
        self.assertEqual(r.rc, 0, r.out)

    def test_list_of_hook_sources_checks_every_entry(self):
        ov = {"hooks/extra.json": json.dumps(hook_cfg("python3 hooks/guard.py"))}
        r = self.run_with([hook_cfg("python hooks/inline.py"), "./hooks/extra.json"], ov)
        self.assertTrue(r.has("hook", path="plugin.json", text="bare 'python'"), r.out)
        self.assertTrue(r.has("hook", path="hooks/extra.json", text="must start with ${CLAUDE_PLUGIN_ROOT}/"), r.out)

    def test_hooks_file_problems(self):
        r = self.run_with("./hooks/missing.json")
        self.assertTrue(r.has("hook", path="plugin.json", text="hooks file does not exist"), r.out)
        r = self.run_with("./hooks/extra.json", {"hooks/extra.json": "{ not json"})
        self.assertTrue(r.has("hook", path="hooks/extra.json", text="not valid JSON"), r.out)
        self.assertNotIn("Traceback", r.err)
        r = self.run_with("../outside.json")
        self.assertTrue(r.has("hook", path="plugin.json", text="relative path inside the plugin"), r.out)
        r = self.run_with("/opt/x/hooks.json")
        self.assertTrue(r.has("hook", path="plugin.json", text="relative path inside the plugin"), r.out)
        r = self.run_with("./hooks/extra.txt", {"hooks/extra.txt": "x"})
        self.assertTrue(r.has("hook", path="plugin.json", text=".json file"), r.out)
        r = self.run_with("./hooks/extra.json", {"hooks/extra.json": "[]"})
        self.assertTrue(r.has("hook", path="hooks/extra.json", text="must be a JSON object"), r.out)

    def test_hooks_file_root_references_are_checked(self):
        ov = {"hooks/extra.json": json.dumps(hook_cfg('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/gone.py"'))}
        r = self.run_with("./hooks/extra.json", ov)
        self.assertTrue(r.has("plugin-root", path="hooks/extra.json", text="does not exist"), r.out)

    def test_hooks_file_that_escapes_through_a_link_is_flagged(self):
        outside = os.path.join(self.repo, "outside.json")
        H.write(outside, json.dumps(hook_cfg(GOOD_CMD)))
        root = self.plugin(manifest={"hooks": "./hooks/extra.json"})
        os.symlink(outside, os.path.join(root, "hooks", "extra.json"))
        r = self.lint("dojo-lab")
        self.assertTrue(r.has("hook", path="plugin.json", text="resolves outside the plugin"), r.out)

    def test_naming_the_default_file_is_only_a_warning_and_is_not_read_twice(self):
        r = self.run_with("./hooks/hooks.json", {"hooks/hooks.json": json.dumps(hook_cfg("python hooks/guard.py"))})
        self.assertEqual(sum(1 for l in r.lines if "bare 'python'" in l), 1, r.out)
        self.assertTrue(r.has("manifest", sev="warning", text="loads by default"), r.out)

    def test_register_ts_listed_from_a_manifest_hooks_file_counts_as_listed(self):
        cfg = hook_cfg(GOOD_CMD, modules=["./register.ts"])
        ov = {"hooks/extra.json": json.dumps(cfg), "hooks/register.ts": "export default function () {}\n"}
        r = self.run_with("./hooks/extra.json", ov)
        self.assertFalse(r.has("hook", text="does not list it in modules"), r.out)

    def test_hooks_file_modules_resolve_next_to_that_file(self):
        cfg = hook_cfg(GOOD_CMD, modules=["./nope.ts"])
        r = self.run_with("./hooks/extra.json", {"hooks/extra.json": json.dumps(cfg)})
        self.assertTrue(r.has("hook", path="hooks/extra.json", text="module does not exist"), r.out)

    def test_plugin_without_manifest_hooks_is_unchanged(self):
        r = self.lint_plugin()
        self.assertEqual(r.rc, 0, r.out)


# ---------------------------------------------------------------------------
# Symlinks
# ---------------------------------------------------------------------------

class TestSymlinks(H.Base):
    def linted(self, link_rel, target, **kw):
        root = self.plugin(**kw)
        path = os.path.join(root, link_rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.symlink(target, path)
        return self.lint("dojo-lab")

    def test_relative_link_inside_the_plugin_is_clean(self):
        r = self.linted("skills/lab/alias.md", "SKILL.md")
        self.assertEqual(r.rc, 0, r.out)
        r = self.linted("docs-link", "skills")
        self.assertEqual(r.rc, 0, r.out)

    def test_absolute_target_is_an_error(self):
        r = self.linted("lnk", "/opt/elsewhere/file.txt")
        self.assertEqual(r.rc, 1, r.out)
        self.assertTrue(r.has("symlink", path="lnk", text="absolute target"), r.out)

    def test_target_that_leaves_the_plugin_is_an_error(self):
        r = self.linted("skills/lab/up", "../../../elsewhere")
        self.assertTrue(r.has("symlink", text="leaves the plugin"), r.out)
        self.assertEqual(r.rc, 1, r.out)

    def test_dangling_link_is_an_error(self):
        r = self.linted("dangling", "no-such-file")
        self.assertTrue(r.has("symlink", text="does not exist"), r.out)

    def test_machine_path_in_the_target_is_an_internal_ref(self):
        r = self.linted("lnk", H.OP_PATH + "/notes.md")
        self.assertTrue(r.has("internal-ref", path="lnk", text="symlink target"), r.out)
        self.assertTrue(r.has("symlink", text="absolute target"), r.out)
        r = self.linted("lnk", H.OP_PATH_WIN + "\\notes.md")
        self.assertTrue(r.has("internal-ref", path="lnk", text="symlink target"), r.out)
        r = self.linted("lnk", H.OP_PATH_LINUX)
        self.assertTrue(r.has("internal-ref", text="symlink target"), r.out)

    def test_machine_path_used_as_the_link_location_is_an_internal_ref(self):
        parts = H.OP_PATH.strip("/").split("/")
        r = self.linted("/".join(parts[:2] + ["notes-link"]), "../../README.md")
        self.assertTrue(r.has("internal-ref", text="symlink name"), r.out)
        r = self.linted("docs/notes-link", "../README.md")
        self.assertEqual(r.rc, 0, r.out)

    def test_directory_links_are_found_even_though_the_walk_does_not_enter_them(self):
        r = self.linted("assets", "/opt/elsewhere")
        self.assertTrue(r.has("symlink", path="assets", text="absolute target"), r.out)
        r = self.linted("node_modules", "/opt/elsewhere")
        self.assertTrue(r.has("symlink", path="node_modules", text="absolute target"), r.out)

    def test_find_symlinks_lists_names_and_target_strings(self):
        root = self.plugin()
        os.symlink("SKILL.md", os.path.join(root, "skills", "lab", "alias.md"))
        os.symlink("/opt/x", os.path.join(root, "dirlink"))
        found = dict(SL.find_symlinks(Path(root)))
        self.assertEqual(found, {"skills/lab/alias.md": "SKILL.md", "dirlink": "/opt/x"})


# ---------------------------------------------------------------------------
# The dependency-only plugin
# ---------------------------------------------------------------------------

class TestSuitePlugin(H.Base):
    def suite(self, *args, **kw):
        H.make_suite(self.repo, **kw)
        return self.lint("dojo-suite", *args)

    def test_clean_suite_plugin(self):
        r = self.suite()
        self.assertEqual(r.rc, 0, r.out)
        self.assertEqual(len(r.lines), 1, r.out)

    def test_dependencies_are_required_and_must_be_a_list_of_names(self):
        r = self.suite(manifest=H.suite_manifest(dependencies=DELETE))
        self.assertTrue(r.has("suite-deps", text="missing dependencies"), r.out)
        r = self.suite(manifest=H.suite_manifest(deps="dojo-gates"))
        self.assertTrue(r.has("suite-deps", text="list of plugin names"), r.out)
        r = self.suite(manifest=H.suite_manifest(deps=[1, 2]))
        self.assertTrue(r.has("suite-deps", text="list of plugin names"), r.out)

    def test_every_suite_member_must_be_a_dependency(self):
        deps = [n for n in H.SUITE_MEMBERS if n != "dojo-meter"]
        r = self.suite(manifest=H.suite_manifest(deps=deps))
        self.assertEqual(r.rc, 1, r.out)
        self.assertTrue(r.has("suite-deps", text="suite plugin dojo-meter is not a dependency"), r.out)
        self.assertEqual(sum(1 for l in r.lines if "is not a dependency" in l), 1, r.out)

    def test_renamed_member_is_not_accepted_as_the_old_name(self):
        deps = [("dojo-dag" if n == "dojo-flow" else n) for n in H.SUITE_MEMBERS]
        r = self.suite(manifest=H.suite_manifest(deps=deps), member_dirs=H.SUITE_MEMBERS + ["dojo-dag"])
        self.assertTrue(r.has("suite-deps", text="dojo-flow is not a dependency"), r.out)

    def test_every_dependency_needs_a_plugin_directory(self):
        r = self.suite(member_dirs=[n for n in H.SUITE_MEMBERS if n != "dojo-doctor"])
        self.assertTrue(r.has("suite-deps", text="dependency dojo-doctor has no directory"), r.out)
        self.assertEqual(r.rc, 1)

    def test_every_dependency_must_be_listed_once_in_the_marketplace(self):
        r = self.suite(listed=[n for n in H.SUITE_MEMBERS if n != "dojo-gates"] + ["dojo-suite"])
        self.assertTrue(r.has("suite-marketplace", text="dojo-gates is not listed"), r.out)
        r = self.suite(listed=H.SUITE_MEMBERS + ["dojo-suite", "dojo-verify"])
        self.assertTrue(r.has("suite-marketplace", text="dojo-verify is listed 2 times"), r.out)

    def test_marketplace_problems(self):
        r = self.suite(marketplace="{ not json")
        self.assertTrue(r.has("suite-marketplace", text="not valid JSON"), r.out)
        r = self.suite(marketplace='{"name": "x"}')
        self.assertTrue(r.has("suite-marketplace", text="no plugins list"), r.out)
        self.assertEqual(r.rc, 1)

    def test_missing_marketplace_is_a_visible_warning_not_a_pass_by_silence(self):
        r = self.suite(marketplace=False)
        self.assertEqual(r.rc, 0, r.out)
        self.assertTrue(r.has("suite-marketplace", sev="warning", text="was not checked"), r.out)

    def test_extra_and_odd_dependencies(self):
        r = self.suite(manifest=H.suite_manifest(deps=H.SUITE_MEMBERS + ["dojo-craft"]), member_dirs=H.SUITE_MEMBERS + ["dojo-craft"],
                       listed=H.SUITE_MEMBERS + ["dojo-suite", "dojo-craft"])
        self.assertEqual(r.rc, 0, r.out)
        self.assertTrue(r.has("suite-deps", sev="warning", text="not one of the eight"), r.out)
        r = self.suite(manifest=H.suite_manifest(deps=H.SUITE_MEMBERS + ["dojo-gates"]))
        self.assertTrue(r.has("suite-deps", text="listed twice"), r.out)
        r = self.suite(manifest=H.suite_manifest(deps=H.SUITE_MEMBERS + ["dojo-suite"]))
        self.assertTrue(r.has("suite-deps", text="cannot depend on itself"), r.out)
        r = self.suite(manifest=H.suite_manifest(deps=H.SUITE_MEMBERS[:-1] + ["dojo-settle@dojo-genesis"]))
        self.assertTrue(r.has("suite-deps", text="bare plugin name"), r.out)

    def test_dependency_objects_with_a_name_are_read(self):
        deps = [{"name": n} for n in H.SUITE_MEMBERS]
        r = self.suite(manifest=H.suite_manifest(deps=deps))
        self.assertEqual(r.rc, 0, r.out)

    def test_no_components_allowed(self):
        r = self.suite(files={"skills/x/SKILL.md": fm(name="x", description="Use when you need x.") + "\nbody\n"})
        self.assertTrue(r.has("suite-deps", text="must not ship components"), r.out)
        r = self.suite(files={"README.md": "# dojo-suite\n\nInstalls the suite.\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_manifest_must_not_declare_any_component_key(self):
        inline_hooks = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": GOOD_CMD}]}]}}
        cases = {
            "hooks": inline_hooks,
            "mcpServers": {"x": {"command": "node", "args": ["server.js"]}},
            "lspServers": {"x": {"command": "x"}},
            "skills": "./skills",
            "agents": ["./agents/a.md"],
            "commands": "./commands",
            "outputStyles": "./output-styles",
            "monitors": "./monitors/monitors.json",
            "userConfig": {"k": {"type": "string", "title": "K", "description": "D"}},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                r = self.suite(manifest=H.suite_manifest(**{key: value}))
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("suite-deps", path="plugin.json", text="must not declare '%s'" % key), r.out)

    def test_manifest_with_an_unknown_key_is_an_error_and_display_name_is_allowed(self):
        r = self.suite(manifest=H.suite_manifest(extraThing=1))
        self.assertTrue(r.has("suite-deps", text="must not declare 'extraThing'"), r.out)
        r = self.suite(manifest=H.suite_manifest(displayName="dojo-suite - all eight", keywords=["suite"]))
        self.assertEqual(r.rc, 0, r.out)

    def test_inline_hook_in_the_suite_manifest_is_also_linted_as_a_hook(self):
        r = self.suite(manifest=H.suite_manifest(hooks={"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "python x.py"}]}]}}))
        self.assertTrue(r.has("hook", path="plugin.json", text="bare 'python'"), r.out)
        self.assertTrue(r.has("suite-deps", text="must not declare 'hooks'"), r.out)

    def test_root_level_settings_mcp_and_monitor_files_are_errors(self):
        for rel in (".mcp.json", "settings.json", "monitors/monitors.json", "hooks.json", "CLAUDE.md", ".DS_Store"):
            with self.subTest(rel=rel):
                r = self.suite(files={rel: "{}\n"})
                self.assertEqual(r.rc, 1, r.out)
                self.assertTrue(r.has("suite-deps", path=rel.split("/")[0], text="must not ship"), r.out)

    def test_extra_files_inside_the_plugin_metadata_folder_are_errors(self):
        r = self.suite(files={".claude-plugin/marketplace.json": "{}\n"})
        self.assertTrue(r.has("suite-deps", path=".claude-plugin/marketplace.json", text="ships only"), r.out)

    def test_readme_and_license_are_allowed_at_the_root(self):
        r = self.suite(files={"README.md": "# dojo-suite\n", "LICENSE": "Apache License\n"})
        self.assertEqual(r.rc, 0, r.out)

    def test_a_symlink_is_not_a_way_around_the_no_components_rule(self):
        root = H.make_suite(self.repo)
        os.makedirs(os.path.join(self.repo, "plugins", "dojo-gates", "skills"), exist_ok=True)
        os.symlink("../dojo-gates/skills", os.path.join(root, "skills"))
        r = self.lint("dojo-suite")
        self.assertEqual(r.rc, 1, r.out)
        self.assertTrue(r.has("suite-deps", path="skills", text="must not ship"), r.out)
        # and a link with an absolute target is flagged by the symlink rule too
        os.remove(os.path.join(root, "skills"))
        os.symlink("/opt/elsewhere", os.path.join(root, "extra"))
        r = self.lint("dojo-suite")
        self.assertTrue(r.has("symlink", path="extra", text="absolute target"), r.out)
        self.assertTrue(r.has("suite-deps", path="extra", text="must not ship"), r.out)

    def test_keywords_are_optional_here_and_nowhere_else(self):
        r = self.suite(manifest=H.suite_manifest(keywords=["suite"]))
        self.assertEqual(r.rc, 0, r.out)
        r = self.suite(manifest=H.suite_manifest(keywords=[]))
        self.assertTrue(r.has("manifest", text="keywords must be"), r.out)

    def test_exempt_from_the_kill_switch_and_budget_rules(self):
        files = {"hooks/guard.py": "import sys\n"}
        for i in range(5):
            files["skills/s%d/SKILL.md" % i] = fm(name="s%d" % i, description="Use when " + "x" * 241) + "\nb\n"
        r = self.suite(files=files)
        self.assertFalse(r.has("kill-switch"), r.out)
        self.assertFalse(r.has("budget"), r.out)
        # the same files in an ordinary plugin do trip both rules
        r = self.lint_plugin(overrides=dict(files, **{"skills/lab/SKILL.md": fm(name="lab", description="Use when " + "x" * 241) + "\nb\n"}))
        self.assertTrue(r.has("kill-switch"), r.out)
        self.assertTrue(r.has("budget"), r.out)

    def test_skip_suite_removes_both_rule_families(self):
        r = self.suite("--skip", "suite", manifest=H.suite_manifest(deps=["dojo-gates"]), listed=["dojo-gates"])
        self.assertEqual(r.rc, 0, r.out)

    def test_default_run_covers_the_suite_plugin_and_the_renamed_member(self):
        for n in H.SUITE_MEMBERS:
            self.plugin(n, manifest={"description": SL.PROMISES[n]})
        H.make_suite(self.repo)
        r = self.lint()
        self.assertEqual(r.rc, 0, r.out)
        self.assertIn("9 plugin(s)", r.out)

    def test_every_suite_member_has_a_frozen_promise_except_none_missing(self):
        self.assertEqual(sorted(SL.PROMISES), sorted(SL.SUITE))
        self.assertIn("dojo-flow", SL.PROMISES)
        self.assertNotIn("dojo-dag", SL.PROMISES)
        self.assertNotIn(SL.META_PLUGIN, SL.SUITE)


# ---------------------------------------------------------------------------
# Targets, exit codes, flags
# ---------------------------------------------------------------------------

class TestCli(H.Base):
    def test_nonexistent_plugin_exits_two(self):
        self.plugin()
        r = self.lint("dojo-nope")
        self.assertEqual(r.rc, 2, r.out + r.err)

    def test_repo_without_plugins_dir_exits_two(self):
        r = self.lint()
        self.assertEqual(r.rc, 2, r.out + r.err)

    def test_no_suite_plugins_exits_two(self):
        self.plugin("dojo-craft")
        r = self.lint()
        self.assertEqual(r.rc, 2, r.out + r.err)

    def test_default_targets_are_the_suite_names(self):
        self.plugin("dojo-gates")
        self.plugin("dojo-craft", manifest={"author": "Someone"})
        r = self.lint()
        self.assertEqual(r.rc, 1, r.out)
        self.assertIn("note: dojo-craft is not a suite plugin, not linted", r.out)
        self.assertFalse(r.has("manifest", path="dojo-craft"), r.out)
        for missing in ("dojo-protocol", "dojo-router", "dojo-meter", "dojo-verify", "dojo-flow", "dojo-doctor", "dojo-settle", "dojo-suite"):
            self.assertTrue(r.has("plugin", path=missing, text="not found"), r.out)
        self.assertFalse(r.has("plugin", path="dojo-gates"), r.out)

    def test_naming_a_non_suite_plugin_lints_it(self):
        self.plugin("dojo-craft", manifest={"author": "Someone"})
        r = self.lint("dojo-craft")
        self.assertTrue(r.has("manifest", path="dojo-craft", text="author must be"), r.out)

    def test_directory_path_target(self):
        root = self.plugin()
        r = self.lint(root)
        self.assertEqual(r.rc, 0, r.out)

    def test_skip_removes_a_rule(self):
        self.plugin(overrides={"README.md": "# t\n\npowerful\n"})
        self.assertEqual(self.lint("dojo-lab").rc, 1)
        self.assertEqual(self.lint("dojo-lab", "--skip", "voice,internal-ref").rc, 0)

    def test_skip_prefix_covers_a_rule_family(self):
        self.plugin(overrides={"scripts/m.py": "def f(x: int | None):\n    return x\n"})
        self.assertEqual(self.lint("dojo-lab").rc, 1)
        self.assertEqual(self.lint("dojo-lab", "--skip", "py39").rc, 0)

    def test_json_output_matches_text(self):
        self.plugin(overrides={"README.md": "# t\n\npowerful\n%s\n" % H.OP_PATH})
        text = self.lint("dojo-lab")
        js = self.lint("dojo-lab", "--json")
        doc = json.loads(js.out)
        self.assertEqual(js.rc, 1)
        n_err = int(text.lines[-1].split(", ")[2].split(" ")[0])
        self.assertEqual(doc["errors"], n_err)
        self.assertEqual(len([f for f in doc["findings"] if f["severity"] == "error"]), n_err)
        self.assertEqual({f["rule"] for f in doc["findings"]}, {"voice", "internal-ref"})
        self.assertEqual(doc["plugins"], ["dojo-lab"])

    def test_help_documents_exit_codes(self):
        r = self.lint("--help")
        self.assertEqual(r.rc, 0)
        self.assertIn("Warnings never change the exit code", r.out)

    def test_runs_from_any_directory_and_in_a_clean_environment(self):
        self.plugin()
        r = self.lint("dojo-lab", cwd=self.home)
        self.assertEqual(r.rc, 0, r.out + r.err)

    def test_runs_under_a_modern_python_too(self):
        import sys
        self.plugin()
        r = self.lint("dojo-lab", python=sys.executable)
        self.assertEqual(r.rc, 0, r.out + r.err)

    def test_files_are_read_but_the_tree_is_left_alone(self):
        root = self.plugin()
        before = sorted(os.path.join(d, f) for d, _s, fs in os.walk(root) for f in fs)
        self.lint("dojo-lab")
        after = sorted(os.path.join(d, f) for d, _s, fs in os.walk(root) for f in fs)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
