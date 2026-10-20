import time

from lookup import annotate_with_prices


def test_matches_known_items():
    orders = [{"item": "a"}, {"item": "b"}]
    prices = [{"item": "a", "price": 10}, {"item": "b", "price": 20}]
    assert annotate_with_prices(orders, prices) == [
        {"item": "a", "price": 10},
        {"item": "b", "price": 20},
    ]


def test_unmatched_item_gets_none():
    orders = [{"item": "z"}]
    prices = [{"item": "a", "price": 10}]
    assert annotate_with_prices(orders, prices) == [{"item": "z", "price": None}]


def test_does_not_mutate_inputs():
    orders = [{"item": "a"}]
    prices = [{"item": "a", "price": 10}]
    orders_copy = [dict(o) for o in orders]
    prices_copy = [dict(p) for p in prices]

    annotate_with_prices(orders, prices)

    assert orders == orders_copy
    assert prices == prices_copy


def test_runs_fast_on_large_input():
    prices = [{"item": f"item-{i}", "price": i} for i in range(25000)]
    orders = [{"item": f"item-{i % 25000}"} for i in range(25000)]
    start = time.perf_counter()
    result = annotate_with_prices(orders, prices)
    elapsed = time.perf_counter() - start

    assert len(result) == 25000
    assert result[0]["price"] == 0
    assert elapsed < 2.0
