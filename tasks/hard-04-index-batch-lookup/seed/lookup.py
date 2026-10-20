def annotate_with_prices(orders, price_list):
    """orders: list of dicts with an 'item' key.
    price_list: list of dicts with 'item' and 'price' keys.
    Returns a new list of orders, each with a 'price' key added
    (None if the item isn't found in price_list).
    """
    result = []
    for order in orders:
        price = None
        for entry in price_list:
            if entry["item"] == order["item"]:
                price = entry["price"]
                break
        result.append({**order, "price": price})
    return result
