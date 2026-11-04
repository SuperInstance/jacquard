#!/usr/bin/env python3
"""Incumbent baseline for the R4 battery: the real elephant
PanicDial, imported unmodified from a sparse checkout of
SuperInstance/elephant, run over real Room/Message objects
built from the battery items.

    python3 run_incumbent.py --elephant ~/wsp-exp16/r4/elephant-src \
        --battery diagnostic.jsonl --out results/incumbent_diagnostic.json

Class form (pre-stated, untuned): reading < 1/3 -> calm,
< 2/3 -> alarmed, else stampede.

Battery representation of replies: a message's n_replies is
realised as that many stub Message objects (empty text, no
reactions, no replies) in its .replies list, exactly as
documented in R4-INVENTORY.md; stubs are not members of
room.messages, so they affect only Room.ripple.

--selftest checks the runner against three hand-worked
readings (the arithmetic is in this file's test only; scoring
always uses the imported dial).
"""
import argparse
import json
import sys
from pathlib import Path

LABELS = ("calm", "alarmed", "stampede")


def classify(reading):
    if reading < 1.0 / 3.0:
        return "calm"
    if reading < 2.0 / 3.0:
        return "alarmed"
    return "stampede"


def build_room(item, Room, Message):
    msgs = []
    for m in item["messages"]:
        stubs = [Message(author="reply", text="", ts=m["ts"])
                 for _ in range(m["n_replies"])]
        msgs.append(Message(author=m["author"], text=m["text"],
                            ts=m["ts"], reactions=dict(m["reactions"]),
                            replies=stubs))
    return Room(item["id"], msgs)


def summarise(records):
    per_class, confusion = {}, {}
    for r in records:
        c = per_class.setdefault(r["gold"], [0, 0])
        c[1] += 1
        c[0] += 1 if r["correct"] else 0
        row = confusion.setdefault(r["gold"], {})
        row[r["predicted"]] = row.get(r["predicted"], 0) + 1
    n = len(records)
    return {"n": n,
            "accuracy": sum(r["correct"] for r in records) / n if n else 0.0,
            "per_class": {k: {"correct": v[0], "n": v[1],
                              "accuracy": v[0] / v[1]}
                          for k, v in sorted(per_class.items())},
            "confusion": {k: dict(sorted(v.items()))
                          for k, v in sorted(confusion.items())}}


def run_selftest(PanicDial, Room, Message):
    import math
    dial = PanicDial()
    cases = []
    cases.append(("empty room", dial.read(Room("t", [])), 0.0))
    r = Room("t", [Message("a", "fire", ts=0.0)])
    cases.append(("one word fire", dial.read(r), 0.40))
    m1 = Message("a", "fire", ts=0.0, reactions={"x": 20})
    m2 = Message("b", "go", ts=10.0)
    r = Room("t", [m1, m2])
    want = 0.40 + 0.20 + 0.15 * (1.0 - math.exp(-12.0 / 30.0))
    cases.append(("fire + 20 reactions + density", dial.read(r), want))
    bad = 0
    for name, got, want in cases:
        ok = abs(got - want) < 1e-9
        bad += 0 if ok else 1
        print(f"{'ok' if ok else 'FAIL'}: {name} got={got:.6f} want={want:.6f}")
    print(f"SELFTEST {'PASS' if not bad else 'FAIL'} ({len(cases)} cases)")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elephant", help="elephant sparse checkout root")
    ap.add_argument("--battery")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if not args.elephant:
        ap.error("--elephant is required")
    sys.path.insert(0, str(Path(args.elephant).resolve()))
    from elephant.dials.panic import PanicDial
    from elephant.room import Message, Room

    if args.selftest:
        return run_selftest(PanicDial, Room, Message)
    if not args.battery:
        ap.error("--battery is required")
    items = [json.loads(ln) for ln in
             Path(args.battery).read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    dial = PanicDial()
    records = []
    for it in items:
        reading = dial.read(build_room(it, Room, Message))
        pred = classify(reading)
        records.append({"id": it["id"], "gold": it["label"],
                        "subtype": it["subtype"], "boundary": it["boundary"],
                        "reading": round(reading, 6), "predicted": pred,
                        "correct": pred == it["label"]})
    split = items[0]["split"]
    res = summarise(records)
    res["items"] = records
    print(f"{split}: accuracy={res['accuracy']:.4f} (n={res['n']})")
    for lab in LABELS:
        pc = res["per_class"].get(lab)
        if pc:
            print(f"  {lab}: {pc['correct']}/{pc['n']} ({pc['accuracy']:.3f})")
    print(f"  confusion: {json.dumps(res['confusion'])}")
    nb = [r for r in records if r["boundary"]]
    if nb:
        bacc = sum(r["correct"] for r in nb) / len(nb)
        print(f"  boundary subset: {sum(r['correct'] for r in nb)}/{len(nb)} "
              f"({bacc:.3f})")
        res["boundary_accuracy"] = bacc
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(
            {"model": "elephant PanicDial @44e7363 (real import)",
             "thresholds": "equal-thirds, pre-stated, untuned",
             "splits": {split: res}}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
