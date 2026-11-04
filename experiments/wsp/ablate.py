#!/usr/bin/env python3
"""E4 ablation runner (coordinator-only).

Takes a FINAL patch (patch.py + edits.json per PATCH-PROTOCOL.md)
and builds the ablation variants:
  full           — the patch as declared
  minus_critical — patch with the patcher's `critical` edits excluded
  minus_random   — patch with a random equal-count set of
                   NON-critical edits excluded (seeded, recorded)
Each variant is materialised with the patcher's own patch.py and
scored by the coordinator with the harness score.py on the
held-out and forgetting splits (the splits the patcher never saw).
Base-model scores come from the baseline results file.

Usage:
  python3 ablate.py --patch-dir DIR --base DIR --harness DIR
                    --work DIR --out JSON [--seed 41]
"""
import argparse, json, pathlib, random, subprocess, sys

PY = str(pathlib.Path.home() / "ml" / ".venv" / "bin" / "python")


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        raise SystemExit(f"command failed: {cmd[0]}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch-dir", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=41)
    a = ap.parse_args()

    pd = pathlib.Path(a.patch_dir); work = pathlib.Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    edits = json.loads((pd / "edits.json").read_text())
    elist = edits["edits"] if isinstance(edits, dict) else edits
    crit = [e["id"] for e in elist if e.get("critical")]
    noncrit = [e["id"] for e in elist if not e.get("critical")]
    print(f"edits: {len(elist)} total, {len(crit)} critical, {len(noncrit)} non-critical")
    if not crit:
        raise SystemExit("no critical edits declared — ablation prediction untestable")
    if len(noncrit) < len(crit):
        raise SystemExit("fewer non-critical than critical edits — random control impossible")

    rng = random.Random(a.seed)
    rand_excl = sorted(rng.sample(noncrit, len(crit)))
    print(f"random control excludes {rand_excl} (seed {a.seed})")

    variants = {"full": [], "minus_critical": crit, "minus_random": rand_excl}
    splits = ["heldout", "forget_instr", "forget_fact", "forget_prose", "validation"]
    results = {"critical": crit, "random_excluded": rand_excl, "seed": a.seed,
               "variants": {}}
    for name, excl in variants.items():
        vdir = work / name
        cmd = [PY, str(pd / "patch.py"), "--edits", str(pd / "edits.json"),
               "--model", a.base, "--out", str(vdir)]
        if excl:
            cmd += ["--exclude", ",".join(excl)]
        receipt = run(cmd)
        merged = {}
        for sp in splits:
            out_json = work / f"scores-{name}-{sp}.json"
            run([PY, str(pathlib.Path(a.harness) / "score.py"), "--model", str(vdir),
                 "--split", sp, "--out", str(out_json)])
            merged.update(json.loads(out_json.read_text())["splits"])
        results["variants"][name] = {"receipt_tail": receipt.strip().splitlines()[-3:],
                                     "splits": merged}
    pathlib.Path(a.out).write_text(json.dumps(results, indent=1))
    for name, v in results["variants"].items():
        h = v["splits"]["heldout"]["accuracy"]
        print(f"{name}: heldout {h:.3f}")


if __name__ == "__main__":
    main()
