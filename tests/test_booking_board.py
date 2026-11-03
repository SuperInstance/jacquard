"""The booking-board adapter (Phase 11, slice 30): the board
stays the board (git rows), the kernel decides before a row
is applied. Hermetic: a tmp inbox with a bare remote, a tmp
kernel log, the real CLI driven as a subprocess.

All fixture times are computed relative to the current time:
the live-row filter is wall-clock based (a row is live until
its check-by), so fixed calendar fixtures are a time bomb —
the first version of this file used 2026-11-03 times and its
tests began failing at 19:00 UTC that day (found by the
slice-31 stranger test, on the Orin, at 19:47 UTC).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
JQBOOK = os.path.join(ROOT, "tools", "jqbook.py")

ENV = dict(os.environ,
           GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="t@t")

NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


INC_FROM = ts(NOW - timedelta(hours=1))        # incumbent: live
INC_CHECKBY = ts(NOW + timedelta(hours=3))
DEAD_FROM = ts(NOW - timedelta(days=3))        # long dead at any now
DEAD_CHECKBY = ts(NOW - timedelta(days=3) + timedelta(hours=2))
INC_ID = "other-lane-thor-gpu-" + INC_FROM.replace(" ", "-").replace(":", "-")


def git(cwd, *args):
    out = subprocess.run(["git", "-C", cwd] + list(args),
                         capture_output=True, text=True, env=ENV)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def jqbook_raw(log, inbox, *args):
    return subprocess.run(
        [sys.executable, JQBOOK, "--log", log]
        + (["--inbox", inbox] if inbox else []) + list(args),
        capture_output=True, text=True, env=ENV)


def jqbook(log, inbox, *args):
    out = jqbook_raw(log, inbox, *args)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def board(tmp_path):
    inbox = str(tmp_path / "inbox")
    os.makedirs(os.path.join(inbox, "schedule"))
    git(tmp_path, "init", "-q", "--bare", "remote.git")
    git(inbox, "init", "-q", ".")
    with open(os.path.join(inbox, "schedule", "thor.md"), "w") as fh:
        fh.write(
            "# thor — bookings\n\n"
            "| lane | seat | from (UTC) | planned | check-by (UTC) | what |\n"
            "|---|---|---|---|---|---|\n"
            "| other-lane | gpu | %s | 4h | %s | incumbent gpu work |\n"
            "| old-lane | box | %s | 2h | %s | long dead |\n"
            % (INC_FROM, INC_CHECKBY, DEAD_FROM, DEAD_CHECKBY))
    git(inbox, "add", "-A")
    git(inbox, "commit", "-qm", "seed")
    git(inbox, "remote", "add", "origin", str(tmp_path / "remote.git"))
    git(inbox, "push", "-q", "origin", "HEAD:master")
    return inbox


def test_init_imports_live_rows_only(tmp_path):
    inbox = board(tmp_path)
    log = str(tmp_path / "kernel.jsonl")
    out = jqbook(log, inbox, "init", "--boxes", "thor")
    assert out["imported"] == 1       # other-lane only
    assert out["skipped"] == 1        # old-lane: check-by passed
    counts = jqbook(log, None, "counts")
    assert counts["bookings_by_status"] == {"active": 1}
    assert "board-import" in counts["board_events"]


def test_clear_propose_commits_and_applies(tmp_path):
    inbox = board(tmp_path)
    log = str(tmp_path / "kernel.jsonl")
    jqbook(log, inbox, "init", "--boxes", "thor")
    out = jqbook(log, inbox, "propose", "--box", "thor",
                 "--seat", "detached",
                 "--from", ts(NOW + timedelta(days=1)),
                 "--planned", "2h",
                 "--checkby", ts(NOW + timedelta(days=1, hours=1)),
                 "--what", "clear work", "--rank", "5")
    assert out["machine_state"] == "active"
    assert out["committed"] is True
    text = open(os.path.join(inbox, "schedule", "thor.md")).read()
    assert "(jq:%s)" % out["booking_id"] in text


def test_tie_holds_then_release_applies(tmp_path):
    inbox = board(tmp_path)
    log = str(tmp_path / "kernel.jsonl")
    jqbook(log, inbox, "init", "--boxes", "thor")
    out = jqbook(log, inbox, "propose", "--box", "thor",
                 "--seat", "gpu",
                 "--from", ts(NOW + timedelta(minutes=30)),
                 "--planned", "1h",
                 "--checkby", ts(NOW + timedelta(hours=1)),
                 "--what", "tie work", "--rank", "5", "--grant")
    # rank 5 against the incumbent's effective 5: a tie holds
    # (the interim disposition) and nothing reaches the board.
    assert out["machine_state"] == "held"
    assert out["committed"] is False
    text = open(os.path.join(inbox, "schedule", "thor.md")).read()
    assert "(jq:%s)" % out["booking_id"] not in text
    queue = jqbook(log, None, "queue")
    assert [i["booking_id"] for i in queue["queued_bookings"]] == \
        [out["booking_id"]]
    rel = jqbook(log, inbox, "release", "--id", out["booking_id"])
    assert rel["released"] is True
    # The incumbent still holds the seat: the machine says so.
    assert rel["machine_state"] == "held"
    text = open(os.path.join(inbox, "schedule", "thor.md")).read()
    assert "(jq:%s)" % out["booking_id"] in text


def test_reject_cancels_and_complete_marks_done(tmp_path):
    inbox = board(tmp_path)
    log = str(tmp_path / "kernel.jsonl")
    jqbook(log, inbox, "init", "--boxes", "thor")
    tie = jqbook(log, inbox, "propose", "--box", "thor",
                 "--seat", "gpu",
                 "--from", ts(NOW + timedelta(minutes=45)),
                 "--planned", "30m", "--what", "reject me",
                 "--rank", "5", "--grant")
    out = jqbook(log, None, "reject", "--id", tie["booking_id"])
    assert out["machine_state"] == "cancelled"
    clear = jqbook(log, inbox, "propose", "--box", "thor",
                   "--seat", "detached",
                   "--from", ts(NOW + timedelta(days=2)),
                   "--planned", "1h",
                   "--what", "finish me", "--rank", "5")
    done = jqbook(log, inbox, "complete", "--id",
                  clear["booking_id"])
    assert done["status"] == "done"
    text = open(os.path.join(inbox, "schedule", "thor.md")).read()
    row = [ln for ln in text.split("\n")
           if "(jq:%s)" % clear["booking_id"] in ln][0]
    assert "DONE" in row
    counts = jqbook(log, None, "counts")
    assert counts["bookings_by_status"].get("done") == 1


def test_import_ids_unique_per_seat(tmp_path):
    """Two live rows from one lane on one box at one time with
    different seats are two bookings (regression: the first
    deployment's slug collided them into one unit)."""
    inbox = board(tmp_path)
    path = os.path.join(inbox, "schedule", "thor.md")
    dual_from = ts(NOW - timedelta(minutes=30))
    dual_checkby = ts(NOW + timedelta(hours=2))
    with open(path, "a") as fh:
        fh.write("| dual-lane | zcode | %s | 3h | %s | seat one |\n"
                 "| dual-lane | mcode | %s | 2h | %s | seat two |\n"
                 % (dual_from, dual_checkby, dual_from, dual_checkby))
    git(inbox, "add", "-A")
    git(inbox, "commit", "-qm", "dual")
    git(inbox, "push", "-q", "origin", "HEAD:master")
    log = str(tmp_path / "kernel.jsonl")
    out = jqbook(log, inbox, "init", "--boxes", "thor")
    assert out["imported"] == 3
    counts = jqbook(log, None, "counts")
    dual = [u for u in counts["bookings"] if "dual-lane" in u]
    assert len(dual) == 2


def test_close_imported_booking_is_kernel_side_only(tmp_path):
    """Completing an IMPORTED booking (another lane's row)
    rewrites its kernel status — making it inert for
    contention — without touching the owner's board row."""
    inbox = board(tmp_path)
    log = str(tmp_path / "kernel.jsonl")
    jqbook(log, inbox, "init", "--boxes", "thor")
    before = open(os.path.join(inbox, "schedule", "thor.md")).read()
    out = jqbook(log, inbox, "complete", "--id", INC_ID)
    assert out["status"] == "done"
    assert out["board_row_marked"] is False
    after = open(os.path.join(inbox, "schedule", "thor.md")).read()
    assert before == after
    counts = jqbook(log, None, "counts")
    assert counts["bookings_by_status"].get("done") == 1


def test_init_rejects_a_non_git_inbox(tmp_path):
    """Slice 31 finding: init used to succeed silently against
    a plain directory copy; the failure then surfaced
    mid-propose, after the kernel had decided. The inbox
    requirement (git clone, origin set) is now a preflight."""
    plain = str(tmp_path / "plain")
    os.makedirs(os.path.join(plain, "schedule"))
    out = jqbook_raw(str(tmp_path / "k.jsonl"), plain,
                     "init", "--boxes", "thor")
    assert out.returncode != 0
    assert "not a git working tree" in out.stderr


def test_init_rejects_an_inbox_without_origin(tmp_path):
    inbox = str(tmp_path / "inbox2")
    os.makedirs(os.path.join(inbox, "schedule"))
    git(inbox, "init", "-q", ".")
    out = jqbook_raw(str(tmp_path / "k.jsonl"), inbox,
                     "init", "--boxes", "thor")
    assert out.returncode != 0
    assert "no origin remote" in out.stderr
