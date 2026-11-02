"""WFQ scheduler: the two guarantees (no starvation, no capture),
weight decay, aging, and the sequencer's batch admission."""
from jacquard import Scheduler, Sequencer, make_envelope

HEAVY = ("heavy", "work")
QUIET = ("quiet", "work")


def test_quiet_flow_is_not_starved_by_a_flood():
    sched = Scheduler()
    for i in range(3):
        sched.submit(HEAVY, "heavy-%d" % i)
    sched.submit(QUIET, "quiet-0")
    for i in range(3, 60):
        sched.submit(HEAVY, "heavy-%d" % i)
    served = sched.serve(10)
    # equal weights: the quiet item's finish tag is 4, so it is
    # served within the first four despite 57 heavy items queued.
    assert "quiet-0" in served[:4]


def test_flooding_flow_cannot_exceed_purchased_share():
    sched = Scheduler()
    buyer = ("buyer", "work")
    plain = ("plain", "work")
    sched.purchase(buyer, 3)  # weight 4 vs baseline 1
    for i in range(100):
        sched.submit(buyer, "b-%d" % i)
        sched.submit(plain, "p-%d" % i)
    served = sched.serve(50)
    bought = sum(1 for item in served if item.startswith("b-"))
    baseline = 50 - bought
    # purchased share is 4/5 = 40 of 50; the buyer must land near
    # it (not above by more than tag slack) and the baseline flow
    # must keep roughly its fifth.
    assert 36 <= bought <= 44
    assert baseline >= 6


def test_equal_flows_share_evenly():
    sched = Scheduler()
    for i in range(40):
        sched.submit(HEAVY, "h-%d" % i)
        sched.submit(QUIET, "q-%d" % i)
    served = sched.serve(40)
    assert sum(1 for s in served if s.startswith("h-")) == 20
    assert sum(1 for s in served if s.startswith("q-")) == 20


def test_purchased_weight_decays_to_baseline():
    sched = Scheduler(half_life=10.0)
    flow = ("buyer", "work")
    sched.purchase(flow, 7)
    assert sched.weight(flow) == 8.0
    other = ("other", "work")
    for i in range(200):
        sched.submit(other, "o-%d" % i)
    sched.serve(200)  # virtual time advances far past the half-life
    assert sched.purchased_extra(flow) < 0.1


def test_aging_eventually_drains_a_pathological_item():
    # One size-1000 item for HEAVY (finish tag 1000) against a
    # continuous flood of size-1 items for QUIET, one new arrival
    # per serve. Without aging the big item waits ~1000 serves;
    # with aging its effective finish tag falls linearly once its
    # wait passes the threshold, and it drains far sooner.
    def run(aging_rate):
        sched = Scheduler(aging_threshold=5.0, aging_rate=aging_rate)
        sched.submit(HEAVY, "big", size=1000)
        for i in range(10):
            sched.submit(QUIET, "q-%d" % i)
        served_at = None
        for step in range(600):
            payload = sched.serve_next()
            if payload == "big":
                served_at = step
                break
            sched.submit(QUIET, "q-next-%d" % step)
        return served_at

    assert run(aging_rate=0.0) is None       # no aging: still stuck
    assert run(aging_rate=1.0) is not None   # aging drains it


def test_order_uses_purchased_weights():
    sched = Scheduler()
    sched.purchase(("buyer", "work"), 3)
    items = [(("plain", "work"), "p1", 1), (("buyer", "work"), "b1", 1),
             (("plain", "work"), "p2", 1), (("buyer", "work"), "b2", 1)]
    ordered = sched.order(items)
    assert ordered[:2] == ["b1", "b2"]
    assert ordered.index("b2") < ordered.index("p2")


# --------------------------------------------- sequencer arenas

def proposal(producer, ident, cls="work"):
    return make_envelope(producer, "proposal",
                         {"class": cls,
                          "requests": [{"verb": "write",
                                        "args": ["u/" + ident, 1]}]},
                         ["write"], ident)


def test_submit_batch_serves_fairly_across_producers():
    from jacquard import envelope_hash
    seq = Sequencer()
    batch = [proposal("heavy", "bh-%d" % i) for i in range(6)]
    quiet_env = proposal("quiet", "bq-0")
    batch.insert(1, quiet_env)
    verdicts = seq.submit_batch(batch)
    assert all(v["outcome"] == "allow" for v in verdicts)
    assert len(verdicts) == 7
    order = [v["proposal_id"] for v in verdicts]
    # the quiet proposal arrived second; at equal weights its
    # finish tag keeps it at the front of the served order.
    assert order.index(envelope_hash(quiet_env)) <= 2


def test_decision_order_presents_queued_items():
    seq = Sequencer()
    for i in range(3):
        seq.submit(make_envelope(
            "prod-%d" % i, "proposal",
            {"requests": [{"verb": "notify", "args": ["ops", i]}]},
            ["notify"], "dq-%d" % i))
    order = seq.decision_order()
    assert sorted(order) == sorted(seq.state.decision_queue.keys())
    assert len(order) == 3
