"""Slice 14: batched queue notifications (tools/jqnotify.py).

Synthetic logs are built through the real sequencer (queued
items are genuine policy/1 queue decisions), then aged by
appending fold-transparent filler checkpoints — substantive
entries that advance the log's own clock. The summary numbers
are checked against an INDEPENDENT recomputation that reads the
raw JSONL file and never imports the tool's snapshot code.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from jacquard import Log, Sequencer, fold, install_lifecycles, make_envelope  # noqa: E402
import jqnotify  # noqa: E402

TOOL = os.path.join(os.path.dirname(__file__), "..", "tools", "jqnotify.py")


def build_log(path, filler=0):
    """Two queued items (alice: notify; bob: spend) plus one
    allowed dispatch, then `filler` substantive entries of age."""
    seq = Sequencer(Log(str(path)))
    install_lifecycles(seq)
    a = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "hi"]}]},
        ["notify"], "n-a"))
    b = seq.submit(make_envelope(
        "bob", "proposal",
        {"requests": [{"verb": "spend", "args": ["compute", 10]}]},
        ["spend"], "n-b"))
    assert a["outcome"] == "queue" and b["outcome"] == "queue"
    for i in range(filler):
        seq.checkpoint("filler-%d" % i)
    return seq, a["proposal_id"], b["proposal_id"]


def run_tool(log, *argv, env=None, expect=0):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run([sys.executable, TOOL, "--log", str(log)]
                          + list(argv), capture_output=True, text=True,
                          env=full_env)
    assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
    status = json.loads(proc.stdout.strip().splitlines()[-1])
    return proc.stdout, status


def recompute_from_raw(path):
    """Independent snapshot: parse the JSONL by hand, mirror the
    documented definitions, import nothing from jqnotify."""
    entries = [json.loads(line) for line in
               open(path, encoding="utf-8") if line.strip()]
    queue = {}
    qseq = {}
    latest = -1
    for entry in entries:
        body = entry["body"]
        own = entry["kind"] == "checkpoint" \
            and body.get("name") == "queue-notification"
        if not own:
            latest = entry["seq"]
        if entry["kind"] != "decision":
            continue
        if body.get("outcome") == "queued":
            queue[body["proposal_id"]] = body
            qseq[body["proposal_id"]] = entry["seq"]
        for key in ("releases", "rejects", "expires"):
            if body.get(key):
                queue.pop(body[key], None)
                qseq.pop(body[key], None)
    by_effect = {}
    ages = {}
    for pid, body in queue.items():
        for effect in body.get("effects", []):
            by_effect[effect] = by_effect.get(effect, 0) + 1
        ages[pid] = latest - qseq[pid]
    return {"depth": len(queue), "by_effect": by_effect,
            "oldest_age": max(ages.values()) if ages else 0,
            "ages": ages}


# ---------------------------------------------------------- snapshot

def test_snapshot_numbers_match_independent_recomputation(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=7)
    entries = Log(str(log)).entries
    summary, _items = jqnotify.compute_snapshot(entries)
    raw = recompute_from_raw(log)
    assert summary["depth"] == raw["depth"] == 2
    assert summary["by_effect"] == raw["by_effect"] == {"notify": 1,
                                                        "spend": 1}
    assert summary["oldest_age_entries"] == raw["oldest_age"]
    assert summary["age_mode"] == "log-entries"
    assert len(summary["snapshot_hash"]) == 64


def test_snapshot_hash_stable_and_content_sensitive(tmp_path):
    log = tmp_path / "k.jsonl"
    seq, _a, _b = build_log(log, filler=3)
    first, _ = jqnotify.compute_snapshot(seq.log.entries)
    again, _ = jqnotify.compute_snapshot(Log(str(log)).entries)
    assert first["snapshot_hash"] == again["snapshot_hash"]
    seq.checkpoint("more-age")  # age grows; content hash must not
    aged, _ = jqnotify.compute_snapshot(seq.log.entries)
    assert aged["snapshot_hash"] == first["snapshot_hash"]
    assert aged["oldest_age_entries"] == first["oldest_age_entries"] + 1
    seq.reject_queued(_a, "operator")  # content changes
    shrunk, _ = jqnotify.compute_snapshot(seq.log.entries)
    assert shrunk["snapshot_hash"] != first["snapshot_hash"]
    assert shrunk["depth"] == 1


# ---------------------------------------------------------- thresholds

def test_no_fire_below_thresholds(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=2)
    _out, status = run_tool(log, "--max-age-s", "1000",
                            "--max-count", "1000")
    assert status["fired"] is False and status["tripped"] == []
    assert not os.path.exists(str(log) + ".jqnotify-state.json")


def test_fire_on_age_threshold(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    _out, status = run_tool(log, "--max-age-s", "10",
                            "--max-count", "1000")
    assert status["fired"] is True and status["tripped"] == ["max-age"]


def test_fire_on_count_threshold(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=0)
    _out, status = run_tool(log, "--max-age-s", "100000",
                            "--max-count", "2")
    assert status["fired"] is True and status["tripped"] == ["max-count"]


def test_thresholds_from_environment(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=0)
    _out, status = run_tool(log, env={"JQNOTIFY_MAX_COUNT": "2",
                                      "JQNOTIFY_MAX_AGE_S": "100000"})
    assert status["fired"] is True and status["tripped"] == ["max-count"]


def test_check_mode_fires_nothing(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    before = len(Log(str(log)).entries)
    _out, status = run_tool(log, "--max-age-s", "10", "--check")
    assert status["would_fire"] is True and status["fired"] is False
    assert len(Log(str(log)).entries) == before


# ---------------------------------------------------------- suppression

def test_repeat_suppression_unchanged_queue(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    _out, first = run_tool(log, "--max-age-s", "10")
    assert first["fired"] is True
    length_after_fire = len(Log(str(log)).entries)
    _out, second = run_tool(log, "--max-age-s", "10")
    assert second["fired"] is False and second["suppressed"] is True
    assert len(Log(str(log)).entries) == length_after_fire


def test_refire_when_queue_grows(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    _out, first = run_tool(log, "--max-age-s", "10")
    assert first["fired"] is True
    # the notifier is an external writer; a live sequencer is
    # rebuilt from the log before submitting again (one writer
    # at a time — a stale in-memory log would fork the chain)
    seq = Sequencer(Log(str(log)))
    seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "again"]}]},
        ["notify"], "n-c"))
    _out, second = run_tool(log, "--max-age-s", "10")
    assert second["fired"] is True
    assert second["depth"] == 3


def test_own_notification_does_not_age_the_queue(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    _out, first = run_tool(log, "--max-age-s", "10")
    assert first["fired"] is True
    summary, _ = jqnotify.compute_snapshot(Log(str(log)).entries)
    # the appended checkpoint is the newest entry, yet ages are
    # measured to the newest SUBSTANTIVE entry, so they did not move
    assert summary["oldest_age_entries"] == first["oldest_age_entries"]


# ---------------------------------------------------------- log record

def test_notification_record_refolds_cleanly(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    before = fold(Log(str(log)).entries)
    _out, status = run_tool(log, "--max-age-s", "10")
    assert status["fired"] is True
    reloaded = Log(str(log))
    assert reloaded.verify_chain()
    after = fold(reloaded.entries)
    # fold-transparent: identical state, nine sections intact
    assert after.state_hash() == before.state_hash()
    assert set(vars(after)) == {"units", "senses", "dictionary",
                                "decision_queue", "machines",
                                "machine_instances", "budgets",
                                "prices", "rules"}
    note = reloaded.entries[status["notification_seq"]]
    assert note["kind"] == "checkpoint"
    assert note["body"]["name"] == "queue-notification"
    assert note["body"]["snapshot_hash"] == status["snapshot_hash"]
    raw = recompute_from_raw(log)
    assert note["body"]["summary"]["depth"] == raw["depth"]
    assert note["body"]["summary"]["by_effect"] == raw["by_effect"]


def test_verify_mode_recomputes_every_record(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    run_tool(log, "--max-age-s", "10")
    seq = Sequencer(Log(str(log)))
    seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "spend", "args": ["compute", 1]}]},
        ["spend"], "n-c"))
    run_tool(log, "--max-age-s", "10")
    proc = subprocess.run([sys.executable, TOOL, "--log", str(log),
                           "--verify"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("OK") == 2


# ---------------------------------------------------------- presentation

def test_default_output_has_no_per_item_listing(tmp_path):
    log = tmp_path / "k.jsonl"
    _seq, id_a, id_b = build_log(log, filler=40)
    out, status = run_tool(log, "--max-age-s", "10")
    assert status["fired"] is True
    assert id_a not in out and id_b not in out
    assert "counts by effect" in out and "snapshot" in out
    out, _status = run_tool(log, "--max-age-s", "10", "--verbose",
                            "--check")
    assert id_a in out


# ---------------------------------------------------------- delivery

def _git(repo, *argv):
    return subprocess.run(["git", "-C", str(repo)] + list(argv),
                          capture_output=True, text=True)


def test_deliver_writes_numbered_committed_drop(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    inbox = tmp_path / "agent-inbox"
    (inbox / "verdicts").mkdir(parents=True)
    (inbox / "verdicts" / "000-firstlight.md").write_text("x\n")
    (inbox / "verdicts" / "001-ticks.md").write_text("x\n")
    assert _git(inbox, "init", "-q").returncode == 0
    _git(inbox, "config", "user.email", "test@example.com")
    _git(inbox, "config", "user.name", "test")
    _git(inbox, "add", "-A")
    assert _git(inbox, "commit", "-qm", "seed").returncode == 0
    _out, status = run_tool(log, "--max-age-s", "10", "--deliver",
                            "--inbox-dir", str(inbox))
    assert status["fired"] is True
    drop = status["delivered"]
    assert drop["file"].startswith("verdicts/002-jqnotify-")
    assert drop["committed"] is True and drop["pushed"] is False
    text = (inbox / drop["file"]).read_text(encoding="utf-8")
    assert status["snapshot_hash"] in text
    assert "decision queue: 2 item(s) waiting" in text
    assert "claims: COMPLETE" in text
    assert "002" in _git(inbox, "log", "--oneline").stdout


def test_no_deliver_flag_writes_no_drop(tmp_path):
    log = tmp_path / "k.jsonl"
    build_log(log, filler=40)
    inbox = tmp_path / "agent-inbox"
    (inbox / "verdicts").mkdir(parents=True)
    _out, status = run_tool(log, "--max-age-s", "10",
                            "--inbox-dir", str(inbox))
    assert status["fired"] is True and "delivered" not in status
    assert os.listdir(inbox / "verdicts") == []
