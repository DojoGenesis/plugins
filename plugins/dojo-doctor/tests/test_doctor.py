"""Tests for scripts/doctor.py.

Run:  cd plugins/dojo-doctor && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

Every subprocess gets an explicit environment (PATH and HOME only, no flag or config-dir variables) and an
explicit --project, so nothing on the machine running the tests can leak into a result.
"""
import sys

sys.dont_write_bytecode = True

import importlib.util
import io
import json
import os
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixtures as F  # noqa: E402

PLUGIN = os.path.dirname(HERE)
DOCTOR = os.path.join(PLUGIN, "scripts", "doctor.py")
SYSTEM_PYTHON = "/usr/bin/python3"


def load_module():
    spec = importlib.util.spec_from_file_location("doctor_under_test", DOCTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = F.Fixture(self.tmp.name)

    def run_doctor(self, *args, env_extra=None, home=True, python=None, drop_bytecode_guard=False, timeout=60):
        cmd = [python or sys.executable, DOCTOR]
        if home:
            cmd += ["--home", self.fx.home]
        cmd += ["--project", self.fx.project] + list(args)
        env = {"PATH": "/usr/bin:/bin", "HOME": self.fx.home}
        if not drop_bytecode_guard:
            env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.update(env_extra or {})
        return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)

    def run_json(self, *args, **kw):
        p = self.run_doctor("--json", *args, **kw)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return json.loads(p.stdout)

    def items(self, doc, sid, level=None, fid=None):
        out = doc["sections"][sid]["items"]
        if level:
            out = [i for i in out if i["level"] == level]
        if fid:
            out = [i for i in out if i["id"] == fid]
        return out

    def status(self, doc, sid):
        return doc["sections"][sid]["status"]

    def interp(self, *args, **kw):
        return self.run_json("--section", "interpreters", *args, **kw)


# --------------------------------------------------------------------------- 1. interpreters


class InterpreterTests(Base):
    def one_plugin(self, command, files=None, **kw):
        files = dict(files or {})
        files.setdefault("hooks/x.py", "print(1)\n")
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json(command, **kw), files=files)
        self.fx.save_settings()

    def test_bare_python_in_plugin_hooks_is_a_problem_with_a_fix(self):
        self.one_plugin('python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"')
        doc = self.interp()
        self.assertEqual(self.status(doc, "interpreters"), "problem")
        found = self.items(doc, "interpreters", "problem", "interp-bare-python")
        self.assertEqual(len(found), 1)
        self.assertIn("example-plugin", found[0]["text"])
        self.assertIn("python3", found[0]["fix"])

    def test_bare_python_is_a_problem_even_when_it_resolves_on_the_current_path(self):
        self.fx.fake_bin("python")
        self.one_plugin('python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"')
        doc = self.interp("--path", self.fx.bin + ":/usr/bin:/bin")
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))

    def test_exec_form_with_bare_python_is_flagged(self):
        hooks = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/x.py"]}]}]}}
        self.fx.plugin("example-plugin", hooks_text=hooks, files={"hooks/x.py": "print(1)\n"})
        self.fx.save_settings()
        self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"))

    def test_quoted_python_is_flagged(self):
        self.one_plugin('"python" "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"')
        self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"))

    def test_versioned_python_is_not_bare_python(self):
        self.one_plugin('python3.11 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"')
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", fid="interp-bare-python"))
        # absent on both PATHs: a normal missing-binary problem
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing"))
        # present only on the current PATH: a note, not a problem
        self.fx.fake_bin("python3.11")
        doc = self.interp("--path", self.fx.bin + ":/usr/bin:/bin")
        self.assertFalse(self.items(doc, "interpreters", "problem"))
        self.assertTrue(self.items(doc, "interpreters", "note", "interp-needs-path"))

    def test_python3_with_present_script_is_ok(self):
        script = os.path.join(self.fx.root, "present.py")
        self.fx.write_text(script, "print(1)\n")
        self.one_plugin('python3 "%s"' % script)
        doc = self.interp()
        self.assertEqual(self.status(doc, "interpreters"), "ok", doc["sections"]["interpreters"]["items"])

    def test_python3_with_missing_script_is_a_missing_script_problem(self):
        self.one_plugin('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/gone.py"')
        doc = self.interp()
        self.assertEqual(self.status(doc, "interpreters"), "problem")
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing-script"))

    def test_env_assignment_prefix_is_skipped_and_value_redacted(self):
        self.one_plugin("SECRET_TOKEN=hunter2value python \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\"")
        p = self.run_doctor("--section", "interpreters")
        self.assertIn("interp-bare-python", p.stdout)
        self.assertNotIn("hunter2value", p.stdout)
        self.assertIn("SECRET_TOKEN=<redacted>", p.stdout)

    def test_compound_command_finds_python_in_the_second_segment(self):
        self.one_plugin("cd /tmp && python foo.py || true")
        self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"))

    def test_direct_exec_script_without_exec_bit_is_flagged(self):
        root = self.fx.plugin(
            "example-plugin",
            hooks=self.fx.hooks_json('"${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"'),
            files={"hooks/run.sh": "#!/bin/sh\nexit 0\n"},
        )
        os.chmod(os.path.join(root, "hooks", "run.sh"), 0o644)
        self.fx.save_settings()
        doc = self.interp()
        found = self.items(doc, "interpreters", "problem", "interp-not-exec")
        self.assertEqual(len(found), 1)
        self.assertIn("126", found[0]["text"])

    def test_path_found_only_on_current_path(self):
        self.fx.fake_bin("mytool")
        self.one_plugin("mytool --flag")
        # only on --path: ok with a note
        doc = self.interp("--path", self.fx.bin + ":/usr/bin:/bin")
        self.assertEqual(self.status(doc, "interpreters"), "ok")
        notes = self.items(doc, "interpreters", "note", "interp-needs-path")
        self.assertEqual(len(notes), 1)
        self.assertIn("shell PATH", notes[0]["text"])
        # on both: ok, no note
        both = self.fx.bin + ":/usr/bin:/bin"
        doc = self.interp("--path", both, "--minimal-path", both)
        self.assertEqual(self.status(doc, "interpreters"), "ok")
        self.assertFalse(self.items(doc, "interpreters", "note"))
        # on neither: problem
        doc = self.interp()
        self.assertEqual(self.status(doc, "interpreters"), "problem")
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing"))

    def test_disabled_and_uninstalled_plugins_are_not_scanned(self):
        bad = self.fx.hooks_json("python x.py")
        self.fx.plugin("off-plugin", hooks=bad, enable=False)
        self.fx.enabled["ghost-plugin@fixture-market"] = True  # enabled but never installed
        self.fx.save_settings()
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", "problem"))
        self.assertTrue(self.items(doc, "interpreters", "note", "plugin-not-installed"))

    def test_project_and_local_settings_hooks_are_scanned(self):
        self.fx.save_settings()
        self.fx.project_settings({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python a.py"}]}]}})
        self.fx.project_settings({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python b.py"}]}]}}, local=True)
        doc = self.interp()
        owners = " ".join(i["text"] for i in self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.assertIn("project settings", owners)
        self.assertIn("local settings", owners)

    def test_garbage_files_are_could_not_check_not_a_crash(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python x.py"))
        self.fx.save_settings()
        self.fx.write_json(os.path.join(self.fx.claude, "settings.json"), "{ this is not json")
        self.fx.write_json(
            os.path.join(self.fx.project, ".claude", "settings.json"),
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/q.py"}]}]}},
        )
        # garbage hooks.json in a second plugin
        self.fx.plugin("broken-plugin", hooks_text="[[[ not json")
        # enabledPlugins lives in the settings file that is now garbage, so enable via project settings
        self.fx.project_settings(
            {
                "enabledPlugins": {"example-plugin@fixture-market": True, "broken-plugin@fixture-market": True},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/q.py"}]}]},
            }
        )
        doc = self.interp()
        could = self.items(doc, "interpreters", "could", "could-not-read")
        self.assertTrue(any("user settings" in c["text"] for c in could))
        self.assertTrue(any("broken-plugin" in c["text"] for c in could))
        # the readable files were still judged
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing-script"))

    def test_unresolved_variable_is_counted_not_flagged(self):
        self.one_plugin('python3 "${CLAUDE_PLUGIN_DATA}/x.py"; python3 "$UNKNOWN_VAR/y.py"')
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", "problem"))
        could = self.items(doc, "interpreters", "could", "could-not-check-commands")
        self.assertEqual(len(could), 1)
        self.assertIn("could not check 1 of 1", could[0]["text"])

    def test_command_substitution_and_fd_redirects_are_not_guessed_at(self):
        # each of these used to raise a false interp-missing problem
        for cmd in (
            "$(which python) foo.py",
            "`which python` x.py",
            '"$(git rev-parse --show-toplevel)/hooks/x.sh"',
            "python3 \"$(git rev-parse --show-toplevel)/hooks/x.py\"",
        ):
            self.fx = F.Fixture(tempfile.mkdtemp(dir=self.tmp.name))
            self.one_plugin(cmd)
            doc = self.interp()
            self.assertFalse(self.items(doc, "interpreters", "problem"), (cmd, doc["sections"]["interpreters"]["items"]))
            self.assertTrue(self.items(doc, "interpreters", "could", "could-not-check-commands"), cmd)

    def test_a_leading_fd_redirect_does_not_become_a_program(self):
        self.one_plugin("exec 2>/dev/null; python \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\"")
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", fid="interp-missing"))
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.fx = F.Fixture(tempfile.mkdtemp(dir=self.tmp.name))
        self.one_plugin("python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\" 2>/dev/null")
        self.assertEqual(self.status(self.interp(), "interpreters"), "ok")

    def test_the_bare_python_fix_has_no_plugin_root_placeholder(self):
        self.one_plugin('python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"')
        fix = self.items(self.interp(), "interpreters", "problem", "interp-bare-python")[0]["fix"]
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", fix)
        self.assertNotIn("<", fix)

    def test_unterminated_quote_is_could_not_check_for_that_command_only(self):
        hooks = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": 'python3 "unterminated'}, {"type": "command", "command": "python x.py"}]}
                ]
            }
        }
        self.fx.plugin("example-plugin", hooks_text=hooks)
        self.fx.save_settings()
        doc = self.interp()
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.assertTrue(self.items(doc, "interpreters", "could", "could-not-check-commands"))

    def test_wrappers_are_looked_through(self):
        for cmd in (
            "env FOO=1 python x.py",
            "exec python x.py",
            "command python x.py",
            "nohup python x.py",
        ):
            with self.subTest(cmd=cmd):
                self.fx.enabled.clear()
                self.fx.installed.clear()
                self.one_plugin(cmd)
                doc = self.interp()
                self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"), cmd)

    def test_shell_dash_c_strings_are_parsed_one_level(self):
        for cmd in ('bash -c "cd d && python x.py"', "sh -lc 'python x.py'"):
            with self.subTest(cmd=cmd):
                self.fx.enabled.clear()
                self.fx.installed.clear()
                self.one_plugin(cmd)
                self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"), cmd)

    def test_env_python3_with_script_is_ok(self):
        script = os.path.join(self.fx.root, "present.py")
        self.fx.write_text(script, "print(1)\n")
        self.one_plugin("/usr/bin/env python3 %s" % script)
        self.assertEqual(self.status(self.interp(), "interpreters"), "ok")

    def test_prefixed_assignment_with_bare_python_redacts_value(self):
        self.one_plugin("PYTHON=python3 python x.py")
        p = self.run_doctor("--section", "interpreters")
        self.assertIn("interp-bare-python", p.stdout)
        self.assertIn("PYTHON=<redacted>", p.stdout)

    def test_shebang_with_bare_python_is_flagged(self):
        for first_line in ("#!/usr/bin/env python", "#!/usr/bin/python"):
            with self.subTest(shebang=first_line):
                self.fx.enabled.clear()
                self.fx.installed.clear()
                self.fx.plugin(
                    "example-plugin",
                    hooks=self.fx.hooks_json('"${CLAUDE_PLUGIN_ROOT}/hooks/run.py"'),
                    files={"hooks/run.py": first_line + "\nprint(1)\n"},
                )
                self.fx.save_settings()
                doc = self.interp()
                found = self.items(doc, "interpreters", "problem", "interp-bare-python")
                self.assertTrue(found)
                self.assertIn("shebang", found[0]["text"])

    def test_project_dir_and_plugin_root_variables_resolve(self):
        script = os.path.join(self.fx.project, ".claude", "hooks", "x.sh")
        self.fx.exe(script)
        self.fx.save_settings(
            hooks={"Stop": [{"hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.sh'}]}]}
        )
        self.assertEqual(self.status(self.interp(), "interpreters"), "ok")
        os.remove(script)
        doc = self.interp()
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing-script"))

    def test_other_hook_types_are_skipped_and_powershell_is_could_not_check(self):
        hooks = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "prompt", "prompt": "hi"},
                            {"type": "agent", "prompt": "hi"},
                            {"type": "http", "url": "http://localhost/x"},
                            {"type": "mcp_tool", "server": "s", "tool": "t"},
                        ]
                    }
                ]
            }
        }
        self.fx.plugin("typed-plugin", hooks_text=hooks)
        self.fx.save_settings()
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", "could", "could-not-check-commands"))
        hooks2 = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "Get-Date", "shell": "powershell"}]}]}}
        self.fx.plugin("ps-plugin", hooks_text=hooks2)
        self.fx.save_settings()
        doc = self.interp()
        self.assertTrue(self.items(doc, "interpreters", "could", "could-not-check-commands"))

    def test_manifest_hooks_as_string_object_and_array_are_all_scanned(self):
        inline = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python inline.py"}]}]}}
        self.fx.plugin(
            "string-plugin",
            manifest={"hooks": "./extra/hooks.json"},
            files={"extra/hooks.json": json.dumps(self.fx.hooks_json("python from-string.py"))},
        )
        self.fx.plugin("object-plugin", manifest={"hooks": inline})
        self.fx.plugin(
            "array-plugin",
            manifest={"hooks": ["./extra/hooks.json", inline]},
            files={"extra/hooks.json": json.dumps(self.fx.hooks_json("python from-array.py"))},
        )
        self.fx.save_settings()
        doc = self.interp()
        text = " ".join(i["text"] for i in self.items(doc, "interpreters", "problem", "interp-bare-python"))
        for owner in ("string-plugin", "object-plugin", "array-plugin"):
            self.assertIn(owner, text)
        self.assertIn("from-string.py", text)
        self.assertIn("from-array.py", text)
        self.assertIn("inline.py", text)

    def test_manifest_hooks_path_escaping_or_missing_is_a_problem(self):
        self.fx.plugin("escape-plugin", manifest={"hooks": "../outside.json"})
        self.fx.plugin("missing-plugin", manifest={"hooks": "./nope.json"})
        self.fx.save_settings()
        doc = self.interp()
        found = self.items(doc, "interpreters", "problem", "interp-manifest")
        text = " ".join(i["text"] for i in found)
        self.assertIn("escape-plugin", text)
        self.assertIn("missing-plugin", text)

    def test_python3_with_relative_missing_script_is_could_not_check(self):
        self.one_plugin("python3 relative/path.py")
        doc = self.interp()
        self.assertFalse(self.items(doc, "interpreters", "problem"))
        self.assertTrue(self.items(doc, "interpreters", "could"))


class EnablementTests(Base):
    def bad(self):
        return self.fx.hooks_json("python x.py")

    def test_project_false_overrides_user_true(self):
        self.fx.plugin("example-plugin", hooks=self.bad())
        self.fx.save_settings()
        self.fx.project_settings({"enabledPlugins": {"example-plugin@fixture-market": False}})
        self.assertFalse(self.items(self.interp(), "interpreters", "problem"))

    def test_local_true_overrides_project_false(self):
        self.fx.plugin("example-plugin", hooks=self.bad(), enable=None)
        self.fx.save_settings()
        self.fx.project_settings({"enabledPlugins": {"example-plugin@fixture-market": False}})
        self.fx.project_settings({"enabledPlugins": {"example-plugin@fixture-market": True}}, local=True)
        self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"))

    def test_project_scope_install_needs_a_matching_project_path(self):
        self.fx.plugin("example-plugin", hooks=self.bad(), scope="project", project_path="/home/tester/elsewhere")
        self.fx.save_settings()
        self.assertFalse(self.items(self.interp(), "interpreters", "problem"))
        self.fx.installed.clear()
        self.fx.plugin("example-plugin", hooks=self.bad(), scope="project", project_path=self.fx.project)
        self.fx.save_settings()
        self.assertTrue(self.items(self.interp(), "interpreters", "problem", "interp-bare-python"))

    def test_synced_plugins_are_scanned_and_labelled(self):
        synced = os.path.join(self.fx.claude, "plugins", "synced", "org1", "synced-plugin")
        self.fx.write_json(os.path.join(synced, "hooks", "hooks.json"), self.bad())
        self.fx.save_settings()
        doc = self.interp()
        found = self.items(doc, "interpreters", "problem", "interp-bare-python")
        self.assertTrue(found)
        self.assertIn("synced org1/synced-plugin", found[0]["text"])

    def test_plugin_dirs_from_the_environment_are_scanned(self):
        extra = os.path.join(self.fx.root, "extra-plugin")
        self.fx.write_json(os.path.join(extra, "hooks", "hooks.json"), self.bad())
        self.fx.save_settings()
        doc = self.run_json("--section", "interpreters", env_extra={"CLAUDE_CODE_PLUGIN_DIRS": extra})
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))

    def test_enabled_plugin_with_missing_install_folder_is_a_problem(self):
        self.fx.plugin("lost-plugin", make_dir=False)
        self.fx.save_settings()
        doc = self.interp()
        self.assertTrue(self.items(doc, "interpreters", "problem", "plugin-path-missing"))

    def test_config_dir_flag_reads_settings_and_global_config_from_that_folder(self):
        cfg = os.path.join(self.fx.root, "alt-config")
        self.fx.write_json(
            os.path.join(cfg, "settings.json"),
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python alt.py"}]}]}, "env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}},
        )
        self.fx.write_json(os.path.join(cfg, ".claude.json"), {"cachedGrowthBookFeatures": {"tengu_plugin_hooks_modules": False}})
        p = self.run_doctor("--json", "--section", "interpreters,flag", home=False, env_extra=None)
        # no --home: uses HOME (the fixture home, which has no hooks); now point at the alt folder
        p = subprocess.run(
            [sys.executable, DOCTOR, "--config-dir", cfg, "--project", self.fx.project, "--json", "--section", "interpreters,flag"],
            env={"PATH": "/usr/bin:/bin", "HOME": self.fx.home, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
        )
        doc = json.loads(p.stdout)
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.assertTrue(doc["sections"]["flag"]["data"]["verdict"])  # settings env beats the cached false

    def test_explicit_home_beats_the_config_dir_variable(self):
        decoy = os.path.join(self.fx.root, "decoy")
        self.fx.write_json(
            os.path.join(decoy, "settings.json"),
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python decoy.py"}]}]}},
        )
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "python fixture.py"}]}]})
        p = self.run_doctor("--section", "interpreters", env_extra={"CLAUDE_CONFIG_DIR": decoy})
        self.assertIn("fixture.py", p.stdout)
        self.assertNotIn("decoy.py", p.stdout)


# --------------------------------------------------------------------------- 2. failures


class FailureTests(Base):
    def failures(self, *args, **kw):
        return self.run_json("--section", "failures", *args, **kw)

    def test_three_127_errors_group_under_the_status_message_and_name_the_owner(self):
        self.fx.plugin(
            "example-plugin",
            hooks=self.fx.hooks_json('python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"', status="Example nudge"),
        )
        self.fx.save_settings()
        time.sleep(0.05)
        lines = [F.error_line("s1", "u%d" % i, "Example nudge") for i in range(3)]
        self.fx.transcript(lines)
        doc = self.failures()
        sec = doc["sections"]["failures"]
        self.assertEqual(sec["status"], "problem")
        found = self.items(doc, "failures", "problem", "hook-failing")
        self.assertEqual(len(found), 1)
        self.assertIn("Example nudge", found[0]["text"])
        self.assertIn("example-plugin", found[0]["text"])
        self.assertIn("3 errors in 1 sessions", found[0]["text"])
        self.assertIn("interpreter missing", found[0]["text"])
        groups = sec["data"]["failure_groups"]
        self.assertEqual(groups[0]["count"], 3)

    def test_exit_126_is_classified_as_not_executable(self):
        self.fx.save_settings()
        self.fx.transcript(
            [F.error_line("s1", "u1", "run it", exit_code=126, stderr="/x/run.sh: Permission denied")]
        )
        doc = self.failures()
        text = " ".join(i["text"] for i in doc["sections"]["failures"]["items"])
        self.assertIn("not executable", text)

    def test_exit_code_as_int_and_string_both_parse(self):
        self.fx.save_settings()
        a = F.error_line("s1", "u1", "cmd one", exit_code=127)
        b = F.error_line("s1", "u2", "cmd one", exit_code=127)
        b["attachment"]["exitCode"] = "127"
        self.fx.transcript([a, b])
        doc = self.failures()
        groups = doc["sections"]["failures"]["data"]["failure_groups"]
        self.assertEqual(groups[0]["count"], 2)
        self.assertIn("exit 127 x2", doc["sections"]["failures"]["items"][0]["text"])

    def test_duplicate_uuid_lines_count_once(self):
        self.fx.save_settings()
        line = F.error_line("s1", "same-uuid", "cmd dup")
        self.fx.transcript([line, line], session="s1")
        self.fx.transcript([line], session="resumed")
        doc = self.failures()
        self.assertEqual(doc["sections"]["failures"]["data"]["failure_groups"][0]["count"], 1)

    def test_old_lines_old_files_bad_json_and_other_lines_are_skipped(self):
        self.fx.save_settings()
        old_ts = F.iso(30 * 86400)
        lines = [
            F.error_line("s1", "u-old", "cmd old", ts=old_ts),
            F.error_line("s1", "u-new", "cmd new"),
            {"type": "user", "uuid": "x", "message": "has no hook attachment"},
        ]
        self.fx.transcript(lines, raw_lines=['{"attachment": "hook_ broken', "not json at all hook_"])
        # a file older than the window is skipped whole, even if its lines are fresh
        self.fx.transcript([F.error_line("s2", "u-stale-file", "cmd stale")], session="stale", age_days=30)
        doc = self.failures()
        labels = [g["label"] for g in doc["sections"]["failures"]["data"]["failure_groups"]]
        self.assertEqual(labels, ["cmd new"])

    def test_timestamps_with_z_fractions_and_offsets_parse_and_bad_ones_are_counted(self):
        self.fx.save_settings()
        lines = [
            F.error_line("s1", "u1", "cmd ts", ts=F.iso(60, zulu=True, fraction=True)),
            F.error_line("s1", "u2", "cmd ts", ts=F.iso(60, zulu=False, fraction=False)),
            F.error_line("s1", "u3", "cmd ts", ts="not a timestamp"),
        ]
        self.fx.transcript(lines)
        doc = self.failures()
        self.assertEqual(doc["sections"]["failures"]["data"]["failure_groups"][0]["count"], 3)
        self.assertIn("unreadable timestamps", " ".join(doc["sections"]["failures"]["lines"]))

    def test_timeouts_are_counted_and_deliberate_blocks_are_excluded_but_noted(self):
        self.fx.save_settings()
        lines = [
            F.hook_line("hook_cancelled", "s1", "t1", command="slow hook", timedOut=True, timeoutMs=5000, durationMs=5000),
            F.hook_line("hook_cancelled", "s1", "t2", command="slow hook", timedOut=False, durationMs=10),
            F.hook_line("hook_blocking_error", "s1", "b1", event="PreToolUse", blockingError="no"),
        ]
        self.fx.transcript(lines)
        doc = self.failures()
        sec = doc["sections"]["failures"]
        timeouts = [i for i in sec["items"] if i["id"] == "hook-timeout" or i["id"] == "hook-timeout"]
        # a timed-out hook that is no longer configured is a note; the count is still right
        self.assertTrue(any("timed out 1 times" in i["text"] for i in sec["items"]))
        self.assertFalse(any(i["id"] == "hook-failing" for i in sec["items"]))
        self.assertIn("1 deliberate blocks", " ".join(sec["lines"]))
        self.assertEqual(timeouts and timeouts[0]["level"], "note")

    def test_timeout_for_a_configured_hook_is_a_problem(self):
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/x.py", "statusMessage": "Slow one"}]}]})
        time.sleep(0.05)
        self.fx.transcript([F.hook_line("hook_cancelled", "s1", "t1", command="Slow one", timedOut=True, timeoutMs=5000)])
        doc = self.failures()
        self.assertTrue(self.items(doc, "failures", "problem", "hook-timeout"))

    def test_stderr_excerpt_is_redacted_and_truncated(self):
        self.fx.save_settings()
        secret_one = "sk-" + "a1b2c3d4e5f6g7h8"
        line = F.error_line(
            "s1",
            "u1",
            "cmd secret",
            exit_code=1,
            stderr="Authorization: Bearer abc123xyz https://u:p@host.example/x " + secret_one + " API_KEY=qwertyvalue",
        )
        self.fx.transcript([line])
        p = self.run_doctor("--section", "failures")
        for leaked in ("abc123xyz", "u:p@", secret_one, "qwertyvalue"):
            self.assertNotIn(leaked, p.stdout)
        self.assertIn("<redacted>", p.stdout)

    def test_long_stderr_is_cut_to_the_excerpt_limit_and_control_characters_are_removed(self):
        self.fx.save_settings()
        self.fx.transcript(
            [
                F.error_line("s1", "u1", "cmd long", exit_code=1, stderr="x" * 5000),
                F.error_line("s1", "u2", "cmd ansi", exit_code=1, stderr="\x1b[31mred\x1b[0m\x07 bell"),
            ]
        )
        p = self.run_doctor("--section", "failures")
        self.assertNotIn("\x1b", p.stdout)
        self.assertNotIn("\x07", p.stdout)
        for line in p.stdout.splitlines():
            if 'stderr (quoted data): "' in line:
                excerpt = line.split('stderr (quoted data): "', 1)[1].rsplit('"', 1)[0]
                self.assertLessEqual(len(excerpt), 120)
        self.assertNotIn("x" * 200, p.stdout)

    def test_subagent_transcripts_are_scanned(self):
        self.fx.save_settings()
        self.fx.transcript([F.error_line("s1", "u1", "cmd sub")], subagent=True)
        doc = self.failures()
        self.assertEqual(doc["sections"]["failures"]["data"]["failure_groups"][0]["count"], 1)

    def test_async_failures_are_counted_per_event_and_not_dropped_by_the_prefilter(self):
        self.fx.save_settings()
        lines = [
            F.hook_line("async_hook_response", "s1", "a1", event="PostToolUse", exitCode=1, stderr="", stdout="", processId="1"),
            F.hook_line("async_hook_response", "s1", "a2", event="PostToolUse", exitCode=0, stderr="", stdout="", processId="2"),
        ]
        odd = F.hook_line("async_hook_response", "s2", "a3", exitCode=1, stderr="", stdout="", processId="3")
        odd["attachment"]["hookName"] = "PostToolUse:mcp__abc__sometool"
        del odd["attachment"]["hookEvent"]
        self.fx.transcript(lines + [odd])
        p = self.run_doctor("--json", "--section", "failures")
        doc = json.loads(p.stdout)
        found = self.items(doc, "failures", "problem", "hook-failing-async")
        self.assertEqual(len(found), 1)
        self.assertIn("2 non-zero results in 2 sessions", found[0]["text"])
        self.assertNotIn("abc", p.stdout)
        self.assertNotIn("sometool", p.stdout)

    def test_ambiguous_and_no_longer_configured_labels(self):
        self.fx.plugin("first-plugin", hooks=self.fx.hooks_json("python3 /nonexistent/a.py", status="Shared label"))
        self.fx.plugin("second-plugin", hooks=self.fx.hooks_json("python3 /nonexistent/b.py", status="Shared label"))
        self.fx.save_settings()
        time.sleep(0.05)
        self.fx.transcript([F.error_line("s1", "u1", "Shared label"), F.error_line("s1", "u2", "A label nobody configures")])
        doc = self.failures()
        sec = doc["sections"]["failures"]
        by_label = {i["text"].split(":")[0]: i for i in sec["items"]}
        self.assertEqual(by_label["Shared label"]["level"], "problem")
        self.assertIn("ambiguous", by_label["Shared label"]["text"])
        self.assertIn("first-plugin", by_label["Shared label"]["text"])
        self.assertIn("second-plugin", by_label["Shared label"]["text"])
        self.assertEqual(by_label["A label nobody configures"]["level"], "note")
        self.assertIn("no longer configured", by_label["A label nobody configures"]["text"])

    def test_only_unconfigured_failures_do_not_make_the_section_a_problem(self):
        self.fx.save_settings()
        self.fx.transcript([F.error_line("s1", "u1", "A label nobody configures")])
        doc = self.failures()
        self.assertEqual(self.status(doc, "failures"), "ok")

    def test_config_changed_since_last_failure_is_noted(self):
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/x.py", "statusMessage": "Edited since"}]}]})
        self.fx.transcript([F.error_line("s1", "u1", "Edited since", ts=F.iso(3600))])
        doc = self.failures()
        self.assertIn("config changed since last failure", doc["sections"]["failures"]["items"][0]["text"])

    def test_zero_transcripts_is_could_not_check_never_ok(self):
        self.fx.save_settings()
        doc = self.failures()
        self.assertEqual(self.status(doc, "failures"), "could not check")
        os.makedirs(os.path.join(self.fx.claude, "projects"), exist_ok=True)
        doc = self.failures()
        self.assertEqual(self.status(doc, "failures"), "could not check")

    def test_transcripts_without_any_hook_record_are_not_a_clean_bill(self):
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/x.py"}]}]})
        self.fx.transcript([{"type": "user", "uuid": "x", "message": "hello"}])
        doc = self.failures()
        self.assertEqual(self.status(doc, "failures"), "could not check")
        self.assertTrue(self.items(doc, "failures", "could", "no-hook-records"))

    def test_a_fifo_named_like_a_transcript_is_skipped_not_waited_on(self):
        self.fx.save_settings()
        proj = os.path.join(self.fx.claude, "projects", "p1")
        os.makedirs(proj, exist_ok=True)
        os.mkfifo(os.path.join(proj, "x.jsonl"))
        self.fx.transcript([F.error_line("s1", "u1", "cmd fifo")], session="real")
        t0 = time.monotonic()
        p = self.run_doctor("--json", "--section", "failures", timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(time.monotonic() - t0, 10)
        doc = json.loads(p.stdout)
        self.assertTrue(any("fifo" in i["text"] for i in doc["sections"]["failures"]["items"]), doc["sections"]["failures"])

    def test_an_over_long_line_is_skipped_and_the_next_line_is_still_read(self):
        self.fx.save_settings()
        mod = load_module()
        big = "x" * (mod.LINE_CAP * 2 + 10)
        lines = [{"type": "user", "uuid": "p1", "message": big}, F.error_line("s1", "u1", "cmd after-long")]
        self.fx.transcript(lines, session="s1")
        doc = self.run_json("--section", "failures")
        self.assertTrue(any("after-long" in i["text"] for i in doc["sections"]["failures"]["items"]), doc["sections"]["failures"])

    def test_size_budget_stops_the_scan_and_says_so(self):
        self.fx.save_settings()
        big = "x" * 100000
        for n in range(3):
            lines = [{"type": "user", "uuid": "p%d-%d" % (n, i), "message": big} for i in range(15)]
            lines.append(F.error_line("s%d" % n, "e%d" % n, "cmd budget"))
            self.fx.transcript(lines, session="s%d" % n)
        p = self.run_doctor("--json", "--section", "failures", "--max-mb", "2")
        doc = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0)
        self.assertIn("stopped at the size budget", " ".join(doc["sections"]["failures"]["lines"]))

    def test_a_single_file_over_the_size_budget_is_could_not_check_not_ok(self):
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/x.py"}]}]})
        big = "x" * 100000
        lines = [{"type": "user", "uuid": "p%d" % i, "message": big} for i in range(25)]
        self.fx.transcript(lines)
        doc = self.failures("--max-mb", "1")
        self.assertEqual(self.status(doc, "failures"), "could not check")
        self.assertIn("size budget", doc["sections"]["failures"]["items"][0]["text"])

    def test_time_budget_stops_the_scan_and_says_so(self):
        mod = load_module()
        self.fx.save_settings()
        self.fx.transcript([F.error_line("s1", "u1", "cmd late")])
        ctx = mod.Ctx()
        ctx.config_dir = self.fx.claude
        ctx.days = 7
        ctx.now = time.time()
        ctx.max_mb = 100
        ctx.deadline = time.monotonic() - 1  # already over
        ctx.home = self.fx.home
        scan = mod.scan_transcripts(ctx)
        self.assertEqual(scan.stopped, "time")
        self.assertIn("stopped at the time budget", mod.coverage_line(ctx, scan))


# --------------------------------------------------------------------------- 3. injection


class InjectionTests(Base):
    def test_per_event_total_counts_the_context_record_once_and_hooks_split_it(self):
        self.fx.save_settings()
        text = "héllo"  # 6 utf-8 bytes
        payload = json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})
        lines = [
            # session one: the same injection in both record types
            F.success_line("s1", "hs1", "Example inject", payload),
            F.context_line("s1", "hc1", [text]),
            # session two: a list with a non-string element that must be ignored
            F.context_line("s2", "hc2", [text, "xx", 5, None]),
            # plain, non-JSON SessionStart stdout is attributed too
            F.success_line("s2", "hs2", "Plain hook", "plain text"),
            # malformed JSON stdout is ignored
            F.success_line("s2", "hs3", "Broken hook", '{"hookSpecificOutput": '),
        ]
        self.fx.transcript(lines)
        p = self.run_doctor("--json", "--section", "injection")
        doc = json.loads(p.stdout)
        data = doc["sections"]["injection"]["data"]
        event = [e for e in data["events"] if e["event"] == "SessionStart"][0]
        self.assertEqual(event["runs"], 2)
        self.assertEqual(event["sessions"], 2)
        self.assertEqual(event["mean_bytes_per_session"], 7.0)  # (6 + 8) / 2, not doubled by hook_success
        self.assertEqual(event["max_bytes_per_session"], 8)
        self.assertEqual(event["est_tokens_mean_per_session"], 2)  # 7 / 4 = 1.75
        labels = {h["label"]: h for h in data["hooks"]}
        self.assertEqual(labels["Example inject"]["mean_bytes_per_run"], 6.0)
        self.assertEqual(labels["Plain hook"]["mean_bytes_per_run"], 10.0)
        self.assertNotIn("Broken hook", labels)
        self.assertIn("estimate", p.stdout)

    def test_events_without_per_hook_records_say_so(self):
        self.fx.save_settings()
        self.fx.transcript([F.context_line("s1", "c1", ["abcd"], event="UserPromptSubmit")])
        p = self.run_doctor("--section", "injection")
        self.assertIn("per hook: not recorded", p.stdout)

    def test_heavy_injection_is_a_problem_at_the_flag_line(self):
        self.fx.save_settings()
        self.fx.transcript([F.context_line("s1", "c1", ["z" * 12000], event="UserPromptSubmit")])
        doc = self.run_json("--section", "injection")
        self.assertTrue(self.items(doc, "injection", "problem", "inject-heavy"))
        doc = self.run_json("--section", "injection", "--inject-bytes", "50000")
        self.assertEqual(self.status(doc, "injection"), "ok")

    def test_hook_names_with_server_ids_are_grouped_by_event(self):
        self.fx.save_settings()
        line = F.context_line("s1", "c1", ["abcd"], event="PostToolUse")
        line["attachment"]["hookName"] = "PostToolUse:mcp__abc123__sometool"
        self.fx.transcript([line])
        p = self.run_doctor("--section", "injection")
        self.assertNotIn("abc123", p.stdout)
        self.assertIn("PostToolUse", p.stdout)


# --------------------------------------------------------------------------- 4. always-on weight


SKILL_A = '---\nname: skill-a\ndescription: "abcd"\n---\nbody\n'
SKILL_B = "---\nname: skill-b\ndescription: >\n  one two\n  three\n---\nbody\n"
SKILL_C = "---\nname: skill-c\ndescription: |\n  line1\n  line2\n---\nbody\n"
SKILL_D = "---\nname: skill-d\ndescription: xx\nwhen_to_use: yyy\n---\nbody\n"
SKILL_E = "---\nname: skill-e\ndisable-model-invocation: true\ndescription: zzzzzzzz\n---\nbody\n"
SKILL_F = "---\nname: skill-f\n---\n# Heading here\ntext\n"
SKILL_G = "---\nname: skill-g\ndescription: %s\n---\nbody\n" % ("x" * 2000)
AGENT_A = "---\nname: agent-a\ndescription: agent desc\nmodel: haiku\n---\nbody\n"
COMMAND_A = '---\ndescription: "cmd"\n---\nbody\n'


class WeightTests(Base):
    def build(self):
        files = {
            "skills/skill-a/SKILL.md": SKILL_A,
            "skills/skill-b/SKILL.md": SKILL_B,
            "skills/skill-c/SKILL.md": SKILL_C,
            "skills/skill-d/SKILL.md": SKILL_D,
            "skills/skill-e/SKILL.md": SKILL_E,
            "skills/skill-f/SKILL.md": SKILL_F,
            "skills/skill-g/SKILL.md": SKILL_G,
            "agents/agent-a.md": AGENT_A,
            "commands/cmd-a.md": COMMAND_A,
        }
        self.fx.plugin("weighty", files=files)
        self.fx.write_text(os.path.join(self.fx.claude, "skills", "mine", "SKILL.md"), '---\nname: mine\ndescription: "uuuu"\n---\nx\n')
        self.fx.save_settings()

    def test_counts_match_hand_computed_numbers(self):
        self.build()
        p = self.run_doctor("--json", "--section", "weight", "--all")
        doc = json.loads(p.stdout)
        data = doc["sections"]["weight"]["data"]
        rows = {r["label"]: r for r in data["rows"]}
        # 4 + 13 + 11 + 8 + 0 + 12 + 1536 + 10 + 3
        self.assertEqual(rows["weighty"]["chars"], 1597)
        self.assertEqual(rows["weighty"]["skills"], 7)
        self.assertEqual(rows["weighty"]["agents"], 1)
        self.assertEqual(rows["weighty"]["commands"], 1)
        self.assertEqual(rows["user (~/.claude)"]["chars"], 4)
        self.assertEqual(data["total_chars"], 1601)
        self.assertEqual(data["estimated_tokens"], 400)  # 1601 / 4 = 400.25
        self.assertIn("estimate", p.stdout)
        self.assertIn("cut", p.stdout)  # the 2,000-character description
        self.assertIn("name-only", p.stdout)  # disable-model-invocation
        self.assertIn("no description; first body line used", p.stdout)

    def test_listing_over_budget_is_a_problem_and_default_budget_is_derived(self):
        self.build()
        doc = self.run_json("--section", "weight")
        self.assertEqual(doc["sections"]["weight"]["data"]["listing_budget"], 8000)
        self.assertEqual(self.status(doc, "weight"), "ok")
        doc = self.run_json("--section", "weight", "--listing-budget", "100")
        self.assertTrue(self.items(doc, "weight", "problem", "weight-heavy"))

    def test_budget_variable_in_the_environment_is_honoured(self):
        self.build()
        doc = self.run_json("--section", "weight", env_extra={"SLASH_COMMAND_TOOL_CHAR_BUDGET": "50"})
        self.assertTrue(self.items(doc, "weight", "problem", "weight-heavy"))

    def test_settings_env_budget_beats_the_default_and_names_its_source(self):
        self.build()
        self.fx.save_settings(env={"SLASH_COMMAND_TOOL_CHAR_BUDGET": "50"})
        doc = self.run_json("--section", "weight")
        self.assertEqual(doc["sections"]["weight"]["data"]["listing_budget"], 50)
        self.assertTrue(self.items(doc, "weight", "problem", "weight-heavy"))
        self.assertIn("settings env", " ".join(doc["sections"]["weight"]["lines"]))

    def test_settings_env_wins_over_the_process_env_for_the_budget(self):
        self.build()
        self.fx.save_settings(env={"SLASH_COMMAND_TOOL_CHAR_BUDGET": "123456"})
        doc = self.run_json("--section", "weight", env_extra={"SLASH_COMMAND_TOOL_CHAR_BUDGET": "50"})
        self.assertEqual(doc["sections"]["weight"]["data"]["listing_budget"], 123456)

    def test_the_listing_fraction_setting_scales_the_budget(self):
        self.build()
        self.fx.save_settings(skillListingBudgetFraction=0.001)
        doc = self.run_json("--section", "weight")
        self.assertEqual(doc["sections"]["weight"]["data"]["listing_budget"], 800)
        text = " ".join(doc["sections"]["weight"]["lines"])
        self.assertIn("skillListingBudgetFraction", text)
        self.assertIn("1M-context", text)

    def test_the_user_row_is_labelled_with_the_folder_that_was_read(self):
        self.build()
        other = os.path.join(self.fx.root, "other-config")
        self.fx.write_text(os.path.join(other, "skills", "mine", "SKILL.md"), '---\nname: mine\ndescription: "uuuu"\n---\nx\n')
        p = self.run_doctor("--json", "--section", "weight", "--config-dir", other, home=False)
        labels = [r["label"] for r in json.loads(p.stdout)["sections"]["weight"]["data"]["rows"]]
        self.assertFalse(any(l.startswith("user (~/.claude)") for l in labels), labels)
        self.assertTrue(any(l.startswith("user (") and "other-config" in l for l in labels), labels)

    def test_rows_are_capped_by_default_and_all_lifts_the_cap(self):
        for n in range(14):
            self.fx.plugin("plug%02d" % n, files={"skills/s/SKILL.md": '---\nname: s\ndescription: "%s"\n---\n' % ("d" * (n + 1))})
        self.fx.save_settings()
        capped = self.run_doctor("--section", "weight").stdout
        full = self.run_doctor("--section", "weight", "--all").stdout
        self.assertIn("more sources (use --all)", capped)
        self.assertNotIn("more sources (use --all)", full)
        self.assertGreater(len(full), len(capped))

    def test_frontmatter_parser_handles_each_style(self):
        mod = load_module()
        fm, body = mod.parse_frontmatter("---\nname: x\ndescription: 'it''s quoted'\n---\nbody")
        self.assertEqual(fm["description"], "it's quoted")
        fm, _ = mod.parse_frontmatter("---\ndescription: >-\n  folded\n  across lines\n\n  second paragraph\n---\n")
        self.assertEqual(fm["description"], "folded across lines\nsecond paragraph")
        fm, _ = mod.parse_frontmatter("---\ndescription: plain\n  continues here\n---\n")
        self.assertEqual(fm["description"], "plain continues here")
        fm, body = mod.parse_frontmatter("no frontmatter here")
        self.assertEqual(fm, {})


# --------------------------------------------------------------------------- 5. flag


class FlagTests(Base):
    def verdict(self, env=None, cache="skip", settings_env=None, extra_settings=None):
        if cache != "skip":
            if isinstance(cache, str):
                self.fx.write_json(os.path.join(self.fx.home, ".claude.json"), cache)
            elif cache is not None:
                self.fx.global_config({"cachedGrowthBookFeatures": cache})
        settings = dict(extra_settings or {})
        if settings_env is not None:
            settings["env"] = settings_env
        self.fx.save_settings(**settings)
        doc = self.run_json("--section", "flag", env_extra=env)
        return doc, doc["sections"]["flag"]["data"]["verdict"]

    def test_environment_one_beats_a_false_cache(self):
        doc, verdict = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}, cache={"tengu_plugin_hooks_modules": False})
        self.assertIs(verdict, True)
        self.assertEqual(self.status(doc, "flag"), "ok")

    def test_environment_zero_beats_a_true_cache(self):
        _, verdict = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"}, cache={"tengu_plugin_hooks_modules": True})
        self.assertIs(verdict, False)

    def test_settings_env_zero_beats_a_true_cache(self):
        _, verdict = self.verdict(settings_env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"}, cache={"tengu_plugin_hooks_modules": True})
        self.assertIs(verdict, False)

    def test_settings_env_beats_the_shell_because_claude_code_applies_it_on_top(self):
        _, verdict = self.verdict(
            env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"},
            settings_env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"},
            cache={"tengu_plugin_hooks_modules": False},
        )
        self.assertIs(verdict, True)
        _, verdict = self.verdict(
            env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"},
            settings_env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"},
        )
        self.assertIs(verdict, False)

    def test_settings_env_one_turns_it_on(self):
        _, verdict = self.verdict(settings_env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}, cache={"tengu_plugin_hooks_modules": False})
        self.assertIs(verdict, True)

    def test_cache_values(self):
        _, verdict = self.verdict(cache={"tengu_plugin_hooks_modules": True})
        self.assertIs(verdict, True)
        _, verdict = self.verdict(cache={"tengu_plugin_hooks_modules": False})
        self.assertIs(verdict, False)

    def test_missing_cache_key_means_on_by_default_never_off(self):
        doc, verdict = self.verdict(cache={})
        self.assertIs(verdict, True)
        self.assertIn("default", doc["sections"]["flag"]["data"]["source"])
        self.assertEqual(self.status(doc, "flag"), "ok")

    def test_missing_or_garbage_global_config_is_default_with_a_could_not_check_note(self):
        doc, verdict = self.verdict(cache="skip")  # no .claude.json at all
        self.assertIs(verdict, True)
        self.assertEqual(self.status(doc, "flag"), "could not check")
        doc, verdict = self.verdict(cache="{ not json")
        self.assertIs(verdict, True)
        self.assertEqual(self.status(doc, "flag"), "could not check")

    def test_unrecognised_value_is_could_not_check(self):
        doc, verdict = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "maybe"}, cache={"tengu_plugin_hooks_modules": True})
        self.assertIsNone(verdict)
        self.assertEqual(self.status(doc, "flag"), "could not check")

    def test_disable_all_hooks_with_a_configured_hook_is_a_problem(self):
        doc, _ = self.verdict(
            cache={},
            extra_settings={"disableAllHooks": True, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 /nonexistent/a.py"}]}]}},
        )
        self.assertTrue(self.items(doc, "flag", "problem", "flag-disabled-all-hooks"))

    def module_plugin(self, name="modp", modules=("./register.ts",), register=True, enable=True):
        files = {}
        if register:
            files["hooks/register.ts"] = "// mod\n"
        hooks_text = {"hooks": {}, "modules": list(modules)} if modules is not None else {"hooks": {}}
        return self.fx.plugin(name, hooks_text=hooks_text, files=files, enable=enable)

    def test_module_plugin_with_flag_off_is_a_problem_and_on_is_ok(self):
        self.module_plugin()
        doc, _ = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"}, cache={})
        self.assertTrue(self.items(doc, "flag", "problem", "flag-off-mods-shipped"))
        doc, _ = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}, cache={})
        self.assertEqual(self.status(doc, "flag"), "ok")

    def test_no_module_plugins_and_flag_off_is_ok(self):
        self.fx.plugin("plain", hooks=self.fx.hooks_json("python3 /nonexistent/a.py"))
        doc, verdict = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"}, cache={})
        self.assertIs(verdict, False)
        self.assertEqual(self.status(doc, "flag"), "ok")
        self.assertIn("No enabled plugin ships a mod", " ".join(doc["sections"]["flag"]["lines"]))

    def test_register_file_not_listed_in_modules_is_a_problem(self):
        self.module_plugin(modules=None)
        doc, _ = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}, cache={})
        self.assertTrue(self.items(doc, "flag", "problem", "flag-register-orphan"))

    def test_module_naming_a_missing_file_is_a_problem(self):
        self.module_plugin(modules=("./gone.ts",), register=False)
        doc, _ = self.verdict(env={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}, cache={})
        self.assertTrue(self.items(doc, "flag", "problem", "flag-module-missing"))


# --------------------------------------------------------------------------- 6. python3


class PythonTests(Base):
    def fake_python(self, version_text, marker=None):
        script = "#!/bin/sh\n"
        if marker:
            script += 'echo ran > "%s"\n' % marker
        script += 'echo "%s"\n' % version_text
        return self.fx.fake_bin("python3", script)

    def python(self, *args, **kw):
        self.fx.save_settings()
        return self.run_json("--section", "python", "--minimal-path", self.fx.bin, "--path", self.fx.bin, *args, **kw)

    def test_version_39_is_ok_and_37_is_a_problem(self):
        self.fake_python("Python 3.9.6")
        doc = self.python()
        self.assertEqual(self.status(doc, "python"), "ok", doc["sections"]["python"])
        self.fake_python("Python 3.7.0")
        doc = self.python()
        self.assertEqual(self.status(doc, "python"), "problem")
        self.assertTrue(self.items(doc, "python", "problem", "python-old"))

    def test_no_exec_never_runs_the_interpreter(self):
        marker = os.path.join(self.fx.root, "probe-marker")
        self.fake_python("Python 3.9.6", marker=marker)
        doc = self.python("--no-exec")
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(self.items(doc, "python", "could", "python-not-probed"))

    def test_probe_runs_otherwise(self):
        marker = os.path.join(self.fx.root, "probe-marker")
        self.fake_python("Python 3.9.6", marker=marker)
        self.python()
        self.assertTrue(os.path.exists(marker))

    def test_a_broken_interpreter_is_a_problem_with_its_output(self):
        self.fx.fake_bin("python3", "#!/bin/sh\necho 'xcode-select: error: no developer tools' >&2\nexit 1\n")
        doc = self.python()
        found = self.items(doc, "python", "problem", "python-broken")
        self.assertTrue(found)
        self.assertIn("no developer tools", found[0]["text"])

    def test_a_hanging_interpreter_is_stopped_within_the_deadline(self):
        self.fx.fake_bin("python3", "#!/bin/sh\n/bin/sleep 10\n")
        start = time.time()
        doc = self.python("--time-budget", "3")
        self.assertLess(time.time() - start, 6)
        self.assertTrue(self.items(doc, "python", "could", "python-probe-timeout"))

    def test_the_running_interpreter_is_not_probed_when_it_is_the_one_on_the_path(self):
        os.symlink(os.path.realpath(sys.executable), os.path.join(self.fx.bin, "python3"))
        doc = self.python()
        data = doc["sections"]["python"]["data"]
        self.assertEqual(data["version"], data["running"])

    def test_python3_missing_everywhere_is_a_problem(self):
        doc = self.python()
        self.assertTrue(self.items(doc, "python", "problem", "python-missing"))


# --------------------------------------------------------------------------- safety, secrets, cli


class SafetyTests(Base):
    def test_a_hook_command_is_never_executed(self):
        marker = os.path.join(self.fx.root, "executed-marker")
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("touch '%s'" % marker))
        self.fx.save_settings(hooks={"Stop": [{"hooks": [{"type": "command", "command": "touch '%s'" % marker}]}]})
        p = self.run_doctor()
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(marker))

    def test_nothing_is_written_to_the_home_tree_or_the_plugin_folder(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python x.py", status="Some hook"))
        self.fx.save_settings()
        self.fx.transcript([F.error_line("s1", "u1", "Some hook"), F.context_line("s1", "c1", ["abc"])])
        before_home = F.tree_hash(self.fx.root)
        before_plugin = F.tree_hash(PLUGIN)
        p = self.run_doctor(drop_bytecode_guard=True, python=SYSTEM_PYTHON if os.path.exists(SYSTEM_PYTHON) else None)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(before_home, F.tree_hash(self.fx.root))
        self.assertEqual(before_plugin, F.tree_hash(PLUGIN))
        self.assertFalse(os.path.isdir(os.path.join(PLUGIN, "scripts", "__pycache__")))

    def test_settings_env_values_never_appear_in_the_report(self):
        token = "ghp_" + "S3cretSyntheticValue1234567890"
        self.fx.save_settings(env={"GITHUB_TOKEN": token, "OTHER_KEY": "plainsecretvalue"})
        for extra in ((), ("--json",)):
            p = self.run_doctor(*extra)
            self.assertNotIn(token, p.stdout)
            self.assertNotIn("plainsecretvalue", p.stdout)

    def test_home_prefix_is_shortened_in_printed_paths(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json('python3 "%s/missing.py"' % self.fx.home))
        self.fx.save_settings()
        p = self.run_doctor("--section", "interpreters")
        self.assertNotIn(self.fx.home, p.stdout)
        self.assertIn("~/missing.py", p.stdout)


class CliTests(Base):
    def test_json_has_the_six_sections_with_statuses(self):
        self.fx.save_settings()
        doc = self.run_json("--no-exec")
        self.assertEqual(
            sorted(doc["sections"]), sorted(["interpreters", "failures", "injection", "weight", "flag", "python"])
        )
        for sec in doc["sections"].values():
            self.assertIn(sec["status"], ("ok", "problem", "could not check"))
        self.assertEqual(set(doc["summary"]), {"problems", "could_not_check"})

    def test_text_report_starts_with_the_summary_line(self):
        self.fx.save_settings()
        p = self.run_doctor("--no-exec")
        self.assertRegex(p.stdout, r"Summary: \d+ problems, \d+ could not check")

    def test_section_flag_filters(self):
        self.fx.save_settings()
        doc = self.run_json("--section", "flag,python", "--no-exec")
        self.assertEqual(sorted(doc["sections"]), ["flag", "python"])

    def test_exit_code_is_zero_with_problems_and_one_with_strict(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python x.py"))
        self.fx.save_settings()
        self.assertEqual(self.run_doctor("--section", "interpreters").returncode, 0)
        self.assertEqual(self.run_doctor("--section", "interpreters", "--strict").returncode, 1)
        self.fx.enabled.clear()
        self.fx.installed.clear()
        self.fx.save_settings()
        self.assertEqual(self.run_doctor("--section", "interpreters", "--strict").returncode, 0)

    def test_free_text_and_unknown_flags_are_ignored_with_a_note(self):
        self.fx.save_settings()
        p = self.run_doctor("why", "is", "startup", "slow", "--bogus-flag", "--no-exec")
        self.assertEqual(p.returncode, 0)
        self.assertIn("ignored arguments: why is startup slow --bogus-flag", p.stdout)

    def test_bad_day_counts_fall_back_with_a_note(self):
        self.fx.save_settings()
        for value in ("0", "-3", "abc", "9999"):
            with self.subTest(days=value):
                p = self.run_doctor("--json", "--no-exec", "--days=%s" % value)
                self.assertEqual(p.returncode, 0)
                doc = json.loads(p.stdout)
                self.assertTrue(any("--days" in n for n in doc["notes"]), doc["notes"])

    def test_an_argument_error_still_prints_a_report_and_exits_zero(self):
        self.fx.save_settings()
        p = self.run_doctor("--no-exec", "--section")  # option missing its value
        self.assertEqual(p.returncode, 0)
        self.assertIn("could not read arguments", p.stdout)

    def test_unknown_section_name_is_ignored_with_a_note(self):
        self.fx.save_settings()
        doc = self.run_json("--section", "bogus", "--no-exec")
        self.assertEqual(len(doc["sections"]), 6)
        self.assertTrue(any("unknown section" in n for n in doc["notes"]))

    def test_a_section_that_raises_does_not_hide_the_others(self):
        mod = load_module()
        self.fx.save_settings()

        def boom(ctx, cfg):
            raise RuntimeError("boom")

        mod.run_weight = boom
        out = io.StringIO()
        rc = mod.main(
            ["--home", self.fx.home, "--project", self.fx.project, "--no-exec"],
            environ={"PATH": "/usr/bin:/bin", "HOME": self.fx.home},
            out=out,
        )
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("internal error (RuntimeError)", text)
        self.assertIn("function hooks flag", text)
        self.assertIn("interpreters", text)

    def test_a_missing_home_makes_the_config_sections_could_not_check(self):
        p = self.run_doctor("--json", "--no-exec", home=False)
        # no --home: HOME points at the fixture home, which has no .claude yet
        doc = json.loads(self.run_doctor("--json", "--no-exec", "--home", os.path.join(self.fx.root, "nowhere"), home=False).stdout)
        for sid in ("interpreters", "failures", "injection", "weight", "flag"):
            self.assertEqual(doc["sections"][sid]["status"], "could not check", sid)

    def test_text_output_is_capped_on_a_fifty_plugin_fixture_and_all_lifts_the_cap(self):
        for n in range(50):
            self.fx.plugin(
                "plug%02d" % n,
                hooks=self.fx.hooks_json("python x.py"),
                files={"skills/s/SKILL.md": '---\nname: s\ndescription: "%s"\n---\n' % ("d" * 100)},
            )
        self.fx.save_settings()
        capped = self.run_doctor("--no-exec").stdout
        full = self.run_doctor("--no-exec", "--all").stdout
        self.assertLess(len(capped), 20000)
        self.assertGreater(len(full), len(capped))
        self.assertIn("more findings (use --all)", capped)

    def test_the_environment_flag_in_the_test_process_cannot_change_a_result(self):
        self.fx.save_settings()
        self.fx.global_config({"cachedGrowthBookFeatures": {"tengu_plugin_hooks_modules": False}})
        saved = os.environ.get("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS")
        os.environ["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] = "1"
        try:
            doc = self.run_json("--section", "flag")
        finally:
            if saved is None:
                del os.environ["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"]
            else:
                os.environ["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] = saved
        self.assertIs(doc["sections"]["flag"]["data"]["verdict"], False)


class NonRegularFileTests(Base):
    """A FIFO or a device in a place the doctor reads must never hang it or grow its memory.

    Every case runs the real script under a 20 s subprocess timeout and then checks the 10 s promise.
    """

    def run_bounded(self, *args):
        t0 = time.monotonic()
        p = self.run_doctor("--json", *args, timeout=20)
        elapsed = time.monotonic() - t0
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertLess(elapsed, 10, "the doctor took %.1f s" % elapsed)
        return json.loads(p.stdout)

    def fifo(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.mkfifo(path)
        return path

    def could_not_read(self, doc, sid="interpreters"):
        return [i for i in doc["sections"][sid]["items"] if i["id"] == "could-not-read"]

    def test_a_fifo_at_the_user_settings_file_is_unreadable_not_a_hang(self):
        self.fifo(os.path.join(self.fx.claude, "settings.json"))
        doc = self.run_bounded()
        self.assertTrue(self.could_not_read(doc), doc["sections"]["interpreters"])
        self.assertNotEqual(doc["sections"]["interpreters"]["status"], "ok")

    def test_fifos_at_project_and_local_settings_files(self):
        self.fx.save_settings()
        self.fifo(os.path.join(self.fx.project, ".claude", "settings.json"))
        self.fifo(os.path.join(self.fx.project, ".claude", "settings.local.json"))
        doc = self.run_bounded()
        self.assertEqual(len(self.could_not_read(doc)), 2, doc["sections"]["interpreters"])

    def test_a_device_symlinked_as_settings_is_refused_without_reading_it(self):
        self.fx.save_settings()
        path = os.path.join(self.fx.claude, "settings.json")
        os.remove(path)
        os.symlink("/dev/zero", path)
        doc = self.run_bounded()
        self.assertTrue(self.could_not_read(doc))

    def test_a_fifo_at_the_global_config_is_could_not_check_for_the_flag(self):
        self.fx.save_settings()
        self.fifo(os.path.join(self.fx.home, ".claude.json"))
        doc = self.run_bounded("--section", "flag")
        self.assertEqual(doc["sections"]["flag"]["status"], "could not check")
        self.assertTrue(self.items(doc, "flag", "could", "flag-cache-unreadable"))

    def test_a_fifo_at_the_installed_plugins_file(self):
        self.fx.save_settings()
        path = os.path.join(self.fx.claude, "plugins", "installed_plugins.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.fifo(path)
        doc = self.run_bounded()
        self.assertEqual(doc["sections"]["interpreters"]["status"], "could not check")

    def test_a_fifo_at_a_plugins_hooks_file(self):
        root = self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python3 x.py"))
        hooks = os.path.join(root, "hooks", "hooks.json")
        os.remove(hooks)
        self.fifo(hooks)
        self.fx.save_settings()
        doc = self.run_bounded()
        self.assertTrue(self.could_not_read(doc), doc["sections"]["interpreters"])

    def test_a_fifo_at_a_plugins_manifest(self):
        root = self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python3 x.py"))
        manifest = os.path.join(root, ".claude-plugin", "plugin.json")
        os.remove(manifest)
        self.fifo(manifest)
        self.fx.save_settings()
        doc = self.run_bounded()
        self.assertTrue(self.could_not_read(doc), doc["sections"]["interpreters"])

    def test_a_fifo_where_an_agent_or_command_file_should_be(self):
        root = self.fx.plugin(
            "example-plugin",
            files={"agents/real.md": "---\nname: real\ndescription: real agent\n---\nx\n"},
        )
        self.fifo(os.path.join(root, "agents", "a.md"))
        self.fifo(os.path.join(root, "commands", "c.md"))
        self.fx.save_settings()
        doc = self.run_bounded("--section", "weight")
        notes = " ".join(doc["sections"]["weight"]["lines"])
        self.assertIn("a (not counted", notes)
        self.assertIn("example-plugin:c (not counted", notes)
        row = [r for r in doc["sections"]["weight"]["data"]["rows"] if r["label"] == "example-plugin"][0]
        self.assertEqual(row["agents"], 1)  # the real agent is still counted

    def test_a_fifo_as_a_skill_file_is_skipped_not_waited_on(self):
        root = self.fx.plugin("example-plugin")
        self.fifo(os.path.join(root, "skills", "odd", "SKILL.md"))
        self.fx.save_settings()
        doc = self.run_bounded("--section", "weight")
        row = [r for r in doc["sections"]["weight"]["data"]["rows"] if r["label"] == "example-plugin"][0]
        self.assertEqual(row["skills"], 0)
        notes = " ".join(doc["sections"]["weight"]["lines"])
        self.assertIn("example-plugin:odd (not counted", notes)  # same note agents and commands get

    def test_a_fifo_as_a_hook_script_is_a_problem_not_a_hang(self):
        root = self.fx.plugin("example-plugin", hooks=self.fx.hooks_json('"${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"'))
        script = os.path.join(root, "hooks", "run.sh")
        self.fifo(script)
        os.chmod(script, 0o755)
        self.fx.save_settings()
        doc = self.run_bounded("--section", "interpreters")
        found = self.items(doc, "interpreters", "problem", "interp-missing-script")
        self.assertEqual(len(found), 1, doc["sections"]["interpreters"])
        self.assertIn("not a regular file", found[0]["text"])

    def test_a_fifo_as_a_script_argument_is_a_problem_not_a_hang(self):
        root = self.fx.plugin("example-plugin", hooks=self.fx.hooks_json('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"'))
        script = os.path.join(root, "hooks", "x.py")
        self.fifo(script)
        self.fx.save_settings()
        doc = self.run_bounded("--section", "interpreters")
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-missing-script"))

    def test_a_fifo_at_the_user_agents_and_commands_folders(self):
        self.fx.save_settings()
        self.fifo(os.path.join(self.fx.claude, "agents", "a.md"))
        self.fifo(os.path.join(self.fx.claude, "commands", "c.md"))
        self.fifo(os.path.join(self.fx.claude, "skills", "odd", "SKILL.md"))
        doc = self.run_bounded("--section", "weight")
        self.assertEqual(doc["sections"]["weight"]["status"], "ok")

    def test_open_regular_refuses_a_fifo_without_blocking(self):
        import threading

        mod = load_module()
        path = self.fifo(os.path.join(self.fx.root, "pipe"))
        out = []

        def attempt():
            try:
                mod.open_regular(path)
                out.append("opened")
            except OSError:
                out.append("refused")

        t = threading.Thread(target=attempt, daemon=True)
        t.start()
        t.join(5)
        self.assertEqual(out, ["refused"])
        self.assertIsNone(mod.read_bounded(path, 10))

    def test_open_regular_refuses_a_device_and_a_folder(self):
        mod = load_module()
        for path in ("/dev/zero", self.fx.root):
            with self.assertRaises(OSError):
                mod.open_regular(path)
            self.assertIsNone(mod.read_bounded(path, 10))

    def test_read_bounded_never_returns_more_than_the_limit(self):
        mod = load_module()
        path = os.path.join(self.fx.root, "big.bin")
        with open(path, "wb") as fh:
            fh.write(b"a" * 5000)
        self.assertEqual(len(mod.read_bounded(path, 100)), 100)

    def test_read_json_over_the_size_cap_is_unreadable(self):
        mod = load_module()
        path = os.path.join(self.fx.root, "big.json")
        with open(path, "w") as fh:
            fh.write(json.dumps({"k": "v" * 200}))
        mod.MAX_JSON_BYTES = 100
        self.assertEqual(mod.read_json(path), (None, "unreadable"))
        mod.MAX_JSON_BYTES = 10 ** 6
        data, err = mod.read_json(path)
        self.assertIsNone(err)
        self.assertEqual(len(data["k"]), 200)

    def test_read_json_on_a_fifo_and_a_folder_is_unreadable(self):
        mod = load_module()
        path = self.fifo(os.path.join(self.fx.root, "pipe.json"))
        self.assertEqual(mod.read_json(path), (None, "unreadable"))
        self.assertEqual(mod.read_json(self.fx.root), (None, "unreadable"))
        self.assertEqual(mod.read_json(os.path.join(self.fx.root, "nope.json")), (None, "missing"))



class DeepJsonTests(Base):
    """Absurdly nested JSON raises RecursionError in the parser. It must read as invalid, never as a
    crash that takes the other sections down."""

    DEPTH = 200000

    def deep(self):
        return "[" * self.DEPTH

    def test_deeply_nested_user_settings_does_not_sink_the_python_section(self):
        self.fx.write_json(os.path.join(self.fx.claude, "settings.json"), self.deep())
        doc = self.run_json()
        self.assertEqual(self.items(doc, "python", fid="internal-error"), [])
        self.assertNotIn("internal error", doc["sections"]["python"]["summary"])
        self.assertEqual(self.items(doc, "interpreters", fid="internal-error"), [])
        self.assertTrue(self.items(doc, "interpreters", fid="could-not-read"), doc["sections"]["interpreters"])
        for sid in doc["sections"]:
            self.assertNotEqual(doc["sections"][sid]["summary"], "internal error", sid)

    def test_a_recursion_error_while_loading_config_still_runs_the_python_section(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("doctor_under_test", DOCTOR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def boom(ctx):
            raise RecursionError("simulated")

        mod.load_config = boom
        ctx = mod.build_ctx(*mod.parse_args(["--home", self.fx.home, "--project", self.fx.project]), dict(os.environ), [])
        results, _cfg = mod.run_all(ctx)
        self.assertEqual(results["python"].summary != "internal error", True)
        self.assertEqual([i for i in results["python"].items if i["id"] == "internal-error"], [])
        for sid in ("flag", "interpreters", "weight"):
            self.assertEqual(results[sid].status, "could_not_check", sid)

    def test_one_failing_section_leaves_the_others_running(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("doctor_under_test2", DOCTOR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def boom(ctx, cfg):
            raise RecursionError("simulated")

        mod.run_weight = boom
        ctx = mod.build_ctx(*mod.parse_args(["--home", self.fx.home, "--project", self.fx.project]), dict(os.environ), [])
        results, _cfg = mod.run_all(ctx)
        self.assertEqual(results["weight"].status, "could_not_check")
        self.assertIn("internal error", results["weight"].summary)
        self.assertEqual([i for i in results["python"].items if i["id"] == "internal-error"], [])
        self.assertNotEqual(results["interpreters"].summary, "internal error")

    def test_a_deeply_nested_transcript_line_is_skipped_and_real_failures_still_show(self):
        self.fx.save_settings()
        self.fx.transcript(
            [F.error_line("s1", "u1", "cmd one")],
            session="real",
        )
        self.fx.transcript([], session="deep", raw_lines=['{"x": "hook_", "y": ' + self.deep()])
        doc = self.run_json("--section", "failures")
        self.assertEqual(self.items(doc, "failures", fid="internal-error"), [])
        self.assertTrue(self.items(doc, "failures", fid="hook-failing"), doc["sections"]["failures"])

    def test_deeply_nested_global_config_takes_down_only_the_flag_section(self):
        self.fx.save_settings()
        self.fx.write_json(os.path.join(self.fx.home, ".claude.json"), self.deep())
        doc = self.run_json()
        self.assertEqual(self.status(doc, "flag"), "could not check")
        self.assertEqual(self.items(doc, "flag", fid="internal-error"), [])
        self.assertNotEqual(doc["sections"]["python"]["summary"], "internal error")

    def test_read_json_returns_invalid_for_deep_nesting(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("doctor_under_test3", DOCTOR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        path = os.path.join(self.fx.root, "deep.json")
        self.fx.write_json(path, self.deep())
        self.assertEqual(mod.read_json(path), (None, "invalid"))


class HonestStatusTests(Base):
    """A header must not read ok when the section could not see everything."""

    def test_interpreters_header_follows_the_could_not_check_count(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"; python3 "$UNKNOWN_VAR/y.py"'), files={"hooks/x.py": "print(1)\n"})
        self.fx.save_settings()
        doc = self.run_json("--section", "interpreters")
        self.assertTrue(self.items(doc, "interpreters", "could", "could-not-check-commands"))
        self.assertEqual(self.status(doc, "interpreters"), "could not check")

    def test_a_clean_partial_scan_is_could_not_check_not_ok(self):
        self.fx.save_settings()
        big = "x" * 100000
        for n in range(3):
            lines = [{"type": "user", "uuid": "p%d-%d" % (n, i), "message": big} for i in range(15)]
            lines.append(F.hook_line("hook_success", "s%d" % n, "ok%d" % n, command="python3 fine.py", stdout="", stderr="", exitCode=0))
            self.fx.transcript(lines, session="s%d" % n)
        for sid in ("failures", "injection"):
            doc = self.run_json("--section", sid, "--max-mb", "2")
            self.assertEqual(self.status(doc, sid), "could not check", sid)
            self.assertTrue(self.items(doc, sid, "could", "scan-partial"), sid)

    def test_a_partial_scan_still_reports_the_problems_it_found(self):
        self.fx.save_settings(hooks={"SessionStart": [{"hooks": [{"type": "command", "command": "cmd budget"}]}]})
        big = "x" * 100000
        for n in range(3):
            lines = [{"type": "user", "uuid": "p%d-%d" % (n, i), "message": big} for i in range(15)]
            lines.append(F.error_line("s%d" % n, "e%d" % n, "cmd budget"))
            self.fx.transcript(lines, session="s%d" % n)
        doc = self.run_json("--section", "failures", "--max-mb", "2")
        self.assertEqual(self.status(doc, "failures"), "problem")

    def test_unrecognised_flag_value_does_not_claim_nothing_was_read(self):
        self.fx.save_settings()
        self.fx.global_config({"cachedGrowthBookFeatures": {"tengu_plugin_hooks_modules": True}})
        p = self.run_doctor("--section", "flag", env_extra={"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "maybe"})
        self.assertEqual(p.returncode, 0)
        self.assertNotIn("no source could be read", p.stdout)
        self.assertIn("not recognised", p.stdout)

    def test_the_description_cap_setting_changes_the_cut_marks(self):
        long_skill = "---\nname: wide\ndescription: %s\n---\nbody\n" % ("y" * 300)
        self.fx.plugin("example-plugin", files={"skills/wide/SKILL.md": long_skill})
        self.fx.save_settings()
        doc = self.run_json("--section", "weight")
        row = [r for r in doc["sections"]["weight"]["data"]["rows"] if r["label"] == "example-plugin"][0]
        self.assertEqual(row["chars"], 300)
        self.fx.save_settings(skillListingMaxDescChars=100)
        doc = self.run_json("--section", "weight")
        row = [r for r in doc["sections"]["weight"]["data"]["rows"] if r["label"] == "example-plugin"][0]
        self.assertEqual(row["chars"], 100)
        self.assertIn("longer than 100 characters", " ".join(doc["sections"]["weight"]["lines"]))


class PositiveControlTests(Base):
    def test_a_known_bad_hook_and_a_known_failure_are_both_found(self):
        """Rule 9: if the parser regresses, 'all ok' must not be the outcome."""
        self.fx.plugin(
            "example-plugin",
            hooks=self.fx.hooks_json('python "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"', status="Control hook"),
            files={"hooks/x.py": "print(1)\n"},
        )
        self.fx.save_settings()
        self.fx.transcript([F.error_line("s1", "u1", "Control hook")])
        doc = self.run_json("--no-exec")
        self.assertTrue(self.items(doc, "interpreters", "problem", "interp-bare-python"))
        self.assertTrue(self.items(doc, "failures", "problem", "hook-failing"))
        self.assertGreaterEqual(doc["summary"]["problems"], 2)


class RunnerTests(Base):
    @unittest.skipUnless(os.path.exists(SYSTEM_PYTHON), "needs the system python3")
    def test_runs_under_a_bare_environment_on_the_system_python_and_finishes_quickly(self):
        self.fx.plugin("example-plugin", hooks=self.fx.hooks_json("python x.py", status="Some hook"))
        self.fx.save_settings()
        lines = [{"type": "user", "uuid": "p%d" % i, "message": "y" * 3000} for i in range(10000)]
        lines.append(F.error_line("s1", "u1", "Some hook"))
        self.fx.transcript(lines)
        start = time.time()
        p = subprocess.run(
            ["env", "-i", "PATH=/usr/bin:/bin", "HOME=%s" % self.fx.home, SYSTEM_PYTHON, DOCTOR, "--home", self.fx.home, "--project", self.fx.project, "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(time.time() - start, 10)
        doc = json.loads(p.stdout)
        self.assertEqual(doc["sections"]["failures"]["data"]["failure_groups"][0]["count"], 1)

    def test_a_sleeping_probe_and_a_large_transcript_stay_inside_the_budget(self):
        self.fx.fake_bin("python3", "#!/bin/sh\n/bin/sleep 10\n")
        self.fx.save_settings()
        lines = [{"type": "user", "uuid": "p%d" % i, "message": "y" * 3000} for i in range(10000)]
        self.fx.transcript(lines)
        start = time.time()
        p = self.run_doctor("--minimal-path", self.fx.bin, "--time-budget", "1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(time.time() - start, 2.5)


if __name__ == "__main__":
    unittest.main()
