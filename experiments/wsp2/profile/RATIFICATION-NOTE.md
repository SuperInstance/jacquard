# Coordinator note — the ratification log (2026-11-04)

The slice-45 governance ratification (5 proposals, 5
decisions, 12 evidence entries for the profile patches) was
executed by the grader in its own clone, against the
governance log as it stood at the patcher branch point —
237 entries. In parallel the coordinator appended the R4
round entries to the log on main (279 entries). The two
chains share their first 237 entries byte-identically
(sha256-verified) and then diverge; a hash-chained log
cannot be union-merged without re-chaining, and re-chaining
would have invalidated the proposal ids cited in
PROFILE-RESULTS.md.

Resolution, recorded rather than smoothed: the log on main
(experiments/wsp/governance/kernel.jsonl, 279 entries)
remains the canonical chain — criteria, the R1 and R3
verdicts, and the R4 proposals/decisions. The grader's
ratification chain is preserved verbatim at
experiments/wsp2/profile/ratification-kernel.jsonl
(398 entries: the shared 237 + the ratification appends) —
itself a complete, internally valid Jacquard log whose
state includes all 22 ratification submissions. Both logs
replay; neither was rewritten.
