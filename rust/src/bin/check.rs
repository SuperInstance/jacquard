//! Jacquard conformance runner — Rust, Phase 8 slice 20.
//!
//! Mirrors `conformance/ts/check.ts` check for check: one
//! PASS/FAIL line per check, exit non-zero on any FAIL, and no
//! SKIP lines — the Rust port executes every golden-vector
//! section (canonical form + hash chain, fold, envelope,
//! dictionary + evaluator, sequencer end to end, sense
//! computation, the section 15 anchor verifier, the section
//! 12.1 shape signature over both proof-run corpora, and the
//! token-form battery).
//!
//! Run from the repository root:
//!   cargo run --release --manifest-path rust/Cargo.toml --bin jacquard-check
//! (or from rust/: the repo root is located by walking up to
//! the directory that carries spec/vectors/vectors.json.)

use jacquard_kernel::anchor::{
    checkpoint_hash, ed25519_pub_from_seed, ed25519_verify, verify_anchor,
};
use jacquard_kernel::core::{
    entry_hash, envelope_id, fold, fold_state_hash, make_entry, spec_seal,
    state_hash, validate_envelope, verify_chain, FoldedState,
};
use jacquard_kernel::kernel::{Refusal, Sequencer};
use jacquard_kernel::senses::compute_sense;
use jacquard_kernel::signature::shape_signature;
use jacquard_kernel::value::{arr, canonical, hash_of, obj, parse_json, s, sort_strings, Value};
use std::io::Read;
use std::path::PathBuf;

struct Reporter {
    failures: usize,
}

impl Reporter {
    fn report(&mut self, ok: bool, label: &str, detail: String) {
        println!("{} {}: {}", if ok { "PASS" } else { "FAIL" }, label, detail);
        if !ok {
            self.failures += 1;
        }
    }
}

fn deep_eq(a: &Value, b: &Value) -> bool {
    canonical(a).unwrap_or_default() == canonical(b).unwrap_or_default()
}

fn make_envelope(producer: &str, kind: &str, body: Value, declared: &[String], id: &str) -> Value {
    let mut dedup: Vec<String> = Vec::new();
    for e in declared {
        if !dedup.contains(e) {
            dedup.push(e.clone());
        }
    }
    dedup = sort_strings(&dedup);
    obj(vec![
        ("v", Value::Int(1)),
        ("id", s(id)),
        ("producer", s(producer)),
        ("kind", s(kind)),
        ("body", body),
        ("declared_effects", arr(dedup.into_iter().map(|e| s(&e)).collect())),
        ("spec_seal", s(&spec_seal())),
    ])
}

fn repo_root() -> PathBuf {
    let mut dir = std::env::current_dir().expect("cwd");
    loop {
        if dir.join("spec/vectors/vectors.json").exists() {
            return dir;
        }
        if !dir.pop() {
            panic!("cannot locate spec/vectors/vectors.json above the current directory");
        }
    }
}

fn load_gz_json(path: &PathBuf) -> Result<Value, String> {
    let bytes = std::fs::read(path).map_err(|e| e.to_string())?;
    let mut decoder = flate2::read::GzDecoder::new(&bytes[..]);
    let mut text = String::new();
    decoder.read_to_string(&mut text).map_err(|e| e.to_string())?;
    parse_json(&text)
}

fn main() {
    let root = repo_root();
    let vectors_path = root.join("spec/vectors/vectors.json");
    let vectors = parse_json(&std::fs::read_to_string(&vectors_path).expect("read vectors"))
        .expect("parse vectors");
    let mut rep = Reporter { failures: 0 };

    // --- a. spec_seal ---
    {
        let computed = spec_seal();
        let recorded = vectors.get("spec_seal").and_then(|v| v.as_str()).unwrap_or("");
        let ok = computed == recorded;
        rep.report(
            ok,
            "a. spec_seal",
            if ok {
                format!("computed seal {} equals vectors.spec_seal", computed)
            } else {
                format!("computed {}, vectors record {}", computed, recorded)
            },
        );
    }

    // --- b. vector entries rebuild + chain ---
    let vec_entries = vectors
        .get("entries")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut rebuilt: Vec<Value> = Vec::new();
    {
        let mut prev = "0".repeat(64);
        let mut all_ok = true;
        let mut problems: Vec<String> = Vec::new();
        for (i, ve) in vec_entries.iter().enumerate() {
            let entry = make_entry(
                ve.get("seq").and_then(|v| v.as_int()).unwrap_or(0),
                &prev,
                ve.get("kind").and_then(|v| v.as_str()).unwrap_or(""),
                ve.get("body").cloned().unwrap_or(Value::Null),
            );
            let h = entry_hash(&entry);
            let recorded = ve.get("hash").and_then(|v| v.as_str()).unwrap_or("");
            if h != recorded {
                all_ok = false;
                problems.push(format!(
                    "entry {} ({}): computed {}, recorded {}",
                    i,
                    ve.get("kind").and_then(|v| v.as_str()).unwrap_or(""),
                    h,
                    recorded
                ));
            }
            let mut stored = entry.clone();
            stored.set("hash", s(recorded));
            rebuilt.push(stored);
            prev = recorded.to_string();
        }
        let chain = verify_chain(&rebuilt);
        if !chain.ok {
            all_ok = false;
            problems.push(format!("chain: {}", chain.failure.unwrap_or_default()));
        }
        rep.report(
            all_ok,
            "b. vector entries",
            if all_ok {
                format!(
                    "all {} entries rebuilt from (kind, body) reproduce their recorded hashes; chain verifies",
                    vec_entries.len()
                )
            } else {
                problems.join("; ")
            },
        );
    }

    // --- c. fold of first two vector entries vs checkpoint ---
    {
        let checkpoint = &vec_entries[2];
        let recorded = if checkpoint.get("kind") == Some(&s("checkpoint")) {
            checkpoint
                .get("body")
                .and_then(|b| b.get("state_hash"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        } else {
            "(third entry is not a checkpoint)".to_string()
        };
        let computed = fold_state_hash(&rebuilt[..2]);
        let ok = computed == recorded;
        rep.report(
            ok,
            "c. vector fold",
            if ok {
                format!(
                    "folding the first two entries gives state_hash {}, as recorded in the checkpoint body",
                    computed
                )
            } else {
                format!("folded state_hash {}, checkpoint records {}", computed, recorded)
            },
        );
    }

    // --- d. envelope id ---
    {
        let envelope_section = vectors.get("envelope").cloned().unwrap_or(Value::Null);
        let envelope = envelope_section.get("envelope").cloned().unwrap_or(Value::Null);
        let problems = validate_envelope(&envelope);
        let computed = envelope_id(&envelope);
        let recorded = envelope_section.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let mut detail = if computed == recorded {
            format!("envelope recomputes to its recorded id {}", computed)
        } else {
            format!("computed id {}, recorded {}", computed, recorded)
        };
        if !problems.is_empty() {
            detail.push_str(&format!("; validation problems: {}", problems.join("; ")));
        }
        rep.report(computed == recorded && problems.is_empty(), "d. envelope id", detail);
    }

    // --- e/f. replay log ---
    let replay_path = root.join("conformance/replay-log.json.gz");
    match load_gz_json(&replay_path) {
        Err(err) => {
            rep.report(false, "e. replay hashes+chain", format!("cannot load {}: {}", replay_path.display(), err));
            rep.report(false, "f. replay fold", format!("cannot load {}: {}", replay_path.display(), err));
        }
        Ok(replay) => {
            let entries = replay
                .get("entries")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            let mut recomputed = 0usize;
            let mut first_bad: Option<String> = None;
            for e in &entries {
                if entry_hash(e) == e.get("hash").and_then(|v| v.as_str()).unwrap_or("") {
                    recomputed += 1;
                } else if first_bad.is_none() {
                    first_bad = Some(format!(
                        "entry seq {} ({})",
                        e.get("seq").and_then(|v| v.as_int()).unwrap_or(-1),
                        e.get("kind").and_then(|v| v.as_str()).unwrap_or("")
                    ));
                }
            }
            let chain = verify_chain(&entries);
            let ok = recomputed == entries.len() && chain.ok;
            rep.report(
                ok,
                "e. replay hashes+chain",
                if ok {
                    format!(
                        "{} entries checked: every recorded hash recomputes and the chain verifies end to end",
                        recomputed
                    )
                } else {
                    format!(
                        "recomputed {}/{}{}{}",
                        recomputed,
                        entries.len(),
                        first_bad.map(|b| format!("; first mismatch at {}", b)).unwrap_or_default(),
                        if chain.ok {
                            "".to_string()
                        } else {
                            format!("; chain failure: {}", chain.failure.unwrap_or_default())
                        }
                    )
                },
            );
            let folded_hash = state_hash(&fold(&entries));
            let expected = replay
                .get("expected_state_hash")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let ok = folded_hash == expected;
            rep.report(
                ok,
                "f. replay fold",
                if ok {
                    format!(
                        "folding all {} replay entries yields state_hash {} == expected_state_hash",
                        entries.len(),
                        folded_hash
                    )
                } else {
                    format!("folded state_hash {}, expected {}", folded_hash, expected)
                },
            );
        }
    }

    // --- g. full log ---
    {
        let full_path = root.join("conformance/full-log.json.gz");
        match load_gz_json(&full_path) {
            Err(err) => rep.report(
                false,
                "g. full-log hashes+chain+fold",
                format!("cannot load {}: {}", full_path.display(), err),
            ),
            Ok(full) => {
                let entries = full
                    .get("entries")
                    .and_then(|v| v.as_array())
                    .cloned()
                    .unwrap_or_default();
                let mut recomputed = 0usize;
                for e in &entries {
                    if entry_hash(e) == e.get("hash").and_then(|v| v.as_str()).unwrap_or("") {
                        recomputed += 1;
                    }
                }
                let chain = verify_chain(&entries);
                let folded_hash = state_hash(&fold(&entries));
                let expected = full
                    .get("expected_state_hash")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let ok = recomputed == entries.len() && chain.ok && folded_hash == expected;
                rep.report(
                    ok,
                    "g. full-log hashes+chain+fold",
                    if ok {
                        format!(
                            "{} entries across all emitted kinds: hashes recompute, chain verifies, fold yields state_hash {}",
                            recomputed, folded_hash
                        )
                    } else {
                        format!(
                            "recomputed {}/{}; chain {}; folded {}, expected {}",
                            recomputed,
                            entries.len(),
                            chain.ok,
                            folded_hash,
                            expected
                        )
                    },
                );
            }
        }
    }

    let definitions = vectors
        .get("definitions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    // --- vectors.definitions ---
    {
        let mut seq = Sequencer::new();
        let mut problems: Vec<String> = Vec::new();
        for item in &definitions {
            let defn = item.get("definition").cloned().unwrap_or(Value::Null);
            let name = defn.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let declared: Vec<String> = defn
                .get("declared_effects")
                .and_then(|v| v.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|e| e.as_str().map(|t| t.to_string()))
                        .collect()
                })
                .unwrap_or_default();
            let verdict = seq.submit(&make_envelope(
                "operator",
                "definition",
                defn.clone(),
                &declared,
                &format!("vec-{}", name),
            ));
            if verdict.get("status") != Some(&s("accepted")) {
                problems.push(format!(
                    "{}: verdict {}",
                    name,
                    canonical(&verdict).unwrap_or_default()
                ));
                continue;
            }
            let stored = seq
                .state
                .dict_get(&name)
                .and_then(|versions| versions.last())
                .map(|w| w.definition.clone())
                .unwrap_or(Value::Null);
            let recorded = item.get("stored").cloned().unwrap_or(Value::Null);
            if !deep_eq(&stored, &recorded) {
                problems.push(format!(
                    "{}: stored {} != recorded {}",
                    name,
                    canonical(&stored).unwrap_or_default(),
                    canonical(&recorded).unwrap_or_default()
                ));
            }
        }
        rep.report(
            problems.is_empty(),
            "vectors.definitions",
            if problems.is_empty() {
                format!(
                    "all {} definitions accepted by the Rust dictionary with stored forms (computed effects + refs) identical to the recorded vectors",
                    definitions.len()
                )
            } else {
                problems.join("; ")
            },
        );
    }

    // --- vectors.state ---
    {
        let mut seq = Sequencer::new();
        for item in &definitions {
            let defn = item.get("definition").cloned().unwrap_or(Value::Null);
            let declared: Vec<String> = defn
                .get("declared_effects")
                .and_then(|v| v.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|e| e.as_str().map(|t| t.to_string()))
                        .collect()
                })
                .unwrap_or_default();
            let id = format!(
                "sv-{}",
                defn.get("name").and_then(|v| v.as_str()).unwrap_or("")
            );
            seq.submit(&make_envelope(
                "operator",
                "definition",
                defn,
                &declared,
                &id,
            ));
        }
        let proposal_body = obj(vec![(
            "requests",
            arr(vec![obj(vec![
                ("verb", s("write")),
                ("args", arr(vec![s("answer"), Value::Int(42)])),
                ("outputs", arr(vec![s("o-42")])),
            ])]),
        )]);
        seq.submit(&make_envelope(
            "operator",
            "proposal",
            proposal_body,
            &["write".to_string()],
            "sv-p1",
        ));
        let state_section = vectors.get("state").cloned().unwrap_or(Value::Null);
        let recorded_units = state_section.get("units").cloned().unwrap_or(Value::Null);
        let recorded_hash = state_section
            .get("state_hash")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let mut problems: Vec<String> = Vec::new();
        if !deep_eq(&seq.state.units, &recorded_units) {
            problems.push(format!(
                "units {} != recorded {}",
                canonical(&seq.state.units).unwrap_or_default(),
                canonical(&recorded_units).unwrap_or_default()
            ));
        }
        if state_hash(&seq.state) != recorded_hash {
            problems.push(format!(
                "state_hash {} != recorded {}",
                state_hash(&seq.state),
                recorded_hash
            ));
        }
        if fold_state_hash(&seq.log.entries) != recorded_hash {
            problems.push("refolded state hash differs from recorded state_hash".to_string());
        }
        rep.report(
            problems.is_empty(),
            "vectors.state",
            if problems.is_empty() {
                format!(
                    "sequencer replay of the vector scenario yields units {} and state_hash {}, live and refolded",
                    canonical(&recorded_units).unwrap_or_default(),
                    recorded_hash
                )
            } else {
                problems.join("; ")
            },
        );
    }

    // --- vectors.senses ---
    {
        let mut problems: Vec<String> = Vec::new();
        let mut cases = 0usize;
        if let Some(senses) = vectors.get("senses").and_then(|v| v.as_object()) {
            for (sense, list) in senses {
                if let Some(list) = list.as_array() {
                    for case in list {
                        cases += 1;
                        let entries = case
                            .get("entries")
                            .and_then(|v| v.as_array())
                            .cloned()
                            .unwrap_or_default();
                        let subject = case.get("subject").and_then(|v| v.as_str()).unwrap_or("");
                        let state: FoldedState = fold(&entries);
                        match compute_sense(&format!("{}:{}", sense, subject), &entries, &state) {
                            Ok(reading) => {
                                let expect = case.get("expect").cloned().unwrap_or(Value::Null);
                                if !deep_eq(&reading.to_value(), &expect) {
                                    problems.push(format!(
                                        "{}:{}: computed {} != recorded {}",
                                        sense,
                                        subject,
                                        canonical(&reading.to_value()).unwrap_or_default(),
                                        canonical(&expect).unwrap_or_default()
                                    ));
                                }
                                let last_seq = entries
                                    .last()
                                    .and_then(|e| e.get("seq"))
                                    .and_then(|v| v.as_int())
                                    .unwrap_or(-1);
                                if reading.as_of_seq != last_seq {
                                    problems.push(format!(
                                        "{}:{}: as_of_seq mismatch",
                                        sense, subject
                                    ));
                                }
                            }
                            Err(err) => {
                                problems.push(format!("{}:{}: threw {}", sense, subject, err));
                            }
                        }
                    }
                }
            }
        }
        rep.report(
            problems.is_empty(),
            "vectors.senses",
            if problems.is_empty() {
                format!(
                    "all {} sense cases (contention + authority) recompute byte-identically, method strings included",
                    cases
                )
            } else {
                problems.join("; ")
            },
        );
    }

    // --- vectors.anchor ---
    {
        let section = vectors.get("anchor").cloned().unwrap_or(Value::Null);
        let envelope = section.get("envelope").cloned().unwrap_or(Value::Null);
        let body = envelope.get("body").cloned().unwrap_or(Value::Null);
        let mut problems: Vec<String> = Vec::new();
        let seed = section.get("test_seed").and_then(|v| v.as_str()).unwrap_or("");
        let derived_pub = ed25519_pub_from_seed(seed);
        let envelope_pub = envelope.get("pubkey").and_then(|v| v.as_str()).unwrap_or("");
        if derived_pub != envelope_pub {
            problems.push(format!(
                "pubkey derived from the recorded test seed is {}, envelope carries {}",
                derived_pub, envelope_pub
            ));
        }
        let expected_body = obj(vec![
            ("format", s("jacquard/anchor/1")),
            ("log_id", vec_entries[0].get("hash").cloned().unwrap_or(Value::Null)),
            ("label", s("golden-vectors")),
            ("checkpoint_seq", Value::Int(0)),
            ("log_length", Value::Int(4)),
            ("head_hash", vec_entries[3].get("hash").cloned().unwrap_or(Value::Null)),
            ("spec", s("jacquard/0.6")),
            ("prev_checkpoint", Value::Null),
        ]);
        if !deep_eq(&body, &expected_body) {
            problems.push("checkpoint body differs from the expected body".to_string());
        }
        let recorded_cp_hash = section
            .get("checkpoint_hash")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if checkpoint_hash(&body) != recorded_cp_hash {
            problems.push(format!(
                "checkpoint_hash {} != recorded {}",
                checkpoint_hash(&body),
                recorded_cp_hash
            ));
        }
        let sig = envelope.get("sig").and_then(|v| v.as_str()).unwrap_or("");
        let body_bytes = jacquard_kernel::value::canonical_bytes(&body).unwrap_or_default();
        if !ed25519_verify(envelope_pub, &body_bytes, sig) {
            problems.push("signature does not verify over the body's canonical bytes".to_string());
        }
        let mut tampered = body.clone();
        tampered.set("log_length", Value::Int(3));
        let tampered_bytes = jacquard_kernel::value::canonical_bytes(&tampered).unwrap_or_default();
        if ed25519_verify(envelope_pub, &tampered_bytes, sig) {
            problems.push("signature WRONGLY verifies over a tampered body".to_string());
        }
        let result = verify_anchor(&rebuilt, &[envelope.clone()], envelope_pub, None);
        if result.outcome.as_deref() != Some("verified")
            || result.anchored_length != 4
            || result.unanchored_tail != 0
            || result.checkpoints_checked != 1
            || !result.internal_chain_ok
        {
            problems.push(format!(
                "section 15.5 over the vector chain: {}",
                canonical(&result.to_value()).unwrap_or_default()
            ));
        }
        rep.report(
            problems.is_empty(),
            "vectors.anchor",
            if problems.is_empty() {
                "test-key pubkey derives from the recorded seed, checkpoint hash recomputes, Ed25519 signature verifies (and fails over a tampered body), and the §15.5 procedure reports the vector chain verified, 4/4 anchored, tail 0".to_string()
            } else {
                problems.join("; ")
            },
        );
    }

    // --- h. shape signatures over both proof-run corpora ---
    {
        let mut problems: Vec<String> = Vec::new();
        let mut details: Vec<String> = Vec::new();
        let exp_path = root.join("conformance/ts/signature-expectations.json");
        match std::fs::read_to_string(&exp_path)
            .map_err(|e| e.to_string())
            .and_then(|text| parse_json(&text))
        {
            Err(err) => problems.push(format!("cannot run: {}", err)),
            Ok(expectations) => {
                if let Some(corpora) = expectations.get("corpora").and_then(|v| v.as_array()) {
                    for corpus in corpora {
                        let rel = corpus.get("path").and_then(|v| v.as_str()).unwrap_or("");
                        let log_path = root.join(rel);
                        let text = match std::fs::read_to_string(&log_path) {
                            Ok(t) => t,
                            Err(err) => {
                                problems.push(format!("{}: {}", rel, err));
                                continue;
                            }
                        };
                        let entries: Vec<Value> = text
                            .lines()
                            .filter(|l| !l.trim().is_empty())
                            .map(|l| parse_json(l).expect("parse corpus line"))
                            .collect();
                        let recorded_count = corpus
                            .get("entry_count")
                            .and_then(|v| v.as_int())
                            .unwrap_or(-1);
                        if entries.len() as i64 != recorded_count {
                            problems.push(format!(
                                "{}: {} entries, fixture records {}",
                                rel,
                                entries.len(),
                                recorded_count
                            ));
                            continue;
                        }
                        let mut items: Vec<Value> = Vec::new();
                        for entry in &entries {
                            let body = entry.get("body").cloned().unwrap_or(Value::Null);
                            if entry.get("kind") == Some(&s("decision")) && body.has("requests") {
                                let requests = body
                                    .get("requests")
                                    .and_then(|v| v.as_array())
                                    .cloned()
                                    .unwrap_or_default();
                                items.push(obj(vec![
                                    ("seq", entry.get("seq").cloned().unwrap_or(Value::Null)),
                                    (
                                        "proposal_id",
                                        body.get("proposal_id").cloned().unwrap_or(Value::Null),
                                    ),
                                    ("signature", shape_signature(Some(&requests))),
                                ]));
                            }
                        }
                        let recorded_items = corpus.get("items").cloned().unwrap_or(Value::Null);
                        if !deep_eq(&arr(items.clone()), &recorded_items) {
                            problems.push(format!("{}: item lists differ", rel));
                            continue;
                        }
                        let h = hash_of(&arr(items.clone()));
                        let recorded_hash = corpus
                            .get("items_hash")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        if h != recorded_hash {
                            problems.push(format!(
                                "{}: items hash {} != Python {}",
                                rel, h, recorded_hash
                            ));
                            continue;
                        }
                        details.push(format!(
                            "{}: {} queued decisions, items hash {} == Python",
                            rel,
                            items.len(),
                            h
                        ));
                    }
                }
            }
        }
        rep.report(
            problems.is_empty(),
            "h. shape signatures (§12.1)",
            if problems.is_empty() {
                details.join("; ")
            } else {
                problems.join("; ")
            },
        );
    }

    // --- i. token-form battery ---
    {
        let problems = token_form_battery();
        rep.report(
            problems.is_empty(),
            "i. token-form battery (§§4–5)",
            if problems.is_empty() {
                "unknown forms REFUSED(SPEC) by name (probe, nested, if-branch, both hybrids, forged-at-evaluation); composition unions effects; literal values stay data".to_string()
            } else {
                problems.join("; ")
            },
        );
    }

    std::process::exit(if rep.failures == 0 { 0 } else { 1 });
}

fn submit_def(seq: &mut Sequencer, defn: Value, id: &str) -> Value {
    seq.submit(&make_envelope("operator", "definition", defn, &[], id))
}

fn token_form_battery() -> Vec<String> {
    let mut problems: Vec<String> = Vec::new();
    let sneaky = obj(vec![
        ("name", s("any-write")),
        (
            "signature",
            obj(vec![
                ("ins", arr(vec![s("list")])),
                ("outs", arr(vec![s("bool")])),
            ]),
        ),
        (
            "body",
            arr(vec![obj(vec![(
                "any",
                arr(vec![
                    s("drop"),
                    obj(vec![("lit", s("probe/sneaky"))]),
                    obj(vec![("lit", Value::Int(1))]),
                    s("write"),
                    obj(vec![("lit", Value::Bool(true))]),
                ]),
            )])]),
        ),
        (
            "examples",
            arr(vec![obj(vec![
                ("args", arr(vec![arr(vec![Value::Int(7)])])),
                ("expect", arr(vec![Value::Bool(true)])),
                ("requests", arr(vec![s("write")])),
            ])]),
        ),
    ]);
    {
        let mut seq = Sequencer::new();
        let v = submit_def(&mut seq, sneaky.clone(), "b-original");
        let detail = v.get("detail").and_then(|x| x.as_str()).unwrap_or("");
        if v.get("status") != Some(&s("REFUSED"))
            || v.get("refusal") != Some(&s("SPEC"))
            || !detail.contains("'any'")
            || seq.state.dict_get("any-write").is_some()
        {
            problems.push(format!(
                "original probe case: {}",
                canonical(&v).unwrap_or_default()
            ));
        }
    }
    {
        let mut seq = Sequencer::new();
        let nested_body_any = obj(vec![(
            "any",
            arr(vec![obj(vec![(
                "any",
                arr(vec![
                    s("drop"),
                    obj(vec![("lit", s("u"))]),
                    obj(vec![("lit", Value::Int(1))]),
                    s("write"),
                    obj(vec![("lit", Value::Bool(true))]),
                ]),
            )])]),
        )]);
        let nested = obj(vec![
            ("name", s("nested")),
            (
                "signature",
                obj(vec![
                    ("ins", arr(vec![s("list")])),
                    ("outs", arr(vec![s("bool")])),
                ]),
            ),
            ("body", arr(vec![nested_body_any])),
            ("examples", arr(vec![])),
        ]);
        let effects: Vec<String> = seq
            .dictionary
            .computed_effects(&nested)
            .into_iter()
            .collect();
        if effects != vec!["write".to_string()] {
            problems.push("nested quotation: walk did not account 'write'".to_string());
        }
        let v = submit_def(&mut seq, nested, "b-nested");
        if v.get("status") != Some(&s("REFUSED")) || v.get("refusal") != Some(&s("SPEC")) {
            problems.push(format!("nested quotation: {}", canonical(&v).unwrap_or_default()));
        }
        let branchy = obj(vec![
            ("name", s("branchy")),
            (
                "signature",
                obj(vec![("ins", arr(vec![])), ("outs", arr(vec![s("bool")]))]),
            ),
            (
                "body",
                arr(vec![
                    obj(vec![("lit", Value::Bool(true))]),
                    obj(vec![
                        (
                            "if",
                            arr(vec![obj(vec![(
                                "any",
                                arr(vec![
                                    s("drop"),
                                    obj(vec![("lit", s("u"))]),
                                    obj(vec![("lit", Value::Int(1))]),
                                    s("write"),
                                    obj(vec![("lit", Value::Bool(true))]),
                                ]),
                            )])]),
                        ),
                        ("else", arr(vec![obj(vec![("lit", Value::Bool(false))])])),
                    ]),
                ]),
            ),
            ("examples", arr(vec![])),
        ]);
        let effects: Vec<String> = seq
            .dictionary
            .computed_effects(&branchy)
            .into_iter()
            .collect();
        if effects != vec!["write".to_string()] {
            problems.push("if-branch quotation: walk did not account 'write'".to_string());
        }
        let v2 = submit_def(&mut seq, branchy, "b-branch");
        if v2.get("status") != Some(&s("REFUSED")) || v2.get("refusal") != Some(&s("SPEC")) {
            problems.push(format!(
                "if-branch quotation: {}",
                canonical(&v2).unwrap_or_default()
            ));
        }
    }
    {
        let mut seq = Sequencer::new();
        let inner = obj(vec![
            ("name", s("maybe-write")),
            (
                "signature",
                obj(vec![("ins", arr(vec![s("bool")])), ("outs", arr(vec![]))]),
            ),
            (
                "body",
                arr(vec![obj(vec![(
                    "if",
                    arr(vec![
                        obj(vec![("lit", s("u"))]),
                        obj(vec![("lit", Value::Int(1))]),
                        s("write"),
                    ]),
                )])]),
            ),
            ("examples", arr(vec![])),
        ]);
        let v = submit_def(&mut seq, inner, "b-inner");
        if v.get("status") != Some(&s("accepted"))
            || !deep_eq(
                v.get("computed_effects").unwrap_or(&Value::Null),
                &arr(vec![s("write")]),
            )
        {
            problems.push(format!(
                "composition inner: {}",
                canonical(&v).unwrap_or_default()
            ));
        }
        let outer = obj(vec![
            ("name", s("outer")),
            (
                "signature",
                obj(vec![("ins", arr(vec![s("bool")])), ("outs", arr(vec![]))]),
            ),
            ("body", arr(vec![s("maybe-write")])),
            ("examples", arr(vec![])),
        ]);
        let v2 = submit_def(&mut seq, outer, "b-outer");
        if v2.get("status") != Some(&s("accepted"))
            || !deep_eq(
                v2.get("computed_effects").unwrap_or(&Value::Null),
                &arr(vec![s("write")]),
            )
        {
            problems.push(format!(
                "composition outer: {}",
                canonical(&v2).unwrap_or_default()
            ));
        }
    }
    {
        let mut seq = Sequencer::new();
        let data_value = arr(vec![
            s("write"),
            s("send"),
            obj(vec![("any", arr(vec![s("spend")]))]),
        ]);
        let data_only = obj(vec![
            ("name", s("data-only")),
            (
                "signature",
                obj(vec![("ins", arr(vec![])), ("outs", arr(vec![s("list")]))]),
            ),
            ("body", arr(vec![obj(vec![("lit", data_value.clone())])])),
            (
                "examples",
                arr(vec![obj(vec![
                    ("args", arr(vec![])),
                    ("expect", arr(vec![data_value.clone()])),
                ])]),
            ),
        ]);
        let v = submit_def(&mut seq, data_only, "b-data");
        if v.get("status") != Some(&s("accepted"))
            || !deep_eq(
                v.get("computed_effects").unwrap_or(&Value::Null),
                &arr(vec![]),
            )
        {
            problems.push(format!(
                "literal data: {}",
                canonical(&v).unwrap_or_default()
            ));
        } else {
            match seq.evaluate_word("data-only", "operator", vec![]) {
                Ok((stack, requests)) => {
                    if !deep_eq(&arr(stack), &arr(vec![data_value.clone()])) || !requests.is_empty() {
                        problems.push("literal data: evaluation was not inert".to_string());
                    }
                }
                Err(err) => problems.push(format!("literal data: evaluation refused: {}", err)),
            }
        }
    }
    {
        let mut seq = Sequencer::new();
        let hybrid_if = obj(vec![
            ("name", s("hybrid-if")),
            (
                "signature",
                obj(vec![("ins", arr(vec![])), ("outs", arr(vec![s("bool")]))]),
            ),
            (
                "body",
                arr(vec![
                    obj(vec![("lit", Value::Bool(true))]),
                    obj(vec![
                        ("if", arr(vec![obj(vec![("lit", Value::Bool(true))])])),
                        ("any", arr(vec![obj(vec![("lit", Value::Bool(true))])])),
                    ]),
                ]),
            ),
            ("examples", arr(vec![])),
        ]);
        let v = submit_def(&mut seq, hybrid_if, "b-hybrid-if");
        if v.get("status") != Some(&s("REFUSED")) || v.get("refusal") != Some(&s("SPEC")) {
            problems.push(format!("hybrid if: {}", canonical(&v).unwrap_or_default()));
        }
        let hybrid_lit = obj(vec![
            ("name", s("hybrid-lit")),
            (
                "signature",
                obj(vec![("ins", arr(vec![])), ("outs", arr(vec![s("int")]))]),
            ),
            (
                "body",
                arr(vec![obj(vec![
                    ("lit", Value::Int(1)),
                    ("any", arr(vec![])),
                ])]),
            ),
            ("examples", arr(vec![])),
        ]);
        let v2 = submit_def(&mut seq, hybrid_lit, "b-hybrid-lit");
        if v2.get("status") != Some(&s("REFUSED")) || v2.get("refusal") != Some(&s("SPEC")) {
            problems.push(format!("hybrid lit: {}", canonical(&v2).unwrap_or_default()));
        }
    }
    {
        let seq = Sequencer::new();
        let mut stack: Vec<Value> = Vec::new();
        let mut requests: Vec<Value> = Vec::new();
        let ctx = seq.context("operator");
        let refs = obj(vec![]);
        let tokens = arr(vec![obj(vec![(
            "any",
            arr(vec![
                obj(vec![("lit", s("u"))]),
                obj(vec![("lit", Value::Int(1))]),
                s("write"),
            ]),
        )])]);
        let tokens = tokens.as_array().unwrap().clone();
        let caught = seq
            .dictionary
            .exec(&tokens, &mut stack, &mut requests, &ctx, &refs)
            .err();
        match caught {
            Some(err) if err.name == "SPEC" && requests.is_empty() => {}
            Some(err) => problems.push(format!(
                "forged body at evaluation refused as {}, not SPEC",
                err.name
            )),
            None => problems.push("forged body at evaluation was not REFUSED(SPEC)".to_string()),
        }
        let _ = Refusal::new("SPEC", "unused");
    }
    problems
}
