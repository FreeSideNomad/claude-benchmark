from pipeline import validate


def test_passes_short_numeric_value():
    assert validate("123") == []


def test_flags_non_numeric_value():
    assert validate("abc") == ["not_numeric"]


def test_flags_too_long_value():
    assert validate("1" * 25) == ["too_long"]


def test_flags_both_errors_at_once():
    assert validate("a" * 25) == ["too_long", "not_numeric"]
