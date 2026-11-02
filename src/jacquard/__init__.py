"""Jacquard: accountable agent state.

A hash-chained log that is the record, a sequencer that is the
only writer, a dictionary whose definitions carry computed
effects, and a small versioned policy gate with a batched
decision queue. See spec/SPEC.md.
"""
from .canonical import SPEC_SEAL, SPEC_VERSION, canonical, hash_of
from .envelope import envelope_hash, make_envelope, validate_envelope
from .log import Log
from .records import output_use_ratio, outputs_and_uses, records
from .sequencer import Sequencer
from .state import Refusal, State, fold

__all__ = [
    "SPEC_SEAL", "SPEC_VERSION", "canonical", "hash_of",
    "envelope_hash", "make_envelope", "validate_envelope",
    "Log", "output_use_ratio", "outputs_and_uses", "records",
    "Sequencer", "Refusal", "State", "fold",
]
