import pytest

from jacquard.canonical import canonical, hash_of


def test_float_rejected():
    with pytest.raises(TypeError):
        canonical({"x": 1.5})


def test_nested_float_rejected():
    with pytest.raises(TypeError):
        canonical({"x": [1, {"y": 0.1}]})


def test_sorted_keys_no_whitespace():
    assert canonical({"b": 1, "a": [True, None, "s"]}) == \
        b'{"a":[true,null,"s"],"b":1}'


def test_bool_is_not_int():
    assert canonical(True) == b"true"
    assert canonical(1) == b"1"


def test_hash_stable_and_sensitive():
    assert hash_of({"a": 1}) == hash_of({"a": 1})
    assert hash_of({"a": 1}) != hash_of({"a": 2})


def test_non_string_key_rejected():
    with pytest.raises(TypeError):
        canonical({1: "x"})
