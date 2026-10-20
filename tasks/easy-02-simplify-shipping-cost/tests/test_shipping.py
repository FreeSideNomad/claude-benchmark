from shipping import shipping_cost


def test_us_standard_base_rate():
    assert shipping_cost(1, "US", False) == 6


def test_us_standard_extra_weight():
    assert shipping_cost(3, "US", False) == 10


def test_us_express():
    assert shipping_cost(2, "US", True) == 19


def test_intl_standard():
    assert shipping_cost(1, "INTL", False) == 12


def test_intl_express_extra_weight():
    assert shipping_cost(4, "INTL", True) == 54
