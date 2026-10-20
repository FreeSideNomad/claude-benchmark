from cache import TTLCache


def make_clock(times):
    it = iter(times)
    return lambda: next(it)


def test_returns_value_before_expiry():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 5]))
    cache.set("a", "hello")
    assert cache.get("a") == "hello"


def test_returns_none_after_expiry():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 11]))
    cache.set("a", "hello")
    assert cache.get("a") is None


def test_expired_entry_is_dropped():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 11, 20, 20]))
    cache.set("a", "hello")
    assert cache.get("a") is None
    cache.set("a", "world")
    assert cache.get("a") == "world"
