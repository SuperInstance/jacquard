"""Probe C, rung 4 candidate: an authority sense, plus the rank
words that consume it. Quarantined in tests/probes/ -- this
module edits nothing in src/. It registers one additional
sense, ``authority``, into ``jacquard.senses.SENSES`` at runtime
(``register()``), with the same callable signature and return
shape as the built-in senses.

Subject grammar::

    authority:<producer>

Value: ``{"ceiling": int | null, "grants": int}``.

The sense is a pure function of the log entries: it scans
EXECUTION entries whose body producer is "operator" and, among
their applied writes to unit ``authority/<producer>``, the
LATEST wins -- its value (an integer) is the ceiling, and
``grants`` counts those writes. Operator authorship is the
whole method: a write to ``authority/<self>`` by the producer
itself lands in units (policy/1 allows the write -- see the C5
self-grant scenario) but is not an operator execution, so the
sense ignores it. Self-grants are visible in the log and inert.

Rank words (dictionary definitions, installed by
``install_words``; all pure, computed effects []):

- ``rank-granted`` (map -> bool): payload {"producer", "rank",
  "sense_name"}. Builds the sense name "authority:<producer>"
  from the payload's producer with ``cat``, reads the published
  reading, and answers True iff the ceiling is not null and
  rank <= ceiling. (The sense_name field is carried for the
  Probe A payload pattern; the name this word reads is the one
  it builds, which is the name ``publish_authority`` published.)
- ``effective-rank`` (map -> int): payload {"producer", "rank",
  "sense_name"} -> the rank a booking is COMMITTED with: the
  asserted rank clamped to the granted ceiling
  (min(asserted, ceiling)) when a grant exists, else 0. This is
  the staged brief's C6 reading -- an asserted rank above the
  ceiling is clamped, not zeroed: grant 2 + assert 5 -> 2;
  assert 1 -> 1; no grant -> 0 whatever was asserted.
- ``rank-below`` (map -> bool): payload {"rank", "limit"} ->
  rank < limit, via the ``lt`` primitive. Exists so the
  disposal pass in priority_flow.py never compares ranks in
  Python: the comparison is dictionary evaluation like every
  other predicate.

Both ceiling-consuming words must guard the null ceiling
BEFORE any comparison: ``sense`` on an unpublished name returns
None and ``getf`` on None crashes, and ``gt``/``min2`` on a
null ceiling would crash too. The flows therefore publish the
authority sense for a producer before evaluating any word
about them (``publish_authority`` -- ceiling null, grants 0
when there are no grants), and each word tests the extracted
ceiling against a literal None inside an ``if`` gate, with the
rank/ceiling pair preserved beneath the gate condition -- the
same branch-shape pattern as booking_flow's guard words.
"""
import copy

from jacquard import make_envelope, publish_senses
from jacquard import senses as _senses_module

METHOD = (
    "authority sense: read set = execution entries whose body "
    "producer is \"operator\"; among their applied writes to "
    "unit authority/<producer>, the LATEST such write's value "
    "(an integer) is the ceiling and grants is the count of "
    "such writes. Only operator-authored writes count: a "
    "producer's own write to authority/<self> may land in "
    "units under policy/1 but is not an operator execution, so "
    "it is visible in the log and inert here. No operator "
    "grant -> ceiling null, grants 0."
)


def authority_sense(entries, state, subject, runtime):
    if not subject:
        raise ValueError("authority sense needs a producer subject")
    unit = "authority/%s" % subject
    ceiling = None
    grants = 0
    for entry in entries:
        if entry["kind"] != "execution":
            continue
        body = entry["body"]
        if body.get("producer") != "operator":
            continue
        for applied in body.get("applied", []):
            if applied.get("verb") == "write" \
                    and applied["args"][0] == unit:
                ceiling = applied["args"][1]
                grants += 1
    return {"value": {"ceiling": ceiling, "grants": grants},
            "method": METHOD}


def register():
    """Insert the sense into jacquard.senses.SENSES under
    "authority". Idempotent."""
    _senses_module.SENSES["authority"] = authority_sense
    return authority_sense


def publish_authority(seq, producer):
    """Publish the authority reading for `producer` against
    current committed state. Returns the sense name,
    "authority:<producer>". Publishing at decision time is
    required: the rank words read the published reading."""
    register()
    name = "authority:%s" % producer
    publish_senses(seq, [name])
    return name


# -------------------------------------------- rank word bodies

# [payload] -> [ceiling, rank]: build the authority sense name
# from the payload's producer, read the published reading, and
# extract its ceiling alongside the payload's asserted rank.
_TO_CEILING_RANK = [
    "dup", {"lit": "producer"}, "getf",
    {"lit": "authority:"}, "swap", "cat", "sense",
    {"lit": "value"}, "getf", {"lit": "ceiling"}, "getf",
    "swap", {"lit": "rank"}, "getf",
]

# From [ceiling, rank]: swap to [rank, ceiling], duplicate the
# ceiling, and leave [rank, ceiling, ceiling-is-not-null] -- the
# gate both ceiling words branch on.
_NULL_GATE = ["swap", "dup", {"lit": None}, "eq", "not"]
_DROP2 = ["drop", "drop"]


def _authority_example(producer, ceiling, grants, rank, expect):
    name = "authority:%s" % producer
    payload = {"producer": producer, "rank": rank,
               "sense_name": name}
    reading = {"value": {"ceiling": ceiling, "grants": grants},
               "method": "example", "as_of_seq": 0}
    return {"args": [payload],
            "state": {"senses": {name: reading}},
            "expect": [expect]}


def _definitions():
    rank_granted = {
        "name": "rank-granted",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        # then: [rank, ceiling] -> rank > ceiling -> not (<=);
        # else: drop both, answer False (no grant).
        "body": _TO_CEILING_RANK + _NULL_GATE + [
            {"if": ["gt", "not"],
             "else": _DROP2 + [{"lit": False}]}],
        "examples": [
            _authority_example("captain", 5, 1, 5, True),
            _authority_example("captain", 5, 1, 3, True),
            _authority_example("captain", 5, 1, 6, False),
            _authority_example("mallory", None, 0, 9, False),
            _authority_example("mallory", None, 0, 0, False)],
    }
    effective_rank = {
        "name": "effective-rank",
        "signature": {"ins": ["map"], "outs": ["int"]},
        # then: [rank, ceiling] -> min2 (the clamp);
        # else: drop both, answer 0 (no grant).
        "body": _TO_CEILING_RANK + _NULL_GATE + [
            {"if": ["min2"],
             "else": _DROP2 + [{"lit": 0}]}],
        "examples": [
            _authority_example("captain", 5, 1, 5, 5),
            _authority_example("captain", 5, 1, 3, 3),
            _authority_example("captain", 2, 1, 5, 2),
            _authority_example("mallory", None, 0, 9, 0)],
    }
    rank_below = {
        "name": "rank-below",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["dup", {"lit": "rank"}, "getf", "swap",
                 {"lit": "limit"}, "getf", "lt"],
        "examples": [
            {"args": [{"rank": 0, "limit": 5}], "expect": [True]},
            {"args": [{"rank": 5, "limit": 5}], "expect": [False]},
            {"args": [{"rank": 7, "limit": 5}], "expect": [False]}],
    }
    return [rank_granted, effective_rank, rank_below]


def install_words(seq):
    """Install the three rank words as operator definitions.
    Returns the verdicts; raises if any was refused (fail loud,
    never half-installed)."""
    register()
    verdicts = {}
    for defn in _definitions():
        verdict = seq.submit(make_envelope(
            "operator", "definition", copy.deepcopy(defn), [],
            "probe-c-def-" + defn["name"]))
        verdicts[defn["name"]] = verdict
        if verdict["status"] != "accepted":
            raise RuntimeError("definition %s refused: %r"
                               % (defn["name"], verdict))
        if verdict["computed_effects"] != []:
            raise RuntimeError("definition %s must be pure, got %r"
                               % (defn["name"], verdict))
    return verdicts
