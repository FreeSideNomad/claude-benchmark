def shipping_cost(weight_kg, country, is_express):
    if country == "US":
        if is_express:
            if weight_kg <= 1:
                return 15
            else:
                return 15 + (weight_kg - 1) * 4
        else:
            if weight_kg <= 1:
                return 6
            else:
                return 6 + (weight_kg - 1) * 2
    else:
        if is_express:
            if weight_kg <= 1:
                return 30
            else:
                return 30 + (weight_kg - 1) * 8
        else:
            if weight_kg <= 1:
                return 12
            else:
                return 12 + (weight_kg - 1) * 5
