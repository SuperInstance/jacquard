BRIEF — patcher seat (Jacquard Phase 15, slice 41: E1 + E4)

You are the patcher in a weight-space-programming experiment.
A strong model (you) will attempt what a recent MIT CSAIL
report claims is possible: improve a small model's behaviour
by editing its weights DIRECTLY — reasoning about what the
weights compute and changing a small number of them — with
no gradient descent, no fine-tuning, no training loop.

THE STUDENT: Qwen/Qwen3-0.6B (bf16), a copy lives at
~/wsp-exp/work/student-base/ on this machine (the Thor).
Your working directory is ~/wsp-exp/patcher/. Never modify
~/wsp-exp/models/ (the gated original) or anything outside
your working directory and ~/wsp-exp/work/.

THE CONTRACT: read PATCH-PROTOCOL.md (provided in your
working directory) before anything else. It defines the
artefacts (patch.py + edits.json + EXPLANATION.md), the
sparsity bound (<=0.1% of scalars, receipt-proven), the
ablation interface (--exclude / --only), and the iteration
rules. It is binding.

YOUR EVIDENCE (in your working directory):
- diag_for_patcher.jsonl — 80 diagnostic arithmetic items:
  prompt, gold answer, and the BASE model's raw output.
- validation_aggregates.json — the base model's accuracy
  per category on a 200-item validation battery you may
  NOT see item-by-item.
- inspect.json — the student's architecture summary.
Baseline numbers (coordinator-run, verified harness):
  diagnostic (80, the items in front of you): 78.8% overall
    addsub_chain 30% | compare 50% | mul_2x2 70% |
    unit_price 80% | word_2step 100% | div_exact 100% |
    mul_2x1 100% | pct_of 100%
  validation (200, aggregates in validation_aggregates.json):
    83.5% overall — addsub_chain 48% and compare 52% are
    the loud failures there; div/mul_2x1/pct/unit_price
    sit at 100% (no headroom — do not break them).
  Note the diagnostic raw outputs: on many failures the
  student writes a worked solution that runs past the
  scoring token cap, so the recorded answer is a
  mid-solution number. Distinguish, in your diagnosis,
  arithmetic slips from completion/format failures.
  Held-out and forgetting batteries are scored by the
  coordinator only after you declare a patch FINAL. A
  forgetting guard applies: a final patch that drops any
  forgetting battery by more than 5 points versus the
  base model is rejected regardless of arithmetic gains.
  Held-out n=200: treat effects under ~5 points as inside
  the noise band when you state your predicted effect.

YOUR JOB:
1. Diagnose: where does the student fail, and what kind of
   failure is it (wrong operation, arithmetic slip, format
   failure, runaway/looping output, early stop, ...)? Use
   the diagnostic items and the student's raw outputs.
   Probe the weights themselves: load the model, inspect
   the tensors your hypotheses implicate. You may run the
   diagnostic scorer (score_diag.py in your directory) as
   often as you like on patched copies.
2. Author a sparse weight patch per the protocol. Iterate
   on the diagnostic split only.
3. Explain it in EXPLANATION.md, marking which edits are
   CRITICAL — a falsifiable prediction: removing the
   critical set should kill the effect; removing an equal
   count of other edits should not. An independent ablation
   run will test your explanation exactly as stated.
4. Declare the patch FINAL in your final message: report
   your diagnostic before/after numbers, the exact edit
   count and fraction, and your predicted effect size on
   unseen items from the same distribution.

HARD RULES:
- No training: no gradient descent, no fine-tuning, no
  LoRA, no optimiser state. Your edits are authored values
  and deterministic formulas, per the protocol. (A separate
  arm of the study covers gradient methods; contaminating
  this arm voids it.)
- No asking for, seeking, or inferring the held-out or
  forgetting items. They are not in your world; scores on
  them arrive only as the coordinator's post-final verdict.
- If your honest conclusion is that no sparse authored
  patch improves this student on this evidence, SAY SO in
  the final message with your reasoning and the best
  negative evidence you gathered. A well-evidenced negative
  is a successful run of this experiment.

ENVIRONMENT NOTES (Thor): Python with torch/transformers is
~/ml/.venv/bin/python (the system python3 has neither). The
GPU is idle and yours. Your diagnostic scorer:
~/ml/.venv/bin/python score_diag.py --model <MODEL_DIR>
--split diagnostic --out <OUT.json>, run from your working
directory. Base model copy for patching experiments:
~/wsp-exp/work/student-base/ (read it, copy from it, never
write to it — your patched copies live in your own dir).
