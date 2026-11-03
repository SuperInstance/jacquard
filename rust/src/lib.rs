//! Jacquard kernel — Rust implementation (Phase 8, slice 20).
//!
//! A port of the kernel contract in `spec/SPEC.md` (version
//! 0.5), mirroring the TypeScript conformance layout in
//! `conformance/ts/`: `core` corresponds to `jacquard.ts`
//! (canonical serialisation, envelope, hash-chained log, fold)
//! and `kernel` to `kernel.ts` (dictionary + evaluator,
//! sequencer with the section 7.1 wait pump, policy gate),
//! with `senses` (section 11.3), `signature` (section 12.1)
//! and `anchor` (section 15.5) split out from the same port.
//!
//! Port scope is the TS port's scope, recorded in
//! `rust/GAPS.md`: a kernel without the lifecycle machines
//! installed (spec section 10.4).

pub mod anchor;
pub mod core;
pub mod kernel;
pub mod senses;
pub mod signature;
pub mod value;
