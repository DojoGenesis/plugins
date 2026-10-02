"""Tests for release-check.sh, run against a synthetic repo with stub tools.

The stubs return scripted exit codes, so these tests prove how the driver reads and
reports results, not whether the real tools are right. Every run starts from a cleared
environment with a temp HOME, and puts a fake `git` first on PATH that fails the test
if anything calls it.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import unittest

try:
    from . import _helpers as H
except ImportError:
    import _helpers as H

PY_STUB = '''import os, sys
with open(os.environ["STUB_LOG"], "a") as f:
    f.write("%(tag)s argv: %%s\\n" %% " ".join(sys.argv[1:]))
if os.environ.get("%(var)s_QUIET") != "1":
    print(%(line)r)
sys.exit(int(os.environ.get("%(var)s", "0")))
'''

CLAUDE_STUB = '''#!/bin/sh
printf 'argv:%s\\n' "$*" >> "$STUB_LOG"
if [ "$1" = "--version" ]; then
  echo "${STUB_VERSION:-2.1.286} (Claude Code)"
  exit 0
fi
spam() { i=0; while [ $i -lt 10000 ]; do echo "noise line $i"; i=$((i+1)); done; }
if [ "$1" = "plugin" ] && [ "$2" = "validate" ]; then
  case "${STUB_VALIDATE_MODE:-ok}" in
    ok) echo '{"success":true,"strict":true,"manifest":{"errors":[],"warnings":[]}}'; exit 0 ;;
    warn) echo '{"success":false,"strict":true,"manifest":{"errors":[],"warnings":["a","b"]}}'; exit 1 ;;
    text) echo 'Validation passed'; exit 0 ;;
    textfail) echo 'Validation failed'; exit 1 ;;
    empty) exit 0 ;;
    nosuccess) echo '{"manifest":{"errors":[],"warnings":[]}}'; exit 0 ;;
    array) echo '[]'; exit 0 ;;
    errs) echo '{"success":true,"strict":true,"manifest":{"errors":["e"],"warnings":[]}}'; exit 0 ;;
    spam3) spam; exit 3 ;;
  esac
fi
if [ "$1" = "plugin" ] && [ "$2" = "test" ]; then
  printf 'fh:%s\\n' "${CLAUDE_CODE_ENABLE_FUNCTION_HOOKS:-unset}" >> "$STUB_LOG"
  if [ "${CLAUDE_CODE_ENABLE_FUNCTION_HOOKS:-}" != "1" ]; then
    echo "hooks modules are turned off in this process"; exit 1
  fi
  case "${STUB_MOD_MODE:-ok}" in
    ok) printf ' 3 pass\\n 0 fail\\nRan 3 tests across 1 file.\\n'; exit 0 ;;
    vacuous) printf ' 0 pass\\n 0 fail\\nRan 0 tests across 0 files.\\n'; exit 0 ;;
    noran) printf 'all good\\n'; exit 0 ;;
    fail) printf ' 2 pass\\n 1 fail\\nRan 3 tests across 1 file.\\n'; exit 1 ;;
    off) echo "hooks modules are turned off in this process"; exit 1 ;;
    spam3) spam; exit 3 ;;
  esac
fi
exit 0
'''

BASH_OK = H.BASH is not None and os.path.exists(H.RELEASE)


def parse_table(out):
    rows = {}
    started = False
    for line in out.splitlines():
        if line.startswith("STEP"):
            started = True
            continue
        if line.startswith("OVERALL"):
            break
        if started and line.strip():
            parts = re.split(r"\s{2,}", line.strip(), maxsplit=2)
            rows[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")
    return rows


@unittest.skipUnless(BASH_OK, "bash not available")
class RC(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="rc-test-")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.repo = os.path.join(self.work, "repo")
        self.home = os.path.join(self.work, "home")
        self.bindir = os.path.join(self.work, "bin with space")
        self.fakebin = os.path.join(self.work, "fakebin")
        self.log = os.path.join(self.work, "stub.log")
        self.git_marker = os.path.join(self.work, "git-was-called")
        for d in (self.home, self.bindir, self.fakebin):
            os.makedirs(d)
        scripts = os.path.join(self.repo, "scripts")
        os.makedirs(scripts)
        shutil.copy(H.RELEASE, scripts)
        self.script = os.path.join(scripts, "release-check.sh")
        for name, tag, var, line in (
            ("suite_lint.py", "lint", "STUB_LINT_RC", "suite-lint: 1 plugin(s), 3 file(s), 0 error(s), 0 warning(s)"),
            ("suite_denylist.py", "denylist", "STUB_DENY_RC", "suite_denylist: 0 hit(s); control ok (2 lists)"),
            ("face-parity.py", "face-parity", "STUB_FP_RC", "face-parity stub ran"),
            ("plugin-lint.py", "plugin-lint", "STUB_PL_RC", "plugin-lint stub ran"),
        ):
            H.write(os.path.join(scripts, name), PY_STUB % {"tag": tag, "var": var, "line": line})
        H.write(os.path.join(scripts, "tests_suite", "__init__.py"), "")
        H.write(os.path.join(scripts, "tests_suite", "test_ok.py"), H.TEST_PY)
        for name in ("README.md", "llms.txt"):
            H.write(os.path.join(self.repo, name), "x\n")
        H.write(os.path.join(self.repo, ".claude-plugin", "marketplace.json"), "{}\n")
        self.add_plugin("dojo-alpha")
        self.claude = os.path.join(self.bindir, "claude")
        self.make_exe(self.claude, CLAUDE_STUB)
        self.make_exe(os.path.join(self.fakebin, "git"), "#!/bin/sh\ntouch '%s'\nexit 99\n" % self.git_marker)

    def make_exe(self, path, text):
        H.write(path, text)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def add_plugin(self, name, tests=H.TEST_PY, register=False):
        root = os.path.join(self.repo, "plugins", name)
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(root, exist_ok=True)
        if tests is not None:
            H.write(os.path.join(root, "tests", "test_x.py"), tests)
        if register:
            H.write(os.path.join(root, "hooks", "register.ts"), "export default function () {}\n")
        return root

    def env(self, **extra):
        e = {"PATH": self.fakebin + ":/usr/bin:/bin", "HOME": self.home, "STUB_LOG": self.log, "CLAUDE_BIN": self.claude}
        for k, v in extra.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return e

    def run_rc(self, *args, cwd=None, bash=None, **extra):
        rc, out, err = H.run_script([bash or H.BASH, self.script] + list(args), self.env(**extra), cwd or self.work)
        return rc, out, err, parse_table(out)

    def logtext(self):
        if not os.path.exists(self.log):
            return ""
        with open(self.log) as fh:
            return fh.read()

    def assertRow(self, rows, name, status, detail=None):
        self.assertIn(name, rows, rows)
        self.assertEqual(rows[name][0], status, rows[name])
        if detail is not None:
            self.assertIn(detail, rows[name][1])

    # ------------------------------------------------------------------ green

    def test_all_green(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("OVERALL: PASS (0 fail, 0 error, 0 warn-ok, 0 warn)", out)
        for step in ("lint", "denylist", "unittest:dojo-alpha", "validate:dojo-alpha", "mod:dojo-alpha", "self-test", "face-parity", "plugin-lint"):
            self.assertIn(step, rows)
        self.assertRow(rows, "unittest:dojo-alpha", "PASS", "1 tests, 0 skipped")
        self.assertRow(rows, "validate:dojo-alpha", "PASS", "0 errors, 0 warnings")
        self.assertRow(rows, "mod:dojo-alpha", "SKIP", "no hooks/register.ts")
        self.assertEqual(os.listdir(self.work).count("git-was-called"), 0)
        self.assertFalse(os.path.exists(self.git_marker))

    def test_runs_under_bash_32_and_a_cleared_environment(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", bash="/bin/bash")
        self.assertEqual(rc, 0, out + err)

    def test_runs_from_any_directory(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", cwd=self.home)
        self.assertEqual(rc, 0, out + err)

    def test_help(self):
        rc, out, err, _ = self.run_rc("-h")
        self.assertEqual(rc, 0)
        self.assertIn("Row status", out)

    # ------------------------------------------------------- each step failing

    def test_each_step_failing_in_turn(self):
        cases = [
            ({"STUB_LINT_RC": "1"}, "lint", "FAIL"),
            ({"STUB_LINT_RC": "2"}, "lint", "ERROR"),
            ({"STUB_DENY_RC": "1"}, "denylist", "FAIL"),
            ({"STUB_DENY_RC": "2"}, "denylist", "ERROR"),
            ({"STUB_VALIDATE_MODE": "warn"}, "validate:dojo-alpha", "FAIL"),
            ({"STUB_FP_RC": "1"}, "face-parity", "FAIL"),
            ({"STUB_PL_RC": "2"}, "plugin-lint", "FAIL"),
        ]
        for extra, row, status in cases:
            with self.subTest(extra=extra):
                rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", **extra)
                self.assertNotEqual(rc, 0, out)
                self.assertRow(rows, row, status)
                self.assertIn("OVERALL: FAIL", out)

    def test_failing_plugin_unittest(self):
        self.add_plugin("dojo-alpha", tests="import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.fail('no')\n")
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertNotEqual(rc, 0)
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL")

    def test_failing_mod_test(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_MOD_MODE="fail")
        self.assertNotEqual(rc, 0)
        self.assertRow(rows, "mod:dojo-alpha", "FAIL")

    def test_self_test_row_fails_when_the_tests_are_missing(self):
        shutil.rmtree(os.path.join(self.repo, "scripts", "tests_suite"))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertNotEqual(rc, 0)
        self.assertRow(rows, "self-test", "FAIL")

    # --------------------------------------------------- plugin-lint baseline

    def test_plugin_lint_warnings_are_warn_ok_and_overall_passes(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_PL_RC="1")
        self.assertEqual(rc, 0, out)
        self.assertRow(rows, "plugin-lint", "WARN-OK")
        self.assertIn("OVERALL: PASS (0 fail, 0 error, 1 warn-ok, 0 warn)", out)

    # ---------------------------------------------------------- no pipe masking

    def test_a_noisy_failing_step_is_still_a_failure(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE="spam3")
        self.assertNotEqual(rc, 0)
        self.assertRow(rows, "validate:dojo-alpha", "FAIL", "exit 3")

    def test_a_noisy_failing_mod_test_is_still_a_failure(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_MOD_MODE="spam3")
        self.assertRow(rows, "mod:dojo-alpha", "FAIL", "exit 3")

    # ------------------------------------------------------ vacuous-pass guards

    def test_unittest_with_zero_tests_fails(self):
        self.add_plugin("dojo-alpha", tests="# no tests here\n")
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL", "0 tests")

    def test_missing_tests_directory_fails(self):
        self.add_plugin("dojo-alpha", tests=None)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL", "no tests/")

    def test_mod_vacuous_outputs_fail(self):
        self.add_plugin("dojo-alpha", register=True)
        for mode in ("vacuous", "noran"):
            with self.subTest(mode=mode):
                rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_MOD_MODE=mode)
                self.assertRow(rows, "mod:dojo-alpha", "FAIL")
                self.assertNotEqual(rc, 0)

    def test_function_hooks_off_text_is_an_error_not_a_failure(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_MOD_MODE="off")
        self.assertRow(rows, "mod:dojo-alpha", "ERROR", "function hooks are off")

    def test_validate_warnings_only_json_fails_with_the_count(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE="warn")
        self.assertRow(rows, "validate:dojo-alpha", "FAIL", "2 warnings")

    # ------------------------------------------- unreadable results are not passes

    def test_validate_output_that_is_not_json_is_never_a_pass(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE="text")
        self.assertRow(rows, "validate:dojo-alpha", "ERROR", "not JSON")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("OVERALL: FAIL", out)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE="textfail")
        self.assertRow(rows, "validate:dojo-alpha", "FAIL", "exit 1")
        self.assertNotEqual(rc, 0)

    def test_validate_with_no_output_or_the_wrong_json_shape_is_an_error(self):
        for mode in ("empty", "nosuccess", "array"):
            with self.subTest(mode=mode):
                rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE=mode)
                self.assertRow(rows, "validate:dojo-alpha", "ERROR")
                self.assertNotEqual(rc, 0)

    def test_validate_success_with_errors_listed_is_a_failure(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VALIDATE_MODE="errs")
        self.assertRow(rows, "validate:dojo-alpha", "FAIL", "1 errors")
        self.assertNotEqual(rc, 0)

    def test_validate_cannot_be_read_without_the_python_interpreter(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", "--only", "validate", DOJO_PY39=os.path.join(self.work, "no-python"))
        self.assertRow(rows, "validate:dojo-alpha", "ERROR", "python 3.9 not found")
        self.assertNotEqual(rc, 0)

    def test_a_silent_lint_or_denylist_run_is_an_error(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_LINT_RC_QUIET="1")
        self.assertRow(rows, "lint", "ERROR", "suite-lint:")
        self.assertNotEqual(rc, 0)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_DENY_RC_QUIET="1")
        self.assertRow(rows, "denylist", "ERROR", "control ok")
        self.assertNotEqual(rc, 0)

    # ------------------------------------------------------------------ skipped tests

    SKIPPY = (
        "import unittest\n\n\nclass T(unittest.TestCase):\n"
        "%s"
    )

    def skippy(self, total, skipped):
        body = ""
        for i in range(total):
            if i < skipped:
                body += "    @unittest.skip('not here')\n"
            body += "    def test_%d(self):\n        self.assertTrue(True)\n" % i
        return self.SKIPPY % body

    def test_a_few_skips_are_a_warn_that_shows_the_count(self):
        self.add_plugin("dojo-alpha", tests=self.skippy(8, 1))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "WARN", "8 tests, 1 skipped")
        self.assertEqual(rc, 0, out)
        self.assertIn("OVERALL: PASS (0 fail, 0 error, 0 warn-ok, 1 warn)", out)

    def test_exactly_a_quarter_skipped_is_still_a_warn_and_more_is_a_fail(self):
        self.add_plugin("dojo-alpha", tests=self.skippy(4, 1))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "WARN", "4 tests, 1 skipped")
        self.add_plugin("dojo-alpha", tests=self.skippy(4, 2))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL", "over 25% skipped")
        self.assertNotEqual(rc, 0)
        self.add_plugin("dojo-alpha", tests=self.skippy(4, 4))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL", "4 tests, 4 skipped")

    def test_skips_in_the_self_test_are_classified_the_same_way(self):
        H.write(os.path.join(self.repo, "scripts", "tests_suite", "test_ok.py"), self.skippy(4, 3))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "self-test", "FAIL", "over 25% skipped")
        H.write(os.path.join(self.repo, "scripts", "tests_suite", "test_ok.py"), self.skippy(10, 1))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "self-test", "WARN", "10 tests, 1 skipped")

    # ------------------------------------------------------------- environment

    def test_missing_claude_binary_gives_error_rows(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", CLAUDE_BIN=None)
        self.assertNotEqual(rc, 0)
        self.assertRow(rows, "validate:dojo-alpha", "ERROR", "claude binary not found")
        self.assertRow(rows, "mod:dojo-alpha", "ERROR", "claude binary not found")
        self.assertNotIn("Traceback", err)

    def test_non_executable_claude_binary(self):
        bad = os.path.join(self.work, "not-executable")
        H.write(bad, "x")
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", CLAUDE_BIN=bad)
        self.assertRow(rows, "validate:dojo-alpha", "ERROR")

    def test_old_claude_version_is_an_error_for_validate_and_mod(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VERSION="2.1.285")
        self.assertRow(rows, "validate:dojo-alpha", "ERROR", "older than 2.1.286")
        self.assertRow(rows, "mod:dojo-alpha", "ERROR", "older than 2.1.286")

    def test_newer_claude_version_is_accepted(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", STUB_VERSION="2.2.0")
        self.assertRow(rows, "validate:dojo-alpha", "PASS")

    def test_claude_found_on_path_when_the_variable_is_unset(self):
        shutil.copy(self.claude, os.path.join(self.fakebin, "claude"))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", CLAUDE_BIN=None)
        self.assertRow(rows, "validate:dojo-alpha", "PASS")

    def test_mod_test_runs_with_function_hooks_on_and_eval_is_never_called(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertEqual(rc, 0, out)
        self.assertRow(rows, "mod:dojo-alpha", "PASS", "3 tests")
        log = self.logtext()
        self.assertIn("fh:1", log)
        self.assertIn("argv:plugin test", log)
        self.assertIn("argv:plugin validate --strict", log)
        argv_lines = [l for l in log.splitlines() if l.startswith("argv:")]
        self.assertTrue(argv_lines)
        for l in argv_lines:
            self.assertNotIn("eval", l)
        self.assertFalse(os.path.exists(self.git_marker))

    def test_no_mods_flag(self):
        self.add_plugin("dojo-alpha", register=True)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", "--no-mods")
        self.assertRow(rows, "mod:dojo-alpha", "SKIP", "--no-mods")
        self.assertNotIn("fh:1", self.logtext())

    def test_the_denylist_step_never_gets_allow_missing(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        log = self.logtext()
        self.assertIn("denylist argv:", log)
        self.assertNotIn("allow-missing", log)

    def test_denylist_covers_the_public_files(self):
        H.write(os.path.join(self.repo, "CHANGELOG.md"), "x\n")
        H.write(os.path.join(self.repo, "STATUS.md"), "x\n")
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        line = [l for l in self.logtext().splitlines() if l.startswith("denylist argv:")][0]
        for part in ("plugins/dojo-alpha", "README.md", "llms.txt", ".claude-plugin/marketplace.json", "CHANGELOG.md", "STATUS.md", "scripts/tests_suite", "scripts/release-check.sh"):
            self.assertIn(part, line)

    def test_missing_contract_path_is_an_error(self):
        os.remove(os.path.join(self.repo, "llms.txt"))
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "denylist", "ERROR", "llms.txt")
        self.assertNotEqual(rc, 0)

    # ------------------------------------------------------------ arguments

    def test_plugin_names_are_validated(self):
        for bad in ("../x", "dojo-a;rm", "alpha", "dojo-", "dojo-A"):
            with self.subTest(bad=bad):
                rc, out, err, rows = self.run_rc("--plugin", bad)
                self.assertEqual(rc, 2, out)
                self.assertEqual(rows, {})

    def test_unknown_argument(self):
        rc, out, err, rows = self.run_rc("--nope")
        self.assertEqual(rc, 2)

    def test_default_plugin_set_is_the_suite_and_missing_ones_are_errors(self):
        rc, out, err, rows = self.run_rc()
        self.assertNotEqual(rc, 0)
        for name in ("dojo-protocol", "dojo-gates", "dojo-router", "dojo-meter", "dojo-verify", "dojo-flow", "dojo-doctor", "dojo-settle", "dojo-suite"):
            self.assertRow(rows, "plugin:" + name, "ERROR", "not found")
        self.assertNotIn("plugin:dojo-dag", rows)

    def test_dependency_only_plugin_has_no_tests_and_no_mod_but_is_validated(self):
        for name in H.SUITE_MEMBERS:
            self.add_plugin(name)
        root = self.add_plugin("dojo-suite", tests=None)
        H.write(os.path.join(root, ".claude-plugin", "plugin.json"), "{}\n")
        rc, out, err, rows = self.run_rc()
        self.assertEqual(rc, 0, out + err)
        self.assertRow(rows, "unittest:dojo-suite", "SKIP", "dependency-only")
        self.assertRow(rows, "validate:dojo-suite", "PASS")
        self.assertRow(rows, "mod:dojo-suite", "SKIP")
        self.assertRow(rows, "unittest:dojo-flow", "PASS")

    def test_other_plugins_without_tests_still_fail(self):
        self.add_plugin("dojo-alpha", tests=None)
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha")
        self.assertRow(rows, "unittest:dojo-alpha", "FAIL", "no tests/")

    def test_only_filter(self):
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", "--only", "lint,unittest")
        self.assertEqual(sorted(rows), ["lint", "unittest:dojo-alpha"])
        rc, out, err, rows = self.run_rc("--plugin", "dojo-alpha", "--only", "validate:dojo-alpha")
        self.assertEqual(sorted(rows), ["validate:dojo-alpha"])

    def test_explicit_plugins_are_passed_to_lint(self):
        self.run_rc("--plugin", "dojo-alpha")
        self.assertIn("lint argv: --repo", self.logtext())
        self.assertIn("dojo-alpha", [l for l in self.logtext().splitlines() if l.startswith("lint argv:")][0])

    def test_no_bytecode_left_in_the_repo(self):
        self.add_plugin("dojo-alpha", register=True)
        self.run_rc("--plugin", "dojo-alpha")
        left = [os.path.join(d, n) for d, ds, fs in os.walk(self.repo) for n in ds + fs if n == "__pycache__" or n.endswith(".pyc")]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
