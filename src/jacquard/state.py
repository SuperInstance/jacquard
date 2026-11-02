"""Folded state (SPEC section 2).

Committed state is derived from the log by folding, in order:
definition entries populate the dictionary, execution entries apply
their recorded writes to units, sense entries publish readings, and
decision entries maintain the decision queue.
"""
from .canonical import hash_of


class State:
    def __init__(self):
        self.units = {}
        self.senses = {}
        self.dictionary = {}
        self.decision_queue = {}

    def state_hash(self):
        return hash_of({
            "units": self.units,
            "senses": self.senses,
            "dictionary": self.dictionary,
            "decision_queue": self.decision_queue,
        })


def fold(entries):
    state = State()
    for entry in entries:
        kind = entry["kind"]
        body = entry["body"]
        if kind == "definition":
            stored = body["definition"]
            state.dictionary.setdefault(stored["name"], []).append({
                "entry_seq": entry["seq"],
                "entry_hash": entry["hash"],
                "definition": stored,
            })
        elif kind == "execution":
            for applied in body.get("applied", []):
                if applied.get("verb") == "write":
                    unit, value = applied["args"]
                    state.units[unit] = value
        elif kind == "sense":
            state.senses[body["name"]] = body["value"]
        elif kind == "decision":
            if body.get("outcome") == "queued":
                state.decision_queue[body["proposal_id"]] = dict(body)
            elif body.get("releases"):
                state.decision_queue.pop(body["releases"], None)
    return state


class Refusal(Exception):
    """A named refusal. Refusals are answers, recorded in the log."""

    def __init__(self, name, detail):
        super().__init__("%s: %s" % (name, detail))
        self.name = name
        self.detail = detail
