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


import ast
import inspect

import shipping


def _max_if_depth(node, current_depth=0):
    max_depth = current_depth if isinstance(node, ast.If) else 0
    if isinstance(node, ast.If):
        for stmt in node.body:
            max_depth = max(max_depth, _max_if_depth(stmt, current_depth + 1))
        for stmt in node.orelse:
            if isinstance(stmt, ast.If) and stmt.col_offset == node.col_offset:
                max_depth = max(max_depth, _max_if_depth(stmt, current_depth))
            else:
                max_depth = max(max_depth, _max_if_depth(stmt, current_depth + 1))
    else:
        for child in ast.iter_child_nodes(node):
            max_depth = max(max_depth, _max_if_depth(child, current_depth))
    return max_depth


def test_shipping_cost_is_not_deeply_nested():
    tree = ast.parse(inspect.getsource(shipping.shipping_cost))
    depth = _max_if_depth(tree.body[0])
    assert depth <= 1, f"shipping_cost has {depth} levels of nested if — expected a flatter implementation"
