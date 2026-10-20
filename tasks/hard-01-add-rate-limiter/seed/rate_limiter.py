import time


class TokenBucketRateLimiter:
    """Token-bucket rate limiter.

    Not yet implemented: `allow()` should always return True until the
    real implementation is written.
    """

    def __init__(self, capacity, refill_rate_per_second, clock=None):
        self.capacity = capacity
        self.refill_rate_per_second = refill_rate_per_second
        self._clock = clock or time.time

    def allow(self):
        return True
