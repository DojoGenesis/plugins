"""Unit tests for router_common: options, kill switches, once-per-session state."""
import os
import stat
import tempfile
import unittest
from unittest import mock

import _helpers  # noqa: F401  (puts hooks/ on sys.path)
import router_common as rc


def env(**kwargs):
    return mock.patch.dict(os.environ, kwargs, clear=True)


class ModeAndTiers(unittest.TestCase):
    def test_defaults_when_nothing_is_set(self):
        with env():
            self.assertEqual(rc.get_mode(), "warn")
            self.assertEqual(rc.get_default_tier(), "sonnet")
            self.assertEqual(rc.get_explore_tier(), "haiku")

    def test_values_are_stripped_and_case_insensitive(self):
        with env(CLAUDE_PLUGIN_OPTION_MODE=" BLOCK ", CLAUDE_PLUGIN_OPTION_DEFAULT_TIER="Opus",
                 CLAUDE_PLUGIN_OPTION_EXPLORE_TIER=" Sonnet"):
            self.assertEqual(rc.get_mode(), "block")
            self.assertEqual(rc.get_default_tier(), "opus")
            self.assertEqual(rc.get_explore_tier(), "sonnet")

    def test_invalid_values_fall_back_to_the_defaults(self):
        with env(CLAUDE_PLUGIN_OPTION_MODE="bogus", CLAUDE_PLUGIN_OPTION_DEFAULT_TIER="gpt",
                 CLAUDE_PLUGIN_OPTION_EXPLORE_TIER=""):
            self.assertEqual(rc.get_mode(), "warn")
            self.assertEqual(rc.get_default_tier(), "sonnet")
            self.assertEqual(rc.get_explore_tier(), "haiku")

    def test_off_mode_is_recognised(self):
        with env(CLAUDE_PLUGIN_OPTION_MODE="off"):
            self.assertEqual(rc.get_mode(), "off")


class KillSwitches(unittest.TestCase):
    def test_either_switch_kills(self):
        with env(DOJO_OFF="1"):
            self.assertTrue(rc.killed())
        with env(DOJO_ROUTER_OFF="1"):
            self.assertTrue(rc.killed())

    def test_zero_and_empty_do_not_kill(self):
        with env(DOJO_OFF="0", DOJO_ROUTER_OFF=""):
            self.assertFalse(rc.killed())
        with env():
            self.assertFalse(rc.killed())

    def test_suite_switch_is_checked_before_the_plugin_switch(self):
        with env(DOJO_OFF="1", DOJO_ROUTER_OFF="0"):
            self.assertTrue(rc.killed())


class OnceState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_state_lives_under_plugin_data_when_set(self):
        with env(CLAUDE_PLUGIN_DATA=self.tmp.name):
            self.assertTrue(rc.state_dir().startswith(self.tmp.name))
            self.assertTrue(rc.first_time("s", "k"))
            self.assertEqual(len(os.listdir(rc.state_dir())), 1)

    def test_state_falls_back_to_the_temp_dir(self):
        with env():
            self.assertTrue(rc.state_dir().startswith(tempfile.gettempdir()))

    def test_same_key_reports_once_then_not(self):
        with env(CLAUDE_PLUGIN_DATA=self.tmp.name):
            self.assertTrue(rc.first_time("s", "k"))
            self.assertFalse(rc.first_time("s", "k"))
            self.assertTrue(rc.first_time("s", "other"))
            self.assertTrue(rc.first_time("other-session", "k"))

    def test_missing_or_bad_session_id_never_dedupes(self):
        with env(CLAUDE_PLUGIN_DATA=self.tmp.name):
            for bad in (None, "", "   ", 7, ["x"]):
                self.assertTrue(rc.first_time(bad, "k"))
                self.assertTrue(rc.first_time(bad, "k"))
            self.assertFalse(os.path.exists(rc.state_dir()))

    @unittest.skipIf(not hasattr(os, "geteuid") or os.geteuid() == 0, "needs a non-root user")
    def test_unwritable_state_dir_reports_every_time(self):
        locked = os.path.join(self.tmp.name, "locked")
        os.mkdir(locked)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, locked, stat.S_IRWXU)
        with env(CLAUDE_PLUGIN_DATA=locked):
            self.assertTrue(rc.first_time("s", "k"))
            self.assertTrue(rc.first_time("s", "k"))


class Labels(unittest.TestCase):
    def test_label_is_bounded_and_clean(self):
        self.assertEqual(rc.safe_label("a/b\nc"), "a_b_c")
        self.assertEqual(len(rc.safe_label("x" * 500)), 60)


if __name__ == "__main__":
    unittest.main()
