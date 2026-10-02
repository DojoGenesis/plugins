import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _payloads as P  # noqa: E402


class ReadGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = P.tmpdir()
        self.addCleanup(P.rmtree, self.tmp)

    def make(self, name, size):
        p = os.path.join(self.tmp, name)
        with open(p, "wb") as f:
            f.write(b"a" * size)
        return p

    def run_read(self, path, env=None, cwd=None, **kw):
        return P.run_hook("read_guard", P.pre_read(path, cwd=cwd or self.tmp, **kw), env=env)

    def assert_denied(self, r):
        self.assertEqual(r.code, 0)
        self.assertEqual(r.err, "")
        self.assertEqual(r.decision, "deny", r.out)
        self.assertTrue(r.reason.startswith("dojo-gates: big-read "), r.reason)
        self.assertIsNone(P.TRIGGER.search(r.reason), r.reason)
        return r

    def assert_silent(self, r):
        self.assertEqual(r.code, 0)
        self.assertEqual(r.out, "")
        self.assertEqual(r.err, "")

    def test_over_the_limit_without_offset_or_limit_is_denied(self):
        p = self.make("big.txt", 262145)
        r = self.assert_denied(self.run_read(p))
        self.assertIn("256 KB", r.reason.replace("256 KB", "256 KB"))  # size is stated in KB
        self.assertIn("grep -n", r.reason)
        self.assertIn("offset", r.reason)
        self.assertIn("limit", r.reason)
        self.assertIn("DOJO_GATES_SKIP=big-read", r.reason)

    def test_reason_states_the_size(self):
        p = self.make("big.txt", 300 * 1024)
        r = self.assert_denied(self.run_read(p))
        self.assertIn("300 KB", r.reason)

    def test_exactly_the_limit_is_allowed(self):
        self.assert_silent(self.run_read(self.make("edge.txt", 262144)))

    def test_small_file_is_allowed(self):
        self.assert_silent(self.run_read(self.make("small.txt", 100)))

    def test_offset_or_limit_lets_a_big_file_through(self):
        p = self.make("big.txt", 262145)
        self.assert_silent(self.run_read(p, offset=0))
        self.assert_silent(self.run_read(p, offset=100))
        self.assert_silent(self.run_read(p, limit=50))
        self.assert_silent(self.run_read(p, offset=10, limit=50))

    def test_null_offset_and_limit_do_not_count(self):
        p = self.make("big.txt", 262145)
        self.assert_denied(self.run_read(p, offset=None, limit=None))

    def test_images_pdfs_and_notebooks_are_left_to_read(self):
        for name in ("a.pdf", "a.PNG", "a.jpg", "a.jpeg", "a.gif", "a.webp", "a.ipynb"):
            with self.subTest(name=name):
                self.assert_silent(self.run_read(self.make(name, 400000)))

    def test_directory_and_missing_file_are_allowed(self):
        self.assert_silent(self.run_read(self.tmp))
        self.assert_silent(self.run_read(os.path.join(self.tmp, "nope.txt")))

    def test_relative_path_resolves_against_payload_cwd(self):
        self.make("rel.txt", 262145)
        self.assert_denied(self.run_read("rel.txt", cwd=self.tmp))
        self.assert_silent(self.run_read("rel.txt", cwd=os.path.join(self.tmp, "elsewhere")))

    def test_symlink_to_a_big_file_is_denied(self):
        p = self.make("real.txt", 262145)
        link = os.path.join(self.tmp, "link.txt")
        os.symlink(p, link)
        self.assert_denied(self.run_read(link))

    def test_kill_switches(self):
        p = self.make("big.txt", 262145)
        self.assert_denied(self.run_read(p))
        self.assert_silent(self.run_read(p, env=P.base_env(DOJO_OFF="1")))
        self.assert_silent(self.run_read(p, env=P.base_env(DOJO_GATES_OFF="1")))
        self.assert_silent(self.run_read(p, env=P.base_env(DOJO_GATES_SKIP="big-read")))
        self.assert_silent(self.run_read(p, env=P.base_env(DOJO_GATES_SKIP=" staging , big-read ")))
        self.assert_denied(self.run_read(p, env=P.base_env(DOJO_GATES_SKIP="staging")))
        self.assert_denied(self.run_read(p, env=P.base_env(DOJO_OFF="0", DOJO_GATES_OFF="")))

    def test_garbage_input_fails_open(self):
        for raw in ["", "nope", "[]", '{"tool_name":"Read"}', '{"tool_name":"Read","tool_input":{"file_path":5}}']:
            with self.subTest(raw=raw):
                self.assert_silent(P.run_hook("read_guard", raw=raw))


if __name__ == "__main__":
    unittest.main()
