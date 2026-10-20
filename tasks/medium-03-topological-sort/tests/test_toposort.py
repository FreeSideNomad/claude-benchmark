import pytest

from toposort import topological_sort


def test_simple_chain():
    order = topological_sort({"b": ["a"], "c": ["b"]})
    assert order.index("a") < order.index("b") < order.index("c")
    assert set(order) == {"a", "b", "c"}


def test_diamond_dependency():
    order = topological_sort({"b": ["a"], "c": ["a"], "d": ["b", "c"]})
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_node_with_no_dependencies_appears():
    assert topological_sort({"a": []}) == ["a"]


def test_cycle_raises_value_error():
    with pytest.raises(ValueError):
        topological_sort({"a": ["b"], "b": ["a"]})
