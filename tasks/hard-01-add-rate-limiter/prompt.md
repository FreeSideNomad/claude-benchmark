Implement a token-bucket rate limiter in `rate_limiter.py`.
`TokenBucketRateLimiter(capacity, refill_rate_per_second, clock=None)`
starts with a full bucket of `capacity` tokens. Each call to `allow()`
should: refill the bucket based on elapsed time since the last refill
(`refill_rate_per_second` tokens per second, capped at `capacity`), then,
if at least 1 token is available, consume one token and return `True`;
otherwise return `False` without consuming a token. `clock` is an
injectable zero-argument callable returning the current time (for
testability) — default to `time.time`. The constructor should call
`clock()` once to initialize the last-refill timestamp.
