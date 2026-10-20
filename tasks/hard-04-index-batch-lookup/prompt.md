`annotate_with_prices` in `lookup.py` is correct but slow for large
inputs — it does a full linear scan over `price_list` for every single
order (O(orders x price_list)). Rewrite it to build a single
`item -> price` lookup dict once, then use it for O(1) lookups per
order. Keep behavior identical: unmatched items get `'price': None`, the
input lists must not be mutated, and output order matches `orders`.
