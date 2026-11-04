#!/usr/bin/env python3
"""E8 battery curation — Jacquard Phase 15, slice 43.

Assembles decision items from Jacquard's own recorded governance
decisions (see ../../E8-SOURCES.md for the source inventory) into
two time-split JSONL batteries:

  diagnostic.jsonl  — decisions recorded BEFORE the boundary
  heldout.jsonl     — decisions recorded AT/AFTER the boundary

Boundary: 2026-11-03T00:00:00Z. The split is by TIME only (each
item's recorded-at timestamp vs the boundary); nothing is shuffled
across it. Where a source carries no per-item timestamp (the
kernel logs carry sequence numbers, not clocks), an era timestamp
is assigned at source-window granularity and flagged in the item
(`ts_basis`); the boundary never cuts inside such a source, so the
assignment cannot move an item across the split.

Item = ONE proposal's FIRST recorded decision, except the booking
board, where the recorded outcome is the incumbent's (the board
took every row). Gold mapping: allow -> ALLOW, queued -> HOLD,
deny -> DENY; board incumbent acceptance -> ALLOW.

Correctness (`operator_correct` / `correct_outcome`):
  - true  : no record shows the recorded outcome was wrong; for
            the shadow-trial window and the proof/gpu reports the
            reports' own disagreement sections are the evidence.
  - false : a report explicitly classifies the recorded outcome
            as wrong; `correct_outcome` + evidence are recorded.
  - null  : correctness is genuinely indeterminate from the
            record (policy-gap disagreements, post-trial board
            rows with no audit, contested consumption repricings,
            operator config writes with no audit).

Deduplication:
  - docs/slice25/kernel.jsonl is the slice-22 live log CONTINUED
    (same log_id, seq 0..196); the slice-22 copy is not read.
  - docs/slice30 booking-class proposals whose board row also
    appears as a board item are dropped (same underlying booking
    recorded twice, with different golds: kernel HOLD vs board
    ALLOW — a contradictory-label duplicate). Config-class
    proposals from that log are kept (no board counterpart).
  - The raw gpu-queue event stream (tests/data/gpu-queue) is NOT
    turned into items: 1,637 dispatches with no per-item Jacquard
    decision. The repo's own curated use of it — the first six
    dispatches as rendered by tools/jev_experiment.py — is a
    source (source "jev").
  - docs/slice27 shadow rows re-price slice-25 proposals; they
    are used only as correctness evidence, never as items.

Contexts are compact and canonical and are rendered ONLY from
facts available at decision time (producer, class, effects,
request targets/commands without file contents, queue/policy
state, contention state, standing-rule state). Decision reasons,
release/reject markers and all post-hoc language are excluded.

Run on the Oracle:  python3 curate.py
Writes diagnostic.jsonl, heldout.jsonl, BATTERY.md beside itself.
"""
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]          # ~/jacquard-p15
INBOX = Path.home() / "agent-inbox"
BOUNDARY = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
OUTCOME = {"allow": "ALLOW", "queued": "HOLD", "queue": "HOLD",
           "deny": "DENY"}

sys.path.insert(0, str(REPO / "src"))
from jacquard import Sequencer, make_envelope  # noqa: E402

# ---------------------------------------------------------------- board
# History/cont contention algorithm follows tools/shadow_trial.py
# (Phase 3, slice 9), extended to keep the commit timestamp and to
# emit every decided item, not only the disagreements.
EXCLUSIVE_SEATS = {"zcode", "mcode", "claude-code", "gpu", "stage",
                   "kimi", "box"}
ROW = re.compile(r"^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
                 r"\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|")


def parse_dt(text):
    text = text.strip().replace("UTC", "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_duration(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*h", text)
    if m:
        return timedelta(hours=float(m.group(1)))
    m = re.search(r"(\d+)\s*m", text)
    if m:
        return timedelta(minutes=int(m.group(1)))
    return None


def board_history():
    out = subprocess.run(
        ["git", "-C", str(INBOX), "log", "--reverse",
         "--format=@%H %ad", "--date=iso", "-p", "--", "schedule/"],
        capture_output=True, text=True, check=True).stdout
    commits, current, box = [], None, None
    marker = re.compile(r"^@([0-9a-f]{40}) (.+)$")
    for line in out.splitlines():
        m = marker.match(line)
        if m:
            ts = datetime.fromisoformat(m.group(2).strip())
            current = {"commit": m.group(1)[:8],
                       "ts": ts.astimezone(timezone.utc),
                       "added": [], "removed": []}
            commits.append(current)
            continue
        if line.startswith("+++ b/schedule/"):
            box = line[len("+++ b/schedule/"):-3]
            continue
        if current is None or box is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            mm = ROW.match(line[1:])
            if mm and "lane" not in mm.group(1):
                current["added"].append(
                    (box, [c.strip() for c in mm.groups()]))
        elif line.startswith("-") and not line.startswith("---"):
            mm = ROW.match(line[1:])
            if mm and "lane" not in mm.group(1):
                current["removed"].append(
                    (box, [c.strip() for c in mm.groups()]))
    return commits


def seats_conflict(a, b):
    if a == b:
        return a in EXCLUSIVE_SEATS or a == "box"
    if "box" in (a, b):
        return True
    return False


# The six classified disagreements of docs/shadow-trial-2026-11-02.md,
# keyed by (box, lane, seat, start). Report item numbers in evidence.
BOARD_WRONG = {
    ("proart", "otherhere-rebuild", "box", "2026-10-27 21:30"):
        "shadow-trial report, disagreements item 2 (Incumbent wrong): "
        "a whole-box claim over a live exclusive seat, no declared "
        "exception in the row; the shadow would have queued it.",
    ("thor", "eden-trial", "box", "2026-10-27 23:00"):
        "shadow-trial report, disagreements item 4 (Incumbent wrong): "
        "the 23:00 whole-box booking ran into the live 02:00 whole-box "
        "booking; the fleet had to re-plan wrapup — the conflict was "
        "real and cost a shuffle.",
    ("thor", "whole-house-stage0", "box", "2026-10-28 02:00"):
        "shadow-trial report, disagreements item 6 (Incumbent wrong): "
        "light read-only measurement over-booked the exclusive box "
        "seat at the same moment as wrapup's box booking; the "
        "double-claim on an exclusive seat is the board's error.",
}
BOARD_GAP = {
    ("thor", "system-three-paper", "kimi", "2026-10-27 20:35"):
        "shadow-trial report, disagreements item 1 (Policy gap): a "
        "conditional, resource-light REBOOK; neither policy/1 nor the "
        "board protocol can express conditional starts.",
    ("thor", "otherhere-rebuild", "box", "2026-10-27 21:30"):
        "shadow-trial report, disagreements item 3 (Policy gap): the "
        "overlap is with a booking whose real occupancy is "
        "event-driven and unknown.",
    ("thor", "casting-call-revisability", "gpu", "2026-10-27 23:57"):
        "shadow-trial report, disagreements item 5 (Policy gap): a "
        "Casey-directed successor probe — an authority priority "
        "override neither the board nor policy/1 can carry.",
}
TRIAL_WINDOW_END = datetime(2026, 11, 2, 23, 59, 59,
                            tzinfo=timezone.utc)


def clean(text, limit=140):
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return t[:limit]


def board_items():
    commits = board_history()
    seq = Sequencer()
    active, seen_ever, items = {}, set(), []
    for cidx, commit in enumerate(commits):
        commit["_idx"] = cidx
        for box, cells in commit["removed"]:
            active.pop((box, cells[0], cells[1], cells[2]), None)
        for box, cells in commit["added"]:
            key = (box, cells[0], cells[1], cells[2])
            if key in active or key in seen_ever:
                if key in active:
                    active[key]["what"] = cells[5]
                    active[key]["done"] = ("DONE" in cells[5]
                                           or "DONE" in cells[3])
                continue
            seen_ever.add(key)
            lane, seat, start_text, planned, checkby, what = cells
            start = parse_dt(start_text)
            duration = parse_duration(planned)
            retro = planned.strip().startswith("DONE")
            booking = {"box": box, "lane": lane, "seat": seat,
                       "start": start, "duration": duration,
                       "checkby": parse_dt(checkby), "what": what,
                       "done": retro, "commit": commit["commit"],
                       "commit_ts": commit["ts"],
                       "planned_raw": planned, "checkby_raw": checkby,
                       "commit_idx": commit["_idx"]}
            active[key] = booking
            if start is None or (duration is None and not retro):
                continue                    # unevaluable: excluded
            if retro:
                continue                    # retroactive note: excluded
            verdict = seq.submit(make_envelope(
                lane, "proposal",
                {"class": "booking",
                 "requests": [{"verb": "write",
                               "args": ["booking/%s/%s" % (box, seat),
                                        what]}]},
                ["write"], "shadow-%d" % len(items)))
            contention = None
            end = start + (duration or timedelta(0))
            for okey, other in active.items():
                if other is booking or other["lane"] == lane \
                        or other["box"] != box or other["done"]:
                    continue
                if other["start"] is None or other["duration"] is None:
                    continue
                if other["checkby"] is not None \
                        and other["checkby"] < start:
                    continue
                if not seats_conflict(seat, other["seat"]):
                    continue
                oend = other["start"] + other["duration"]
                if start < oend and other["start"] < end:
                    contention = {"lane": other["lane"],
                                  "seat": other["seat"],
                                  "start": str(other["start"])}
                    break
            shadow = "queue" if contention else verdict["outcome"]
            if shadow not in ("allow", "queue", "deny"):
                continue
            items.append({**booking, "shadow": shadow,
                          "contention": contention})
    out = []
    for i, it in enumerate(items):
        key = (it["box"], it["lane"], it["seat"],
               it["start"].strftime("%Y-%m-%d %H:%M"))
        if key in BOARD_WRONG:
            oc, co, ev = False, "HOLD", BOARD_WRONG[key]
        elif key in BOARD_GAP:
            oc, co, ev = None, None, BOARD_GAP[key]
        elif it["commit_idx"] < 63:
            # the published trial scanned 63 schedule commits and
            # classified every disagreement in that history
            if it["shadow"] == "allow":
                oc, co = True, "ALLOW"
                ev = ("shadow-trial report: all six disagreements are "
                      "classified individually; this item is not among "
                      "them, and its shadow decision agrees with the "
                      "incumbent acceptance.")
            else:
                oc, co, ev = None, None, (
                    "post-hoc classification not found for this "
                    "disagreement in the trial report.")
        else:
            oc, co, ev = None, None, (
                "board row first committed after the shadow "
                "trial's scanned history (the trial scanned 63 "
                "schedule commits, through 2026-11-02): the board "
                "took it, but no audit or classification of later "
                "board decisions exists in the record.")
        cont = "none"
        if it["contention"]:
            c = it["contention"]
            cont = ("overlaps an active booking (lane %s, seat %s, "
                    "start %s UTC)" % (c["lane"], c["seat"], c["start"]))
        ctx = (
            "producer: %s; effect: write booking/%s/%s; resource: "
            "%s seat %s; start: %s UTC; planned duration: %s; "
            "check-by: %s; task: %s; contention: %s; policy facts: "
            "exclusive seats are single-driver; first booking wins "
            "ties; a booking past its check-by does not contend; "
            "same-lane overlaps are renewals"
            % (it["lane"], it["box"], it["seat"], it["box"],
               it["seat"], it["start"].strftime("%Y-%m-%d %H:%M"),
               it["planned_raw"], it["checkby_raw"] or "not stated",
               clean(it["what"]), cont))
        out.append({
            "source": "board-shadow",
            "order_ts": it["commit_ts"].isoformat(),
            "ts_basis": "git commit timestamp of the row's first "
                        "appearance in ~/agent-inbox schedule/",
            "context": ctx,
            "gold": "ALLOW",
            "operator_correct": oc,
            "correct_outcome": co,
            "correctness_evidence": ev,
            "source_pointer": {
                "file": "~/agent-inbox/schedule/%s.md" % it["box"],
                "locator": "git commit %s; row lane=%s seat=%s "
                           "start=%s" % (it["commit"], it["lane"],
                                         it["seat"],
                                         it["start"].strftime(
                                             "%Y-%m-%d %H:%M"))},
            "_key": key,
            "_bkey": (it["box"], it["seat"],
                      it["start"].strftime("%Y-%m-%d %H:%M")),
        })
    return out


# ---------------------------------------------------------------- jev
def jev_items():
    events = []
    ev_path = REPO / "tests/data/gpu-queue/events.jsonl"
    with ev_path.open(encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if line.strip():
                e = json.loads(line)
                e["_line"] = ln
                events.append(e)
    dispatches = [e for e in events if e.get("event") == "dispatch"]
    items = []
    for e in dispatches[:6]:
        ts = datetime.fromisoformat(e["ts"]).astimezone(timezone.utc)
        items.append({
            "source": "jev",
            "order_ts": ts.isoformat(),
            "ts_basis": "timestamp of the recorded gpu-queue "
                        "dispatch event this case renders",
            "context": ("GPU job-queue dispatch decision. Job %s "
                        "(%s), lane %s, attempt %d. Every previous "
                        "job in the record finished with exit 0; no "
                        "foreign work is using the GPU; the queue is "
                        "not halted." % (e["job"], e["name"], e["lane"],
                                         e["attempt"])),
            "gold": "ALLOW",
            "operator_correct": True,
            "correct_outcome": "ALLOW",
            "correctness_evidence": "tools/jev_experiment.py records "
                "this case class (real-dispatch) with truth 'allow': "
                "the successor rule dispatched these jobs and every "
                "previous job finished with exit 0.",
            "source_pointer": {
                "file": "tools/jev_experiment.py",
                "locator": "cases(): real-dispatch, from "
                           "tests/data/gpu-queue/events.jsonl line "
                           "%d (job %s)" % (e["_line"], e["job"])},
            "_key": ("jev", "real-dispatch", e["job"]),
        })
    extra = [
        ("fixture-hold", "HOLD",
         "GPU job-queue dispatch decision. The head job has no "
         "successor defined and the feeder that generates work is "
         "disabled, so dispatching it would strand the queue. "
         "(Reconstructed fixture scenario.)"),
        ("fixture-halt", "DENY",
         "GPU job-queue dispatch decision. The last two job starts "
         "failed within their grace period; the queue's rule is to "
         "halt dispatching after two consecutive start failures. "
         "(Reconstructed fixture scenario.)"),
        ("policy-spend", "HOLD",
         "A producer who is not the operator submits a proposal "
         "whose declared effects include spending from a shared "
         "budget. Policy requires an operator decision for spend "
         "effects."),
        ("policy-suspended", "DENY",
         "A producer whose standing is suspended submits a proposal "
         "to write a shared unit. Suspended producers are denied "
         "by policy."),
        ("policy-undeclared", "DENY",
         "A proposal declares only the write effect, but its "
         "request list also contains a send effect that was not "
         "declared. Undeclared effects are refused."),
    ]
    for cls, gold, text in extra:
        recon = cls.startswith("fixture")
        items.append({
            "source": "jev",
            "order_ts": "2026-10-28T00:00:00+00:00",
            "ts_basis": "era marker: the advisor experiment (SPEC "
                        "section 13) predates the 2026-11-02 proof "
                        "runs; no per-case timestamp is recorded",
            "context": text,
            "gold": gold,
            "operator_correct": True,
            "correct_outcome": gold,
            "correctness_evidence": "tools/jev_experiment.py records "
                "truth '%s' for case class %s%s." % (
                    {"ALLOW": "allow", "HOLD": "queue",
                     "DENY": "deny"}[gold], cls,
                    " (labelled reconstructed in the tool's docstring)"
                    if recon else " (a policy/1 case from the spec)"),
            "source_pointer": {"file": "tools/jev_experiment.py",
                               "locator": "cases(): %s" % cls},
            "_key": ("jev", cls),
        })
    return items


# ---------------------------------------------------------------- kernels
def load_log(rel):
    rows = []
    with (REPO / rel).open(encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if line.strip():
                r = json.loads(line)
                r["_line"] = ln
                rows.append(r)
    return rows


def render_requests(body):
    parts = []
    for req in body.get("requests") or []:
        verb, args = req.get("verb"), req.get("args") or []
        if verb == "notify":
            continue            # approval-notification mechanism
        if verb == "write" and args:
            if len(args) > 1 and isinstance(args[1], dict) \
                    and "seat" in args[1] and "start" in args[1]:
                v = args[1]
                st = datetime.fromtimestamp(int(v["start"]) * 60,
                                            timezone.utc)
                extra = ""
                if "end" in v:
                    mins = int(v["end"]) - int(v["start"])
                    extra = "; planned: %dm" % mins
                if "checkby" in v:
                    cb = datetime.fromtimestamp(
                        int(v["checkby"]) * 60, timezone.utc)
                    extra += "; check-by: %s" % cb.strftime(
                        "%Y-%m-%d %H:%M")
                parts.append("write booking/%s/%s start %s UTC%s"
                             % (v.get("box"), v.get("seat"),
                                st.strftime("%Y-%m-%d %H:%M"), extra))
            else:
                parts.append("write %s" % str(args[0])[:110])
        elif verb == "dispatch" and args and isinstance(args[0], dict):
            cmd = args[0].get("cmd")
            if isinstance(cmd, list):
                parts.append("shell: %s" % clean(" ".join(
                    str(x) for x in cmd), 130))
            else:
                parts.append("dispatch %s" % clean(str(args[0]), 110))
        else:
            parts.append("%s %s" % (verb, clean(str(args[0]), 90)
                                    if args else ""))
    return parts


def first_decisions(rows):
    """proposal_id -> (first decision row, [all decision rows],
    execution rows, gpu-policy sense value or None)."""
    dec, exe, sense = {}, {}, {}
    for r in rows:
        b = r.get("body") or {}
        if r.get("kind") == "decision":
            dec.setdefault(b.get("proposal_id"), []).append(r)
        elif r.get("kind") == "execution":
            exe.setdefault(b.get("proposal_id"), []).append(r)
        elif r.get("kind") == "sense" and b.get("name") == "gpu-policy":
            v = b.get("value") or {}
            if v.get("proposal_id"):
                sense[v["proposal_id"]] = v
    return dec, exe, sense


def kernel_items(rel, source, era_ts, era_basis, policy_facts,
                 evidence_true, enrich=None):
    rows = load_log(rel)
    dec, exe, sense = first_decisions(rows)
    items = []
    for pid, dlist in sorted(dec.items(),
                             key=lambda kv: kv[1][0]["seq"]):
        first = dlist[0]
        b = first["body"]
        gold = OUTCOME[b["outcome"]]
        rule = ("standing rule in force for this shape: yes"
                if b.get("decided_by") else
                "standing rule in force for this shape: none recorded")
        req = render_requests(b)
        if not req and pid in exe:
            applied = []
            for er in exe[pid]:
                for a in (er["body"].get("applied") or []):
                    if a.get("verb") == "write" and a.get("args"):
                        applied.append(str(a["args"][0])[:80])
            if applied:
                req = ["write targets (from the proposal's execution "
                       "record): %s" % ", ".join(applied[:4])]
        extra = enrich(pid, b, exe, sense) if enrich else ""
        ctx = ("producer: %s; class: %s; effects: %s; requests: %s; "
               "%s; policy facts: %s"
               % (b.get("producer"), b.get("class"),
                  ", ".join(b.get("effects") or []) or "none recorded",
                  "; ".join(req) if req else
                  "request detail not preserved in the decision entry",
                  rule, policy_facts))
        if extra:
            ctx = ctx.replace("; policy facts:", "; %s; policy facts:"
                              % extra)
        items.append({
            "source": source,
            "order_ts": era_ts,
            "ts_basis": era_basis,
            "context": ctx,
            "gold": gold,
            "operator_correct": True,
            "correct_outcome": gold,
            "correctness_evidence": evidence_true,
            "source_pointer": {
                "file": rel,
                "locator": "seq %d (line %d), proposal_id %s…; first "
                           "of %d decision entries for this proposal"
                           % (first["seq"], first["_line"], pid[:12],
                              len(dlist))},
            "_key": (source, pid),
            "_seq": first["seq"],
        })
    return items


PROOF_POLICY = ("policy/1: a non-operator producer's write, shell "
                "and notify effects are protected and require an "
                "operator decision; unprotected reads proceed")
GPU_POLICY = ("gpu-bridge-policy/1 governs the jacquard lane of the "
              "Thor gpu job-queue; the feeder stays off; each job "
              "declares one output artifact")


def gpu_enrich_factory(journal_rel):
    names = {}
    jp = REPO / journal_rel
    if jp.exists():
        for line in jp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                j = json.loads(line)
                aid = j.get("action_id", "")
                if "/" in aid and j.get("name"):
                    names[aid.split("/")[0]] = j["name"]

    def enrich(pid, b, exe, sense):
        parts = []
        name = names.get(pid)
        if pid in sense:
            name = sense[pid].get("name") or name
            reason = sense[pid].get("reason", "")
            shape = reason.split(":")[0].strip()
            if shape:
                parts.append("command shape: %s" % shape)
        if name:
            parts.append("job name: %s" % name)
        uses = b.get("uses") or []
        if not uses:
            for er in exe.get(pid, []):
                for a in (er["body"].get("applied") or []):
                    uses = uses or a.get("uses") or []
        if uses:
            parts.append("uses: %s" % ", ".join(str(u) for u in uses))
        return "; ".join(parts)
    return enrich


# ---------------------------------------------------------------- main
def main():
    items = []
    items += board_items()
    items += jev_items()

    proof_ev = ("docs/proof-run-2026-11-02.md, 'Disagreements, "
                "classified': Jacquard wrong: none observed; host "
                "wrong: none in this run.")
    items += kernel_items(
        "docs/proof-run/kernel.jsonl", "proof-run",
        "2026-11-02T12:00:00+00:00",
        "era marker: kernel logs carry sequence numbers, not "
        "timestamps; the run is dated 2026-11-02 in its report",
        PROOF_POLICY, proof_ev)

    proof2_ev = ("docs/proof-run-2-2026-11-02.md: 'Regretted rules: "
                 "none'; no decision in the run is classified wrong "
                 "by the report.")
    items += kernel_items(
        "docs/proof-run-2/kernel.jsonl", "proof-run-2",
        "2026-11-02T18:00:00+00:00",
        "era marker: kernel logs carry sequence numbers, not "
        "timestamps; the run is dated 2026-11-02 in its report and "
        "follows proof-run 1",
        PROOF_POLICY, proof2_ev)

    gpu_items = kernel_items(
        "docs/slice25/kernel.jsonl", "gpu-windows",
        "2026-11-03T03:00:00+00:00",
        "era marker: window 1 ran 2026-11-03 01:15-05:00 UTC "
        "(slice-22 report); window 2 followed the same day "
        "(slice-25 report); per-item split inside this source is "
        "by log seq (window 1: seq <= 90, window 2: seq >= 91)",
        GPU_POLICY,
        "docs/slice22-live-report.md and docs/slice25-live-report.md"
        ": Jacquard wrong 0 in window 2 and exactly 1 in window 1 "
        "(itemised separately in this battery); incumbent wrong: 0.",
        enrich=gpu_enrich_factory(
            "docs/slice25/kernel.jsonl.gpu-journal.jsonl"))
    # per-item era + correctness overrides for the gpu source
    for it in gpu_items:
        if it["_seq"] >= 91:
            it["order_ts"] = "2026-11-03T15:00:00+00:00"
        ctx = it["context"]
        if "jacquard-sentinel" in ctx and it["gold"] == "DENY" \
                and "feeder" in ctx:
            it["operator_correct"] = False
            it["correct_outcome"] = "ALLOW"
            it["correctness_evidence"] = (
                "docs/slice22-live-report.md, 'Disagreements': "
                "Jacquard wrong: 1 — the first sentinel submission "
                "was denied as a feeder shape because its command's "
                "prose note mentioned gpuq and the feeder and the "
                "bridge regex matched; the shape was tightened and "
                "the resubmitted sentinel was allowed and "
                "dispatched (the ALLOW item for jacquard-sentinel "
                "later in this same source).")
        elif "jacquard-bench-7" in ctx:
            it["operator_correct"] = None
            it["correct_outcome"] = None
            it["correctness_evidence"] = (
                "contested: docs/slice27-consumption-policy-v2.md "
                "reprices this submission HOLD under the raw v2 "
                "consumption policy (its job then failed — a true "
                "positive in the wasted-work sense) but the refined "
                "policy still exempts it, and the failure was a "
                "job-content error no consumption policy claims to "
                "catch. The record supports both readings.")
        elif "jacquard-sentinel-3" in ctx:
            it["operator_correct"] = None
            it["correct_outcome"] = None
            it["correctness_evidence"] = (
                "contested: docs/slice27-consumption-policy-v2.md "
                "reprices this submission HOLD under v2, but names "
                "it an honest blemish — it never dispatched, no GPU "
                "time was at stake, and it stands in the queue by "
                "design as the window's declared successor.")
    items += gpu_items

    # slice-30: config proposals kept; booking proposals deduped
    # against board items on (box, seat, start).
    board_keys = {it["_bkey"] for it in items
                  if it["source"] == "board-shadow"}
    # fallback dedup key: (normalised box, start). The slice-30
    # log calls the Orin "orin" where the board file is
    # jetson-orin.md, and records the governed seat where the
    # board row records the occupied seat (detached vs cpu), so
    # seat-exact matching misses real duplicates; (box, start)
    # is unique among the slice-30 bookings.
    def norm_box(b):
        return "jetson-orin" if b == "orin" else b
    board_keys_ns = {(norm_box(k[0]), k[2]) for k in board_keys}
    s30 = kernel_items(
        "docs/slice30/booking-log.jsonl", "slice30-booking",
        "2026-11-03T17:00:00+00:00",
        "era marker: the slice-30 deployment is dated 2026-11-03 "
        "in docs/slice30-device-matrix.md; its booking rows are "
        "timestamped 2026-11-03 17:15-19:45 in the log's senses",
        "policy/1: operator config writes proceed; booking-class "
        "writes by a non-operator producer carry protected effects "
        "(notify, write) and require an operator decision",
        "no audit or classification of these config decisions "
        "exists in the record",
        enrich=None)
    rows = load_log("docs/slice30/booking-log.jsonl")
    dec30, _, _ = first_decisions(rows)
    board_rows = {}
    for r in rows:
        b = r.get("body") or {}
        if r.get("kind") == "sense" and str(b.get("name", "")) \
                .startswith("board-row:"):
            board_rows[b["name"]] = b.get("value") or {}

    def s30_class(pid):
        d = dec30.get(pid)
        return d[0]["body"].get("class") if d else None

    kept, dupes = [], 0
    for it in s30:
        if s30_class(it["_key"][1]) == "config":
            it["operator_correct"] = None
            it["correct_outcome"] = None
            it["correctness_evidence"] = (
                "operator config write; no audit or classification "
                "of config decisions exists in the record.")
            kept.append(it)
            continue
        # booking-class: recover (box, seat, start) from its
        # board-row sense via the write target in its requests
        m = re.search(r"write booking/([a-z-]+)/([a-z-]+) start "
                      r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})",
                      it["context"])
        bkey = None
        if m:
            bkey = (m.group(1), m.group(2), m.group(3))
        if bkey and (bkey in board_keys or
                     (norm_box(bkey[0]), bkey[2]) in board_keys_ns):
            dupes += 1
            continue
        it["operator_correct"] = None
        it["correct_outcome"] = None
        it["correctness_evidence"] = (
            "slice-30 booking decision; no classification record; "
            "not matched to a board-shadow item.")
        kept.append(it)
    items += kept

    # ---- split by time
    for it in items:
        ts = datetime.fromisoformat(it["order_ts"])
        it["split"] = "diagnostic" if ts < BOUNDARY else "heldout"
    items.sort(key=lambda x: (x["order_ts"], x["source"],
                              x["id"] if "id" in x else ""))
    # ids in record order per source
    counters = Counter()
    for it in items:
        counters[it["source"]] += 1
        it["id"] = "e8-%s-%03d" % (it["source"],
                                   counters[it["source"]])
    order = ["id", "split", "source", "order_ts", "ts_basis",
             "context", "gold", "operator_correct",
             "correct_outcome", "correctness_evidence",
             "source_pointer"]
    clean_items = []
    for it in items:
        it = {k: v for k, v in it.items() if not k.startswith("_")}
        clean_items.append({k: it[k] for k in order})
    diag = [i for i in clean_items if i["split"] == "diagnostic"]
    held = [i for i in clean_items if i["split"] == "heldout"]
    for name, rows_out in (("diagnostic.jsonl", diag),
                           ("heldout.jsonl", held)):
        with (HERE / name).open("w", encoding="utf-8") as fh:
            for it in rows_out:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    write_battery_md(diag, held, clean_items, dupes)
    print("diagnostic", len(diag), Counter(i["gold"] for i in diag))
    print("heldout", len(held), Counter(i["gold"] for i in held))
    print("per source", Counter(i["source"] for i in clean_items))
    print("board dupes dropped", dupes)
    return 0


LEAK_WORDS = {"allow", "allowed", "allows", "hold", "held", "deny",
              "denied", "denies", "queue", "queued", "release",
              "released", "reject", "rejected", "approve",
              "approved", "refused", "refusal"}


def wilson_halfwidth(p, n, z=1.96):
    if n == 0:
        return 0.0
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return half, centre


def write_battery_md(diag, held, items_all, board_dupes):
    def bal(rows):
        c = Counter(i["gold"] for i in rows)
        return "ALLOW %d / HOLD %d / DENY %d" % (
            c["ALLOW"], c["HOLD"], c["DENY"])

    def src_table(rows):
        c = Counter(i["source"] for i in rows)
        return "\n".join("| %s | %d |" % (s, c[s])
                         for s in sorted(c))

    wrong = [i for i in items_all if i["operator_correct"] is False]
    nulls = [i for i in items_all if i["operator_correct"] is None]
    null_diag = sum(1 for i in diag if i["operator_correct"] is None)
    null_held = sum(1 for i in held if i["operator_correct"] is None)
    known_held = len(held) - null_held
    hw_base, _ = wilson_halfwidth(0.88, len(held)) if held else (0, 0)
    hw_mid, _ = wilson_halfwidth(0.50, len(held)) if held else (0, 0)
    hw_corr, _ = wilson_halfwidth(0.50, known_held) if known_held \
        else (0, 0)
    hits = [(it, w) for it in items_all for w in sorted(
        set(re.findall(r"[a-z]+", it["context"].lower()))
        & LEAK_WORDS)]
    hit_counts = Counter(w for _, w in hits)
    lines = []
    lines.append("# E8 battery — the custom decision model")
    lines.append("")
    lines.append("Curated by `curate.py` from Jacquard's own record "
                 "(inventory: `../E8-SOURCES.md`). Every number in "
                 "this file is computed from the assembled JSONL "
                 "files at curation time. The battery builder does "
                 "not patch any model; the scorer is "
                 "`score_decision.py`; the independent checks are "
                 "`verify_e8.py`.")
    lines.append("")
    lines.append("## The instrument")
    lines.append("")
    lines.append("One item = one recorded governance decision: a "
                 "compact canonical context (producer, effect "
                 "shape/verb, resource or target, queue/policy "
                 "state, stated facts) rendered only from facts "
                 "available at decision time, plus the recorded "
                 "outcome as gold (ALLOW / HOLD / DENY). For kernel "
                 "logs the item is the proposal's FIRST decision "
                 "entry (allow / queued / deny at submission); "
                 "later release/reject entries for the same "
                 "proposal are the queue's downstream, not separate "
                 "items. For the booking board the recorded outcome "
                 "is the incumbent's: the board took every row, so "
                 "board gold is ALLOW throughout, and the shadow "
                 "trial's contention computation is carried in the "
                 "context as queue state, not as gold.")
    lines.append("")
    lines.append("Two scores (see `score_decision.py`): "
                 "(a) agreement-with-operator, gold = the recorded "
                 "outcome; (b) agreement-with-correctness, on the "
                 "subset where `operator_correct` is known, gold = "
                 "`correct_outcome`. Learning the operator's "
                 "mistakes as faithfully as their judgement is a "
                 "finding, not a success. The custom model remains "
                 "a sense behind the provider seam; it advises, it "
                 "never decides.")
    lines.append("")
    lines.append("## Sources and counts")
    lines.append("")
    lines.append("| source | items |")
    lines.append("|---|---:|")
    tot = Counter(i["source"] for i in items_all)
    for s in sorted(tot):
        lines.append("| %s | %d |" % (s, tot[s]))
    lines.append("| **total** | **%d** |" % len(items_all))
    lines.append("")
    lines.append("Source notes (all counts above are the assembled "
                 "items, after the exclusions stated here):")
    lines.append("")
    lines.append("- `board-shadow` — the agent-inbox booking board "
                 "(`~/agent-inbox/schedule/*.md`, git history), "
                 "replayed with the shadow-trial method "
                 "(`tools/shadow_trial.py`): every booking row's "
                 "first appearance is one proposal; rows that are "
                 "retroactive notes (planned cell DONE at first "
                 "appearance) and rows with unparseable start or "
                 "duration are excluded, exactly as in the trial. "
                 "The trial window (commits through 2026-11-02) "
                 "reproduces the published trial's decided set; "
                 "later rows are the same instrument run over the "
                 "board's continuation. Rows first committed after "
                 "the trial's 63 scanned commits but before the "
                 "split boundary are diagnostic items whose "
                 "correctness is unclassified (null), not trial "
                 "items.")
    lines.append("- `jev` — `tools/jev_experiment.py` cases(6): six "
                 "real-dispatch cases rendered from "
                 "`tests/data/gpu-queue/events.jsonl`, two "
                 "reconstructed fixtures (labelled as such in the "
                 "context), three policy/1 cases from the spec. "
                 "The raw gpu-queue event stream itself is not "
                 "turned into items (see Weaknesses).")
    lines.append("- `proof-run` / `proof-run-2` — the frozen kernel "
                 "logs `docs/proof-run/kernel.jsonl` and "
                 "`docs/proof-run-2/kernel.jsonl`, one item per "
                 "distinct proposal (first decision).")
    lines.append("- `gpu-windows` — `docs/slice25/kernel.jsonl`, the "
                 "slice-22 live log continued through window 2 "
                 "(same log, seq 0-196). The slice-22 copy of the "
                 "same log is NOT read separately. Job names and "
                 "command shapes come from the log's `gpu-policy` "
                 "senses and the bridge journal.")
    lines.append("- `slice30-booking` — `docs/slice30/booking-log."
                 "jsonl`. Booking-class proposals whose board row "
                 "also appears as a `board-shadow` item are dropped "
                 "as contradictory-label duplicates of the same "
                 "underlying booking (kernel gold HOLD vs board "
                 "gold ALLOW): %d dropped. Matching is seat-exact "
                 "or by (normalised box, start): the slice-30 log "
                 "calls the Orin 'orin' where the board file is "
                 "jetson-orin.md, and records the governed seat "
                 "where the board row records the occupied seat. "
                 "The kept items are the operator config proposals "
                 "(authority writes and board-import writes) — a "
                 "distinct decision type from the board's own "
                 "acceptance of any row they import." % board_dupes)
    lines.append("- `docs/slice27` shadow rows re-price gpu-window "
                 "submissions; they are used only as correctness "
                 "evidence, never as separate items.")
    lines.append("")
    lines.append("## The time split")
    lines.append("")
    lines.append("**Boundary: 2026-11-03T00:00:00Z.** Items with a "
                 "recorded-at timestamp before the boundary are "
                 "diagnostic; at or after it, held-out. No item "
                 "appears in both splits (checked by "
                 "`verify_e8.py`), and the split is by time only — "
                 "no shuffling. Diagnostic range: %s to %s. "
                 "Held-out range: %s to %s."
                 % (min(i["order_ts"] for i in diag),
                    max(i["order_ts"] for i in diag),
                    min(i["order_ts"] for i in held),
                    max(i["order_ts"] for i in held)))
    lines.append("")
    lines.append("Timestamp basis per source: board items carry "
                 "the git commit timestamp of the row's first "
                 "appearance; jev real-dispatch items carry the "
                 "dispatch event's timestamp; kernel logs carry "
                 "sequence numbers, not clocks, so proof-run, "
                 "gpu-window and slice-30 items carry an era "
                 "timestamp at source-window granularity (the "
                 "window's dated report), flagged per item in "
                 "`ts_basis`. The boundary never cuts inside a "
                 "kernel-log source, so era assignment cannot move "
                 "an item across the split; within-source order is "
                 "the log sequence, preserved in the source "
                 "pointer.")
    lines.append("")
    lines.append("## Class balance")
    lines.append("")
    lines.append("| split | n | balance |")
    lines.append("|---|---:|---|")
    lines.append("| diagnostic | %d | %s |" % (len(diag), bal(diag)))
    lines.append("| heldout | %d | %s |" % (len(held), bal(held)))
    lines.append("")
    lines.append("Per-source counts per split:")
    lines.append("")
    lines.append("Diagnostic:")
    lines.append("")
    lines.append("| source | n |")
    lines.append("|---|---:|")
    lines.append(src_table(diag))
    lines.append("")
    lines.append("Held-out:")
    lines.append("")
    lines.append("| source | n |")
    lines.append("|---|---:|")
    lines.append(src_table(held))
    lines.append("")
    lines.append("## Incumbent-wrong cases (operator_correct: false)")
    lines.append("")
    lines.append("%d items. On these, the recorded outcome is the "
                 "operator/incumbent's mistake; the correctness "
                 "score (b) grades against `correct_outcome`, "
                 "not against gold." % len(wrong))
    lines.append("")
    for it in wrong:
        lines.append("- `%s` (split %s, source %s) — gold %s, "
                     "correct %s. Evidence: %s"
                     % (it["id"], it["split"], it["source"],
                        it["gold"], it["correct_outcome"],
                        it["correctness_evidence"]))
    lines.append("")
    lines.append("## Correctness coverage")
    lines.append("")
    lines.append("`operator_correct` is null on %d of %d items "
                 "(diagnostic %d, held-out %d), so score (b) is "
                 "computed on %d diagnostic and %d held-out items. "
                 "Null means the record genuinely does not settle "
                 "correctness: the shadow trial's policy-gap "
                 "disagreements (a concept is missing, not an "
                 "error), board rows committed after the 2026-11-02 "
                 "trial (no audit of later board decisions "
                 "exists), the two contested slice-27 consumption "
                 "repricings (raw v2 would hold; the refined "
                 "policy exempts or no GPU time was at stake), and "
                 "operator config writes (no classification "
                 "record). Each null item carries its reason in "
                 "`correctness_evidence`."
                 % (len(nulls), len(items_all), null_diag, null_held,
                    len(diag) - null_diag, known_held))
    lines.append("")
    lines.append("## Leakage scan")
    lines.append("")
    lines.append("Contexts were scanned for outcome-lexicon tokens "
                 "(allow/allowed, hold/held, deny/denied, "
                 "queue/queued, release/reject/approve forms and "
                 "refused/refusal). The scan rule and the "
                 "hard-fail verdict-phrase patterns live in "
                 "`verify_e8.py`; this section reports the soft "
                 "hits it must surface, not hide. Token counts "
                 "across all contexts: %s."
                 % (", ".join("%s x%d" % (w, c) for w, c
                              in sorted(hit_counts.items())) or
                    "none"))
    lines.append("")
    named = [i["id"] for i in items_all
             if "jacquard-held-1" in i["context"]]
    if named:
        lines.append("Borderline naming case, flagged plainly: %s "
                     "carries the job name 'jacquard-held-1' — a "
                     "name the window designers gave the job they "
                     "designed to be held. The name is a "
                     "decision-time fact in the record, but it is "
                     "outcome-suggestive; a coordinator may drop "
                     "this item rather than let a name teach the "
                     "answer." % ", ".join("`%s`" % n for n in named))
        lines.append("")
    lines.append("Known legitimate sources of those tokens: the "
                 "resource name 'gpu job-queue' / 'job-queue' and "
                 "queue-state descriptions (the queue is the "
                 "resource being governed, a neutral mention); "
                 "stated policy rules in the jev policy cases (e.g. "
                 "'Suspended producers are denied by policy' — the "
                 "rule is a decision-time fact, present in the "
                 "source text the experiment itself used); booking "
                 "task text written by lanes at booking time. No "
                 "context contains its item's outcome as a verdict "
                 "statement; `verify_e8.py` fails the battery if a "
                 "verdict-phrase pattern appears.")
    lines.append("")
    lines.append("## Known weaknesses")
    lines.append("")
    lines.append("- **DENY is rare in the diagnostic split** (%s). "
                 "The record's denials cluster in the gpu windows "
                 "(held-out). A patcher can learn ALLOW and HOLD "
                 "shapes from the diagnostic split but sees very "
                 "few denied shapes; held-out DENY performance "
                 "will rest on a handful of items."
                 % bal(diag))
    lines.append("- **HOLD is rare in the held-out split** (%s): "
                 "the later record is dominated by board "
                 "acceptances and operator config writes. Held-out "
                 "accuracy mostly measures ALLOW fidelity plus "
                 "the gpu windows' DENY/HOLD minority."
                 % bal(held))
    lines.append("- **Board gold is structurally uniform.** Every "
                 "board item's recorded outcome is ALLOW (the "
                 "incumbent took them all), so the board source "
                 "alone teaches 'always allow bookings'. The "
                 "signal that distinguishes the wrong acceptances "
                 "is the contention state in the context, and it "
                 "is graded by score (b), not score (a).")
    lines.append("- **Policy facts make many kernel items "
                 "rule-derivable.** Stating policy/1's protected "
                 "effects (or gpu-bridge-policy/1's shapes) in the "
                 "context means a model that reads the policy can "
                 "derive most first decisions. That is the nature "
                 "of the recorded decisions — the jev cases have "
                 "the same property — and it is why the "
                 "correctness split and the contention items carry "
                 "the experiment's weight.")
    lines.append("- **Standing-rule state is summarised, not "
                 "reconstructed.** The context states whether a "
                 "standing rule was in force for the shape (from "
                 "the decision entry's `decided_by`); the rule's "
                 "own history is not rendered. Two proof-run-2 "
                 "shapes are near-identical across sessions with "
                 "different outcomes, distinguished in the context "
                 "only by that field.")
    lines.append("- **Contexts the record does not preserve.** "
                 "Fast-path read decisions and most gpu-window "
                 "allow decisions carry no request detail in their "
                 "decision entries; their contexts are rendered "
                 "from class, effects, job name (journal / "
                 "gpu-policy senses) and declared uses where the "
                 "log records them, and say so where it does not. "
                 "File contents of writes are never rendered "
                 "(targets and byte counts only).")
    lines.append("- **The raw gpu-queue stream is excluded.** "
                 "tests/data/gpu-queue records ~1,637 dispatches, "
                 "all incumbent-allowed, with no per-item Jacquard "
                 "decision; turning them into items would flood "
                 "the battery with uniform ALLOW filler. Only the "
                 "jev experiment's curated rendering of its first "
                 "six dispatches is included.")
    lines.append("- **Era timestamps.** Kernel-log items are "
                 "placed by their source window's dated report, "
                 "not by a per-item clock (the logs have none). "
                 "The time split is exact at source granularity "
                 "and at commit/event granularity for board and "
                 "jev items; it is not a per-second ordering "
                 "inside a kernel log.")
    lines.append("- **Fixture/policy jev cases are not fleet "
                 "decisions.** Two are labelled reconstructed "
                 "fixtures and three are spec policy cases; they "
                 "are part of the repo's recorded experiment, "
                 "kept because E8-SOURCES lists the experiment as "
                 "a source, and flagged in each item's evidence.")
    lines.append("")
    lines.append("## Noise band (held-out)")
    lines.append("")
    lines.append("Held-out n = %d. A single accuracy figure on "
                 "this split carries a Wilson 95%% half-width of "
                 "about +/-%.1f points around the shadow-trial "
                 "baseline rate of 88%%, and +/-%.1f points at "
                 "50%%. Differences smaller than that are inside "
                 "the noise band and must not be reported as "
                 "effects. The held-out correctness subset is "
                 "smaller still (n = %d known-correctness items; "
                 "Wilson half-width at 50%% about +/-%.1f points) "
                 "— score (b) on held-out data can detect only "
                 "gross disagreement with correctness, not fine "
                 "weighting differences."
                 % (len(held), hw_base * 100, hw_mid * 100,
                    known_held, hw_corr * 100))
    lines.append("")
    (HERE / "BATTERY.md").write_text("\n".join(lines) + "\n",
                                     encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
