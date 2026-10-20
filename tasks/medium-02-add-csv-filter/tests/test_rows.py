from rows import filter_rows


def test_filters_matching_rows():
    rows = [{"name": "a", "age": 10}, {"name": "b", "age": 20}, {"name": "c", "age": 30}]
    result = filter_rows(rows, lambda r: r["age"] >= 20)
    assert result == [{"name": "b", "age": 20}, {"name": "c", "age": 30}]


def test_preserves_order_and_does_not_mutate_input():
    rows = [{"n": 1}, {"n": 2}, {"n": 3}]
    original = list(rows)
    result = filter_rows(rows, lambda r: r["n"] != 2)
    assert result == [{"n": 1}, {"n": 3}]
    assert rows == original


def test_empty_result_when_nothing_matches():
    rows = [{"n": 1}]
    assert filter_rows(rows, lambda r: r["n"] > 100) == []
