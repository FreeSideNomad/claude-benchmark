import time

from dedupe import unique_preserve_order


def test_preserves_first_occurrence_order():
    assert unique_preserve_order([3, 1, 3, 2, 1, 4]) == [3, 1, 2, 4]


def test_empty_list():
    assert unique_preserve_order([]) == []


def test_runs_fast_on_large_input():
    items = list(range(40000)) + list(range(20000))
    start = time.perf_counter()
    result = unique_preserve_order(items)
    elapsed = time.perf_counter() - start

    assert result == list(range(40000))
    assert elapsed < 2.0
