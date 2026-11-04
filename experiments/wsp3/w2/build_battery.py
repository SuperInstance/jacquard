#!/usr/bin/env python3
"""W2 battery builder — gpu-queue job-shape (foundry archetype).

Reads a COPY of the Thor gpu-queue record (queue.json) and builds
the temporal-split battery defined in ../W2-BATTERY.md:

  diagnostic = earliest 70% of foundry jobs by `added` time
  heldout    = latest 30%  (sealed; hash recorded, never shown
               to the patcher)

A foundry job is one whose recorded cmd carries `--archetype`;
its label is that recorded archetype. Item schema mirrors the
Phase 15 E7 battery ({id, split, label, subtype, boundary,
message}) plus provenance ({job_id, added, kind}).

Also emits leakage.json: exact / normalised duplicate counts,
digit-normalised template overlap across the split boundary,
and cross-split token-Jaccard statistics (nearest neighbour per
held-out item) — the checks that caught the E7 reskin in
Phase 15, run here expecting them to FAIL the joint (see
W2-INVENTORY.md: the label is verbatim in the input).

Usage:
  python3 build_battery.py --queue queue.json --outdir .
Stdlib only. Deterministic: sort key is (added, id).
"""
import argparse, hashlib, json, re
from pathlib import Path

LABELS = ("fishing_boat", "harbor_house", "pier", "spruce")


def archetype(cmd):
    m = re.search(r"--archetype (\w+)", cmd or "")
    return m.group(1) if m else None


def tokens(text):
    return set(re.findall(r"[a-z0-9_]+", (text or "").lower()))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def norm_template(text):
    return re.sub(r"\d+", "N", text or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", required=True, help="copy of Thor queue.json")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    jobs = json.loads(Path(a.queue).read_text())["jobs"]
    foundry = [j for j in jobs if archetype(j.get("cmd")) in LABELS]
    foundry.sort(key=lambda j: (j["added"], j["id"]))
    cut = int(len(foundry) * 0.7)
    splits = {"diagnostic": foundry[:cut], "heldout": foundry[cut:]}
    written = {}
    for split, part in splits.items():
        items = []
        for i, j in enumerate(part, 1):
            items.append({
                "id": f"w2{'diag' if split=='diagnostic' else 'held'}-{i:04d}",
                "split": split, "label": archetype(j["cmd"]),
                "subtype": j.get("kind"), "boundary": j.get("kind") != "feeder",
                "message": f"{j['name']}\n{j['cmd']}",
                "job_id": j["id"], "added": j["added"], "kind": j.get("kind"),
            })
        name = "diagnostic.jsonl" if split == "diagnostic" else "heldout.sealed.jsonl"
        data = "".join(json.dumps(it) + "\n" for it in items)
        (outdir / name).write_text(data)
        written[split] = {"n": len(items), "file": name,
                          "sha256": hashlib.sha256(data.encode()).hexdigest(),
                          "range": [part[0]["added"], part[-1]["added"]]}
        print(f"{split}: n={len(items)} sha256={written[split]['sha256']}")
    # ---- leakage checks across the boundary ----
    diag, held = splits["diagnostic"], splits["heldout"]
    dmsg = [f"{j['name']}\n{j['cmd']}" for j in diag]
    hmsg = [f"{j['name']}\n{j['cmd']}" for j in held]
    dtok = [tokens(m) for m in dmsg]
    exact_cross = len(set(dmsg) & set(hmsg))
    dtmpl = set(norm_template(m) for m in dmsg)
    held_tmpl_seen = sum(1 for m in hmsg if norm_template(m) in dtmpl)
    maxj, sumj = 0.0, 0.0
    for hm in hmsg:
        ht = tokens(hm)
        best = max(jaccard(ht, dt) for dt in dtok)
        maxj = max(maxj, best); sumj += best
    leak = {"exact_duplicate_messages_cross_split": exact_cross,
            "held_items_with_digit_normalised_template_in_diag": held_tmpl_seen,
            "held_n": len(hmsg),
            "cross_split_token_jaccard_max": round(maxj, 4),
            "cross_split_token_jaccard_mean_nearest": round(sumj / len(hmsg), 4),
            "distinct_cmd_templates_total": len(set(norm_template(j["cmd"]) for j in foundry))}
    (outdir / "leakage.json").write_text(json.dumps(leak, indent=1))
    (outdir / "split.json").write_text(json.dumps(written, indent=1))
    print(json.dumps(leak, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
