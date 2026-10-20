`order.py` and `inventory.py` mix validation, stock management, and order
recording together inside `place_order`. Refactor `order.py` so each
concern is a separate top-level function:

- `validate_order(qty, customer_email)` — returns an error string
  (`"invalid_email"` or `"invalid_quantity"`) or `None`.
- `reserve_stock(item, qty)` — returns `"out_of_stock"` or `None`, and
  reduces stock via `inventory.reduce_stock` on success.
- `record_order(item, qty, customer_email)` — appends to the order log
  and returns the order dict.

`place_order(item, qty, customer_email)` should call these three in
sequence and `order_count()` should remain as-is. Keep behavior
identical for: invalid email (no '@'), non-positive quantity,
insufficient stock, and the success path.
