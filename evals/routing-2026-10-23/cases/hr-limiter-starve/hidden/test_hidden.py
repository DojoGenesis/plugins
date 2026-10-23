import unittest

from ratelimit.bucket import TokenBucket
from ratelimit.clock import ManualClock
from ratelimit.limiter import Limiter
from ratelimit.middleware import guard
from ratelimit.policy import Policy

# All times below are multiples of 0.25 and all rates are binary fractions,
# so the arithmetic is exact and the expected step counts are not rounding luck.


def make(capacity=2, rate=0.5):
    clock = ManualClock()
    return clock, TokenBucket(capacity, rate, clock)


def drain(bucket):
    while bucket.allow():
        pass


class PollingDoesNotStarveRefill(unittest.TestCase):
    def test_status_polls_between_requests(self):
        clock, bucket = make()
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        for _ in range(8):
            clock.advance(0.25)
            bucket.available()
        self.assertTrue(bucket.allow())

    def test_rejected_retries_get_in_on_time(self):
        clock, bucket = make()
        drain(bucket)
        first = None
        for step in range(1, 41):
            clock.advance(0.25)
            if bucket.allow():
                first = step
                break
        self.assertEqual(first, 8)

    def test_faster_rate_gets_in_on_time(self):
        clock, bucket = make(capacity=3, rate=1.5)
        drain(bucket)
        first = None
        for step in range(1, 41):
            clock.advance(0.25)
            if bucket.allow():
                first = step
                break
        self.assertEqual(first, 3)

    def test_steady_client_under_the_limit_is_never_refused(self):
        clock, bucket = make()
        for i in range(20):
            clock.advance(1.0)
            bucket.available()
            clock.advance(1.0)
            self.assertTrue(bucket.allow(), f"request {i}")

    def test_throughput_of_a_client_that_retries_constantly(self):
        clock, bucket = make()
        allowed = 0
        for _ in range(160):  # 40 seconds in quarter-second steps
            clock.advance(0.25)
            if bucket.allow():
                allowed += 1
        # 2 from the full bucket plus one token every 2 seconds
        self.assertIn(allowed, (21, 22))

    def test_partial_progress_is_remembered(self):
        clock, bucket = make()
        drain(bucket)
        clock.advance(1.0)
        self.assertFalse(bucket.allow())
        clock.advance(1.0)
        self.assertTrue(bucket.allow())

    def test_available_counts_whole_tokens(self):
        clock, bucket = make()
        drain(bucket)
        clock.advance(1.0)
        self.assertEqual(int(bucket.available()), 0)
        clock.advance(1.0)
        self.assertEqual(int(bucket.available()), 1)
        clock.advance(100.0)
        self.assertEqual(int(bucket.available()), 2)


class IdleTimeWhileFullIsNotBanked(unittest.TestCase):
    def test_refill_clock_starts_when_a_token_is_taken(self):
        clock, bucket = make()
        clock.advance(1.75)  # bucket has been full the whole time
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        clock.advance(0.25)  # t = 2.0: only a quarter second since the bucket emptied
        self.assertFalse(bucket.allow())
        clock.advance(1.5)  # t = 3.5
        self.assertFalse(bucket.allow())
        clock.advance(0.25)  # t = 3.75: two seconds since it emptied
        self.assertTrue(bucket.allow())

    def test_a_look_at_a_full_bucket_changes_nothing(self):
        clock, bucket = make()
        clock.advance(1.75)
        self.assertEqual(int(bucket.available()), 2)
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        clock.advance(0.25)
        self.assertFalse(bucket.allow())

    def test_never_more_than_capacity_after_long_idle(self):
        clock, bucket = make()
        clock.advance(1000)
        self.assertEqual(int(bucket.available()), 2)
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())


class OtherBehaviourUnchanged(unittest.TestCase):
    def test_burst_then_refused(self):
        _, bucket = make()
        self.assertTrue(bucket.allow())
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())

    def test_asking_for_several_tokens(self):
        clock, bucket = make(capacity=5, rate=1.0)
        self.assertTrue(bucket.allow(3))
        self.assertFalse(bucket.allow(3))
        clock.advance(1.0)
        self.assertTrue(bucket.allow(3))

    def test_refused_request_takes_nothing(self):
        clock, bucket = make(capacity=5, rate=1.0)
        self.assertTrue(bucket.allow(4))
        self.assertFalse(bucket.allow(4))
        self.assertTrue(bucket.allow(1))


class ThroughTheLimiter(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.limiter = Limiter(Policy(limit=2, window=4.0), self.clock)

    def test_status_polling_does_not_block_the_client(self):
        self.assertTrue(self.limiter.allow("alice"))
        self.assertTrue(self.limiter.allow("alice"))
        for _ in range(8):
            self.clock.advance(0.25)
            self.limiter.status("alice")
        self.assertTrue(self.limiter.allow("alice"))

    def test_other_clients_are_not_affected(self):
        self.limiter.allow("alice")
        self.limiter.allow("alice")
        self.clock.advance(0.25)
        self.assertEqual(self.limiter.status("bob"), {"remaining": 2, "limit": 2})
        self.assertTrue(self.limiter.allow("bob"))

    def test_guard_lets_a_retrying_client_back_in(self):
        for _ in range(2):
            self.assertEqual(guard(self.limiter, "carol", lambda: "ok")[0], 200)
        first_ok = None
        for step in range(1, 41):
            self.clock.advance(0.25)
            status, body = guard(self.limiter, "carol", lambda: "ok")
            if status == 200:
                first_ok = step
                self.assertEqual(body, "ok")
                break
            self.assertEqual((status, body), (429, "slow down"))
        self.assertEqual(first_ok, 8)


if __name__ == "__main__":
    unittest.main()
