"""Sandboxed command executor for the action outbox (SPEC
section 10.5).

The kernel decides and records; executors act. This adapter —
deployment code, outside the kernel package — consumes action
instances standing at `dispatched`, runs their commands in a
sandbox, and reports the outcome back through the action
machine (confirm / fail, then compensate when a compensating
command was supplied).

The dispatch payload is a map: {"cmd": [argv...],
"compensate": [argv...] (optional)}. The action id
(<proposal-id>/action-<n>, n = the dispatch's index among the
proposal's dispatch requests) is the idempotency key: the
executor's journal (a JSONL file) records every run BEFORE the
outcome is reported to the kernel, so a duplicate delivery —
or a crash between running and reporting — never runs the
command twice; the recorded outcome is simply reported again.

Sandbox: bubblewrap where available (read-only root, private
/tmp, no network), else a plain subprocess with a scrubbed
environment and a scratch working directory. The journal
records which sandbox actually ran each command; a fallback is
a fact in the record, not a silent downgrade.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class SandboxedExecutor:
    def __init__(self, sequencer, journal_path, sandbox="auto",
                 timeout=30, producer="executor"):
        self.seq = sequencer
        self.journal_path = journal_path
        self.timeout = timeout
        self.producer = producer
        if sandbox == "auto":
            sandbox = "bwrap" if shutil.which("bwrap") else "subprocess"
        self.sandbox = sandbox
        self._journal = {}
        if os.path.exists(journal_path):
            with open(journal_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        self._journal[record["action_id"]] = record

    # -------------------------------------------------- outbox
    def _payloads(self):
        """action_id -> dispatch payload, from execution entries:
        the n-th dispatch item of a proposal's applied list is
        action-<n> of that proposal."""
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
                    payloads[action_id] = args[0] if args else {}
                    index += 1
        return payloads

    def pending_actions(self):
        payloads = self._payloads()
        pending = []
        for instance, current in self.seq.state.machine_instances.items():
            if current["machine"] == "action" \
                    and current["state"] == "dispatched" \
                    and instance in payloads:
                pending.append((instance, payloads[instance]))
        return sorted(pending)

    # -------------------------------------------------- running
    def _run_sandboxed(self, argv):
        if self.sandbox == "bwrap":
            command = ["bwrap", "--ro-bind", "/", "/",
                       "--dev", "/dev", "--proc", "/proc",
                       "--tmpfs", "/tmp", "--chdir", "/tmp",
                       "--unshare-net", "--die-with-parent",
                       "--new-session", "--"] + argv
            proc = subprocess.run(command, capture_output=True,
                                  text=True, timeout=self.timeout)
            return proc.returncode, proc.stdout, proc.stderr
        with tempfile.TemporaryDirectory(prefix="jacquard-exec-") as work:
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "LANG": "C.UTF-8"}
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  timeout=self.timeout, cwd=work, env=env)
            return proc.returncode, proc.stdout, proc.stderr

    def _record(self, record):
        self._journal[record["action_id"]] = record
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def deliver(self, action_id, payload):
        """Run one action (or replay its recorded outcome) and
        report through the action machine. Returns the journal
        record."""
        if action_id in self._journal:
            record = self._journal[action_id]
            self._report(action_id, record)  # re-report, never re-run
            return record
        cmd = payload.get("cmd")
        if not isinstance(cmd, list) or not cmd \
                or not all(isinstance(part, str) for part in cmd):
            record = {"action_id": action_id, "exit": None,
                      "sandbox": self.sandbox,
                      "error": "payload has no cmd argv list"}
            self._record(record)
            self.seq.report_action(action_id, "fail", self.producer)
            return record
        try:
            code, stdout, stderr = self._run_sandboxed(cmd)
            record = {"action_id": action_id, "cmd": cmd, "exit": code,
                      "sandbox": self.sandbox,
                      "stdout": stdout[-2000:], "stderr": stderr[-2000:]}
        except subprocess.TimeoutExpired:
            record = {"action_id": action_id, "cmd": cmd, "exit": None,
                      "sandbox": self.sandbox, "error": "timeout"}
        self._record(record)
        self._report(action_id, record, payload)
        return record

    def _report(self, action_id, record, payload=None):
        if self.seq.machine_instance_state(action_id) != "dispatched":
            return  # already reported (e.g. by an earlier delivery)
        if record.get("exit") == 0:
            self.seq.report_action(action_id, "confirm", self.producer)
            return
        self.seq.report_action(action_id, "fail", self.producer)
        compensate = (payload or {}).get("compensate")
        if compensate is None and action_id in self._journal:
            compensate = self._payloads().get(action_id, {}).get("compensate")
        if isinstance(compensate, list) and compensate:
            try:
                code, stdout, _stderr = self._run_sandboxed(compensate)
                self._record({"action_id": action_id + ":compensate",
                              "cmd": compensate, "exit": code,
                              "sandbox": self.sandbox,
                              "stdout": stdout[-2000:]})
            except subprocess.TimeoutExpired:
                self._record({"action_id": action_id + ":compensate",
                              "cmd": compensate, "exit": None,
                              "sandbox": self.sandbox, "error": "timeout"})
            self.seq.report_action(action_id, "compensate", self.producer)

    def run_once(self):
        """Deliver every pending action. Returns the records."""
        return [self.deliver(action_id, payload)
                for action_id, payload in self.pending_actions()]
