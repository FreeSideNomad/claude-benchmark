from inventory import has_stock, reduce_stock

_ORDERS = []


def place_order(item, qty, customer_email):
    if "@" not in customer_email:
        return {"ok": False, "reason": "invalid_email"}
    if qty <= 0:
        return {"ok": False, "reason": "invalid_quantity"}
    if not has_stock(item, qty):
        return {"ok": False, "reason": "out_of_stock"}
    reduce_stock(item, qty)
    order = {"item": item, "qty": qty, "customer_email": customer_email}
    _ORDERS.append(order)
    return {"ok": True, "order": order}


def order_count():
    return len(_ORDERS)
