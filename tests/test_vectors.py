import hashlib
import json
import os

from jacquard import Log, Sequencer, envelope_hash, fold, make_envelope
from jacquard.canonical import SPEC_SEAL

VECTORS = os.path.join(os.path.dirname(__file__), "..",
                       "spec", "vectors", "vectors.json")


def load():
    with open(VECTORS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_spec_seal():
    assert load()["spec_seal"] == SPEC_SEAL
    assert SPEC_SEAL == hashlib.sha256(b"jacquard-spec/0.2").hexdigest()


def test_entry_zero_hash_from_handwritten_canonical_string():
    # Independent of jacquard.canonical: the literal below is the
    # canonical form of entry 0 written out by hand.
    literal = (
        '{"body":{"name":"gpu-foreign","producer":"operator","value":false},'
        '"kind":"sense","prev":"' + "0" * 64 + '","seq":0,'
        '"spec":"jacquard/0.2"}')
    expect = hashlib.sha256(literal.encode("utf-8")).hexdigest()
    assert load()["entries"][0]["hash"] == expect


def test_entry_chain_recomputed():
    log = Log()
    for recorded in load()["entries"]:
        entry = log.append(recorded["kind"], recorded["body"])
        assert entry["hash"] == recorded["hash"]
    assert log.verify_chain()


def test_envelope_vector():
    recorded = load()["envelope"]
    env = recorded["envelope"]
    assert envelope_hash(env) == recorded["id"]
    rebuilt = make_envelope(env["producer"], env["kind"], env["body"],
                            env["declared_effects"], env["id"])
    assert rebuilt == env


def test_definition_vectors():
    seq = Sequencer()
    for item in load()["definitions"]:
        verdict = seq.submit(make_envelope(
            "operator", "definition", item["definition"],
            item["definition"].get("declared_effects", []),
            "vec-" + item["definition"]["name"]))
        assert verdict["status"] == "accepted"
        stored = seq.state.dictionary[item["definition"]["name"]][-1]
        assert stored["definition"] == item["stored"]


def test_state_vector():
    recorded = load()["state"]
    # Replay the generator's scenario end to end.
    vectors = load()
    seq = Sequencer()
    for item in vectors["definitions"]:
        seq.submit(make_envelope(
            "operator", "definition", item["definition"],
            item["definition"].get("declared_effects", []),
            "sv-" + item["definition"]["name"]))
    env = vectors["envelope"]["envelope"]
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": ["answer", 42],
                       "outputs": ["o-42"]}]},
        ["write"], "sv-p1"))
    assert seq.state.units == recorded["units"]
    assert seq.state.state_hash() == recorded["state_hash"]
    assert fold(seq.log.entries).state_hash() == recorded["state_hash"]
    assert env["body"]["requests"][0]["args"] == ["answer", 42]
