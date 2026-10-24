"""Command line entry point: `fetchkit URL [--retries N] [--timeout S]`."""

import argparse

from fetchkit.client import Client
from fetchkit.errors import RetriesExhausted
from fetchkit.settings import load_settings


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="fetchkit")
    parser.add_argument("url")
    parser.add_argument(
        "--retries", type=int, default=None, help="extra attempts after the first one"
    )
    parser.add_argument("--timeout", type=float, default=None)
    return parser.parse_args(argv)


def run(argv, transport, env=None, sleep=lambda seconds: None):
    """Run one fetch. Returns the process exit code."""
    args = parse_args(argv)
    overrides = {}
    if args.retries is not None:
        overrides["max_retries"] = args.retries
    if args.timeout is not None:
        overrides["timeout"] = args.timeout
    settings = load_settings(overrides, env)
    client = Client(transport, settings, sleep=sleep)
    try:
        print(client.fetch(args.url))
    except RetriesExhausted as exc:
        print(f"error: {exc}")
        return 1
    return 0
