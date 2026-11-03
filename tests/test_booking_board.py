"""The booking-board adapter (Phase 11, slice 30): the board
stays the board (git rows), the kernel decides before a row
is applied. Hermetic: a tmp inbox with a bare remote, a tmp
kernel log, the real CLI driven as a subprocess.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
JQBOOK = os.path.join(ROOT, "tools", "jqbook.py")

ENV = dict(os.environ,
           GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="t@t")


def git(cwd, *args):
    out = subprocess.run(["git", "-C", cwd] + list(args),
                         capture_output=True, text=True, env=ENV)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def jqbook(log, inbox, *args):
    out = subprocess.run(
        [sys.executable, JQBOOK, "--log", log]
        + (["--inbox", inbox] if inbox else []) + list(args),
        capture_output=True, text=True, env=ENV)
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
            "| other-lane | gpu | 2026-11-03 16:00 | 4h | "
            "2026-11-03 19:00 | incumbent gpu work |\n"
            "| old-lane | box | 2026-10-01 10:00 | 2h | "
            "2026-10-01 12:00 | long dead |\n")
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
                 "--seat", "detached", "--from", "2026-11-04 10:00",
                 "--planned", "2h", "--checkby", "2026-11-04 11:00",
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
                 "--seat", "gpu", "--from", "2026-11-03 18:00",
                 "--planned", "1h", "--checkby", "2026-11-03 18:30",
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
                 "--seat", "gpu", "--from", "2026-11-03 18:15",
                 "--planned", "30m", "--what", "reject me",
                 "--rank", "5", "--grant")
    out = jqbook(log, None, "reject", "--id", tie["booking_id"])
    assert out["machine_state"] == "cancelled"
    clear = jqbook(log, inbox, "propose", "--box", "thor",
                   "--seat", "detached",
                   "--from", "2026-11-05 09:00", "--planned", "1h",
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
    with open(path, "a") as fh:
        fh.write("| dual-lane | zcode | 2026-11-03 17:10 | 3h | "
                 "2026-11-03 18:30 | seat one |\n"
                 "| dual-lane | mcode | 2026-11-03 17:10 | 2h | "
                 "2026-11-03 18:30 | seat two |\n")
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
    out = jqbook(log, inbox, "complete",
                 "--id", "other-lane-thor-gpu-2026-11-03-16-00")
    assert out["status"] == "done"
    assert out["board_row_marked"] is False
    after = open(os.path.join(inbox, "schedule", "thor.md")).read()
    assert before == after
    counts = jqbook(log, None, "counts")
    assert counts["bookings_by_status"].get("done") == 1
