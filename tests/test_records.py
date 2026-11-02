from jacquard import Sequencer, make_envelope
from jacquard.records import output_use_ratio, outputs_and_uses, records


def test_records_and_output_use():
    seq = Sequencer()
    seq.submit(make_envelope(
        "maker", "proposal",
        {"requests": [
            {"verb": "write", "args": ["asset/1", {"n": 1}],
             "outputs": ["asset-1"]},
            {"verb": "write", "args": ["asset/2", {"n": 2}],
             "outputs": ["asset-2"]}]},
        ["write"], "m1"))
    seq.submit(make_envelope(
        "reader", "proposal",
        {"requests": [{"verb": "write", "args": ["scene", ["asset-1"]]}],
         "uses": ["asset-1"]},
        ["write"], "r1"))
    view = records(seq.log.entries)
    assert view["maker"]["work"]["executions"] == 1
    assert view["maker"]["work"]["allowed"] == 1
    assert outputs_and_uses(seq.log.entries, "maker") == (2, 1)
    assert output_use_ratio(seq.log.entries, "maker") == 0.5
    assert output_use_ratio(seq.log.entries, "reader") is None
