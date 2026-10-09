//! The canonical run document: what a run of one program did - its
//! output, its exit status, and the error it stopped with - as
//! `sabline/run_dump.py` writes it (9.0, M3).
//!
//! `check_agreement.py` compares this document with the Python package's,
//! byte for byte, over every program it holds. The run is `sabline
//! <file>`'s - the checkers as the command line runs them, then the
//! program - with the budget `io`, a fixed input, fixed arguments and a
//! step limit, and without the prover, native code or the operating
//! system's confinement. sabline/run_dump.py's docstring says why each of
//! those is fixed or left out; this module copies what it fixes.

use std::collections::HashSet;

use crate::budget::{Budget, DEFAULT_ALLOW};
use crate::checker::check_types;
use crate::effects::check_effects;
use crate::errors::SablineError;
use crate::interp::{Io, RunError, Runtime, Stop};
use crate::json::Json;
use crate::loader::load_program;
use crate::text::Text;

/// The format's version, carried in every document.
pub const RUN_VERSION: i64 = 1;

/// What `read_line` and `ask` read.
pub const STDIN: &str = "1\n2\nthree\n";

/// What `args()` answers.
pub const ARGS: [&str; 2] = ["first", "2"];

/// How many calls and loop turns before a run is stopped.
pub const STEPS: u64 = 20000;

fn error_json(
    code: &str,
    message: Json,
    file: Option<&str>,
    line: u32,
    fixes: &[String],
    path: &str,
) -> Json {
    Json::obj([
        ("code", Json::text(code)),
        ("file", Json::text(file.unwrap_or(path))),
        ("fixes", Json::List(fixes.iter().map(|f| Json::text(f.clone())).collect())),
        ("line", Json::Int(i64::from(line))),
        ("message", message),
    ])
}

fn checked(e: &SablineError, path: &str) -> Json {
    error_json(
        e.code,
        Json::text(e.message.clone()),
        e.file.as_deref(),
        e.line,
        &e.fixes,
        path,
    )
}

fn ran(e: &RunError, path: &str) -> Json {
    error_json(
        e.code,
        Json::Text(e.message.clone()),
        e.file.as_deref(),
        e.line,
        &e.fixes,
        path,
    )
}

struct Doc {
    refused: Json,
    error: Json,
    exit: Json,
    stdout: Text,
    stderr: Text,
    stopped: Json,
    raised: Json,
}

impl Doc {
    fn json(self) -> Json {
        Json::obj([
            ("run", Json::Int(RUN_VERSION)),
            ("refused", self.refused),
            ("error", self.error),
            ("exit", self.exit),
            ("stdout", Json::Text(self.stdout)),
            ("stderr", Json::Text(self.stderr)),
            ("stopped", self.stopped),
            ("raised", self.raised),
        ])
    }
}

/// The document for one program.
pub fn run_document(path: &str, install_dir: &str) -> Json {
    let mut doc = Doc {
        refused: Json::Null,
        error: Json::Null,
        exit: Json::Int(0),
        stdout: Text::default(),
        stderr: Text::default(),
        stopped: Json::Null,
        raised: Json::Null,
    };
    let loaded = match load_program(path, install_dir) {
        Ok(loaded) => loaded,
        Err(e) => {
            doc.error = checked(&e, path);
            doc.exit = Json::Int(1);
            return doc.json();
        }
    };
    let mut errors = Vec::new();
    check_effects(&loaded.funcs, install_dir, &mut errors);
    if let Err(stopped) = check_types(&loaded.funcs, &loaded.records, &mut errors) {
        doc.error = checked(&stopped, path);
        doc.exit = Json::Int(1);
        return doc.json();
    }
    if !errors.is_empty() {
        let mut seen: HashSet<(&'static str, String, u32, String)> = HashSet::new();
        let mut unique: Vec<&SablineError> = Vec::new();
        for e in &errors {
            let file = e.file.clone().unwrap_or_else(|| path.to_string());
            if seen.insert((e.code, file, e.line, e.message.clone())) {
                unique.push(e);
            }
        }
        unique.sort_by(|a, b| {
            let fa = a.file.as_deref().unwrap_or(path);
            let fb = b.file.as_deref().unwrap_or(path);
            fa.cmp(fb).then(a.line.cmp(&b.line))
        });
        doc.refused = Json::List(unique.iter().map(|e| checked(e, path)).collect());
        doc.exit = Json::Int(1);
        return doc.json();
    }
    let budget = Budget::parse(DEFAULT_ALLOW).unwrap_or_default();
    let io = Io::new(STDIN, ARGS.iter().map(|a| Text::from(*a)).collect());
    let mut rt =
        Runtime::new(&loaded.funcs, &loaded.records, budget, io).with_step_limit(STEPS);
    match rt.interpret() {
        Ok(()) => {}
        Err(Stop::Error(e)) => {
            doc.error = ran(&e, path);
            doc.exit = Json::Int(1);
        }
        Err(Stop::Exit(code)) => doc.exit = Json::Int(code),
        Err(Stop::Steps(line)) => {
            doc.stopped = Json::Int(i64::from(line));
            doc.exit = Json::Null;
        }
        Err(Stop::Fail(_)) => {
            doc.raised = Json::text("FailSignal");
            doc.exit = Json::Null;
        }
        Err(Stop::Raised(what)) => {
            doc.raised = Json::text(what);
            doc.exit = Json::Null;
        }
    }
    doc.stdout = std::mem::take(&mut rt.io.stdout).done();
    doc.stderr = std::mem::take(&mut rt.io.stderr).done();
    doc.json()
}

/// Whether a document is of a run that ended with status 0.
pub fn ran_clean(document: &Json) -> bool {
    matches!(document, Json::Obj(fields) if fields.get("exit") == Some(&Json::Int(0)))
}
