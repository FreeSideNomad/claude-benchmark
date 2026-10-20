from formatter import shout
from greeter import greet


def test_shout_uppercases_and_adds_exclamation():
    assert shout("hi") == "HI!"


def test_greet_uses_shout():
    assert greet("ana") == "HELLO, ANA!"
