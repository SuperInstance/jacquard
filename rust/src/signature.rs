//! The section 12.1 shape signature — a port of the signature
//! section of `conformance/ts/kernel.ts`, which ports
//! `src/jacquard/learner.py`'s `shape_signature`.

use crate::value::{arr, s, Value};

fn basename_of(path: &str) -> String {
    match path.rfind('/') {
        Some(idx) => path[idx + 1..].to_string(),
        None => path.to_string(),
    }
}

fn abstract_token(token: &str) -> String {
    if token.len() > 1 && token.starts_with('-') {
        // The part before any `=`.
        return token.split('=').next().unwrap_or(token).to_string();
    }
    if token.contains("://") {
        return "<url>".to_string();
    }
    if token.contains('/') {
        return "<path>".to_string();
    }
    if !token.is_empty() && token.chars().all(|c| c.is_numeric()) {
        return "<num>".to_string();
    }
    token.to_string()
}

/// POSIX shell tokenisation (Python shlex.split, comments off),
/// mirroring the TS port's hand-rolled splitter.
pub fn shlex_split(raw: &str) -> Result<Vec<String>, String> {
    let chars: Vec<char> = raw.chars().collect();
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut started = false;
    let mut i = 0;
    while i < chars.len() {
        let ch = chars[i];
        if matches!(ch, ' ' | '\t' | '\n' | '\r') {
            if started {
                tokens.push(std::mem::take(&mut current));
                started = false;
            }
            i += 1;
        } else if ch == '\'' {
            started = true;
            i += 1;
            while i < chars.len() && chars[i] != '\'' {
                current.push(chars[i]);
                i += 1;
            }
            if i >= chars.len() {
                return Err("No closing quotation".to_string());
            }
            i += 1;
        } else if ch == '"' {
            started = true;
            i += 1;
            let mut closed = false;
            while i < chars.len() {
                if chars[i] == '"' {
                    closed = true;
                    i += 1;
                    break;
                }
                if chars[i] == '\\'
                    && i + 1 < chars.len()
                    && matches!(chars[i + 1], '"' | '\\' | '$' | '`' | '\n')
                {
                    if chars[i + 1] != '\n' {
                        current.push(chars[i + 1]);
                    }
                    i += 2;
                } else {
                    current.push(chars[i]);
                    i += 1;
                }
            }
            if !closed {
                return Err("No closing quotation".to_string());
            }
        } else if ch == '\\' {
            started = true;
            if i + 1 < chars.len() {
                if chars[i + 1] != '\n' {
                    current.push(chars[i + 1]);
                }
                i += 2;
            } else {
                i += 1;
            }
        } else {
            started = true;
            current.push(ch);
            i += 1;
        }
    }
    if started {
        tokens.push(current);
    }
    Ok(tokens)
}

fn split_segments(script: &str) -> Vec<String> {
    // Split on &&, ||, ;, | and newlines (the TS port's
    // /&&|\|\||[;|\n]/ — a single | also splits).
    let chars: Vec<char> = script.chars().collect();
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '&' && i + 1 < chars.len() && chars[i + 1] == '&' {
            out.push(std::mem::take(&mut cur));
            i += 2;
        } else if chars[i] == '|' && i + 1 < chars.len() && chars[i + 1] == '|' {
            out.push(std::mem::take(&mut cur));
            i += 2;
        } else if matches!(chars[i], ';' | '|' | '\n') {
            out.push(std::mem::take(&mut cur));
            i += 1;
        } else {
            cur.push(chars[i]);
            i += 1;
        }
    }
    out.push(cur);
    out
}

fn to_text(v: &Value) -> String {
    // TS String(t) over the token shapes that appear: strings
    // verbatim; other values in their JS text form.
    match v {
        Value::Str(t) => t.clone(),
        Value::Int(n) => n.to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Null => "null".to_string(),
        other => crate::value::canonical(other).unwrap_or_default(),
    }
}

fn command_skeleton(cmd: &[Value]) -> Vec<Vec<String>> {
    let tokens: Vec<String> = cmd.iter().map(to_text).collect();
    let shell_programs = ["sh", "bash", "dash", "zsh", "ksh"];
    let mut segments: Vec<Vec<String>> = Vec::new();
    if tokens.len() >= 3 && tokens[1] == "-c" && shell_programs.contains(&basename_of(&tokens[0]).as_str()) {
        for raw in split_segments(&tokens[2]) {
            let parts = match shlex_split(&raw) {
                Ok(p) => p,
                Err(_) => raw.split_whitespace().map(|p| p.to_string()).collect(),
            };
            if !parts.is_empty() {
                segments.push(parts);
            }
        }
    } else if !tokens.is_empty() {
        segments.push(tokens);
    }
    segments
        .iter()
        .map(|parts| {
            let mut seg = vec![basename_of(&parts[0])];
            for t in &parts[1..] {
                seg.push(abstract_token(t));
            }
            seg
        })
        .collect()
}

fn send_host(channel: &str) -> String {
    // Python urlparse(...).hostname as the TS port reproduces
    // it: lowercased host of the netloc, or "" with no netloc.
    let mut rest = channel;
    // scheme: ^[A-Za-z][A-Za-z0-9+.-]*:
    let bytes: Vec<char> = channel.chars().collect();
    if !bytes.is_empty() && bytes[0].is_ascii_alphabetic() {
        let mut i = 1;
        while i < bytes.len()
            && (bytes[i].is_ascii_alphanumeric() || matches!(bytes[i], '+' | '-' | '.'))
        {
            i += 1;
        }
        if i < bytes.len() && bytes[i] == ':' {
            rest = &channel[channel.char_indices().nth(i + 1).map(|(b, _)| b).unwrap_or(channel.len())..];
        }
    }
    if !rest.starts_with("//") {
        return String::new();
    }
    rest = &rest[2..];
    let netloc: String = rest
        .chars()
        .take_while(|c| !matches!(c, '/' | '?' | '#'))
        .collect();
    let hostport = match netloc.rfind('@') {
        Some(idx) => &netloc[idx + 1..],
        None => &netloc[..],
    };
    if hostport.starts_with('[') {
        let inner = match hostport.find(']') {
            Some(end) => &hostport[1..end],
            None => &hostport[1..],
        };
        return inner.to_lowercase();
    }
    hostport
        .split(':')
        .next()
        .unwrap_or("")
        .to_lowercase()
}

/// Section 12.1: one [verb, detail] component per request, in
/// order.
pub fn shape_signature(requests: Option<&Vec<Value>>) -> Value {
    let mut components: Vec<Value> = Vec::new();
    if let Some(requests) = requests {
        for request in requests {
            if !request.is_object() {
                components.push(arr(vec![Value::Null, s("")]));
                continue;
            }
            let verb = request.get("verb").cloned().unwrap_or(Value::Null);
            let args: Vec<Value> = request
                .get("args")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            let mut detail = s("");
            if verb == s("dispatch") {
                if let Some(first) = args.first() {
                    if let Some(cmd) = first.get("cmd").and_then(|v| v.as_array()) {
                        detail = arr(command_skeleton(cmd)
                            .into_iter()
                            .map(|seg| arr(seg.into_iter().map(|t| s(&t)).collect()))
                            .collect());
                    }
                }
            } else if verb == s("write") {
                if let Some(target) = args.first().and_then(|v| v.as_str()) {
                    let base = basename_of(target);
                    detail = s(match base.rfind('.') {
                        Some(idx) => &base[idx..],
                        None => "",
                    });
                }
            } else if verb == s("send") {
                if let Some(channel) = args.first().and_then(|v| v.as_str()) {
                    detail = s(&send_host(channel));
                }
            }
            components.push(arr(vec![verb, detail]));
        }
    }
    arr(components)
}
