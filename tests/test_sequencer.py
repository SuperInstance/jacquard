from jacquard import Sequencer, make_envelope, records


def proposal(seq, producer, body, declared, idem):
    return seq.submit(make_envelope(producer, "proposal", body,
                                    declared, idem))


def test_idempotent_resubmission():
    seq = Sequencer()
    defn = {"name": "double",
            "signature": {"ins": ["int"], "outs": ["int"]},
            "body": ["dup", "add"],
            "examples": [{"args": [2], "expect": [4]}]}
    env = make_envelope("operator", "definition", defn, [], "same-1")
    first = seq.submit(env)
    count = len(seq.log.entries)
    second = seq.submit(env)
    # SPEC 3.1 (0.7): a duplicate returns the recorded verdict,
    # marked as a replay; before 0.7 the copy was unmarked.
    assert second == dict(first, duplicate=True)
    assert len(seq.log.entries) == count


def test_bad_seal_refused_without_log_entry():
    seq = Sequencer()
    env = make_envelope("a", "proposal", {"requests": []}, [], "s1")
    env["spec_seal"] = "0" * 64
    verdict = seq.submit(env)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"
    assert len(seq.log.entries) == 0


def test_underdeclared_proposal_records_fault():
    seq = Sequencer()
    verdict = proposal(seq, "agent-a",
                         {"requests": [{"verb": "dispatch",
                                        "args": [{"job": "x"}]}]},
                         ["reads"], "u1")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"
    view = records(seq.log.entries)
    assert view["agent-a"]["work"]["faults"] == 1
    assert view["agent-a"]["work"]["executions"] == 0


def test_decision_queue_and_release():
    seq = Sequencer()
    verdict = proposal(seq, "agent-a",
                         {"requests": [{"verb": "send",
                                        "args": ["ops", "hello"]}]},
                         ["send"], "q1")
    assert verdict["status"] == "decided"
    assert verdict["outcome"] == "queue"
    pid = verdict["proposal_id"]
    assert pid in seq.state.decision_queue
    released = seq.release_queued(pid, "operator")
    assert released["outcome"] == "allow"
    assert pid not in seq.state.decision_queue
    view = records(seq.log.entries)
    assert view["agent-a"]["work"]["executions"] == 1


def test_operator_bypasses_queue_for_protected_effects():
    seq = Sequencer()
    verdict = proposal(seq, "operator",
                         {"requests": [{"verb": "send",
                                        "args": ["ops", "hi"]}]},
                         ["send"], "op1")
    assert verdict["outcome"] == "allow"


def test_suspended_producer_denied():
    seq = Sequencer(standing={"bad": {"status": "suspended"}})
    verdict = proposal(seq, "bad",
                         {"requests": [{"verb": "write",
                                        "args": ["u", 1]}]},
                         ["write"], "sp1")
    assert verdict["outcome"] == "deny"
    assert "u" not in seq.state.units


def test_proposal_applies_atomically():
    seq = Sequencer()
    bad_definition = {"name": "broken",
                      "signature": {"ins": [], "outs": []},
                      "body": [], "examples": [{"args": [], "expect": [1]}]}
    before = len(seq.log.entries)
    verdict = proposal(
        seq, "agent-a",
        {"requests": [{"verb": "write", "args": ["u", 1]},
                      {"verb": "define", "args": [bad_definition]}]},
        ["write", "define"], "at1")
    assert verdict["status"] == "REFUSED"
    # Atomicity: neither request applied — no definition entry,
    # no execution, the unit unwritten. Since spec 0.7 (3.1) the
    # refusal itself is recorded as one fault decision, exactly
    # as the underdeclared refusal is; before 0.7 this path
    # appended nothing.
    assert len(seq.log.entries) == before + 1
    entry = seq.log.entries[-1]
    assert entry["kind"] == "decision"
    assert entry["body"]["outcome"] == "refused"
    assert entry["body"]["fault"] == verdict["refusal"]
    assert "broken" not in seq.state.dictionary
    assert "u" not in seq.state.units


def test_sense_then_word_reads_it():
    seq = Sequencer()
    seq.submit_sense("lamp", "on", "operator")
    defn = {"name": "lamp-on?",
            "signature": {"ins": [], "outs": ["bool"]},
            "body": [{"lit": "lamp"}, "sense", {"lit": "on"}, "eq"],
            "examples": [{"args": [], "state": {"senses": {"lamp": "on"}},
                          "expect": [True]}]}
    verdict = seq.submit(make_envelope("operator", "definition", defn,
                                       [], "sn1"))
    assert verdict["status"] == "accepted"
    stack, _ = seq.evaluate_word("lamp-on?", "operator")
    assert stack == [True]
