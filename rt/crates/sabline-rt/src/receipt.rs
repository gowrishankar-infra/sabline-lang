//! `sabline.receipt/1`: what one run did, as an in-toto Statement - what
//! `sabline/recorder.py` records while a program runs and
//! `sabline/receipts.py` makes of it afterwards (9.0, M3).
//!
//! A receipt holds no value the program handled. A refusal is its code,
//! its effect and its line; a declassification is the reason written in the
//! source and, for an HMAC, the fingerprint of its key; the output, the
//! input, the arguments and every message are left out. Each refusal and
//! each declassification is kept once per place, with a count, so a loop
//! that declassifies a million times is one entry.
//!
//! **The audit stream** (decisions/0007, 32b) is the receipt's fields as
//! they are produced, one JSON object an event: `start`, `subjects`, then
//! as each happens `effect`, `grant`, `refusal` and `declassify`, and `end`
//! with the receipt - `sabline/recorder.py`'s `tell`, and docs/receipts.md.
//!
//! The run document (`run_dump`) writes one after each run, and
//! `check_agreement.py` compares it with the Python package's field for
//! field, after normalising exactly plan/9.0.md's list: the producer's name
//! and version, `startedAt`, `wall_time_ms`, a `<source>` subject's name,
//! and the confinement fields, which are compared by rule.

use std::collections::{HashMap, HashSet};

use crate::digest;
use crate::json::Json;
use crate::pypath::{self, os_path, posix};
use crate::tables::ALL_EFFECTS;
use crate::text::Text;

/// `RECEIPT_SCHEMA`.
pub const RECEIPT_SCHEMA: &str = "sabline.receipt/1";
/// `RECEIPT_SPEC`: the sabline-spec version whose receipt this is.
pub const RECEIPT_SPEC: &str = "sabline-spec 0.13.0";
/// `RECEIPT_PREDICATE_TYPE`.
pub const RECEIPT_PREDICATE_TYPE: &str = "https://sabline.dev/receipt/v1";
/// `INTOTO_STATEMENT_TYPE`.
pub const INTOTO_STATEMENT_TYPE: &str = "https://in-toto.io/Statement/v1";
/// `AUDIT_STREAM_SCHEMA`.
pub const AUDIT_STREAM_SCHEMA: &str = "sabline.audit-stream/1";
/// `findings.REPOSITORY`: where the producer is.
pub const REPOSITORY: &str = "https://github.com/gowrishankar-infra/sabline-lang";
/// The producer's name, which is the one thing a receipt is supposed to
/// say differently from the Python package's `sabline-lang`.
pub const PRODUCER: &str = "sabline-rt";

/// `REFUSAL_CODES`: the refusals a receipt lists - the budget's, and the
/// read ceiling's.
pub const REFUSAL_CODES: [&str; 12] = [
    "E310", "E311", "E313", "E314", "E315", "E316", "E317", "E318", "E320", "E321", "E322",
    "E323",
];

/// `tables.HMAC_REASON`: the reason an HMAC's declassification is recorded
/// with, which nothing else has.
pub const HMAC_REASON: &str = "hmac signature";

/// `runtime.FINGERPRINTS_PER_SITE`: how many keys one call site may name in
/// a receipt before it says "many".
pub const FINGERPRINTS_PER_SITE: usize = 16;

/// What a site is about, beside its line.
#[derive(Debug, Clone, PartialEq, Eq)]
enum Kind {
    Refusal { code: Option<&'static str>, effect: Option<String>, stopped: bool },
    Declassify { reason: Text, key_fingerprint: Option<String> },
}

#[derive(Debug, Clone)]
struct Site {
    kind: Kind,
    line: u32,
    times: u64,
}

/// `_RunRecorder`: what a receipt records about one run, while it happens.
#[derive(Debug, Clone, Default)]
pub struct Recorder {
    sites: Vec<Site>,
    /// The code and line the run stopped at: `recorder.stop`.
    pub stop: Option<(&'static str, u32)>,
    /// Whether the program passed its checks and began to run.
    pub compiled: bool,
    /// line -> the key fingerprints an HMAC call there has named.
    keys_at: HashMap<u32, HashSet<String>>,
    /// The audit stream's events so far, when one was asked for.
    pub stream: Option<Vec<Json>>,
}

impl Recorder {
    /// A recorder that keeps the audit stream as well.
    pub fn streaming() -> Recorder {
        Recorder { stream: Some(Vec::new()), ..Recorder::default() }
    }

    /// `tell(event)`: one event of the audit stream, when one was asked for.
    pub fn tell(&mut self, event: Json) {
        if let Some(stream) = &mut self.stream {
            stream.push(event);
        }
    }

    /// `set_subjects(subjects)`, as far as the stream is concerned.
    pub fn tell_subjects(&mut self, subjects: &[Json]) {
        self.tell(Json::obj([
            ("event", Json::text("subjects")),
            ("subject", Json::List(subjects.to_vec())),
        ]));
    }

    /// A builtin call the budget let through.
    pub fn effect(&mut self, effect: &str, builtin: &str, line: u32) {
        if self.stream.is_some() {
            self.tell(Json::obj([
                ("event", Json::text("effect")),
                ("effect", Json::text(effect)),
                ("builtin", Json::text(builtin)),
                ("line", Json::Int(i64::from(line))),
            ]));
        }
    }

    /// An operation a grant let through, by the grant's own text.
    pub fn grant(&mut self, grant: &str) {
        if self.stream.is_some() {
            self.tell(Json::obj([
                ("event", Json::text("grant")),
                ("grant", Json::text(grant)),
            ]));
        }
    }

    /// `note(kind, **fields)`: one more of this, at this place - and, in the
    /// stream, this one.
    fn note(&mut self, kind: Kind, line: u32) {
        if self.stream.is_some() {
            let event = event_of(&kind, line);
            self.tell(event);
        }
        match self.sites.iter_mut().find(|s| s.kind == kind && s.line == line) {
            Some(site) => site.times += 1,
            None => self.sites.push(Site { kind, line, times: 1 }),
        }
    }

    /// `declassify` ran here, with this reason.
    pub fn note_declassify(&mut self, reason: Text, line: u32) {
        self.note(Kind::Declassify { reason, key_fingerprint: None }, line);
    }

    /// An HMAC signed here under this key: named by its fingerprint, and
    /// as "many" once the site has named `FINGERPRINTS_PER_SITE` others.
    pub fn note_hmac(&mut self, key: &[u8], line: u32) {
        let seen = self.keys_at.entry(line).or_default();
        let mut print = key_fingerprint(key);
        if !seen.contains(&print) && seen.len() >= FINGERPRINTS_PER_SITE {
            print = "many".to_string();
        } else {
            seen.insert(print.clone());
        }
        self.note(
            Kind::Declassify { reason: Text::from(HMAC_REASON), key_fingerprint: Some(print) },
            line,
        );
    }

    /// `_note_error(e)`: an error stopped the run, here; a refusal among
    /// them is listed, with the effect it is about.
    pub fn note_error(&mut self, code: &'static str, line: u32, message: &str) {
        self.stop = Some((code, line));
        if REFUSAL_CODES.contains(&code) {
            let effect = refusal_effect(code, message);
            self.note(Kind::Refusal { code: Some(code), effect, stopped: true }, line);
        }
    }

    /// `_note_stop(code, line)`: the run stopped here, before it ran.
    pub fn note_stop(&mut self, code: &'static str, line: u32) {
        self.stop = Some((code, line));
    }
}

/// What the stream says of one refusal or declassification: what the
/// receipt keeps of it, without the count.
fn event_of(kind: &Kind, line: u32) -> Json {
    let line = Json::Int(i64::from(line));
    match kind {
        Kind::Refusal { code, effect, stopped } => Json::obj([
            ("event", Json::text("refusal")),
            ("code", code.map_or(Json::Null, Json::text)),
            ("effect", effect.clone().map_or(Json::Null, Json::Str)),
            ("line", line),
            ("stopped", Json::Bool(*stopped)),
        ]),
        Kind::Declassify { reason, key_fingerprint } => {
            let mut fields = vec![
                ("event".to_string(), Json::text("declassify")),
                ("reason".to_string(), Json::Text(reason.clone())),
                ("line".to_string(), line),
            ];
            if let Some(print) = key_fingerprint {
                fields.push(("key_fingerprint".to_string(), Json::Str(print.clone())));
            }
            Json::Obj(fields.into_iter().collect())
        }
    }
}

/// The run parameters a receipt says and the stream's `start` says, but for
/// the confinement, which is not known before the run.
fn parameters(run: &Run<'_>) -> Option<Vec<(&'static str, Json)>> {
    let freeze_time = match run.freeze_time {
        Some(t) => Json::Str(instant(t)?),
        None => Json::Null,
    };
    Some(vec![
        ("seed", run.seed.map_or(Json::Null, |s| Json::Num(s.to_string()))),
        ("freeze_time", freeze_time),
        ("timeout", Json::Null),
        ("max_memory_mb", Json::Null),
        ("max_read_bytes", Json::Int(i64::try_from(run.max_read).unwrap_or(i64::MAX))),
    ])
}

fn producer() -> Json {
    Json::obj([
        ("name", Json::text(PRODUCER)),
        ("uri", Json::text(REPOSITORY)),
        ("version", Json::text(crate::VERSION)),
    ])
}

/// `stream_start`: the audit stream's first event - what the run was given,
/// before it ran. `false` for a frozen clock past what an instant can say,
/// which has neither a stream nor a receipt.
pub fn stream_start(recorder: &mut Recorder, run: &Run<'_>) -> bool {
    let Some(given) = parameters(run) else { return false };
    recorder.tell(Json::obj([
        ("event", Json::text("start")),
        ("schema", Json::text(AUDIT_STREAM_SCHEMA)),
        ("producer", producer()),
        ("startedAt", Json::text(run.started_at.clone())),
        ("budget", Json::text(run.budget.clone())),
        (
            "run_parameters",
            Json::Obj(given.into_iter().map(|(k, v)| (k.to_string(), v)).collect()),
        ),
    ]));
    true
}

/// `stream_end`: the audit stream's last event, the receipt.
pub fn stream_end(recorder: &mut Recorder, receipt: &Json) {
    recorder.tell(Json::obj([("event", Json::text("end")), ("receipt", receipt.clone())]));
}

/// `key_fingerprint(key)`: twelve hex digits of a SHA-256 over a fixed label
/// and the key.
pub fn key_fingerprint(key: &[u8]) -> String {
    let mut labelled = b"sabline key fingerprint\0".to_vec();
    labelled.extend_from_slice(key);
    digest::hex(&digest::sha256(&labelled))[..12].to_string()
}

/// `_refusal_effect(code, message)`: the effect a refusal is about, as one
/// of the effect names - never the path, host or module the program gave.
fn refusal_effect(code: &str, message: &str) -> Option<String> {
    match code {
        // re.search(r"needs the '(\w+)' effect", message)
        "E310" => {
            let mut at = 0;
            while let Some(found) = message[at..].find("needs the '") {
                let start = at + found + "needs the '".len();
                let word: String = message[start..]
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '_')
                    .collect();
                if !word.is_empty() && message[start + word.len()..].starts_with("' effect") {
                    return ALL_EFFECTS.contains(&word.as_str()).then_some(word);
                }
                at = start;
            }
            None
        }
        // re.search(r" (fs|net) operation", message)
        "E315" => {
            let fs = message.find(" fs operation");
            let net = message.find(" net operation");
            match (fs, net) {
                (Some(f), Some(n)) => Some(if f < n { "fs" } else { "net" }.to_string()),
                (Some(_), None) => Some("fs".to_string()),
                (None, Some(_)) => Some("net".to_string()),
                (None, None) => None,
            }
        }
        "E311" => Some("ffi".to_string()),
        "E313" | "E316" | "E318" => Some("fs".to_string()),
        "E314" | "E317" => Some("net".to_string()),
        "E320" | "E321" | "E322" | "E323" => Some("tool".to_string()),
        _ => None,
    }
}

/// `_subject_name(path, entry, entry_name)`: how a Statement names a file
/// the program loads - in the terms the program was named in, or
/// `<stdlib>/NAME` for the standard library this runtime ships.
fn subject_name(path: &str, entry: &str, entry_name: &str, install_dir: &str) -> String {
    let full = pypath::abspath(path);
    let base = os_path::dirname(&pypath::abspath(entry));
    let std = os_path::join(&pypath::abspath(install_dir), "stdlib");
    let rel = pypath::relpath(&full, &base).map(|r| r.replace(pypath::SEP, "/"));
    let beside = |rel: &str| posix::normpath(&posix::join(&posix::dirname(entry_name), rel));
    if let Some(rel) = &rel {
        if rel != ".." && !rel.starts_with("../") {
            return beside(rel);
        }
    }
    if full.starts_with(&format!("{std}{}", pypath::SEP)) {
        let inside = pypath::relpath(&full, &std).unwrap_or_default();
        return format!("<stdlib>/{}", inside.replace(pypath::SEP, "/"));
    }
    match rel {
        Some(rel) => beside(&rel),
        None => full.replace(pypath::SEP, "/"),
    }
}

fn digested(name: String, bytes: &[u8]) -> Json {
    Json::obj([
        ("name", Json::Str(name)),
        ("digest", Json::obj([("sha256", Json::Str(digest::hex(&digest::sha256(bytes))))])),
    ])
}

/// `_receipt_subjects(entry, name, entry_bytes, loaded)`: the program, by
/// the sha256 of the text that ran, then each other file it read, by the
/// sha256 of its bytes now, named as `subject_name` says. A file that can
/// no longer be read is left out.
pub fn subjects(
    entry: &str,
    name: &str,
    entry_bytes: &[u8],
    loaded: &[String],
    install_dir: &str,
) -> Vec<Json> {
    let mut out = vec![digested(name.to_string(), entry_bytes)];
    let mut seen: HashSet<String> = HashSet::from([pypath::abspath(entry)]);
    for p in loaded {
        if !seen.insert(pypath::abspath(p)) {
            continue;
        }
        let Ok(bytes) = std::fs::read(p) else { continue };
        out.push(digested(subject_name(p, entry, name, install_dir), &bytes));
    }
    out
}

/// `posixpath.normpath(path.replace(os.sep, "/"))`: how a receipt names
/// the program it ran.
pub fn entry_name(path: &str) -> String {
    posix::normpath(&path.replace(pypath::SEP, "/"))
}

/// Epoch seconds as a UTC calendar date and time, (year, month, day, hour,
/// minute, second), as `datetime(1970, 1, 1) + timedelta(seconds=t)` gives
/// it: `None` outside the years 1 to 9999, where that overflows.
fn utc(t: i64) -> Option<(i64, i64, i64, i64, i64, i64)> {
    let (days, secs) = (t.div_euclid(86400), t.rem_euclid(86400));
    // days since 1970-01-01 to a civil date (the proleptic Gregorian
    // calendar CPython's datetime uses)
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    (1..=9999).contains(&year).then_some((
        year,
        month,
        day,
        secs / 3600,
        secs % 3600 / 60,
        secs % 60,
    ))
}

/// A frozen clock as a receipt's `run_parameters` say it, `receipts._instant`:
/// RFC 3339 in UTC to the second, a four-digit year, or `None` outside the
/// years 1 to 9999, where the reference raises `ValueError`.
pub fn instant(t: i64) -> Option<String> {
    let (y, mo, d, h, mi, s) = utc(t)?;
    Some(format!("{y:04}-{mo:02}-{d:02}T{h:02}:{mi:02}:{s:02}Z"))
}

/// `_utc_now_ms()`: now, to the millisecond, as `startedAt` says it.
pub fn utc_now_ms() -> String {
    let now =
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default();
    let secs = i64::try_from(now.as_secs()).unwrap_or(0);
    let (y, mo, d, h, mi, s) = utc(secs).unwrap_or((1970, 1, 1, 0, 0, 0));
    format!("{y:04}-{mo:02}-{d:02}T{h:02}:{mi:02}:{s:02}.{:03}Z", now.subsec_millis())
}

/// How a run ended, as a receipt's `exit` is made from it.
#[derive(Debug, Clone, Copy, Default)]
pub struct Ending {
    /// The exit status, or `None` when a limit stopped the run.
    pub status: Option<i64>,
    /// The step limit stopped it: recorded as a timeout.
    pub timed_out: bool,
    /// The size limit stopped it: recorded as out of memory.
    pub out_of_memory: bool,
}

/// What the receipt says of a run besides what the recorder kept.
#[derive(Debug)]
pub struct Run<'a> {
    /// The program's name, `entry_name(path)`.
    pub name: &'a str,
    /// `subjects(...)`.
    pub subjects: Vec<Json>,
    /// The budget's `spec()`.
    pub budget: String,
    /// `--seed`.
    pub seed: Option<i128>,
    /// `--freeze-time`, as epoch seconds.
    pub freeze_time: Option<i64>,
    /// The read ceiling, in bytes.
    pub max_read: u64,
    /// How many builtin calls each effect let through.
    pub effect_uses: &'a HashMap<String, u64>,
    /// What each grant let through, by its text.
    pub grant_uses: &'a [(String, u64)],
    /// When it started, `utc_now_ms()`.
    pub started_at: String,
    /// How long it took.
    pub wall_time_ms: f64,
    /// How it ended.
    pub ending: Ending,
}

fn none_or(s: Option<&str>) -> String {
    s.unwrap_or("None").to_string()
}

/// `receipt_statement(recorder, ...)` of a run nothing was asked of the
/// operating system for, which is the run document's (`run_dump`'s
/// docstring in the Python package says why): `None` for a frozen clock
/// past what an instant can say, which has no receipt.
pub fn statement(recorder: &Recorder, run: &Run<'_>) -> Option<Json> {
    let mut given = parameters(run)?;
    let mut refusals: Vec<(u32, String, String, bool, Json)> = Vec::new();
    let mut declassifications: Vec<(u32, Text, String, Json)> = Vec::new();
    for site in &recorder.sites {
        let line = Json::Int(i64::from(site.line));
        let times = Json::Int(i64::try_from(site.times).unwrap_or(i64::MAX));
        match &site.kind {
            Kind::Refusal { code, effect, stopped } => refusals.push((
                site.line,
                none_or(*code),
                none_or(effect.as_deref()),
                *stopped,
                Json::obj([
                    ("code", code.map_or(Json::Null, Json::text)),
                    ("effect", effect.clone().map_or(Json::Null, Json::Str)),
                    ("line", line),
                    ("stopped", Json::Bool(*stopped)),
                    ("times", times),
                ]),
            )),
            Kind::Declassify { reason, key_fingerprint } => {
                let mut entry = vec![
                    ("reason".to_string(), Json::Text(reason.clone())),
                    ("line".to_string(), line),
                    ("times".to_string(), times),
                ];
                if let Some(print) = key_fingerprint {
                    entry.push(("key_fingerprint".to_string(), Json::Str(print.clone())));
                }
                declassifications.push((
                    site.line,
                    reason.clone(),
                    key_fingerprint.clone().unwrap_or_default(),
                    Json::Obj(entry.into_iter().collect()),
                ));
            }
        }
    }
    refusals.sort_by(|a, b| (a.0, &a.1, &a.2, a.3).cmp(&(b.0, &b.1, &b.2, b.3)));
    declassifications.sort_by(|a, b| (a.0, &a.1, &a.2).cmp(&(b.0, &b.1, &b.2)));
    let refused = refusals.iter().any(|r| r.3);

    let ending = run.ending;
    let (outcome, code) = if ending.timed_out {
        ("timeout", Some("E610"))
    } else if ending.out_of_memory {
        ("out_of_memory", Some("E611"))
    } else {
        let stop = recorder.stop.map(|(code, _)| code);
        let ok = ending.status == Some(0) && stop.is_none();
        let outcome = if refused {
            "refused"
        } else if ok {
            "ok"
        } else if !recorder.compiled && stop.is_some() {
            "did_not_compile"
        } else {
            "failed"
        };
        (outcome, stop)
    };

    let mut grants: Vec<&(String, u64)> = run.grant_uses.iter().collect();
    grants.sort();
    let count = |n: u64| Json::Int(i64::try_from(n).unwrap_or(i64::MAX));
    Some(Json::obj([
        ("_type", Json::text(INTOTO_STATEMENT_TYPE)),
        ("subject", Json::List(run.subjects.clone())),
        ("predicateType", Json::text(RECEIPT_PREDICATE_TYPE)),
        (
            "predicate",
            Json::obj([
                ("schema", Json::text(RECEIPT_SCHEMA)),
                ("producer", producer()),
                ("specification", Json::text(RECEIPT_SPEC)),
                ("startedAt", Json::text(run.started_at.clone())),
                ("wall_time_ms", Json::Num(format!("{:.1}", run.wall_time_ms))),
                ("budget", Json::text(run.budget.clone())),
                ("run_parameters", {
                    // nothing was asked of the operating system:
                    // `_confinement_fields({})`
                    given.extend([
                        ("confinement", Json::text("none")),
                        (
                            "confinement_reason",
                            Json::text("nothing was asked of the operating system"),
                        ),
                        ("confinement_layers", Json::List(Vec::new())),
                        ("os_policy_sha256", Json::Null),
                    ]);
                    Json::Obj(given.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
                }),
                (
                    "effects_used",
                    Json::Obj(
                        run.effect_uses.iter().map(|(e, n)| (e.clone(), count(*n))).collect(),
                    ),
                ),
                (
                    "grants_used",
                    Json::List(
                        grants
                            .into_iter()
                            .map(|(g, n)| {
                                Json::obj([
                                    ("grant", Json::text(g.clone())),
                                    ("times", count(*n)),
                                ])
                            })
                            .collect(),
                    ),
                ),
                ("refusals", Json::List(refusals.into_iter().map(|r| r.4).collect())),
                (
                    "declassifications",
                    Json::List(declassifications.into_iter().map(|d| d.3).collect()),
                ),
                (
                    "exit",
                    Json::obj([
                        ("status", ending.status.map_or(Json::Null, Json::Int)),
                        ("outcome", Json::text(outcome)),
                        ("code", code.map_or(Json::Null, Json::text)),
                    ]),
                ),
                ("complete", Json::Bool(true)),
            ]),
        ),
    ]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_instant_is_the_reference_s() {
        // receipts._instant(t), on every platform
        assert_eq!(instant(0).as_deref(), Some("1970-01-01T00:00:00Z"));
        assert_eq!(instant(-1).as_deref(), Some("1969-12-31T23:59:59Z"));
        assert_eq!(instant(1_767_225_600).as_deref(), Some("2026-01-01T00:00:00Z"));
        assert_eq!(instant(951_782_400).as_deref(), Some("2000-02-29T00:00:00Z"));
        assert_eq!(instant(32_536_850_399).as_deref(), Some("3001-01-19T21:59:59Z"));
        assert_eq!(instant(-43_201).as_deref(), Some("1969-12-31T11:59:59Z"));
        assert_eq!(instant(253_402_300_799).as_deref(), Some("9999-12-31T23:59:59Z"));
        assert_eq!(instant(-62_135_596_800).as_deref(), Some("0001-01-01T00:00:00Z"));
        assert_eq!(instant(253_402_300_800), None);
        assert_eq!(instant(-62_135_596_801), None);
    }

    #[test]
    fn a_key_s_fingerprint_is_the_reference_s() {
        // runtime.key_fingerprint(b"key")
        assert_eq!(key_fingerprint(b"key"), "7b266fd765cf");
    }

    #[test]
    fn a_refusal_names_its_effect_and_nothing_else() {
        let e310 = "'read_file' needs the 'fs' effect, which this run does not allow";
        assert_eq!(refusal_effect("E310", e310).as_deref(), Some("fs"));
        assert_eq!(refusal_effect("E310", "needs the 'wifi' effect"), None);
        assert_eq!(
            refusal_effect("E315", "this run allows 2 fs operation(s)").as_deref(),
            Some("fs")
        );
        assert_eq!(refusal_effect("E313", "anything").as_deref(), Some("fs"));
        assert_eq!(refusal_effect("E600", "anything"), None);
    }

    #[test]
    fn the_stream_says_each_occurrence_in_order_and_only_when_asked() {
        let mut quiet = Recorder::default();
        quiet.effect("io", "print", 1);
        quiet.note_declassify(Text::from("why"), 2);
        assert!(quiet.stream.is_none());
        let mut r = Recorder::streaming();
        r.effect("declassify", "declassify", 2);
        r.note_declassify(Text::from("why"), 2);
        r.note_declassify(Text::from("why"), 2);
        r.grant("fs:read:/d");
        r.note_error("E313", 9, "anything");
        let said: Vec<String> =
            r.stream.as_ref().unwrap().iter().map(Json::canonical).collect();
        assert_eq!(
            said,
            [
                r#"{"builtin":"declassify","effect":"declassify","event":"effect","line":2}"#,
                r#"{"event":"declassify","line":2,"reason":"why"}"#,
                r#"{"event":"declassify","line":2,"reason":"why"}"#,
                r#"{"event":"grant","grant":"fs:read:/d"}"#,
                r#"{"code":"E313","effect":"fs","event":"refusal","line":9,"stopped":true}"#,
            ]
        );
        // and the receipt keeps the two as one place, counted twice
        assert_eq!(r.sites.iter().map(|s| s.times).collect::<Vec<_>>(), [2, 1]);
    }

    #[test]
    fn a_site_signing_under_many_keys_says_many() {
        let mut r = Recorder::default();
        for k in 0..20u8 {
            r.note_hmac(&[k], 7);
        }
        r.note_hmac(&[0], 7);
        let prints: Vec<String> = r
            .sites
            .iter()
            .filter_map(|s| match &s.kind {
                Kind::Declassify { key_fingerprint: Some(p), .. } => Some(p.clone()),
                _ => None,
            })
            .collect();
        assert_eq!(prints.len(), FINGERPRINTS_PER_SITE + 1);
        assert_eq!(prints.last().map(String::as_str), Some("many"));
        let many = r.sites.iter().find(|s| {
            matches!(&s.kind, Kind::Declassify { key_fingerprint: Some(p), .. } if p == "many")
        });
        assert_eq!(many.map(|s| s.times), Some(4));
    }
}
