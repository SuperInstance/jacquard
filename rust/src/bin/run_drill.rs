//! Cross-language drill, Rust side (slice 20).
//!
//! Drives fixture.json through the Rust Sequencer port and
//! writes the resulting log (canonical lines, exactly the Log
//! file form) plus the canonical JSON of every op's verdict.
//! Usage: jacquard-cross-drill <fixture> <log-out> <verdicts-out>

use jacquard_kernel::core::spec_seal;
use jacquard_kernel::kernel::{envelope_hash, Sequencer};
use jacquard_kernel::value::{arr, canonical, obj, parse_json, s, sort_strings, Value};
use std::process::ExitCode;

fn make_envelope(
    producer: &str,
    kind: &str,
    body: Value,
    declared_effects: &[String],
    id: &str,
) -> Value {
    let mut declared: Vec<String> = Vec::new();
    for e in declared_effects {
        if !declared.contains(e) {
            declared.push(e.clone());
        }
    }
    declared = sort_strings(&declared);
    obj(vec![
        ("v", Value::Int(1)),
        ("id", s(id)),
        ("producer", s(producer)),
        ("kind", s(kind)),
        ("body", body),
        (
            "declared_effects",
            arr(declared.into_iter().map(|e| s(&e)).collect()),
        ),
        ("spec_seal", s(&spec_seal())),
    ])
}

fn strings_of(v: Option<&Value>) -> Vec<String> {
    v.and_then(|x| x.as_array())
        .map(|items| {
            items
                .iter()
                .filter_map(|e| e.as_str().map(|t| t.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let (fixture_path, log_out, verdicts_out) = (&args[1], &args[2], &args[3]);
    let fixture = parse_json(&std::fs::read_to_string(fixture_path).expect("read fixture"))
        .expect("parse fixture");
    let ops = fixture.get("ops").and_then(|v| v.as_array()).expect("ops").clone();
    let mut seq = Sequencer::new();
    let mut hashes: Vec<(String, String)> = Vec::new();
    let mut verdicts: Vec<Value> = Vec::new();
    let hash_of_idem = |hashes: &Vec<(String, String)>, idem: &str| -> String {
        hashes
            .iter()
            .find(|(k, _)| k == idem)
            .map(|(_, v)| v.clone())
            .unwrap_or_default()
    };
    for op in &ops {
        let kind = op.get("op").and_then(|v| v.as_str()).unwrap_or("");
        match kind {
            "define" => {
                let env = make_envelope(
                    op.get("producer").and_then(|v| v.as_str()).unwrap_or(""),
                    "definition",
                    op.get("definition").cloned().unwrap_or(Value::Null),
                    &[],
                    op.get("idem").and_then(|v| v.as_str()).unwrap_or(""),
                );
                hashes.push((
                    op.get("idem").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    envelope_hash(&env),
                ));
                verdicts.push(seq.submit(&env));
            }
            "proposal" => {
                let env = make_envelope(
                    op.get("producer").and_then(|v| v.as_str()).unwrap_or(""),
                    "proposal",
                    op.get("body").cloned().unwrap_or(Value::Null),
                    &strings_of(op.get("declared")),
                    op.get("idem").and_then(|v| v.as_str()).unwrap_or(""),
                );
                hashes.push((
                    op.get("idem").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    envelope_hash(&env),
                ));
                verdicts.push(seq.submit(&env));
            }
            "release" | "reject" | "expire" => {
                let target = hash_of_idem(&hashes, op.get("of").and_then(|v| v.as_str()).unwrap_or(""));
                let by = op.get("by").and_then(|v| v.as_str()).unwrap_or("");
                let reason = op.get("reason").and_then(|v| v.as_str());
                verdicts.push(match kind {
                    "release" => seq.release_queued(&target, by, reason),
                    "reject" => seq.reject_queued(&target, by, reason),
                    _ => seq.expire_queued(&target, by, reason),
                });
            }
            "grant" => {
                verdicts.push(seq.grant_budget(
                    op.get("producer").and_then(|v| v.as_str()).unwrap_or(""),
                    op.get("amount").and_then(|v| v.as_int()).unwrap_or(0),
                ));
            }
            "price" => {
                verdicts.push(seq.post_price(
                    op.get("resource").and_then(|v| v.as_str()).unwrap_or(""),
                    op.get("price").and_then(|v| v.as_int()).unwrap_or(0),
                ));
            }
            "sense" => {
                let entry = seq.submit_sense(
                    op.get("name").and_then(|v| v.as_str()).unwrap_or(""),
                    op.get("value").cloned().unwrap_or(Value::Null),
                    op.get("producer").and_then(|v| v.as_str()).unwrap_or(""),
                );
                verdicts.push(obj(vec![(
                    "entry",
                    entry.get("hash").cloned().unwrap_or(Value::Null),
                )]));
            }
            "checkpoint" => {
                let entry = seq.checkpoint(op.get("name").and_then(|v| v.as_str()).unwrap_or(""));
                verdicts.push(obj(vec![(
                    "entry",
                    entry.get("hash").cloned().unwrap_or(Value::Null),
                )]));
            }
            "standing" => {
                seq.set_standing(
                    op.get("producer").and_then(|v| v.as_str()).unwrap_or(""),
                    op.get("standing").cloned().unwrap_or(Value::Null),
                );
                verdicts.push(obj(vec![("standing", s("set"))]));
            }
            "append_rule" => {
                let entry = seq
                    .log
                    .append(
                        "rule",
                        obj(vec![
                            ("producer", s("learner")),
                            ("rule", op.get("rule").cloned().unwrap_or(Value::Null)),
                        ]),
                    )
                    .expect("rule kind");
                seq.refold();
                verdicts.push(obj(vec![(
                    "appended",
                    entry.get("hash").cloned().unwrap_or(Value::Null),
                )]));
            }
            other => panic!("unknown op: {}", other),
        }
    }
    std::fs::write(log_out, seq.log.serialise()).expect("write log");
    let verdicts_text = canonical(&arr(verdicts.clone())).expect("canonical verdicts") + "\n";
    std::fs::write(verdicts_out, verdicts_text).expect("write verdicts");
    println!(
        "rust: {} entries, {} verdicts",
        seq.log.entries.len(),
        verdicts.len()
    );
    ExitCode::SUCCESS
}
