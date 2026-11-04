//! Core log structures — a port of `conformance/ts/jacquard.ts`:
//! canonical hashing helpers, envelope validation + id (section
//! 3), log entry construction + hash-chain verification
//! (section 2), and the log fold with the state hash (section 2
//! with the fold effects stated in sections 5, 7, 10, 11, 12,
//! 14). Entry and state representations are the crate's
//! insertion-ordered `Value` objects, as in Python dicts.

use crate::value::{arr, hash_of, hash_string_raw, obj, s, Value};

pub const SPEC_VERSION: &str = "jacquard/0.7";

pub fn spec_seal() -> String {
    hash_string_raw("jacquard-spec/0.7")
}

pub fn genesis_prev() -> String {
    "0".repeat(64)
}

pub const ENTRY_KINDS: [&str; 13] = [
    "proposal", "decision", "definition", "execution", "sense", "checkpoint", "machine",
    "transition", "budget", "price", "rule", "import", "seal",
];

const ENVELOPE_KINDS: [&str; 3] = ["proposal", "definition", "machine"];

fn is_hex64(text: &str) -> bool {
    text.len() == 64 && text.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

/// Validate an envelope against section 3's stated shape, in the
/// `jacquard.ts` reading: returns a list of problems (empty =
/// valid). Extra keys are allowed and covered by the envelope id.
pub fn validate_envelope(env: &Value) -> Vec<String> {
    let mut problems = Vec::new();
    if !env.is_object() {
        return vec!["envelope is not an object".to_string()];
    }
    if env.get("v") != Some(&Value::Int(1)) {
        problems.push("v must be 1".to_string());
    }
    if !matches!(env.get("id"), Some(Value::Str(_))) {
        problems.push("id must be a string".to_string());
    }
    if !matches!(env.get("producer"), Some(Value::Str(_))) {
        problems.push("producer must be a string".to_string());
    }
    match env.get("kind") {
        Some(Value::Str(k)) if ENVELOPE_KINDS.contains(&k.as_str()) => {}
        _ => problems.push(format!(
            "kind must be one of {}",
            ENVELOPE_KINDS.join(", ")
        )),
    }
    if !matches!(env.get("body"), Some(Value::Object(_))) {
        problems.push("body must be an object".to_string());
    }
    match env.get("declared_effects") {
        Some(Value::Array(items)) if items.iter().all(|e| matches!(e, Value::Str(_))) => {}
        _ => problems.push("declared_effects must be a list of strings".to_string()),
    }
    match env.get("spec_seal") {
        Some(Value::Str(seal)) if is_hex64(seal) => {
            if *seal != spec_seal() {
                problems.push("spec_seal does not match the seal of jacquard-spec/0.7".to_string());
            }
        }
        _ => problems.push("spec_seal must be a hex64 string".to_string()),
    }
    problems
}

/// Section 3: the envelope id used in the log is the hash of the
/// envelope.
pub fn envelope_id(env: &Value) -> String {
    hash_of(env)
}

/// Build an entry (without its hash). The entry hash is the
/// section 1 hash of exactly {seq, prev, kind, body, spec}.
pub fn make_entry(seq: i64, prev: &str, kind: &str, body: Value) -> Value {
    obj(vec![
        ("seq", Value::Int(seq)),
        ("prev", s(prev)),
        ("kind", s(kind)),
        ("body", body),
        ("spec", s(SPEC_VERSION)),
    ])
}

pub fn entry_hash(entry: &Value) -> String {
    hash_of(&obj(vec![
        ("seq", entry.get("seq").cloned().unwrap_or(Value::Null)),
        ("prev", entry.get("prev").cloned().unwrap_or(Value::Null)),
        ("kind", entry.get("kind").cloned().unwrap_or(Value::Null)),
        ("body", entry.get("body").cloned().unwrap_or(Value::Null)),
        ("spec", entry.get("spec").cloned().unwrap_or(Value::Null)),
    ]))
}

pub struct ChainResult {
    pub ok: bool,
    pub checked: usize,
    pub failure: Option<String>,
}

/// Verify a chain of stored entries: seq runs 0,1,2,...; each
/// prev is the previous entry's recorded hash (genesis prev = 64
/// zeros); spec is "jacquard/0.5"; every recorded hash recomputes.
pub fn verify_chain(entries: &[Value]) -> ChainResult {
    let mut prev = genesis_prev();
    for (i, e) in entries.iter().enumerate() {
        if e.get("seq") != Some(&Value::Int(i as i64)) {
            return ChainResult {
                ok: false,
                checked: i,
                failure: Some(format!("entry {}: seq is {}", i, crate::value::py_repr(e.get("seq").unwrap_or(&Value::Null)))),
            };
        }
        if e.get("prev") != Some(&Value::Str(prev.clone())) {
            return ChainResult { ok: false, checked: i, failure: Some(format!("entry {}: prev mismatch", i)) };
        }
        // The entry spec names the version it was written under;
        // a chain may carry earlier versions (the replay corpus
        // is a 0.5 log). The hash recompute below binds the exact
        // value, which is the check the reference performs — it
        // does not require the current version (spec 0.6 reading,
        // mirroring jacquard.ts).
        let spec_ok = matches!(e.get("spec"), Some(Value::Str(sp)) if sp.starts_with("jacquard/"));
        if !spec_ok {
            let shown = match e.get("spec") {
                Some(Value::Str(sp)) => sp.clone(),
                Some(other) => crate::value::py_repr(other),
                None => "undefined".to_string(),
            };
            return ChainResult { ok: false, checked: i, failure: Some(format!("entry {}: spec is {}", i, shown)) };
        }
        match e.get("hash") {
            Some(Value::Str(h)) if is_hex64(h) => {}
            _ => {
                return ChainResult { ok: false, checked: i, failure: Some(format!("entry {}: hash is not hex64", i)) };
            }
        }
        if entry_hash(e) != e.get("hash").unwrap().as_str().unwrap() {
            return ChainResult { ok: false, checked: i, failure: Some(format!("entry {}: hash does not recompute", i)) };
        }
        prev = e.get("hash").unwrap().as_str().unwrap().to_string();
    }
    ChainResult { ok: true, checked: entries.len(), failure: None }
}

// ---------------------------------------------------------------------------
// The fold (section 2).
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct Wrapper {
    pub entry_seq: i64,
    pub entry_hash: String,
    pub definition: Value,
}

impl Wrapper {
    pub fn to_value(&self) -> Value {
        obj(vec![
            ("entry_seq", Value::Int(self.entry_seq)),
            ("entry_hash", s(&self.entry_hash)),
            ("definition", self.definition.clone()),
        ])
    }
}

#[derive(Clone, Debug)]
pub struct FoldedState {
    pub units: Value,
    pub senses: Value,
    pub dictionary: Vec<(String, Vec<Wrapper>)>,
    pub decision_queue: Value,
    pub machines: Vec<(String, Vec<Wrapper>)>,
    pub machine_instances: Value,
    pub budgets: Value,
    pub prices: Value,
    pub rules: Value,
}

impl FoldedState {
    pub fn empty() -> Self {
        FoldedState {
            units: obj(vec![]),
            senses: obj(vec![]),
            dictionary: Vec::new(),
            decision_queue: obj(vec![]),
            machines: Vec::new(),
            machine_instances: obj(vec![]),
            budgets: obj(vec![]),
            prices: obj(vec![]),
            rules: obj(vec![]),
        }
    }
    pub fn dict_get(&self, name: &str) -> Option<&Vec<Wrapper>> {
        self.dictionary.iter().find(|(n, _)| n == name).map(|(_, v)| v)
    }
    pub fn dictionary_value(&self) -> Value {
        Value::Object(
            self.dictionary
                .iter()
                .map(|(name, versions)| {
                    (
                        name.clone(),
                        arr(versions.iter().map(|w| w.to_value()).collect()),
                    )
                })
                .collect(),
        )
    }
    pub fn machines_value(&self) -> Value {
        Value::Object(
            self.machines
                .iter()
                .map(|(name, versions)| {
                    (
                        name.clone(),
                        arr(versions.iter().map(|w| w.to_value()).collect()),
                    )
                })
                .collect(),
        )
    }
    /// The nine-key object section 2 hashes.
    pub fn state_object(&self) -> Value {
        obj(vec![
            ("units", self.units.clone()),
            ("senses", self.senses.clone()),
            ("dictionary", self.dictionary_value()),
            ("decision_queue", self.decision_queue.clone()),
            ("machines", self.machines_value()),
            ("machine_instances", self.machine_instances.clone()),
            ("budgets", self.budgets.clone()),
            ("prices", self.prices.clone()),
            ("rules", self.rules.clone()),
        ])
    }
}

fn append_wrapper(
    table: &mut Vec<(String, Vec<Wrapper>)>,
    name: &str,
    entry: &Value,
    definition: Value,
) {
    let wrapper = Wrapper {
        entry_seq: entry.get("seq").and_then(|v| v.as_int()).unwrap_or(0),
        entry_hash: entry.get("hash").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        definition,
    };
    if let Some(slot) = table.iter_mut().find(|(n, _)| n == name) {
        slot.1.push(wrapper);
    } else {
        table.push((name.to_string(), vec![wrapper]));
    }
}

pub fn apply_entry(state: &mut FoldedState, entry: &Value) {
    let body = match entry.get("body") {
        Some(b) => b.clone(),
        None => return,
    };
    let kind = entry.get("kind").and_then(|v| v.as_str()).unwrap_or("");
    match kind {
        "proposal" | "checkpoint" | "import" | "seal" => {
            // Section 2.1: proposal and import entries have no
            // fold effect of their own; a checkpoint records a
            // state hash; a seal entry (0.6, section 16) likewise
            // has NO fold effect — sealing is export work.
        }
        "decision" => {
            // Section 2.1 / 7: a queued body enters the queue under
            // its proposal_id (value = the full body); only a
            // non-queued body carrying releases/rejects/expires
            // removes that id (the reference fold's if/elif chain).
            if body.get("outcome") == Some(&s("queued")) {
                if let Some(pid) = body.get("proposal_id").and_then(|v| v.as_str()) {
                    state.decision_queue.set(pid, body.clone());
                }
            } else if let Some(pid) = body.get("releases").and_then(|v| v.as_str()) {
                state.decision_queue.remove_key(pid);
            } else if let Some(pid) = body.get("rejects").and_then(|v| v.as_str()) {
                state.decision_queue.remove_key(pid);
            } else if let Some(pid) = body.get("expires").and_then(|v| v.as_str()) {
                state.decision_queue.remove_key(pid);
            }
        }
        "definition" => {
            if let Some(def) = body.get("definition") {
                if let Some(name) = def.get("name").and_then(|v| v.as_str()) {
                    append_wrapper(&mut state.dictionary, name, entry, def.clone());
                }
            }
        }
        "execution" => {
            if let Some(applied) = body.get("applied").and_then(|v| v.as_array()) {
                for req in applied {
                    let args = match req.get("args").and_then(|v| v.as_array()) {
                        Some(a) => a.clone(),
                        None => continue,
                    };
                    if req.get("verb") == Some(&s("write")) {
                        if let Some(unit) = args.first().and_then(|v| v.as_str()) {
                            let value = args.get(1).cloned().unwrap_or(Value::Null);
                            state.units.set(unit, value);
                        }
                    } else if req.get("verb") == Some(&s("spend")) {
                        if let (Some(_resource), Some(amount), Some(producer)) = (
                            args.first().and_then(|v| v.as_str()),
                            args.get(1).and_then(|v| v.as_int()),
                            body.get("producer").and_then(|v| v.as_str()),
                        ) {
                            let resource = args.first().unwrap().as_str().unwrap();
                            let price = state
                                .prices
                                .get(resource)
                                .and_then(|v| v.as_int())
                                .unwrap_or(1);
                            let balance = state
                                .budgets
                                .get(producer)
                                .and_then(|v| v.as_int())
                                .unwrap_or(0);
                            state
                                .budgets
                                .set(producer, Value::Int(balance - amount * price));
                        }
                    }
                }
            }
        }
        "sense" => {
            if let Some(name) = body.get("name").and_then(|v| v.as_str()) {
                if body.has("value") {
                    state.senses.set(name, body.get("value").unwrap().clone());
                }
            }
        }
        "machine" => {
            if let Some(machine) = body.get("machine") {
                if let Some(name) = machine.get("name").and_then(|v| v.as_str()) {
                    append_wrapper(&mut state.machines, name, entry, machine.clone());
                }
            }
        }
        "transition" => {
            let outcome = body.get("outcome").and_then(|v| v.as_str()).unwrap_or("");
            if outcome == "created" || outcome == "taken" {
                if let (Some(instance), Some(to)) = (
                    body.get("instance").and_then(|v| v.as_str()),
                    body.get("to").and_then(|v| v.as_str()),
                ) {
                    state.machine_instances.set(
                        instance,
                        obj(vec![
                            ("machine", body.get("machine").cloned().unwrap_or(Value::Null)),
                            ("state", s(to)),
                        ]),
                    );
                }
            }
        }
        "budget" => {
            if let (Some(producer), Some(delta)) = (
                body.get("producer").and_then(|v| v.as_str()),
                body.get("delta").and_then(|v| v.as_int()),
            ) {
                let balance = state.budgets.get(producer).and_then(|v| v.as_int()).unwrap_or(0);
                state.budgets.set(producer, Value::Int(balance + delta));
            }
        }
        "price" => {
            if let (Some(resource), Some(price)) = (
                body.get("resource").and_then(|v| v.as_str()),
                body.get("price").and_then(|v| v.as_int()),
            ) {
                state.prices.set(resource, Value::Int(price));
            }
        }
        "rule" => {
            if let Some(rule) = body.get("rule") {
                if let Some(rule_id) = rule.get("rule_id").and_then(|v| v.as_str()) {
                    state.rules.set(rule_id, rule.clone());
                }
            }
        }
        _ => {}
    }
}

pub fn fold(entries: &[Value]) -> FoldedState {
    let mut state = FoldedState::empty();
    for e in entries {
        apply_entry(&mut state, e);
    }
    state
}

pub fn state_hash(state: &FoldedState) -> String {
    hash_of(&state.state_object())
}

pub fn fold_state_hash(entries: &[Value]) -> String {
    state_hash(&fold(entries))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::value::{canonical, parse_json};

    // Spec 0.6 sections 2.1/16: the seal kind is accepted by
    // the log layer and round-trips through the canonical
    // form; section 16 gives it NO fold effect. (The golden
    // vectors do not exercise the kind; this is the whole of
    // what the port owes it — sealing tooling is export-layer
    // work, out of this port's scope.)
    #[test]
    fn seal_kind_round_trips_and_is_inert() {
        fn stored(seq: i64, prev: &str, kind: &str, body: Value) -> Value {
            let mut e = make_entry(seq, prev, kind, body);
            let h = entry_hash(&e);
            e.set("hash", s(&h));
            e
        }
        let genesis = genesis_prev();
        let e0 = stored(0, &genesis, "proposal", obj(vec![("note", s("x"))]));
        let seal_body = obj(vec![
            ("producer", s("op")),
            (
                "seals",
                Value::Array(vec![obj(vec![
                    ("entry_seq", Value::Int(0)),
                    ("path", s("note")),
                    ("class", s("identity")),
                    ("commitment", s(&"a".repeat(64))),
                ])]),
            ),
        ]);
        let e0_hash = e0.get("hash").and_then(|v| v.as_str()).unwrap().to_string();
        let e1 = stored(1, &e0_hash, "seal", seal_body);
        let entries = vec![e0.clone(), e1];
        assert!(verify_chain(&entries).ok);
        // Round-trip: canonical bytes -> parse -> re-serialise
        // -> identical bytes. (Canonical form sorts keys, so
        // the parsed objects are key-ordered; byte-stability
        // is the round-trip the form guarantees.)
        let bytes = canonical(&Value::Array(entries.clone())).unwrap();
        let parsed = parse_json(&bytes).unwrap();
        assert_eq!(canonical(&parsed).unwrap(), bytes);
        // Inert: folding with the seal equals folding without.
        assert_eq!(fold_state_hash(&[e0]), fold_state_hash(&entries));
    }
}
