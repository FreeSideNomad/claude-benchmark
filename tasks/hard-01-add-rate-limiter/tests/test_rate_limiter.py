from rate_limiter import TokenBucketRateLimiter


def make_clock(times):
    it = iter(times)
    return lambda: next(it)


def test_allows_up_to_capacity_then_denies():
    limiter = TokenBucketRateLimiter(capacity=2, refill_rate_per_second=1, clock=make_clock([0, 0, 0, 0]))
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False


def test_refills_over_time():
    limiter = TokenBucketRateLimiter(capacity=1, refill_rate_per_second=1, clock=make_clock([0, 0, 0, 2]))
    assert limiter.allow() is True
    assert limiter.allow() is False
    assert limiter.allow() is True


def test_refill_is_capped_at_capacity():
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_second=1, clock=make_clock([0, 0, 100, 100]))
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is True
