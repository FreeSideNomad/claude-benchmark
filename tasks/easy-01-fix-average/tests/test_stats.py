import pytest

from stats import average


def test_average_of_integers():
    assert average([1, 2, 3, 4]) == 2.5


def test_average_of_single_value():
    assert average([7]) == 7.0


def test_average_raises_on_empty():
    with pytest.raises(ValueError):
        average([])
