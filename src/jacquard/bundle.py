"""State export bundles (SPEC section 14).

A bundle moves a kernel's portable state to another kernel.
What travels, in plain terms:

- configuration (committed unit values) — as-is;
- definitions and machine definitions — re-checked on entry by
  the destination's own dictionary and profile checker;
- standing rules — UNPROVEN. A rule's stage at export is carried
  as provenance only (`stage_at_export`); in the destination the
  rule re-enters at shadow and must re-earn promotion on the
  destination's own record.

What never travels: authority, credentials, standing, and
budgets. The destination issues its own budgets. The importer
refuses, by name (PROVENANCE), any bundle that tries to smuggle
them — as a top-level section, as an unknown key anywhere, or
as a rule field that purports to instruct the importer (a rule
carrying `stage` is refused; `stage_at_export` is provenance,
not an instruction). Definition and machine collisions with
different content are refused the same way; identical content
is skipped, so re-importing a bundle is safe.
"""
import copy

from .canonical import hash_of
from .envelope import make_envelope
from .state import Refusal, rule_stage

BUNDLE_FORMAT = "jacquard/state-export/1"

_TOP_KEYS = {"format", "exported_from", "config", "definitions",
             "machines", "rules"}
_CONFIG_KEYS = {"units"}
_DEFINITION_KEYS = {"name", "signature", "body", "examples"}
_RULE_KEYS = {"rule_id", "definition", "shape", "predicted_outcome",
              "support", "dominance_bp", "origin", "stage_at_export"}
_FORBIDDEN_KEYS = {"credential", "credentials", "authority",
                   "api_key", "apikey", "token", "secret", "password",
                   "budget", "budgets", "standing", "stage",
                   "import_stage", "active"}


def _scan_keys(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_KEYS or "credential" in lowered \
                    or "secret" in lowered:
                raise Refusal("PROVENANCE",
                              "bundle carries forbidden key %r at %s"
                              % (key, path))
            _scan_keys(value, path + "." + str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _scan_keys(value, "%s[%d]" % (path, index))


def _check_keys(node, allowed, what):
    extra = set(node) - allowed
    if extra:
        raise Refusal("PROVENANCE", "%s carries unknown keys %s"
                      % (what, sorted(extra)))


def export_bundle(seq, producer="operator"):
    """Assemble the portable state of a kernel into a bundle
    dict. Pure: appends nothing."""
    state = seq.state
    definitions = []
    for _name, versions in state.dictionary.items():
        stored = versions[-1]["definition"]
        definitions.append({key: copy.deepcopy(stored[key])
                            for key in ("name", "signature", "body",
                                        "examples")})
    machines = []
    for _name, versions in state.machines.items():
        stored = dict(versions[-1]["definition"])
        stored.pop("action_effects", None)
        machines.append(copy.deepcopy(stored))
    rules = []
    for rule_id, record in state.rules.items():
        exported = {key: copy.deepcopy(record[key]) for key in
                    ("rule_id", "definition", "shape",
                     "predicted_outcome", "support", "dominance_bp",
                     "origin") if key in record}
        exported["stage_at_export"] = rule_stage(state, rule_id)
        rules.append(exported)
    return {"format": BUNDLE_FORMAT,
            "exported_from": {"entries": len(seq.log.entries),
                              "state_hash": state.state_hash()},
            "config": {"units": copy.deepcopy(state.units)},
            "definitions": definitions,
            "machines": machines,
            "rules": rules}


def import_bundle(seq, bundle, producer="operator"):
    """Import a bundle into a kernel. Raises Refusal(PROVENANCE)
    for anything that must not travel, Refusal from the checker
    or dictionary for content the destination refuses on its own
    terms. Rules always re-enter at shadow."""
    if not isinstance(bundle, dict) or bundle.get("format") != BUNDLE_FORMAT:
        raise Refusal("PROVENANCE", "not a %s bundle" % BUNDLE_FORMAT)
    _check_keys(bundle, _TOP_KEYS, "bundle")
    # The smuggling scan covers the bundle's structural sections.
    # Definition bodies are code, not structure: they re-enter
    # through the dictionary, which computes their effects, so
    # they cannot carry authority whatever their contents are.
    for section in ("config", "machines", "rules", "exported_from"):
        _scan_keys(bundle.get(section, {}), "$." + section)
    config = bundle.get("config", {})
    _check_keys(config, _CONFIG_KEYS, "bundle config")
    bundle_hash = hash_of(bundle)
    seq.log.append("import", {"producer": producer,
                              "bundle_hash": bundle_hash,
                              "format": BUNDLE_FORMAT,
                              "exported_from": bundle.get("exported_from")})
    seq._refold()
    # Configuration travels as-is: one execution entry of writes.
    units = config.get("units", {})
    if units:
        applied = [{"verb": "write", "args": [unit, value]}
                   for unit, value in sorted(units.items())]
        seq.log.append("execution", {
            "producer": producer, "class": "import",
            "proposal_id": bundle_hash, "applied": applied, "uses": []})
        seq._refold()
    skipped = []
    # Definitions re-enter through the dictionary (examples are
    # re-run; computed effects are recomputed, never carried).
    for definition in bundle.get("definitions", []):
        _check_keys(definition, _DEFINITION_KEYS, "definition")
        existing = seq.state.dictionary.get(definition["name"])
        if existing:
            current = existing[-1]["definition"]
            if all(current[key] == definition[key]
                   for key in ("signature", "body", "examples")):
                skipped.append("definition:" + definition["name"])
                continue
            raise Refusal("PROVENANCE",
                          "definition %s already exists with different "
                          "content" % definition["name"])
        verdict = seq.submit(make_envelope(
            producer, "definition", definition, [],
            "import-def-" + definition["name"]))
        if verdict["status"] != "accepted":
            raise Refusal(verdict["refusal"],
                          "imported definition %s refused: %s"
                          % (definition["name"], verdict["detail"]))
    # Machines re-enter through the profile checker.
    for machine in bundle.get("machines", []):
        existing = seq.state.machines.get(machine["name"])
        if existing:
            current = dict(existing[-1]["definition"])
            current.pop("action_effects", None)
            if current == machine:
                skipped.append("machine:" + machine["name"])
                continue
            raise Refusal("PROVENANCE",
                          "machine %s already exists with different "
                          "content" % machine["name"])
        seq.submit_machine_definition(machine, producer)
    # Rules re-enter UNPROVEN, at shadow, whatever their stage at
    # export was. The stage at export is provenance, recorded on
    # the imported record, with no effect on the stage itself.
    imported_rules = []
    for rule in bundle.get("rules", []):
        _check_keys(rule, _RULE_KEYS, "rule")
        existing = seq.state.rules.get(rule["rule_id"])
        if existing is not None:
            if existing["shape"] == rule["shape"] \
                    and existing["predicted_outcome"] == \
                    rule["predicted_outcome"]:
                skipped.append("rule:" + rule["rule_id"])
                continue
            raise Refusal("PROVENANCE",
                          "rule %s already exists with different content"
                          % rule["rule_id"])
        if rule["definition"] not in seq.state.dictionary:
            raise Refusal("PROVENANCE",
                          "rule %s references missing definition %s"
                          % (rule["rule_id"], rule["definition"]))
        record = {"rule_id": rule["rule_id"],
                  "definition": rule["definition"],
                  "shape": rule["shape"],
                  "predicted_outcome": rule["predicted_outcome"],
                  "support": rule.get("support", 0),
                  "dominance_bp": rule.get("dominance_bp", 0),
                  "origin": "imported",
                  "imported_from_stage": rule.get("stage_at_export")}
        seq.log.append("rule", {"producer": producer, "rule": record})
        seq._refold()
        seq.create_machine_instance("standing-rule", rule["rule_id"],
                                    producer)
        seq.step_machine(rule["rule_id"], "evaluate", {}, producer)
        seq.step_machine(rule["rule_id"], "deploy", {}, producer)
        seq.log.append("rule", {"producer": producer,
                                "rule": {**record,
                                         "shadow_from_seq":
                                         seq.log.entries[-1]["seq"]}})
        seq._refold()
        imported_rules.append(rule["rule_id"])
    return {"status": "imported", "bundle_hash": bundle_hash,
            "definitions": len(bundle.get("definitions", [])),
            "machines": len(bundle.get("machines", [])),
            "rules_at_shadow": imported_rules, "skipped": skipped}
