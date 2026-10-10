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
//!
//! Each document is followed by the run's receipt ([`crate::receipt`]),
//! recorded as `sabline <file> --receipt` records it, or `null` where the
//! command line writes none.

use std::collections::{HashMap, HashSet};

use crate::budget::budget_from;
use crate::checker::check_types;
use crate::effects::check_effects;
use crate::errors::SablineError;
use crate::host::Environ;
use crate::interp::{Io, Relay, RunError, RunParams, Runtime, Stop};
use crate::json::Json;
use crate::loader::load_program_given;
use crate::receipt::{self, Ending};
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
    /// A step limit and a size limit of the line's own, in place of `STEPS`
    /// and `SIZE`: what the differential fuzzer runs under, and the gate
    /// never gives.
    pub steps: Option<u64>,
    /// See `steps`.
    pub size: Option<u64>,
    /// What `args()` answers, in place of `ARGS`: a relayed run's own.
    pub args: Option<Vec<Text>>,
    /// The name the receipt gives the program, in place of its path's: the
    /// library's `<source>`, or the path as the command line was given it.
    pub name: Option<String>,
    /// A relayed run is a user's, not the gate's: no step limit and no size
    /// limit, and an audit stream only when one was asked for.
    pub relayed: bool,
    /// Whether a relayed run's audit stream was asked for.
    pub stream: bool,
    /// The entry's text, in place of the file at its path: the library's
    /// `sabline.run(source, path=...)`.
    pub source: Option<String>,
}

impl Given {
    /// A line of the list: a path, or a JSON object naming one with any of
    /// `allow`, `deny`, `seed`, `freeze_time`, `max_read`, `environ`,
    /// `steps` and `size`.
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
        let limit = |k: &str| int(k).map(|n| n.max(0) as u64);
        Ok((
            path,
            Given {
                allow: text("allow"),
                deny: text("deny"),
                params,
                environ,
                steps: limit("steps"),
                size: limit("size"),
                ..Given::default()
            },
        ))
    }
}

/// The document for one program, under the budget `io`.
pub fn run_document(path: &str, install_dir: &str) -> Json {
    run_document_given(path, install_dir, &Given::default())
}

/// The document for one program, under what its line of the list gives.
pub fn run_document_given(path: &str, install_dir: &str, given: &Given) -> Json {
    run_recorded(path, install_dir, given).0
}

/// What a run's receipt and audit stream are made from besides the
/// recorder: the program as it was given and read, and when it started.
struct Facts<'a> {
    path: &'a str,
    install_dir: &'a str,
    given: &'a Given,
    spec: String,
    name: String,
    entry_bytes: Vec<u8>,
    files: Vec<String>,
    started_at: String,
    t0: std::time::Instant,
}

impl Facts<'_> {
    fn subjects(&self) -> Vec<Json> {
        receipt::subjects(
            self.path,
            &self.name,
            &self.entry_bytes,
            &self.files,
            self.install_dir,
        )
    }

    fn run<'r>(
        &'r self,
        effect_uses: &'r HashMap<String, u64>,
        grant_uses: &'r [(String, u64)],
        ending: Ending,
        subjects: Vec<Json>,
    ) -> receipt::Run<'r> {
        receipt::Run {
            name: &self.name,
            subjects,
            budget: self.spec.clone(),
            seed: self.given.params.seed,
            freeze_time: self.given.params.freeze_time,
            max_read: self.given.params.max_read,
            effect_uses,
            grant_uses,
            started_at: self.started_at.clone(),
            wall_time_ms: self.t0.elapsed().as_secs_f64() * 1000.0,
            ending,
        }
    }

    /// The receipt and the audit stream of a run that has ended, or two
    /// nulls for a frozen clock past what an instant can say.
    fn ended(
        &self,
        recorder: &mut receipt::Recorder,
        effect_uses: &HashMap<String, u64>,
        grant_uses: &[(String, u64)],
        ending: Ending,
    ) -> (Json, Json) {
        let run = self.run(effect_uses, grant_uses, ending, self.subjects());
        match receipt::statement(recorder, &run) {
            Some(receipt) => {
                receipt::stream_end(recorder, &receipt);
                let stream = Json::List(recorder.stream.take().unwrap_or_default());
                (receipt, stream)
            }
            None => (Json::Null, Json::Null),
        }
    }
}

/// The run document, the receipt of the same run, and its audit stream as a
/// list of events - the last two `Json::Null` where the command line writes
/// no receipt: a budget that does not parse, a failure that escaped, and a
/// frozen clock past what an instant can say.
pub fn run_recorded(path: &str, install_dir: &str, given: &Given) -> (Json, Json, Json) {
    run_inner(path, install_dir, given, None)
}

/// A run for whoever started this process (`sabline-rt exec`, 9.0 M3):
/// what the program writes and asks for, and each event of its audit stream
/// when one was asked for, go to `relay` as they happen; what comes back is
/// the run document - its `stdout` and `stderr` empty, since both were
/// relayed - and the receipt. No step limit and no size limit: those are
/// the gate's, and a user's run has neither.
pub fn run_relayed(
    path: &str,
    install_dir: &str,
    given: &Given,
    relay: Relay,
) -> (Json, Json) {
    let given = Given { relayed: true, ..given.clone() };
    let (doc, receipt, _) = run_inner(path, install_dir, &given, Some(relay));
    (doc, receipt)
}

fn run_inner(
    path: &str,
    install_dir: &str,
    given: &Given,
    relay: Option<Relay>,
) -> (Json, Json, Json) {
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
        return (doc.json(), Json::Null, Json::Null);
    };
    // read before the run, as the command line reads it for the receipt
    let mut facts = Facts {
        path,
        install_dir,
        given,
        spec: budget.spec(),
        name: given.name.clone().unwrap_or_else(|| receipt::entry_name(path)),
        entry_bytes: match &given.source {
            Some(text) => text.as_bytes().to_vec(),
            None => std::fs::read(path).unwrap_or_default(),
        },
        files: Vec::new(),
        started_at: receipt::utc_now_ms(),
        t0: std::time::Instant::now(),
    };
    let none = HashMap::new();
    let failed = Ending { status: Some(1), ..Ending::default() };
    let mut recorder = if given.relayed && !given.stream {
        receipt::Recorder::default()
    } else {
        receipt::Recorder::streaming()
    };
    recorder.live = relay.as_ref().map(|r| r.frames.clone());
    if !receipt::stream_start(&mut recorder, &facts.run(&none, &[], failed, Vec::new())) {
        recorder.stream = None; // no instant: neither a stream nor a receipt
    }
    let loaded =
        load_program_given(path, given.source.as_deref(), install_dir, &mut facts.files);
    // the audit stream's subjects, once loading is over
    if !facts.files.is_empty() && recorder.stream.is_some() {
        recorder.tell_subjects(&facts.subjects());
    }
    let loaded = match loaded {
        Ok(loaded) => loaded,
        Err(e) => {
            recorder.note_error(e.code, e.line, &e.message);
            doc.error = checked(&e, path);
            doc.exit = Json::Int(1);
            let (receipt, stream) = facts.ended(&mut recorder, &none, &[], failed);
            return (doc.json(), receipt, stream);
        }
    };
    let mut errors = Vec::new();
    check_effects(&loaded.funcs, install_dir, &mut errors);
    if let Err(stopped) = check_types(&loaded.funcs, &loaded.records, &mut errors) {
        recorder.note_error(stopped.code, stopped.line, &stopped.message);
        doc.error = checked(&stopped, path);
        doc.exit = Json::Int(1);
        let (receipt, stream) = facts.ended(&mut recorder, &none, &[], failed);
        return (doc.json(), receipt, stream);
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
        recorder.note_stop(unique[0].code, unique[0].line);
        let (receipt, stream) = facts.ended(&mut recorder, &none, &[], failed);
        return (doc.json(), receipt, stream);
    }
    let args =
        given.args.clone().unwrap_or_else(|| ARGS.iter().map(|a| Text::from(*a)).collect());
    let io = match relay {
        Some(relay) => Io::relayed(relay, args),
        None => Io::new(STDIN, args),
    };
    let mut environ = Environ::of_process();
    for (name, value) in &given.environ {
        environ.set(name, value);
    }
    let mut rt = Runtime::new(&loaded.funcs, &loaded.records, budget, io)
        .with_environ(environ)
        .with_params(given.params.clone());
    if !given.relayed {
        rt = rt
            .with_step_limit(given.steps.unwrap_or(STEPS))
            .with_size_limit(given.size.unwrap_or(SIZE));
    }
    rt.recorder = recorder;
    rt.recorder.compiled = true;
    let mut ending = Ending::default();
    let mut escaped = false;
    match rt.interpret() {
        Ok(()) => ending.status = Some(0),
        Err(Stop::Error(e)) => {
            rt.recorder.note_error(e.code, e.line, &e.message.to_string_lossy());
            doc.error = ran(&e, path);
            doc.exit = Json::Int(1);
            ending.status = Some(1);
        }
        Err(Stop::Exit(code)) => {
            doc.exit = Json::Int(code);
            ending.status = Some(code);
        }
        Err(Stop::Steps(line)) => {
            doc.stopped = Json::Int(i64::from(line));
            doc.stopped_by = Json::text("steps");
            doc.exit = Json::Null;
            ending.timed_out = true;
        }
        Err(Stop::Size(line)) => {
            doc.stopped = Json::Int(i64::from(line));
            doc.stopped_by = Json::text("size");
            doc.exit = Json::Null;
            ending.out_of_memory = true;
        }
        Err(Stop::Fail(_)) => {
            doc.raised = Json::text("FailSignal");
            doc.exit = Json::Null;
            escaped = true;
        }
        Err(Stop::Raised(what)) => {
            doc.raised = Json::text(what);
            doc.exit = Json::Null;
            escaped = true;
        }
    }
    doc.stdout = std::mem::take(&mut rt.io.stdout).done();
    doc.stderr = std::mem::take(&mut rt.io.stderr).done();
    if escaped {
        return (doc.json(), Json::Null, Json::Null); // the command line wrote none
    }
    let mut recorder = std::mem::take(&mut rt.recorder);
    let (receipt, stream) =
        facts.ended(&mut recorder, &rt.effect_uses, &rt.grant_uses, ending);
    (doc.json(), receipt, stream)
}

/// Whether a document is of a run that ended with status 0.
pub fn ran_clean(document: &Json) -> bool {
    matches!(document, Json::Obj(fields) if fields.get("exit") == Some(&Json::Int(0)))
}
