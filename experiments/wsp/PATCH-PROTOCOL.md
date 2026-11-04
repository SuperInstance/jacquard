# Patch Protocol — the contract every weight patch in Phase 15 follows

## Artefacts (all inside the patcher's working directory)

1. `patch.py` — a data-driven applier:
   `python3 patch.py --edits edits.json --model BASE_DIR --out OUT_DIR
   [--exclude id,id,...] [--only id,id,...]`
   It loads the base model weights, applies the edits named in
   edits.json (minus --exclude, or only --only), writes a complete
   model directory to OUT_DIR, and prints a receipt: edits applied,
   exact scalar count changed, fraction of total parameters.
   No randomness anywhere in patch.py; every new value is either
   explicit in edits.json or a deterministic formula over the base
   tensor's own values, stated in the edit record.
2. `edits.json` — the edit list. Each edit:
   {"id": "E1", "tensor": "<safetensors key>",
    "selector": {"kind": "rows|cols|elements|slice",
                 ...coordinates...},
    "op": "set|add|scale",
    "value": <number or list or formula string>,
    "group": "<failure mode this addresses>",
    "critical": true|false}
   Sparsity bound: total changed scalars <= 0.1% of the model's
   parameter count (the apply receipt must prove it).
3. `EXPLANATION.md` — per group: which weights, what they compute
   (the patcher's stated model of the mechanism), why these edits,
   which failure evidence motivates them. The `critical` flags are
   a PREDICTION: ablating the critical set should kill the effect;
   ablating an equal count of non-critical edits should not.
   E4 tests exactly this prediction.

## Rules

- The gated original at ~/wsp-exp/models/Qwen3-0.6B is read-only.
  Work on copies. Residents are never touched.
- The patcher sees: the diagnostic split (items, gold answers,
  base-model outputs), per-category validation AGGREGATES, the
  model config, and its own diagnostic scoring runs. It never
  sees validation items, held-out material, or forgetting
  material — in files, prompts, or conversation — and does not
  ask for them. Scores on those splits come back only as the
  coordinator's verdicts after a patch is final.
- Iteration happens on the diagnostic split only. A patch is
  FINAL when the patcher declares it; the coordinator then
  scores validation -> heldout -> forgetting, in that order,
  with the verified harness. Post-verdict tweaks make a NEW
  patch version (v2, v3...), each with its own edit list and
  explanation delta. Nothing is silently re-rolled.
- Every claim in EXPLANATION.md must be checkable against the
  edit list or the diagnostic evidence. Mechanism stories the
  ablation contradicts get recorded as contradicted, not edited
  away.
