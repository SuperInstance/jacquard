//! Chain-head anchoring verification (spec section 15.5) — a
//! port of the anchor section of `conformance/ts/kernel.ts`,
//! which ports `src/jacquard/anchor.py`. Ed25519 via the
//! ed25519-dalek crate.

use crate::core::genesis_prev;
use crate::kernel::verify_internal_chain;
use crate::value::{canonical_bytes, hash_of, hex_decode, obj, py_repr, s, sort_strings, Value};
use ed25519_dalek::{Signature, SigningKey, VerifyingKey};

pub const ANCHOR_FORMAT: &str = "jacquard/anchor/1";
const BODY_KEYS: [&str; 8] = [
    "format", "log_id", "label", "checkpoint_seq", "log_length", "head_hash", "spec",
    "prev_checkpoint",
];

fn is_hex(text: &str, len: usize) -> bool {
    text.len() == len
        && text
            .chars()
            .all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))
}

pub fn ed25519_verify(pubkey_hex: &str, message: &[u8], sig_hex: &str) -> bool {
    let (Some(pub_bytes), Some(sig_bytes)) = (hex_decode(pubkey_hex), hex_decode(sig_hex)) else {
        return false;
    };
    let (Ok(pub_arr), Ok(sig_arr)) = (
        <[u8; 32]>::try_from(pub_bytes.as_slice()),
        <[u8; 64]>::try_from(sig_bytes.as_slice()),
    ) else {
        return false;
    };
    let Ok(key) = VerifyingKey::from_bytes(&pub_arr) else {
        return false;
    };
    let sig = Signature::from_bytes(&sig_arr);
    key.verify_strict(message, &sig).is_ok()
}

pub fn ed25519_pub_from_seed(seed_hex: &str) -> String {
    let bytes = hex_decode(seed_hex).expect("test seed hex");
    let arr = <[u8; 32]>::try_from(bytes.as_slice()).expect("seed is 32 bytes");
    let signing = SigningKey::from_bytes(&arr);
    crate::value::hex_encode(signing.verifying_key().as_bytes())
}

pub fn checkpoint_hash(body: &Value) -> String {
    hash_of(body)
}

pub fn log_id_of(entries: &[Value]) -> String {
    if entries.is_empty() {
        genesis_prev()
    } else {
        entries[0]
            .get("hash")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string()
    }
}

pub fn head_at(entries: &[Value], length: usize) -> String {
    if length == 0 {
        genesis_prev()
    } else {
        entries[length - 1]
            .get("hash")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string()
    }
}

pub fn validate_anchor_body(body: &Value) -> Option<String> {
    if !body.is_object() {
        return Some("body is not an object".to_string());
    }
    let keys = body.keys();
    if keys.len() != BODY_KEYS.len() || !BODY_KEYS.iter().all(|k| keys.contains(&k.to_string())) {
        return Some(format!(
            "body keys are {}, expected exactly {}",
            py_repr(&Value::Array(
                sort_strings(&keys).into_iter().map(|k| s(&k)).collect()
            )),
            py_repr(&Value::Array(
                BODY_KEYS.iter().map(|k| s(k)).collect()
            ))
        ));
    }
    if body.get("format") != Some(&s(ANCHOR_FORMAT)) {
        return Some(format!(
            "format is {}",
            py_repr(body.get("format").unwrap_or(&Value::Null))
        ));
    }
    match body.get("log_id") {
        Some(Value::Str(v)) if is_hex(v, 64) => {}
        _ => return Some("log_id is not hex64".to_string()),
    }
    if !matches!(body.get("label"), Some(Value::Str(_))) {
        return Some("label is not a string".to_string());
    }
    match body.get("checkpoint_seq") {
        Some(Value::Int(v)) if *v >= 0 => {}
        _ => return Some("checkpoint_seq is not an integer >= 0".to_string()),
    }
    match body.get("log_length") {
        Some(Value::Int(v)) if *v >= 0 => {}
        _ => return Some("log_length is not an integer >= 0".to_string()),
    }
    match body.get("head_hash") {
        Some(Value::Str(v)) if is_hex(v, 64) => {}
        _ => return Some("head_hash is not hex64".to_string()),
    }
    // Spec 15.1 (0.6): the anchor format did not change in
    // 0.6, so checkpoints issued under 0.5 remain valid;
    // refuse any other.
    let body_spec = body.get("spec").and_then(|v| v.as_str()).unwrap_or("");
    if body_spec != "jacquard/0.5" && body_spec != "jacquard/0.6" {
        return Some(format!(
            "spec is {}, expected \"jacquard/0.5\" or \"jacquard/0.6\"",
            py_repr(body.get("spec").unwrap_or(&Value::Null))
        ));
    }
    let seq = body.get("checkpoint_seq").unwrap().as_int().unwrap();
    let prev = body.get("prev_checkpoint").unwrap_or(&Value::Null);
    if seq == 0 && *prev != Value::Null {
        return Some("checkpoint_seq 0 must carry prev_checkpoint null".to_string());
    }
    if seq > 0 {
        match prev {
            Value::Str(v) if is_hex(v, 64) => {}
            _ => return Some("prev_checkpoint is not hex64".to_string()),
        }
    }
    None
}

#[derive(Clone, Debug)]
pub struct AnchorResult {
    pub outcome: Option<String>,
    pub log_id: String,
    pub log_length: usize,
    pub anchored_length: usize,
    pub unanchored_tail: usize,
    pub checkpoints_checked: usize,
    pub internal_chain_ok: bool,
    pub failure: Option<Value>,
}

impl AnchorResult {
    pub fn to_value(&self) -> Value {
        obj(vec![
            (
                "outcome",
                self.outcome.clone().map(|o| s(&o)).unwrap_or(Value::Null),
            ),
            ("log_id", s(&self.log_id)),
            ("log_length", Value::Int(self.log_length as i64)),
            ("anchored_length", Value::Int(self.anchored_length as i64)),
            ("unanchored_tail", Value::Int(self.unanchored_tail as i64)),
            (
                "checkpoints_checked",
                Value::Int(self.checkpoints_checked as i64),
            ),
            ("internal_chain_ok", Value::Bool(self.internal_chain_ok)),
            ("failure", self.failure.clone().unwrap_or(Value::Null)),
        ])
    }
}

fn scheduled_key(schedule: &[(i64, String)], checkpoint_seq: i64) -> Option<String> {
    let mut chosen = None;
    for (from_seq, pubkey) in schedule {
        if checkpoint_seq >= *from_seq {
            chosen = Some(pubkey.clone());
        }
    }
    chosen
}

/// Returns (ok, detail, offending checkpoint_seq).
pub fn authenticate_history(
    history: &[Value],
    schedule: &[(i64, String)],
) -> (bool, Option<String>, Option<Value>) {
    let mut prev_hash: Option<String> = None;
    for (expected_seq, envelope) in history.iter().enumerate() {
        let expected = expected_seq as i64;
        let body = envelope.get("body").cloned().unwrap_or(Value::Null);
        if let Some(detail) = validate_anchor_body(&body) {
            return (
                false,
                Some(format!("checkpoint {}: {}", expected, detail)),
                body.get("checkpoint_seq").cloned().unwrap_or(Value::Null).into(),
            );
        }
        if body.get("checkpoint_seq") != Some(&Value::Int(expected)) {
            return (
                false,
                Some(format!(
                    "checkpoint sequence gap: expected seq {}, found {}",
                    expected,
                    body.get("checkpoint_seq").unwrap().as_int().unwrap()
                )),
                body.get("checkpoint_seq").cloned().unwrap_or(Value::Null).into(),
            );
        }
        let expected_prev = prev_hash.clone().map(|h| s(&h)).unwrap_or(Value::Null);
        if body.get("prev_checkpoint") != Some(&expected_prev) {
            return (
                false,
                Some(format!(
                    "checkpoint {}: prev_checkpoint does not recompute",
                    expected
                )),
                Some(Value::Int(expected)),
            );
        }
        let pinned = scheduled_key(schedule, expected);
        let envelope_pub = envelope.get("pubkey").and_then(|v| v.as_str());
        if pinned.is_none() || envelope_pub != pinned.as_deref() {
            return (
                false,
                Some(format!(
                    "checkpoint {}: envelope pubkey is not the pinned key for its sequence",
                    expected
                )),
                Some(Value::Int(expected)),
            );
        }
        let pinned = pinned.unwrap();
        let sig_ok = match envelope.get("sig") {
            Some(Value::Str(sig)) if is_hex(sig, 128) => ed25519_verify(
                &pinned,
                &canonical_bytes(&body).unwrap_or_default(),
                sig,
            ),
            _ => false,
        };
        if !sig_ok {
            return (
                false,
                Some(format!(
                    "checkpoint {}: signature does not verify",
                    expected
                )),
                Some(Value::Int(expected)),
            );
        }
        prev_hash = Some(checkpoint_hash(&body));
    }
    (true, None, None)
}

pub fn history_for(envelopes: &[Value], log_id: &str) -> Vec<Value> {
    let mut out: Vec<Value> = envelopes
        .iter()
        .filter(|e| {
            matches!(e.get("body"), Some(b) if b.is_object() && b.get("log_id") == Some(&s(log_id)))
        })
        .cloned()
        .collect();
    out.sort_by_key(|e| {
        e.get("body")
            .and_then(|b| b.get("checkpoint_seq"))
            .and_then(|v| v.as_int())
            .unwrap_or(0)
    });
    out
}

pub fn verify_anchor(
    entries: &[Value],
    envelopes: &[Value],
    pubkey_hex: &str,
    schedule: Option<&[(i64, String)]>,
) -> AnchorResult {
    let sched_owned;
    let sched: &[(i64, String)] = match schedule {
        Some(sch) => sch,
        None => {
            sched_owned = vec![(0, pubkey_hex.to_string())];
            &sched_owned
        }
    };
    let log_id = log_id_of(entries);
    let mut result = AnchorResult {
        outcome: None,
        log_id: log_id.clone(),
        log_length: entries.len(),
        anchored_length: 0,
        unanchored_tail: entries.len(),
        checkpoints_checked: 0,
        internal_chain_ok: verify_internal_chain(entries),
        failure: None,
    };
    let history = history_for(envelopes, &log_id);
    if history.is_empty() {
        result.outcome = Some("unanchored".to_string());
        return result;
    }
    let (ok, detail, offender) = authenticate_history(&history, sched);
    if !ok {
        result.outcome = Some("failed".to_string());
        result.failure = Some(obj(vec![
            ("stage", s("history")),
            ("checkpoint_seq", offender.unwrap_or(Value::Null)),
            ("detail", s(&detail.unwrap_or_default())),
        ]));
        return result;
    }
    if !result.internal_chain_ok {
        result.outcome = Some("failed".to_string());
        result.failure = Some(obj(vec![
            ("stage", s("internal")),
            ("checkpoint_seq", Value::Null),
            (
                "detail",
                s("presented log fails its own hash-chain verification"),
            ),
        ]));
        return result;
    }
    for envelope in &history {
        let body = envelope.get("body").unwrap();
        result.checkpoints_checked += 1;
        let log_length = body.get("log_length").unwrap().as_int().unwrap() as usize;
        if log_length > entries.len() {
            result.unanchored_tail = entries.len() - result.anchored_length;
            result.outcome = Some("failed".to_string());
            result.failure = Some(obj(vec![
                ("stage", s("prefix")),
                (
                    "checkpoint_seq",
                    body.get("checkpoint_seq").cloned().unwrap_or(Value::Null),
                ),
                (
                    "detail",
                    s(&format!(
                        "checkpoint anchors length {}, presented log has {} entries (truncated or missing anchored history)",
                        log_length,
                        entries.len()
                    )),
                ),
                (
                    "expected_head",
                    body.get("head_hash").cloned().unwrap_or(Value::Null),
                ),
                ("actual_head", Value::Null),
            ]));
            return result;
        }
        let actual = head_at(entries, log_length);
        if actual != body.get("head_hash").unwrap().as_str().unwrap() {
            result.unanchored_tail = entries.len() - result.anchored_length;
            result.outcome = Some("failed".to_string());
            let cp_seq = body.get("checkpoint_seq").unwrap().as_int().unwrap();
            let expected_head = body.get("head_hash").unwrap().as_str().unwrap();
            result.failure = Some(obj(vec![
                ("stage", s("prefix")),
                ("checkpoint_seq", Value::Int(cp_seq)),
                (
                    "detail",
                    s(&format!(
                        "first divergent checkpoint: checkpoint {} anchors length {} at head {}, presented log's head at that length is {}",
                        cp_seq, log_length, expected_head, actual
                    )),
                ),
                ("expected_head", s(expected_head)),
                ("actual_head", s(&actual)),
            ]));
            return result;
        }
        result.anchored_length = log_length;
    }
    result.unanchored_tail = entries.len() - result.anchored_length;
    result.outcome = Some(
        if result.unanchored_tail == 0 {
            "verified"
        } else {
            "verified_to_anchor"
        }
        .to_string(),
    );
    result
}
