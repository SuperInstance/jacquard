"""The bridge's consumption gate (Phase 10, slice 28).

The v2 policy (adapters/consumption.py) wired into the
gpu-queue bridge as machinery: a log whose policy record
carries a `consumption_gate` holds submissions of the gated
class from producers whose completed-consumption ratio is
below threshold once their exemption budget is spent. Runs
against the same in-memory FakeThor as the slice-22 battery.
The gate is OFF unless the record configures it — the last
test proves a gate-less log behaves exactly as before.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "adapters"))

from gpu_queue import GpuQueueBridge  # noqa: E402
from jacquard import Sequencer  # noqa: E402

WINDOW = {"target_jobs": 4, "opens": "test", "closes": "test"}
GATE = {"job_class": "gpu-heavy", "threshold_bp": 5000,
        "exemption_budget": 3}
CMD = "python3 -c 'import torch; print(1)'"


class FakeThor:
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
        return ""

    def finish(self, name, status="done", exit_code=0):
        job = next(j for j in self.jobs if j["name"] == name)
        job["status"] = status
        job["exit"] = exit_code


def make_bridge(tmp_path, gate=GATE):
    seq = Sequencer()
    thor = FakeThor()
    bridge = GpuQueueBridge(seq, thor,
                            str(tmp_path / "journal.jsonl"))
    bridge.ensure_kernel("/oracle/live/kernel.jsonl", WINDOW,
                         consumption_gate=gate)
    return bridge, thor


def run_job(bridge, thor, name):
    bridge.dispatch_pending()
    thor.finish(name)
    bridge.poll_outcomes()


def policy_entries(bridge, name=None):
    out = []
    for e in bridge.seq.log.entries:
        if e["kind"] == "sense" \
                and e["body"].get("name") == "gpu-policy":
            v = e["body"]["value"]
            if name is None or v.get("name") == name:
                out.append(v)
    return out


def build_bad_record(bridge, thor):
    """Three completed outputs, none ever consumed: the
    exemption budget exactly spent, ratio 0."""
    for i in (1, 2, 3):
        v = bridge.submit_job("jacquard-build", "h%d" % i, CMD,
                              output="a%d" % i,
                              job_class="gpu-heavy")
        assert v["outcome"] == "allow", v
        run_job(bridge, thor, "h%d" % i)


def test_budget_claims_recorded_then_hold(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    build_bad_record(bridge, thor)
    claims = policy_entries(bridge)
    assert [c["rule"] for c in claims] == \
        ["consumption-exempt"] * 3
    assert all(c["pricing"]["exemption_claimed"]
               for c in claims)
    assert claims[-1]["pricing"]["completed_outputs"] == 2
    v = bridge.submit_job("jacquard-build", "h4", CMD,
                          output="a4", job_class="gpu-heavy")
    assert v["outcome"] == "queue", v
    assert v["pricing"]["ratio_bp"] == 0
    assert v["pricing"]["budget_exempt"] is False
    held = policy_entries(bridge, "h4")
    assert held and held[0]["rule"] == "consumption-hold"
    assert held[0]["policy_id"] == "gpu-consumption-policy/2"
    # a held job never reaches the queue
    assert thor.add_calls == 3
    bridge.dispatch_pending()
    assert thor.add_calls == 3


def test_budget_is_per_producer(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    build_bad_record(bridge, thor)
    v = bridge.submit_job("operator", "g1", CMD, output="b1",
                          job_class="gpu-heavy")
    assert v["outcome"] == "allow", v
    assert v["pricing"]["budget_exempt"] is True


def test_completed_consumption_restores_passage(tmp_path):
    bridge, thor = make_bridge(tmp_path)
    build_bad_record(bridge, thor)
    # a consumer job is held by the raw rule too (it declares
    # an output nobody consumes); release it the operator way
    v = bridge.submit_job("jacquard-build", "eater", CMD,
                          output="e1", uses=["a1"],
                          job_class="gpu-heavy")
    assert v["outcome"] == "queue", v
    released = bridge.seq.release_queued(v["proposal_id"],
                                         "operator")
    assert released["outcome"] == "allow"
    run_job(bridge, thor, "eater")
    # now: 4 completed outputs, 1 completed consumption,
    # and a second consumer completes too -> ratio 2/5 after
    # one more plain job... assert the mechanism directly:
    v2 = bridge.submit_job("jacquard-build", "eater2", CMD,
                           output="e2", uses=["a2"],
                           job_class="gpu-heavy")
    released = bridge.seq.release_queued(v2["proposal_id"],
                                         "operator")
    assert released["outcome"] == "allow"
    run_job(bridge, thor, "eater2")
    # 6 completed outputs (a1..a3, e1, e2 + none), 2 used of
    # the producer's first three + ... ratio over ALL the
    # producer's completed outputs: a1,a2 used; a3,e1,e2 not
    # -> 2/5 = 4000 bp < 5000: still held. One more used
    # output tips it: consume a3 as well.
    v3 = bridge.submit_job("jacquard-build", "eater3", CMD,
                           output="e3", uses=["a3"],
                           job_class="gpu-heavy")
    assert v3["outcome"] == "queue", v3
    released = bridge.seq.release_queued(v3["proposal_id"],
                                         "operator")
    assert released["outcome"] == "allow"
    run_job(bridge, thor, "eater3")
    # completed outputs now a1,a2,a3,e1,e2,e3 (6); used
    # a1,a2,a3 (3) -> 5000 bp, not < threshold: passage.
    v4 = bridge.submit_job("jacquard-build", "h9", CMD,
                           output="a9", job_class="gpu-heavy")
    assert v4["outcome"] == "allow", v4
    assert v4["pricing"]["ratio_bp"] == 5000


def test_refinement_flag_exempts_consumers(tmp_path):
    gate = dict(GATE, exempt_self_consuming=True)
    bridge, thor = make_bridge(tmp_path, gate)
    build_bad_record(bridge, thor)
    v = bridge.submit_job("jacquard-build", "eater", CMD,
                          output="e1", uses=["a1"],
                          job_class="gpu-heavy")
    assert v["outcome"] == "allow", v
    assert v["pricing"]["would_hold"] is True
    assert v["pricing"]["would_hold_refined"] is False


def test_gate_off_unless_configured(tmp_path):
    bridge, thor = make_bridge(tmp_path, gate=None)
    for i in (1, 2, 3, 4):
        v = bridge.submit_job("jacquard-build", "h%d" % i, CMD,
                              output="a%d" % i,
                              job_class="gpu-heavy")
        assert v["outcome"] == "allow", v
        assert "pricing" not in v
    assert policy_entries(bridge) == []
