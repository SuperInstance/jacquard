//! jacquard-verify-anchor — the Rust port of
//! tools/jqanchor.py's verify verb (spec 15.5), over the
//! section 15 verifier in the anchor module.
//!
//!   jacquard-verify-anchor <log.jsonl> --checkpoints <dir> --pubkey <hex>
//!   jacquard-verify-anchor <log.jsonl> --checkpoints <dir> --keys <registry>
//!
//! --keys reads the witness key registry (spec 15.3,
//! jacquard/anchor-keys/1 or jacquard/anchor-keys/2) from a
//! keys.json file or a transport directory holding one, and
//! builds the pinned schedule for the presented log's id —
//! mirroring the TS twin and `jqanchor verify --keys`. The
//! /1 grammar is read under the legacy rule and the /2
//! grammar under the null-window rule (spec 15.3, erratum 2);
//! any other registry format is refused by name.
//!
//! Prints the result as JSON (the same eight fields as the
//! Python tool) and exits 0 for verified / verified_to_anchor,
//! 1 for failed, 3 for unanchored, 2 for tool refusal.

use jacquard_kernel::anchor::{schedule_from_registry, verify_anchor};
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
        } else if path.extension().map(|e| e == "json").unwrap_or(false)
            && path.file_name().map(|n| n != "keys.json").unwrap_or(false)
        {
            out.push(path);
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let log_path = args.get(1);
    let mut checkpoints_dir: Option<String> = None;
    let mut pubkey: Option<String> = None;
    let mut keys_path: Option<String> = None;
    let mut i = 2;
    while i < args.len() {
        if args[i] == "--checkpoints" {
            i += 1;
            checkpoints_dir = args.get(i).cloned();
        } else if args[i] == "--pubkey" {
            i += 1;
            pubkey = args.get(i).cloned();
        } else if args[i] == "--keys" {
            i += 1;
            keys_path = args.get(i).cloned();
        }
        i += 1;
    }
    let (Some(log_path), Some(checkpoints_dir)) = (log_path, checkpoints_dir) else {
        eprintln!(
            "usage: jacquard-verify-anchor <log.jsonl> --checkpoints <dir> (--pubkey <hex> | --keys <registry>)"
        );
        std::process::exit(2);
    };
    if pubkey.is_none() && keys_path.is_none() {
        eprintln!(
            "usage: jacquard-verify-anchor <log.jsonl> --checkpoints <dir> (--pubkey <hex> | --keys <registry>)"
        );
        std::process::exit(2);
    }
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
    // --keys: build the pinned schedule for this log's id from
    // the witness registry, exactly as the TS twin does.
    let mut schedule: Option<Vec<(i64, String)>> = None;
    let mut pinned: Option<String> = pubkey.clone();
    if let Some(keys_path) = &keys_path {
        let registry_file = if Path::new(keys_path).is_dir() {
            Path::new(keys_path).join("keys.json")
        } else {
            Path::new(keys_path).to_path_buf()
        };
        let registry = std::fs::read_to_string(&registry_file)
            .ok()
            .and_then(|text| parse_json(&text).ok());
        let registry = match registry {
            Some(r)
                if r.get("format") == Some(&s("jacquard/anchor-keys/1"))
                    || r.get("format") == Some(&s("jacquard/anchor-keys/2")) =>
            {
                r
            }
            _ => {
                eprintln!(
                    "{}: not a jacquard/anchor-keys/1 or jacquard/anchor-keys/2 registry",
                    registry_file.display()
                );
                std::process::exit(2);
            }
        };
        let log_id = if entries.is_empty() {
            "0".repeat(64)
        } else {
            entries[0]
                .get("hash")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        };
        let derived = match schedule_from_registry(&registry, &log_id) {
            Ok(sch) => sch,
            Err(err) => {
                eprintln!("{}", err);
                std::process::exit(2);
            }
        };
        pinned = Some(derived[0].1.clone());
        schedule = Some(derived);
    }
    let result = verify_anchor(
        &entries,
        &envelopes,
        pinned.as_deref().unwrap_or(""),
        schedule.as_deref(),
    );
    println!("{}", pretty_json(&result.to_value(), 0));
    std::process::exit(match result.outcome.as_deref() {
        Some("failed") => 1,
        Some("unanchored") => 3,
        _ => 0,
    });
}
