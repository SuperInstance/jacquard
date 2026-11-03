//! jacquard-verify-anchor — the Rust port of
//! tools/jqanchor.py's verify verb (spec 15.5), over the
//! section 15 verifier in the anchor module.
//!
//!   jacquard-verify-anchor <log.jsonl> --checkpoints <dir> --pubkey <hex>
//!
//! Prints the result as JSON (the same eight fields as the
//! Python tool) and exits 0 for verified / verified_to_anchor,
//! 1 for failed, 3 for unanchored, 2 for tool refusal.

use jacquard_kernel::anchor::verify_anchor;
use jacquard_kernel::value::{obj, parse_json, pretty_json, s, Value};
use std::path::Path;

fn collect_json(dir: &Path, out: &mut Vec<std::path::PathBuf>) {
    let mut names: Vec<_> = std::fs::read_dir(dir)
        .expect("read checkpoints dir")
        .filter_map(|e| e.ok())
        .collect();
    names.sort_by_key(|e| e.file_name());
    for entry in names {
        let path = entry.path();
        if path.is_dir() {
            collect_json(&path, out);
        } else if path.extension().map(|e| e == "json").unwrap_or(false) {
            out.push(path);
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let log_path = args.get(1);
    let mut checkpoints_dir: Option<String> = None;
    let mut pubkey: Option<String> = None;
    let mut i = 2;
    while i < args.len() {
        if args[i] == "--checkpoints" {
            i += 1;
            checkpoints_dir = args.get(i).cloned();
        } else if args[i] == "--pubkey" {
            i += 1;
            pubkey = args.get(i).cloned();
        }
        i += 1;
    }
    let (Some(log_path), Some(checkpoints_dir), Some(pubkey)) = (log_path, checkpoints_dir, pubkey)
    else {
        eprintln!(
            "usage: jacquard-verify-anchor <log.jsonl> --checkpoints <dir> --pubkey <hex>"
        );
        std::process::exit(2);
    };
    let entries: Vec<Value> = std::fs::read_to_string(log_path)
        .expect("read log")
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| parse_json(l).expect("parse log line"))
        .collect();
    let mut files = Vec::new();
    collect_json(Path::new(&checkpoints_dir), &mut files);
    let mut envelopes: Vec<Value> = Vec::new();
    let mut problems: Vec<String> = Vec::new();
    for file in &files {
        match std::fs::read_to_string(file) {
            Ok(text) => match parse_json(&text) {
                Ok(env) => {
                    let mut keys = env.keys();
                    keys.sort();
                    if keys.len() != 3 || keys[0] != "body" || keys[1] != "pubkey" || keys[2] != "sig" {
                        problems.push(format!("{}: not a checkpoint envelope", file.display()));
                        continue;
                    }
                    envelopes.push(env);
                }
                Err(err) => problems.push(format!("{}: {}", file.display(), err)),
            },
            Err(err) => problems.push(format!("{}: {}", file.display(), err)),
        }
    }
    if !problems.is_empty() {
        let out = obj(vec![
            ("outcome", s("failed")),
            (
                "failure",
                obj(vec![
                    ("stage", s("history")),
                    ("checkpoint_seq", Value::Null),
                    (
                        "detail",
                        s(&format!("checkpoint store problems: {}", problems.join("; "))),
                    ),
                ]),
            ),
        ]);
        println!("{}", pretty_json(&out, 0));
        std::process::exit(1);
    }
    let result = verify_anchor(&entries, &envelopes, &pubkey, None);
    println!("{}", pretty_json(&result.to_value(), 0));
    std::process::exit(match result.outcome.as_deref() {
        Some("failed") => 1,
        Some("unanchored") => 3,
        _ => 0,
    });
}
