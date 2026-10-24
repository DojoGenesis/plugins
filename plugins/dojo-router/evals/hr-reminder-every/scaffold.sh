#!/bin/sh
# Writes the project files into the current directory.
set -e

mkdir -p 'remind'
cat > 'remind/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""remind: parse one-line reminders such as 'stretch every 2h'."""
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/absolute.py' <<'__SCAFFOLD_FILE_END__'
"""Handles lines of the form '<text> at HH:MM' (24 hour clock)."""

DAY = 24 * 3600


def parse(rest, now=0):
    """`rest` is 'HH:MM'. `now` is seconds since midnight.

    Returns the number of seconds until the next occurrence of that time.
    """
    hours, sep, minutes = rest.partition(":")
    if not sep or not hours.isdigit() or not minutes.isdigit():
        raise ValueError(f"bad time of day: {rest!r}")
    hh, mm = int(hours), int(minutes)
    if hh > 23 or mm > 59:
        raise ValueError(f"bad time of day: {rest!r}")
    target = hh * 3600 + mm * 60
    return (target - now) % DAY
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/cli.py' <<'__SCAFFOLD_FILE_END__'
"""Tiny command line front end: prints one line per reminder."""

from remind.parser import parse_line


def describe(reminder):
    if reminder.kind == "every":
        return f"{reminder.text}: every {reminder.seconds}s"
    return f"{reminder.text}: fires in {reminder.seconds}s"


def main(lines, now=0):
    for line in lines:
        print(describe(parse_line(line, now)))
    return 0
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/durations.py' <<'__SCAFFOLD_FILE_END__'
"""Shared duration parsing: '90s', '2h', '1h30m' -> whole seconds."""

import re

UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_CHUNK = re.compile(r"(\d+)([smhd])")


def parse_duration(text):
    text = text.strip().lower()
    if not text:
        raise ValueError("empty duration")
    total = 0
    pos = 0
    for match in _CHUNK.finditer(text):
        if match.start() != pos:
            raise ValueError(f"bad duration: {text!r}")
        total += int(match.group(1)) * UNIT_SECONDS[match.group(2)]
        pos = match.end()
    if pos != len(text):
        raise ValueError(f"bad duration: {text!r}")
    return total
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/parser.py' <<'__SCAFFOLD_FILE_END__'
"""Split a reminder line and hand the time part to the right module."""

import re

from remind import absolute, recurring, relative
from remind.reminder import Reminder

_LINE = re.compile(r"^(?P<text>.+?)\s+(?P<kind>in|at|every)\s+(?P<rest>\S+)$")


def parse_line(line, now=0):
    """Parse '<text> in|at|every <when>' into a Reminder.

    `now` (seconds since midnight) is only used for 'at' reminders.
    """
    match = _LINE.match(line.strip())
    if not match:
        raise ValueError(f"cannot parse reminder: {line!r}")
    kind = match.group("kind")
    rest = match.group("rest")
    if kind == "in":
        seconds = relative.parse(rest)
    elif kind == "at":
        seconds = absolute.parse(rest, now)
    else:
        seconds = recurring.parse(rest)
    return Reminder(match.group("text"), kind, seconds)
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/recurring.py' <<'__SCAFFOLD_FILE_END__'
"""Handles lines of the form '<text> every <interval>'."""

import re

_UNITS = {"s": 1, "m": 60, "h": 60, "d": 24 * 60}
_SINGLE = re.compile(r"(\d+)([smhd])")


def _to_seconds(text):
    match = _SINGLE.fullmatch(text.strip().lower())
    if not match:
        raise ValueError(f"bad interval: {text!r}")
    return int(match.group(1)) * _UNITS[match.group(2)]


def parse(rest):
    """`rest` is the text after the word 'every'. Returns the interval in seconds."""
    seconds = _to_seconds(rest)
    if seconds <= 0:
        raise ValueError("interval must be positive")
    return seconds
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/relative.py' <<'__SCAFFOLD_FILE_END__'
"""Handles lines of the form '<text> in <duration>'."""

from remind.durations import parse_duration


def parse(rest):
    """`rest` is the text after the word 'in'. Returns the delay in seconds."""
    seconds = parse_duration(rest)
    if seconds <= 0:
        raise ValueError("delay must be positive")
    return seconds
__SCAFFOLD_FILE_END__

mkdir -p 'remind'
cat > 'remind/reminder.py' <<'__SCAFFOLD_FILE_END__'
"""The parsed form of a reminder line."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Reminder:
    text: str
    kind: str  # "in", "at" or "every"
    seconds: int  # delay (in/at) or interval (every)
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""Tests for remind."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_parser.py' <<'__SCAFFOLD_FILE_END__'
import unittest

from remind.parser import parse_line


class RelativeAndAbsolute(unittest.TestCase):
    def test_in_minutes(self):
        self.assertEqual(parse_line("call mom in 10m").seconds, 600)

    def test_in_compound(self):
        self.assertEqual(parse_line("standup in 1h30m").seconds, 5400)

    def test_at_later_today(self):
        self.assertEqual(parse_line("lunch at 12:00", now=0).seconds, 12 * 3600)

    def test_at_wraps_to_tomorrow(self):
        self.assertEqual(parse_line("lunch at 12:00", now=13 * 3600).seconds, 23 * 3600)


class Every(unittest.TestCase):
    def test_every_seconds(self):
        reminder = parse_line("ping every 45s")
        self.assertEqual(reminder.kind, "every")
        self.assertEqual(reminder.seconds, 45)

    def test_every_hours(self):
        self.assertEqual(parse_line("stretch every 2h").seconds, 7200)

    def test_every_compound(self):
        self.assertEqual(parse_line("water plants every 1h30m").seconds, 5400)

    def test_every_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_line("nothing every 0s")


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__
