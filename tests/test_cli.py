"""The operator drill (SPEC: slice 10 acceptance): proposals in,
queue presented, batch decided with hash-bound approvals,
actions executed via the executor, replay matching the log.

Drives tools/jq.py as a subprocess, the way an operator (or a
cold agent following the README) would.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402

JQ = os.path.join(os.path.dirname(__file__), "..", "tools", "jq.py")


def run_cli(log, *argv, expect=0):
    proc = subprocess.run([sys.executable, JQ, "--log", str(log)] + list(argv),
                          capture_output=True, text=True)
    assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
    return proc.stdout


def test_operator_drill(tmp_path):
    log = tmp_path / "kernel.jsonl"
    seed = json.loads(run_cli(log, "seed-demo"))
    (id_a, hash_a), (id_b, hash_b) = sorted(seed["queued"].items())
    action_id = seed["action"]

    # the queue presents both items with their bindings
    out = run_cli(log, "queue")
    assert id_a in out and hash_a in out and id_b in out

    # hash-bound: a wrong binding fails and changes nothing
    out = run_cli(log, "decide", "approve", id_a, "--hash", "0" * 64,
                  expect=1)
    assert "binding mismatch" in out
    assert id_a in run_cli(log, "queue")

    # batch: approve A, and the same batch file shape denies B
    batch = tmp_path / "decisions.txt"
    batch.write_text("%s %s\n" % (id_a, hash_a), encoding="utf-8")
    out = run_cli(log, "decide", "approve", "--batch", str(batch))
    assert "approved %s" % id_a in out
    out = run_cli(log, "decide", "deny", id_b, "--hash", hash_b)
    assert "denied %s" % id_b in out
    assert "empty" in run_cli(log, "queue")

    # the approved proposal executed (notify applied); B never did
    seq = Sequencer(Log(str(log)))
    executions = [e["body"] for e in seq.log.entries
                  if e["kind"] == "execution"]
    assert any(e["proposal_id"] == id_a for e in executions)
    assert not any(e["proposal_id"] == id_b for e in executions)
    assert seq.machine_instance_state(id_a) == "closed"
    assert seq.machine_instance_state(id_b) == "refused"

    # actions execute through the executor; the drill command ran
    out = run_cli(log, "execute")
    assert "exit 0" in out and action_id in out
    seq = Sequencer(Log(str(log)))
    assert seq.machine_instance_state(action_id) == "confirmed"

    # replay matches the log: outcome + lifecycle, end to end
    out = run_cli(log, "replay", id_a)
    assert "decision: queued" in out
    assert "decision: allow" in out
    assert "final proposal state: closed" in out
    out = run_cli(log, "replay", seed["dispatched"])
    assert "action" in out and "confirmed" in out


def test_replay_of_unknown_proposal_fails_cleanly(tmp_path):
    log = tmp_path / "kernel.jsonl"
    run_cli(log, "seed-demo")
    out = run_cli(log, "replay", "no-such-id", expect=1)
    assert "no entries" in out


def test_seed_demo_refuses_nonempty_log(tmp_path):
    from pathlib import Path
    log = tmp_path / "k.jsonl"
    run_cli(log, "seed-demo")
    before = Path(log).read_text()
    out = run_cli(log, "seed-demo", expect=1)
    assert "fresh log" in out
    assert Path(log).read_text() == before  # nothing mutated


def test_queue_annotates_waiting_item(tmp_path):
    """A wait-conditioned item is listed as waiting (guard +
    deadline), and hash-bound decisions still work on an
    ordinary item in the same queue."""
    from jacquard import install_lifecycles, make_envelope
    log = tmp_path / "k.jsonl"
    seq = Sequencer(Log(str(log)))
    install_lifecycles(seq)
    guard = {
        "name": "x-landed",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["drop", {"lit": "artifact/x"}, "dup", "keys",
                 "swap", "contains",
                 {"if": [{"lit": "artifact/x"}, "get",
                         {"lit": "status"}, "getf",
                         {"lit": "landed"}, "eq"],
                  "else": [{"lit": False}]}],
        "examples": [
            {"args": [{"proposal_id": "e"}],
             "state": {"units": {"artifact/x": {"status": "landed"}}},
             "expect": [True]},
            {"args": [{"proposal_id": "e"}],
             "state": {"units": {}}, "expect": [False]}],
    }
    verdict = seq.submit(make_envelope(
        "operator", "definition", guard, [], "def-x-landed"))
    assert verdict["status"] == "accepted"
    deadline = len(seq.log.entries) + 1000
    waiting = seq.submit(make_envelope(
        "agent-a", "proposal",
        {"requests": [{"verb": "write",
                       "args": ["job/w1", {"job": "w1"}]}],
         "wait": {"guard": "x-landed", "deadline_seq": deadline}},
        ["write"], "cli-waiter"))
    assert waiting["outcome"] == "queue"
    ordinary = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "hi"]}]},
        ["notify"], "cli-ordinary"))
    assert ordinary["outcome"] == "queue"

    out = run_cli(log, "queue")
    assert waiting["proposal_id"] in out
    assert "waiting: x-landed (deadline seq %d)" % deadline in out

    # decide still works, hash-bound, on the ordinary item
    seq2 = Sequencer(Log(str(log)))
    binding = None
    for entry in seq2.log.entries:
        if entry["kind"] == "decision" \
                and entry["body"].get("proposal_id") == \
                ordinary["proposal_id"] \
                and entry["body"].get("outcome") == "queued":
            binding = entry["hash"]
    out = run_cli(log, "decide", "approve", ordinary["proposal_id"],
                  "--hash", binding)
    assert "approved %s" % ordinary["proposal_id"] in out
    # the waiter is untouched by the ordinary item's decision
    assert waiting["proposal_id"] in run_cli(log, "queue")


def test_mixed_batch(tmp_path):
    log = tmp_path / "k.jsonl"
    seed = json.loads(run_cli(log, "seed-demo"))
    (approve_id, approve_hash), (deny_id, deny_hash) = \
        seed["queued"].items()
    batch = tmp_path / "decisions.txt"
    batch.write_text("approve %s %s\ndeny %s %s\n"
                     % (approve_id, approve_hash, deny_id, deny_hash))
    out = run_cli(log, "decide", "approve", "--batch", str(batch))
    assert "approved %s" % approve_id in out
    assert "denied %s" % deny_id in out
    assert "empty" in run_cli(log, "queue")
