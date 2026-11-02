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


# Rendering and hash-bound deciding live in jacquard.present,
# shared with the network service (slice 13) so the CLI and the
# service present the queue, replay and status byte-for-byte
# identically. The names are re-exported here for compatibility.
from jacquard.present import binding_hash  # noqa: E402,F401


def cmd_queue(seq, _args):
    from jacquard.present import render_queue
    print(render_queue(seq))
    return 0


def cmd_decide(seq, args):
    from jacquard.present import decide_one
    failures = 0

    def run_one(action, proposal_id, expect_hash):
        ok, line = decide_one(seq, action, proposal_id, expect_hash)
        print(line)
        return 0 if ok else 1

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
            failures += run_one(action, proposal_id, expect_hash)
    else:
        failures += run_one(args.action, args.proposal_id, args.hash)
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
    from jacquard.present import render_replay
    found, text = render_replay(seq, args.proposal_id)
    print(text)
    return 0 if found else 1


def cmd_status(seq, _args):
    from jacquard.present import render_status
    print(render_status(seq))
    return 0


def cmd_seed_demo(seq, args):
    from jacquard.present import seed_demo
    ok, payload = seed_demo(seq, args.log)
    if not ok:
        print(payload)
        return 1
    print(json.dumps(payload, indent=1))
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
