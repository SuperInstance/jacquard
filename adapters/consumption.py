"""Consumption policy v2 (Phase 10, slice 27).

The pricing core for consumption-aware governance of a job
class, as one implementation shared by the shadow analysis
(docs/slice27/shadow_analysis_v2.py) and the gpu-queue
bridge's optional consumption gate (adapters/gpu_queue.py),
so the shadow scores and any live behaviour can never drift
apart semantically.

v2 fixes the two gaps the Phase 9 shadow analysis named in
its own v1 semantics:

1. **Promise flattery.** v1's trailing use-ratio counted a
   use the moment a consuming job DECLARED it (its execution
   entry, recorded at submission/dispatch), so a promise
   lifted the producer's ratio before the consuming job had
   run — and the flattery stood even if that job then failed
   (the bench-7 case). v2 counts a use only when the
   consuming job's COMPLETION is recorded in the log: the
   consumer ran, read the output, and finished. A failed or
   never-run consumer contributes nothing.

2. **Cold start.** v1 simply exempted a producer with no
   recorded completions — an invisible, unbounded exemption
   that leaves the policy blind exactly when a new producer
   is most prolific. v2 replaces it with an EXEMPTION
   BUDGET, claimed as exemptions in the accounting: while a
   producer's completed-output count is below the budget,
   its submissions are exempt from a consumption hold, and
   every such pricing is recorded as a claim (the shadow
   rows and, live, the per-item `gpu-policy` sense entry),
   so the fleet can see exactly how much unpriced production
   the budget bought. Once the budget is exhausted the
   ratio rules — and by construction the ratio is then
   defined (the budget is denominated in completed outputs,
   so it drains only as evidence lands; a producer whose
   jobs are still in flight keeps its exemption, which is
   the honest state: there is nothing to price on yet).

Semantics (all readings strictly causal — a submission at
log position S is priced only on entries before S):

- A producer's completed outputs at S: the declared outputs
  of its submissions whose producing job's completion
  (`gpu-outcome` sense entry, status completed) is recorded
  before S.
- A completed output counts as USED at S iff some job whose
  completion is also recorded before S named it in its
  execution entry's `uses` list.
- ratio_bp = 10000 * used / completed_outputs (None when
  the producer has no completed outputs at S).
- A submission WOULD BE HELD iff it was (or would be)
  allowed, declares an output, that output has no declared
  consumer in any earlier execution entry (v1's condition
  (a), retained unchanged — a named future consumer is a
  commitment the record later grades through this same
  ratio), the exemption budget is exhausted, and
  ratio_bp < threshold_bp.

The refinement from v1 is retained alongside: a submission
that itself declares consumed inputs is reported separately
(would_hold_refined), because a consuming job is part of
the demand the policy exists to protect.
"""
import json
from collections import defaultdict

BP_THRESHOLD = 5000      # 50%: the v1 threshold, carried as data
EXEMPTION_BUDGET = 3     # completed outputs of grace per producer


def streams(entries, job_class):
    """The projections the policy reads, from the log alone:
    submissions (first decision per proposal, in log order),
    declared outputs and uses per proposal, and completion
    events in log order."""
    submissions = []
    seen = set()
    for e in entries:
        if e["kind"] == "decision" \
                and e["body"].get("class") == job_class:
            pid = e["body"]["proposal_id"]
            if pid in seen:
                continue
            seen.add(pid)
            submissions.append({
                "seq": e["seq"], "proposal_id": pid,
                "producer": e["body"]["producer"],
                "outcome": e["body"]["outcome"]})
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
    completions = []       # (seq, proposal_id, status)
    final_status = {}
    for e in entries:
        if e["kind"] == "sense" \
                and e["body"].get("name") == "gpu-outcome":
            v = e["body"]["value"]
            pid = v["action_id"].split("/")[0]
            completions.append((e["seq"], pid, v["status"]))
            final_status[pid] = v["status"]
    return submissions, outputs_of, uses_of, completions, final_status


def _completed(entries, completions, before_seq):
    return {pid for (s, pid, st) in completions
            if s < before_seq and st == "completed"}


def _producer_outputs(submissions, outputs_of, producer, done):
    outs = []
    for sub in submissions:
        if sub["producer"] == producer \
                and sub["proposal_id"] in done:
            outs.extend(outputs_of.get(sub["proposal_id"], []))
    return outs


def completed_output_count(submissions, outputs_of, completions,
                           producer, before_seq):
    done = _completed(None, completions, before_seq)
    return len(_producer_outputs(submissions, outputs_of,
                                 producer, done))


def ratio_bp(submissions, outputs_of, uses_of, completions,
             producer, before_seq):
    """The v2 trailing use-ratio in basis points, or None
    when the producer has no completed outputs yet. A use
    counts only when the consuming job's completion is
    recorded before `before_seq` (v2 fix 1)."""
    done = _completed(None, completions, before_seq)
    outs = _producer_outputs(submissions, outputs_of,
                             producer, done)
    if not outs:
        return None
    used_ids = set()
    for pid in done:
        used_ids.update(uses_of.get(pid, []))
    used = [o for o in outs if o in used_ids]
    return round(10000 * len(used) / len(outs))


def price_one(entries, job_class, producer, output,
              threshold_bp=BP_THRESHOLD,
              budget=EXEMPTION_BUDGET):
    """Price a single about-to-be-decided submission of
    `job_class` against the log as it stands (the bridge
    gate's form of the same arithmetic as price_stream).
    `output` is the submission's declared output (or None).
    Returns the pricing record the bridge writes into its
    per-item sense entry, including whether an exemption was
    claimed against the producer's budget."""
    submissions, outputs_of, uses_of, completions, _ = \
        streams(entries, job_class)
    head = (entries[-1]["seq"] + 1) if entries else 0
    ratio = ratio_bp(submissions, outputs_of, uses_of,
                     completions, producer, head)
    n_done = completed_output_count(submissions, outputs_of,
                                    completions, producer, head)
    budget_exempt = n_done < budget
    has_consumer = False
    if output:
        for e in entries:
            if e["kind"] == "execution" \
                    and output in e["body"].get("uses", []):
                has_consumer = True
                break
    would_hold = (
        output is not None and not has_consumer
        and not budget_exempt and ratio is not None
        and ratio < threshold_bp)
    return {
        "ratio_bp": ratio,
        "completed_outputs": n_done,
        "budget": budget,
        "budget_exempt": budget_exempt,
        "exemption_claimed": budget_exempt,
        "has_declared_consumer": has_consumer,
        "threshold_bp": threshold_bp,
        "would_hold": would_hold,
    }


def price_stream(entries, job_class, names=None,
                 threshold_bp=BP_THRESHOLD,
                 budget=EXEMPTION_BUDGET):
    """Price every submission of `job_class` in the log,
    strictly causally, and classify would-holds by the
    outputs' actual fates (read from the whole log, for
    classification only). This is the shadow scorer; the
    bridge gate uses the same projections and arithmetic
    for one submission at decision time."""
    submissions, outputs_of, uses_of, completions, \
        final_status = streams(entries, job_class)
    names = names or {}
    uses_by_seq = []
    for e in entries:
        if e["kind"] == "execution":
            uses_by_seq.append(
                (e["seq"], set(e["body"].get("uses", [])),
                 e["body"].get("proposal_id")))
    used_outputs = set()
    for u in uses_of.values():
        used_outputs.update(u)

    rows = []
    claims = defaultdict(int)
    for sub in submissions:
        pid = sub["proposal_id"]
        out = (outputs_of.get(pid) or [None])[0]
        ratio = ratio_bp(submissions, outputs_of, uses_of,
                         completions, sub["producer"], sub["seq"])
        n_done = completed_output_count(
            submissions, outputs_of, completions,
            sub["producer"], sub["seq"])
        budget_exempt = n_done < budget
        if budget_exempt and sub["outcome"] == "allow" \
                and out is not None:
            # a claim is an exemption actually spent: the
            # policy waved through a priced submission it
            # could otherwise have held
            claims[sub["producer"]] += 1
        has_consumer = False
        if out:
            for (s, us, _pid) in uses_by_seq:
                if s < sub["seq"] and out in us:
                    has_consumer = True
                    break
        would_hold = (
            sub["outcome"] == "allow" and out is not None
            and not has_consumer and not budget_exempt
            and ratio is not None and ratio < threshold_bp)
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
            "seq": sub["seq"],
            "name": names.get(pid, pid[:8]),
            "producer": sub["producer"],
            "outcome": sub["outcome"],
            "output": out,
            "uses": uses_of.get(pid, []),
            "trailing_ratio_bp": ratio,
            "completed_outputs": n_done,
            "budget_exempt": budget_exempt,
            "would_hold": would_hold,
            "would_hold_refined": would_hold
            and not refinement_exempt,
            "fate": fate,
            "classification": cls})
    return rows, dict(claims)


def load_names(entries, journal_path=None):
    """Job names from the log's gpu-policy sense entries,
    plus the bridge journal when available (as v1)."""
    names = {}
    for e in entries:
        if e["kind"] == "sense" \
                and e["body"].get("name") == "gpu-policy":
            v = e["body"]["value"]
            names[v["proposal_id"]] = v.get("name")
    if journal_path:
        try:
            for line in open(journal_path):
                rec = json.loads(line)
                names[rec["action_id"].split("/")[0]] = rec["name"]
        except FileNotFoundError:
            pass
    return names
