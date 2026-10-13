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
//! - `import_root`: the directory every import must stay inside, as the
//!   library's `import_root=` gives it (E515).
//! - `tests`: `true` for `sabline test` - each test function of the entry
//!   called in turn rather than `main` ([`crate::run_dump::test_relayed`]),
//!   a `{"test": ...}` frame after each, and the end `{"end": {"tests":
//!   ...}}`.
//! - `tool_ceiling`: the ceiling record of the host's tool session, when it
//!   has one (`sabline run --tools`): the receipt then lists the run's tool
//!   calls and the ceiling.
//! - `stop_file`: the file whose appearance stops the run with E615 at the
//!   next call or loop turn, which `sabline eval` gives and nothing else
//!   does (9.0, M4).
//! - `ceilings`: the organisation ceilings the run is held to (9.0,
//!   [`crate::ceiling`]), each `{"path", "text"}` as the package read it: a
//!   budget wider than one is E325 before the program is read, and each is
//!   named in the receipt.
//! - `dump`: `true` for the gate's run document of a run the host makes the
//!   relayed builtins of ([`crate::run_dump::run_hosted`]): the run takes a
//!   line of the gate's list - `environ`, `steps` and `size` too - keeps
//!   what it prints and reads in the document, as the gate's batch does,
//!   and sends only `call` frames; the end is `{"end": {"records": [...]}}`,
//!   the run document, the receipt and the audit stream as the canonical
//!   text the batch would write.
//!
//! Then the run, and on standard output a frame for each thing it does, in
//! the order it does them: `{"out": text}` for what `print` writes and
//! `{"err": text}` for what `log` writes, each with its line feed;
//! `{"read": "line"}` for `read_line` and `{"ask": prompt}` for `ask`, each
//! answered by one line on standard input, `{"line": text}` or
//! `{"line": null}` for the end of the input; `{"event": ...}` for each
//! event of the audit stream, when it was asked for; `{"call": {"name",
//! "args", "line"}}` for each builtin whose work is the host's - the
//! network, Python, a tool ([`crate::interp::RELAYED`]) - asked once its
//! effect is spent, and answered by one line, `{"answer": ...}`: how the
//! call ended - `{"value": v}`, `{"fail": reason}`, `{"error": {"code",
//! "message", "line", "fixes", "file"}}`, `{"exit": n}` or `{"raised":
//! name}` - with `did`, what the host's recorder noted while it made the
//! call, in order (`{"grant": text}` and `{"note": {"kind", ...}}`),
//! `counted`, what each grant let through, and for a tool call the
//! session's `tool_ceiling` record. A value travels as itself - a text, a
//! number, a yes/no, `null`, a list - or a handle as `{"handle": id,
//! "what": name}`; and last
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
    let tests = matches!(field(fields, "tests"), Some(Value::Bool(true)));
    let dump = matches!(field(fields, "dump"), Some(Value::Bool(true)));
    let tool_ceiling = match field(fields, "tool_ceiling") {
        None => None,
        Some(ceiling @ Value::Map(_)) => Some(crate::interp::json_of(&ceiling)),
        Some(_) => return Err("sabline-rt exec: 'tool_ceiling' is not an object".to_string()),
    };
    let mut environ = Vec::new();
    match field(fields, "environ") {
        None => {}
        Some(Value::Map(vars)) => {
            for (name, value) in vars.entries() {
                match (name, value) {
                    (Value::Text(n), Value::Text(v)) => match (n.to_str(), v.to_str()) {
                        (Some(n), Some(v)) => environ.push((n, v)),
                        _ => {
                            return Err("sabline-rt exec: a variable holds a lone surrogate"
                                .to_string())
                        }
                    },
                    _ => return Err("sabline-rt exec: a variable is not a text".to_string()),
                }
            }
        }
        Some(_) => return Err("sabline-rt exec: 'environ' is not an object".to_string()),
    }
    let limit = |k: &str| -> Result<Option<u64>, String> {
        Ok(int_field(fields, k)?.map(|n| u64::try_from(n.max(0)).unwrap_or(u64::MAX)))
    };
    let (steps, size) = (limit("steps")?, limit("size")?);
    let mut ceilings = Vec::new();
    match field(fields, "ceilings") {
        None => {}
        Some(Value::List(listed)) => {
            for c in listed.iter() {
                let Value::Map(c) = c else {
                    return Err("sabline-rt exec: a ceiling is not an object".to_string());
                };
                let (Some(path), Some(text)) =
                    (text_field(c.entries(), "path")?, text_field(c.entries(), "text")?)
                else {
                    return Err(
                        "sabline-rt exec: a ceiling names no path or no text".to_string()
                    );
                };
                ceilings.push((path, text));
            }
        }
        Some(_) => return Err("sabline-rt exec: 'ceilings' is not a list".to_string()),
    }
    // what the host asked of the operating system (9.0, M4): absent is
    // "nothing was asked", which is what a run through sabline-rt was
    // before this rung and what the gate's own batches still are
    let confine = match field(fields, "confine") {
        None | Some(Value::None) => None,
        Some(Value::Bool(on)) => {
            Some(crate::confine::Asked { on, strict: false, ..Default::default() })
        }
        Some(Value::Text(t)) if t.to_str().as_deref() == Some("strict") => {
            Some(crate::confine::Asked { on: true, strict: true, ..Default::default() })
        }
        Some(_) => {
            return Err("sabline-rt exec: 'confine' is true, false or \"strict\"".to_string())
        }
    };
    let confine = match confine {
        None => None,
        Some(mut asked) => {
            asked.require = match text_field(fields, "require_confinement")? {
                None => None,
                Some(word) if crate::confine::REQUIRE_WORDS.contains(&word.as_str()) => {
                    Some(word)
                }
                Some(word) => {
                    return Err(format!(
                        "sabline-rt exec: 'require_confinement' is {word:?}, not full or \
                         partial"
                    ))
                }
            };
            asked.reads = texts(fields, "confine_reads")?;
            asked.writes = texts(fields, "confine_writes")?;
            asked.temp = text_field(fields, "confine_temp")?;
            asked.read_any =
                matches!(field(fields, "confine_read_any"), Some(Value::Bool(true)));
            asked.host = text_field(fields, "host_confinement")?;
            Some(asked)
        }
    };
    Ok((
        path,
        Given {
            confine,
            allow: text_field(fields, "allow")?,
            deny: text_field(fields, "deny")?,
            params,
            args: Some(args),
            name: text_field(fields, "name")?,
            relayed: true,
            stream,
            source: text_field(fields, "source")?,
            import_root: text_field(fields, "import_root")?,
            tests,
            tool_ceiling,
            dump,
            environ,
            steps,
            size,
            ceilings,
            stop_file: text_field(fields, "stop_file")?,
        },
    ))
}

/// A list of texts under one name, `[]` when it is absent.
fn texts(fields: &[(Value, Value)], name: &str) -> Result<Vec<String>, String> {
    match field(fields, name) {
        None | Some(Value::None) => Ok(Vec::new()),
        Some(Value::List(xs)) => xs
            .iter()
            .map(|x| match x {
                Value::Text(t) => t
                    .to_str()
                    .ok_or_else(|| format!("sabline-rt exec: a '{name}' holds a surrogate")),
                _ => Err(format!("sabline-rt exec: a '{name}' is not a text")),
            })
            .collect(),
        Some(_) => Err(format!("sabline-rt exec: '{name}' is not a list")),
    }
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
        Frame::Call(c) => Json::obj([("call", c)]),
    }
}

/// The last frame: the run document and the receipt.
pub fn end(document: Json, receipt: Json) -> Json {
    Json::obj([("end", Json::obj([("document", document), ("receipt", receipt)]))])
}

/// The last frame of a hosted run (`dump`): what the end carries - its
/// three records, each the canonical text the gate's batch writes.
pub fn records(document: &Json, receipt: &Json, stream: &Json) -> Json {
    Json::obj([(
        "records",
        Json::List(vec![
            Json::Str(document.canonical()),
            Json::Str(receipt.canonical()),
            Json::Str(stream.canonical()),
        ]),
    )])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_request_gives_the_run_what_the_command_line_would() {
        let (path, given) = request(
            r#"{"path": "p.vel", "allow": "io,fs:read:.", "deny": null, "seed": 7,
               "freeze_time": -5, "max_read": 10, "args": ["a", "\ud800"], "name": "<source>",
               "stream": true, "import_root": "box", "tests": true,
               "tool_ceiling": {"calls": 2, "cost": 1.5}, "dump": true,
               "environ": {"HOME": "/h"}, "steps": 9, "size": -1}"#,
        )
        .unwrap();
        assert_eq!(
            given.tool_ceiling.as_ref().map(Json::canonical).as_deref(),
            Some(r#"{"calls":2,"cost":1.5}"#)
        );
        assert!(given.dump);
        assert_eq!(given.environ, [("HOME".to_string(), "/h".to_string())]);
        assert_eq!((given.steps, given.size), (Some(9), Some(0)));
        assert_eq!(path, "p.vel");
        assert_eq!(given.allow.as_deref(), Some("io,fs:read:."));
        assert_eq!(given.deny, None);
        assert_eq!(
            (given.params.seed, given.params.freeze_time, given.params.max_read),
            (Some(7), Some(-5), 10)
        );
        assert_eq!(given.args.unwrap()[1], Text::from(vec![0xD800]));
        assert_eq!(given.name.as_deref(), Some("<source>"));
        assert_eq!(given.import_root.as_deref(), Some("box"));
        assert!(given.tests);
        assert!(given.relayed && given.stream);
        assert!(request(r#"{"allow": "io"}"#).unwrap_err().contains("no 'path'"));
        assert!(request("[1]").unwrap_err().contains("not an object"));
        assert!(request(r#"{"path": "p", "seed": true}"#).is_err());
        assert!(request(r#"{"path": "p", "tool_ceiling": 3}"#).is_err());
        assert!(request(r#"{"path": "p", "environ": {"A": 1}}"#).is_err());
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
            frame(Frame::Call(Json::obj([("name", Json::text("py"))]))).canonical(),
            r#"{"call":{"name":"py"}}"#
        );
        assert_eq!(
            records(&Json::Int(1), &Json::Null, &Json::text("a\"b")).canonical(),
            r#"{"records":["1","null","\"a\\\"b\""]}"#
        );
        assert_eq!(
            end(Json::Null, Json::Null).canonical(),
            r#"{"end":{"document":null,"receipt":null}}"#
        );
    }
}
