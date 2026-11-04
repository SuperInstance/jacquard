#!/usr/bin/env python3
"""Independent checks for the R4 PanicDial battery.

The verifier carries its OWN copy of the gold function from
R4-BATTERY.md and recomputes every item's label from its stored
construction parameters (genuine / corroborators /
roomwide_action) -- never from the text, never from the
incumbent, never from any model.

Checks:
 1. JSONL validity + required fields/types, all splits
 2. sizes and class balance (120 = 40/40/40; 60 = 20/20/20)
 3. id format / uniqueness / sequence per split
 4. gold recomputation from construction parameters == label
 5. subtype <-> construction-parameter consistency (own table)
 6. structural room sanity: 3..12 messages; author/text present;
    ts non-decreasing, first ts == 0; reactions values >= 0 ints;
    n_replies >= 0 int
 7. construction plausibility: genuine items have at least
    corroborators+1 distinct authors; roomwide_action items
    have >= 3 distinct authors; non-genuine items have
    corroborators == 0 and roomwide_action == False
 8. boundary share reported per split (target ~40%)
 9. no exact duplicate items (concatenated normalised text)
    within or across splits
10. no normalised message text shared across splits
11. cross-split near-duplicate screen: token Jaccard over each
    item's full concatenated message text, all split pairs;
    maximum reported, must be < 0.60

Prints PASS/FAIL per check; exit 0 iff all pass. Stdlib only.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {"calm", "alarmed", "stampede"}
FILES = {"diagnostic": ("diagnostic.jsonl", "r4diag", 120, 40),
         "validation": ("validation.jsonl", "r4val", 60, 20),
         "heldout": ("heldout.jsonl", "r4held", 120, 40)}
JACCARD_THRESHOLD = 0.60

# verifier's own subtype -> (genuine, minor, boundary) expectations
SUBTYPE_PARAMS = {
    "everyday_chat": (False, False, False),
    "work_routine": (False, False, False),
    "trivia_burst": (False, False, True),
    "surprise_urgency": (False, False, True),
    "drill_notice": (False, False, True),
    "fiction_discussion": (False, False, True),
    "negated_alarm": (False, False, True),
    "polysemy_calm": (False, False, True),
    "first_report": (True, False, False),
    "minor_incident": (True, True, False),
    "weather_warning": (True, False, False),
    "uncertain_signal": (True, False, False),
    "slow_burn_technical": (True, False, True),
    "single_loud_voice": (True, False, True),
    "confirmed_spread": (True, False, False),
    "fast_water": (True, False, False),
    "impact_event": (True, False, False),
    "evacuation_underway": (True, False, False),
    "technical_cascade": (True, False, True),
    "escalating_cascade": (True, False, True),
}

results = []


def report(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: {name}"
          + (f" ({detail})" if detail else ""))


def gold_from_params(c):
    """The verifier's own copy of the R4-BATTERY.md gold function."""
    if not c["genuine"]:
        return "calm"
    if c["roomwide_action"] or c["corroborators"] >= 3:
        return "stampede"
    return "alarmed"


def normalise(text):
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def item_text(it):
    return "\n".join(m["text"] for m in it["messages"])


def load(split):
    fn, _p, _n, _pc = FILES[split]
    items, errors = [], []
    with (HERE / fn).open(encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if not ln.strip():
                errors.append(f"{split}:{i} blank")
                continue
            try:
                items.append(json.loads(ln))
            except ValueError as e:
                errors.append(f"{split}:{i} {e}")
    return items, errors


def main():
    all_items = {}
    for split in FILES:
        items, errors = load(split)
        all_items[split] = items
        ok = not errors and all(
            isinstance(it.get("id"), str)
            and isinstance(it.get("label"), str)
            and isinstance(it.get("subtype"), str)
            and isinstance(it.get("boundary"), bool)
            and isinstance(it.get("construction"), dict)
            and isinstance(it.get("messages"), list)
            for it in items)
        report(f"{split} JSONL validity + required fields", ok,
               f"n={len(items)}" + (f" errors={errors[:2]}" if errors else ""))

    for split, (_fn, prefix, n_exp, per_class) in FILES.items():
        items = all_items[split]
        counts = {lab: sum(1 for it in items if it["label"] == lab)
                  for lab in sorted(LABELS)}
        report(f"{split} size + class balance",
               len(items) == n_exp
               and all(v == per_class for v in counts.values()),
               f"n={len(items)} balance={counts}")
        ids = [it["id"] for it in items]
        seq = sorted(ids) == [f"{prefix}-{i:03d}" for i in range(1, n_exp + 1)]
        report(f"{split} id format/uniqueness/sequence",
               len(set(ids)) == len(ids) and seq)
        report(f"{split} split-field consistency",
               all(it["split"] == split for it in items))
        bad = [it["id"] for it in items
               if gold_from_params(it["construction"]) != it["label"]]
        report(f"{split} gold recomputation from construction params",
               not bad, f"mismatches={bad[:5]}")
        bad = []
        for it in items:
            exp = SUBTYPE_PARAMS.get(it["subtype"])
            c = it["construction"]
            if exp is None or (c["genuine"], c["minor"], it["boundary"]) != exp:
                bad.append(it["id"])
        report(f"{split} subtype/params/boundary consistency", not bad,
               f"mismatches={bad[:5]}")
        bad = []
        for it in items:
            ms = it["messages"]
            authors = {m["author"] for m in ms}
            c = it["construction"]
            if not (3 <= len(ms) <= 12):
                bad.append((it["id"], "n_messages"))
            if ms and ms[0]["ts"] != 0:
                bad.append((it["id"], "first_ts"))
            if any(ms[i]["ts"] > ms[i + 1]["ts"] for i in range(len(ms) - 1)):
                bad.append((it["id"], "ts_order"))
            if any(not m["author"] or not m["text"] for m in ms):
                bad.append((it["id"], "empty_field"))
            if any(not isinstance(m["n_replies"], int) or m["n_replies"] < 0
                   for m in ms):
                bad.append((it["id"], "n_replies"))
            if any(any((not isinstance(v, int)) or v < 0
                       for v in m["reactions"].values()) for m in ms):
                bad.append((it["id"], "reactions"))
            if c["genuine"] and len(authors) < c["corroborators"] + 1:
                bad.append((it["id"], "corroborators>authors"))
            if c["roomwide_action"] and len(authors) < 3:
                bad.append((it["id"], "roomwide_authors"))
            if not c["genuine"] and (c["corroborators"] != 0
                                     or c["roomwide_action"]):
                bad.append((it["id"], "calm_params"))
        report(f"{split} structural + construction plausibility", not bad,
               f"violations={bad[:5]}")
        nb = sum(it["boundary"] for it in items)
        report(f"{split} boundary share reported", True,
               f"boundary={nb}/{len(items)} = {nb / len(items):.1%}")

    texts = {s: [normalise(item_text(it)) for it in all_items[s]]
             for s in FILES}
    everything = [t for s in texts for t in texts[s]]
    report("no exact duplicate items within/across splits",
           len(set(everything)) == len(everything),
           f"unique={len(set(everything))}/{len(everything)}")
    msg_sets = {}
    for s in FILES:
        msg_sets[s] = {normalise(m["text"]) for it in all_items[s]
                       for m in it["messages"]}
    cross_msg = 0
    splits = list(FILES)
    for i in range(len(splits)):
        for j in range(i + 1, len(splits)):
            cross_msg += len(msg_sets[splits[i]] & msg_sets[splits[j]])
    report("no normalised message text shared across splits",
           cross_msg == 0, f"shared={cross_msg}")

    tok = {s: [set(t.split()) for t in texts[s]] for s in FILES}
    worst, worst_where = 0.0, None
    for i in range(len(splits)):
        for j in range(i + 1, len(splits)):
            a_list, b_list = tok[splits[i]], tok[splits[j]]
            for a in a_list:
                for b in b_list:
                    if not a or not b:
                        continue
                    jac = len(a & b) / len(a | b)
                    if jac > worst:
                        worst, worst_where = jac, (splits[i], splits[j])
    report(f"cross-split token Jaccard < {JACCARD_THRESHOLD}",
           worst < JACCARD_THRESHOLD,
           f"max={worst:.3f} between {worst_where}")

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'}: {sum(results)}/{len(results)} checks")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
