//! The kernel port — a port of `conformance/ts/kernel.ts`, which
//! ports the Python reference modules primitives.py, records.py,
//! dictionary.py, policy.py, envelope.py, log.py and
//! sequencer.py (sections 7 and 7.1 — a kernel WITHOUT the
//! lifecycle machines installed, which per spec section 10.4
//! behaves exactly as the 0.1 kernel). Senses live in
//! `senses.rs`, the section 12.1 signature in `signature.rs`,
//! and the section 15.5 anchor verifier in `anchor.rs`.

use crate::core::{
    entry_hash, fold, genesis_prev, make_entry, spec_seal, state_hash, FoldedState,
    SPEC_VERSION,
};
use crate::value::{
    arr, canonical, hash_of, obj, py_compare, py_eq, py_repr, py_truthy, s, sort_strings,
    sorted_set, Value,
};
use std::collections::{BTreeSet, HashSet};
use std::fmt;
use std::rc::Rc;

// ---------------------------------------------------------------------------
// Refusals
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct Refusal {
    pub name: String,
    pub detail: String,
}

impl Refusal {
    pub fn new(name: &str, detail: impl Into<String>) -> Self {
        Refusal { name: name.to_string(), detail: detail.into() }
    }
    pub fn field(detail: impl Into<String>) -> Self {
        Refusal::new("FIELD", detail)
    }
    pub fn spec(detail: impl Into<String>) -> Self {
        Refusal::new("SPEC", detail)
    }
}

impl fmt::Display for Refusal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.name, self.detail)
    }
}

impl std::error::Error for Refusal {}

pub type KResult<T> = Result<T, Refusal>;

fn int_checked(value: &Value, what: &str) -> KResult<i64> {
    match value {
        Value::Int(n) => Ok(*n),
        _ => Err(Refusal::field(format!(
            "{} expects an integer, got {}",
            what,
            py_repr(value)
        ))),
    }
}

// ---------------------------------------------------------------------------
// Primitives (the 26) and syntax forms.
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
pub enum Tier {
    P,
    E,
}

pub struct PrimSpec {
    pub tier: Tier,
    pub ins: &'static [&'static str],
    pub outs: &'static [&'static str],
}

pub fn prim_spec(name: &str) -> Option<PrimSpec> {
    let (tier, ins, outs): (Tier, &[&str], &[&str]) = match name {
        "self" => (Tier::P, &[], &["str"]),
        "now" => (Tier::P, &[], &["int"]),
        "get" => (Tier::P, &["str"], &["val"]),
        "keys" => (Tier::P, &["str"], &["list"]),
        "cands" => (Tier::P, &["str"], &["list"]),
        "age" => (Tier::P, &["int"], &["int"]),
        "record" => (Tier::P, &["str", "str"], &["map"]),
        "sense" => (Tier::P, &["str"], &["val"]),
        "similar" => (Tier::P, &["str", "int"], &["list"]),
        "history" => (Tier::P, &["str", "int"], &["list"]),
        "eq" | "lt" | "gt" => (Tier::P, &["val", "val"], &["bool"]),
        "and" | "or" => (Tier::P, &["bool", "bool"], &["bool"]),
        "not" => (Tier::P, &["bool"], &["bool"]),
        "add" | "sub" | "mul" | "div" | "mod" => (Tier::P, &["int", "int"], &["int"]),
        "neg" | "abs" => (Tier::P, &["int"], &["int"]),
        "min2" | "max2" => (Tier::P, &["int", "int"], &["int"]),
        "count" => (Tier::P, &["list"], &["int"]),
        "sum" => (Tier::P, &["list"], &["int"]),
        "min" | "max" => (Tier::P, &["list"], &["val"]),
        "contains" => (Tier::P, &["list", "val"], &["bool"]),
        "hash" => (Tier::P, &["val"], &["str"]),
        "verify" => (Tier::P, &["val", "str"], &["bool"]),
        "evidence" => (Tier::P, &["int"], &["list"]),
        "def" => (Tier::P, &["str"], &["map"]),
        "write" => (Tier::E, &["str", "val"], &[]),
        "dispatch" => (Tier::E, &["map"], &[]),
        "spend" => (Tier::E, &["str", "int"], &[]),
        "notify" => (Tier::E, &["str", "val"], &[]),
        "send" => (Tier::E, &["str", "val"], &[]),
        "schedule" => (Tier::E, &["int", "map"], &[]),
        "define" => (Tier::E, &["map"], &[]),
        "checkpoint" => (Tier::E, &["str"], &[]),
        _ => return None,
    };
    Some(PrimSpec { tier, ins, outs })
}

pub fn is_tier_e(name: &str) -> bool {
    matches!(prim_spec(name), Some(p) if p.tier == Tier::E)
}

pub const SYNTAX_FORMS: [&str; 9] = [
    "dup", "drop", "swap", "over", "snoc", "assoc", "getf", "first", "cat",
];

// ---------------------------------------------------------------------------
// Evaluation context + records projection.
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct EvalContext {
    pub state: FoldedState,
    pub entries: Vec<Value>,
    pub producer: String,
    pub tentative: Value,
}

impl EvalContext {
    pub fn now_seq(&self) -> i64 {
        self.entries.len() as i64
    }
    pub fn record_lookup(&self, producer: &str, cls: &str) -> Value {
        let view = project_records(&self.entries);
        view
            .get(producer)
            .and_then(|by_cls| by_cls.get(cls))
            .cloned()
            .unwrap_or_else(|| obj(vec![]))
    }
}

/// records.py — producer records projection.
pub fn project_records(entries: &[Value]) -> Value {
    let mut out = obj(vec![]);
    let bucket_names = ["submissions", "allowed", "denied", "queued", "faults", "executions"];
    for entry in entries {
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        let producer = match body.get("producer").and_then(|v| v.as_str()) {
            Some(p) => p.to_string(),
            None => continue,
        };
        let kind = entry.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        let (cls, bump): (String, Vec<&str>) = match kind {
            "definition" => ("definition".to_string(), vec!["submissions", "allowed"]),
            "decision" => {
                let cls = body
                    .get("class")
                    .and_then(|v| v.as_str())
                    .unwrap_or("work")
                    .to_string();
                let mut bumps = vec!["submissions"];
                match body.get("outcome").and_then(|v| v.as_str()) {
                    Some("allow") => bumps.push("allowed"),
                    Some("deny") => bumps.push("denied"),
                    Some("queued") => bumps.push("queued"),
                    _ => {}
                }
                if body.has("fault") && !matches!(body.get("fault"), Some(Value::Null)) && body.get("fault") != Some(&Value::Bool(false)) {
                    // TS: `if (body.fault)` — Python truthiness.
                    if py_truthy(body.get("fault").unwrap()) {
                        bumps.push("faults");
                    }
                }
                (cls, bumps)
            }
            "execution" => (
                body.get("class")
                    .and_then(|v| v.as_str())
                    .unwrap_or("work")
                    .to_string(),
                vec!["executions"],
            ),
            _ => continue,
        };
        // Ensure bucket exists with the six counters in order.
        let mut root = std::mem::replace(&mut out, obj(vec![]));
        if !root.has(&producer) {
            root.set(&producer, obj(vec![]));
        }
        let by_cls = root.get_mut(&producer).unwrap();
        if !by_cls.has(&cls) {
            by_cls.set(
                &cls,
                obj(bucket_names.iter().map(|n| (*n, Value::Int(0))).collect::<Vec<_>>()),
            );
        }
        let bucket = by_cls.get_mut(&cls).unwrap();
        for name in bump {
            let cur = bucket.get(name).and_then(|v| v.as_int()).unwrap_or(0);
            bucket.set(name, Value::Int(cur + 1));
        }
        out = root;
    }
    out
}

pub fn outputs_and_uses(entries: &[Value], producer: &str) -> (i64, i64) {
    let mut produced: Vec<Value> = Vec::new();
    for entry in entries {
        if entry.get("kind") != Some(&s("execution")) {
            continue;
        }
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        if body.get("producer") != Some(&s(producer)) {
            continue;
        }
        if let Some(applied) = body.get("applied").and_then(|v| v.as_array()) {
            for item in applied {
                if let Some(outputs) = item.get("outputs").and_then(|v| v.as_array()) {
                    for o in outputs {
                        if !produced.iter().any(|p| py_eq(p, o)) {
                            produced.push(o.clone());
                        }
                    }
                }
            }
        }
    }
    let mut used: Vec<Value> = Vec::new();
    for entry in entries {
        if entry.get("kind") != Some(&s("execution")) {
            continue;
        }
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        if let Some(uses) = body.get("uses").and_then(|v| v.as_array()) {
            for u in uses {
                if produced.iter().any(|p| py_eq(p, u)) && !used.iter().any(|p| py_eq(p, u)) {
                    used.push(u.clone());
                }
            }
        }
    }
    (produced.len() as i64, used.len() as i64)
}

fn shape_key(cls: &str, effects: &[String]) -> String {
    format!("{}|{}", cls, sort_strings(effects).join(","))
}

fn similar_impl(ctx: &EvalContext, shape: &Value, k_raw: &Value) -> KResult<Value> {
    let shape_text = shape.as_str().unwrap_or("");
    let mut matches = Vec::new();
    for entry in &ctx.entries {
        if entry.get("kind") != Some(&s("decision")) {
            continue;
        }
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        if body.get("producer") != Some(&s(&ctx.producer)) {
            continue;
        }
        let cls = body.get("class").and_then(|v| v.as_str()).unwrap_or("work");
        let effects: Vec<String> = body
            .get("effects")
            .and_then(|v| v.as_array())
            .map(|items| {
                items
                    .iter()
                    .filter_map(|e| e.as_str().map(|t| t.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        if shape_key(cls, &effects) != shape_text {
            continue;
        }
        matches.push(obj(vec![
            ("class", s(cls)),
            ("effects", body.get("effects").cloned().unwrap_or_else(|| arr(vec![]))),
            ("outcome", body.get("outcome").cloned().unwrap_or(Value::Null)),
        ]));
    }
    let k = int_checked(k_raw, "similar")?;
    if k > 0 {
        let start = matches.len().saturating_sub(k as usize);
        Ok(arr(matches[start..].to_vec()))
    } else {
        Ok(arr(vec![]))
    }
}

fn history_impl(ctx: &EvalContext, unit: &Value, window_raw: &Value) -> KResult<Value> {
    let mut values = Vec::new();
    for entry in &ctx.entries {
        if entry.get("kind") != Some(&s("execution")) {
            continue;
        }
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        if let Some(applied) = body.get("applied").and_then(|v| v.as_array()) {
            for item in applied {
                if item.get("verb") == Some(&s("write")) {
                    if let Some(args) = item.get("args").and_then(|v| v.as_array()) {
                        if args.first() == Some(unit) {
                            values.push(args.get(1).cloned().unwrap_or(Value::Null));
                        }
                    }
                }
            }
        }
    }
    let window = int_checked(window_raw, "history")?;
    if window >= 0 {
        if window == 0 {
            return Ok(arr(vec![]));
        }
        let start = values.len().saturating_sub(window as usize);
        return Ok(arr(values[start..].to_vec()));
    }
    Ok(arr(values))
}

fn divmod_py(a_raw: &Value, b_raw: &Value) -> KResult<(i64, i64)> {
    let a = int_checked(a_raw, "div/mod")?;
    let b = int_checked(b_raw, "div/mod")?;
    if b == 0 {
        return Err(Refusal::field("division by zero"));
    }
    Ok((a.div_euclid(b), a.rem_euclid(b)))
}

fn prim_impl(ctx: &EvalContext, name: &str, args: &[Value]) -> KResult<Value> {
    let a = |i: usize| args.get(i).cloned().unwrap_or(Value::Null);
    match name {
        "self" => Ok(s(&ctx.producer.clone())),
        "now" => Ok(Value::Int(ctx.now_seq())),
        "get" => {
            let unit = a(0);
            let key = unit.as_str().unwrap_or("");
            Ok(ctx.state.units.get(key).cloned().unwrap_or(Value::Null))
        }
        "keys" => {
            let prefix = a(0);
            let prefix = prefix.as_str().unwrap_or("");
            let mut names: Vec<String> = ctx
                .state
                .units
                .keys()
                .into_iter()
                .filter(|k| k.starts_with(prefix))
                .collect();
            names = sort_strings(&names);
            Ok(arr(names.into_iter().map(|k| s(&k)).collect()))
        }
        "cands" => {
            let unit = a(0);
            let items = ctx
                .tentative
                .get(unit.as_str().unwrap_or(""))
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            Ok(arr(items))
        }
        "age" => {
            let seq = int_checked(&a(0), "age")?;
            Ok(Value::Int((ctx.now_seq() - seq).max(0)))
        }
        "record" => Ok(ctx.record_lookup(
            a(0).as_str().unwrap_or(""),
            a(1).as_str().unwrap_or(""),
        )),
        "sense" => {
            let name = a(0);
            Ok(ctx
                .state
                .senses
                .get(name.as_str().unwrap_or(""))
                .cloned()
                .unwrap_or(Value::Null))
        }
        "similar" => similar_impl(ctx, &a(0), &a(1)),
        "history" => history_impl(ctx, &a(0), &a(1)),
        "eq" => Ok(Value::Bool(py_eq(&a(0), &a(1)))),
        "lt" => Ok(Value::Bool(
            py_compare(&a(0), &a(1)).map_err(Refusal::field)? == std::cmp::Ordering::Less,
        )),
        "gt" => Ok(Value::Bool(
            py_compare(&a(0), &a(1)).map_err(Refusal::field)? == std::cmp::Ordering::Greater,
        )),
        "and" => Ok(Value::Bool(py_truthy(&a(0)) && py_truthy(&a(1)))),
        "or" => Ok(Value::Bool(py_truthy(&a(0)) || py_truthy(&a(1)))),
        "not" => Ok(Value::Bool(!py_truthy(&a(0)))),
        "add" => Ok(Value::Int(int_checked(&a(0), "add")? + int_checked(&a(1), "add")?)),
        "sub" => Ok(Value::Int(int_checked(&a(0), "sub")? - int_checked(&a(1), "sub")?)),
        "mul" => Ok(Value::Int(int_checked(&a(0), "mul")? * int_checked(&a(1), "mul")?)),
        "div" => Ok(Value::Int(divmod_py(&a(0), &a(1))?.0)),
        "mod" => Ok(Value::Int(divmod_py(&a(0), &a(1))?.1)),
        "neg" => Ok(Value::Int(-int_checked(&a(0), "neg")?)),
        "abs" => Ok(Value::Int(int_checked(&a(0), "abs")?.abs())),
        "min2" => Ok(Value::Int(int_checked(&a(0), "min2")?.min(int_checked(&a(1), "min2")?))),
        "max2" => Ok(Value::Int(int_checked(&a(0), "max2")?.max(int_checked(&a(1), "max2")?))),
        "count" => Ok(Value::Int(
            a(0).as_array().map(|v| v.len() as i64).unwrap_or(0),
        )),
        "sum" => {
            let mut total: i64 = 0;
            if let Some(items) = a(0).as_array() {
                for x in items {
                    total += int_checked(x, "sum")?;
                }
            }
            Ok(Value::Int(total))
        }
        "min" | "max" => {
            let list = a(0);
            let items = match list.as_array() {
                Some(v) if !v.is_empty() => v.clone(),
                _ => return Ok(Value::Null),
            };
            let mut best = items[0].clone();
            for x in &items[1..] {
                let c = py_compare(x, &best).map_err(Refusal::field)?;
                if (name == "min" && c == std::cmp::Ordering::Less)
                    || (name == "max" && c == std::cmp::Ordering::Greater)
                {
                    best = x.clone();
                }
            }
            Ok(best)
        }
        "contains" => {
            let list = a(0);
            let found = list
                .as_array()
                .map(|items| items.iter().any(|item| py_eq(item, &a(1))))
                .unwrap_or(false);
            Ok(Value::Bool(found))
        }
        "hash" => Ok(s(&hash_of(&a(0)))),
        "verify" => {
            let digest = a(1);
            Ok(Value::Bool(
                digest.as_str().map(|d| hash_of(&a(0)) == d).unwrap_or(false),
            ))
        }
        "evidence" => {
            let seq = int_checked(&a(0), "evidence")?;
            if seq >= 0 && (seq as usize) < ctx.entries.len() {
                let ev = ctx.entries[seq as usize]
                    .get("body")
                    .and_then(|b| b.get("evidence"))
                    .cloned()
                    .unwrap_or(Value::Null);
                if let Some(items) = ev.as_array() {
                    return Ok(arr(items.clone()));
                }
            }
            Ok(arr(vec![]))
        }
        "def" => {
            let name = a(0);
            if let Some(versions) = ctx.state.dict_get(name.as_str().unwrap_or("")) {
                if let Some(latest) = versions.last() {
                    return Ok(latest.definition.clone());
                }
            }
            Ok(obj(vec![]))
        }
        _ => Err(Refusal::spec(format!("no implementation: {}", name))),
    }
}

// ---------------------------------------------------------------------------
// Dictionary (spec section 5).
// ---------------------------------------------------------------------------

pub const TYPES: [&str; 6] = ["val", "int", "bool", "str", "list", "map"];

fn type_of(value: &Value) -> &'static str {
    match value {
        Value::Bool(_) => "bool",
        Value::Int(_) => "int",
        Value::Str(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "map",
        _ => "val",
    }
}

fn unify(a: &str, b: &str) -> Option<String> {
    if a == b {
        return Some(a.to_string());
    }
    if a == "val" {
        return Some(b.to_string());
    }
    if b == "val" {
        return Some(a.to_string());
    }
    None
}

fn form_key(token: &Value) -> String {
    let keys = sort_strings(&token.keys());
    keys.first().cloned().unwrap_or_default()
}

fn is_lit_token(token: &Value) -> bool {
    token.is_object() && token.keys().len() == 1 && token.has("lit")
}

fn is_if_token(token: &Value) -> bool {
    token.is_object()
        && token.has("if")
        && token.keys().iter().all(|k| k == "if" || k == "else")
}

/// The form-agnostic effects walk (spec section 5): descend into
/// every token position of every form except a literal's value.
pub fn walk_tokens(tokens: &[Value], out: &mut Vec<Value>) {
    for token in tokens {
        out.push(token.clone());
        if let Some(pairs) = token.as_object() {
            for (key, value) in pairs {
                if key == "lit" && pairs.len() == 1 {
                    continue;
                }
                if let Some(items) = value.as_array() {
                    walk_tokens(items, out);
                }
            }
        } else if let Some(items) = token.as_array() {
            walk_tokens(items, out);
        }
    }
}

pub fn walk_all(tokens: &[Value]) -> Vec<Value> {
    let mut out = Vec::new();
    walk_tokens(tokens, &mut out);
    out
}

/// The per-call environment the dictionary needs from its host:
/// the log entries (example contexts read them), and tentative
/// candidates.
pub struct Env<'a> {
    pub entries: &'a [Value],
    pub tentative: &'a Value,
}

pub struct Resolved {
    pub kind: &'static str, // "primitive" | "word"
    pub ins: Vec<String>,
    pub outs: Vec<String>,
    pub entry_hash: Option<String>,
    pub definition: Option<Value>,
}

#[derive(Clone)]
pub struct Dictionary {
    pub state: FoldedState,
}

impl Dictionary {
    pub fn new(state: FoldedState) -> Self {
        Dictionary { state }
    }

    pub fn resolve(&self, name: &str) -> Option<Resolved> {
        if let Some(spec) = prim_spec(name) {
            return Some(Resolved {
                kind: "primitive",
                ins: spec.ins.iter().map(|t| t.to_string()).collect(),
                outs: spec.outs.iter().map(|t| t.to_string()).collect(),
                entry_hash: None,
                definition: None,
            });
        }
        if let Some(versions) = self.state.dict_get(name) {
            if let Some(latest) = versions.last() {
                let defn = latest.definition.clone();
                let sig = defn.get("signature").cloned().unwrap_or(Value::Null);
                let strings = |v: Option<&Value>| -> Vec<String> {
                    v.and_then(|x| x.as_array())
                        .map(|items| {
                            items
                                .iter()
                                .map(|t| t.as_str().unwrap_or("").to_string())
                                .collect()
                        })
                        .unwrap_or_default()
                };
                return Some(Resolved {
                    kind: "word",
                    ins: strings(sig.get("ins")),
                    outs: strings(sig.get("outs")),
                    entry_hash: Some(latest.entry_hash.clone()),
                    definition: Some(defn),
                });
            }
        }
        None
    }

    fn version_by_hash(&self, name: &str, entry_hash: &str) -> Option<Value> {
        if let Some(versions) = self.state.dict_get(name) {
            for version in versions {
                if version.entry_hash == entry_hash {
                    return Some(version.definition.clone());
                }
            }
        }
        None
    }

    pub fn computed_effects(&self, defn: &Value) -> BTreeSet<String> {
        let mut seen = HashSet::new();
        self.computed_effects_inner(defn, &mut seen)
    }

    fn computed_effects_inner(
        &self,
        defn: &Value,
        seen: &mut HashSet<String>,
    ) -> BTreeSet<String> {
        let mut effects = BTreeSet::new();
        let body = defn.get("body").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        for token in walk_all(&body) {
            let name = match &token {
                Value::Str(t) => t.clone(),
                _ => continue,
            };
            if is_tier_e(&name) {
                effects.insert(name);
            } else if prim_spec(&name).is_none() && !SYNTAX_FORMS.contains(&name.as_str()) {
                if let Some(resolved) = self.resolve(&name) {
                    if resolved.kind == "word" {
                        let key = resolved.entry_hash.clone().unwrap_or_default();
                        if !seen.contains(&key) {
                            seen.insert(key);
                            let inner = self.computed_effects_inner(
                                resolved.definition.as_ref().unwrap(),
                                seen,
                            );
                            effects.extend(inner);
                        }
                    }
                }
            }
        }
        effects
    }

    pub fn define(&self, env: &Env, defn: &Value) -> KResult<Value> {
        for field in ["name", "signature", "body", "examples"] {
            if !defn.has(field) {
                return Err(Refusal::field(format!("definition missing field: {}", field)));
            }
        }
        let sig = defn.get("signature").cloned().unwrap_or(Value::Null);
        if !sig.has("ins") || !sig.has("outs") {
            return Err(Refusal::field("signature needs ins and outs"));
        }
        let mut sig_types: Vec<Value> = Vec::new();
        if let Some(items) = sig.get("ins").and_then(|v| v.as_array()) {
            sig_types.extend(items.iter().cloned());
        }
        if let Some(items) = sig.get("outs").and_then(|v| v.as_array()) {
            sig_types.extend(items.iter().cloned());
        }
        for t in &sig_types {
            let name = t.as_str().unwrap_or("");
            if !TYPES.contains(&name) {
                return Err(Refusal::field(format!(
                    "unknown type in signature: {}",
                    py_repr(t)
                )));
            }
        }
        let body = defn.get("body").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        // Reference existence (SPEC), gathering pinned refs.
        let mut refs = obj(vec![]);
        for token in walk_all(&body) {
            if let Value::Str(name) = &token {
                if prim_spec(name).is_none() && !SYNTAX_FORMS.contains(&name.as_str()) {
                    let resolved = self.resolve(name);
                    match resolved {
                        Some(r) if r.kind == "word" => {
                            refs.set(name, s(r.entry_hash.as_deref().unwrap_or("")));
                        }
                        _ => {
                            return Err(Refusal::spec(format!("unknown reference: {}", name)));
                        }
                    }
                }
            }
        }
        self.check_signature(defn)?;
        let effects = self.computed_effects(defn);
        if let Some(declared) = defn.get("declared_effects") {
            if !matches!(declared, Value::Null) {
                let declared_set: BTreeSet<String> = declared
                    .as_array()
                    .map(|items| {
                        items
                            .iter()
                            .filter_map(|e| e.as_str().map(|t| t.to_string()))
                            .collect()
                    })
                    .unwrap_or_default();
                if declared_set != effects {
                    return Err(Refusal::new(
                        "UNDERDECLARED",
                        format!(
                            "declared effects {} do not equal computed effects {}",
                            py_repr(&arr(sorted_set(&declared_set).into_iter().map(|x| s(&x)).collect())),
                            py_repr(&arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()))
                        ),
                    ));
                }
            }
        }
        self.check_examples(env, defn, &refs)?;
        Ok(obj(vec![
            ("name", defn.get("name").cloned().unwrap_or(Value::Null)),
            ("signature", defn.get("signature").cloned().unwrap_or(Value::Null)),
            ("body", defn.get("body").cloned().unwrap_or(Value::Null)),
            ("examples", defn.get("examples").cloned().unwrap_or(Value::Null)),
            ("refs", refs),
            (
                "computed_effects",
                arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()),
            ),
        ]))
    }

    // ---- signature simulation ----
    pub fn simulate(
        &self,
        tokens: &[Value],
        mut stack: Vec<String>,
        defn_name: &str,
    ) -> KResult<Vec<String>> {
        for token in tokens {
            if is_lit_token(token) {
                stack.push(type_of(token.get("lit").unwrap()).to_string());
            } else if is_if_token(token) {
                if stack.is_empty() {
                    return Err(Refusal::field(format!("{}: if with empty stack", defn_name)));
                }
                let cond = stack.pop().unwrap();
                if unify(&cond, "bool").is_none() {
                    return Err(Refusal::field(format!(
                        "{}: if condition is {}, not bool",
                        defn_name, cond
                    )));
                }
                let then_tokens = token.get("if").and_then(|v| v.as_array()).cloned().unwrap_or_default();
                let else_tokens = token.get("else").and_then(|v| v.as_array()).cloned().unwrap_or_default();
                let then_stack = self.simulate(&then_tokens, stack.clone(), defn_name)?;
                let else_stack = self.simulate(&else_tokens, stack.clone(), defn_name)?;
                if then_stack.len() != else_stack.len()
                    || then_stack
                        .iter()
                        .zip(else_stack.iter())
                        .any(|(a, b)| unify(a, b).is_none())
                {
                    return Err(Refusal::field(format!(
                        "{}: if branches leave different stack shapes ({} vs {})",
                        defn_name,
                        py_repr(&arr(then_stack.iter().map(|x| s(x)).collect())),
                        py_repr(&arr(else_stack.iter().map(|x| s(x)).collect()))
                    )));
                }
                stack = then_stack;
            } else if token.is_object() {
                return Err(Refusal::spec(format!(
                    "{}: token form {} is not defined in this version (SPEC section 5)",
                    defn_name,
                    py_repr(&s(&form_key(token)))
                )));
            } else if let Value::Str(name) = token {
                if SYNTAX_FORMS.contains(&name.as_str()) {
                    self.simulate_syntax(name, &mut stack, defn_name)?;
                } else {
                    let resolved = self
                        .resolve(name)
                        .ok_or_else(|| Refusal::spec(format!("unknown reference: {}", name)))?;
                    let (ins, outs) = (resolved.ins.clone(), resolved.outs.clone());
                    if stack.len() < ins.len() {
                        return Err(Refusal::field(format!(
                            "{}: stack underflow at {}",
                            defn_name, name
                        )));
                    }
                    let args: Vec<String> = stack[stack.len() - ins.len()..].to_vec();
                    stack.truncate(stack.len() - ins.len());
                    for (want, got) in ins.iter().zip(args.iter()) {
                        if unify(want, got).is_none() {
                            return Err(Refusal::field(format!(
                                "{}: {} expects {}, stack has {}",
                                defn_name,
                                name,
                                py_repr(&arr(ins.iter().map(|x| s(x)).collect())),
                                py_repr(&arr(args.iter().map(|x| s(x)).collect()))
                            )));
                        }
                    }
                    stack.extend(outs);
                }
            } else {
                return Err(Refusal::field(format!(
                    "{}: bad token {}",
                    defn_name,
                    py_repr(token)
                )));
            }
        }
        Ok(stack)
    }

    fn simulate_syntax(&self, token: &str, stack: &mut Vec<String>, defn_name: &str) -> KResult<()> {
        let need = |stack: &Vec<String>, n: usize| -> KResult<()> {
            if stack.len() < n {
                Err(Refusal::field(format!(
                    "{}: stack underflow at {}",
                    defn_name, token
                )))
            } else {
                Ok(())
            }
        };
        match token {
            "dup" => {
                need(stack, 1)?;
                stack.push(stack.last().unwrap().clone());
            }
            "drop" => {
                need(stack, 1)?;
                stack.pop();
            }
            "swap" => {
                need(stack, 2)?;
                let n = stack.len();
                stack.swap(n - 1, n - 2);
            }
            "over" => {
                need(stack, 2)?;
                stack.push(stack[stack.len() - 2].clone());
            }
            "snoc" => {
                need(stack, 2)?;
                stack.pop();
                let xs = stack.pop().unwrap();
                if unify(&xs, "list").is_none() {
                    return Err(Refusal::field(format!("{}: snoc on {}", defn_name, xs)));
                }
                stack.push("list".to_string());
            }
            "assoc" => {
                need(stack, 3)?;
                stack.pop();
                let key = stack.pop().unwrap();
                let m = stack.pop().unwrap();
                if unify(&m, "map").is_none() || unify(&key, "str").is_none() {
                    return Err(Refusal::field(format!(
                        "{}: assoc on {}/{}",
                        defn_name, m, key
                    )));
                }
                stack.push("map".to_string());
            }
            "getf" => {
                need(stack, 2)?;
                let key = stack.pop().unwrap();
                let m = stack.pop().unwrap();
                if unify(&m, "map").is_none() || unify(&key, "str").is_none() {
                    return Err(Refusal::field(format!(
                        "{}: getf on {}/{}",
                        defn_name, m, key
                    )));
                }
                stack.push("val".to_string());
            }
            "first" => {
                need(stack, 1)?;
                let xs = stack.pop().unwrap();
                if unify(&xs, "list").is_none() {
                    return Err(Refusal::field(format!("{}: first on {}", defn_name, xs)));
                }
                stack.push("val".to_string());
            }
            "cat" => {
                need(stack, 2)?;
                let b = stack.pop().unwrap();
                let a = stack.pop().unwrap();
                if unify(&a, "str").is_none() || unify(&b, "str").is_none() {
                    return Err(Refusal::field(format!(
                        "{}: cat on {}/{}",
                        defn_name, a, b
                    )));
                }
                stack.push("str".to_string());
            }
            _ => {}
        }
        Ok(())
    }

    fn check_signature(&self, defn: &Value) -> KResult<()> {
        let sig = defn.get("signature").cloned().unwrap_or(Value::Null);
        let stack: Vec<String> = sig
            .get("ins")
            .and_then(|v| v.as_array())
            .map(|items| items.iter().map(|t| t.as_str().unwrap_or("").to_string()).collect())
            .unwrap_or_default();
        let body = defn.get("body").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        let name = defn.get("name").and_then(|v| v.as_str()).unwrap_or("");
        let result = self.simulate(&body, stack, name)?;
        let outs: Vec<String> = sig
            .get("outs")
            .and_then(|v| v.as_array())
            .map(|items| items.iter().map(|t| t.as_str().unwrap_or("").to_string()).collect())
            .unwrap_or_default();
        if result.len() != outs.len()
            || result.iter().zip(outs.iter()).any(|(a, b)| unify(a, b).is_none())
        {
            return Err(Refusal::field(format!(
                "{}: body leaves stack {}, signature promises {}",
                name,
                py_repr(&arr(result.iter().map(|x| s(x)).collect())),
                py_repr(&arr(outs.iter().map(|x| s(x)).collect()))
            )));
        }
        Ok(())
    }

    // ---- examples ----
    fn check_examples(&self, env: &Env, defn: &Value, _refs: &Value) -> KResult<()> {
        let examples = defn
            .get("examples")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        let body = defn.get("body").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        for (i, example) in examples.iter().enumerate() {
            let mut state = FoldedState::empty();
            let given = example.get("state").cloned().unwrap_or(Value::Null);
            if let Some(units) = given.get("units").and_then(|v| v.as_object()) {
                for (k, v) in units {
                    state.units.set(k, v.clone());
                }
            }
            if let Some(senses) = given.get("senses").and_then(|v| v.as_object()) {
                for (k, v) in senses {
                    state.senses.set(k, v.clone());
                }
            }
            let ctx = EvalContext {
                state,
                entries: env.entries.to_vec(),
                producer: "example".to_string(),
                tentative: env.tentative.clone(),
            };
            // Word refs resolve against the current dictionary,
            // pinned by the refs gathered in define().
            let mut refs = obj(vec![]);
            for token in walk_all(&body) {
                if let Value::Str(name) = &token {
                    if prim_spec(name).is_none() && !SYNTAX_FORMS.contains(&name.as_str()) {
                        if let Some(resolved) = self.resolve(name) {
                            if resolved.kind == "word" {
                                refs.set(name, s(resolved.entry_hash.as_deref().unwrap_or("")));
                            }
                        }
                    }
                }
            }
            let args = example
                .get("args")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            let (stack, requests) = match self.run(&body, args, &ctx, &refs) {
                Ok(v) => v,
                Err(err) => {
                    return Err(Refusal::new(
                        "EXAMPLE",
                        format!("example {}: evaluation refused: {}", i, err.detail),
                    ))
                }
            };
            if example.has("expect") {
                let expect = example.get("expect").unwrap();
                if !py_eq(&arr(stack.clone()), expect) {
                    return Err(Refusal::new(
                        "EXAMPLE",
                        format!(
                            "example {}: expected final stack {}, got {}",
                            i,
                            py_repr(expect),
                            py_repr(&arr(stack))
                        ),
                    ));
                }
            }
            if example.has("requests") {
                let verbs = arr(requests
                    .iter()
                    .map(|r| r.get("verb").cloned().unwrap_or(Value::Null))
                    .collect());
                let expect = example.get("requests").unwrap();
                if !py_eq(&verbs, expect) {
                    return Err(Refusal::new(
                        "EXAMPLE",
                        format!(
                            "example {}: expected requests {}, got {}",
                            i,
                            py_repr(expect),
                            py_repr(&verbs)
                        ),
                    ));
                }
            }
        }
        Ok(())
    }

    // ---- evaluation ----
    pub fn evaluate(
        &self,
        name: &str,
        args: Vec<Value>,
        ctx: &EvalContext,
    ) -> KResult<(Vec<Value>, Vec<Value>)> {
        let versions = self
            .state
            .dict_get(name)
            .ok_or_else(|| Refusal::spec(format!("no such definition: {}", name)))?;
        let defn = versions
            .last()
            .ok_or_else(|| Refusal::spec(format!("no such definition: {}", name)))?
            .definition
            .clone();
        let refs = defn.get("refs").cloned().unwrap_or_else(|| obj(vec![]));
        let body = defn.get("body").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        self.run(&body, args, ctx, &refs)
    }

    pub fn run(
        &self,
        tokens: &[Value],
        stack: Vec<Value>,
        ctx: &EvalContext,
        refs: &Value,
    ) -> KResult<(Vec<Value>, Vec<Value>)> {
        let mut stack = stack;
        let mut requests = Vec::new();
        self.exec(tokens, &mut stack, &mut requests, ctx, refs)?;
        Ok((stack, requests))
    }

    pub fn exec(
        &self,
        tokens: &[Value],
        stack: &mut Vec<Value>,
        requests: &mut Vec<Value>,
        ctx: &EvalContext,
        refs: &Value,
    ) -> KResult<()> {
        for token in tokens {
            if is_lit_token(token) {
                stack.push(token.get("lit").unwrap().clone());
            } else if is_if_token(token) {
                if stack.is_empty() {
                    return Err(Refusal::field("if with empty stack"));
                }
                let branch = if py_truthy(&stack.pop().unwrap()) {
                    token.get("if").and_then(|v| v.as_array()).cloned().unwrap_or_default()
                } else {
                    token.get("else").and_then(|v| v.as_array()).cloned().unwrap_or_default()
                };
                self.exec(&branch, stack, requests, ctx, refs)?;
            } else if let Value::Str(name) = token {
                if SYNTAX_FORMS.contains(&name.as_str()) {
                    exec_syntax(name, stack)?;
                } else if let Some(spec) = prim_spec(name) {
                    let n = spec.ins.len();
                    if stack.len() < n {
                        return Err(Refusal::field(format!("stack underflow at {}", name)));
                    }
                    let args: Vec<Value> = stack[stack.len() - n..].to_vec();
                    stack.truncate(stack.len() - n);
                    if spec.tier == Tier::E {
                        requests.push(obj(vec![("verb", s(name)), ("args", arr(args))]));
                    } else {
                        let value = prim_impl(ctx, name, &args)?;
                        stack.push(value);
                    }
                } else {
                    let mut defn: Option<Value> = None;
                    if let Some(hash) = refs.get(name).and_then(|v| v.as_str()) {
                        defn = self.version_by_hash(name, hash);
                    }
                    if defn.is_none() {
                        if let Some(versions) = self.state.dict_get(name) {
                            defn = versions.last().map(|w| w.definition.clone());
                        }
                    }
                    let defn = defn.ok_or_else(|| {
                        Refusal::spec(format!("unknown reference: {}", name))
                    })?;
                    let inner_refs = defn.get("refs").cloned().unwrap_or_else(|| obj(vec![]));
                    let body = defn
                        .get("body")
                        .and_then(|v| v.as_array())
                        .cloned()
                        .unwrap_or_default();
                    self.exec(&body, stack, requests, ctx, &inner_refs)?;
                }
            } else if token.is_object() {
                return Err(Refusal::spec(format!(
                    "token form {} is not defined in this version (SPEC section 5)",
                    py_repr(&s(&form_key(token)))
                )));
            } else {
                return Err(Refusal::field(format!("bad token {}", py_repr(token))));
            }
        }
        Ok(())
    }
}

fn exec_syntax(token: &str, stack: &mut Vec<Value>) -> KResult<()> {
    let need = |stack: &Vec<Value>, n: usize| -> KResult<()> {
        if stack.len() < n {
            Err(Refusal::field(format!("stack underflow at {}", token)))
        } else {
            Ok(())
        }
    };
    match token {
        "dup" => {
            need(stack, 1)?;
            stack.push(stack.last().unwrap().clone());
        }
        "drop" => {
            need(stack, 1)?;
            stack.pop();
        }
        "swap" => {
            need(stack, 2)?;
            let n = stack.len();
            stack.swap(n - 1, n - 2);
        }
        "over" => {
            need(stack, 2)?;
            stack.push(stack[stack.len() - 2].clone());
        }
        "snoc" => {
            need(stack, 2)?;
            let value = stack.pop().unwrap();
            let xs = stack.pop().unwrap();
            let mut items = xs.as_array().cloned().unwrap_or_default();
            items.push(value);
            stack.push(arr(items));
        }
        "assoc" => {
            need(stack, 3)?;
            let value = stack.pop().unwrap();
            let key = stack.pop().unwrap();
            let mut m = stack.pop().unwrap();
            if m.is_object() {
                m.set(key.as_str().unwrap_or(""), value);
            }
            stack.push(m);
        }
        "getf" => {
            need(stack, 2)?;
            let key = stack.pop().unwrap();
            let m = stack.pop().unwrap();
            let value = m
                .get(key.as_str().unwrap_or(""))
                .cloned()
                .unwrap_or(Value::Null);
            stack.push(value);
        }
        "first" => {
            need(stack, 1)?;
            let xs = stack.pop().unwrap();
            let items = xs.as_array().cloned().unwrap_or_default();
            if items.is_empty() {
                return Err(Refusal::field("first of empty list"));
            }
            stack.push(items[0].clone());
        }
        "cat" => {
            need(stack, 2)?;
            let b = stack.pop().unwrap();
            let a = stack.pop().unwrap();
            stack.push(s(&format!(
                "{}{}",
                a.as_str().unwrap_or(""),
                b.as_str().unwrap_or("")
            )));
        }
        _ => {}
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Policy gate (spec section 7), policy/1.
// ---------------------------------------------------------------------------

pub const POLICY_VERSION: &str = "policy/1";
const PROTECTED_EFFECTS: [&str; 4] = ["send", "notify", "spend", "irreversible"];

pub fn decide_policy(
    producer: &str,
    effects: &BTreeSet<String>,
    standing: Option<&Value>,
) -> (String, Vec<String>) {
    if let Some(st) = standing {
        if st.get("status") == Some(&s("suspended")) {
            return ("deny".to_string(), vec!["producer-suspended".to_string()]);
        }
    }
    let protected: Vec<String> = effects
        .iter()
        .filter(|e| PROTECTED_EFFECTS.contains(&e.as_str()))
        .cloned()
        .collect();
    if !protected.is_empty() && producer != "operator" {
        return (
            "queue".to_string(),
            protected.iter().map(|v| format!("protected-effect:{}", v)).collect(),
        );
    }
    ("allow".to_string(), Vec::new())
}

// ---------------------------------------------------------------------------
// Envelope validation (spec section 3), Python order.
// ---------------------------------------------------------------------------

const ENVELOPE_FIELDS: [&str; 7] = [
    "v", "id", "producer", "kind", "body", "declared_effects", "spec_seal",
];

pub fn validate_envelope_py(envelope: &Value) -> Option<(String, String)> {
    if !envelope.is_object() {
        return Some(("FIELD".to_string(), "envelope is not an object".to_string()));
    }
    for field in ENVELOPE_FIELDS {
        if !envelope.has(field) {
            return Some((
                "FIELD".to_string(),
                format!("envelope missing field: {}", field),
            ));
        }
    }
    if envelope.get("v") != Some(&Value::Int(1)) {
        return Some((
            "SPEC".to_string(),
            format!(
                "unsupported envelope version: {}",
                py_repr(envelope.get("v").unwrap())
            ),
        ));
    }
    if envelope.get("spec_seal") != Some(&s(&spec_seal())) {
        return Some(("SPEC".to_string(), "spec seal mismatch".to_string()));
    }
    match envelope.get("kind").and_then(|v| v.as_str()) {
        Some("proposal") | Some("definition") | Some("machine") => {}
        _ => {
            return Some((
                "FIELD".to_string(),
                format!(
                    "unknown envelope kind: {}",
                    py_repr(envelope.get("kind").unwrap())
                ),
            ))
        }
    }
    if !matches!(envelope.get("declared_effects"), Some(Value::Array(_))) {
        return Some((
            "FIELD".to_string(),
            "declared_effects must be a list".to_string(),
        ));
    }
    None
}

pub fn envelope_hash(env: &Value) -> String {
    hash_of(env)
}

// ---------------------------------------------------------------------------
// The append-only hash-chained log (spec section 2).
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct Log {
    pub entries: Vec<Value>,
}

impl Log {
    pub fn new() -> Self {
        Log { entries: Vec::new() }
    }
    pub fn append(&mut self, kind: &str, body: Value) -> Result<Value, String> {
        if !crate::core::ENTRY_KINDS.contains(&kind) {
            return Err(format!("unknown entry kind: {}", py_repr(&s(kind))));
        }
        let prev = if let Some(last) = self.entries.last() {
            last.get("hash").and_then(|v| v.as_str()).unwrap_or("").to_string()
        } else {
            genesis_prev()
        };
        let entry = make_entry(self.entries.len() as i64, &prev, kind, body);
        let mut stored = entry.clone();
        stored.set("hash", s(&entry_hash(&entry)));
        self.entries.push(stored.clone());
        Ok(stored)
    }
    pub fn verify_chain(&self) -> bool {
        verify_internal_chain(&self.entries)
    }
    /// The on-disk form: one canonical line per entry, hash included.
    pub fn serialise(&self) -> String {
        let mut out = String::new();
        for e in &self.entries {
            out.push_str(&canonical(e).expect("canonical entry"));
            out.push('\n');
        }
        out
    }
}

pub fn verify_internal_chain(entries: &[Value]) -> bool {
    let mut prev = genesis_prev();
    for (i, e) in entries.iter().enumerate() {
        if e.get("seq") != Some(&Value::Int(i as i64)) {
            return false;
        }
        if e.get("prev") != Some(&s(&prev)) {
            return false;
        }
        if entry_hash(e) != e.get("hash").and_then(|v| v.as_str()).unwrap_or("") {
            return false;
        }
        prev = e.get("hash").unwrap().as_str().unwrap_or("").to_string();
    }
    true
}

// ---------------------------------------------------------------------------
// The sequencer (spec sections 3, 7, 7.1). A kernel without the
// lifecycle machines installed (spec 10.4).
// ---------------------------------------------------------------------------

pub type RuleDecider = Rc<
    dyn Fn(
        &str,
        &str,
        &BTreeSet<String>,
        &str,
        &Vec<String>,
        Option<&Vec<Value>>,
    ) -> Option<(String, String)>,
>;

fn outcome_stored(outcome: &str) -> &'static str {
    match outcome {
        "allow" => "allow",
        "deny" => "deny",
        _ => "queued",
    }
}

fn verdict_refused(name: &str, detail: &str) -> Value {
    obj(vec![
        ("status", s("REFUSED")),
        ("refusal", s(name)),
        ("detail", s(detail)),
    ])
}

pub struct Sequencer {
    pub log: Log,
    pub standing: Value,
    pub tentative: Value,
    pub verdicts: Vec<(String, Value)>,
    pub pumping: bool,
    pub rule_decider: Option<RuleDecider>,
    pub state: FoldedState,
    pub dictionary: Dictionary,
}

impl Sequencer {
    pub fn new() -> Self {
        Sequencer::with_log(Log::new())
    }

    pub fn with_log(log: Log) -> Self {
        let state = fold(&log.entries);
        let dictionary = Dictionary::new(state.clone());
        Sequencer {
            log,
            standing: obj(vec![]),
            tentative: obj(vec![]),
            verdicts: Vec::new(),
            pumping: false,
            rule_decider: None,
            state,
            dictionary,
        }
    }

    pub fn refold(&mut self) {
        self.state = fold(&self.log.entries);
        self.dictionary.state = self.state.clone();
    }

    pub fn record_lookup(&self, producer: &str, cls: &str) -> Value {
        let view = project_records(&self.log.entries);
        view
            .get(producer)
            .and_then(|by_cls| by_cls.get(cls))
            .cloned()
            .unwrap_or_else(|| obj(vec![]))
    }

    pub fn context(&self, producer: &str) -> EvalContext {
        EvalContext {
            state: self.state.clone(),
            entries: self.log.entries.clone(),
            producer: producer.to_string(),
            tentative: self.tentative.clone(),
        }
    }

    pub fn evaluate_word(
        &self,
        name: &str,
        producer: &str,
        args: Vec<Value>,
    ) -> KResult<(Vec<Value>, Vec<Value>)> {
        self.dictionary.evaluate(name, args, &self.context(producer))
    }

    pub fn set_standing(&mut self, producer: &str, standing: Value) {
        self.standing.set(producer, standing);
    }

    // ---- senses / checkpoints / budgets / prices ----
    pub fn submit_sense(&mut self, name: &str, value: Value, producer: &str) -> Value {
        let entry = self
            .log
            .append("sense", obj(vec![("producer", s(producer)), ("name", s(name)), ("value", value)]))
            .expect("sense kind");
        self.refold();
        self.pump_waits();
        entry
    }

    pub fn checkpoint(&mut self, name: &str) -> Value {
        let entry = self
            .log
            .append(
                "checkpoint",
                obj(vec![("name", s(name)), ("state_hash", s(&state_hash(&self.state)))]),
            )
            .expect("checkpoint kind");
        self.refold();
        self.pump_waits();
        entry
    }

    pub fn grant_budget(&mut self, producer: &str, amount: i64) -> Value {
        let entry = self
            .log
            .append(
                "budget",
                obj(vec![
                    ("producer", s(producer)),
                    ("delta", Value::Int(amount)),
                    ("by", s("operator")),
                ]),
            )
            .expect("budget kind");
        self.refold();
        self.pump_waits();
        obj(vec![
            ("entry", entry.get("hash").cloned().unwrap_or(Value::Null)),
            (
                "balance",
                self.state.budgets.get(producer).cloned().unwrap_or(Value::Int(0)),
            ),
        ])
    }

    pub fn post_price(&mut self, resource: &str, price: i64) -> Value {
        let entry = self
            .log
            .append(
                "price",
                obj(vec![
                    ("resource", s(resource)),
                    ("price", Value::Int(price)),
                    ("by", s("operator")),
                ]),
            )
            .expect("price kind");
        self.refold();
        self.pump_waits();
        obj(vec![
            ("entry", entry.get("hash").cloned().unwrap_or(Value::Null)),
            ("price", Value::Int(price)),
        ])
    }

    // ---- submit ----
    pub fn submit(&mut self, envelope: &Value) -> Value {
        if let Some((name, detail)) = validate_envelope_py(envelope) {
            return verdict_refused(&name, &detail);
        }
        let env_hash = envelope_hash(envelope);
        if let Some((_, verdict)) = self.verdicts.iter().find(|(h, _)| *h == env_hash) {
            return verdict.clone();
        }
        let kind = envelope.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        let verdict = match kind {
            "definition" => self.submit_definition(envelope),
            "machine" => verdict_refused(
                "SPEC",
                "machine envelopes are outside the Rust port's scope (spec section 10; the fold covers machine entries)",
            ),
            _ => self.submit_proposal(envelope, &env_hash),
        };
        self.verdicts.push((env_hash, verdict.clone()));
        self.pump_waits();
        verdict
    }

    fn submit_definition(&mut self, envelope: &Value) -> Value {
        let entries = self.log.entries.clone();
        let tentative = self.tentative.clone();
        let env = Env { entries: &entries, tentative: &tentative };
        let stored = self
            .dictionary
            .define(&env, envelope.get("body").unwrap_or(&Value::Null));
        let stored = match stored {
            Ok(v) => v,
            Err(err) => return verdict_refused(&err.name, &err.detail),
        };
        let entry = self
            .log
            .append(
                "definition",
                obj(vec![
                    ("producer", envelope.get("producer").cloned().unwrap_or(Value::Null)),
                    ("definition", stored.clone()),
                ]),
            )
            .expect("definition kind");
        self.refold();
        obj(vec![
            ("status", s("accepted")),
            ("entry", entry.get("hash").cloned().unwrap_or(Value::Null)),
            (
                "computed_effects",
                stored.get("computed_effects").cloned().unwrap_or(Value::Null),
            ),
        ])
    }

    fn check_requests(requests: Option<&Vec<Value>>) -> Option<(String, String)> {
        let requests = match requests {
            Some(r) => r,
            None => {
                return Some((
                    "FIELD".to_string(),
                    "proposal body.requests must be a list".to_string(),
                ))
            }
        };
        for request in requests {
            if !request.is_object() || !request.has("verb") || !request.has("args") {
                return Some((
                    "FIELD".to_string(),
                    "each request needs verb and args".to_string(),
                ));
            }
            let verb = request.get("verb").unwrap();
            if !matches!(verb, Value::Str(name) if is_tier_e(name)) {
                return Some((
                    "FIELD".to_string(),
                    format!("unknown effect verb: {}", py_repr(verb)),
                ));
            }
            if verb == &s("write") {
                let args = request.get("args").and_then(|v| v.as_array());
                let ok = matches!(args, Some(a) if a.len() == 2 && matches!(a.first(), Some(Value::Str(_))));
                if !ok {
                    return Some((
                        "FIELD".to_string(),
                        "write expects [unit, value]".to_string(),
                    ));
                }
            }
        }
        None
    }

    fn wait_precheck(
        &self,
        wait: &Value,
        declared_effects: &[Value],
        body: &Value,
        requests: &[Value],
        env_hash: &str,
    ) -> Option<Value> {
        let refused = |name: &str, detail: String| -> Option<Value> {
            let mut v = verdict_refused(name, &detail);
            v.set("proposal_id", s(env_hash));
            Some(v)
        };
        let bad_shape = !wait.is_object()
            || !matches!(wait.get("guard"), Some(Value::Str(_)))
            || !matches!(wait.get("deadline_seq"), Some(Value::Int(_)));
        if bad_shape {
            return refused(
                "FIELD",
                "wait must be {\"guard\": <word name>, \"deadline_seq\": <int>}".to_string(),
            );
        }
        let guard = wait.get("guard").unwrap().as_str().unwrap().to_string();
        let resolved = self.dictionary.resolve(&guard);
        let resolved = match resolved {
            Some(r) if r.kind == "word" => r,
            _ => {
                return refused(
                    "SPEC",
                    format!("wait guard is not a dictionary word: {}", guard),
                )
            }
        };
        if resolved.ins != vec!["map".to_string()] || resolved.outs != vec!["bool".to_string()] {
            return refused(
                "FIELD",
                format!(
                    "wait guard {} must have signature (map -> bool), has ({} -> {})",
                    guard,
                    py_repr(&arr(resolved.ins.iter().map(|x| s(x)).collect())),
                    py_repr(&arr(resolved.outs.iter().map(|x| s(x)).collect()))
                ),
            );
        }
        let defn = resolved.definition.as_ref().unwrap();
        let effects: BTreeSet<String> = defn
            .get("computed_effects")
            .and_then(|v| v.as_array())
            .map(|items| {
                items
                    .iter()
                    .filter_map(|e| e.as_str().map(|t| t.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        if !effects.is_empty() {
            return refused(
                "SPEC",
                format!(
                    "wait guard {} must be pure, its computed effects are {}",
                    guard,
                    py_repr(&arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()))
                ),
            );
        }
        let mut actual = BTreeSet::new();
        for request in requests {
            if let Some(verb) = request.get("verb").and_then(|v| v.as_str()) {
                actual.insert(verb.to_string());
            }
        }
        if let Some(irr) = body.get("irreversible") {
            if py_truthy(irr) {
                actual.insert("irreversible".to_string());
            }
        }
        let declared: BTreeSet<String> = declared_effects
            .iter()
            .filter_map(|e| e.as_str().map(|t| t.to_string()))
            .collect();
        if !actual.iter().all(|e| declared.contains(e)) {
            return refused(
                "UNDERDECLARED",
                format!(
                    "declared effects {} do not cover actual effects {}",
                    py_repr(&arr(sorted_set(&declared).into_iter().map(|x| s(&x)).collect())),
                    py_repr(&arr(sorted_set(&actual).into_iter().map(|x| s(&x)).collect()))
                ),
            );
        }
        None
    }

    fn submit_proposal(&mut self, envelope: &Value, env_hash: &str) -> Value {
        let producer = envelope.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let body = envelope.get("body").cloned().unwrap_or(Value::Null);
        let cls = body.get("class").and_then(|v| v.as_str()).unwrap_or("work").to_string();
        let requests = body.get("requests").and_then(|v| v.as_array());
        if let Some((name, detail)) = Self::check_requests(requests) {
            return verdict_refused(&name, &detail);
        }
        let reqs: Vec<Value> = requests.unwrap().clone();
        let mut wait_satisfied: Option<String> = None;
        if let Some(wait) = body.get("wait") {
            if !matches!(wait, Value::Null) {
                let wait = wait.clone();
                let declared = envelope
                    .get("declared_effects")
                    .and_then(|v| v.as_array())
                    .cloned()
                    .unwrap_or_default();
                if let Some(early) = self.wait_precheck(&wait, &declared, &body, &reqs, env_hash) {
                    return early;
                }
                let guard = wait.get("guard").unwrap().as_str().unwrap().to_string();
                let evaluated = self.evaluate_word(
                    &guard,
                    &producer,
                    vec![obj(vec![("proposal_id", s(env_hash))])],
                );
                let (stack, emitted) = match evaluated {
                    Ok(v) => v,
                    Err(err) => {
                        let mut v = verdict_refused(&err.name, &err.detail);
                        v.set("proposal_id", s(env_hash));
                        return v;
                    }
                };
                if !emitted.is_empty() {
                    let mut v = verdict_refused(
                        "SPEC",
                        &format!(
                            "wait guard {} emitted requests {}",
                            guard,
                            py_repr(&arr(emitted))
                        ),
                    );
                    v.set("proposal_id", s(env_hash));
                    return v;
                }
                if py_eq(&arr(stack.clone()), &arr(vec![Value::Bool(true)])) {
                    wait_satisfied = Some(guard);
                } else if py_eq(&arr(stack.clone()), &arr(vec![Value::Bool(false)])) {
                    let mut effects = BTreeSet::new();
                    for request in &reqs {
                        if let Some(verb) = request.get("verb").and_then(|v| v.as_str()) {
                            effects.insert(verb.to_string());
                        }
                    }
                    if let Some(irr) = body.get("irreversible") {
                        if py_truthy(irr) {
                            effects.insert("irreversible".to_string());
                        }
                    }
                    let irreversible = body
                        .get("irreversible")
                        .map(py_truthy)
                        .unwrap_or(false);
                    self.log
                        .append(
                            "decision",
                            obj(vec![
                                ("producer", s(&producer)),
                                ("class", s(&cls)),
                                ("proposal_id", s(env_hash)),
                                ("policy_version", s(POLICY_VERSION)),
                                ("outcome", s("queued")),
                                ("reasons", arr(vec![s(&format!("waiting:{}", guard))])),
                                (
                                    "effects",
                                    arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()),
                                ),
                                ("requests", arr(reqs.clone())),
                                ("irreversible", Value::Bool(irreversible)),
                                ("uses", body.get("uses").cloned().unwrap_or_else(|| arr(vec![]))),
                                ("wait", wait.clone()),
                            ]),
                        )
                        .expect("decision kind");
                    self.refold();
                    return obj(vec![
                        ("status", s("decided")),
                        ("outcome", s("queue")),
                        ("proposal_id", s(env_hash)),
                        ("reasons", arr(vec![s(&format!("waiting:{}", guard))])),
                    ]);
                } else {
                    let mut v = verdict_refused(
                        "FIELD",
                        &format!(
                            "wait guard {} must leave exactly one bool, got {}",
                            guard,
                            py_repr(&arr(stack))
                        ),
                    );
                    v.set("proposal_id", s(env_hash));
                    return v;
                }
            }
        }
        // Normal path.
        let mut effects = BTreeSet::new();
        for request in &reqs {
            if let Some(verb) = request.get("verb").and_then(|v| v.as_str()) {
                effects.insert(verb.to_string());
            }
        }
        if let Some(irr) = body.get("irreversible") {
            if py_truthy(irr) {
                effects.insert("irreversible".to_string());
            }
        }
        let declared: BTreeSet<String> = envelope
            .get("declared_effects")
            .and_then(|v| v.as_array())
            .map(|items| {
                items
                    .iter()
                    .filter_map(|e| e.as_str().map(|t| t.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        if !effects.iter().all(|e| declared.contains(e)) {
            let detail = format!(
                "declared effects {} do not cover actual effects {}",
                py_repr(&arr(sorted_set(&declared).into_iter().map(|x| s(&x)).collect())),
                py_repr(&arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()))
            );
            self.log
                .append(
                    "decision",
                    obj(vec![
                        ("producer", s(&producer)),
                        ("class", s(&cls)),
                        ("proposal_id", s(env_hash)),
                        ("policy_version", s(POLICY_VERSION)),
                        ("outcome", s("refused")),
                        ("fault", s("UNDERDECLARED")),
                        ("reasons", arr(vec![s(&detail)])),
                        (
                            "effects",
                            arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()),
                        ),
                    ]),
                )
                .expect("decision kind");
            self.refold();
            let mut v = verdict_refused("UNDERDECLARED", &detail);
            v.set("proposal_id", s(env_hash));
            return v;
        }
        for request in &reqs {
            if request.get("verb") == Some(&s("define")) {
                let entries = self.log.entries.clone();
                let tentative = self.tentative.clone();
                let env = Env { entries: &entries, tentative: &tentative };
                let target = request
                    .get("args")
                    .and_then(|v| v.as_array())
                    .and_then(|a| a.first())
                    .cloned()
                    .unwrap_or(Value::Null);
                if let Err(err) = self.dictionary.define(&env, &target) {
                    let mut v = verdict_refused(&err.name, &err.detail);
                    v.set("proposal_id", s(env_hash));
                    return v;
                }
            }
        }
        let view = self.record_lookup(&producer, &cls);
        let _ = view;
        let standing = self.standing.get(&producer).cloned();
        let (mut outcome, mut reasons) = decide_policy(&producer, &effects, standing.as_ref());
        let mut decided_by: Option<String> = None;
        let policy_outcome = outcome.clone();
        if let Some(decider) = self.rule_decider.clone() {
            if let Some((by, new_outcome)) = decider(
                &producer,
                &cls,
                &effects,
                &outcome,
                &reasons,
                Some(&reqs),
            ) {
                decided_by = Some(by);
                outcome = new_outcome;
                reasons = vec![format!("standing-rule:{}", decided_by.as_ref().unwrap())];
            }
        }
        if let Some(guard) = &wait_satisfied {
            let mut with_wait = vec![format!("wait-satisfied:{}", guard)];
            with_wait.extend(reasons);
            reasons = with_wait;
        }
        let mut decision = obj(vec![
            ("producer", s(&producer)),
            ("class", s(&cls)),
            ("proposal_id", s(env_hash)),
            ("policy_version", s(POLICY_VERSION)),
            ("outcome", s(outcome_stored(&outcome))),
            ("reasons", arr(reasons.iter().map(|r| s(r)).collect())),
            (
                "effects",
                arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()),
            ),
        ]);
        if let Some(by) = &decided_by {
            decision.set("decided_by", s(by));
            decision.set("policy_outcome", s(outcome_stored(&policy_outcome)));
        }
        if outcome == "queue" {
            decision.set("requests", arr(reqs.clone()));
            decision.set(
                "irreversible",
                Value::Bool(body.get("irreversible").map(py_truthy).unwrap_or(false)),
            );
            decision.set("uses", body.get("uses").cloned().unwrap_or_else(|| arr(vec![])));
        }
        self.log.append("decision", decision).expect("decision kind");
        if outcome == "allow" {
            self.execute(&producer, &cls, env_hash, &body);
        }
        self.refold();
        obj(vec![
            ("status", s("decided")),
            ("outcome", s(&outcome)),
            ("proposal_id", s(env_hash)),
            ("reasons", arr(reasons.iter().map(|r| s(r)).collect())),
        ])
    }

    // ---- execution ----
    pub fn execute(&mut self, producer: &str, cls: &str, proposal_id: &str, body: &Value) {
        let requests = body
            .get("requests")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        // Prepare every define first (validated against the
        // pre-execution dictionary, as in the reference).
        let mut prepared: Vec<Option<Value>> = Vec::new();
        for request in &requests {
            if request.get("verb") == Some(&s("define")) {
                let entries = self.log.entries.clone();
                let tentative = self.tentative.clone();
                let env = Env { entries: &entries, tentative: &tentative };
                let target = request
                    .get("args")
                    .and_then(|v| v.as_array())
                    .and_then(|a| a.first())
                    .cloned()
                    .unwrap_or(Value::Null);
                let stored = self
                    .dictionary
                    .define(&env, &target)
                    .expect("define prepared during submit");
                prepared.push(Some(stored));
            } else {
                prepared.push(None);
            }
        }
        let mut applied: Vec<Value> = Vec::new();
        for (i, request) in requests.iter().enumerate() {
            if request.get("verb") == Some(&s("define")) {
                let stored = prepared[i].clone().unwrap();
                self.log
                    .append(
                        "definition",
                        obj(vec![("producer", s(producer)), ("definition", stored)]),
                    )
                    .expect("definition kind");
            } else {
                let mut item = obj(vec![
                    ("verb", request.get("verb").cloned().unwrap_or(Value::Null)),
                    ("args", request.get("args").cloned().unwrap_or(Value::Null)),
                ]);
                if request.has("outputs") {
                    item.set("outputs", request.get("outputs").unwrap().clone());
                }
                applied.push(item);
            }
        }
        self.log
            .append(
                "execution",
                obj(vec![
                    ("producer", s(producer)),
                    ("class", s(cls)),
                    ("proposal_id", s(proposal_id)),
                    ("applied", arr(applied)),
                    ("uses", body.get("uses").cloned().unwrap_or_else(|| arr(vec![]))),
                ]),
            )
            .expect("execution kind");
        self.refold();
    }

    // ---- queue closing ----
    fn queued_or_refusal(&self, proposal_id: &str) -> Result<Value, Value> {
        match self.state.decision_queue.get(proposal_id) {
            Some(q) => Ok(q.clone()),
            None => Err(verdict_refused(
                "FIELD",
                &format!("no queued proposal with id {}", proposal_id),
            )),
        }
    }

    pub fn release_queued(
        &mut self,
        proposal_id: &str,
        operator: &str,
        reason: Option<&str>,
    ) -> Value {
        let queued = match self.queued_or_refusal(proposal_id) {
            Ok(q) => q,
            Err(v) => return v,
        };
        let producer = queued.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let cls = queued.get("class").and_then(|v| v.as_str()).unwrap_or("work").to_string();
        self.log
            .append(
                "decision",
                obj(vec![
                    ("producer", s(&producer)),
                    ("class", s(&cls)),
                    ("proposal_id", s(proposal_id)),
                    ("policy_version", s(POLICY_VERSION)),
                    ("outcome", s("allow")),
                    (
                        "reasons",
                        arr(vec![s(reason.unwrap_or("released-by-operator"))]),
                    ),
                    ("releases", s(proposal_id)),
                    ("released_by", s(operator)),
                    ("effects", queued.get("effects").cloned().unwrap_or_else(|| arr(vec![]))),
                ]),
            )
            .expect("decision kind");
        let body = obj(vec![
            ("requests", queued.get("requests").cloned().unwrap_or_else(|| arr(vec![]))),
            ("uses", queued.get("uses").cloned().unwrap_or_else(|| arr(vec![]))),
        ]);
        self.execute(&producer, &cls, proposal_id, &body);
        self.refold();
        self.pump_waits();
        obj(vec![
            ("status", s("decided")),
            ("outcome", s("allow")),
            ("released", s(proposal_id)),
        ])
    }

    pub fn reject_queued(
        &mut self,
        proposal_id: &str,
        operator: &str,
        reason: Option<&str>,
    ) -> Value {
        let queued = match self.queued_or_refusal(proposal_id) {
            Ok(q) => q,
            Err(v) => return v,
        };
        let producer = queued.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let cls = queued.get("class").and_then(|v| v.as_str()).unwrap_or("work").to_string();
        self.log
            .append(
                "decision",
                obj(vec![
                    ("producer", s(&producer)),
                    ("class", s(&cls)),
                    ("proposal_id", s(proposal_id)),
                    ("policy_version", s(POLICY_VERSION)),
                    ("outcome", s("deny")),
                    (
                        "reasons",
                        arr(vec![s(reason.unwrap_or("rejected-by-operator"))]),
                    ),
                    ("rejects", s(proposal_id)),
                    ("rejected_by", s(operator)),
                    ("effects", queued.get("effects").cloned().unwrap_or_else(|| arr(vec![]))),
                ]),
            )
            .expect("decision kind");
        self.refold();
        self.pump_waits();
        obj(vec![
            ("status", s("decided")),
            ("outcome", s("deny")),
            ("rejected", s(proposal_id)),
        ])
    }

    pub fn expire_queued(
        &mut self,
        proposal_id: &str,
        operator: &str,
        reason: Option<&str>,
    ) -> Value {
        let queued = match self.queued_or_refusal(proposal_id) {
            Ok(q) => q,
            Err(v) => return v,
        };
        let producer = queued.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let cls = queued.get("class").and_then(|v| v.as_str()).unwrap_or("work").to_string();
        self.log
            .append(
                "decision",
                obj(vec![
                    ("producer", s(&producer)),
                    ("class", s(&cls)),
                    ("proposal_id", s(proposal_id)),
                    ("policy_version", s(POLICY_VERSION)),
                    ("outcome", s("expired")),
                    (
                        "reasons",
                        arr(vec![s(reason.unwrap_or("expired-in-queue"))]),
                    ),
                    ("expires", s(proposal_id)),
                    ("expired_by", s(operator)),
                    ("effects", queued.get("effects").cloned().unwrap_or_else(|| arr(vec![]))),
                ]),
            )
            .expect("decision kind");
        self.refold();
        self.pump_waits();
        obj(vec![
            ("status", s("decided")),
            ("outcome", s("expired")),
            ("expired", s(proposal_id)),
        ])
    }

    // ---- the wait pump (spec 7.1) ----
    pub fn pump_waits(&mut self) {
        if self.pumping {
            return;
        }
        self.pumping = true;
        for _pass in 0..64 {
            let mut changed = false;
            let snapshot: Vec<String> = self
                .state
                .decision_queue
                .as_object()
                .map(|pairs| {
                    pairs
                        .iter()
                        .filter(|(_, body)| {
                            matches!(body.get("wait"), Some(w) if w.is_object())
                        })
                        .map(|(pid, _)| pid.clone())
                        .collect()
                })
                .unwrap_or_default();
            for pid in snapshot {
                if !self.state.decision_queue.has(&pid) {
                    continue;
                }
                let queued = self.state.decision_queue.get(&pid).unwrap().clone();
                if self.pump_one_waiter(&pid, &queued) {
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        self.pumping = false;
    }

    fn pump_one_waiter(&mut self, proposal_id: &str, queued: &Value) -> bool {
        let wait = queued.get("wait").cloned().unwrap_or(Value::Null);
        let guard = wait.get("guard").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let producer = queued.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let evaluated = self.evaluate_word(
            &guard,
            &producer,
            vec![obj(vec![("proposal_id", s(proposal_id))])],
        );
        let stack = match evaluated {
            Ok((stack, emitted)) => {
                if !emitted.is_empty() {
                    // Fall into the refusal-record path below with
                    // a SPEC refusal, as in the TS port.
                    let err = Refusal::spec(format!(
                        "wait guard {} emitted requests {}",
                        guard,
                        py_repr(&arr(emitted))
                    ));
                    return self.record_wait_refusal(proposal_id, queued, &wait, &err);
                }
                if !py_eq(&arr(stack.clone()), &arr(vec![Value::Bool(true)]))
                    && !py_eq(&arr(stack.clone()), &arr(vec![Value::Bool(false)]))
                {
                    let err = Refusal::field(format!(
                        "wait guard {} must leave exactly one bool, got {}",
                        guard,
                        py_repr(&arr(stack))
                    ));
                    return self.record_wait_refusal(proposal_id, queued, &wait, &err);
                }
                stack
            }
            Err(err) => {
                return self.record_wait_refusal(proposal_id, queued, &wait, &err);
            }
        };
        if py_eq(&arr(stack), &arr(vec![Value::Bool(true)])) {
            self.decide_waiter_fresh(proposal_id, queued, &guard);
            return true;
        }
        let deadline = wait.get("deadline_seq").and_then(|v| v.as_int()).unwrap_or(0);
        if (self.log.entries.len() as i64) > deadline {
            self.expire_queued(
                proposal_id,
                "wait-pump",
                Some(&format!("wait-expired:{}", guard)),
            );
            return true;
        }
        false
    }

    fn record_wait_refusal(
        &mut self,
        proposal_id: &str,
        queued: &Value,
        wait: &Value,
        err: &Refusal,
    ) -> bool {
        let marker = queued.get("wait_refusal_at");
        if let Some(Value::Int(m)) = marker {
            if *m == (self.log.entries.len() as i64) - 1 {
                return false;
            }
        }
        let seq_now = self.log.entries.len() as i64;
        self.log
            .append(
                "decision",
                obj(vec![
                    ("producer", queued.get("producer").cloned().unwrap_or(Value::Null)),
                    (
                        "class",
                        queued.get("class").cloned().unwrap_or_else(|| s("work")),
                    ),
                    ("proposal_id", s(proposal_id)),
                    ("policy_version", s(POLICY_VERSION)),
                    ("outcome", s("queued")),
                    (
                        "reasons",
                        arr(vec![s(&format!("wait-guard-refused:{}", err.name))]),
                    ),
                    ("effects", queued.get("effects").cloned().unwrap_or_else(|| arr(vec![]))),
                    (
                        "requests",
                        queued.get("requests").cloned().unwrap_or_else(|| arr(vec![])),
                    ),
                    (
                        "irreversible",
                        Value::Bool(
                            queued.get("irreversible").map(py_truthy).unwrap_or(false),
                        ),
                    ),
                    ("uses", queued.get("uses").cloned().unwrap_or_else(|| arr(vec![]))),
                    ("wait", wait.clone()),
                    ("wait_refusal_at", Value::Int(seq_now)),
                ]),
            )
            .expect("decision kind");
        self.refold();
        true
    }

    fn decide_waiter_fresh(&mut self, proposal_id: &str, queued: &Value, guard: &str) {
        let producer = queued.get("producer").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let cls = queued.get("class").and_then(|v| v.as_str()).unwrap_or("work").to_string();
        let effects: BTreeSet<String> = queued
            .get("effects")
            .and_then(|v| v.as_array())
            .map(|items| {
                items
                    .iter()
                    .filter_map(|e| e.as_str().map(|t| t.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let standing = self.standing.get(&producer).cloned();
        let (mut outcome, mut reasons) = decide_policy(&producer, &effects, standing.as_ref());
        let mut decided_by: Option<String> = None;
        let policy_outcome = outcome.clone();
        if let Some(decider) = self.rule_decider.clone() {
            let requests = queued
                .get("requests")
                .and_then(|v| v.as_array())
                .cloned();
            if let Some((by, new_outcome)) = decider(
                &producer,
                &cls,
                &effects,
                &outcome,
                &reasons,
                requests.as_ref(),
            ) {
                decided_by = Some(by);
                outcome = new_outcome;
                reasons = vec![format!("standing-rule:{}", decided_by.as_ref().unwrap())];
            }
        }
        let mut with_wait = vec![format!("wait-satisfied:{}", guard)];
        with_wait.extend(reasons);
        let reasons = with_wait;
        let mut decision = obj(vec![
            ("producer", s(&producer)),
            ("class", s(&cls)),
            ("proposal_id", s(proposal_id)),
            ("policy_version", s(POLICY_VERSION)),
            ("outcome", s(outcome_stored(&outcome))),
            ("reasons", arr(reasons.iter().map(|r| s(r)).collect())),
            (
                "effects",
                arr(sorted_set(&effects).into_iter().map(|x| s(&x)).collect()),
            ),
        ]);
        if let Some(by) = &decided_by {
            decision.set("decided_by", s(by));
            decision.set("policy_outcome", s(outcome_stored(&policy_outcome)));
        }
        if outcome == "allow" {
            decision.set("releases", s(proposal_id));
            self.log.append("decision", decision).expect("decision kind");
            let body = obj(vec![
                (
                    "requests",
                    queued.get("requests").cloned().unwrap_or_else(|| arr(vec![])),
                ),
                ("uses", queued.get("uses").cloned().unwrap_or_else(|| arr(vec![]))),
            ]);
            self.execute(&producer, &cls, proposal_id, &body);
        } else if outcome == "deny" {
            decision.set("releases", s(proposal_id));
            self.log.append("decision", decision).expect("decision kind");
        } else if outcome == "queue" {
            decision.set(
                "requests",
                queued.get("requests").cloned().unwrap_or_else(|| arr(vec![])),
            );
            decision.set(
                "irreversible",
                Value::Bool(queued.get("irreversible").map(py_truthy).unwrap_or(false)),
            );
            decision.set("uses", queued.get("uses").cloned().unwrap_or_else(|| arr(vec![])));
            self.log.append("decision", decision).expect("decision kind");
            self.refold();
        }
        self.refold();
    }
}

// Re-export so bins can name the spec constant from one place.
pub const SPEC_VERSION_TEXT: &str = SPEC_VERSION;
