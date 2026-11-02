"""jq — the Jacquard operator CLI (Phase 3, slice 10).

The decision queue is the operator's surface: approvals are
batched, and every approval is HASH-BOUND — you approve the
item you were shown, identified by the hash of the decision
entry that queued it. If the item changed since presentation,
the hash will not match and the decision fails, item untouched.

    python3 tools/jq.py --log kernel.jsonl seed-demo
    python3 tools/jq.py --log kernel.jsonl queue
    python3 tools/jq.py --log kernel.jsonl decide approve <id> --hash <h>
    python3 tools/jq.py --log kernel.jsonl decide deny --batch decisions.txt
    python3 tools/jq.py --log kernel.jsonl execute
    python3 tools/jq.py --log kernel.jsonl replay <id>
    python3 tools/jq.py --log kernel.jsonl status

`decisions.txt` lines: `<proposal_id> <binding_hash>` (decided
with the command's action), or `<approve|deny> <proposal_id>
<binding_hash>` for a mixed batch in one file.
Exit code is 0 when everything asked for succeeded, 1 when any
item failed (the rest of a batch still processes).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters"))

from jacquard import Log, Sequencer, install_lifecycles, make_envelope  # noqa: E402


def open_kernel(path):
    return Sequencer(Log(path))


def binding_hash(seq, proposal_id):
    """The hash of the decision entry that queued this item —
    the value an approval binds to."""
    for entry in seq.log.entries:
        body = entry["body"]
        if entry["kind"] == "decision" \
                and body.get("proposal_id") == proposal_id \
                and body.get("outcome") == "queued":
            return entry["hash"]
    return None


def cmd_queue(seq, _args):
    order = seq.decision_order()
    if not order:
        print("decision queue: empty")
        return 0
    print("decision queue: %d item(s), presentation order" % len(order))
    for proposal_id in order:
        body = seq.state.decision_queue[proposal_id]
        print("- %s" % proposal_id)
        print("    producer %s · class %s · effects %s"
              % (body["producer"], body.get("class", "work"),
                 ", ".join(body.get("effects", []))))
        print("    binding %s" % binding_hash(seq, proposal_id))
    return 0


def decide_one(seq, action, proposal_id, expect_hash):
    current = binding_hash(seq, proposal_id)
    if proposal_id not in seq.state.decision_queue:
        print("FAIL %s: not in the decision queue" % proposal_id)
        return 1
    if current != expect_hash:
        print("FAIL %s: binding mismatch (item changed since "
              "presentation; current binding %s)" % (proposal_id, current))
        return 1
    if action == "approve":
        seq.release_queued(proposal_id, "operator")
        print("approved %s" % proposal_id)
    else:
        seq.reject_queued(proposal_id, "operator")
        print("denied %s" % proposal_id)
    return 0


def cmd_decide(seq, args):
    failures = 0
    if args.batch:
        with open(args.batch, encoding="utf-8") as fh:
            lines = [line.strip() for line in fh
                     if line.strip() and not line.startswith("#")]
        for line in lines:
            parts = line.split()
            if len(parts) == 3 and parts[0] in ("approve", "deny"):
                action, proposal_id, expect_hash = parts
            elif len(parts) == 2:
                action = args.action
                proposal_id, expect_hash = parts
            else:
                print("FAIL %s: malformed batch line (want "
                      "'<id> <binding>' or '<approve|deny> <id> "
                      "<binding>')" % line)
                failures += 1
                continue
            failures += decide_one(seq, action, proposal_id, expect_hash)
    else:
        failures += decide_one(seq, args.action, args.proposal_id,
                               args.hash)
    return 1 if failures else 0


def cmd_execute(seq, args):
    from executor import SandboxedExecutor
    journal = args.log + ".executor.jsonl"
    executor = SandboxedExecutor(seq, journal, sandbox=args.sandbox)
    records = executor.run_once()
    if not records:
        print("execute: no dispatched actions pending")
        return 0
    for record in records:
        print("executed %s: exit %s via %s -> state %s"
              % (record["action_id"], record["exit"], record["sandbox"],
                 seq.machine_instance_state(record["action_id"])))
    return 0


def cmd_replay(seq, args):
    proposal_id = args.proposal_id
    lines = ["replay of proposal %s" % proposal_id]
    found = False
    for entry in seq.log.entries:
        body = entry["body"]
        kind = entry["kind"]
        if kind == "decision" and body.get("proposal_id") == proposal_id:
            found = True
            extra = ""
            if body.get("decided_by"):
                extra = " (decided_by %s; policy would: %s)" \
                    % (body["decided_by"], body.get("policy_outcome"))
            lines.append("  seq %d decision: %s by %s%s — reasons: %s"
                         % (entry["seq"], body["outcome"],
                            body["policy_version"], extra,
                            ", ".join(body.get("reasons", [])) or "none"))
        elif kind == "execution" and body.get("proposal_id") == proposal_id:
            found = True
            verbs = [item["verb"] for item in body.get("applied", [])]
            lines.append("  seq %d execution: applied %s"
                         % (entry["seq"], ", ".join(verbs) or "nothing"))
        elif kind == "transition" and (
                body.get("instance") == proposal_id
                or body.get("instance") == "approval:" + proposal_id
                or body.get("instance", "").startswith(proposal_id + "/")):
            found = True
            lines.append("  seq %d transition: %s %s -%s-> %s (%s)"
                         % (entry["seq"], body["machine"],
                            body["from"], body["event"], body["to"],
                            body["outcome"]))
    if not found:
        print("replay: no entries for proposal %s" % proposal_id)
        return 1
    state = seq.machine_instance_state(proposal_id)
    if state:
        lines.append("  final proposal state: %s" % state)
    print("\n".join(lines))
    return 0


def cmd_status(seq, _args):
    print("entries %d · state %s" % (len(seq.log.entries),
                                     seq.state.state_hash()))
    print("decision queue: %d item(s)" % len(seq.state.decision_queue))
    print("units %d · definitions %d · machines %d · rules %d"
          % (len(seq.state.units), len(seq.state.dictionary),
             len(seq.state.machines), len(seq.state.rules)))
    return 0


def cmd_seed_demo(seq, args):
    if seq.log.entries:
        print("FAIL seed-demo: log %s already has %d entries; "
              "seed-demo needs a fresh log (delete it or pick a new "
              "path). Nothing was changed." % (args.log,
                                                len(seq.log.entries)))
        return 1
    install_lifecycles(seq)
    queued_a = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "deploy done"]}]},
        ["notify"], "demo-a"))
    queued_b = seq.submit(make_envelope(
        "bob", "proposal",
        {"requests": [{"verb": "spend", "args": ["compute", 10]}]},
        ["spend"], "demo-b"))
    dispatched = seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "dispatch", "args": [{
            "cmd": ["python3", "-c", "print('drill-ran')"],
            "compensate": ["python3", "-c", "print('drill-undone')"]}]}]},
        ["dispatch"], "demo-c"))
    print(json.dumps({
        "queued": {queued_a["proposal_id"]: binding_hash(
            seq, queued_a["proposal_id"]),
                   queued_b["proposal_id"]: binding_hash(
                       seq, queued_b["proposal_id"])},
        "dispatched": dispatched["proposal_id"],
        "action": dispatched["proposal_id"] + "/action-0"}, indent=1))
    return 0


def main():
    parser = argparse.ArgumentParser(prog="jq")
    parser.add_argument("--log", required=True, help="kernel log (JSONL)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-demo")
    sub.add_parser("queue")
    sub.add_parser("status")
    decide = sub.add_parser("decide")
    decide.add_argument("action", choices=["approve", "deny"])
    decide.add_argument("proposal_id", nargs="?")
    decide.add_argument("--hash")
    decide.add_argument("--batch")
    execute = sub.add_parser("execute")
    execute.add_argument("--sandbox", default="subprocess",
                         choices=["subprocess", "bwrap", "auto"])
    replay = sub.add_parser("replay")
    replay.add_argument("proposal_id")
    args = parser.parse_args()
    seq = open_kernel(args.log)
    handler = {"seed-demo": cmd_seed_demo, "queue": cmd_queue,
               "status": cmd_status, "decide": cmd_decide,
               "execute": cmd_execute, "replay": cmd_replay}[args.command]
    return handler(seq, args)


if __name__ == "__main__":
    raise SystemExit(main())
