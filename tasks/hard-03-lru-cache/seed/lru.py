class LRUCache:
    """Fixed-capacity cache. Not yet implemented.

    `get(key)` returns the value or None if absent, and marks it as
    most-recently-used. `put(key, value)` inserts/updates a value,
    evicting the least-recently-used entry if capacity is exceeded.
    """

    def __init__(self, capacity):
        self.capacity = capacity

    def get(self, key):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError
