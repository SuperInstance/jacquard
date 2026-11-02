"""Learning-bridge driver for the Phase 6 live proof run.

Kernel-level rehearsal rounds on the shared proof log: repeats
of the two learned shapes submitted through the same
coding-agent profile functions the ZCode adapter uses, released
by the operator, carrying the mined rules up the ladder. Kept
with the run's raw inputs as evidence of exactly what was done.
"""
import sys

sys.path.insert(0, "/home/ubuntu/jacquard/src")

from jacquard import Log, Sequencer, Learner  # noqa: E402
from jacquard.coding_agent import (  # noqa: E402
    install_coding_agent, submit_tool_action)
from jacquard.learner import rule_stage  # noqa: E402

LOG = "/home/ubuntu/jacquard-phase6-proof/kernel.jsonl"
BASE = "/home/ubuntu/jacquard-phase6-proof/bridge"


def decision_of(seq, pid):
    for e in reversed(seq.log.entries):
        if e["kind"] == "decision" and e["body"].get("proposal_id") == pid:
            return e["body"]
    raise KeyError(pid)


def main():
    seq = Sequencer(log=Log(LOG))
    install_coding_agent(seq)
    learner = Learner()
    learner.install(seq)
    cands = {c["shape"]["class"]: c for c in learner.mine(seq.log.entries)
             if c["origin"] == "operator" and c["predicted_outcome"] == "allow"}
    write_c = cands["agent-write"]
    shell_c = cands["agent-shell"]
    for cand in (write_c, shell_c):
        print("register", cand["rule_id"], learner.register(seq, cand))
    counter = [0]

    def rehearse(round_no):
        for i in range(3):
            counter[0] += 1
            v = submit_tool_action(
                seq, "zcode-agent", "agent-write",
                {"unit": "agent-file:%s/r%d/mod%d.py" % (BASE, round_no, i),
                 "value": "X = %d\n" % i}, "bridge-w-%d" % counter[0])
            assert decision_of(seq, v["proposal_id"])["outcome"] == "queued"
            counter[0] += 1
            v = submit_tool_action(
                seq, "zcode-agent", "agent-shell",
                {"cmd": ["sh", "-c", "python3 -m pytest -q"]},
                "bridge-s-%d" % counter[0])
            assert decision_of(seq, v["proposal_id"])["outcome"] == "queued"
        for pid in list(seq.state.decision_queue):
            seq.release_queued(pid, "operator")
        print("round", round_no, "released; stages:",
              rule_stage(seq.state, write_c["rule_id"]),
              rule_stage(seq.state, shell_c["rule_id"]))

    rehearse(1)
    for cand in (write_c, shell_c):
        print("promote", cand["rule_id"], learner.promote(seq, cand["rule_id"]))
    rehearse(2)
    for cand in (write_c, shell_c):
        print("activate", cand["rule_id"],
              learner.activate(seq, cand["rule_id"]))
    print("final stages:", rule_stage(seq.state, write_c["rule_id"]),
          rule_stage(seq.state, shell_c["rule_id"]))


if __name__ == "__main__":
    main()
