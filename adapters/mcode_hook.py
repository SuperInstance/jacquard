#!/usr/bin/env python3
"""mcode_hook — the Jacquard adapter for MCode (Phase 14, slice 39).

Registered as an MCode `PreToolUse` hook through the
MINIMAX plugin surface (see adapters/mcode/). For every tool
call MCode is about to make, this process:

1. reads the hook event JSON on stdin (MCode sends
   snake_case spellings; camelCase is also accepted),
2. translates tool + arguments into a Jacquard proposal in the
   coding-agent profile (src/jacquard/coding_agent.py),
3. submits it to the kernel in-process against the log at
   $JACQUARD_LOG (default: <workspace>/.jacquard/kernel.jsonl),
4. prints the verdict in MCode's hook output schema
   (the Claude-style hookSpecificOutput shape, verified live):
   kernel allow -> allow; kernel deny -> deny with the policy
   reason; kernel QUEUED -> deny whose reason names the queue
   proposal id and its binding hash and tells the agent the
   item is batched for an operator decision, to continue other
   work and retry later. An approval authorises exactly one
   retry of the identical action (see the profile module).
   Tools outside the four governed classes (host bookkeeping)
   get no output at all: the host's own flow governs them.
   On PostToolUse the same process reports the outcome of an
   approved shell action against its action machine, so the
   log records what actually ran.

Any adapter-internal error fails CLOSED: deny with reason
"adapter error: ...". This process never exits non-zero with
an allow, and never prints anything but the verdict JSON.

Every invocation appends one line to a latency sidecar (JSONL
next to the kernel log, or $JACQUARD_LATENCY_LOG):
{ts, tool, verdict, decision_ms, proposal_id?}. The sidecar
carries no tool arguments. The kernel log DOES record the full
proposal requests (that is what makes decisions replayable) —
see the adapter README's redaction note before pointing an
agent holding secrets at this hook.

Concurrent tool calls run concurrent hook processes; a file
lock next to the kernel log serialises kernel access so the
append-only log is never written by two hooks at once.
"""
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402
from jacquard.canonical import hash_of  # noqa: E402
from jacquard.coding_agent import (  # noqa: E402
    binding_hash, find_unconsumed_release, install_coding_agent,
    mark_consumed, prepare_requests, profile_installed, proposals_for)
from jacquard.learner import Learner  # noqa: E402

DEFAULT_PRODUCER = "mcode-agent"


# ---------------------------------------------------------- translation

def _read_payload(tool_input):
    return {"path": tool_input.get("path")
            or tool_input.get("file_path")
            or tool_input.get("pattern") or ""}


def _write_payload(tool_input):
    path = tool_input.get("path") or tool_input.get("file_path") or ""
    value = {"path": path}
    for field in ("content", "old_string", "new_string", "patch"):
        if field in tool_input:
            value[field] = tool_input[field]
    return {"unit": "agent-file:" + path, "value": value}


def _shell_payload(tool_input):
    return {"cmd": ["sh", "-c", tool_input.get("command") or ""]}


def _network_payload(tool_input):
    channel = tool_input.get("url") or tool_input.get("query") \
        or tool_input.get("channel") or ""
    payload = {k: v for k, v in tool_input.items()
               if k not in ("url", "channel")}
    return {"channel": channel, "payload": payload}


# MCode tool name -> (profile class, payload builder). MCode
# tool names are lowercase (bash, read, write, edit, glob,
# grep, fetch, web_search - captured live, slice 39); the
# camelCase spellings are accepted as aliases so one table
# serves both spellings of the same call. The mapping is the
# adapter's whole knowledge of the host; the policy for each
# class lives in the profile, not here.
TOOL_MAP = {
    "read": ("agent-read", _read_payload),
    "glob": ("agent-read", _read_payload),
    "grep": ("agent-read", _read_payload),
    "Read": ("agent-read", _read_payload),
    "Glob": ("agent-read", _read_payload),
    "Grep": ("agent-read", _read_payload),
    "LS": ("agent-read", _read_payload),
    "write": ("agent-write", _write_payload),
    "edit": ("agent-write", _write_payload),
    "Write": ("agent-write", _write_payload),
    "Edit": ("agent-write", _write_payload),
    "ApplyPatch": ("agent-write", _write_payload),
    "bash": ("agent-shell", _shell_payload),
    "Bash": ("agent-shell", _shell_payload),
    "fetch": ("agent-network", _network_payload),
    "web_search": ("agent-network", _network_payload),
    "WebFetch": ("agent-network", _network_payload),
    "WebSearch": ("agent-network", _network_payload),
}


def translate(tool_name, tool_input):
    """-> (tool_class, payload) or None if the tool is unmapped."""
    row = TOOL_MAP.get(tool_name)
    if row is None:
        return None
    tool_class, build = row
    return tool_class, build(tool_input or {})


# ---------------------------------------------------------- decision

def queued_reason(proposal_id, binding):
    return (
        "Jacquard: QUEUED for operator decision - proposal %s, "
        "binding %s. This action is batched in the Jacquard "
        "decision queue; it is not rejected and nothing has "
        "timed out. The operator decides the batch with "
        "tools/jq.py (the approval binds this hash). Continue "
        "other work and retry this exact action later: once "
        "approved, the retry is allowed." % (proposal_id, binding))


def decide(event, log_path, producer=DEFAULT_PRODUCER):
    """The hook's decision for one event dict. Returns
    {decision, reason, proposal_id?, outcome?}. Raises on
    adapter-internal failure; the caller fails closed."""
    tool_name = event.get("toolName") or event.get("tool_name")
    tool_input = event.get("toolInput") or event.get("tool_input") or {}
    mapped = translate(tool_name, tool_input)
    if mapped is None:
        # Not one of the four governed action classes (host
        # bookkeeping: todo lists, plan mode, questions...).
        # No Jacquard decision exists for it; stay silent so
        # the host's own permission flow governs. The pass is
        # counted in the latency sidecar.
        return {"decision": "pass", "silent": True,
                "reason": "Jacquard: tool %r is not a governed "
                          "action class; host flow governs"
                          % (tool_name,),
                "outcome": "pass"}
    tool_class, payload = mapped

    os.makedirs(os.path.dirname(os.path.abspath(log_path)),
                exist_ok=True)
    lock_path = log_path + ".lock"
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        seq = Sequencer(Log(log_path))
        if not profile_installed(seq):
            install_coding_agent(seq)
        Learner().install(seq)

        requests = prepare_requests(seq, producer, tool_class, payload)

        # Already queued? Report the same item; never duplicate it.
        for item in proposals_for(seq, producer, tool_class, requests):
            if item["proposal_id"] in seq.state.decision_queue:
                return {"decision": "deny",
                        "reason": queued_reason(
                            item["proposal_id"],
                            binding_hash(seq, item["proposal_id"])),
                        "proposal_id": item["proposal_id"],
                        "outcome": "queue"}

        # An unconsumed operator approval authorises this retry.
        released = find_unconsumed_release(seq, producer, tool_class,
                                           requests)
        if released is not None:
            mark_consumed(seq, released, producer)
            return {"decision": "allow",
                    "reason": "Jacquard: allowed - operator approval "
                              "of proposal %s consumed for this "
                              "execution" % released,
                    "proposal_id": released, "outcome": "allow"}

        # A rejected twin stays rejected (the operator's deny is
        # terminal for this exact action; a changed action is a
        # new proposal).
        prior = proposals_for(seq, producer, tool_class, requests)
        if prior and prior[-1]["rejected"] and not prior[-1]["released"]:
            return {"decision": "deny",
                    "reason": "Jacquard: denied - the operator "
                              "already denied this exact action "
                              "(proposal %s); it is not re-queued"
                              % prior[-1]["proposal_id"],
                    "proposal_id": prior[-1]["proposal_id"],
                    "outcome": "deny"}

        idem = "mcode-%d-%s" % (
            len(seq.log.entries),
            hash_of({"producer": producer, "class": tool_class,
                     "requests": requests})[:16])
        from jacquard.coding_agent import submit_tool_action
        verdict = submit_tool_action(seq, producer, tool_class,
                                     payload, idem)
        if verdict.get("status") == "REFUSED":
            return {"decision": "deny",
                    "reason": "Jacquard: proposal refused (%s): %s"
                              % (verdict.get("refusal"),
                                 verdict.get("detail")),
                    "outcome": "refused"}
        outcome = verdict.get("outcome")
        if outcome == "allow":
            return {"decision": "allow",
                    "reason": "Jacquard: allowed (%s)" % tool_class,
                    "proposal_id": verdict.get("proposal_id"),
                    "outcome": "allow"}
        if outcome == "queue":
            pid = verdict["proposal_id"]
            return {"decision": "deny",
                    "reason": queued_reason(pid, binding_hash(seq, pid)),
                    "proposal_id": pid, "outcome": "queue"}
        return {"decision": "deny",
                "reason": "Jacquard: denied - %s"
                          % ", ".join(verdict.get("reasons", [])),
                "proposal_id": verdict.get("proposal_id"),
                "outcome": outcome or "deny"}


def report_outcome(event, log_path, producer, failed):
    """PostToolUse / PostToolUseFailure: if this event is the
    host-side execution of a released shell proposal, report
    the outcome against its action machine (pid/action-0), so
    the log records what actually ran and the operator CLI
    never re-executes it. Returns the action id reported, or
    None. Never raises."""
    try:
        tool_name = event.get("toolName") or event.get("tool_name")
        tool_input = event.get("toolInput") \
            or event.get("tool_input") or {}
        mapped = translate(tool_name, tool_input)
        if mapped is None:
            return None
        tool_class, payload = mapped
        if tool_class != "agent-shell":
            return None  # only dispatch creates action machines
        lock_path = log_path + ".lock"
        with open(lock_path, "a") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            seq = Sequencer(Log(log_path))
            if not profile_installed(seq):
                return None
            requests = prepare_requests(seq, producer, tool_class,
                                        payload)
            for item in proposals_for(seq, producer, tool_class,
                                      requests):
                action_id = item["proposal_id"] + "/action-0"
                machine = seq.state.machine_instances.get(action_id)
                if machine and machine.get("state") == "dispatched":
                    seq.report_action(
                        action_id, "fail" if failed else "confirm",
                        producer)
                    return action_id
    except Exception:
        return None
    return None


# ---------------------------------------------------------- process

def default_log_path(event):
    configured = os.environ.get("JACQUARD_LOG")
    if configured:
        return configured
    workspace = event.get("cwd") or os.getcwd()
    return os.path.join(workspace, ".jacquard", "kernel.jsonl")


def emit(event_name, decision, reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": decision,
            "permissionDecisionReason": reason}}) + "\n")
    sys.stdout.flush()


def main():
    started = time.perf_counter()
    raw = sys.stdin.read()
    event_name = "PreToolUse"
    tool_name = None
    result = None
    log_path = os.environ.get("JACQUARD_LOG") or ""
    try:
        event = json.loads(raw) if raw.strip() else {}
        event_name = event.get("hookEventName") \
            or event.get("hook_event_name") or event_name
        tool_name = event.get("toolName") or event.get("tool_name")
        log_path = default_log_path(event)
        producer = os.environ.get("JACQUARD_PRODUCER", DEFAULT_PRODUCER)
        if event_name in ("PostToolUse", "PostToolUseFailure"):
            reported = report_outcome(
                event, log_path, producer,
                failed=(event_name == "PostToolUseFailure"
                        or event.get("is_error") is True))
            result = {"decision": "pass", "silent": True,
                      "reason": "Jacquard: outcome %s"
                                % (("reported for " + reported)
                                   if reported else "not tracked"),
                      "outcome": "reported" if reported else "pass"}
        elif event_name != "PreToolUse":
            # Registered for PreToolUse + Post only; anything
            # else is a no-decision pass (host flow governs).
            result = {"decision": "pass", "silent": True,
                      "reason": "Jacquard: no decision for event %s"
                                % event_name,
                      "outcome": "pass"}
        else:
            result = decide(event, log_path, producer)
    except Exception as exc:  # fail closed, never crash-allow
        result = {"decision": "deny",
                  "reason": "adapter error: %s: %s"
                            % (type(exc).__name__, exc),
                  "outcome": "error"}
    decision_ms = round((time.perf_counter() - started) * 1000.0, 3)
    try:
        sidecar = os.environ.get("JACQUARD_LATENCY_LOG") \
            or (log_path + ".latency.jsonl")
        if log_path:
            os.makedirs(os.path.dirname(os.path.abspath(sidecar)),
                        exist_ok=True)
            line = {"ts": datetime.now(timezone.utc).isoformat(),
                    "tool": tool_name, "verdict": result["decision"],
                    "decision_ms": decision_ms}
            if result.get("proposal_id"):
                line["proposal_id"] = result["proposal_id"]
            if result.get("outcome"):
                line["outcome"] = result["outcome"]
            with open(sidecar, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
    except Exception:
        pass  # the sidecar never blocks or breaks a decision
    if not result.get("silent"):
        emit(event_name, result["decision"], result["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
