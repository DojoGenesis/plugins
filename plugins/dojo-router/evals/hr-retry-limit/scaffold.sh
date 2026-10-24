#!/bin/sh
# Writes the project files into the current directory.
set -e

cat > 'README.md' <<'__SCAFFOLD_FILE_END__'
# fetchkit

A tiny fetch client with retries. The transport is a stand-in that fails a set
number of times, so everything can be exercised without a network.

- `fetchkit/defaults.py`  built-in defaults
- `fetchkit/settings.py`  merges defaults, environment (`FETCHKIT_*`) and overrides
- `fetchkit/client.py`    `Client.fetch(url)` with retry and backoff
- `fetchkit/transport.py` `FlakyTransport`
- `fetchkit/cli.py`       `run(argv, transport)`
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""fetchkit: a tiny fetch client with retries, driven by a fake transport."""
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/cli.py' <<'__SCAFFOLD_FILE_END__'
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
    if args.retries:
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
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/client.py' <<'__SCAFFOLD_FILE_END__'
"""The client: send a request, retry on transport errors."""

import time

from fetchkit.defaults import DEFAULTS
from fetchkit.errors import RetriesExhausted, TransportError
from fetchkit.settings import load_settings


class Client:
    def __init__(self, transport, settings=None, sleep=time.sleep):
        self.transport = transport
        self.settings = settings if settings is not None else load_settings()
        self.sleep = sleep
        # number of extra attempts allowed after the first one
        self.max_retries = self.settings.get("max_retries") or DEFAULTS["max_retries"]

    def fetch(self, url):
        attempts = 0
        while True:
            attempts += 1
            try:
                return self.transport.send(url, timeout=self.settings["timeout"])
            except TransportError as exc:
                if attempts > self.max_retries:
                    raise RetriesExhausted(url, attempts) from exc
                self.sleep(self.settings["backoff"] * attempts)
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/defaults.py' <<'__SCAFFOLD_FILE_END__'
"""Built-in defaults for the fetch client."""

DEFAULTS = {
    "timeout": 5.0,
    "max_retries": 3,
    "backoff": 0.5,
}
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/errors.py' <<'__SCAFFOLD_FILE_END__'
"""Exceptions raised by fetchkit."""


class TransportError(Exception):
    """One attempt to reach the server failed."""


class RetriesExhausted(Exception):
    """Every allowed attempt failed."""

    def __init__(self, url, attempts):
        super().__init__(f"gave up on {url} after {attempts} attempt(s)")
        self.url = url
        self.attempts = attempts
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/settings.py' <<'__SCAFFOLD_FILE_END__'
"""Build the effective settings from defaults, environment and explicit overrides."""

from fetchkit.defaults import DEFAULTS

ENV_PREFIX = "FETCHKIT_"


def _from_env(env):
    found = {}
    if not env:
        return found
    raw = env.get(ENV_PREFIX + "MAX_RETRIES")
    if raw not in (None, ""):
        found["max_retries"] = int(raw)
    raw = env.get(ENV_PREFIX + "TIMEOUT")
    if raw not in (None, ""):
        found["timeout"] = float(raw)
    raw = env.get(ENV_PREFIX + "BACKOFF")
    if raw not in (None, ""):
        found["backoff"] = float(raw)
    return found


def load_settings(overrides=None, env=None):
    """Return the effective settings.

    Explicit overrides win over the environment, which wins over the defaults.
    """
    merged = dict(DEFAULTS)
    merged.update(_from_env(env))
    if overrides:
        for key in ("timeout", "backoff"):
            if overrides.get(key) is not None:
                merged[key] = overrides[key]
        merged["max_retries"] = overrides.get("max_retries") or merged["max_retries"]
    return merged
__SCAFFOLD_FILE_END__

mkdir -p 'fetchkit'
cat > 'fetchkit/transport.py' <<'__SCAFFOLD_FILE_END__'
"""A fake transport used by the tests and the demo CLI."""

from fetchkit.errors import TransportError


class FlakyTransport:
    """Fails the first `fail_times` calls, then succeeds."""

    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.calls = 0

    def send(self, url, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TransportError(f"simulated failure {self.calls}")
        return "ok:" + url
__SCAFFOLD_FILE_END__
