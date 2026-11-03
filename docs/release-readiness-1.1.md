# Release readiness — v1.1.0 (Phase 10 addendum)

The 1.0 checklist (`docs/release-readiness-1.0.md`) stands
for the 1.0 evidence; this addendum carries only what
Phase 10 changed and the checks re-run for this tag.

| Item | Evidence |
|---|---|
| Python suite green FROM THE TAG | (filled at verification) |
| TS conformance | unchanged by this phase (spec 0.6 erratum 3 is a deployment-policy note; golden vectors untouched) — 13 PASS / 0 SKIP / 0 FAIL as at v1.0.1 |
| Rust conformance | unchanged, same basis — 14 PASS / 0 SKIP / 0 FAIL as at v1.0.1 |
| New batteries | `tests/test_consumption.py` (6), `tests/test_consumption_gate.py` (5), `tests/test_jqgpu_note.py` (3) — all in the suite count above |
| Spec | 0.6 erratum 3 (section 17, deployment-policy note). No kernel semantics, no vectors, no seal change |
| Consumption gate state | built + tested; **not active on any live log** (slice 28 honesty gate: no qualifying job class exists on the Thor) |
| README currency | Phase 10 paragraph added; not-built list updated (gate activation, sentinel marker); stale slice-20 line corrected |
| Registry publication | unchanged from 1.0: owner steps in `docs/PUBLISHING.md`; nothing published by this phase |
| Cold-agent drill | not re-run for 1.1.0: the operator surface delta is one additive verb (`jqgpu note`) and one additive init option, both exercised by their batteries and a CLI smoke run recorded in the builder's log; the 1.0 drill's README path is unchanged. Stated as a judgement, not hidden |
