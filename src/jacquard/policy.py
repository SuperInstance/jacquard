"""The policy gate (SPEC section 7).

One small table, versioned. The gate reads standing, the
computed effect set, and the producer record. It never reads a
model output: the record gates; advisors advise. Denials,
queueing, and faults are entries in the log, not exceptions
thrown away.

policy/1:
  - a producer whose standing is suspended is denied;
  - a proposal whose effects include send, notify, spend, or
    irreversible goes to the decision queue, unless the producer
    is the operator;
  - anything else is allowed.
"""
POLICY_VERSION = "policy/1"
PROTECTED_EFFECTS = ("send", "notify", "spend", "irreversible")


def decide(producer, kind, effects, record_view, standing):
    """-> (outcome, reasons). outcome in allow | deny | queue."""
    if standing and standing.get("status") == "suspended":
        return ("deny", ["producer-suspended"])
    protected = sorted(set(effects) & set(PROTECTED_EFFECTS))
    if protected and producer != "operator":
        return ("queue", ["protected-effect:%s" % verb for verb in protected])
    return ("allow", [])
