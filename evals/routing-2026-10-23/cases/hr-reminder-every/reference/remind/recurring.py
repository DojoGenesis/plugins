"""Handles lines of the form '<text> every <interval>'."""

from remind.durations import parse_duration


def parse(rest):
    """`rest` is the text after the word 'every'. Returns the interval in seconds."""
    seconds = parse_duration(rest)
    if seconds <= 0:
        raise ValueError("interval must be positive")
    return seconds
