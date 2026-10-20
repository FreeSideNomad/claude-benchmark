_STOCK = {"widget": 5, "gadget": 0, "gizmo": 10}


def has_stock(item, qty):
    return _STOCK.get(item, 0) >= qty


def reduce_stock(item, qty):
    _STOCK[item] = _STOCK.get(item, 0) - qty
