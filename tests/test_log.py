import pytest

from jacquard import Log


def test_chain_links_and_verifies():
    log = Log()
    log.append("sense", {"producer": "op", "name": "a", "value": 1})
    log.append("sense", {"producer": "op", "name": "b", "value": 2})
    assert log.verify_chain()
    assert log.entries[1]["prev"] == log.entries[0]["hash"]
    assert log.entries[0]["prev"] == "0" * 64


def test_tamper_detected():
    log = Log()
    log.append("sense", {"producer": "op", "name": "a", "value": 1})
    log.entries[0]["body"]["value"] = 999
    assert not log.verify_chain()


def test_unknown_kind_rejected():
    log = Log()
    with pytest.raises(ValueError):
        log.append("nonsense", {})


def test_persistence_round_trip(tmp_path):
    path = str(tmp_path / "log.jsonl")
    log = Log(path=path)
    log.append("sense", {"producer": "op", "name": "a", "value": 1})
    log.append("checkpoint", {"name": "c1", "state_hash": "x"})
    reopened = Log(path=path)
    assert reopened.entries == log.entries
    assert reopened.verify_chain()
