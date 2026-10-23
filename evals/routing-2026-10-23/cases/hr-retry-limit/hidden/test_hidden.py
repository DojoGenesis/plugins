import contextlib
import io
import unittest

from fetchkit import cli
from fetchkit.client import Client
from fetchkit.errors import RetriesExhausted
from fetchkit.settings import load_settings
from fetchkit.transport import FlakyTransport


def nosleep(seconds):
    pass


class ZeroRetries(unittest.TestCase):
    def test_settings_keep_zero(self):
        self.assertEqual(load_settings({"max_retries": 0})["max_retries"], 0)

    def test_env_zero_reaches_settings(self):
        settings = load_settings(env={"FETCHKIT_MAX_RETRIES": "0"})
        self.assertEqual(settings["max_retries"], 0)

    def test_client_zero_means_one_attempt(self):
        transport = FlakyTransport(fail_times=10)
        client = Client(transport, load_settings({"max_retries": 0}), sleep=nosleep)
        with self.assertRaises(RetriesExhausted) as ctx:
            client.fetch("http://x/a")
        self.assertEqual(transport.calls, 1)
        self.assertEqual(ctx.exception.attempts, 1)

    def test_client_zero_from_env(self):
        transport = FlakyTransport(fail_times=10)
        settings = load_settings(env={"FETCHKIT_MAX_RETRIES": "0"})
        client = Client(transport, settings, sleep=nosleep)
        with self.assertRaises(RetriesExhausted):
            client.fetch("http://x/a")
        self.assertEqual(transport.calls, 1)

    def test_client_given_a_plain_dict_with_zero(self):
        transport = FlakyTransport(fail_times=10)
        settings = dict(load_settings())
        settings["max_retries"] = 0
        client = Client(transport, settings, sleep=nosleep)
        with self.assertRaises(RetriesExhausted):
            client.fetch("http://x/a")
        self.assertEqual(transport.calls, 1)

    def test_cli_retries_zero(self):
        transport = FlakyTransport(fail_times=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.run(["--retries", "0", "http://x/a"], transport)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, 1)

    def test_cli_retries_zero_beats_env(self):
        transport = FlakyTransport(fail_times=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.run(
                ["--retries", "0", "http://x/a"],
                transport,
                env={"FETCHKIT_MAX_RETRIES": "5"},
            )
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, 1)

    def test_cli_zero_succeeds_when_first_attempt_works(self):
        transport = FlakyTransport(fail_times=0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.run(["--retries", "0", "http://x/a"], transport)
        self.assertEqual(code, 0)
        self.assertIn("ok:http://x/a", out.getvalue())


class OtherCountsStillWork(unittest.TestCase):
    def test_default_is_three_retries(self):
        transport = FlakyTransport(fail_times=10)
        client = Client(transport, sleep=nosleep)
        with self.assertRaises(RetriesExhausted):
            client.fetch("http://x/a")
        self.assertEqual(transport.calls, 4)

    def test_default_recovers_after_two_failures(self):
        transport = FlakyTransport(fail_times=2)
        client = Client(transport, sleep=nosleep)
        self.assertEqual(client.fetch("http://x/a"), "ok:http://x/a")
        self.assertEqual(transport.calls, 3)

    def test_two_retries_means_three_attempts(self):
        transport = FlakyTransport(fail_times=10)
        client = Client(transport, load_settings({"max_retries": 2}), sleep=nosleep)
        with self.assertRaises(RetriesExhausted):
            client.fetch("http://x/a")
        self.assertEqual(transport.calls, 3)

    def test_cli_without_flag_uses_default(self):
        transport = FlakyTransport(fail_times=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.run(["http://x/a"], transport)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, 4)

    def test_cli_flag_overrides_env(self):
        transport = FlakyTransport(fail_times=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.run(
                ["--retries", "1", "http://x/a"],
                transport,
                env={"FETCHKIT_MAX_RETRIES": "5"},
            )
        self.assertEqual(transport.calls, 2)

    def test_env_used_when_no_flag(self):
        transport = FlakyTransport(fail_times=10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.run(["http://x/a"], transport, env={"FETCHKIT_MAX_RETRIES": "1"})
        self.assertEqual(transport.calls, 2)


if __name__ == "__main__":
    unittest.main()
