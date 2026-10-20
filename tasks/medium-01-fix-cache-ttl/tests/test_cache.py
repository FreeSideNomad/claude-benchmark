from cache import TTLCache


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


def test_returns_value_before_expiry():
    clock = FakeClock(0)
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("a", "hello")
    clock.now = 5
    assert cache.get("a") == "hello"


def test_returns_none_after_expiry():
    clock = FakeClock(0)
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("a", "hello")
    clock.now = 11
    assert cache.get("a") is None


def test_expired_entry_is_dropped():
    clock = FakeClock(0)
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("a", "hello")
    clock.now = 11
    assert cache.get("a") is None
    clock.now = 20
    cache.set("a", "world")
    assert cache.get("a") == "world"
