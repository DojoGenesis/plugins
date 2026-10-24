import contextlib
import io
import unittest

from remind import cli
from remind.parser import parse_line


class EveryIntervals(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(parse_line("stretch every 2h").seconds, 7200)

    def test_one_hour(self):
        self.assertEqual(parse_line("drink water every 1h").seconds, 3600)

    def test_days(self):
        self.assertEqual(parse_line("backup every 1d").seconds, 86400)

    def test_minutes(self):
        self.assertEqual(parse_line("check mail every 10m").seconds, 600)

    def test_many_minutes(self):
        self.assertEqual(parse_line("walk every 90m").seconds, 5400)

    def test_seconds(self):
        self.assertEqual(parse_line("ping every 45s").seconds, 45)

    def test_hours_and_minutes(self):
        self.assertEqual(parse_line("water plants every 1h30m").seconds, 5400)

    def test_days_and_hours(self):
        self.assertEqual(parse_line("rotate logs every 2d12h").seconds, 2 * 86400 + 12 * 3600)

    def test_three_parts(self):
        self.assertEqual(parse_line("big job every 1d2h3m").seconds, 86400 + 7200 + 180)

    def test_kind_and_text(self):
        reminder = parse_line("stretch every 2h")
        self.assertEqual(reminder.kind, "every")
        self.assertEqual(reminder.text, "stretch")

    def test_text_may_contain_the_word_every(self):
        reminder = parse_line("check every door every 3h")
        self.assertEqual(reminder.text, "check every door")
        self.assertEqual(reminder.seconds, 3 * 3600)


class EveryRejects(unittest.TestCase):
    def test_zero_seconds(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every 0s")

    def test_zero_compound(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every 0h0m")

    def test_no_unit(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every 5")

    def test_garbage(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every banana")

    def test_trailing_junk(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every 1h30")


class OtherKindsUnchanged(unittest.TestCase):
    def test_in_hours(self):
        self.assertEqual(parse_line("laundry in 2h").seconds, 7200)

    def test_in_compound(self):
        self.assertEqual(parse_line("standup in 1h30m").seconds, 5400)

    def test_in_zero_rejected(self):
        with self.assertRaises(ValueError):
            parse_line("nothing in 0m")

    def test_at_same_day(self):
        self.assertEqual(parse_line("coffee at 09:15", now=8 * 3600).seconds, 4500)

    def test_at_next_day(self):
        self.assertEqual(parse_line("coffee at 07:00", now=8 * 3600).seconds, 23 * 3600)

    def test_at_bad_time(self):
        with self.assertRaises(ValueError):
            parse_line("coffee at 25:00")

    def test_unparseable_line(self):
        with self.assertRaises(ValueError):
            parse_line("just some words")


class CliOutput(unittest.TestCase):
    def test_describe_every(self):
        self.assertEqual(
            cli.describe(parse_line("stretch every 2h")), "stretch: every 7200s"
        )

    def test_main_prints_one_line_each(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["stretch every 1h30m", "call mom in 10m"])
        self.assertEqual(code, 0)
        self.assertEqual(
            out.getvalue().splitlines(),
            ["stretch: every 5400s", "call mom: fires in 600s"],
        )


if __name__ == "__main__":
    unittest.main()
