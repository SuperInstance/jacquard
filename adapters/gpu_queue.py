"""The gpu-queue bridge (Phase 8, slice 22 — beachhead 3).

Jacquard governs REAL job submissions to the Thor's GPU queue
(the incumbent `~/gpu-queue/gpuq` CLI behind the Thor's
`gpu-queue` user service). This adapter is deployment code,
outside the kernel package, and follows the executor adapter's
discipline (adapters/executor.py):

- a fresh process per invocation rebuilds kernel state from the
  live log (one writer at a time; fresh-process-per-call
  satisfies the one-writer rule, as the slice-12 hook does);
- the action id (`<proposal-id>/action-0`) is the idempotency
  key: the bridge journal records an intent BEFORE the gpuq
  add is attempted and the resulting gpuq job id BEFORE any
  outcome is reported to the kernel, so a duplicate dispatch
  re-reports and never re-adds. A crash between the add and
  the journal update recovers by adopting the unclaimed gpuq
  job with this action's unique name, never by re-adding.

Hard constraints (BUILD-BRIEF-PHASE8 slice 22, binding):

- ZERO new persistent processes or services on the Thor. The
  bridge runs on the operator side and is invoked per dispatch
  over the Thor's existing SSH door; it calls `gpuq` only for
  jobs the kernel allowed. Nothing is installed on the Thor;
  the only Thor-side footprint is what gpuq itself creates for
  jobs it accepts (queue entries, job logs, and the jobs' own
  declared output artifacts). Removing this adapter restores
  the incumbent path exactly; other lanes keep using gpuq
  directly throughout.
- The feeder stays OFF. The bridge never invokes `gpuq feeder`
  except that policy DENIES, by shape, any submission whose
  command invokes the feeder.

Bridge policy (POLICY below is data, applied through the
kernel's rule hook — the same seam the learner uses — so every
bridge decision is a real kernel decision entry carrying
`decided_by: gpu-bridge-policy/1` and the policy's own outcome
alongside what policy/1 would have done; a sense entry named
`gpu-policy` records the precise rule and reason per item):

- feeder shapes (a command invoking `gpuq feeder`, the feeder
  materialiser, or `--feeder`) -> DENY (feeder-shape);
- fetch-and-execute shapes (curl/wget piped to a shell, or a
  shell `-c` body containing a fetch) -> DENY
  (fetch-and-execute);
- network-fetch shapes without execution (curl/wget present)
  -> HOLD for operator decision (network-fetch);
- unknown producers (not in KNOWN_PRODUCERS) -> HOLD
  (unknown-producer);
- anything else in the governed job class -> policy/1 decides
  (a plain `dispatch` effect, which policy/1 allows).

The governed namespace, stated before going live and recorded
in the kernel log's policy record (see `policy_record`):

- governed gpuq lane: `jacquard`;
- job class: `gpu-bench` — short, finite GPU bench/inference
  jobs submitted through this bridge, each declaring one
  output artifact;
- live window: stated in the policy record at log genesis
  (job-count target and time bound are parameters of the
  record, not constants of this module).
"""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer, install_lifecycles, make_envelope  # noqa: E402
from consumption import price_one  # noqa: E402
from jacquard.canonical import hash_of  # noqa: E402
from jacquard.records import outputs_and_uses  # noqa: E402
from jacquard.senses import publish_senses  # noqa: E402

POLICY_ID = "gpu-bridge-policy/1"
GATE_POLICY_ID = "gpu-consumption-policy/2"
GOVERNED_LANE = "jacquard"
JOB_CLASS = "gpu-bench"
BRIDGE_PRODUCER = "gpu-bridge"
KNOWN_PRODUCERS = ("jacquard-build", "operator")
GPUQ = "/home/caseydigennaro/gpu-queue/gpuq"
QUEUE_JSON = "/home/caseydigennaro/gpu-queue/queue.json"

POLICY = {
    "allow": "known producer, governed class, no feeder / fetch "
             "shape: policy/1 allows the dispatch outright",
    "hold": "network-fetch shapes and unknown producers queue "
            "for a batched, hash-bound operator decision "
            "(tools/jq.py); a held job dispatches only after a "
            "release entry exists in the log",
    "deny": "feeder shapes and fetch-and-execute shapes are "
            "denied by shape, with the reason recorded",
}

_FEEDER = re.compile(
    r"\bgpuq\s+(?:-\S+\s+)*feeder\b|materialise_feeder|--feeder\b")
_FETCH = re.compile(r"\b(curl|wget)\b")
_PIPE_SHELL = re.compile(r"\|\s*(sudo\s+)?(sh|bash|dash|zsh)\b")
_SHELL_C = re.compile(r"\b(sh|bash|dash|zsh)\s+-c\b")


def classify(producer, cmd):
    """The bridge policy as a pure function of (producer, cmd).

    Returns (rule, reason): rule in allow | hold | deny. This is
    the whole shape policy; the kernel hook below only maps it
    onto kernel outcomes, and the per-item sense entry records
    which rule fired.
    """
    if _FEEDER.search(cmd):
        return ("deny", "feeder-shape: command invokes the gpuq "
                        "feeder; the feeder stays OFF (ruling 6)")
    if _FETCH.search(cmd) and (_PIPE_SHELL.search(cmd)
                                or _SHELL_C.search(cmd)):
        return ("deny", "fetch-and-execute: command fetches over "
                        "the network and executes the result")
    if _FETCH.search(cmd):
        return ("hold", "network-fetch: command fetches over the "
                        "network; operator decides")
    if producer not in KNOWN_PRODUCERS:
        return ("hold", "unknown-producer: %r is not a known "
                        "producer for the governed lane" % producer)
    return ("allow", "known producer, no denied or held shape")


def _gpuq_cmd_of(requests):
    """The gpuq job command carried by a proposal's dispatch
    request, or None when the proposal is not a gpu job."""
    for request in requests or []:
        if request.get("verb") != "dispatch":
            continue
        args = request.get("args") or []
        if args and isinstance(args[0], dict) \
                and isinstance(args[0].get("gpuq"), dict):
            return args[0]["gpuq"].get("cmd")
    return None


def _dispatch_request(requests):
    """The dispatch request carrying a gpuq payload, or
    None when the proposal is not a gpu job."""
    for request in requests or []:
        if request.get("verb") != "dispatch":
            continue
        args = request.get("args") or []
        if args and isinstance(args[0], dict) \
                and isinstance(args[0].get("gpuq"), dict):
            return request
    return None


def gate_config(seq):
    """The consumption gate configured by this log's policy
    record, or None. The gate is data in the log (stated
    before the class goes live, like every bound in this
    bridge), never a constant of this module: a log without
    a gate in its record is not consumption-gated."""
    for entry in seq.log.entries:
        if entry["kind"] == "sense" \
                and entry["body"].get("name") == "gpu-policy-record":
            return entry["body"]["value"].get("consumption_gate")
    return None


def install_bridge_policy(seq):
    """Wire the bridge policy into a sequencer through the
    kernel's rule hook (the learner's seam). The hook never
    overrides a suspension (constitutional) and speaks only for
    the governed job class."""
    def decide_by_bridge(producer, cls, effects, policy_outcome,
                         policy_reasons, requests=None):
        if "producer-suspended" in (policy_reasons or []):
            return None
        if cls != JOB_CLASS:
            return None
        cmd = _gpuq_cmd_of(requests)
        if cmd is None:
            return None
        rule, _reason = classify(producer, cmd)
        if rule == "deny":
            return (POLICY_ID, "deny")
        if rule == "hold":
            return (POLICY_ID, "queue")
        return None

    def decide_by_gate(producer, cls, effects, policy_outcome,
                       policy_reasons, requests=None):
        gate = gate_config(seq)
        if not gate or cls != gate.get("job_class"):
            return decide_by_bridge(producer, cls, effects,
                                    policy_outcome,
                                    policy_reasons, requests)
        if "producer-suspended" in (policy_reasons or []):
            return None
        request = _dispatch_request(requests)
        if request is None:
            return None
        cmd = request["args"][0]["gpuq"].get("cmd")
        rule, _reason = classify(producer, cmd)
        if rule == "deny":
            return (POLICY_ID, "deny")
        if rule == "hold":
            return (POLICY_ID, "queue")
        outputs = request.get("outputs") or []
        pricing = price_one(seq.log.entries, cls, producer,
                            outputs[0] if outputs else None,
                            threshold_bp=gate.get(
                                "threshold_bp", 5000),
                            budget=gate.get(
                                "exemption_budget", 3),
                            own_uses=request.get("uses") or [])
        hold = pricing["would_hold_refined"] \
            if gate.get("exempt_self_consuming") \
            else pricing["would_hold"]
        if hold:
            return (GATE_POLICY_ID, "queue")
        return None
    seq.rule_decider = decide_by_gate
    return seq


def policy_record(log_label, window, consumption_gate=None):
    """The bounded-start statement, published into the kernel
    log at genesis (before the first live dispatch)."""
    return {
        "governed_lane": GOVERNED_LANE,
        "job_class": JOB_CLASS,
        "job_class_description":
            "short, finite GPU bench/inference jobs submitted "
            "through the bridge, each declaring one output "
            "artifact under ~/jacquard-gpu-live/ on the Thor",
        "kernel_log": log_label,
        "policy": POLICY,
        "policy_id": POLICY_ID,
        "known_producers": list(KNOWN_PRODUCERS),
        "feeder": "OFF; never invoked by the bridge; feeder "
                  "shapes are denied by shape",
        "thor_route": "per-dispatch SSH over the Thor's existing "
                      "door only; zero new persistent processes "
                      "or services on the Thor",
        "successor_rule": "gpuq dispatches a finite job only "
                          "with another job queued behind it or "
                          "the feeder on; the live chain therefore "
                          "always carries a named successor, and "
                          "the window's last job is a declared "
                          "sentinel that stays queued in gpuq",
        "window": window,
        "consumption_gate": consumption_gate,
    }


# ---------------------------------------------------------- transport

class ThorTransport:
    """The bridge's only Thor surface: run one command over the
    existing SSH door. The command prefix comes from
    JACQUARD_GPU_THOR_CMD (default: the fleet's thor.config
    door from the operator VM — the route verified for this
    slice; the Oracle's own keys are not authorised on the
    Thor, and adding one would be a persistent Thor-side
    change the constraints forbid)."""

    def __init__(self, prefix=None):
        if prefix is None:
            prefix = os.environ.get("JACQUARD_GPU_THOR_CMD") or (
                "ssh -F %s thor" % os.path.expanduser(
                    "~/workspace/ssh/thor.config"))
        self.prefix = shlex.split(prefix)

    def run(self, argv):
        remote = " ".join(shlex.quote(str(a)) for a in argv)
        proc = subprocess.run(self.prefix + [remote],
                              capture_output=True, text=True,
                              timeout=120)
        return proc.returncode, proc.stdout, proc.stderr

    def add_job(self, lane, name, cmd):
        code, out, err = self.run(
            [GPUQ, "add", "--lane", lane, "--name", name,
             "--cmd", cmd])
        if code != 0:
            raise RuntimeError("gpuq add failed (%d): %s %s"
                               % (code, out, err))
        return out.strip()

    def queue_state(self):
        code, out, err = self.run(["cat", QUEUE_JSON])
        if code != 0:
            raise RuntimeError("reading gpuq queue failed (%d): %s"
                               % (code, err))
        return json.loads(out)

    def list_text(self):
        code, out, err = self.run([GPUQ, "list"])
        if code != 0:
            raise RuntimeError("gpuq list failed (%d): %s"
                               % (code, err))
        return out


# ---------------------------------------------------------- the bridge

class GpuQueueBridge:
    def __init__(self, sequencer, transport, journal_path):
        self.seq = sequencer
        install_bridge_policy(sequencer)
        self.transport = transport
        self.journal_path = journal_path
        self._journal = {}
        if os.path.exists(journal_path):
            with open(journal_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        self._journal[record["action_id"]] = record

    # ------------------------------------------------ genesis
    def ensure_kernel(self, log_label, window,
                      consumption_gate=None):
        """On a fresh log: install the lifecycles and publish
        the policy record BEFORE any proposal. On an existing
        governed log: verify the record is present. Returns the
        policy record entry, or None if it already existed."""
        for entry in self.seq.log.entries:
            if entry["kind"] == "sense" \
                    and entry["body"].get("name") == "gpu-policy-record":
                return None
        if self.seq.log.entries:
            raise RuntimeError(
                "log has %d entries but no gpu-policy-record; "
                "refusing to govern a log that was not opened "
                "with the bounded-start statement"
                % len(self.seq.log.entries))
        install_lifecycles(self.seq)
        return self.seq.submit_sense(
            "gpu-policy-record",
            policy_record(log_label, window, consumption_gate),
            BRIDGE_PRODUCER)

    # ------------------------------------------------ submit
    def submit_job(self, producer, name, cmd, output=None,
                   uses=None, idem=None, job_class=None):
        """One governed submission: proposal -> kernel decision.
        The dispatch payload carries the gpuq job; the declared
        output artifact rides on the request so the kernel's
        output/use projection (and the downstream-use sense)
        sees it. Returns the kernel verdict plus the bridge
        classification that explains it."""
        if job_class is None:
            job_class = JOB_CLASS
        rule, reason = classify(producer, cmd)
        gate = gate_config(self.seq)
        gated = bool(gate) and gate.get("job_class") == job_class
        pricing = None
        if gated:
            # priced on the log as it stands BEFORE this
            # submission's entries land (strictly causal,
            # the shadow scorer's arithmetic)
            pricing = price_one(
                list(self.seq.log.entries), job_class, producer,
                output,
                threshold_bp=gate.get("threshold_bp", 5000),
                budget=gate.get("exemption_budget", 3),
                own_uses=list(uses or []))
        payload = {"cmd": ["gpuq-add", GOVERNED_LANE, name],
                   "gpuq": {"lane": GOVERNED_LANE, "name": name,
                            "cmd": cmd}}
        request = {"verb": "dispatch", "args": [payload]}
        if output:
            request["outputs"] = [output]
        if uses:
            # declared uses ride on the request as well as the
            # proposal body: the rule hook sees requests only,
            # and the consumption gate's refinement (exempt
            # self-consuming submissions) prices on them. The
            # body-level list remains the canonical record the
            # projections read.
            request["uses"] = list(uses)
        body = {"class": job_class, "requests": [request],
                "uses": list(uses or [])}
        if idem is None:
            idem = "gpu-%s" % hash_of({
                "producer": producer, "name": name, "cmd": cmd,
                "n": len(self.seq.log.entries)})[:20]
        verdict = self.seq.submit(make_envelope(
            producer, "proposal", body, ["dispatch"], idem))
        result = dict(verdict)
        result["classification"] = {"rule": rule, "reason": reason}
        if gated:
            result["pricing"] = pricing
        if verdict.get("proposal_id") and (
                verdict.get("outcome") in ("deny", "queue")
                or gated):
            entry_rule, entry_reason, entry_policy = \
                rule, reason, POLICY_ID
            if gated and verdict.get("outcome") == "queue":
                decided_by = None
                for entry in self.seq.log.entries:
                    if entry["kind"] == "decision" and \
                            entry["body"].get("proposal_id") == \
                            verdict["proposal_id"]:
                        decided_by = entry["body"].get(
                            "decided_by")
                if decided_by == GATE_POLICY_ID:
                    entry_rule = "consumption-hold"
                    entry_reason = (
                        "consumption policy v2: producer "
                        "trailing completed-consumption ratio "
                        "%s bp < threshold %s bp, exemption "
                        "budget exhausted (%s completed "
                        "outputs); output has no declared "
                        "consumer" % (
                            pricing["ratio_bp"],
                            pricing["threshold_bp"],
                            pricing["completed_outputs"]))
                    entry_policy = GATE_POLICY_ID
            elif gated and verdict.get("outcome") == "allow":
                if pricing["budget_exempt"]:
                    entry_rule = "consumption-exempt"
                    entry_reason = (
                        "consumption policy v2: exemption "
                        "budget claim (%s of %s completed "
                        "outputs); claim recorded in the "
                        "pricing record" % (
                            pricing["completed_outputs"],
                            pricing["budget"]))
                else:
                    entry_rule = "consumption-pass"
                    entry_reason = (
                        "consumption policy v2: priced, no "
                        "hold (ratio %s bp, threshold %s bp, "
                        "declared consumer: %s)" % (
                            pricing["ratio_bp"],
                            pricing["threshold_bp"],
                            pricing["has_declared_consumer"]))
                entry_policy = GATE_POLICY_ID
            sense_value = {
                "proposal_id": verdict["proposal_id"],
                "producer": producer, "name": name,
                "rule": entry_rule, "reason": entry_reason,
                "policy_id": entry_policy}
            if gated:
                sense_value["pricing"] = pricing
            self.seq.submit_sense("gpu-policy", sense_value,
                                  BRIDGE_PRODUCER)
        return result

    # ------------------------------------------------ dispatch
    def _payloads(self):
        """action_id -> gpuq job spec, from execution entries
        (the executor adapter's reconstruction, restricted to
        gpuq payloads). Queued and denied proposals have no
        execution entry, so they can never appear here — a held
        job dispatches only after a release creates one."""
        payloads = {}
        for entry in self.seq.log.entries:
            if entry["kind"] != "execution":
                continue
            index = 0
            for item in entry["body"].get("applied", []):
                if item.get("verb") == "dispatch":
                    action_id = "%s/action-%d" % (
                        entry["body"]["proposal_id"], index)
                    args = item.get("args", [])
                    payload = args[0] if args else {}
                    if isinstance(payload, dict) \
                            and isinstance(payload.get("gpuq"), dict):
                        payloads[action_id] = payload["gpuq"]
                    index += 1
        return payloads

    def pending_actions(self):
        payloads = self._payloads()
        pending = []
        for action_id, spec in sorted(payloads.items()):
            if self.seq.machine_instance_state(action_id) \
                    == "dispatched":
                pending.append((action_id, spec))
        return pending

    def _record(self, record):
        self._journal[record["action_id"]] = record
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def _find_unclaimed(self, state, name, claimed):
        matches = [job for job in state["jobs"]
                   if job.get("lane") == GOVERNED_LANE
                   and job.get("name") == name
                   and job.get("id") not in claimed]
        return matches

    def dispatch_one(self, action_id, spec):
        """Dispatch exactly once. A journal record with a gpuq
        job id is re-reported, never re-added; an intent with
        no job id adopts the unclaimed gpuq job carrying this
        action's unique name if one exists (crash recovery),
        and only otherwise adds."""
        existing = self._journal.get(action_id)
        if existing and existing.get("gpuq_job_id"):
            return existing  # re-report, never re-add
        if existing is None:
            self._record({"action_id": action_id,
                          "name": spec["name"],
                          "status": "add-intended"})
        before = self.transport.queue_state()
        claimed = {r.get("gpuq_job_id")
                   for r in self._journal.values()} - {None}
        matches = self._find_unclaimed(before, spec["name"], claimed)
        if len(matches) > 1:
            raise RuntimeError(
                "gpuq holds %d unclaimed jobs named %r; refusing "
                "to guess" % (len(matches), spec["name"]))
        if matches:
            record = {"action_id": action_id, "name": spec["name"],
                      "status": "dispatched",
                      "gpuq_job_id": matches[0]["id"],
                      "adopted": True}
            self._record(record)
            return record
        self.transport.add_job(spec["lane"], spec["name"],
                               spec["cmd"])
        after = self.transport.queue_state()
        matches = self._find_unclaimed(after, spec["name"], claimed)
        if len(matches) != 1:
            raise RuntimeError(
                "gpuq add for %r did not produce exactly one new "
                "job (found %d); journal intent stands for "
                "adoption on the next dispatch"
                % (spec["name"], len(matches)))
        record = {"action_id": action_id, "name": spec["name"],
                  "status": "dispatched",
                  "gpuq_job_id": matches[0]["id"]}
        self._record(record)
        return record

    def dispatch_pending(self):
        return [self.dispatch_one(action_id, spec)
                for action_id, spec in self.pending_actions()
                if self.seq.machine_instance_state(action_id)
                == "dispatched"]

    # ------------------------------------------------ outcomes
    def poll_outcomes(self):
        """Read gpuq state for dispatched job ids and write
        outcome entries into the kernel log: a confirm/fail
        transition on the action machine plus a `gpu-outcome`
        sense entry carrying the gpuq job id and exit."""
        state = None
        results = []
        for action_id, record in sorted(self._journal.items()):
            job_id = record.get("gpuq_job_id")
            if not job_id or record.get("outcome"):
                continue
            if state is None:
                state = self.transport.queue_state()
            job = next((j for j in state["jobs"]
                        if j.get("id") == job_id), None)
            if job is None:
                results.append({"action_id": action_id,
                                "gpuq_job_id": job_id,
                                "status": "missing-in-gpuq"})
                continue
            if job["status"] == "done":
                self.seq.report_action(action_id, "confirm",
                                       BRIDGE_PRODUCER)
                outcome = {"action_id": action_id,
                           "gpuq_job_id": job_id,
                           "status": "completed",
                           "exit": job.get("exit")}
                self._record(dict(record, outcome=outcome))
                self.seq.submit_sense("gpu-outcome", outcome,
                                      BRIDGE_PRODUCER)
                results.append(outcome)
            elif job["status"] == "failed":
                self.seq.report_action(action_id, "fail",
                                       BRIDGE_PRODUCER)
                outcome = {"action_id": action_id,
                           "gpuq_job_id": job_id,
                           "status": "failed",
                           "exit": job.get("exit")}
                self._record(dict(record, outcome=outcome))
                self.seq.submit_sense("gpu-outcome", outcome,
                                      BRIDGE_PRODUCER)
                results.append(outcome)
            else:
                results.append({"action_id": action_id,
                                "gpuq_job_id": job_id,
                                "status": job["status"]})
        return results

    # ------------------------------------------------ senses + counts
    def downstream_use(self):
        """The C3 churn question as a live reading, computed
        from the log: of the governed jobs that COMPLETED
        (their action confirmed), how many declared outputs
        were ever used (named in a later execution's uses)."""
        entries = self.seq.log.entries
        completed_outputs = []
        for entry in entries:
            if entry["kind"] != "execution" \
                    or entry["body"].get("class") != JOB_CLASS:
                continue
            pid = entry["body"]["proposal_id"]
            action_id = pid + "/action-0"
            if self.seq.machine_instance_state(action_id) \
                    != "confirmed":
                continue
            for item in entry["body"].get("applied", []):
                completed_outputs.extend(item.get("outputs", []))
        used_ids = set()
        for entry in entries:
            if entry["kind"] == "execution":
                used_ids.update(entry["body"].get("uses", []))
        used = [o for o in completed_outputs if o in used_ids]
        total = len(completed_outputs)
        return {
            "completed_jobs_with_outputs": total,
            "outputs_used": len(used),
            "outputs_unused": total - len(used),
            "used": sorted(used),
            "ratio_bp": (10000 * len(used)) // total if total else 0,
        }

    DOWNSTREAM_METHOD = (
        "gpu-downstream-use sense: read set = execution entries "
        "of class gpu-bench whose action instance stands "
        "confirmed; outputs = the outputs declared on their "
        "applied dispatch items; an output counts as used iff "
        "some execution entry's uses list names it. Computed "
        "from the log alone at publish time.")

    def publish_live_senses(self, producers=KNOWN_PRODUCERS):
        names = ["queue-depth"] + ["output-use:%s" % p
                                   for p in producers]
        published = publish_senses(self.seq, names,
                                   producer=BRIDGE_PRODUCER)
        reading = {"value": self.downstream_use(),
                   "method": self.DOWNSTREAM_METHOD,
                   "as_of_seq": (self.seq.log.entries[-1]["seq"]
                                 if self.seq.log.entries else -1)}
        published.append(self.seq.submit_sense(
            "gpu-downstream-use", reading, BRIDGE_PRODUCER))
        return published

    def counts(self):
        """The live counts table, derived from the log and the
        journal: primary decisions (release/reject follow-ups
        and faults excluded, as in the learner's projection),
        plus dispatch and completion state."""
        primary = {"allow": 0, "deny": 0, "queued": 0}
        submitted = 0
        for entry in self.seq.log.entries:
            if entry["kind"] != "decision":
                continue
            body = entry["body"]
            if body.get("class") != JOB_CLASS:
                continue
            if body.get("releases") or body.get("rejects") \
                    or body.get("expires") or body.get("fault"):
                continue
            if body.get("outcome") not in primary:
                continue
            primary[body["outcome"]] += 1
            submitted += 1
        completed = failed = 0
        for action_id in self._payloads():
            state = self.seq.machine_instance_state(action_id)
            if state == "confirmed":
                completed += 1
            elif state in ("failed", "compensated"):
                failed += 1
        dispatched = sum(1 for r in self._journal.values()
                         if r.get("gpuq_job_id"))
        return {
            "submitted": submitted,
            "allowed": primary["allow"],
            "held_at_submission": primary["queued"],
            "denied": primary["deny"],
            "currently_queued": len(self.seq.state.decision_queue),
            "dispatched_to_gpuq": dispatched,
            "completed": completed,
            "failed": failed,
            "entries": len(self.seq.log.entries),
            "chain_ok": self.seq.log.verify_chain(),
        }


def open_bridge(log_path, transport=None, journal_path=None):
    """One fresh bridge over the log at `log_path` — the
    per-invocation entry point every CLI verb uses."""
    seq = Sequencer(Log(log_path))
    if journal_path is None:
        journal_path = log_path + ".gpu-journal.jsonl"
    return GpuQueueBridge(seq, transport or ThorTransport(),
                          journal_path)
