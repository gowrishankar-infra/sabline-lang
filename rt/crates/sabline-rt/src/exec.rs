//! `sabline-rt exec`: one program run for whoever started this process -
//! `sabline run` and `sabline.run` when `SABLINE_REFERENCE_RUNTIME` is
//! `rust` (9.0, M3; decisions/0002: the commands stay in Python and the
//! run inside them goes through sabline-rt).
//!
//! **The conversation**, one JSON object a line each way. The first line on
//! standard input is the request:
//!
//! ```text
//! {"path": ..., "allow": ..., "deny": ..., "seed": ..., "freeze_time": ...,
//!  "max_read": ..., "args": [...], "name": ..., "stream": true}
//! ```
//!
//! - `path`: the program; the only field that must be there.
//! - `allow`, `deny`: the budget, as the command line's `--allow` and
//!   `--deny` give it - `null`, or absent, for `io`.
//! - `seed`, `freeze_time`, `max_read`: the run's parameters, as the run
//!   document's lines give them.
//! - `args`: what `args()` answers.
//! - `name`: the name the receipt gives the program - the path as the
//!   command line was given it, or the library's `<source>`.
//! - `stream`: whether the audit stream is wanted.
//! - `source`: the program's text, when the file at `path` - where its
//!   imports resolve from - does not hold it (`sabline.run(source,
//!   path=...)`).
//!
//! Then the run, and on standard output a frame for each thing it does, in
//! the order it does them: `{"out": text}` for what `print` writes and
//! `{"err": text}` for what `log` writes, each with its line feed;
//! `{"read": "line"}` for `read_line` and `{"ask": prompt}` for `ask`, each
//! answered by one line on standard input, `{"line": text}` or
//! `{"line": null}` for the end of the input; `{"event": ...}` for each
//! event of the audit stream, when it was asked for; and last
//! `{"end": {"document": ..., "receipt": ...}}` - the run document, its
//! `stdout` and `stderr` empty since both were sent as they happened, and
//! the receipt.
//!
//! **Why frames and not the program's own standard streams.** What a
//! program prints reaches its user through the Python package's own
//! `sys.stdout`, and what it reads comes from `sys.stdin` - with their
//! encoding, their buffering, their newline translation and `input()`'s
//! way with a terminal - so that a run through sabline-rt writes and reads
//! exactly what the same run in the package does. Texts travel as JSON
//! escapes, so a lone surrogate arrives as one.
//!
//! **A parent that goes away** takes the run with it: standard input ends,
//! which the parent never does on purpose before the end frame, and the
//! process exits ([`ORPHANED`]).
//!
//! Text is read with [`crate::pyjson`], which takes a lone surrogate; the
//! frames are written by [`crate::json`], in ASCII.

use crate::interp::{Frame, RunParams};
use crate::json::Json;
use crate::pyjson;
use crate::run_dump::Given;
use crate::text::Text;
use crate::value::Value;

/// The exit status of a run whose parent went away before it ended.
pub const ORPHANED: u8 = 3;

fn field(fields: &[(Value, Value)], name: &str) -> Option<Value> {
    fields
        .iter()
        .find(|(k, _)| matches!(k, Value::Text(t) if *t == Text::from(name)))
        .map(|(_, v)| v.clone())
        .filter(|v| !matches!(v, Value::None))
}

fn text_field(fields: &[(Value, Value)], name: &str) -> Result<Option<String>, String> {
    match field(fields, name) {
        None => Ok(None),
        Some(Value::Text(t)) => match t.to_str() {
            Some(s) => Ok(Some(s)),
            None => Err(format!("sabline-rt exec: '{name}' holds a lone surrogate")),
        },
        Some(_) => Err(format!("sabline-rt exec: '{name}' is not a text")),
    }
}

fn int_field(fields: &[(Value, Value)], name: &str) -> Result<Option<i128>, String> {
    match field(fields, name) {
        None => Ok(None),
        Some(v) => match v.as_i128() {
            Some(n) if !matches!(v, Value::Bool(_)) => Ok(Some(n)),
            _ => Err(format!("sabline-rt exec: '{name}' is not a whole number")),
        },
    }
}

/// The request: the program's path, and what its run is given.
pub fn request(line: &str) -> Result<(String, Given), String> {
    let doc = pyjson::loads(&Text::from(line.trim_end_matches(['\r', '\n'])))
        .map_err(|e| format!("sabline-rt exec: the request is not JSON: {e}"))?;
    let Value::Map(m) = doc else {
        return Err("sabline-rt exec: the request is not an object".to_string());
    };
    let fields = m.entries();
    let path = text_field(fields, "path")?
        .ok_or_else(|| "sabline-rt exec: the request names no 'path'".to_string())?;
    let freeze_time = match int_field(fields, "freeze_time")? {
        Some(t) => {
            Some(i64::try_from(t).map_err(|_| "sabline-rt exec: 'freeze_time' is too far")?)
        }
        None => None,
    };
    let mut params =
        RunParams { seed: int_field(fields, "seed")?, freeze_time, ..RunParams::default() };
    if let Some(n) = int_field(fields, "max_read")? {
        params.max_read = u64::try_from(n.max(0)).unwrap_or(u64::MAX);
    }
    let args = match field(fields, "args") {
        None => Vec::new(),
        Some(Value::List(xs)) => xs
            .iter()
            .map(|x| match x {
                Value::Text(t) => Ok(t.clone()),
                _ => Err("sabline-rt exec: an argument is not a text".to_string()),
            })
            .collect::<Result<_, _>>()?,
        Some(_) => return Err("sabline-rt exec: 'args' is not a list".to_string()),
    };
    let stream = matches!(field(fields, "stream"), Some(Value::Bool(true)));
    Ok((
        path,
        Given {
            allow: text_field(fields, "allow")?,
            deny: text_field(fields, "deny")?,
            params,
            args: Some(args),
            name: text_field(fields, "name")?,
            relayed: true,
            stream,
            source: text_field(fields, "source")?,
            ..Given::default()
        },
    ))
}

/// An answer to `read_line` or `ask`: the text, or `None` for the end of
/// the input - and for a line that is not an answer, which ends it too.
pub fn answer(line: &str) -> Option<Text> {
    match pyjson::loads(&Text::from(line.trim_end_matches(['\r', '\n']))) {
        Ok(Value::Map(m)) => match field(m.entries(), "line") {
            Some(Value::Text(t)) => Some(t),
            _ => None,
        },
        _ => None,
    }
}

/// One frame, as the line it is written as.
pub fn frame(f: Frame) -> Json {
    match f {
        Frame::Out(t) => Json::obj([("out", Json::Text(t))]),
        Frame::Err(t) => Json::obj([("err", Json::Text(t))]),
        Frame::ReadLine => Json::obj([("read", Json::text("line"))]),
        Frame::Ask(p) => Json::obj([("ask", Json::Text(p))]),
        Frame::Event(e) => Json::obj([("event", e)]),
    }
}

/// The last frame: the run document and the receipt.
pub fn end(document: Json, receipt: Json) -> Json {
    Json::obj([("end", Json::obj([("document", document), ("receipt", receipt)]))])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_request_gives_the_run_what_the_command_line_would() {
        let (path, given) = request(
            r#"{"path": "p.vel", "allow": "io,fs:read:.", "deny": null, "seed": 7,
               "freeze_time": -5, "max_read": 10, "args": ["a", "\ud800"], "name": "<source>",
               "stream": true}"#,
        )
        .unwrap();
        assert_eq!(path, "p.vel");
        assert_eq!(given.allow.as_deref(), Some("io,fs:read:."));
        assert_eq!(given.deny, None);
        assert_eq!(
            (given.params.seed, given.params.freeze_time, given.params.max_read),
            (Some(7), Some(-5), 10)
        );
        assert_eq!(given.args.unwrap()[1], Text::from(vec![0xD800]));
        assert_eq!(given.name.as_deref(), Some("<source>"));
        assert!(given.relayed && given.stream);
        assert!(request(r#"{"allow": "io"}"#).unwrap_err().contains("no 'path'"));
        assert!(request("[1]").unwrap_err().contains("not an object"));
        assert!(request(r#"{"path": "p", "seed": true}"#).is_err());
    }

    #[test]
    fn an_answer_is_a_line_or_the_end() {
        assert_eq!(answer(r#"{"line": "a\r\n"}"#), Some(Text::from("a\r\n")));
        assert_eq!(answer(r#"{"line": "\udc80"}"#), Some(Text::from(vec![0xDC80])));
        assert_eq!(answer(r#"{"line": null}"#), None);
        assert_eq!(answer("not json"), None);
    }

    #[test]
    fn frames_are_ascii_json_lines() {
        let out = frame(Frame::Out(Text::from(vec![0x61, 0xD800, 0x0A]))).canonical();
        assert_eq!(out, r#"{"out":"a\ud800\n"}"#);
        assert_eq!(frame(Frame::ReadLine).canonical(), r#"{"read":"line"}"#);
        assert_eq!(
            end(Json::Null, Json::Null).canonical(),
            r#"{"end":{"document":null,"receipt":null}}"#
        );
    }
}
