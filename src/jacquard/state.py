"""Folded state (SPEC section 2).

Committed state is derived from the log by folding, in order:
definition entries populate the dictionary, execution entries apply
their recorded writes to units and their recorded spends to
budgets, sense entries publish readings, decision entries maintain
the decision queue, machine entries populate the machine registry,
transition entries move machine instances, budget and price entries
maintain the accounts, and rule entries register standing rules
(their stage is the state of their standing-rule machine instance).
"""
from .canonical import hash_of


class State:
    def __init__(self):
        self.units = {}
        self.senses = {}
        self.dictionary = {}
        self.decision_queue = {}
        self.machines = {}
        self.machine_instances = {}
        self.budgets = {}
        self.prices = {}
        self.rules = {}

    def state_hash(self):
        return hash_of({
            "units": self.units,
            "senses": self.senses,
            "dictionary": self.dictionary,
            "decision_queue": self.decision_queue,
            "machines": self.machines,
            "machine_instances": self.machine_instances,
            "budgets": self.budgets,
            "prices": self.prices,
            "rules": self.rules,
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
            producer = body.get("producer")
            for applied in body.get("applied", []):
                if applied.get("verb") == "write":
                    unit, value = applied["args"]
                    state.units[unit] = value
                elif applied.get("verb") == "spend" and producer is not None:
                    resource, amount = applied["args"]
                    price = state.prices.get(resource, 1)
                    state.budgets[producer] = (
                        state.budgets.get(producer, 0) - amount * price)
        elif kind == "sense":
            state.senses[body["name"]] = body["value"]
        elif kind == "decision":
            if body.get("outcome") == "queued":
                state.decision_queue[body["proposal_id"]] = dict(body)
            elif body.get("releases"):
                state.decision_queue.pop(body["releases"], None)
            elif body.get("rejects"):
                state.decision_queue.pop(body["rejects"], None)
            elif body.get("expires"):
                state.decision_queue.pop(body["expires"], None)
        elif kind == "machine":
            stored = body["machine"]
            state.machines.setdefault(stored["name"], []).append({
                "entry_seq": entry["seq"],
                "entry_hash": entry["hash"],
                "definition": stored,
            })
        elif kind == "transition":
            if body.get("outcome") in ("created", "taken"):
                state.machine_instances[body["instance"]] = {
                    "machine": body["machine"],
                    "state": body["to"],
                }
        elif kind == "budget":
            producer = body["producer"]
            state.budgets[producer] = (
                state.budgets.get(producer, 0) + body["delta"])
        elif kind == "price":
            state.prices[body["resource"]] = body["price"]
        elif kind == "rule":
            stored = body["rule"]
            state.rules[stored["rule_id"]] = dict(stored)
    return state


def rule_stage(state, rule_id):
    """A standing rule's stage is its machine instance's state."""
    instance = state.machine_instances.get(rule_id)
    if instance is None:
        return None
    return instance["state"]


class Refusal(Exception):
    """A named refusal. Refusals are answers, recorded in the log."""

    def __init__(self, name, detail):
        super().__init__("%s: %s" % (name, detail))
        self.name = name
        self.detail = detail
