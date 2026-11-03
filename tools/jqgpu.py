"""jqgpu — the Jacquard gpu-queue bridge CLI (Phase 8, slice 22).

Every verb is ONE fresh process over the live kernel log: it
rebuilds kernel state from the log, acts, and exits. Nothing
here (or anywhere in the bridge) is a daemon, and nothing is
installed on the Thor — dispatch and poll reach the Thor's
gpuq over its existing SSH door, per invocation.

    python3 tools/jqgpu.py --log LOG init \
        --window '{"target_jobs": 7, "opens": "...", "closes": "..."}'
    python3 tools/jqgpu.py --log LOG submit --producer P \
        --name NAME --cmd CMD [--output ARTIFACT] [--uses A,B]
    python3 tools/jqgpu.py --log LOG dispatch
    python3 tools/jqgpu.py --log LOG poll
    python3 tools/jqgpu.py --log LOG senses
    python3 tools/jqgpu.py --log LOG counts

Held jobs are released or rejected with the existing operator
CLI (tools/jq.py queue / decide), hash-bound as always; the
next `dispatch` invocation then — and only then — adds them
to gpuq.

The log's canonical home is stated in its policy record; the
transport prefix is JACQUARD_GPU_THOR_CMD (see
adapters/gpu_queue.py for the verified route and why).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters"))

from gpu_queue import open_bridge  # noqa: E402


def main():
    parser = argparse.ArgumentParser(prog="jqgpu")
    parser.add_argument("--log", required=True,
                        help="live kernel log (JSONL)")
    parser.add_argument("--journal", default=None,
                        help="bridge journal (default: <log>.gpu-journal.jsonl)")
    parser.add_argument("--log-label", default=None,
                        help="canonical log path stated in the policy "
                             "record (default: --log)")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--window", required=True,
                      help="JSON window statement for the policy record")
    submit = sub.add_parser("submit")
    submit.add_argument("--producer", required=True)
    submit.add_argument("--name", required=True)
    submit.add_argument("--cmd", required=True)
    submit.add_argument("--output", default=None)
    submit.add_argument("--uses", default=None,
                        help="comma-separated artifact ids this job uses")
    sub.add_parser("dispatch")
    sub.add_parser("poll")
    sub.add_parser("senses")
    sub.add_parser("counts")
    args = parser.parse_args()

    bridge = open_bridge(args.log, journal_path=args.journal)
    label = args.log_label or args.log

    if args.command == "init":
        entry = bridge.ensure_kernel(label, json.loads(args.window))
        print(json.dumps(
            {"policy_record": "already present" if entry is None
             else "published",
             "entries": len(bridge.seq.log.entries),
             "log_id": (bridge.seq.log.entries[0]["hash"]
                        if bridge.seq.log.entries else None)},
            indent=1))
        return 0
    if args.command == "submit":
        uses = [u.strip() for u in args.uses.split(",") if u.strip()] \
            if args.uses else []
        verdict = bridge.submit_job(args.producer, args.name,
                                    args.cmd, output=args.output,
                                    uses=uses)
        print(json.dumps(verdict, indent=1))
        return 0
    if args.command == "dispatch":
        records = bridge.dispatch_pending()
        print(json.dumps(
            {"dispatched": [{"action_id": r["action_id"],
                             "gpuq_job_id": r.get("gpuq_job_id"),
                             "name": r.get("name"),
                             "adopted": bool(r.get("adopted"))}
                            for r in records]}, indent=1))
        return 0
    if args.command == "poll":
        print(json.dumps({"outcomes": bridge.poll_outcomes()},
                         indent=1))
        return 0
    if args.command == "senses":
        published = bridge.publish_live_senses()
        print(json.dumps(
            {"published": [e["body"]["name"] for e in published],
             "downstream_use": bridge.downstream_use()}, indent=1))
        return 0
    if args.command == "counts":
        print(json.dumps(bridge.counts(), indent=1))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
