//! Sense computation (spec section 11.3) — a port of the
//! senses section of `conformance/ts/kernel.ts`, which ports
//! `src/jacquard/senses.py`. Method strings are copied verbatim:
//! they are part of the published reading and of the golden
//! vectors.

use crate::core::FoldedState;
use crate::kernel::outputs_and_uses;
use crate::value::{arr, obj, py_eq, s, sort_strings, Value};
use std::collections::BTreeSet;

pub const DRIFT_WINDOW: i64 = 25;

pub fn exclusive_seats() -> BTreeSet<&'static str> {
    ["zcode", "mcode", "claude-code", "gpu", "stage", "kimi", "box"]
        .into_iter()
        .collect()
}

const CONTENTION_METHOD: &str = "contention sense: read set = committed units with prefix booking/<box>/ (the subject's box); a committed booking contends iff ALL of: status is \"active\" only (done, cancelled, preempted and expired bookings are inert); its id differs from the candidate's id (a booking never contends with itself -- a committed row whose id equals the candidate's id is excluded even when its producer differs); its producer differs from the candidate's producer (a same-producer overlap is a renewal, not contention); its checkby is null or >= the candidate start (a booking whose check-by passed before the candidate starts is dead by the board protocol); seat rules -- equal seats contend iff the seat is in {zcode, mcode, claude-code, gpu, stage, kimi, box}, \"box\" contends with every seat, other distinct seats do not contend; and strict interval overlap candidate.start < other.end and other.start < candidate.end (touching endpoints do not contend). Value reports every contender sorted by id, their count, the maximum contender rank (-1 when none), the highest-rank contender's id (ties: smallest id, null when none), and \"unclassified\": the sorted seat strings -- the candidate's seat and the seats of status-\"active\" rows under the prefix -- that are in neither the exclusive set nor {\"detached\"}. Rank otherwise plays no part in contention itself.";

const AUTHORITY_METHOD: &str = "authority sense: read set = log entries passing three filters -- entry kind is \"execution\", the entry body's producer is \"operator\", and the entry's applied writes include a write to unit authority/<producer>. Among those writes the LATEST wins: its value (an integer) is the ceiling, so a later lower grant is a downward revocation; grants is the count of such writes. Only operator-authored writes count: a producer's own write to authority/<self> may land in units under policy/1 but fails the producer filter, so it is visible in the log and inert here. The unit's current value alone is not evidence of a grant. No operator grant -> ceiling null, grants 0.";

pub struct SenseReading {
    pub value: Value,
    pub method: String,
    pub as_of_seq: i64,
}

impl SenseReading {
    pub fn to_value(&self) -> Value {
        obj(vec![
            ("value", self.value.clone()),
            ("method", s(&self.method)),
            ("as_of_seq", Value::Int(self.as_of_seq)),
        ])
    }
}

fn seats_conflict(candidate: &Value, other: &Value) -> bool {
    if py_eq(candidate, other) {
        return match candidate {
            Value::Str(seat) => exclusive_seats().contains(seat.as_str()),
            _ => false,
        };
    }
    if candidate == &s("box") || other == &s("box") {
        return true;
    }
    false
}

fn contention(state: &FoldedState, subject: &str) -> Result<(Value, String), String> {
    let all: Vec<&str> = subject.split('/').collect();
    if all.len() < 6 {
        return Err(format!(
            "contention subject must be <box>/<seat>/<start>/<end>/<producer>/<id>: '{}'",
            subject
        ));
    }
    let n = all.len();
    let (seat, start_s, end_s, producer, cand_id) =
        (all[n - 5], all[n - 4], all[n - 3], all[n - 2], all[n - 1]);
    let bx = all[..n - 5].join("/");
    let parse_int = |t: &str| -> Option<i64> {
        // The subject grammar carries integer minutes (Python
        // int() on the field; the TS port's ^[+-]?\d+$ gate).
        let body = t.strip_prefix(['+', '-']).unwrap_or(t);
        if body.is_empty() || !body.chars().all(|c| c.is_ascii_digit()) {
            None
        } else {
            t.parse::<i64>().ok()
        }
    };
    let (cand_start, cand_end) = match (parse_int(start_s), parse_int(end_s)) {
        (Some(a), Some(b)) => (a, b),
        _ => {
            return Err(format!(
                "contention subject start/end must be integer minutes: '{}'",
                subject
            ))
        }
    };
    let prefix = format!("booking/{}/", bx);
    let mut contenders: Vec<Value> = Vec::new();
    let mut seats_seen: Vec<String> = vec![seat.to_string()];
    for unit in sort_strings(&state.units.keys()) {
        if !unit.starts_with(&prefix) {
            continue;
        }
        let other = state.units.get(&unit).unwrap();
        if !other.is_object() {
            continue;
        }
        if other.get("status") != Some(&s("active")) {
            continue;
        }
        if let Some(seat_v) = other.get("seat").and_then(|v| v.as_str()) {
            if !seats_seen.contains(&seat_v.to_string()) {
                seats_seen.push(seat_v.to_string());
            }
        }
        if py_eq(other.get("id").unwrap_or(&Value::Null), &s(cand_id)) {
            continue;
        }
        if other.get("producer") == Some(&s(producer)) {
            continue;
        }
        match other.get("checkby") {
            None | Some(Value::Null) => {}
            Some(Value::Int(cb)) if *cb < cand_start => continue,
            Some(_) => {}
        }
        let empty = Value::Null;
        let other_seat = other.get("seat").unwrap_or(&empty);
        if !seats_conflict(&s(seat), other_seat) {
            continue;
        }
        let (o_start, o_end) = (
            other.get("start").and_then(|v| v.as_int()).unwrap_or(0),
            other.get("end").and_then(|v| v.as_int()).unwrap_or(0),
        );
        if !(cand_start < o_end && o_start < cand_end) {
            continue;
        }
        contenders.push(obj(vec![
            ("id", other.get("id").cloned().unwrap_or(Value::Null)),
            ("producer", other.get("producer").cloned().unwrap_or(Value::Null)),
            ("seat", other.get("seat").cloned().unwrap_or(Value::Null)),
            ("start", other.get("start").cloned().unwrap_or(Value::Null)),
            ("end", other.get("end").cloned().unwrap_or(Value::Null)),
            ("rank", other.get("rank").cloned().unwrap_or(Value::Int(0))),
        ]));
    }
    contenders.sort_by(|a, b| {
        crate::value::compare_code_points(
            a.get("id").and_then(|v| v.as_str()).unwrap_or(""),
            b.get("id").and_then(|v| v.as_str()).unwrap_or(""),
        )
    });
    let (max_rank, top_id) = if contenders.is_empty() {
        (-1, Value::Null)
    } else {
        let max_rank = contenders
            .iter()
            .map(|c| c.get("rank").and_then(|v| v.as_int()).unwrap_or(0))
            .max()
            .unwrap();
        let mut top: Vec<String> = contenders
            .iter()
            .filter(|c| c.get("rank").and_then(|v| v.as_int()).unwrap_or(0) == max_rank)
            .map(|c| c.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string())
            .collect();
        top = sort_strings(&top);
        (max_rank, s(&top[0]))
    };
    let exclusive = exclusive_seats();
    let unclassified = sort_strings(
        &seats_seen
            .into_iter()
            .filter(|seat| !exclusive.contains(seat.as_str()) && seat != "detached")
            .collect::<Vec<_>>(),
    );
    let count = contenders.len() as i64;
    Ok((
        obj(vec![
            ("contenders", arr(contenders)),
            ("count", Value::Int(count)),
            ("max_rank", Value::Int(max_rank)),
            ("top_id", top_id),
            (
                "unclassified",
                arr(unclassified.into_iter().map(|x| s(&x)).collect()),
            ),
        ]),
        CONTENTION_METHOD.to_string(),
    ))
}

fn authority(entries: &[Value], subject: &str) -> (Value, String) {
    let unit = format!("authority/{}", subject);
    let mut ceiling = Value::Null;
    let mut grants: i64 = 0;
    for entry in entries {
        if entry.get("kind") != Some(&s("execution")) {
            continue;
        }
        let body = match entry.get("body") {
            Some(b) => b,
            None => continue,
        };
        if body.get("producer") != Some(&s("operator")) {
            continue;
        }
        if let Some(applied) = body.get("applied").and_then(|v| v.as_array()) {
            for item in applied {
                if item.get("verb") == Some(&s("write")) {
                    if let Some(args) = item.get("args").and_then(|v| v.as_array()) {
                        if args.first() == Some(&s(&unit)) {
                            ceiling = args.get(1).cloned().unwrap_or(Value::Null);
                            grants += 1;
                        }
                    }
                }
            }
        }
    }
    (
        obj(vec![("ceiling", ceiling), ("grants", Value::Int(grants))]),
        AUTHORITY_METHOD.to_string(),
    )
}

/// Compute a sense reading. `name` may carry a `:subject` suffix.
/// Mirrors kernel.ts's computeSense with no live runtime (the
/// starvation sense reports its no-runtime reading, exactly as
/// the TS checker invokes it).
pub fn compute_sense(
    name: &str,
    entries: &[Value],
    state: &FoldedState,
) -> Result<SenseReading, String> {
    let (base, subject) = match name.find(':') {
        Some(idx) => {
            let subj = &name[idx + 1..];
            (&name[..idx], if subj.is_empty() { None } else { Some(subj) })
        }
        None => (name, None),
    };
    let (value, method) = match base {
        "queue-depth" => (
            Value::Int(state.decision_queue.keys().len() as i64),
            "count of folded decision_queue entries".to_string(),
        ),
        "output-use" => {
            let subject = subject.ok_or("output-use sense needs a producer subject")?;
            let (outputs, used) = outputs_and_uses(entries, subject);
            let ratio_bp = if outputs != 0 { (10000 * used) / outputs } else { 0 };
            (
                obj(vec![
                    ("producer", s(subject)),
                    ("outputs", Value::Int(outputs)),
                    ("used", Value::Int(used)),
                    ("ratio_bp", Value::Int(ratio_bp)),
                ]),
                "records projection: outputs listed on executed proposals vs outputs named in later proposals' uses".to_string(),
            )
        }
        "starvation" => (
            obj(vec![("status", s("no-runtime"))]),
            "starvation evidence needs a live scheduler's counters; none was supplied at publish time".to_string(),
        ),
        "calibration-drift" => {
            let mut outcomes: Vec<String> = Vec::new();
            for e in entries {
                if e.get("kind") == Some(&s("decision")) {
                    if let Some(body) = e.get("body") {
                        match body.get("outcome").and_then(|v| v.as_str()) {
                            Some("allow") => outcomes.push("allow".to_string()),
                            Some("deny") => outcomes.push("deny".to_string()),
                            _ => {}
                        }
                    }
                }
            }
            let w = DRIFT_WINDOW as usize;
            if outcomes.len() < 2 * w {
                (
                    obj(vec![
                        ("status", s("insufficient-data")),
                        ("decisions", Value::Int(outcomes.len() as i64)),
                    ]),
                    format!("stub: needs {} decisions for two windows", 2 * DRIFT_WINDOW),
                )
            } else {
                let allow_bp = |window: &[String]| -> i64 {
                    (10000 * window.iter().filter(|o| *o == "allow").count() as i64)
                        / window.len() as i64
                };
                let baseline = &outcomes[..w];
                let recent = &outcomes[outcomes.len() - w..];
                let (b, r) = (allow_bp(baseline), allow_bp(recent));
                (
                    obj(vec![
                        ("status", s("stub")),
                        ("drift_bp", Value::Int((r - b).abs())),
                        ("baseline_allow_bp", Value::Int(b)),
                        ("recent_allow_bp", Value::Int(r)),
                        ("window", Value::Int(DRIFT_WINDOW)),
                    ]),
                    format!("stub: kernel-wide allow-rate drift between the first and last {} decisions; per-rule calibration arrives with the learner", DRIFT_WINDOW),
                )
            }
        }
        "contention" => {
            let subject = subject.ok_or("contention sense needs a subject")?;
            contention(state, subject)?
        }
        "authority" => {
            let subject = subject.ok_or("authority sense needs a producer subject")?;
            authority(entries, subject)
        }
        _ => return Err(format!("unknown sense: {}", name)),
    };
    Ok(SenseReading {
        value,
        method,
        as_of_seq: entries.last().and_then(|e| e.get("seq")).and_then(|v| v.as_int()).unwrap_or(-1),
    })
}
