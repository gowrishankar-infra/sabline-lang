//! `sabline-rt`: the crate's command line.
//!
//! One command in 9.0.0-alpha.1:
//!
//! ```text
//! sabline-rt ast <file.vel>        the canonical dump of one file
//! sabline-rt ast --list <paths>    one dump per line of <paths>, framed
//! sabline-rt --version
//! ```
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
