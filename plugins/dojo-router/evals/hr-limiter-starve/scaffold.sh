#!/bin/sh
# Writes the project files into the current directory.
set -e

cat > 'README.md' <<'__SCAFFOLD_FILE_END__'
# ratelimit

A small per-client rate limiter.

- `ratelimit/policy.py`     `Policy(limit, window)`
- `ratelimit/bucket.py`     `TokenBucket`
- `ratelimit/limiter.py`    `Limiter`: one bucket per client
- `ratelimit/middleware.py` `guard(limiter, client_id, handler)`
- `ratelimit/clock.py`      `SystemClock` and a `ManualClock` for tests
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""ratelimit: per-client token bucket limiter."""
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/bucket.py' <<'__SCAFFOLD_FILE_END__'
"""Token bucket.

The bucket holds up to `capacity` tokens and gains `rate` tokens per second.
A request takes one token, or is refused when the bucket is empty.
"""


class TokenBucket:
    def __init__(self, capacity, rate, clock):
        self.capacity = capacity
        self.rate = rate
        self.clock = clock
        self.tokens = capacity  # whole tokens currently in the bucket
        self.last = clock.now()  # when we last looked at the clock

    def _refill(self):
        now = self.clock.now()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + int(elapsed * self.rate))

    def available(self):
        """Whole tokens that could be taken right now."""
        self._refill()
        return self.tokens

    def allow(self, amount=1):
        """Take `amount` tokens if they are there. Returns True when taken."""
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/clock.py' <<'__SCAFFOLD_FILE_END__'
"""Clocks. The limiter only ever asks a clock for the current time in seconds."""

import time


class SystemClock:
    def now(self):
        return time.monotonic()


class ManualClock:
    """A clock that only moves when told to (used by the tests)."""

    def __init__(self, start=0.0):
        self._now = float(start)

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/limiter.py' <<'__SCAFFOLD_FILE_END__'
"""One bucket per client, all following the same policy."""

from ratelimit.bucket import TokenBucket


class Limiter:
    def __init__(self, policy, clock):
        self.policy = policy
        self.clock = clock
        self._buckets = {}

    def _bucket(self, client_id):
        bucket = self._buckets.get(client_id)
        if bucket is None:
            bucket = TokenBucket(self.policy.limit, self.policy.rate, self.clock)
            self._buckets[client_id] = bucket
        return bucket

    def allow(self, client_id):
        return self._bucket(client_id).allow()

    def status(self, client_id):
        """What a quota dashboard shows for this client."""
        return {
            "remaining": self._bucket(client_id).available(),
            "limit": self.policy.limit,
        }
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/middleware.py' <<'__SCAFFOLD_FILE_END__'
"""Glue between the limiter and a request handler."""


def guard(limiter, client_id, handler):
    """Run `handler()` unless the client is over its limit.

    Returns (status_code, body).
    """
    if not limiter.allow(client_id):
        return 429, "slow down"
    return 200, handler()
__SCAFFOLD_FILE_END__

mkdir -p 'ratelimit'
cat > 'ratelimit/policy.py' <<'__SCAFFOLD_FILE_END__'
"""How many requests a client may make in a time window."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    limit: int  # requests allowed per window (also the burst size)
    window: float  # seconds

    @property
    def rate(self):
        """Tokens gained per second."""
        return self.limit / self.window
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""Tests for ratelimit."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_bucket.py' <<'__SCAFFOLD_FILE_END__'
import unittest

from ratelimit.bucket import TokenBucket
from ratelimit.clock import ManualClock


def make(capacity=2, rate=0.5):
    clock = ManualClock()
    return clock, TokenBucket(capacity, rate, clock)


class BucketBasics(unittest.TestCase):
    def test_starts_full(self):
        _, bucket = make()
        self.assertEqual(bucket.available(), 2)

    def test_burst_then_refused(self):
        _, bucket = make()
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())

    def test_long_wait_refills_to_capacity(self):
        clock, bucket = make()
        bucket.allow()
        bucket.allow()
        clock.advance(100)
        self.assertEqual(bucket.available(), 2)

    def test_never_holds_more_than_capacity(self):
        clock, bucket = make()
        clock.advance(1000)
        self.assertEqual(bucket.available(), 2)
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())

    def test_one_token_after_two_seconds(self):
        clock, bucket = make()
        bucket.allow()
        bucket.allow()
        clock.advance(2.0)
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())

    def test_asking_for_several_tokens(self):
        clock, bucket = make(capacity=5, rate=1.0)
        self.assertTrue(bucket.allow(3))
        self.assertFalse(bucket.allow(3))
        clock.advance(1.0)
        self.assertTrue(bucket.allow(3))


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_limiter.py' <<'__SCAFFOLD_FILE_END__'
import unittest

from ratelimit.clock import ManualClock
from ratelimit.limiter import Limiter
from ratelimit.middleware import guard
from ratelimit.policy import Policy


class LimiterBasics(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.limiter = Limiter(Policy(limit=2, window=4.0), self.clock)

    def test_clients_are_independent(self):
        self.assertTrue(self.limiter.allow("a"))
        self.assertTrue(self.limiter.allow("a"))
        self.assertFalse(self.limiter.allow("a"))
        self.assertTrue(self.limiter.allow("b"))

    def test_status_shows_remaining(self):
        self.limiter.allow("a")
        status = self.limiter.status("a")
        self.assertEqual(status, {"remaining": 1, "limit": 2})

    def test_guard_returns_429_when_over(self):
        self.assertEqual(guard(self.limiter, "a", lambda: "hi"), (200, "hi"))
        self.assertEqual(guard(self.limiter, "a", lambda: "hi"), (200, "hi"))
        self.assertEqual(guard(self.limiter, "a", lambda: "hi"), (429, "slow down"))

    def test_waiting_quietly_lets_a_client_back_in(self):
        self.limiter.allow("a")
        self.limiter.allow("a")
        self.clock.advance(2.0)
        self.assertTrue(self.limiter.allow("a"))


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__
