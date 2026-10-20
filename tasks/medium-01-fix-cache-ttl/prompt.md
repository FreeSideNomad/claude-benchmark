`TTLCache.get` in `cache.py` should return `None` (and drop the entry)
once `ttl_seconds` has elapsed since the matching `set`, and otherwise
return the stored value. It currently ignores expiry entirely. Fix it,
keeping the existing constructor signature (`ttl_seconds`, optional
`clock` callable) so callers can inject a fake clock in tests.
