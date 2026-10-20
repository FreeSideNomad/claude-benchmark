`unique_preserve_order(items)` in `dedupe.py` returns the items in their
original order with duplicates removed, but is accidentally O(n^2) for
large inputs because of the `item not in result` list scan. Rewrite it to
run in O(n) time (a set to track items already seen), keeping identical
behavior: same order, first occurrence kept, all items are hashable.
