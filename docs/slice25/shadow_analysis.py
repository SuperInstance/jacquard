#!/usr/bin/env python3
"""Phase 9 slice 25 — SHADOW consumption-policy analysis.

Evidence only: nothing here changes live behaviour. Scores the
policy defined in the window-2 opening record over both live
windows' submission streams, replayed from the log alone:

  A submission WOULD have been held (instead of allowed) iff
  (a) its declared output has no declared consumer in the log
      at submission time (no earlier execution's uses list
      names it), and
  (b) its producer's trailing output-use ratio — over that
      producer's outputs whose completions are recorded BEFORE
      the submission in log order, counting a use only when
      the using execution is also recorded before it — was
      < 50%. A producer with no recorded completions yet is
      exempt (no track record).

Scoring is strictly causal: a shadow replay that prices a
submission with knowledge from later in the log would be
lookahead, not evidence. (The actual fates, used only for
classification, are of course read from the whole log.)

Denied and actually-held submissions are outside the policy's
scope (it speaks only to allows). Each would-hold is
classified by the output's actual fate: completed and unused
= true positive; completed and used = false positive; the job
failed (wasted GPU time, no output) = true positive (wasted
work); never completed = no GPU time at stake. A refinement
that exempts submissions which themselves declare a consumed
input is scored alongside.
"""
import json
import sys
from collections import defaultdict

BP_THRESHOLD = 5000  # 50%


def main(path):
    entries = [json.loads(l) for l in open(path)]

    # Submission stream: proposal envelopes are not entries;
    # submissions are identified by their first decision entry
    # (class gpu-bench), in log order.
    submissions = []
    seen = set()
    for e in entries:
        if e["kind"] == "decision" and e["body"].get("class") == "gpu-bench":
            pid = e["body"]["proposal_id"]
            if pid in seen:
                continue
            seen.add(pid)
            submissions.append({
                "seq": e["seq"], "proposal_id": pid,
                "producer": e["body"]["producer"],
                "outcome": e["body"]["outcome"]})

    # Declared outputs + uses per proposal, from executions.
    outputs_of = {}
    uses_of = {}
    for e in entries:
        if e["kind"] != "execution":
            continue
        pid = e["body"].get("proposal_id")
        outs = []
        for item in e["body"].get("applied", []):
            outs.extend(item.get("outputs", []))
        if outs:
            outputs_of[pid] = outs
        uses_of[pid] = list(e["body"].get("uses", []))

    # Names, from the bridge's gpu-policy sense entries.
    names = {}
    for e in entries:
        if e["kind"] == "sense" and e["body"].get("name") == "gpu-policy":
            v = e["body"]["value"]
            names[v["proposal_id"]] = v.get("name")

    # Completion events in log order: (seq, proposal_id).
    completions = []
    final_status = {}
    for e in entries:
        if e["kind"] == "sense" and e["body"].get("name") == "gpu-outcome":
            v = e["body"]["value"]
            aid = v["action_id"]
            pid = aid.split("/")[0]
            completions.append((e["seq"], pid, v["status"]))
            final_status[pid] = v["status"]

    # Every use ever recorded (for fate classification), and
    # uses by execution seq (for causal scoring).
    used_outputs = set()
    uses_by_seq = []
    for u in uses_of.values():
        used_outputs.update(u)
    for e in entries:
        if e["kind"] == "execution":
            uses_by_seq.append((e["seq"],
                                set(e["body"].get("uses", []))))

    # Names: the bridge journal names every dispatched job;
    # gpu-policy sense entries name the rest.
    journal = path + ".gpu-journal.jsonl"
    try:
        for line in open(journal):
            rec = json.loads(line)
            names[rec["action_id"].split("/")[0]] = rec["name"]
    except FileNotFoundError:
        pass

    def trailing_ratio_bp(producer, before_seq):
        done = {pid for (s, pid, st) in completions
                if s < before_seq and st == "completed"}
        outs = []
        for sub in submissions:
            if sub["producer"] == producer and sub["proposal_id"] in done:
                outs.extend(outputs_of.get(sub["proposal_id"], []))
        if not outs:
            return None
        used_so_far = set()
        for (s, us) in uses_by_seq:
            if s < before_seq:
                used_so_far.update(us)
        used = [o for o in outs if o in used_so_far]
        return round(10000 * len(used) / len(outs))

    rows = []
    for sub in submissions:
        pid = sub["proposal_id"]
        out = (outputs_of.get(pid) or [None])[0]
        ratio = trailing_ratio_bp(sub["producer"], sub["seq"])
        has_consumer = False
        if out:
            for (s, us) in uses_by_seq:
                if s < sub["seq"] and out in us:
                    has_consumer = True
                    break
        would_hold = (sub["outcome"] == "allow" and out is not None
                      and not has_consumer and ratio is not None
                      and ratio < BP_THRESHOLD)
        refinement_exempt = bool(uses_of.get(pid))
        fate = final_status.get(pid, "never-dispatched")
        if not would_hold:
            cls = "no-change"
        elif fate == "completed" and out in used_outputs:
            cls = "false-positive"
        elif fate == "completed":
            cls = "true-positive"
        elif fate == "failed":
            cls = "true-positive (wasted work)"
        else:
            cls = "no GPU time at stake"
        rows.append({
            "seq": sub["seq"], "name": names.get(pid, pid[:8]),
            "producer": sub["producer"], "outcome": sub["outcome"],
            "output": out, "uses": uses_of.get(pid, []),
            "trailing_ratio_bp": ratio,
            "would_hold": would_hold,
            "would_hold_refined": would_hold and not refinement_exempt,
            "fate": fate, "classification": cls})

    print(json.dumps(rows, indent=1))
    tp = sum(1 for r in rows if r["classification"].startswith("true-positive"))
    fp = sum(1 for r in rows if r["classification"] == "false-positive")
    ns = sum(1 for r in rows if r["classification"] == "no GPU time at stake")
    wh = sum(1 for r in rows if r["would_hold"])
    whr = sum(1 for r in rows if r["would_hold_refined"])
    print("SUMMARY would_hold=%d refined=%d true_positive=%d "
          "false_positive=%d no_stake=%d" % (wh, whr, tp, fp, ns),
          file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
