"""Fair scheduling: weighted fair queueing over flows (SPEC
section 11).

One Scheduler implementation arbitrates three arenas with the
same rules: sequencer admission, executor slots, and
decision-queue attention. A flow is a (producer, service class)
pair. Each flow has a baseline weight of 1; extra weight is
purchased from the producer's budget (the sequencer charges the
budget; the scheduler only records the purchase) and decays back
to baseline with virtual time — a purchase buys a temporary
share, never a permanent one.

Mechanics (standard WFQ): virtual time advances with served
work. An item arriving at virtual time v for a flow whose last
finish tag is f gets start = max(v, f) and finish = start +
size / weight, where weight is the flow's weight at arrival
(baseline plus the still-undecayed part of its purchases:
each purchase's extra halves every HALF_LIFE virtual-time
units). The scheduler serves the queued item with the smallest
finish tag, ties broken by arrival order. Aging is a secondary
nudge: an item that has waited more than AGING_THRESHOLD
virtual-time units past arrival gets its finish tag reduced
linearly, so pathological cases still drain.

Guarantees the tests pin: a quiet flow keeps its baseline share
across a busy window (no starvation), and a flooding flow cannot
exceed its purchased share (no capture).
"""
BASE_WEIGHT = 1.0


class _Item:
    __slots__ = ("seq", "flow", "payload", "size", "arrival_vt",
                 "start", "finish")

    def __init__(self, seq, flow, payload, size, arrival_vt, start, finish):
        self.seq = seq
        self.flow = flow
        self.payload = payload
        self.size = size
        self.arrival_vt = arrival_vt
        self.start = start
        self.finish = finish


class Scheduler:
    def __init__(self, half_life=1000.0, aging_threshold=50.0,
                 aging_rate=0.01):
        self.half_life = float(half_life)
        self.aging_threshold = float(aging_threshold)
        self.aging_rate = float(aging_rate)
        self.vt = 0.0
        self._seq = 0
        self._queue = []
        self._last_finish = {}
        self._purchases = {}
        self._served = {}
        self._submitted = {}

    # -------------------------------------------------- weights
    def purchase(self, flow, extra):
        """Record purchased extra weight for a flow, stamped at
        the current virtual time. (Charging the budget is the
        caller's job; the log entry is the evidence.)"""
        self._purchases.setdefault(flow, []).append((self.vt, float(extra)))

    def weight(self, flow):
        extra = 0.0
        for bought_vt, amount in self._purchases.get(flow, ()):
            age = max(0.0, self.vt - bought_vt)
            extra += amount * (0.5 ** (age / self.half_life))
        return BASE_WEIGHT + extra

    def purchased_extra(self, flow):
        return self.weight(flow) - BASE_WEIGHT

    # -------------------------------------------------- queueing
    def submit(self, flow, payload, size=1):
        start = max(self.vt, self._last_finish.get(flow, 0.0))
        finish = start + float(size) / self.weight(flow)
        item = _Item(self._seq, flow, payload, size, self.vt, start, finish)
        self._seq += 1
        self._last_finish[flow] = finish
        self._queue.append(item)
        self._submitted[flow] = self._submitted.get(flow, 0) + 1
        return item

    def _effective_finish(self, item):
        waited = self.vt - item.arrival_vt
        bonus = max(0.0, waited - self.aging_threshold) * self.aging_rate
        return item.finish - bonus

    def serve_next(self):
        if not self._queue:
            return None
        best = min(self._queue,
                   key=lambda item: (self._effective_finish(item), item.seq))
        self._queue.remove(best)
        self.vt = max(self.vt, best.start)
        stats = self._served.setdefault(best.flow, {"items": 0, "size": 0})
        stats["items"] += 1
        stats["size"] += best.size
        return best.payload

    def serve(self, count):
        served = []
        for _ in range(count):
            payload = self.serve_next()
            if payload is None:
                break
            served.append(payload)
        return served

    def order(self, submissions):
        """One-shot WFQ ordering of (flow, payload, size) triples
        in arrival order, using this scheduler's current weights,
        without disturbing the live queue. (Decision-queue
        attention: the order a batch is presented in.)"""
        last_finish = {}
        tagged = []
        for seq, (flow, payload, size) in enumerate(submissions):
            start = max(self.vt, last_finish.get(flow, 0.0))
            finish = start + float(size) / self.weight(flow)
            last_finish[flow] = finish
            tagged.append((finish, seq, payload))
        tagged.sort()
        return [payload for _finish, _seq, payload in tagged]

    # -------------------------------------------------- evidence
    def stats(self):
        waiting = {}
        for item in self._queue:
            waiting[item.flow] = waiting.get(item.flow, 0) + 1
        flows = set(self._submitted) | set(self._served) | set(waiting)
        return {"virtual_time": self.vt,
                "flows": {flow: {"submitted": self._submitted.get(flow, 0),
                                 "served_items": self._served.get(flow, {})
                                 .get("items", 0),
                                 "served_size": self._served.get(flow, {})
                                 .get("size", 0),
                                 "waiting": waiting.get(flow, 0),
                                 "weight": self.weight(flow)}
                          for flow in flows}}
