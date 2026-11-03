//! Canonical JSON values, the section 1 serialiser, and the
//! Python-semantics helpers the kernel port must reproduce.
//!
//! Written for Jacquard slice 20 as a port of the readings in
//! `conformance/ts/jacquard.ts` + `kernel.ts` (which themselves
//! port `src/jacquard/canonical.py` and the Python reference).
//!
//! Section 1, as the golden vectors and both existing
//! implementations establish it (see rust/GAPS.md for the spec
//! text divergence on this point): keys sorted lexicographic by
//! Unicode code point; separators `,` and `:`; integers only,
//! exact in the safe range -(2^53-1) .. 2^53-1 (refused outside
//! it rather than approximated, mirroring the TS reading);
//! strings emitted RAW as UTF-8 except the JSON-required escapes
//! (`"`, `\`, and control characters, with the short escapes
//! \b \f \n \r \t where they exist, else \u00xx lowercase hex) —
//! exactly Python `json.dumps(..., ensure_ascii=False)` and JS
//! `JSON.stringify` behaviour on the shapes the log contains.

use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::collections::BTreeSet;

pub const MAX_SAFE_INT: i64 = 9_007_199_254_740_991; // 2^53 - 1

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    /// A JSON number with a fraction/exponent. Canonical form
    /// refuses these; the variant exists so a parser can carry
    /// one far enough for the refusal to be the reported error.
    Float(f64),
    Str(String),
    Array(Vec<Value>),
    /// Insertion-ordered object (Python dict order).
    Object(Vec<(String, Value)>),
}

pub fn obj(pairs: Vec<(&str, Value)>) -> Value {
    Value::Object(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

pub fn arr(items: Vec<Value>) -> Value {
    Value::Array(items)
}

pub fn s(v: &str) -> Value {
    Value::Str(v.to_string())
}

impl Value {
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Object(pairs) => pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn get_mut(&mut self, key: &str) -> Option<&mut Value> {
        match self {
            Value::Object(pairs) => pairs.iter_mut().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn has(&self, key: &str) -> bool {
        self.get(key).is_some()
    }
    /// Python dict assignment: existing key keeps its position,
    /// a new key appends.
    pub fn set(&mut self, key: &str, value: Value) {
        if let Value::Object(pairs) = self {
            if let Some(slot) = pairs.iter_mut().find(|(k, _)| k == key) {
                slot.1 = value;
                return;
            }
            pairs.push((key.to_string(), value));
        }
    }
    pub fn remove_key(&mut self, key: &str) {
        if let Value::Object(pairs) = self {
            pairs.retain(|(k, _)| k != key);
        }
    }
    pub fn keys(&self) -> Vec<String> {
        match self {
            Value::Object(pairs) => pairs.iter().map(|(k, _)| k.clone()).collect(),
            _ => Vec::new(),
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(v) => Some(v),
            _ => None,
        }
    }
    pub fn as_int(&self) -> Option<i64> {
        match self {
            Value::Int(v) => Some(*v),
            _ => None,
        }
    }
    pub fn as_array(&self) -> Option<&Vec<Value>> {
        match self {
            Value::Array(v) => Some(v),
            _ => None,
        }
    }
    pub fn as_object(&self) -> Option<&Vec<(String, Value)>> {
        match self {
            Value::Object(v) => Some(v),
            _ => None,
        }
    }
    pub fn is_object(&self) -> bool {
        matches!(self, Value::Object(_))
    }
}

// ---------------------------------------------------------------------------
// JSON parsing (own code; preserves object insertion order and
// integer exactness, refuses nothing the reference accepts).
// ---------------------------------------------------------------------------

pub fn parse_json(text: &str) -> Result<Value, String> {
    let mut p = Parser { chars: text.chars().collect(), pos: 0 };
    p.skip_ws();
    let v = p.parse_value()?;
    p.skip_ws();
    if p.pos != p.chars.len() {
        return Err(format!("trailing characters at {}", p.pos));
    }
    Ok(v)
}

struct Parser {
    chars: Vec<char>,
    pos: usize,
}

impl Parser {
    fn peek(&self) -> Option<char> {
        self.chars.get(self.pos).copied()
    }
    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(' ' | '\t' | '\n' | '\r')) {
            self.pos += 1;
        }
    }
    fn expect(&mut self, c: char) -> Result<(), String> {
        if self.peek() == Some(c) {
            self.pos += 1;
            Ok(())
        } else {
            Err(format!("expected {:?} at {}", c, self.pos))
        }
    }
    fn parse_value(&mut self) -> Result<Value, String> {
        match self.peek() {
            Some('{') => {
                self.pos += 1;
                let mut pairs: Vec<(String, Value)> = Vec::new();
                self.skip_ws();
                if self.peek() == Some('}') {
                    self.pos += 1;
                    return Ok(Value::Object(pairs));
                }
                loop {
                    self.skip_ws();
                    let key = match self.parse_value()? {
                        Value::Str(k) => k,
                        _ => return Err("object key is not a string".into()),
                    };
                    self.skip_ws();
                    self.expect(':')?;
                    self.skip_ws();
                    let val = self.parse_value()?;
                    // Python json: a duplicate key keeps its first
                    // position and takes the last value.
                    if let Some(slot) = pairs.iter_mut().find(|(k, _)| *k == key) {
                        slot.1 = val;
                    } else {
                        pairs.push((key, val));
                    }
                    self.skip_ws();
                    match self.peek() {
                        Some(',') => {
                            self.pos += 1;
                        }
                        Some('}') => {
                            self.pos += 1;
                            return Ok(Value::Object(pairs));
                        }
                        other => return Err(format!("expected , or }} got {:?} at {}", other, self.pos)),
                    }
                }
            }
            Some('[') => {
                self.pos += 1;
                let mut items = Vec::new();
                self.skip_ws();
                if self.peek() == Some(']') {
                    self.pos += 1;
                    return Ok(Value::Array(items));
                }
                loop {
                    self.skip_ws();
                    items.push(self.parse_value()?);
                    self.skip_ws();
                    match self.peek() {
                        Some(',') => {
                            self.pos += 1;
                        }
                        Some(']') => {
                            self.pos += 1;
                            return Ok(Value::Array(items));
                        }
                        other => return Err(format!("expected , or ] got {:?} at {}", other, self.pos)),
                    }
                }
            }
            Some('"') => Ok(Value::Str(self.parse_string()?)),
            Some('t') => {
                self.literal("true")?;
                Ok(Value::Bool(true))
            }
            Some('f') => {
                self.literal("false")?;
                Ok(Value::Bool(false))
            }
            Some('n') => {
                self.literal("null")?;
                Ok(Value::Null)
            }
            Some(c) if c == '-' || c.is_ascii_digit() => self.parse_number(),
            other => Err(format!("unexpected {:?} at {}", other, self.pos)),
        }
    }
    fn literal(&mut self, word: &str) -> Result<(), String> {
        for c in word.chars() {
            if self.peek() != Some(c) {
                return Err(format!("bad literal at {}", self.pos));
            }
            self.pos += 1;
        }
        Ok(())
    }
    fn parse_string(&mut self) -> Result<String, String> {
        self.expect('"')?;
        let mut out = String::new();
        loop {
            let c = self.peek().ok_or("unterminated string")?;
            self.pos += 1;
            match c {
                '"' => return Ok(out),
                '\\' => {
                    let e = self.peek().ok_or("unterminated escape")?;
                    self.pos += 1;
                    match e {
                        '"' => out.push('"'),
                        '\\' => out.push('\\'),
                        '/' => out.push('/'),
                        'b' => out.push('\u{0008}'),
                        'f' => out.push('\u{000C}'),
                        'n' => out.push('\n'),
                        'r' => out.push('\r'),
                        't' => out.push('\t'),
                        'u' => {
                            let hi = self.hex4()?;
                            if (0xD800..0xDC00).contains(&hi) {
                                // High surrogate: a \uXXXX pair must follow.
                                if self.peek() == Some('\\') {
                                    self.pos += 1;
                                    if self.peek() == Some('u') {
                                        self.pos += 1;
                                        let lo = self.hex4()?;
                                        let cp = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00);
                                        out.push(char::from_u32(cp).ok_or("bad surrogate pair")?);
                                        continue;
                                    }
                                }
                                return Err("lone high surrogate".into());
                            }
                            if (0xDC00..0xE000).contains(&hi) {
                                return Err("lone low surrogate".into());
                            }
                            out.push(char::from_u32(hi).ok_or("bad \\u escape")?);
                        }
                        other => return Err(format!("bad escape {:?}", other)),
                    }
                }
                c => out.push(c),
            }
        }
    }
    fn hex4(&mut self) -> Result<u32, String> {
        let mut v: u32 = 0;
        for _ in 0..4 {
            let c = self.peek().ok_or("short \\u escape")?;
            self.pos += 1;
            v = v * 16 + c.to_digit(16).ok_or("bad hex digit")?;
        }
        Ok(v)
    }
    fn parse_number(&mut self) -> Result<Value, String> {
        let start = self.pos;
        if self.peek() == Some('-') {
            self.pos += 1;
        }
        let mut is_float = false;
        while let Some(c) = self.peek() {
            if c.is_ascii_digit() {
                self.pos += 1;
            } else if matches!(c, '.' | 'e' | 'E' | '+' | '-') {
                if matches!(c, '.' | 'e' | 'E') {
                    is_float = true;
                }
                self.pos += 1;
            } else {
                break;
            }
        }
        let text: String = self.chars[start..self.pos].iter().collect();
        if is_float {
            text.parse::<f64>().map(Value::Float).map_err(|e| e.to_string())
        } else {
            text.parse::<i64>()
                .map(Value::Int)
                .map_err(|_| format!("integer literal out of range: {}", text))
        }
    }
}

// ---------------------------------------------------------------------------
// Section 1 canonical serialisation (own code, byte-exact).
// ---------------------------------------------------------------------------

/// Lexicographic comparison by Unicode code point.
pub fn compare_code_points(a: &str, b: &str) -> Ordering {
    let mut ac = a.chars();
    let mut bc = b.chars();
    loop {
        match (ac.next(), bc.next()) {
            (None, None) => return Ordering::Equal,
            (None, Some(_)) => return Ordering::Less,
            (Some(_), None) => return Ordering::Greater,
            (Some(x), Some(y)) => {
                if x != y {
                    return (x as u32).cmp(&(y as u32));
                }
            }
        }
    }
}

pub fn sort_strings(values: &[String]) -> Vec<String> {
    let mut out = values.to_vec();
    out.sort_by(|a, b| compare_code_points(a, b));
    out
}

pub fn sorted_set(set: &BTreeSet<String>) -> Vec<String> {
    // BTreeSet's byte order equals code-point order in UTF-8, but
    // sort explicitly so the rule is the stated one.
    sort_strings(&set.iter().cloned().collect::<Vec<_>>())
}

fn escape_string(value: &str, out: &mut String) {
    out.push('"');
    for c in value.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{0008}' => out.push_str("\\b"),
            '\u{000C}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn canonical(value: &Value) -> Result<String, String> {
    let mut out = String::new();
    write_canonical(value, &mut out)?;
    Ok(out)
}

fn write_canonical(value: &Value, out: &mut String) -> Result<(), String> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Int(v) => {
            if v.abs() > MAX_SAFE_INT {
                return Err(format!(
                    "canonical: integer {} is outside the safe range",
                    v
                ));
            }
            out.push_str(&v.to_string());
        }
        Value::Float(v) => {
            return Err(format!(
                "canonical: non-integer number {} is not allowed",
                v
            ))
        }
        Value::Str(v) => escape_string(v, out),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_canonical(item, out)?;
            }
            out.push(']');
        }
        Value::Object(pairs) => {
            let mut keys: Vec<&String> = pairs.iter().map(|(k, _)| k).collect();
            keys.sort_by(|a, b| compare_code_points(a, b));
            out.push('{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                escape_string(k, out);
                out.push(':');
                write_canonical(value.get(k).unwrap(), out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

pub fn canonical_bytes(value: &Value) -> Result<Vec<u8>, String> {
    Ok(canonical(value)?.into_bytes())
}

/// The section 1 hash: lowercase hex SHA-256 of the canonical bytes.
pub fn hash_of(value: &Value) -> String {
    let bytes = canonical_bytes(value).expect("canonical form");
    hex_encode(&Sha256::digest(&bytes))
}

/// SHA-256 of the raw UTF-8 bytes of a bare string (the spec seal).
pub fn hash_string_raw(text: &str) -> String {
    hex_encode(&Sha256::digest(text.as_bytes()))
}

pub fn sha256_hex(data: &[u8]) -> String {
    hex_encode(&Sha256::digest(data))
}

pub fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

pub fn hex_decode(text: &str) -> Option<Vec<u8>> {
    if text.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(text.len() / 2);
    let bytes = text.as_bytes();
    for i in (0..bytes.len()).step_by(2) {
        let hi = (bytes[i] as char).to_digit(16)?;
        let lo = (bytes[i + 1] as char).to_digit(16)?;
        out.push((hi * 16 + lo) as u8);
    }
    Some(out)
}

// ---------------------------------------------------------------------------
// Python semantics helpers (mirroring kernel.ts's pyRepr /
// pyTruthy / pyEq / pyCompare, which mirror CPython).
// ---------------------------------------------------------------------------

pub fn py_repr(v: &Value) -> String {
    match v {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Int(n) => n.to_string(),
        Value::Float(f) => {
            if f.fract() == 0.0 && f.is_finite() {
                format!("{:.1}", f)
            } else {
                format!("{}", f)
            }
        }
        Value::Str(text) => {
            let mut out = String::from("'");
            for c in text.chars() {
                match c {
                    '\\' => out.push_str("\\\\"),
                    '\'' => out.push_str("\\'"),
                    '\n' => out.push_str("\\n"),
                    '\r' => out.push_str("\\r"),
                    '\t' => out.push_str("\\t"),
                    c => out.push(c),
                }
            }
            out.push('\'');
            out
        }
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(pairs) => {
            let parts: Vec<String> = pairs
                .iter()
                .map(|(k, x)| format!("{}: {}", py_repr(&Value::Str(k.clone())), py_repr(x)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
    }
}

pub fn py_truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Int(n) => *n != 0,
        Value::Float(f) => *f != 0.0,
        Value::Str(t) => !t.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

fn as_num(v: &Value) -> Option<f64> {
    match v {
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::Int(n) => Some(*n as f64),
        Value::Float(f) => Some(*f),
        _ => None,
    }
}

/// Python == over canonical values (True == 1, deep containers).
pub fn py_eq(a: &Value, b: &Value) -> bool {
    let (na, nb) = (as_num(a), as_num(b));
    if na.is_some() || nb.is_some() {
        return na.is_some() && nb.is_some() && na == nb;
    }
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y.iter()).all(|(u, v)| py_eq(u, v))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len()
                && x.iter().all(|(k, u)| match b.get(k) {
                    Some(v) => py_eq(u, v),
                    None => false,
                })
        }
        _ => false,
    }
}

pub fn py_compare(a: &Value, b: &Value) -> Result<Ordering, String> {
    let (na, nb) = (as_num(a), as_num(b));
    if na.is_some() && nb.is_some() {
        return Ok(na.unwrap().partial_cmp(&nb.unwrap()).unwrap_or(Ordering::Equal));
    }
    match (a, b) {
        (Value::Str(x), Value::Str(y)) => Ok(compare_code_points(x, y)),
        (Value::Array(x), Value::Array(y)) => {
            for (u, v) in x.iter().zip(y.iter()) {
                let c = py_compare(u, v)?;
                if c != Ordering::Equal {
                    return Ok(c);
                }
            }
            Ok(x.len().cmp(&y.len()))
        }
        _ => Err(format!("unorderable values: {} vs {}", py_repr(a), py_repr(b))),
    }
}

/// A small JSON pretty printer, indent 1 — the output shape of
/// the Python/TS anchor verifier CLIs (json.dumps(indent=1)).
pub fn pretty_json(value: &Value, indent: usize) -> String {
    let pad = " ".repeat(indent);
    let inner = " ".repeat(indent + 1);
    match value {
        Value::Array(items) => {
            if items.is_empty() {
                return "[]".to_string();
            }
            let parts: Vec<String> = items
                .iter()
                .map(|v| format!("{}{}", inner, pretty_json(v, indent + 1)))
                .collect();
            format!("[\n{}\n{}]", parts.join(",\n"), pad)
        }
        Value::Object(pairs) => {
            if pairs.is_empty() {
                return "{}".to_string();
            }
            let parts: Vec<String> = pairs
                .iter()
                .map(|(k, v)| {
                    let mut key = String::new();
                    escape_string(k, &mut key);
                    format!("{}{}: {}", inner, key, pretty_json(v, indent + 1))
                })
                .collect();
            format!("{{\n{}\n{}}}", parts.join(",\n"), pad)
        }
        other => canonical(other).unwrap_or_else(|_| "null".to_string()),
    }
}
