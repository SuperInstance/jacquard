import hashlib
import json
import os

from jacquard import Log, Sequencer, envelope_hash, fold, make_envelope
from jacquard import senses as _senses_module
from jacquard.canonical import SPEC_SEAL
from jacquard.senses import compute_sense

VECTORS = os.path.join(os.path.dirname(__file__), "..",
                       "spec", "vectors", "vectors.json")


def load():
    with open(VECTORS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_spec_seal():
    assert load()["spec_seal"] == SPEC_SEAL
    assert SPEC_SEAL == hashlib.sha256(b"jacquard-spec/0.6").hexdigest()


def test_entry_zero_hash_from_handwritten_canonical_string():
    # Independent of jacquard.canonical: the literal below is the
    # canonical form of entry 0 written out by hand.
    literal = (
        '{"body":{"name":"gpu-foreign","producer":"operator","value":false},'
        '"kind":"sense","prev":"' + "0" * 64 + '","seq":0,'
        '"spec":"jacquard/0.6"}')
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


def test_senses_vectors():
    # The probe modules register their own candidate senses into
    # SENSES at runtime (the registry hazard); re-register the
    # production functions first, as the other production tests do.
    _senses_module.SENSES["contention"] = _senses_module._contention
    _senses_module.SENSES["authority"] = _senses_module._authority
    section = load()["senses"]
    assert set(section) == {"contention", "authority"}
    assert len(section["contention"]) >= 3
    assert len(section["authority"]) >= 2
    for sense, cases in section.items():
        for case in cases:
            entries = case["entries"]
            state = fold(entries)
            reading = compute_sense(
                "%s:%s" % (sense, case["subject"]), entries, state)
            assert reading == case["expect"]
            assert reading["as_of_seq"] == entries[-1]["seq"]
    # The recorded expectations, pinned in words (not just
    # re-derived): the shapes the brief names.
    contention = [c["expect"]["value"] for c in section["contention"]]
    assert contention[0]["count"] == 0
    assert contention[0]["unclassified"] == []
    assert contention[1]["count"] == 2
    assert contention[1]["max_rank"] == 3
    assert contention[1]["top_id"] == "bk-2"
    assert contention[2]["count"] == 0
    assert contention[2]["unclassified"] == ["zcod"]
    authority = [c["expect"]["value"] for c in section["authority"]]
    assert authority[0] == {"ceiling": None, "grants": 0}
    assert authority[1] == {"ceiling": 2, "grants": 2}


def test_anchor_vector():
    # Spec 15: the vectors carry one checkpoint over the vector
    # entry chain, signed under the published test key whose seed
    # they record. Verified here with the `cryptography` package
    # directly (not through jacquard.anchor), so the vector pins
    # the format independently of the anchor tooling.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    from jacquard.canonical import canonical, hash_of

    section = load()["anchor"]
    seed = bytes.fromhex(section["test_seed"])
    key = Ed25519PrivateKey.from_private_bytes(seed)
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat)
    pub_hex = key.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex()
    envelope = section["envelope"]
    assert envelope["pubkey"] == pub_hex
    body = envelope["body"]
    entries = load()["entries"]
    assert body == {"format": "jacquard/anchor/1",
                    "log_id": entries[0]["hash"],
                    "label": "golden-vectors",
                    "checkpoint_seq": 0,
                    "log_length": 4,
                    "head_hash": entries[3]["hash"],
                    "spec": "jacquard/0.6",
                    "prev_checkpoint": None}
    assert section["checkpoint_hash"] == hash_of(body)
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
    pub.verify(bytes.fromhex(envelope["sig"]), canonical(body))
    with __import__("pytest").raises(InvalidSignature):
        pub.verify(bytes.fromhex(envelope["sig"]),
                   canonical(dict(body, log_length=3)))


def test_anchor_registry_vectors():
    # Spec 15.3 (erratum 2): the registry grammar. Schedule cases
    # run the registry -> schedule derivation; refusal cases pin
    # the failure text; auth cases run the section 15.5 procedure
    # over the anchor vector's own history under a registry
    # schedule. The first schedule cases carry the live witness
    # registry verbatim: the gpu-queue log's null window is the
    # defect this grammar fixes.
    import pytest
    from jacquard.anchor import (AnchorError, schedule_from_registry,
                                 verify_entries)
    section = load()["anchor_registry"]
    for case in section["schedule_cases"]:
        if "expect_schedule" in case:
            got = schedule_from_registry(case["registry"],
                                         case["log_id"])
            assert [list(pair) for pair in got] == \
                case["expect_schedule"], case["name"]
        else:
            with pytest.raises(AnchorError) as excinfo:
                schedule_from_registry(case["registry"],
                                       case["log_id"])
            assert case["expect_refusal"] in str(excinfo.value), \
                case["name"]
    # The vectors carry entry projections (seq/kind/body/hash);
    # rebuild the full entries the section 15.5 procedure needs.
    # The reconstruction is self-validating: verify_entries
    # recomputes every hash, so a wrong prev or spec fails the
    # chain check instead of passing silently.
    entries = []
    prev = "0" * 64
    for projection in load()["entries"]:
        entries.append({"seq": projection["seq"],
                        "kind": projection["kind"],
                        "body": projection["body"],
                        "prev": prev, "spec": "jacquard/0.6",
                        "hash": projection["hash"]})
        prev = projection["hash"]
    envelope = load()["anchor"]["envelope"]
    for case in section["auth_cases"]:
        schedule = schedule_from_registry(case["registry"],
                                          case["log_id"])
        result = verify_entries(entries, [envelope], schedule[0][1],
                                schedule=schedule)
        assert result["outcome"] == case["expect_outcome"], \
            case["name"]
        if "expect_detail" in case:
            assert result["failure"]["detail"] == \
                case["expect_detail"], case["name"]
        else:
            assert result["anchored_length"] == 4, case["name"]
            assert result["unanchored_tail"] == 0, case["name"]
