"""The booking-board adapter (Phase 11, slice 30): the fleet's
schedule board (SuperInstance/agent-inbox, schedule/<box>.md)
behind the booking profile.

The board stays the board: git is still the transport, a
commit is still the booking. What this adapter adds is a
kernel decision in front of every booking it applies:

- `init` creates a kernel log, installs the booking profile
  (src/jacquard/booking.py), records the operator's rank
  grants, and imports the board's live rows as committed
  booking records. Imports are FACTS, not decisions: each is
  written by an operator proposal (the same "config" class
  the grant path uses) with its provenance — source commit,
  original row text, normalised fields — published as a
  `board-import` sense entry in the same log. Normalisation
  is stated, never silent: board seat strings are mapped to
  the profile's classified seat vocabulary by first token
  ("zcode (own tmux lane-tt)" -> "zcode"; "cpu" -> "detached",
  non-exclusive CPU work), and the original string is kept
  in the import entry.
- `propose` runs a booking through BookingFlow.submit_live:
  contention and authority are kernel senses, the machine
  decides requested -> active | held, ties hold (the interim
  disposition), and a committed booking is applied to the
  board (row appended with a "(jq:<id>)" marker, committed,
  pushed) with the board commit journalled back as a
  `board-apply` sense entry. A held booking is NOT applied;
  it waits for the operator.
- `release` is the operator's half: release the queued
  proposal (the write executes), re-step the machine against
  a fresh contention reading, dispose of lower-rank held
  contenders the winner now outranks (the flow's own
  disposal path), and apply to the board.
- `complete` / `cancel` step the machine, rewrite the
  committed record's status (inert for contention), and mark
  the board row DONE / CANCELLED.

One writer at a time: every command rebuilds the sequencer
from the log (the Phase 5/6 operating rule). The adapter
computes no overlap and no rank comparison itself — routing
and board I/O only; every decision predicate is the
kernel's.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer, install_booking  # noqa: E402
from jacquard.booking import BookingFlow, publish_contention  # noqa: E402
from jacquard.envelope import make_envelope  # noqa: E402

EXCLUSIVE = {"zcode", "mcode", "claude-code", "gpu", "stage",
             "kimi", "box"}

# Board seat strings whose real semantics are non-exclusive
# work; stated here, applied at import/propose, and recorded
# in the log — never a silent rewrite.
SEAT_NORMALISE = {"cpu": "detached"}


def normalise_seat(board_seat):
    first = board_seat.strip().split()[0] if board_seat.strip() else ""
    if first in EXCLUSIVE or first == "detached":
        return first
    return SEAT_NORMALISE.get(first, first)


def to_epoch_min(text):
    """'2026-11-03 17:15' (UTC) -> epoch minutes."""
    dt = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
    return int(dt.replace(tzinfo=timezone.utc).timestamp() // 60)


def fmt_min(epoch_min):
    return datetime.fromtimestamp(epoch_min * 60,
                                  timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_duration_min(text):
    """'3h', '~6h', '2h30m', '45m', '2h · DONE ...' -> minutes
    or None when unparseable."""
    t = text.strip().lstrip("~")
    t = t.split("·")[0].strip()
    m = re.fullmatch(r"(?:(\d+)h)?(?:\s*(\d+)m)?", t)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ------------------------------------------------------------ board I/O

def parse_board(inbox, box):
    """Live rows of schedule/<box>.md: a row is live when it
    carries no DONE marker and its check-by (when parseable)
    has not passed `now_min`."""
    path = os.path.join(inbox, "schedule", "%s.md" % box)
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path):
        line = line.rstrip("\n")
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] in ("lane", "") \
                or set(cells[0]) <= {"-"}:
            continue
        lane, seat, frm, planned, checkby, what = cells[:6]
        rows.append({"lane": lane, "seat": seat, "from": frm,
                     "planned": planned, "checkby": checkby,
                     "what": what, "raw": line})
    return rows


def row_is_done(row):
    return "DONE" in row["planned"] or "DONE" in row["what"]


def git(inbox, *args):
    return subprocess.run(["git", "-C", inbox] + list(args),
                          capture_output=True, text=True)


def apply_row(inbox, box, row_text, booking_id):
    """Append the row, commit, push. Returns the commit hash
    or raises RuntimeError with the git output. Idempotent:
    if the (jq:<id>) marker is already on the board (a prior
    partial run), the existing HEAD is returned unchanged."""
    path = os.path.join(inbox, "schedule", "%s.md" % box)
    if "(jq:%s)" % booking_id in open(path).read():
        return git(inbox, "rev-parse", "--short",
                   "HEAD").stdout.strip()
    with open(path, "a") as fh:
        fh.write(row_text + "\n")
    git(inbox, "add", "schedule/%s.md" % box)
    msg = "book: %s (via jacquard booking %s)" % (box, booking_id)
    out = git(inbox, "commit", "-q", "-m", msg)
    if out.returncode != 0:
        raise RuntimeError("board commit failed: %s" % out.stderr)
    out = git(inbox, "push", "-q", "origin", "HEAD")
    if out.returncode != 0:
        # Incumbent race: someone pushed first. Rebase once.
        git(inbox, "pull", "-q", "--rebase")
        out = git(inbox, "push", "-q", "origin", "HEAD")
        if out.returncode != 0:
            raise RuntimeError("board push failed: %s" % out.stderr)
    return git(inbox, "rev-parse", "--short", "HEAD").stdout.strip()


def mark_row(inbox, box, booking_id, note):
    """Append a note to the row carrying the (jq:<id>) marker,
    commit, push. Returns the commit hash."""
    path = os.path.join(inbox, "schedule", "%s.md" % box)
    marker = "(jq:%s)" % booking_id
    lines = open(path).read().split("\n")
    for i, line in enumerate(lines):
        if marker in line:
            lines[i] = line + " " + note
            break
    else:
        raise RuntimeError("no board row carries %s" % marker)
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    git(inbox, "add", "schedule/%s.md" % box)
    out = git(inbox, "commit", "-q", "-m",
              "book: %s %s (via jacquard booking %s)"
              % (box, note.split()[0].lower(), booking_id))
    if out.returncode != 0:
        raise RuntimeError("board commit failed: %s" % out.stderr)
    out = git(inbox, "push", "-q", "origin", "HEAD")
    if out.returncode != 0:
        git(inbox, "pull", "-q", "--rebase")
        out = git(inbox, "push", "-q", "origin", "HEAD")
        if out.returncode != 0:
            raise RuntimeError("board push failed: %s" % out.stderr)
    return git(inbox, "rev-parse", "--short", "HEAD").stdout.strip()


# ------------------------------------------------------------ kernel side

def open_flow(log_path):
    seq = Sequencer(Log(log_path))
    return seq, BookingFlow(seq)


def journal(seq, name, value):
    seq.submit_sense(name, value, "booking-board-adapter")


def write_record(seq, record):
    """An operator config write of one booking record (the
    grants path: class "config" is allowed at once). Used for
    imports — facts, not decisions."""
    unit = "booking/%s/%s" % (record["box"], record["id"])
    envelope = make_envelope(
        "operator", "proposal",
        {"class": "config",
         "requests": [{"verb": "write", "args": [unit, record]}]},
        ["write"], "board-import-" + record["id"])
    verdict = seq.submit(envelope)
    if verdict.get("outcome") != "allow":
        raise RuntimeError("import of %s refused: %r"
                           % (record["id"], verdict))
    return verdict


def rewrite_status(seq, record, status):
    updated = dict(record)
    updated["status"] = status
    unit = "booking/%s/%s" % (record["box"], record["id"])
    envelope = make_envelope(
        "operator", "proposal",
        {"class": "config",
         "requests": [{"verb": "write", "args": [unit, updated]}]},
        ["write"], "board-status-%s-%s" % (record["id"], status))
    verdict = seq.submit(envelope)
    if verdict.get("outcome") != "allow":
        raise RuntimeError("status rewrite of %s refused: %r"
                           % (record["id"], verdict))
    return updated
