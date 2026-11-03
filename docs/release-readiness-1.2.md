# Release readiness — v1.2.0 (Phase 11: general device)

The addendum to `docs/release-readiness-1.0.md` for the
Phase 11 release. The question it answers: which of the
device matrix's cells are real, and what backs the claim.

## The matrix, as released

| Device | Cell | State | Evidence |
|---|---|---|---|
| Thor | GPU job queue | **Real, live** | Standing deployment audited in slice 30; stranger window 3 (slice 31): 19 submitted / 12 completed / 1 failed, log 227 entries, sha256-verified round trip; sentinel-4 stands last in gpuq (job-16) |
| Oracle | Schedule board | **Real, live** | The fleet board itself runs through jqbook: 207-entry deployment log at slice 30, since grown by governed use (the tie release, five slice-31 bookings proposed/completed through the gate) |
| ProArt | Seat supervision | **Real** (deployed slice 30) | 109-entry log, sha256 3f6423b1…; stranger re-run environment-blocked (the box was dark for both booked windows — recorded, not papered over) |
| Orin | Seat supervision | **Real** | Slice-30 deployment (117-entry log, sha256 5717625e…) + two stranger runs (58 and 56 entries) under the fixed docs |
| Laptop (HP) | Single-user profile | **Pending — Casey's desk action** | Profile prepared (QUICKSTART + DEVICES); the box is not meshed and no deployment record exists. Joining: power on, join LAN, cross-authorise the fleet key or take tunnel slot 2226 |

## Verification at the tag

- Python suite: **340 passed, 7 skipped** (from the tag's
  fresh clone) — includes the slice-31 repairs: the
  booking battery on wall-clock-independent fixtures (8
  tests) and the inbox preflight tests.
- TypeScript conformance: **14 PASS, 0 SKIP, 0 FAIL**.
- Rust conformance: **14 PASS, 0 SKIP, 0 FAIL** (the
  checker gained `vectors.anchor_registry` with the
  Phase 9 registry work; the README's older "13" is
  corrected in the new head).
- Stranger test: 4 profiles in round 1 (3 completed, 1
  environment-blocked), fixes shipped, 2 re-runs completed
  clean (report: `docs/slice31-stranger-test.md`).

## What v1.2.0 is not

- Nothing is published to any registry; installs are from
  git (the batched owner steps in `docs/PUBLISHING.md`
  stand as they were).
- MCode has no adapter: its plugin hook surface is
  evidenced statically, never live-fired (DEVICES.md).
- The consumption gate remains built, tested, and
  inactive (no qualifying job class exists yet).
- The rank-tie disposition remains INTERIM (ties hold the
  challenger); nothing in this release depends on
  flipping it.
