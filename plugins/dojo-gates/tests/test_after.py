import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _payloads as P  # noqa: E402


class AfterCase(unittest.TestCase):
    def setUp(self):
        self.data = P.tmpdir()
        self.addCleanup(P.rmtree, self.data)
        self.env = P.base_env(CLAUDE_PLUGIN_DATA=self.data)

    def run_after(self, payload, env=None):
        return P.run_hook("bash_after", payload, env=env or self.env)

    def note(self, payload, event, env=None):
        r = self.run_after(payload, env)
        self.assertEqual(r.code, 0)
        self.assertEqual(r.err, "")
        self.assertEqual(r.hso.get("hookEventName"), event, r.out)
        self.assertNotIn("permissionDecision", r.out)
        self.assertNotIn("systemMessage", r.out)
        self.assertTrue(r.context.startswith("dojo-gates: "), r.out)
        return r

    def quiet(self, payload, env=None):
        r = self.run_after(payload, env)
        self.assertEqual(r.code, 0)
        self.assertEqual(r.out, "", r.out)
        self.assertEqual(r.err, "")


class ConfigFirstTests(AfterCase):
    CASES = [
        ("curl -s https://x.example/a", "HTTP/1.1 401 Unauthorized\n", "auth"),
        ("curl -f https://x.example/a", "curl: (22) The requested URL returned error: 403\n", "auth"),
        ("curl https://x.example/a", '{"status":401}', "auth"),
        ("curl -i https://x.example/a", "HTTP/2 403\n", "auth"),
        ("curl https://x.example/a", "Error 403: Forbidden", "auth"),
        ("gh api /x", "gh: Unauthorized (HTTP 401)", "auth"),
        ("npm run dev", "connect ECONNREFUSED 127.0.0.1:5432\n", "connection"),
        ("curl localhost:9", "curl: (7) Failed to connect to localhost port 9: Connection refused", "connection"),
        ("foo", "bash: foo: command not found\n", "command"),
        ("foo", "zsh: command not found: foo\n", "command"),
        ("ls nope", "ls: nope: No such file or directory\n", "path"),
    ]

    def test_post_tool_use_shape(self):
        for i, (cmd, out, kind) in enumerate(self.CASES):
            with self.subTest(out=out[:30]):
                payload = P.post_bash(cmd, stdout="", stderr=out, session="sess-%d" % i)
                r = self.note(payload, "PostToolUse")
                self.assertIn("config-first", r.context)
                self.assertIn("Check env, settings and credentials", r.context)
                self.assertIsNone(P.TRIGGER.search(r.context), r.context)
                # the same text on stdout works too
                self.note(P.post_bash(cmd, stdout=out, session="sess-b-%d" % i), "PostToolUse")

    def test_post_tool_use_failure_shape(self):
        for i, (cmd, out, kind) in enumerate(self.CASES):
            with self.subTest(out=out[:30]):
                payload = P.post_fail(cmd, "Exit code 127\n" + out, session="fail-%d" % i)
                self.note(payload, "PostToolUseFailure")

    def test_clean_output_is_silent(self):
        for out in [
            "401 passed", "403 insertions(+)", "  401 total", "all good\n", "tests: 40 passed",
            "Processed 401 records with status ok",
            "line 403 of file: error parsing",
            "403 files changed, error budget unchanged",
            "see section 401 (authentication notes)",
        ]:
            with self.subTest(out=out):
                self.quiet(P.post_bash("make", stdout=out))

    def test_assertion_lines_from_a_test_run_are_not_a_config_problem(self):
        out = "FAILED t.py::test_x - AssertionError: status: 403 != 200\n"
        self.quiet(P.post_fail("pytest -q", "Exit code 1\n" + out))
        self.quiet(P.post_fail("cd sub && python3 -m pytest", "Exit code 1\n" + out, session="s2"))
        self.quiet(P.post_fail("npm test", "Exit code 1\n  expected 401 to equal 200\n", session="s3"))
        # the same words from a non-test command, or without an assertion, still note
        self.note(P.post_bash("curl x", stderr="status: 403 != 200", session="s4"), "PostToolUse")
        self.note(P.post_fail("pytest -q", "Exit code 1\nHTTP/1.1 401 Unauthorized\n", session="s5"),
                  "PostToolUseFailure")
        # a missing command during a test run is still a configuration problem
        self.note(P.post_fail("npm test", "Exit code 127\nsh: vitest: command not found\n", session="s6"),
                  "PostToolUseFailure")

    def test_readers_and_searchers_are_skipped(self):
        for cmd, out in [
            ("rg ECONNREFUSED src/", "src/net.js:12: // handle ECONNREFUSED here"),
            ("grep -rn 401 .", "./a.py:1: status = 401 Unauthorized"),
            ("cat notes.txt", "see: command not found"),
            ("git log --oneline", "abc fix: No such file or directory crash"),
            ("sed -n 1,5p f", "HTTP 403 forbidden"),
        ]:
            with self.subTest(cmd=cmd):
                self.quiet(P.post_bash(cmd, stdout=out))

    def test_once_per_session_per_pattern(self):
        p = P.post_bash("foo", stderr="bash: foo: command not found", session="one")
        self.note(p, "PostToolUse")
        self.quiet(p)
        self.quiet(P.post_bash("bar", stderr="bash: bar: command not found", session="one"))
        # a different session fires again
        self.note(P.post_bash("foo", stderr="bash: foo: command not found", session="two"), "PostToolUse")
        # a different pattern in the same session fires
        self.note(P.post_bash("curl x", stderr="HTTP 401 Unauthorized", session="one"), "PostToolUse")
        # the failure event shares the same once-marker
        self.quiet(P.post_fail("foo", "Exit code 127\nbash: foo: command not found", session="one"))

    def test_output_lines_are_not_echoed(self):
        secret_line = "HTTP 401 Unauthorized for token hunter2-value"
        r = self.note(P.post_bash("curl x", stderr=secret_line), "PostToolUse")
        self.assertNotIn("hunter2", r.out)

    def test_parallel_hooks_emit_once(self):
        import json

        payload = json.dumps(P.post_bash("foo", stderr="bash: foo: command not found", session="race")).encode()
        procs = [
            subprocess.Popen([P.PY, P.SCRIPTS["bash_after"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=self.env)
            for _ in range(6)
        ]
        outs = [p.communicate(payload)[0].decode() for p in procs]
        self.assertEqual(sum(1 for o in outs if o.strip()), 1, outs)

    def test_session_id_cannot_escape_the_state_directory(self):
        self.note(P.post_bash("foo", stderr="bash: foo: command not found", session="../../evil"), "PostToolUse")
        top = os.listdir(self.data)
        self.assertEqual(top, ["dojo-gates"])
        inner = os.listdir(os.path.join(self.data, "dojo-gates"))
        self.assertEqual(len(inner), 1)
        self.assertNotIn("/", inner[0])
        self.assertNotIn("..", inner[0])

    def test_no_session_id_still_works(self):
        payload = P.post_bash("foo", stderr="bash: foo: command not found")
        del payload["session_id"]
        self.note(payload, "PostToolUse")
        self.quiet(payload)


class EmptyProbeTests(AfterCase):
    def test_post_tool_use_empty_output_fires(self):
        for i, cmd in enumerate([
            "grep -rn foo .",
            "rg foo src",
            "find . -name x",
            "ls emptydir",
            "fd foo",
            "curl -s https://x.example/a",
            "curl -fsSL https://x.example/a | jq .x",
            "cat f | grep needle",
            "cd src && grep -n foo *.py",
        ]):
            with self.subTest(cmd=cmd):
                payload = P.post_bash(cmd, session="probe-%d" % i)
                payload["tool_response"]["returnCodeInterpretation"] = "No matches found"
                r = self.note(payload, "PostToolUse")
                self.assertIn("empty-probe", r.context)
                self.assertIn("known positive", r.context)

    def test_post_tool_use_failure_exit_one_fires(self):
        for i, cmd in enumerate(["curl -s https://x.example/a | jq .x", "ls missing 2>/dev/null", "fd foo"]):
            with self.subTest(cmd=cmd):
                r = self.note(P.post_fail(cmd, "Exit code 1", session="pf-%d" % i), "PostToolUseFailure")
                self.assertIn("empty-probe", r.context)

    def test_silent_cases(self):
        cases = [
            P.post_bash("grep foo f", stdout="foo\n"),                       # non-empty output
            P.post_bash("mkdir x"),                                          # not a probe
            P.post_bash("grep -q foo f"),                                    # quiet by request
            P.post_bash("grep --quiet foo f"),
            P.post_bash("grep -rq foo ."),
            P.post_bash("grep foo f > hits.txt"),                            # output went to a file
            P.post_bash("grep foo f >/dev/null"),
            P.post_bash("grep foo f &>/dev/null"),
            P.post_bash("curl -sS -o out.html https://x.example"),           # body saved to a file
            P.post_bash("grep foo f", interrupted=True),
            P.post_bash("grep foo f", stderr="grep: f: warning"),            # stderr: not ours to explain
            P.post_fail("grep foo f", "Exit code 2\ngrep: f: bad"),
            P.post_fail("curl -s x", "Exit code 22"),
            P.post_fail("ls missing", "Exit code 1\nls: missing: gone"),
            P.post_fail("jq .x f", "Exit code 5\njq: error"),
        ]
        bg = P.post_bash("grep foo f")
        bg["tool_input"]["run_in_background"] = True
        cases.append(bg)
        bg2 = P.post_bash("grep foo f")
        bg2["tool_response"]["backgroundTaskId"] = "bg1"
        cases.append(bg2)
        for i, payload in enumerate(cases):
            with self.subTest(i=i, cmd=payload["tool_input"]["command"]):
                payload["session_id"] = "quiet-%d" % i
                self.quiet(payload)

    def test_once_per_session(self):
        p = P.post_bash("grep -rn foo .", session="once")
        self.note(p, "PostToolUse")
        self.quiet(p)
        self.quiet(P.post_bash("find . -name y", session="once"))
        self.note(P.post_bash("grep -rn foo .", session="other"), "PostToolUse")

    def test_both_notes_can_arrive_together_as_one_object(self):
        # empty stdout, but stderr says a path is missing: config-first speaks, empty-probe stays out
        r = self.note(P.post_fail("ls nope", "Exit code 2\nls: nope: No such file or directory"), "PostToolUseFailure")
        self.assertIn("config-first", r.context)
        self.assertNotIn("empty-probe", r.context)


class SwitchTests(AfterCase):
    def test_kill_switches(self):
        payload = P.post_bash("foo", stderr="bash: foo: command not found")
        for name, env in [
            ("DOJO_OFF", dict(DOJO_OFF="1")),
            ("DOJO_GATES_OFF", dict(DOJO_GATES_OFF="1")),
            ("skip config-first", dict(DOJO_GATES_SKIP="config-first")),
            ("skip list with spaces", dict(DOJO_GATES_SKIP=" empty-probe , config-first ")),
        ]:
            with self.subTest(name=name):
                data = P.tmpdir()
                self.addCleanup(P.rmtree, data)
                self.quiet(payload, env=P.base_env(CLAUDE_PLUGIN_DATA=data, **env))
        data = P.tmpdir()
        self.addCleanup(P.rmtree, data)
        self.note(payload, "PostToolUse", env=P.base_env(CLAUDE_PLUGIN_DATA=data, DOJO_GATES_SKIP="empty-probe"))

    def test_skipping_one_guard_leaves_the_other(self):
        probe = P.post_bash("grep -rn foo .")
        data = P.tmpdir()
        self.addCleanup(P.rmtree, data)
        self.quiet(probe, env=P.base_env(CLAUDE_PLUGIN_DATA=data, DOJO_GATES_SKIP="empty-probe"))
        data2 = P.tmpdir()
        self.addCleanup(P.rmtree, data2)
        self.note(probe, "PostToolUse", env=P.base_env(CLAUDE_PLUGIN_DATA=data2, DOJO_GATES_SKIP="config-first"))

    def test_unwritable_state_makes_the_hook_quiet(self):
        env = P.base_env(CLAUDE_PLUGIN_DATA="/dev/null/nope")
        self.quiet(P.post_bash("foo", stderr="bash: foo: command not found"), env=env)

    def test_other_events_and_tools_are_ignored(self):
        p = P.post_bash("foo", stderr="bash: foo: command not found")
        p["hook_event_name"] = "PostToolBatch"
        self.quiet(p)
        p = P.post_bash("foo", stderr="bash: foo: command not found")
        p["tool_name"] = "Read"
        self.quiet(p)


if __name__ == "__main__":
    unittest.main()
