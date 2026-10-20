`order.py` and `inventory.py` mix validation, stock management, and order
recording together inside `place_order`. Refactor so each concern is a
clearly separated function (e.g. a validation step, a stock-check/reduce
step, a record step), keeping `place_order(item, qty, customer_email)`
and `order_count()` in `order.py` as the only functions other code calls,
with unchanged behavior for: invalid email (no '@'), non-positive
quantity, insufficient stock, and the success path.
