"""Producer records: pure projections of the log (SPEC section 2).

Any component that needs history reads it here. A producer record
aggregates, per class of work, the decisions and executions that
mention that producer. Output and use counts feed the
output-use reading: what fraction of a producer's outputs were
ever used by anyone.
"""


def _bucket(records_map, producer, cls):
    return records_map.setdefault(producer, {}).setdefault(cls, {
        "submissions": 0, "allowed": 0, "denied": 0, "queued": 0,
        "faults": 0, "executions": 0})


def records(entries):
    out = {}
    for entry in entries:
        body = entry["body"]
        producer = body.get("producer")
        if producer is None:
            continue
        if entry["kind"] == "definition":
            bucket = _bucket(out, producer, "definition")
            bucket["submissions"] += 1
            bucket["allowed"] += 1
        elif entry["kind"] == "decision":
            bucket = _bucket(out, producer, body.get("class", "work"))
            bucket["submissions"] += 1
            outcome = body.get("outcome")
            if outcome == "allow":
                bucket["allowed"] += 1
            elif outcome == "deny":
                bucket["denied"] += 1
            elif outcome == "queued":
                bucket["queued"] += 1
            if body.get("fault"):
                bucket["faults"] += 1
        elif entry["kind"] == "execution":
            bucket = _bucket(out, producer, body.get("class", "work"))
            bucket["executions"] += 1
    return out


def output_ids(entries, producer):
    ids = set()
    for entry in entries:
        if entry["kind"] != "execution":
            continue
        if entry["body"].get("producer") != producer:
            continue
        for applied in entry["body"].get("applied", []):
            for output_id in applied.get("outputs", []):
                ids.add(output_id)
    return ids


def outputs_and_uses(entries, producer):
    """(outputs, uses): outputs produced by `producer`, and how
    many of them were ever referenced by a recorded use."""
    produced = output_ids(entries, producer)
    used = set()
    for entry in entries:
        if entry["kind"] != "execution":
            continue
        for used_id in entry["body"].get("uses", []):
            if used_id in produced:
                used.add(used_id)
    return (len(produced), len(used))


def output_use_ratio(entries, producer):
    outputs, uses = outputs_and_uses(entries, producer)
    if outputs == 0:
        return None
    return uses / outputs
