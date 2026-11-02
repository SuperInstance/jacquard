"""Jacquard: accountable agent state.

A hash-chained log that is the record, a sequencer that is the
only writer, a dictionary whose definitions carry computed
effects, and a small versioned policy gate with a batched
decision queue. See spec/SPEC.md.
"""
from .canonical import SPEC_SEAL, SPEC_VERSION, canonical, hash_of
from .envelope import envelope_hash, make_envelope, validate_envelope
from .lifecycles import LIFECYCLES, install_lifecycles
from .log import Log
from .machines import check_machine, find_transition, parse_machine
from .records import output_use_ratio, outputs_and_uses, records
from .sequencer import Sequencer
from .state import Refusal, State, fold, rule_stage

__all__ = [
    "SPEC_SEAL", "SPEC_VERSION", "canonical", "hash_of",
    "envelope_hash", "make_envelope", "validate_envelope",
    "LIFECYCLES", "install_lifecycles",
    "Log", "check_machine", "find_transition", "parse_machine",
    "output_use_ratio", "outputs_and_uses", "records",
    "Sequencer", "Refusal", "State", "fold", "rule_stage",
]
