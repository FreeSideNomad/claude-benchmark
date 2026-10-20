import inventory
import order


def test_successful_order_reduces_stock_and_is_recorded():
    before = order.order_count()
    result = order.place_order("widget", 2, "a@example.com")
    assert result == {"ok": True, "order": {"item": "widget", "qty": 2, "customer_email": "a@example.com"}}
    assert inventory.has_stock("widget", 4) is False
    assert order.order_count() == before + 1


def test_rejects_invalid_email():
    before = order.order_count()
    result = order.place_order("gizmo", 1, "not-an-email")
    assert result == {"ok": False, "reason": "invalid_email"}
    assert order.order_count() == before


def test_rejects_non_positive_quantity():
    before = order.order_count()
    result = order.place_order("gizmo", 0, "a@example.com")
    assert result == {"ok": False, "reason": "invalid_quantity"}
    assert order.order_count() == before


def test_rejects_when_out_of_stock():
    before = order.order_count()
    result = order.place_order("gadget", 1, "a@example.com")
    assert result == {"ok": False, "reason": "out_of_stock"}
    assert order.order_count() == before
