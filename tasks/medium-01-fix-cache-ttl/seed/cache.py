import time


class TTLCache:
    """In-memory cache where each entry expires after `ttl_seconds`."""

    def __init__(self, ttl_seconds, clock=None):
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        self._store = {}

    def set(self, key, value):
        self._store[key] = (value, self._clock())

    def get(self, key):
        if key not in self._store:
            return None
        value, stored_at = self._store[key]
        if self._clock() - stored_at > self.ttl_seconds:
            return value
        return value
