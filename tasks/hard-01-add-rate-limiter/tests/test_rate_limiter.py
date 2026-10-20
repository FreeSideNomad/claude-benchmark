from rate_limiter import TokenBucketRateLimiter


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


def test_allows_up_to_capacity_then_denies():
    clock = FakeClock(0)
    limiter = TokenBucketRateLimiter(capacity=2, refill_rate_per_second=1, clock=clock)
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False


def test_refills_over_time():
    clock = FakeClock(0)
    limiter = TokenBucketRateLimiter(capacity=1, refill_rate_per_second=1, clock=clock)
    assert limiter.allow() is True
    assert limiter.allow() is False
    clock.now = 2
    assert limiter.allow() is True


def test_refill_is_capped_at_capacity():
    clock = FakeClock(0)
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_second=1, clock=clock)
    assert limiter.allow() is True
    assert limiter.allow() is True
    clock.now = 100
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False
