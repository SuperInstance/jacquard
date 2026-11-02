"""jqnotify — batched decision-queue notifications (Phase 5, slice 14).

The decision queue is decided in the operator CLI / service; this
tool is only a tap on the shoulder. It folds the kernel log,
computes the CURRENT decision-queue snapshot, and — when the
queue waits past a configurable age or count — fires ONE batched
summary. It proposes nothing and approves nothing.

    python3 tools/jqnotify.py --log kernel.jsonl \
        [--max-age-s N] [--max-count N] [--deliver] [--verbose]
        [--check] [--state-file PATH] [--inbox-dir PATH]

Age, honestly defined. The kernel log carries NO wall-clock
timestamps: its clock is the log itself (spec section 5: primitive
P2 `now` is the entry count, P6 `age` is staleness in entries).
A queued item's age is therefore defined in log entries:

    age(item) = latest substantive seq - seq of the decision
                entry that queued the item

where "substantive" excludes this tool's own notification records
(so a notification never ages the queue it reports on). Every
number in the summary is a pure function of the log prefix, so a
verifier re-folds the log and recomputes them exactly. The
summary always states its age mode ("log-entries"); there is no
wall-clock mode, because there is no wall-clock data in the log
to verify one against. The flag spelling --max-age-s is kept
from the slice brief; --max-age is the same flag. Its unit is
log entries, stated here, in --help, and in every summary.

Thresholds trip when a value is AT OR BEYOND the limit:
oldest_age >= max_age, or queue depth >= max_count. Either
threshold may be set alone. CLI flags win over the environment
(JQNOTIFY_MAX_AGE_S / JQNOTIFY_MAX_COUNT / JQNOTIFY_STATE_FILE /
JQNOTIFY_INBOX_DIR). Defaults when nothing is configured:
max age 100 entries, max count 5.

Repeat suppression. A small state file (default:
<log>.jqnotify-state.json) records the last notified snapshot
hash, the oldest item and its age, and the latest substantive
seq at firing time. A later run re-fires only when the queue is
still past a threshold AND the snapshot materially changed:
the snapshot hash differs (items arrived, left, or changed), or
the same oldest item has grown strictly older on substantive
log growth. A poll loop over an unchanged queue never re-fires.

Channels, when a notification fires:
  (a) a record appended to the kernel log itself (see below);
  (b) with --deliver, a Markdown drop committed to the fleet's
      agent-inbox repo, folder verdicts/, numbered sequentially
      in that folder's existing format. Without --deliver nothing
      leaves the machine; tests never deliver to the real inbox.

The log record's shape, and why. The record is a `checkpoint`
entry (body name "queue-notification") carrying the snapshot
hash, the exact summary numbers, the thresholds that tripped,
and the folded state hash from before the append. A NEW entry
kind was rejected: the kind list is closed in spec section 2
(twelve kinds), Log.append enforces it, and the TypeScript
conformance checker folds fixtures by kind — a thirteenth kind
is a spec change, not a notification. `checkpoint` is the
existing kind whose fold is defined as NO fold effect (spec
section 2.1: "no fold effect"; state.py has no checkpoint
branch), so the record keeps fold determinism and the
nine-section state shape exactly, and the state hash after the
append equals the state hash before it. The body carries fields
beyond the minimal checkpoint shape {"name", "state_hash"} —
that is an annotation payload on a fold-transparent kind, and
it is flagged as such in the builders log rather than hidden.
Verification: re-fold the log up to (not including) a
notification entry, recompute the snapshot with this module,
and compare — `jqnotify --verify` does exactly that for every
notification record in a log.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, fold, hash_of  # noqa: E402

NOTIFY_NAME = "queue-notification"
AGE_MODE = "log-entries"
DEFAULT_MAX_AGE = 100
DEFAULT_MAX_COUNT = 5


# ------------------------------------------------------------ snapshot

def is_notification(entry):
    return entry["kind"] == "checkpoint" \
        and entry["body"].get("name") == NOTIFY_NAME


def queued_seqs(entries):
    """proposal_id -> seq of the decision entry that queued it,
    for items still in the queue. Mirrors the fold's decision
    branch order (queued sets; releases/rejects/expires remove).
    """
    seqs = {}
    for entry in entries:
        if entry["kind"] != "decision":
            continue
        body = entry["body"]
        if body.get("outcome") == "queued":
            seqs[body["proposal_id"]] = entry["seq"]
        elif body.get("releases"):
            seqs.pop(body["releases"], None)
        elif body.get("rejects"):
            seqs.pop(body["rejects"], None)
        elif body.get("expires"):
            seqs.pop(body["expires"], None)
    return seqs


def latest_substantive_seq(entries):
    """Seq of the newest entry that is not one of this tool's own
    notification records; -1 when there is none."""
    seq = -1
    for entry in entries:
        if not is_notification(entry):
            seq = entry["seq"]
    return seq


def compute_snapshot(entries):
    """The current decision-queue snapshot: a pure function of
    the log entries given. Returns (summary, items) where items
    is the per-item detail used only by --verbose and the
    verifier; the summary is the batched shape that ships."""
    state = fold(entries)
    queue = state.decision_queue
    seqs = queued_seqs(entries)
    latest = latest_substantive_seq(entries)
    by_effect = {}
    by_class = {}
    items = []
    for proposal_id in sorted(queue):
        body = queue[proposal_id]
        effects = sorted(body.get("effects", []))
        cls = body.get("class", "work")
        for effect in effects:
            by_effect[effect] = by_effect.get(effect, 0) + 1
        by_class[cls] = by_class.get(cls, 0) + 1
        items.append({
            "proposal_id": proposal_id,
            "producer": body.get("producer"),
            "class": cls,
            "effects": effects,
            "queued_seq": seqs.get(proposal_id, latest),
            "age_entries": max(0, latest - seqs.get(proposal_id, latest)),
        })
    oldest = None
    for item in items:
        if oldest is None or item["age_entries"] > oldest["age_entries"]:
            oldest = item
    content = {
        "depth": len(items),
        "by_class": by_class,
        "by_effect": by_effect,
        "items": [[item["proposal_id"], item["queued_seq"],
                   item["effects"], item["class"]] for item in items],
    }
    summary = {
        "depth": len(items),
        "by_effect": by_effect,
        "by_class": by_class,
        "oldest_id": oldest["proposal_id"] if oldest else None,
        "oldest_age_entries": oldest["age_entries"] if oldest else 0,
        "latest_seq": latest,
        "age_mode": AGE_MODE,
        "snapshot_hash": hash_of(content),
    }
    return summary, items


def summary_text(summary):
    """The batched summary, exactly the shape that ships: counts
    by effect class, the oldest item's age, total depth, and the
    snapshot hash. No per-item listing."""
    lines = [
        "decision queue: %d item(s) waiting" % summary["depth"],
        "counts by effect: %s" % (
            ", ".join("%s %d" % (k, summary["by_effect"][k])
                      for k in sorted(summary["by_effect"])) or "none"),
        "counts by class: %s" % (
            ", ".join("%s %d" % (k, summary["by_class"][k])
                      for k in sorted(summary["by_class"])) or "none"),
        "oldest item age: %d log entries (age mode: %s)"
        % (summary["oldest_age_entries"], summary["age_mode"]),
        "snapshot %s" % summary["snapshot_hash"],
    ]
    return "\n".join(lines)


# ------------------------------------------------------------ firing

def tripped_by(summary, max_age, max_count):
    """Names of the thresholds the snapshot is at or beyond."""
    tripped = []
    if max_age is not None and summary["oldest_age_entries"] >= max_age:
        tripped.append("max-age")
    if max_count is not None and summary["depth"] >= max_count:
        tripped.append("max-count")
    return tripped


def load_notify_state(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def save_notify_state(path, summary):
    record = {
        "snapshot_hash": summary["snapshot_hash"],
        "oldest_id": summary["oldest_id"],
        "oldest_age_entries": summary["oldest_age_entries"],
        "latest_seq": summary["latest_seq"],
        "depth": summary["depth"],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return record


def materially_changed(summary, record):
    """True when the snapshot differs from the last notified one
    in a way that justifies firing again: different snapshot
    (items arrived / left / changed), or the same oldest item
    strictly older on substantive log growth."""
    if record is None:
        return True
    if record.get("snapshot_hash") != summary["snapshot_hash"]:
        return True
    return (summary["oldest_id"] is not None
            and summary["oldest_id"] == record.get("oldest_id")
            and summary["oldest_age_entries"]
            > record.get("oldest_age_entries", 0)
            and summary["latest_seq"] > record.get("latest_seq", -1))


def append_notification(log, summary, tripped, max_age, max_count):
    """Append the verifiable record: a fold-transparent
    checkpoint entry (see module docstring for why). `log` must
    be the Log the snapshot was computed from, before append."""
    body = {
        "name": NOTIFY_NAME,
        "producer": "jqnotify",
        "state_hash": fold(log.entries).state_hash(),
        "snapshot_hash": summary["snapshot_hash"],
        "summary": {
            "depth": summary["depth"],
            "by_effect": summary["by_effect"],
            "by_class": summary["by_class"],
            "oldest_id": summary["oldest_id"],
            "oldest_age_entries": summary["oldest_age_entries"],
            "latest_seq": summary["latest_seq"],
            "age_mode": summary["age_mode"],
        },
        "thresholds": {"max_age_entries": max_age,
                       "max_count": max_count,
                       "tripped": tripped},
        "note": "batched queue notification (annotation only; "
                "proposes nothing, approves nothing; recompute "
                "from the log prefix to verify)",
    }
    return log.append("checkpoint", body)


def verify_notifications(entries):
    """Recompute every notification record from its log prefix.
    Returns a list of (seq, ok, detail)."""
    results = []
    for index, entry in enumerate(entries):
        if not is_notification(entry):
            continue
        summary, _items = compute_snapshot(entries[:index])
        body = entry["body"]
        recorded = body.get("summary", {})
        ok = (body.get("snapshot_hash") == summary["snapshot_hash"]
              and recorded.get("depth") == summary["depth"]
              and recorded.get("by_effect") == summary["by_effect"]
              and recorded.get("by_class") == summary["by_class"]
              and recorded.get("oldest_id") == summary["oldest_id"]
              and recorded.get("oldest_age_entries")
              == summary["oldest_age_entries"]
              and recorded.get("latest_seq") == summary["latest_seq"])
        results.append((entry["seq"], ok,
                        "snapshot %s" % body.get("snapshot_hash")))
    return results


# ------------------------------------------------------------ delivery

def next_verdict_number(verdicts_dir):
    highest = -1
    if os.path.isdir(verdicts_dir):
        for name in os.listdir(verdicts_dir):
            head = name.split("-", 1)[0]
            if len(head) == 3 and head.isdigit():
                highest = max(highest, int(head))
    return highest + 1


def deliver_drop(inbox_dir, summary, log_path):
    """Write the operator drop into <inbox>/verdicts/, numbered
    sequentially in that folder's format, and commit it to the
    inbox repo (pushing when the repo has an origin). Returns a
    dict describing what actually happened."""
    verdicts_dir = os.path.join(inbox_dir, "verdicts")
    os.makedirs(verdicts_dir, exist_ok=True)
    number = next_verdict_number(verdicts_dir)
    filename = "%03d-jqnotify-%s.md" % (number, summary["snapshot_hash"][:8])
    filed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Verdict %03d — jqnotify queue summary %s"
        % (number, summary["snapshot_hash"][:8]),
        "",
        "Filed: %s (receipt time; every queue number below is "
        "log-derived and replay-verifiable)" % filed,
        "Log: %s (snapshot at substantive seq %d)"
        % (log_path, summary["latest_seq"]),
        "Snapshot sha256: %s" % summary["snapshot_hash"],
        "Witnesses: 1 (jqnotify — automated notifier; this "
        "verdict does not price the witness)",
        "Session: jacquard phase 5 slice 14, batched queue "
        "notification",
        "",
        "claims: COMPLETE (1 claim, addressed below)",
        "",
        "## claim: queue-snapshot-%s — REPORTED (numbers "
        "recomputable from the log)" % summary["snapshot_hash"][:8],
        "",
        summary_text(summary),
        "",
        "This is a tap on the shoulder, not a second queue: it "
        "proposes nothing and approves nothing. Decisions stay "
        "in the operator CLI / service. Verify by re-folding "
        "the kernel log up to the queue-notification checkpoint "
        "entry carrying this snapshot hash and recomputing the "
        "summary (`python3 tools/jqnotify.py --log <path> "
        "--verify`).",
        "",
    ]
    path = os.path.join(verdicts_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    result = {"file": "verdicts/%s" % filename, "committed": False,
              "pushed": False}

    def git(*argv):
        return subprocess.run(["git", "-C", inbox_dir] + list(argv),
                              capture_output=True, text=True)

    if git("rev-parse", "--git-dir").returncode != 0:
        result["error"] = "inbox dir is not a git repository; " \
                          "drop written but not committed"
        return result
    git("add", "verdicts/%s" % filename)
    commit = git("commit", "-m",
                 "verdict %03d: jqnotify queue summary %s "
                 "(depth %d, oldest %d entries)"
                 % (number, summary["snapshot_hash"][:8],
                    summary["depth"], summary["oldest_age_entries"]))
    if commit.returncode != 0:
        result["error"] = "git commit failed: %s" % commit.stderr.strip()
        return result
    result["committed"] = True
    if git("remote", "get-url", "origin").returncode == 0:
        push = git("push")
        result["pushed"] = push.returncode == 0
        if push.returncode != 0:
            result["push_error"] = push.stderr.strip()
    return result


# ------------------------------------------------------------ CLI

def _int_or_none(value):
    return None if value is None else int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="jqnotify",
        description="Batched decision-queue notifications. Age is "
                    "measured in log entries (the kernel log has "
                    "no wall-clock timestamps; see module docs).")
    parser.add_argument("--log", required=True, help="kernel log (JSONL)")
    parser.add_argument("--max-age-s", "--max-age", dest="max_age",
                        type=int, default=None,
                        help="fire when the oldest waiting item's "
                             "age reaches N log entries "
                             "(env JQNOTIFY_MAX_AGE_S; default %d)"
                             % DEFAULT_MAX_AGE)
    parser.add_argument("--max-count", type=int, default=None,
                        help="fire when the queue depth reaches N "
                             "(env JQNOTIFY_MAX_COUNT; default %d)"
                             % DEFAULT_MAX_COUNT)
    parser.add_argument("--state-file", default=None,
                        help="repeat-suppression state file "
                             "(env JQNOTIFY_STATE_FILE; default "
                             "<log>.jqnotify-state.json)")
    parser.add_argument("--deliver", action="store_true",
                        help="also commit a Markdown drop to the "
                             "agent-inbox verdicts/ folder")
    parser.add_argument("--inbox-dir", default=None,
                        help="agent-inbox repo (env "
                             "JQNOTIFY_INBOX_DIR; default ~/agent-inbox)")
    parser.add_argument("--verbose", action="store_true",
                        help="also list waiting item ids (the "
                             "default drop is the batched summary)")
    parser.add_argument("--check", action="store_true",
                        help="dry run: report whether a notification "
                             "would fire; append nothing, deliver "
                             "nothing, write no state")
    parser.add_argument("--verify", action="store_true",
                        help="verify every notification record in "
                             "the log against its prefix and exit")
    args = parser.parse_args(argv)

    log = Log(args.log) if os.path.exists(args.log) else Log()

    if args.verify:
        results = verify_notifications(log.entries)
        if not results:
            print("verify: no notification records in %s" % args.log)
            return 0
        bad = 0
        for seq, ok, detail in results:
            print("verify seq %d: %s (%s)"
                  % (seq, "OK" if ok else "MISMATCH", detail))
            bad += 0 if ok else 1
        return 1 if bad else 0

    max_age = args.max_age
    if max_age is None:
        max_age = _int_or_none(os.environ.get("JQNOTIFY_MAX_AGE_S"))
    if max_age is None:
        max_age = DEFAULT_MAX_AGE
    max_count = args.max_count
    if max_count is None:
        max_count = _int_or_none(os.environ.get("JQNOTIFY_MAX_COUNT"))
    if max_count is None:
        max_count = DEFAULT_MAX_COUNT
    state_file = args.state_file or os.environ.get(
        "JQNOTIFY_STATE_FILE") or (args.log + ".jqnotify-state.json")

    summary, items = compute_snapshot(log.entries)
    tripped = tripped_by(summary, max_age, max_count)
    record = load_notify_state(state_file)
    changed = materially_changed(summary, record)
    fired = bool(tripped) and changed and not args.check

    delivered = None
    notified_seq = None
    if fired:
        entry = append_notification(log, summary, tripped,
                                    max_age, max_count)
        notified_seq = entry["seq"]
        save_notify_state(state_file, summary)
        if args.deliver:
            inbox_dir = args.inbox_dir or os.environ.get(
                "JQNOTIFY_INBOX_DIR") or os.path.expanduser("~/agent-inbox")
            delivered = deliver_drop(inbox_dir, summary, args.log)

    print(summary_text(summary))
    if args.verbose:
        for item in items:
            print("  - %s producer %s class %s effects %s "
                  "queued seq %d age %d"
                  % (item["proposal_id"], item["producer"],
                     item["class"], ", ".join(item["effects"]),
                     item["queued_seq"], item["age_entries"]))
    status = {
        "fired": fired,
        "would_fire": bool(tripped) and changed,
        "tripped": tripped,
        "suppressed": bool(tripped) and not changed,
        "thresholds": {"max_age_entries": max_age,
                       "max_count": max_count},
        "snapshot_hash": summary["snapshot_hash"],
        "depth": summary["depth"],
        "oldest_age_entries": summary["oldest_age_entries"],
        "age_mode": summary["age_mode"],
        "state_file": state_file,
    }
    if notified_seq is not None:
        status["notification_seq"] = notified_seq
    if delivered is not None:
        status["delivered"] = delivered
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
