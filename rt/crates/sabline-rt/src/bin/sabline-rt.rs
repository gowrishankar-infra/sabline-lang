//! `sabline-rt`: the crate's command line.
//!
//! ```text
//! sabline-rt ast <file.vel>        the canonical dump of one file
//! sabline-rt ast --list <paths>    one dump per line of <paths>, framed
//! sabline-rt check --install-dir DIR <file.vel>
//!                                  the canonical check document (9.0, M2)
//! sabline-rt check --install-dir DIR --list <paths>
//! sabline-rt tables                the builtin tables the checkers read
//! sabline-rt budget --list <file>  one budget document per line of <file>,
//!                                  each line `[allow, deny]` as JSON (M2)
//! sabline-rt os-policy --list <file>
//!                                  one OS policy document per line of
//!                                  <file>, framed as `budget --list` is:
//!                                  what the operating system is asked to
//!                                  hold for that budget (M4)
//! sabline-rt os-policy --table     the confinement tables, as one
//!                                  document (M4)
//! sabline-rt os-policy --enforces  how much of each row of THREAT_MODEL's
//!                                  table this runtime's kernel holds, one
//!                                  word per system (M4)
//! sabline-rt run --install-dir DIR --list <file>
//!                                  the run document, receipt and audit
//!                                  stream of each line's program (M3)
//! sabline-rt exec --install-dir DIR
//!                                  one program run for whoever started
//!                                  this process, a frame at a time on
//!                                  standard input and output: what
//!                                  `sabline run` and `sabline.run` go
//!                                  through under SABLINE_REFERENCE_RUNTIME
//!                                  =rust (M3; `src/exec.rs` says how)
//! sabline-rt exec --install-dir DIR --contained SID
//!                                  the same, for a process started inside
//!                                  the Windows AppContainer whose SID that
//!                                  is - which the run asks the kernel
//!                                  about rather than believing (M4,
//!                                  `src/confine_appcontainer.rs`). Nobody
//!                                  types it: `sabline-rt exec` starts it
//! sabline-rt --version
//! ```
//!
//! `--install-dir` is where the host keeps the shipped standard library,
//! as `DIR/stdlib/`: an import a program's own directory does not have is
//! looked for there by its base name, as the Python package looks beside
//! itself. The host says where, because the host is what knows.
//!
//! `--list` exists because the agreement gate compares some hundreds of
//! files on every commit in every leg, and a process per file would make
//! the gate the slowest thing in CI. The array's elements are the same
//! documents the one-file form writes.
//!
//! Exit status: 0 when every file parsed, 1 when any was refused with a
//! code, 2 when the command line itself was wrong. A refusal is always a
//! document on standard output - never a panic, and never a message on
//! standard error alone.

use std::io::{Read, Write};
use std::process::ExitCode;

use sabline_rt::json::Json;
use sabline_rt::{dump_bytes, source, VERSION};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = args.iter().map(String::as_str).collect();
    match run(&words) {
        Ok(code) => code,
        Err(message) => {
            eprintln!("{message}");
            eprintln!("usage: sabline-rt ast <file.vel>");
            eprintln!("       sabline-rt ast --list <paths-file>");
            eprintln!("       sabline-rt check --install-dir <dir> <file.vel>");
            eprintln!("       sabline-rt check --install-dir <dir> --list <paths-file>");
            eprintln!("       sabline-rt tables");
            eprintln!("       sabline-rt budget --list <budgets-file>");
            eprintln!("       sabline-rt os-policy --list <budgets-file>");
            eprintln!("       sabline-rt os-policy --table");
            eprintln!("       sabline-rt os-policy --enforces");
            eprintln!("       sabline-rt run --install-dir <dir> --list <paths-file>");
            eprintln!("       sabline-rt exec --install-dir <dir>");
            eprintln!("       sabline-rt exec --install-dir <dir> --contained <sid>");
            eprintln!("       sabline-rt --version");
            ExitCode::from(2)
        }
    }
}

fn run(words: &[&str]) -> Result<ExitCode, String> {
    match words {
        ["--version"] | ["version"] => {
            println!("sabline-rt {VERSION}");
            Ok(ExitCode::SUCCESS)
        }
        ["--help"] | ["-h"] | [] => Err("sabline-rt: say what to do".to_string()),
        ["ast", "--list", list] => on_a_big_stack(list_of((*list).to_string())),
        ["ast", path] if !path.starts_with('-') => on_a_big_stack(one((*path).to_string())),
        ["check", "--install-dir", dir, "--list", list] => {
            on_a_big_stack(check_list_of((*dir).to_string(), (*list).to_string()))
        }
        ["check", "--install-dir", dir, path] if !path.starts_with('-') => {
            on_a_big_stack(check_one((*dir).to_string(), (*path).to_string()))
        }
        ["tables"] => {
            write_out(&sabline_rt::tables::document().canonical())?;
            Ok(ExitCode::SUCCESS)
        }
        ["budget", "--list", list] => budget_list_of(list),
        ["os-policy", "--list", list] => policy_list_of(list),
        ["os-policy", "--table"] => {
            write_out(&sabline_rt::confine::table_document().canonical())?;
            Ok(ExitCode::SUCCESS)
        }
        ["os-policy", "--enforces"] => {
            write_out(&sabline_rt::confine::enforces_document().canonical())?;
            Ok(ExitCode::SUCCESS)
        }
        ["run", "--install-dir", dir, "--list", list] => {
            on_a_big_stack(run_list_of((*dir).to_string(), (*list).to_string()))
        }
        ["exec", "--install-dir", dir] => exec((*dir).to_string(), None),
        ["exec", "--install-dir", dir, "--contained", sid] => {
            exec((*dir).to_string(), Some((*sid).to_string()))
        }
        _ => Err(format!("sabline-rt: cannot read '{}'", words.join(" "))),
    }
}

/// Run `work` on the stack a parse needs (`sabline_rt::PARSE_STACK`).
fn on_a_big_stack<F>(work: F) -> Result<ExitCode, String>
where
    F: FnOnce() -> Result<ExitCode, String> + Send + 'static,
{
    sabline_rt::on_parse_stack(work)
}

fn one(path: String) -> impl FnOnce() -> Result<ExitCode, String> + Send + 'static {
    move || {
        let (document, ok) = document_of(&path);
        write_out(&document.canonical())?;
        Ok(if ok { ExitCode::SUCCESS } else { ExitCode::from(1) })
    }
}

/// The header of the framed stream `--list` writes.
///
/// Each record after it is
///
/// ```text
/// --- <bytes> <path>\n
/// <that many bytes of canonical document>\n
/// ```
///
/// A length rather than a separator, so that a record's bytes are the
/// document's bytes and a reader never has to parse one to find the next.
/// The gate compares those bytes; it reads a document only to say where
/// two of them first differ, and a document 4,000 levels deep is deeper
/// than a JSON reader's own recursion.
const BATCH_HEADER: &str = "sabline.ast-batch/1";

fn list_of(list: String) -> impl FnOnce() -> Result<ExitCode, String> + Send + 'static {
    move || {
        let text = read_list(&list)?;
        let mut every = true;
        out(format!("{BATCH_HEADER}\n").as_bytes())?;
        for line in text.lines() {
            let path = line.trim_end_matches('\r');
            if path.is_empty() {
                continue;
            }
            let (document, ok) = document_of(path);
            every &= ok;
            let body = document.canonical();
            out(format!("--- {} {path}\n", body.len()).as_bytes())?;
            out(body.as_bytes())?;
            out(b"\n")?;
        }
        Ok(if every { ExitCode::SUCCESS } else { ExitCode::from(1) })
    }
}

/// The header of the framed stream `check --list` writes; the records are
/// framed as `ast --list`'s are.
const CHECK_BATCH_HEADER: &str = "sabline.check-batch/1";

fn check_one(
    dir: String,
    path: String,
) -> impl FnOnce() -> Result<ExitCode, String> + Send + 'static {
    move || {
        let document = sabline_rt::check_dump::check_document(&path, &dir);
        write_out(&document.canonical())?;
        let clean = sabline_rt::check_dump::checked_clean(&document);
        Ok(if clean { ExitCode::SUCCESS } else { ExitCode::from(1) })
    }
}

fn check_list_of(
    dir: String,
    list: String,
) -> impl FnOnce() -> Result<ExitCode, String> + Send + 'static {
    move || {
        let text = read_list(&list)?;
        let mut every = true;
        out(format!("{CHECK_BATCH_HEADER}\n").as_bytes())?;
        for line in text.lines() {
            let path = line.trim_end_matches('\r');
            if path.is_empty() {
                continue;
            }
            let document = sabline_rt::check_dump::check_document(path, &dir);
            every &= sabline_rt::check_dump::checked_clean(&document);
            let body = document.canonical();
            out(format!("--- {} {path}\n", body.len()).as_bytes())?;
            out(body.as_bytes())?;
            out(b"\n")?;
        }
        Ok(if every { ExitCode::SUCCESS } else { ExitCode::from(1) })
    }
}

/// The header of the framed stream `run --list` writes; the records are
/// framed as `ast --list`'s are, three for each program: its run document,
/// its receipt, and its audit stream as a list of events (3, from the
/// stream; 2 added the receipt).
const RUN_BATCH_HEADER: &str = "sabline.run-batch/3";

fn run_list_of(
    dir: String,
    list: String,
) -> impl FnOnce() -> Result<ExitCode, String> + Send + 'static {
    move || {
        let text = read_list(&list)?;
        let mut every = true;
        out(format!("{RUN_BATCH_HEADER}\n").as_bytes())?;
        for line in text.lines() {
            let line = line.trim_end_matches('\r');
            if line.is_empty() {
                continue;
            }
            let (path, given) = sabline_rt::run_dump::Given::of_line(line)?;
            let path = path.as_str();
            let (document, receipt, stream) =
                sabline_rt::run_dump::run_recorded(path, &dir, &given);
            every &= sabline_rt::run_dump::ran_clean(&document);
            for record in [document, receipt, stream] {
                let body = record.canonical();
                out(format!("--- {} {path}\n", body.len()).as_bytes())?;
                out(body.as_bytes())?;
                out(b"\n")?;
            }
        }
        Ok(if every { ExitCode::SUCCESS } else { ExitCode::from(1) })
    }
}

/// `sabline-rt exec`: the request from the first line of standard input,
/// the run on a thread with the stack a parse needs, every frame it makes
/// written as it is made, and the end frame last (`src/exec.rs`). A thread
/// reads the rest of standard input for the whole run: its lines are the
/// answers to the run's questions, and its end while the run is going -
/// which a parent that is still there never gives before the end frame -
/// is a parent gone, so the process exits. That thread is started before
/// the first statement and not before the request, so a parent that goes
/// away while the program is being read and checked is noticed when it
/// starts rather than at once; it is noticed, and before anything runs.
///
/// **Which thread does what, and why in that order** (9.0, M4). Landlock
/// holds the thread that enters a ruleset and the threads that thread
/// starts afterwards, never a sibling that was already running, so a run
/// whose level says `full` must leave no thread out. This process has
/// three while a program runs - this one, which writes the frames; the
/// run's own; and the one that reads the answers - and they are started in
/// the order that holds all three:
///
/// 1. this thread reads the request, and starts the run's thread;
/// 2. the run's thread reads the program, checks it, and asks the
///    operating system to hold its budget;
/// 3. asking reaches back here ([`sabline_rt::confine`]'s hook), and this
///    thread enters the same ruleset and says whether it did, which the
///    run counts before it decides its level;
/// 4. this thread then starts the thread that reads the answers, which is
///    a thread it started afterwards and so is held by the same ruleset;
/// 5. the run's first statement runs.
///
/// A run the host asked nothing about is not confined, and the run's thread
/// says so at once (step 2 is skipped), so the frames and the answers flow
/// from the first moment - which is what every run before this rung did and
/// what the agreement gate's own batches still do.
fn exec(dir: String, contained: Option<String>) -> Result<ExitCode, String> {
    use std::io::BufRead;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::mpsc::{channel, Sender};

    use sabline_rt::confine::HoldMe;
    use sabline_rt::exec;
    use sabline_rt::interp::Relay;

    /// What the run's thread tells this one before the first statement.
    enum Holding {
        /// Hold this thread with the run's own ruleset, and say whether it
        /// took: 1 for yes, 0 for no. Only Landlock asks, because only
        /// Landlock holds a thread rather than a process.
        Me(HoldMe, Sender<usize>),
        /// The confinement is settled - applied, or decided against - and
        /// this thread may go on.
        Settled,
    }

    static RUNNING: AtomicBool = AtomicBool::new(false);
    static ENDED: AtomicBool = AtomicBool::new(false);
    let orphaned = || std::process::exit(i32::from(exec::ORPHANED));

    // the request: one line, read here. What is left in standard input's own
    // buffer after it stays there, and the thread that reads the answers
    // locks the same buffer, so nothing of the input is lost between them.
    let stdin = std::io::stdin();
    let mut first = String::new();
    match stdin.lock().read_line(&mut first) {
        Ok(n) if n > 0 => {}
        _ => return Err("sabline-rt exec: no request on standard input".to_string()),
    }

    // Windows, and the run's own process (9.0, M4): a process cannot enter
    // an AppContainer after it has started, so this one starts the run's
    // inside one and pumps the request and the answers through - or says
    // why it did not, and runs the program here.
    // (`sabline_rt::confine_appcontainer` says what the two halves do.)
    #[cfg(windows)]
    match &contained {
        None => {
            if let sabline_rt::confine_appcontainer::Taken::Ran(code) =
                sabline_rt::confine_appcontainer::consider(&first, &dir)
            {
                return Ok(ExitCode::from(code));
            }
        }
        Some(claimed) => {
            // the parent's claim, asked of the kernel rather than believed
            use sabline_rt::confine_appcontainer::{stands, Where};
            match sabline_rt::confine_appcontainer::in_a_container(claimed) {
                Ok(()) => stands(Where::Inside),
                Err(why) => stands(Where::Without(why)),
            }
        }
    }
    #[cfg(not(windows))]
    if contained.is_some() {
        return Err("sabline-rt exec: --contained is Windows' own, where a run's process is \
             started inside an AppContainer"
            .to_string());
    }

    let (lines, lines_in) = channel::<String>();
    let (frames, frames_in) = channel::<String>();
    let (holding, holding_in) = channel::<Holding>();
    // the hook the confinement asks through: it runs on the run's thread
    // and hands the ruleset to this one
    let asked = std::sync::Mutex::new(holding.clone());
    sabline_rt::confine::other_threads_hold_themselves(Box::new(move |hold_me| {
        let (took, answer) = channel::<usize>();
        let Ok(asked) = asked.lock() else { return 0 };
        if asked.send(Holding::Me(hold_me, took)).is_err() {
            return 0;
        }
        answer.recv().unwrap_or(0)
    }));
    let told = std::sync::Mutex::new(holding.clone());
    sabline_rt::confine::when_settled(Box::new(move || {
        if let Ok(told) = told.lock() {
            let _ = told.send(Holding::Settled);
        }
    }));

    /// The run, on its own thread: the request, and then the program.
    fn one_run(
        first: &str,
        dir: &str,
        frames: Sender<String>,
        answers: std::sync::mpsc::Receiver<String>,
        holding: &Sender<Holding>,
        running: &AtomicBool,
    ) -> Result<String, String> {
        // the request is read on the run's own thread: what it gives holds
        // texts, which stay on the thread that made them
        let (path, given) = exec::request(first)?;
        // from here an end of the input is a parent gone
        running.store(true, Ordering::SeqCst);
        if given.confine.is_none() {
            // nothing is asked of the operating system, so it is settled
            // here and the frames and the answers flow from this moment
            let _ = holding.send(Holding::Settled);
        }
        // the rest of standard input is the answers, a line each
        let relay = Relay { frames, answers };
        if given.tests {
            let ended = sabline_rt::run_dump::test_relayed(&path, dir, &given, relay);
            return Ok(format!("{{\"tests\":{}}}", ended.canonical()));
        }
        if given.dump {
            let (document, receipt, stream) =
                sabline_rt::run_dump::run_hosted(&path, dir, &given, relay);
            return Ok(exec::records(&document, &receipt, &stream).canonical());
        }
        let (document, receipt) = sabline_rt::run_dump::run_relayed(&path, dir, &given, relay);
        Ok(format!(
            "{{\"document\":{},\"receipt\":{}}}",
            document.canonical(),
            receipt.canonical()
        ))
    }

    let run = std::thread::Builder::new()
        .stack_size(sabline_rt::PARSE_STACK)
        .spawn(move || -> Result<String, String> {
            let ended = one_run(&first, &dir, frames, lines_in, &holding, &RUNNING);
            // whatever happened, this thread will not ask again. A run that
            // ended before its first statement - its checks refused the
            // program, or its request was not a request - must not leave
            // the thread that writes the frames waiting to be asked, and
            // the hook keeps a sender of its own, so the channel closing is
            // not what says so.
            let _ = holding.send(Holding::Settled);
            ended
        })
        .map_err(|e| format!("sabline-rt exec: no thread for the run: {e}"))?;

    // Once, before the first statement: hold this thread if the run asks,
    // and then start the thread that reads the answers - a thread this one
    // started, so that what holds this thread holds it too. The run's
    // thread always says it is settled, on every path it can end by, so the
    // channel going quiet means the run's thread panicked - and then there
    // is nothing left to read or to answer.
    let mut settled = false;
    loop {
        match holding_in.recv() {
            Err(_) => break,
            Ok(Holding::Me(hold_me, took)) => {
                let _ = took.send(usize::from(hold_me().is_none()));
            }
            Ok(Holding::Settled) => {
                settled = true;
                break;
            }
        }
    }
    if !settled {
        drop(lines);
    } else {
        // it reads until the input ends or the process does
        drop(
            std::thread::Builder::new()
                .spawn(move || {
                    let stdin = std::io::stdin();
                    let mut stdin = stdin.lock();
                    loop {
                        let mut line = String::new();
                        match stdin.read_line(&mut line) {
                            Ok(n) if n > 0 && lines.send(line).is_ok() => {}
                            _ => {
                                if RUNNING.load(Ordering::SeqCst)
                                    && !ENDED.load(Ordering::SeqCst)
                                {
                                    orphaned();
                                }
                                return;
                            }
                        }
                    }
                })
                .map_err(|e| format!("sabline-rt exec: no thread for the input: {e}"))?,
        );
    }

    let stdout = std::io::stdout();
    let mut stdout = stdout.lock();
    let mut write = |line: String| -> Result<(), String> {
        stdout
            .write_all(line.as_bytes())
            .and_then(|()| stdout.write_all(b"\n"))
            .and_then(|()| stdout.flush())
            .map_err(|_| "sabline-rt exec: standard output is closed".to_string())
    };
    // every frame as it is made, until the run lets go of the relay
    for line in frames_in {
        if write(line).is_err() {
            orphaned();
        }
    }
    let ended = run.join().map_err(|_| "sabline-rt exec: the run panicked")??;
    ENDED.store(true, Ordering::SeqCst);
    write(format!("{{\"end\":{ended}}}"))?;
    Ok(ExitCode::SUCCESS)
}

/// The header of the framed stream `budget --list` writes; the records are
/// framed as `ast --list`'s are, each named by its line's number.
const BUDGET_BATCH_HEADER: &str = "sabline.budget-batch/1";

/// One budget document per line of `list`. A line is a JSON array of two,
/// the budget's text and the effects it denies, each a string or `null`:
/// JSON, so that a tab, a comma or a character past ASCII in a budget
/// arrives as the Python package received it.
fn budget_list_of(list: &str) -> Result<ExitCode, String> {
    framed_budgets(list, BUDGET_BATCH_HEADER, |allow, deny| {
        sabline_rt::budget::budget_document(allow, deny)
    })
}

/// The header of the framed stream `os-policy --list` writes.
const POLICY_BATCH_HEADER: &str = sabline_rt::confine::POLICY_BATCH_HEADER;

/// One OS policy document per line of `list` (M4): what the operating
/// system is asked to hold for that budget, under `--confine strict` and
/// without it and under `--no-confine`. The lines are `budget --list`'s.
fn policy_list_of(list: &str) -> Result<ExitCode, String> {
    framed_budgets(list, POLICY_BATCH_HEADER, |allow, deny| {
        sabline_rt::confine::policy_document(allow, deny)
    })
}

/// A framed document per line of `list`, each line a JSON array of two,
/// the budget's text and the effects it denies, each a string or `null`:
/// JSON, so that a tab, a comma or a character past ASCII in a budget
/// arrives as the Python package received it.
fn framed_budgets<F>(list: &str, header: &str, document_of: F) -> Result<ExitCode, String>
where
    F: Fn(Option<&str>, Option<&str>) -> Json,
{
    let text = read_list(list)?;
    let mut every = true;
    out(format!("{header}\n").as_bytes())?;
    for (n, line) in text.lines().enumerate() {
        let line = line.trim_end_matches('\r');
        if line.is_empty() {
            continue;
        }
        let given =
            Json::parse(line).map_err(|e| format!("sabline-rt: line {}: {e}", n + 1))?;
        let field = |v: &Json| -> Result<Option<String>, String> {
            match v {
                Json::Null => Ok(None),
                Json::Str(s) => Ok(Some(s.clone())),
                _ => Err(format!("sabline-rt: line {}: a budget is text or null", n + 1)),
            }
        };
        let (allow, deny) = match &given {
            Json::List(pair) if pair.len() == 2 => (field(&pair[0])?, field(&pair[1])?),
            _ => return Err(format!("sabline-rt: line {} is not [allow, deny]", n + 1)),
        };
        let document = document_of(allow.as_deref(), deny.as_deref());
        every &=
            matches!(&document, Json::Obj(f) if f.get("valid") == Some(&Json::Bool(true)));
        let body = document.canonical();
        out(format!("--- {} {}\n", body.len(), n + 1).as_bytes())?;
        out(body.as_bytes())?;
        out(b"\n")?;
    }
    Ok(if every { ExitCode::SUCCESS } else { ExitCode::from(1) })
}

/// The document for one path, and whether it parsed.
fn document_of(path: &str) -> (Json, bool) {
    let document = match std::fs::read(path) {
        Ok(bytes) => dump_bytes(&bytes, path),
        Err(_) => sabline_rt::dump::error_document(&source::not_found(path)),
    };
    let ok = matches!(
        &document,
        Json::Obj(fields) if fields.get("ok") == Some(&Json::Bool(true))
    );
    (document, ok)
}

fn read_list(path: &str) -> Result<String, String> {
    if path == "-" {
        let mut text = String::new();
        std::io::stdin()
            .read_to_string(&mut text)
            .map_err(|e| format!("sabline-rt: cannot read the list on stdin: {e}"))?;
        return Ok(text);
    }
    std::fs::read_to_string(path)
        .map_err(|e| format!("sabline-rt: cannot read the list '{path}': {e}"))
}

/// Write bytes to standard output, so that a console code page cannot
/// change what a comparison sees.
fn out(payload: &[u8]) -> Result<(), String> {
    let stdout = std::io::stdout();
    let mut handle = stdout.lock();
    handle
        .write_all(payload)
        .and_then(|()| handle.flush())
        .map_err(|e| format!("sabline-rt: cannot write the dump: {e}"))
}

/// Write one document and the newline after it.
fn write_out(text: &str) -> Result<(), String> {
    out(text.as_bytes())?;
    out(b"\n")
}
