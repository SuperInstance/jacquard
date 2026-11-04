#!/usr/bin/env python3
"""W3 core-set + variant builder (deterministic, stdlib only).

FIXED BEFORE ANY JUDGE RUN (2026-11-04, profiler):
- Core set = the E8 battery verbatim (experiments/wsp/e8/{diagnostic,heldout}.jsonl,
  165 items; the 166th E8 item was dropped by the Phase 15 coordinator before
  scoring, see experiments/wsp/e8/BATTERY.md). No item added, removed or edited.
  Extension attempt (documented in W3-PROFILE.md): post-E8 governance-log
  proposals (Phase 15/16, seq>=246) are weight-patch deployment releases whose
  final outcomes duplicate E8 proof sources; no new decision-context class was
  renderable without inventing context, so none was added.
- Judge mapping (pre-stated): question = the trained go-no-go family question
  "Should this action proceed?"; argmax class pos->ALLOW, zero->HOLD, neg->DENY.
- Variants are mechanical only (no model, no hand paraphrase):
  G1: trunc_half, upper, wrapper, whitespace
  G2: field_reorder (reverse '; '-separated fields), label_paraphrase
      (fixed label substitutions, values untouched)
- Sealed half: sha256(item id) first byte odd -> heldout-sealed, even -> visible.
  The sealed file is committed hashed; a patcher must never tune on it.
"""
import hashlib, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parent

def load_core():
    items=[]
    for name in ("diagnostic","heldout"):
        for line in open(ROOT/"experiments"/"wsp"/"e8"/f"{name}.jsonl"):
            if line.strip():
                r=json.loads(line)
                items.append({k:r.get(k) for k in ("id","split","source","order_ts","context","gold","operator_correct","correct_outcome")})
    return items

SUBS=[("producer:","submitted by:"),("effect:","action:"),("resource:","target resource:"),
      ("planned duration:","duration planned:"),("contention:","conflict state:"),
      ("policy facts:","rules:"),("task:","work:"),("start:","begins:")]
def g1(kind, ctx):
    if kind=="trunc_half": return ctx[:len(ctx)//2]
    if kind=="upper": return ctx.upper()
    if kind=="wrapper": return "Note: please consider the following proposal.\n"+ctx+"\n(End of proposal.)"
    if kind=="whitespace": return ctx.replace("; "," ;\n   ").replace(": ",":    ")
    raise ValueError(kind)
def g2(kind, ctx):
    if kind=="field_reorder":
        parts=ctx.split("; ")
        return "; ".join(reversed(parts)) if len(parts)>2 else ctx
    if kind=="label_paraphrase":
        out=ctx
        for a,b in SUBS: out=out.replace(a,b)
        return out
    raise ValueError(kind)

def main():
    core=load_core()
    (OUT/"core.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in core))
    vis, sealed = [], []
    for r in core:
        for cls, kinds, fn in (("G1",("trunc_half","upper","wrapper","whitespace"),g1),
                               ("G2",("field_reorder","label_paraphrase"),g2)):
            for kind in kinds:
                v={"id":f"{r['id']}::{kind}","base_id":r["id"],"class":cls,"kind":kind,
                   "split":r["split"],"source":r["source"],"context":fn(kind,r["context"]),
                   "gold":r["gold"],"operator_correct":r["operator_correct"],"correct_outcome":r["correct_outcome"]}
                sealed_flag = hashlib.sha256(r["id"].encode()).digest()[0] % 2 == 1
                (sealed if sealed_flag else vis).append(v)
    for name, rows in (("variants-visible.jsonl",vis),("variants-heldout-sealed.jsonl",sealed)):
        (OUT/name).write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows))
    print(f"core={len(core)} visible={len(vis)} sealed={len(sealed)}")
if __name__=="__main__": main()
