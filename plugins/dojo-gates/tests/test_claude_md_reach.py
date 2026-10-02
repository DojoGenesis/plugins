import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _payloads as P  # noqa: E402


class ReachCase(unittest.TestCase):
    def setUp(self):
        self.root = P.tmpdir()
        self.data = P.tmpdir()
        self.addCleanup(P.rmtree, self.root)
        self.addCleanup(P.rmtree, self.data)
        self.work = os.path.join(self.root, "work")
        self.app = os.path.join(self.work, "app")
        os.makedirs(os.path.join(self.app, "pkg", "new"))
        os.makedirs(os.path.join(self.app, "other", ".claude"))
        os.makedirs(os.path.join(self.root, "real", "proj"))
        os.makedirs(os.path.join(self.root, "bare"))
        self.touch(os.path.join(self.work, "CLAUDE.md"))
        self.touch(os.path.join(self.app, "pkg", "CLAUDE.md"))
        self.touch(os.path.join(self.app, "other", ".claude", "CLAUDE.md"))
        self.touch(os.path.join(self.root, "real", "proj", "CLAUDE.md"))
        self.touch(os.path.join(self.app, "y.py"))
        self.touch(os.path.join(self.app, "pkg", "x.py"))
        self.touch(os.path.join(self.app, "other", "z.py"))
        self.touch(os.path.join(self.root, "bare", "b.py"))
        os.symlink(os.path.join(self.root, "real"), os.path.join(self.root, "alias"))
        self.transcript = self.write_transcript(self.app)
        self.env = self.make_env(True)

    def touch(self, path):
        with open(path, "w") as f:
            f.write("x\n")

    def write_transcript(self, cwd, name="t.jsonl"):
        p = os.path.join(self.root, name)
        with open(p, "w") as f:
            f.write(json.dumps({"type": "summary", "summary": "x"}) + "\n")
            f.write(json.dumps({"type": "file-history-snapshot"}) + "\n")
            f.write(json.dumps({"type": "user", "cwd": cwd, "message": {"content": "hi"}}) + "\n")
            f.write(json.dumps({"type": "user", "cwd": "/somewhere/else"}) + "\n")
        return p

    def make_env(self, on, **extra):
        env = P.base_env(CLAUDE_PLUGIN_DATA=self.data, **extra)
        if on is not None:
            env["CLAUDE_PLUGIN_OPTION_CLAUDE_MD_REACH"] = on if isinstance(on, str) else "true"
        return env

    def edit(self, path, env=None, session="s-reach", transcript=None, tool="Edit", cwd=None):
        payload = P.pre_edit(path, tool=tool, cwd=cwd or self.app, session=session,
                             transcript=transcript or self.transcript)
        return P.run_hook("claude_md_reach", payload, env=env or self.env)

    def assert_deny(self, r, naming):
        self.assertEqual(r.code, 0)
        self.assertEqual(r.err, "")
        self.assertEqual(r.decision, "deny", r.out)
        self.assertTrue(r.reason.startswith("dojo-gates: claude-md-reach "), r.reason)
        self.assertIn(os.path.realpath(naming), r.reason)
        self.assertIn("Read", r.reason)
        self.assertIn("DOJO_GATES_SKIP=claude-md-reach", r.reason)
        self.assertIsNone(P.TRIGGER.search(r.reason.replace(self.root, "").replace("/private", "")), r.reason)

    def assert_silent(self, r):
        self.assertEqual(r.code, 0)
        self.assertEqual(r.out, "", r.out)
        self.assertEqual(r.err, "")


class OptionTests(ReachCase):
    def test_absent_or_false_option_is_silent(self):
        target = os.path.join(self.app, "pkg", "x.py")
        self.assert_silent(self.edit(target, env=self.make_env(None)))
        self.assert_silent(self.edit(target, env=self.make_env("false")))
        self.assert_silent(self.edit(target, env=self.make_env("0")))
        self.assert_silent(self.edit(target, env=self.make_env("")))

    def test_accepted_spellings_turn_it_on(self):
        target = os.path.join(self.app, "pkg", "x.py")
        for i, v in enumerate(["true", "TRUE", "1", "yes"]):
            with self.subTest(value=v):
                r = self.edit(target, env=self.make_env(v), session="spell-%d" % i)
                self.assertEqual(r.decision, "deny")

    def test_kill_switches(self):
        target = os.path.join(self.app, "pkg", "x.py")
        for name, extra in [
            ("DOJO_OFF", dict(DOJO_OFF="1")),
            ("DOJO_GATES_OFF", dict(DOJO_GATES_OFF="1")),
            ("skip", dict(DOJO_GATES_SKIP="claude-md-reach")),
            ("skip spaces", dict(DOJO_GATES_SKIP=" big-read , claude-md-reach ")),
        ]:
            with self.subTest(name=name):
                self.assert_silent(self.edit(target, env=self.make_env(True, **extra), session="k-" + name))
        r = self.edit(target, env=self.make_env(True, DOJO_GATES_SKIP="staging"), session="k-other")
        self.assertEqual(r.decision, "deny")


class ReachTests(ReachCase):
    def test_denies_once_per_file_per_session(self):
        target = os.path.join(self.app, "pkg", "x.py")
        self.assert_deny(self.edit(target), os.path.join(self.app, "pkg", "CLAUDE.md"))
        self.assert_silent(self.edit(target))
        # a sibling file under the same governing CLAUDE.md is covered by the same marker
        self.touch(os.path.join(self.app, "pkg", "x2.py"))
        self.assert_silent(self.edit(os.path.join(self.app, "pkg", "x2.py")))
        # a new session is nudged again
        self.assert_deny(self.edit(target, session="another"), os.path.join(self.app, "pkg", "CLAUDE.md"))

    def test_write_tool_and_multiedit_name_are_covered(self):
        target = os.path.join(self.app, "pkg", "x.py")
        self.assert_deny(self.edit(target, tool="Write", session="w"), os.path.join(self.app, "pkg", "CLAUDE.md"))
        self.assert_deny(self.edit(target, tool="MultiEdit", session="m"), os.path.join(self.app, "pkg", "CLAUDE.md"))
        self.assert_silent(self.edit(target, tool="Read", session="r"))

    def test_claude_md_at_or_above_startup_cwd_is_allowed(self):
        self.assert_silent(self.edit(os.path.join(self.app, "y.py")))

    def test_dot_claude_directory_counts(self):
        self.assert_deny(
            self.edit(os.path.join(self.app, "other", "z.py")),
            os.path.join(self.app, "other", ".claude", "CLAUDE.md"),
        )

    def test_no_claude_md_anywhere_is_allowed(self):
        self.assert_silent(self.edit(os.path.join(self.root, "bare", "b.py")))

    def test_instructions_loaded_event_marks_a_file_as_loaded(self):
        target = os.path.join(self.app, "pkg", "x.py")
        gov = os.path.join(self.app, "pkg", "CLAUDE.md")
        r = P.run_hook("claude_md_reach", P.instructions_loaded(gov, session="seen"), env=self.env)
        self.assert_silent(r)
        self.assert_silent(self.edit(target, session="seen"))
        # other sessions don't inherit it
        self.assertEqual(self.edit(target, session="unseen").decision, "deny")

    def test_instructions_loaded_is_ignored_when_the_option_is_off(self):
        gov = os.path.join(self.app, "pkg", "CLAUDE.md")
        off = self.make_env(None)
        self.assert_silent(P.run_hook("claude_md_reach", P.instructions_loaded(gov, session="off"), env=off))
        self.assertEqual(os.listdir(self.data), [])

    def test_symlinked_startup_path_is_the_same_directory(self):
        transcript = self.write_transcript(os.path.join(self.root, "alias", "proj"), "alias.jsonl")
        target = os.path.join(self.root, "real", "proj", "f.py")
        self.touch(target)
        self.assert_silent(self.edit(target, transcript=transcript, cwd=os.path.join(self.root, "alias", "proj")))
        # and the other way round
        target2 = os.path.join(self.root, "alias", "proj", "g.py")
        transcript2 = self.write_transcript(os.path.join(self.root, "real", "proj"), "real.jsonl")
        self.assert_silent(self.edit(target2, transcript=transcript2, session="s2"))

    def test_new_nested_path_walks_from_the_nearest_existing_directory(self):
        target = os.path.join(self.app, "pkg", "new", "deeper", "still", "f.py")
        self.assert_deny(self.edit(target), os.path.join(self.app, "pkg", "CLAUDE.md"))

    def test_missing_transcript_falls_back_to_payload_cwd(self):
        target = os.path.join(self.app, "pkg", "x.py")
        gone = os.path.join(self.root, "gone.jsonl")
        self.assert_deny(self.edit(target, transcript=gone, cwd=self.app), os.path.join(self.app, "pkg", "CLAUDE.md"))
        self.assert_silent(self.edit(os.path.join(self.app, "y.py"), transcript=gone, cwd=self.app, session="s3"))

    def test_transcript_without_cwd_falls_back_to_payload_cwd(self):
        p = os.path.join(self.root, "nocwd.jsonl")
        with open(p, "w") as f:
            f.write(json.dumps({"type": "summary"}) + "\n")
            f.write("not json\n")
        self.assert_silent(self.edit(os.path.join(self.app, "y.py"), transcript=p))

    def test_huge_first_line_is_read_in_bounded_time(self):
        p = os.path.join(self.root, "huge.jsonl")
        with open(p, "wb") as f:
            f.write(b"x" * (10 * 1024 * 1024))
        t0 = time.monotonic()
        r = self.edit(os.path.join(self.app, "pkg", "x.py"), transcript=p, cwd=self.app)
        self.assertLess(time.monotonic() - t0, 3.0)
        self.assertEqual(r.code, 0)
        self.assertEqual(r.decision, "deny")  # fell back to the payload cwd

    def test_relative_target_resolves_against_payload_cwd(self):
        self.assert_deny(self.edit("pkg/x.py", cwd=self.app), os.path.join(self.app, "pkg", "CLAUDE.md"))

    def test_session_id_cannot_escape_the_state_directory(self):
        self.edit(os.path.join(self.app, "pkg", "x.py"), session="../../evil")
        self.assertEqual(os.listdir(self.data), ["dojo-gates"])
        for name in os.listdir(os.path.join(self.data, "dojo-gates")):
            self.assertNotIn("/", name)
            self.assertNotIn("..", name)

    def test_unwritable_state_makes_the_hook_quiet(self):
        env = self.make_env(True)
        env["CLAUDE_PLUGIN_DATA"] = "/dev/null/nope"
        self.assert_silent(self.edit(os.path.join(self.app, "pkg", "x.py"), env=env))

    def test_garbage_fails_open(self):
        for raw in ["", "nope", "[]", '{"tool_name":"Edit"}', '{"tool_name":"Edit","tool_input":{"file_path":7}}',
                    '{"hook_event_name":"InstructionsLoaded"}', '{"hook_event_name":"InstructionsLoaded","file_path":5}']:
            with self.subTest(raw=raw):
                self.assert_silent(P.run_hook("claude_md_reach", raw=raw, env=self.env))


if __name__ == "__main__":
    unittest.main()
