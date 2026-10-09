//! The canonical run document: what a run of one program did - its
//! output, its exit status, and the error it stopped with - as
//! `sabline/run_dump.py` writes it (9.0, M3).
//!
//! `check_agreement.py` compares this document with the Python package's,
//! byte for byte, over every program it holds. The run is `sabline
//! <file>`'s - the checkers as the command line runs them, then the
//! program - with the budget `io`, a fixed input, fixed arguments, a
//! step limit and a size limit, and without the prover, native code or the operating
//! system's confinement. sabline/run_dump.py's docstring says why each of
//! those is fixed or left out; this module copies what it fixes.

use std::collections::HashSet;

use crate::budget::budget_from;
use crate::checker::check_types;
use crate::effects::check_effects;
use crate::errors::SablineError;
use crate::host::Environ;
use crate::interp::{Io, RunError, RunParams, Runtime, Stop};
use crate::json::Json;
use crate::loader::load_program;
use crate::text::Text;

/// The format's version, carried in every document: 2 from the size
/// limit, whose stop the document names in `stopped_by`.
pub const RUN_VERSION: i64 = 2;

/// What `read_line` and `ask` read.
pub const STDIN: &str = "1\n2\nthree\n";

/// What `args()` answers.
pub const ARGS: [&str; 2] = ["first", "2"];

/// How many calls and loop turns before a run is stopped.
pub const STEPS: u64 = 20000;

/// How much a run may make before it is stopped, counted as
/// `interp::size_of` counts it: `run_dump.SIZE`.
pub const SIZE: u64 = 1 << 22;

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
    stopped_by: Json,
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
            ("stopped_by", self.stopped_by),
            ("raised", self.raised),
        ])
    }
}

/// What a line of the list gives besides the program's path: the budget,
/// as `--allow` and `--deny` give it, and the run's parameters.
#[derive(Debug, Clone, Default)]
pub struct Given {
    /// `--allow`, or `None` for `io`.
    pub allow: Option<String>,
    /// `--deny`.
    pub deny: Option<String>,
    /// The seed, the frozen clock and the read ceiling.
    pub params: RunParams,
    /// Variables set for the run over the process's environment.
    pub environ: Vec<(String, String)>,
}

impl Given {
    /// A line of the list: a path, or a JSON object naming one with any of
    /// `allow`, `deny`, `seed`, `freeze_time` and `max_read`.
    pub fn of_line(line: &str) -> Result<(String, Given), String> {
        if !line.starts_with('{') {
            return Ok((line.to_string(), Given::default()));
        }
        let Json::Obj(fields) = Json::parse(line)? else {
            return Err(format!("not an object: {line}"));
        };
        let text = |k: &str| match fields.get(k) {
            Some(Json::Str(s)) => Some(s.clone()),
            _ => None,
        };
        let int = |k: &str| match fields.get(k) {
            Some(Json::Int(n)) => Some(*n),
            _ => None,
        };
        let path = text("path").ok_or_else(|| format!("no path: {line}"))?;
        let mut params = RunParams {
            seed: int("seed").map(i128::from),
            freeze_time: int("freeze_time"),
            ..RunParams::default()
        };
        if let Some(n) = int("max_read") {
            params.max_read = n.max(0) as u64;
        }
        let mut environ = Vec::new();
        if let Some(Json::Obj(vars)) = fields.get("environ") {
            for (name, value) in vars {
                if let Json::Str(v) = value {
                    environ.push((name.clone(), v.clone()));
                }
            }
        }
        Ok((path, Given { allow: text("allow"), deny: text("deny"), params, environ }))
    }
}

/// The document for one program, under the budget `io`.
pub fn run_document(path: &str, install_dir: &str) -> Json {
    run_document_given(path, install_dir, &Given::default())
}

/// The document for one program, under what its line of the list gives.
pub fn run_document_given(path: &str, install_dir: &str, given: &Given) -> Json {
    let mut doc = Doc {
        refused: Json::Null,
        error: Json::Null,
        exit: Json::Int(0),
        stdout: Text::default(),
        stderr: Text::default(),
        stopped: Json::Null,
        stopped_by: Json::Null,
        raised: Json::Null,
    };
    let Ok(budget) = budget_from(given.allow.as_deref(), given.deny.as_deref()) else {
        doc.raised = Json::text("BudgetError");
        doc.exit = Json::Null;
        return doc.json();
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
    let io = Io::new(STDIN, ARGS.iter().map(|a| Text::from(*a)).collect());
    let mut environ = Environ::of_process();
    for (name, value) in &given.environ {
        environ.set(name, value);
    }
    let mut rt = Runtime::new(&loaded.funcs, &loaded.records, budget, io)
        .with_environ(environ)
        .with_params(given.params.clone())
        .with_step_limit(STEPS)
        .with_size_limit(SIZE);
    match rt.interpret() {
        Ok(()) => {}
        Err(Stop::Error(e)) => {
            doc.error = ran(&e, path);
            doc.exit = Json::Int(1);
        }
        Err(Stop::Exit(code)) => doc.exit = Json::Int(code),
        Err(Stop::Steps(line)) => {
            doc.stopped = Json::Int(i64::from(line));
            doc.stopped_by = Json::text("steps");
            doc.exit = Json::Null;
        }
        Err(Stop::Size(line)) => {
            doc.stopped = Json::Int(i64::from(line));
            doc.stopped_by = Json::text("size");
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
