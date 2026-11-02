"""Probe A corpus: the Jacquard replay of the REAL booking-board history.

The reference semantics are the shadow trial's
(``tools/shadow_trial.py`` + ``docs/shadow-trial-2026-11-02.md``):
every booking row's first appearance in ``~/agent-inbox``'s
``schedule/`` git history is one item; contention is overlap with
an ACTIVE booking for a conflicting seat on the same box, same
lane = renewal, bookings past their check-by are dead.

Parsing is NOT re-implemented here: the trial's own helpers
(``history``, ``parse_dt``, ``parse_duration``, ``key_of``,
``seats_conflict``) are imported via importlib from
``tools/shadow_trial.py`` -- a single source of parsing truth.

Trial window: the trial report states it scanned 63 commits.
The live board has since gained two more schedule commits (a
"DONE" marking for the Jacquard build and the Phase-4 booking
itself), which would make 69 items / 53 decided and break
comparability with the reference. This corpus therefore replays
exactly the first 63 commits of the history (head ``0d23fd56``),
which reproduces the trial's published counts precisely; the
self-test asserts that head so a shifting window fails loudly
instead of silently drifting.

Booking record (committed as unit ``booking/<box>/<id>``)::

    {"id", "box", "producer", "seat", "start", "end", "checkby",
     "status", "rank"}

Times are integer minutes since the epoch UTC
(``calendar.timegm``); ``checkby`` may be None; ``status`` is one
of active|done|cancelled|preempted; ``rank`` is 0 throughout
this probe's corpus.

Event stream (``build()["events"]``), in history order:

- ``candidate`` -- a decided item at its first appearance,
  emitted BEFORE its ``commit`` (the shadow decision is taken
  against the committed state that precedes it, exactly as the
  trial evaluates contention before the board takes the row);
- ``commit`` -- a first-appearance decided or note item enters
  committed state (notes commit with status ``"done"``);
- ``status`` -- a removal, or a DONE-marking re-add, changes a
  committed item's status (the full updated record is carried).

Unevaluable items (unparseable start, or no duration and not a
retroactive note) are EXCLUDED from the stream: they were inert
as contenders in the reference walk (its contention loop skips
start/duration-less bookings). The self-test proves inertness by
re-running the label walk with unevaluable items never added to
the active set and asserting identical labels.
"""
import calendar
import importlib.util
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX = Path.home() / "agent-inbox"
TRIAL_COMMIT_COUNT = 63
TRIAL_HEAD = "0d23fd56"


def _load_trial():
    # The trial module does sys.path.insert(0, "src") relative to
    # the caller's cwd; give it the repo's absolute src instead.
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    spec = importlib.util.spec_from_file_location(
        "shadow_trial_ref", REPO_ROOT / "tools" / "shadow_trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRIAL = _load_trial()
history = TRIAL.history
parse_dt = TRIAL.parse_dt
parse_duration = TRIAL.parse_duration
key_of = TRIAL.key_of
seats_conflict = TRIAL.seats_conflict


def _minutes(dt):
    if dt is None:
        return None
    return calendar.timegm(dt.timetuple()) // 60


def _walk(commits, include_unevaluable=True):
    """One faithful port of the trial's active-set walk.

    Returns (items, labels, events). With
    ``include_unevaluable=False`` unevaluable items are never
    added to the active set (their keys are still seen), which
    the self-test uses to prove they cannot affect any label.
    """
    items = []
    labels = {}
    events = []
    active = {}          # key -> item index (insertion ordered)
    seen_ever = set()
    starts = []          # per item: datetime or None
    durations = []       # per item: timedelta or None
    checkbys = []        # per item: datetime or None
    done_flags = []      # per item: current done flag (trial semantics)
    statuses = []        # per item: current Jacquard status string
    records = []         # per item: current booking record

    def emit_status(idx, new_status):
        statuses[idx] = new_status
        record = dict(records[idx], status=new_status)
        records[idx] = record
        events.append({"type": "status", "item": idx,
                       "id": record["id"], "box": record["box"],
                       "status": new_status, "booking": dict(record)})

    for commit in commits:
        # Removals before adds within a commit (the trial's order).
        for box, cells in commit["removed"]:
            idx = active.pop(key_of(box, cells), None)
            if idx is None:
                continue
            if items[idx]["category"] in ("decided", "note") \
                    and statuses[idx] != "done":
                emit_status(idx, "done")
        for box, cells in commit["added"]:
            key = key_of(box, cells)
            if key in active or key in seen_ever:
                if key in active:
                    idx = active[key]
                    new_done = "DONE" in cells[5] or "DONE" in cells[3]
                    done_flags[idx] = new_done
                    if items[idx]["category"] in ("decided", "note"):
                        wanted = "done" if new_done else "active"
                        if statuses[idx] != wanted:
                            emit_status(idx, wanted)
                continue
            seen_ever.add(key)
            lane, seat, start_text, planned, checkby_text, what = cells
            start = parse_dt(start_text)
            duration = parse_duration(planned)
            retroactive = planned.strip().startswith("DONE")
            checkby = parse_dt(checkby_text)
            if start is None or (duration is None and not retroactive):
                category = "unevaluable"
            elif retroactive:
                category = "note"
            else:
                category = "decided"
            idx = len(items)
            start_min = _minutes(start)
            duration_min = (int(duration.total_seconds()) // 60
                            if duration is not None else None)
            if start_min is not None and duration_min is not None:
                end_min = start_min + duration_min
            elif start_min is not None and retroactive:
                end_min = start_min
            else:
                end_min = None
            record = {"id": "bk-%03d" % idx, "box": box,
                      "producer": lane, "seat": seat,
                      "start": start_min, "end": end_min,
                      "checkby": _minutes(checkby),
                      "status": "done" if retroactive else "active",
                      "rank": 0}
            items.append({
                "index": idx, "id": record["id"], "box": box,
                "lane": lane, "seat": seat,
                "start": start_min, "end": end_min,
                "checkby": record["checkby"], "what": what,
                "commit": commit["commit"], "category": category,
                "retroactive": retroactive, "booking": dict(record)})
            starts.append(start)
            durations.append(duration)
            checkbys.append(checkby)
            done_flags.append(retroactive)
            statuses.append(record["status"])
            records.append(record)
            if category == "unevaluable" and not include_unevaluable:
                continue
            active[key] = idx
            if category == "decided":
                end_dt = start + duration
                contenders = []
                for other_idx in active.values():
                    if other_idx == idx:
                        continue
                    other = items[other_idx]
                    if other["lane"] == lane or other["box"] != box:
                        continue
                    if done_flags[other_idx]:
                        continue
                    if starts[other_idx] is None \
                            or durations[other_idx] is None:
                        continue
                    if checkbys[other_idx] is not None \
                            and checkbys[other_idx] < start:
                        continue
                    if not seats_conflict(seat, other["seat"]):
                        continue
                    other_end = starts[other_idx] + durations[other_idx]
                    if start < other_end and starts[other_idx] < end_dt:
                        contenders.append(other_idx)
                labels[idx] = {"contends": bool(contenders),
                               "with": contenders}
                events.append({"type": "candidate", "item": idx,
                               "booking": dict(record)})
                events.append({"type": "commit", "item": idx,
                               "booking": dict(record)})
            elif category == "note":
                events.append({"type": "commit", "item": idx,
                               "booking": dict(record)})
    return items, labels, events


def build(inbox=None):
    """-> {"events": [...], "labels": {...}, "items": [...],
    "commits_scanned": int, "trial_head": str}"""
    commits = history(str(inbox or DEFAULT_INBOX))
    commits = commits[:TRIAL_COMMIT_COUNT]
    items, labels, events = _walk(commits, include_unevaluable=True)
    return {"events": events, "labels": labels, "items": items,
            "commits_scanned": len(commits),
            "trial_head": commits[-1]["commit"] if commits else None,
            "_commits": commits}


# ------------------------------------------------------------ self-test

EXPECTED_CONTENDED_ORDER = [
    # (seat, lane, box) in the report's disagreement order
    ("kimi", "system-three-paper", "thor"),
    ("box", "otherhere-rebuild", "proart"),
    ("box", "otherhere-rebuild", "thor"),
    ("box", "eden-trial", "thor"),
    ("gpu", "casting-call-revisability", "thor"),
    ("box", "whole-house-stage0", "thor"),
]


def self_test(built=None):
    """Cross-check assertions from the task brief. Raises
    AssertionError on any mismatch; returns a summary dict."""
    built = built if built is not None else build()
    items, labels, events = built["items"], built["labels"], built["events"]
    assert built["commits_scanned"] == TRIAL_COMMIT_COUNT, \
        built["commits_scanned"]
    assert built["trial_head"] == TRIAL_HEAD, built["trial_head"]
    assert len(items) == 68, len(items)
    counts = Counter(i["category"] for i in items)
    assert counts["note"] == 6, counts
    assert counts["unevaluable"] == 10, counts
    assert counts["decided"] == 52, counts
    assert len(labels) == 52, len(labels)
    contended = [i for i in items
                 if i["index"] in labels and labels[i["index"]]["contends"]]
    assert len(contended) == 6, [i["id"] for i in contended]
    order = [(i["seat"], i["lane"], i["box"]) for i in contended]
    assert order == EXPECTED_CONTENDED_ORDER, order
    assert Counter((i["box"], i["seat"]) for i in contended) == Counter({
        ("thor", "kimi"): 1, ("proart", "box"): 1, ("thor", "box"): 3,
        ("thor", "gpu"): 1})
    # The three incumbent-wrong items must be among the contended.
    incumbent_wrong = {("proart", "otherhere-rebuild"),
                       ("thor", "eden-trial"),
                       ("thor", "whole-house-stage0")}
    assert incumbent_wrong <= {(i["box"], i["lane"]) for i in contended}
    # Unevaluable inertness: walk again with them never activated.
    _items2, labels2, _events2 = _walk(built["_commits"],
                                       include_unevaluable=False)
    assert labels2 == labels, "unevaluable items changed a label"
    # Stream shape: decided items have candidate immediately
    # before commit; notes commit as done with no candidate;
    # no event touches an unevaluable item.
    by_type = Counter(e["type"] for e in events)
    assert by_type["candidate"] == 52, by_type
    assert by_type["commit"] == 58, by_type  # 52 decided + 6 notes
    for pos, event in enumerate(events):
        category = items[event["item"]]["category"]
        assert category in ("decided", "note"), event
        if event["type"] == "candidate":
            assert category == "decided"
            nxt = events[pos + 1]
            assert nxt["type"] == "commit" and nxt["item"] == event["item"]
        if event["type"] == "commit" and category == "note":
            assert event["booking"]["status"] == "done"
    return {"items": len(items), "notes": counts["note"],
            "unevaluable": counts["unevaluable"],
            "decided": counts["decided"],
            "contended": len(contended),
            "events": len(events), "by_type": dict(by_type)}


if __name__ == "__main__":
    print(self_test())
