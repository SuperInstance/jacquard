"""Shared operator presentation (Phase 5, slice 13).

The text the operator sees — the decision-queue listing, the
per-proposal replay, the status summary, and the one-line
decision outcomes — is rendered here, once. The operator CLI
(tools/jq.py) prints exactly these strings and the network
service (service.py) returns exactly these strings, so the two
surfaces cannot drift: queue presentation and replay are
byte-for-byte identical between CLI and service by
construction, and tests/test_service.py proves it against the
CLI run as a subprocess.

Every function takes a Sequencer and returns text WITHOUT a
trailing newline (callers that print add it; the service
returns text with the newline the CLI would have emitted, so
`service_text == cli_stdout` holds byte-for-byte).
"""


def binding_hash(seq, proposal_id):
    """The hash of the decision entry that queued this item —
    the value an approval binds to."""
    for entry in seq.log.entries:
        body = entry["body"]
        if entry["kind"] == "decision" \
                and body.get("proposal_id") == proposal_id \
                and body.get("outcome") == "queued":
            return entry["hash"]
    return None


def _is_authority_tie(seq, body):
    """A booking item is an authority tie when its booking
    instance's latest taken transition event is "tie" (the
    challenger waits; the incumbent holds the interval)."""
    booking_id = None
    for request in body.get("requests", []):
        if request.get("verb") == "write" \
                and request["args"][0].startswith("booking/") \
                and isinstance(request["args"][1], dict) \
                and "id" in request["args"][1]:
            booking_id = request["args"][1]["id"]
    if booking_id is None:
        return False
    instance = "booking:%s" % booking_id
    latest_taken = None
    for entry in seq.log.entries:
        entry_body = entry["body"]
        if entry["kind"] == "transition" \
                and entry_body.get("instance") == instance \
                and entry_body.get("outcome") == "taken":
            latest_taken = entry_body.get("event")
    return latest_taken == "tie"


def render_queue(seq):
    order = seq.decision_order()
    if not order:
        return "decision queue: empty"
    lines = ["decision queue: %d item(s), presentation order"
             % len(order)]
    for proposal_id in order:
        body = seq.state.decision_queue[proposal_id]
        lines.append("- %s" % proposal_id)
        lines.append("    producer %s · class %s · effects %s"
                     % (body["producer"], body.get("class", "work"),
                        ", ".join(body.get("effects", []))))
        lines.append("    binding %s" % binding_hash(seq, proposal_id))
        wait = body.get("wait")
        if isinstance(wait, dict):
            lines.append("    waiting: %s (deadline seq %s)"
                         % (wait.get("guard"), wait.get("deadline_seq")))
        if _is_authority_tie(seq, body):
            lines.append("    authority tie")
    return "\n".join(lines)


def queue_items(seq):
    """Structured form of the queue, for JSON consumers. The
    `binding` values are the same hashes render_queue shows."""
    items = []
    for proposal_id in seq.decision_order():
        body = seq.state.decision_queue[proposal_id]
        item = {
            "proposal_id": proposal_id,
            "producer": body["producer"],
            "class": body.get("class", "work"),
            "effects": list(body.get("effects", [])),
            "binding": binding_hash(seq, proposal_id),
        }
        wait = body.get("wait")
        if isinstance(wait, dict):
            item["wait"] = wait
        if _is_authority_tie(seq, body):
            item["authority_tie"] = True
        items.append(item)
    return items


def decide_one(seq, action, proposal_id, expect_hash):
    """One hash-bound decision. Returns (ok, line) where `line`
    is exactly the line the CLI prints. A binding mismatch (or
    an item that is not queued) changes nothing."""
    current = binding_hash(seq, proposal_id)
    if proposal_id not in seq.state.decision_queue:
        return False, "FAIL %s: not in the decision queue" % proposal_id
    if current != expect_hash:
        return False, ("FAIL %s: binding mismatch (item changed since "
                       "presentation; current binding %s)"
                       % (proposal_id, current))
    if action == "approve":
        seq.release_queued(proposal_id, "operator")
        return True, "approved %s" % proposal_id
    else:
        seq.reject_queued(proposal_id, "operator")
        return True, "denied %s" % proposal_id


def render_replay(seq, proposal_id):
    """Returns (found, text). When nothing matches, text is the
    CLI's failure line and found is False."""
    lines = ["replay of proposal %s" % proposal_id]
    found = False
    for entry in seq.log.entries:
        body = entry["body"]
        kind = entry["kind"]
        if kind == "decision" and body.get("proposal_id") == proposal_id:
            found = True
            extra = ""
            if body.get("decided_by"):
                extra = " (decided_by %s; policy would: %s)" \
                    % (body["decided_by"], body.get("policy_outcome"))
            lines.append("  seq %d decision: %s by %s%s — reasons: %s"
                         % (entry["seq"], body["outcome"],
                            body["policy_version"], extra,
                            ", ".join(body.get("reasons", [])) or "none"))
        elif kind == "execution" and body.get("proposal_id") == proposal_id:
            found = True
            verbs = [item["verb"] for item in body.get("applied", [])]
            lines.append("  seq %d execution: applied %s"
                         % (entry["seq"], ", ".join(verbs) or "nothing"))
        elif kind == "transition" and (
                body.get("instance") == proposal_id
                or body.get("instance") == "approval:" + proposal_id
                or body.get("instance", "").startswith(proposal_id + "/")):
            found = True
            lines.append("  seq %d transition: %s %s -%s-> %s (%s)"
                         % (entry["seq"], body["machine"],
                            body["from"], body["event"], body["to"],
                            body["outcome"]))
    if not found:
        return False, "replay: no entries for proposal %s" % proposal_id
    state = seq.machine_instance_state(proposal_id)
    if state:
        lines.append("  final proposal state: %s" % state)
    return True, "\n".join(lines)


def render_status(seq):
    lines = [
        "entries %d · state %s" % (len(seq.log.entries),
                                   seq.state.state_hash()),
        "decision queue: %d item(s)" % len(seq.state.decision_queue),
        "units %d · definitions %d · machines %d · rules %d"
        % (len(seq.state.units), len(seq.state.dictionary),
           len(seq.state.machines), len(seq.state.rules)),
    ]
    return "\n".join(lines)


def status_data(seq):
    return {
        "entries": len(seq.log.entries),
        "state_hash": seq.state.state_hash(),
        "queue": len(seq.state.decision_queue),
        "units": len(seq.state.units),
        "definitions": len(seq.state.dictionary),
        "machines": len(seq.state.machines),
        "rules": len(seq.state.rules),
    }


def seed_demo(seq, log_label=""):
    """The demo seed, shared by the CLI and the service.
    Returns (ok, payload): on success payload is the dict the
    CLI prints as JSON; on refusal payload is the failure line
    (the CLI's exact wording) and nothing was changed."""
    from . import install_lifecycles, make_envelope
    if seq.log.entries:
        return False, ("FAIL seed-demo: log %s already has %d entries; "
                       "seed-demo needs a fresh log (delete it or pick a "
                       "new path). Nothing was changed."
                       % (log_label, len(seq.log.entries)))
    install_lifecycles(seq)
    queued_a = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "deploy done"]}]},
        ["notify"], "demo-a"))
    queued_b = seq.submit(make_envelope(
        "bob", "proposal",
        {"requests": [{"verb": "spend", "args": ["compute", 10]}]},
        ["spend"], "demo-b"))
    dispatched = seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "dispatch", "args": [{
            "cmd": ["python3", "-c", "print('drill-ran')"],
            "compensate": ["python3", "-c",
                           "print('drill-undone')"]}]}]},
        ["dispatch"], "demo-c"))
    return True, {
        "queued": {queued_a["proposal_id"]: binding_hash(
            seq, queued_a["proposal_id"]),
                   queued_b["proposal_id"]: binding_hash(
                       seq, queued_b["proposal_id"])},
        "dispatched": dispatched["proposal_id"],
        "action": dispatched["proposal_id"] + "/action-0"}
