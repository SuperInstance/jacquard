"""jqbook — the booking-board operator CLI (Phase 11, slice 30).

Puts the fleet schedule board's booking decisions through the
booking profile (src/jacquard/booking.py) via the board
adapter (adapters/booking_board.py). The board stays the
board — git commits are still the bookings — but every
booking this tool applies was first decided by the kernel,
and the board commit is journalled back into the kernel log.

    python3 tools/jqbook.py --log L --inbox I init --boxes thor,proart,...
    python3 tools/jqbook.py --log L --inbox I propose --box orin ...
    python3 tools/jqbook.py --log L queue
    python3 tools/jqbook.py --log L --inbox I release --id <booking>
    python3 tools/jqbook.py --log L --inbox I complete --id <booking>
    python3 tools/jqbook.py --log L counts

Times are UTC, "YYYY-MM-DD HH:MM". Durations: "3h", "2h30m",
"45m". One writer at a time: each invocation rebuilds the
sequencer from the log.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.booking_board import (  # noqa: E402
    apply_row, fmt_min, git, journal, mark_row, normalise_seat,
    open_flow, parse_board, parse_duration_min, rewrite_status,
    row_is_done, slug, to_epoch_min, write_record)
from jacquard import install_booking  # noqa: E402
from jacquard.booking import publish_contention  # noqa: E402

BOX_FILES = {"thor": "thor", "proart": "proart",
             "orin": "jetson-orin", "oracle": "oracle"}


def now_min():
    return int(datetime.now(timezone.utc).timestamp() // 60)


def find_booking(seq, booking_id):
    for unit, value in sorted(seq.state.units.items()):
        if unit.startswith("booking/") and isinstance(value, dict) \
                and value.get("id") == booking_id:
            return unit, value
    return None, None


def find_queued(seq, booking_id):
    """(proposal_id, record) for a queued booking proposal.
    The record rides in the proposal's write request — a held
    booking's write has not executed, so the record is NOT in
    committed state yet."""
    for pid, queued in seq.state.decision_queue.items():
        for req in queued.get("requests", []):
            if req.get("verb") == "write" \
                    and req["args"][0].startswith("booking/") \
                    and isinstance(req["args"][1], dict) \
                    and req["args"][1].get("id") == booking_id:
                return pid, req["args"][1]
    return None, None


def cmd_init(args):
    if os.path.exists(args.log) and os.path.getsize(args.log) > 0:
        raise SystemExit("log exists and is non-empty: %s" % args.log)
    seq, flow = open_flow(args.log)
    install_booking(seq)
    boxes = args.boxes.split(",")
    head = git(args.inbox, "rev-parse", "--short", "HEAD").stdout.strip()
    rows = []
    for box in boxes:
        for row in parse_board(args.inbox, BOX_FILES[box]):
            rows.append((box, row))
    flow.grant("jacquard-build", 10)
    producers = ["jacquard-build"]
    for box, row in rows:
        if row_is_done(row):
            continue
        cb = None
        try:
            cb = to_epoch_min(row["checkby"])
        except (ValueError, TypeError):
            cb = None
        if cb is not None and cb < now_min():
            continue
        if row["lane"] not in producers:
            producers.append(row["lane"])
    for producer in producers:
        flow.grant(producer, 10 if producer == "jacquard-build" else 5)
    imported, skipped = [], []
    for box, row in rows:
        cb = None
        try:
            cb = to_epoch_min(row["checkby"])
        except (ValueError, TypeError):
            cb = None
        if row_is_done(row) or (cb is not None and cb < now_min()):
            skipped.append({"lane": row["lane"], "box": box,
                            "from": row["from"],
                            "why": "done" if row_is_done(row)
                                   else "check-by passed"})
            continue
        start = to_epoch_min(row["from"])
        dur = parse_duration_min(row["planned"])
        assumption = None
        if dur is None:
            end = cb if cb is not None else start + 120
            assumption = ("planned %r unparseable; end = %s"
                          % (row["planned"],
                             "check-by" if cb is not None
                             else "start+120m"))
        else:
            end = start + dur
        asserted = 10 if row["lane"] == "jacquard-build" else 5
        record = {"id": slug("%s-%s-%s-%s" % (
                        row["lane"], box,
                        normalise_seat(row["seat"]), row["from"])),
                  "box": box, "producer": row["lane"],
                  "seat": normalise_seat(row["seat"]),
                  "start": start, "end": end, "checkby": cb,
                  "status": "active", "rank": asserted,
                  "asserted_rank": asserted}
        write_record(seq, record)
        imported.append({"id": record["id"], "box": box,
                         "producer": row["lane"],
                         "seat_board": row["seat"],
                         "seat": record["seat"],
                         "start": row["from"],
                         "end": fmt_min(end),
                         "end_assumption": assumption,
                         "raw": row["raw"]})
    journal(seq, "board-import",
            {"source": "agent-inbox@%s" % head, "imported": imported,
             "skipped": skipped})
    print(json.dumps({"initialised": args.log, "entries": len(seq.log.entries),
                      "imported": len(imported),
                      "skipped": len(skipped)}, indent=1))
    return 0


def cmd_propose(args):
    seq, flow = open_flow(args.log)
    start = to_epoch_min(args.from_)
    dur = parse_duration_min(args.planned)
    if dur is None:
        raise SystemExit("unparseable --planned: %r" % args.planned)
    booking = {"id": slug("%s-%s-%s-%s" % (
                        args.lane, args.box,
                        normalise_seat(args.seat), args.from_)),
               "box": args.box, "producer": args.lane,
               "seat": normalise_seat(args.seat),
               "start": start, "end": start + dur,
               "checkby": to_epoch_min(args.checkby)
               if args.checkby else None,
               "rank": args.rank}
    if args.grant:
        flow.grant(args.lane, args.rank)
    report = flow.submit_live(booking)
    row_text = "| %s | %s | %s | %s | %s | %s (jq:%s) |" % (
        args.lane, args.seat, args.from_, args.planned,
        args.checkby or "—", args.what, booking["id"])
    journal(seq, "board-row:" + booking["id"],
            {"row": row_text, "box": args.box,
             "machine_state": report["machine_state"]})
    out = {"booking_id": booking["id"], "box": args.box,
           "seat_kernel": booking["seat"], "seat_board": args.seat,
           "machine_state": report["machine_state"],
           "effective_rank": report["effective_rank"],
           "asserted_rank": report["asserted_rank"],
           "preempted": report["preempted"],
           "proposal_id": report["proposal_id"],
           "committed": report["release"] is not None}
    if report["release"] is not None:
        disposed = flow.dispose(report["record"])
        out["disposed"] = disposed
        commit = apply_row(args.inbox, BOX_FILES[args.box],
                           row_text, booking["id"])
        journal(seq, "board-apply:" + booking["id"],
                {"commit": commit, "box": args.box})
        out["board_commit"] = commit
    print(json.dumps(out, indent=1))
    return 0


def cmd_release(args):
    seq, flow = open_flow(args.log)
    pid, record = find_queued(seq, args.id)
    if pid is None:
        raise SystemExit("no queued proposal for %s" % args.id)
    release = seq.release_queued(pid, "operator")
    instance = "booking:%s" % args.id
    state = None
    if instance in seq.state.machine_instances:
        name = publish_contention(seq, record)
        try:
            seq.step_machine(instance, "commit",
                             {**record, "sense_name": name,
                              "rank": record["rank"]})
        except Exception as exc:  # guard refused: still held
            print("step commit: %s" % exc, file=sys.stderr)
        state = seq.machine_instance_state(instance)
    disposed = flow.dispose(record)
    row = None
    for entry in reversed(seq.log.entries):
        if entry["kind"] == "sense" and entry["body"].get(
                "name") == "board-row:" + args.id:
            row = entry["body"]["value"]["row"]
            break
    out = {"booking_id": args.id, "released": release is not None,
           "machine_state": state, "disposed": disposed}
    if row is not None:
        commit = apply_row(args.inbox, BOX_FILES[record["box"]],
                           row, args.id)
        journal(seq, "board-apply:" + args.id,
                {"commit": commit, "box": record["box"],
                 "via": "operator-release"})
        out["board_commit"] = commit
    print(json.dumps(out, indent=1))
    return 0


def cmd_reject(args):
    seq, _flow = open_flow(args.log)
    pid, _record = find_queued(seq, args.id)
    if pid is None:
        raise SystemExit("no queued proposal for %s" % args.id)
    seq.reject_queued(pid, "operator", reason=args.reason)
    instance = "booking:%s" % args.id
    state = None
    if instance in seq.state.machine_instances:
        seq.step_machine(instance, "cancel", {})
        state = seq.machine_instance_state(instance)
    print(json.dumps({"booking_id": args.id, "rejected": True,
                      "machine_state": state}, indent=1))
    return 0


def cmd_close(args, event, status, note_word):
    seq, _flow = open_flow(args.log)
    unit, record = find_booking(seq, args.id)
    if record is None:
        raise SystemExit("no booking %s" % args.id)
    instance = "booking:%s" % args.id
    state = None
    if instance in seq.state.machine_instances:
        seq.step_machine(instance, event, {})
        state = seq.machine_instance_state(instance)
    rewrite_status(seq, record, status)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Bookings this tool applied carry a (jq:<id>) marker and
    # get their board row marked. IMPORTED bookings are other
    # lanes' rows: their owners mark them; the kernel-side
    # close is journal-only for those.
    ours = any(e["kind"] == "sense" and e["body"].get("name")
               == "board-row:" + args.id for e in seq.log.entries)
    commit = None
    if ours:
        commit = mark_row(args.inbox, BOX_FILES[record["box"]],
                          args.id,
                          "— %s %s (jacquard)" % (note_word, stamp))
    journal(seq, "board-close:" + args.id,
            {"commit": commit, "box": record["box"], "status": status,
             "board_row_marked": ours})
    print(json.dumps({"booking_id": args.id, "status": status,
                      "machine_state": state,
                      "board_commit": commit,
                      "board_row_marked": ours}, indent=1))
    return 0


def cmd_queue(args):
    seq, _flow = open_flow(args.log)
    items = []
    for pid, queued in seq.state.decision_queue.items():
        for req in queued.get("requests", []):
            if req.get("verb") == "write" \
                    and req["args"][0].startswith("booking/") \
                    and isinstance(req["args"][1], dict) \
                    and "start" in req["args"][1]:
                rec = req["args"][1]
                items.append({"proposal_id": pid,
                              "booking_id": rec.get("id"),
                              "box": rec.get("box"),
                              "producer": rec.get("producer"),
                              "seat": rec.get("seat"),
                              "start": fmt_min(rec["start"]),
                              "end": fmt_min(rec["end"]),
                              "rank": rec.get("rank")})
    print(json.dumps({"queued_bookings": items}, indent=1))
    return 0


def cmd_counts(args):
    seq, _flow = open_flow(args.log)
    bookings = {}
    by_status = {}
    for unit, value in sorted(seq.state.units.items()):
        if unit.startswith("booking/") and isinstance(value, dict):
            bookings[unit] = value.get("status")
            by_status[value.get("status")] = \
                by_status.get(value.get("status"), 0) + 1
    senses = [e["body"].get("name") for e in seq.log.entries
              if e["kind"] == "sense"]
    print(json.dumps({"entries": len(seq.log.entries),
                      "bookings_by_status": by_status,
                      "bookings": bookings,
                      "board_events": [s for s in senses
                                       if s and s.startswith(
                                           "board-")]}, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="jqbook")
    ap.add_argument("--log", required=True)
    ap.add_argument("--inbox")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--boxes", default="thor,proart,orin,oracle")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("propose")
    p.add_argument("--box", required=True)
    p.add_argument("--seat", required=True)
    p.add_argument("--lane", default="jacquard-build")
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--planned", required=True)
    p.add_argument("--checkby")
    p.add_argument("--what", required=True)
    p.add_argument("--rank", type=int, default=10)
    p.add_argument("--grant", action="store_true",
                   help="grant the producer a ceiling = rank first")
    p.set_defaults(fn=cmd_propose)
    p = sub.add_parser("release")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_release)
    p = sub.add_parser("reject")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", default="operator decision")
    p.set_defaults(fn=cmd_reject)
    p = sub.add_parser("complete")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=lambda a: cmd_close(a, "complete", "done",
                                          "DONE"))
    p = sub.add_parser("cancel")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=lambda a: cmd_close(a, "cancel", "cancelled",
                                          "CANCELLED"))
    p = sub.add_parser("queue")
    p.set_defaults(fn=cmd_queue)
    p = sub.add_parser("counts")
    p.set_defaults(fn=cmd_counts)
    args = ap.parse_args()
    if args.cmd in ("init", "propose", "release", "complete",
                    "cancel") and not args.inbox:
        raise SystemExit("--inbox is required for %s" % args.cmd)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
