"""Token bucket.

The bucket holds up to `capacity` tokens and gains `rate` tokens per second.
A request takes one token, or is refused when the bucket is empty.
"""


class TokenBucket:
    def __init__(self, capacity, rate, clock):
        self.capacity = capacity
        self.rate = rate
        self.clock = clock
        self.tokens = float(capacity)  # tokens currently in the bucket (may be fractional)
        self.last = clock.now()  # when we last looked at the clock

    def _refill(self):
        now = self.clock.now()
        elapsed = now - self.last
        self.last = now
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

    def available(self):
        """Whole tokens that could be taken right now."""
        self._refill()
        return int(self.tokens)

    def allow(self, amount=1):
        """Take `amount` tokens if they are there. Returns True when taken."""
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False
