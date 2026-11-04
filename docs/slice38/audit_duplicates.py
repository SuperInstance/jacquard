#!/usr/bin/env python3
"""Duplicate audit over the live deployments' kernel logs
(slice 38, spec 0.7 section 3.1).

Read-only. For each log: group `decision` entries by
proposal id and count SUBMISSION decisions -- the first
decision recorded for a submission, excluding operator
decisions (entries carrying releases / rejects / expires)
and wait-pump re-decision records (refusals whose reasons
start "wait-guard-refused:" or "wait-expired:", which are
the pump re-recording an undecided item, a known shape of
the 0.6 kernel, counted separately). A proposal id with
more than one submission decision is a landed duplicate of
exactly the kind SPEC 3.1 now makes impossible. Execution
entries are grouped the same way: more than one execution
per proposal id means an effect ran twice.

Usage: audit_duplicates.py LABEL=PATH [LABEL=PATH ...]
Output: one JSON object per log on stdout.
"""
import json
import sys
from collections import Counter, defaultdict


def audit(path):
    entries = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    submissions = defaultdict(list)
    operator_decisions = 0
    wait_records = 0
    for entry in entries:
        if entry["kind"] != "decision":
            continue
        body = entry["body"]
        pid = body.get("proposal_id")
        if pid is None:
            continue
        if any(k in body for k in ("releases", "rejects", "expires")):
            operator_decisions += 1
            continue
        reasons = body.get("reasons") or []
        if any(isinstance(r, str) and
               r.startswith(("wait-guard-refused:", "wait-expired:"))
               for r in reasons):
            wait_records += 1
            continue
        submissions[pid].append(body.get("outcome"))
    executions = Counter(
        entry["body"].get("proposal_id")
        for entry in entries if entry["kind"] == "execution")
    executions.pop(None, None)
    dup_decisions = {pid: outcomes for pid, outcomes
                     in submissions.items() if len(outcomes) > 1}
    dup_executions = {pid: n for pid, n in executions.items() if n > 1}
    return {
        "entries": len(entries),
        "proposals_with_submission_decision": len(submissions),
        "operator_decisions": operator_decisions,
        "wait_pump_records": wait_records,
        "duplicate_submission_decisions": dup_decisions,
        "executions": sum(executions.values()),
        "duplicate_executions": dup_executions,
    }


def main():
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        result = audit(path)
        result["log"] = label
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
