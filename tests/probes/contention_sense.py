"""Probe A, rung 4 candidate: a parameterised contention sense.

Quarantined in tests/probes/ -- this module edits nothing in
src/. It registers one additional sense, ``contention``, into
``jacquard.senses.SENSES`` at runtime (``register()``), with the
same callable signature and return shape as the built-in senses:
``fn(entries, state, subject, runtime) -> {"value", "method"}``.

Subject grammar::

    contention:<box>/<seat>/<start>/<end>/<producer>/<id>

parsed by splitting from the RIGHT (id last, then producer,
then end, then start, then seat; the box is whatever remains,
joined by "/"), so box names carrying "/" survive.

The sense is a pure function of (entries, state): it reads
committed units, mutates nothing, appends nothing, and its
output is deterministically sorted. It is the kernel-computed
projection the booking machine's guards consume via the existing
``sense`` primitive: publish it at decision time, then a guard
word reads the published reading from folded state.

Revision against the independent adversarial corpus: the
subject grammar originally carried no candidate *id*, so the
sense could not express the trial walk's identity skip ("a
booking never contends with itself") when a committed row
reused the candidate's id under a DIFFERENT producer -- the
only two divergences in that corpus. The grammar now carries
the candidate id as its final field and the sense excludes a
committed row whose id equals it, in addition to the existing
same-producer renewal exclusion, so both cases match exactly.
See test_probe_a.py's adversarial runner.
"""
from jacquard import senses as _senses_module

EXCLUSIVE_SEATS = {"zcode", "mcode", "claude-code", "gpu", "stage",
                   "kimi", "box"}

METHOD = (
    "contention sense: read set = committed units with prefix "
    "booking/<box>/ (the subject's box); a committed booking "
    "contends iff ALL of: status is \"active\" only (done, "
    "cancelled, preempted and expired bookings are inert); its "
    "id differs from the candidate's id (a booking never "
    "contends with itself -- a committed row whose id equals "
    "the candidate's id is excluded even when its producer "
    "differs); its producer differs from the candidate's "
    "producer (a same-producer overlap is a renewal, not "
    "contention); its "
    "checkby is null or >= the candidate start (a booking whose "
    "check-by passed before the candidate starts is dead by the "
    "board protocol); seat rules -- equal seats contend iff the "
    "seat is in {zcode, mcode, claude-code, gpu, stage, kimi, "
    "box}, \"box\" contends with every seat, other distinct "
    "seats do not contend; and strict interval overlap "
    "candidate.start < other.end and other.start < candidate.end "
    "(touching endpoints do not contend). Value reports every "
    "contender sorted by id, their count, the maximum contender "
    "rank (-1 when none) and the highest-rank contender's id "
    "(ties: smallest id, null when none). Rank otherwise plays "
    "no part in contention itself."
)


def seats_conflict(candidate_seat, other_seat):
    """Port of the trial's seat rule (see METHOD)."""
    if candidate_seat == other_seat:
        return candidate_seat in EXCLUSIVE_SEATS
    if "box" in (candidate_seat, other_seat):
        return True
    return False


def parse_subject(subject):
    """-> (box, seat, start, end, producer, id). Splits from
    the right so the box may itself contain "/"."""
    if not subject:
        raise ValueError("contention sense needs a subject")
    parts = subject.rsplit("/", 5)
    if len(parts) != 6:
        raise ValueError(
            "contention subject must be "
            "<box>/<seat>/<start>/<end>/<producer>/<id>: %r"
            % subject)
    box, seat, start, end, producer, cand_id = parts
    try:
        return box, seat, int(start), int(end), producer, cand_id
    except ValueError:
        raise ValueError(
            "contention subject start/end must be integer minutes: "
            "%r" % subject)


def contention_sense(entries, state, subject, runtime):
    box, seat, cand_start, cand_end, producer, cand_id = \
        parse_subject(subject)
    prefix = "booking/%s/" % box
    contenders = []
    for unit in sorted(state.units):
        if not unit.startswith(prefix):
            continue
        other = state.units[unit]
        if not isinstance(other, dict):
            continue
        if other.get("status") != "active":
            continue
        if other.get("id") == cand_id:
            continue
        if other.get("producer") == producer:
            continue
        checkby = other.get("checkby")
        if checkby is not None and checkby < cand_start:
            continue
        if not seats_conflict(seat, other.get("seat")):
            continue
        if not (cand_start < other["end"] and other["start"] < cand_end):
            continue
        contenders.append({"id": other["id"],
                           "producer": other["producer"],
                           "seat": other["seat"],
                           "start": other["start"],
                           "end": other["end"],
                           "rank": other.get("rank", 0)})
    contenders.sort(key=lambda c: c["id"])
    if contenders:
        max_rank = max(c["rank"] for c in contenders)
        top_id = min(c["id"] for c in contenders if c["rank"] == max_rank)
    else:
        max_rank = -1
        top_id = None
    return {"value": {"contenders": contenders,
                      "count": len(contenders),
                      "max_rank": max_rank,
                      "top_id": top_id},
            "method": METHOD}


def register():
    """Insert the sense into jacquard.senses.SENSES under
    "contention". Idempotent."""
    _senses_module.SENSES["contention"] = contention_sense
    return contention_sense
