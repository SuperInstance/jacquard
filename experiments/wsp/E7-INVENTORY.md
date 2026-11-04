# E7 inventory — signal-chain soft joint (read-only pass, 2026-11-04)

Repo: SuperInstance/signal-chain @ f113fbf (read-only clone
~/sigchain-read on the Oracle). Contents: a Rust DSP library
(src/lib.rs, 577 lines: SineOsc/Gain/LowPass/Delay/Clipper in a
SignalChain pipeline), the thesis README, and
signal_chain_dial.py — a self-contained reference
implementation of elephant's ModelVsCodeDial.

Findings:
- The Rust DSP chain has NO judgement joint: every stage is a
  pure function of its parameters. All hard, by design.
- The workflow with a soft joint is the room-reading pipeline
  the dial serves: raw events -> dials -> field -> tint/nudge
  (README thesis diagram). Inside signal-chain itself, the
  joint lives in signal_chain_dial.py::_score.
- THE JOINT: the spine (hard, decided) is feature extraction —
  lexicon membership counts (MODEL_WORDS/MODEL_PHRASES,
  CODE_WORDS/CODE_PHRASES) and code-symbol density. The
  judgement the spine cannot make is the WEIGHTING: _score
  counts every hit equally (a hedge phrase = a keyword = one
  symbol cluster) and maps (model-code)/total onto [-1,+1].
  On mixed messages — warm commit messages, prose quoting
  code, error-shaped prose, terse human chat — equal weighting
  is exactly where the reading goes wrong, and no decision
  tree over these features fixes it, because the right weight
  is contextual (who is speaking, what the symbols are doing).
- Narrow set for the loop (to be built at slice 43): messages
  labelled on the model<->code spectrum (3-way: code / mixed /
  model, plus the continuous reading as a secondary score).
  Labels by construction + provenance (real commit messages,
  real model prose, engineered mixtures at known ratios);
  held-out = a disjoint source pool. Teacher = strong-model
  readings on the same items. The student learns the joint;
  the spine (feature counting, field math, tint rules) stays
  exactly as auditable as it is today.
- Claim under test (Casey's): hard spine stays auditable,
  only the joints are soft, and each joint's coaching rounds
  are themselves a governed record (the E6 loop log).
