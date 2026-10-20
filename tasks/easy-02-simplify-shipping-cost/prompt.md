`shipping_cost` in `shipping.py` works correctly but is deeply nested and
hard to follow. Refactor it to be flatter and clearer (e.g. a small rate
table instead of nested if/else) without changing its behavior for any
input. `country` is only ever `'US'` or `'INTL'`, and both `is_express`
values must be handled.
