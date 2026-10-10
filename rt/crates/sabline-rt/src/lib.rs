//! sabline-rt: the Sabline runtime, in Rust.
//!
//! `decisions/0002-runtime-in-rust.md` says what this crate is for and
//! what stays in the Python package; `plan/9.0.md` is the ladder it
//! climbs. **It holds a lexer, a parser, from M2 the loader, the checkers
//! and the budget parser** - effects, types with `Secret of T` and `Money
//! of C`, the rules for `main`, each loop's termination verdict, and what
//! a budget grants - **and from M3 the interpreter**: a program run under a
//! budget, every builtin spent against it, and the work of every builtin
//! short of the network, Python and a tool ([`interp`], [`host`]). The work
//! of those three is not ported yet; a budget that does not grant them
//! refuses them first, as the reference does. It records each run's
//! receipt ([`receipt`]) into the run document the gate compares. It does
//! not prove, does not hold a budget at the operating system, and has no
//! command that runs a program for you.
//! Do not use it to decide whether a program is safe to run: the Python
//! package is what does that, and it is the reference.
//!
//! What it claims is checked on every commit: for every Sabline source this
//! project has, sabline-rt builds the same tree the Python parser builds,
//! or refuses it with the same code, the same message, the same fixes and
//! the same line; its checkers find what `sabline check` finds, stage by
//! stage and message for message; its budget parser reads every budget
//! the gate holds to the same grants, or the same refusal; and a run of
//! every program under the budget `io`, and of every program written for a
//! budget under its own, prints what the reference prints, ends with its
//! status, stops with its error and records its receipt.
//! `check_agreement.py` is what says so;
//! rt/README.md says how to run it.
//!
//! ```
//! use sabline_rt::{lex, Parser};
//!
//! let tokens = lex("fn main() uses io { print(\"hi\") }", false).unwrap();
//! let program = Parser::new(tokens).parse_program().unwrap();
//! assert_eq!(program.funcs[0].name, "main");
//! assert_eq!(program.funcs[0].effects, vec!["io"]);
//!
//! let mut problems = Vec::new();
//! sabline_rt::checker::check_main(&program.funcs, &mut problems, true);
//! sabline_rt::effects::check_effects(&program.funcs, ".", &mut problems);
//! sabline_rt::checker::check_types(&program.funcs, &program.records, &mut problems).unwrap();
//! assert!(problems.is_empty());
//! ```
//!
//! # No `unsafe`
//!
//! The crate is `unsafe_code = "forbid"` at the workspace root, so there
//! is none and none can be added without changing that line. When a later
//! alpha has to - Landlock, seccomp, `sandbox_init`, the AppContainer, the
//! C ABI - rt/README.md's rule applies: every block carries a `// SAFETY:`
//! comment naming the invariant that makes it sound and the test that
//! would fail if the invariant were broken, and a lint job refuses a block
//! without one.

#![forbid(unsafe_code)]
#![deny(missing_docs)]

pub mod bigint;
pub mod budget;
pub mod check_dump;
pub mod checker;
pub mod digest;
pub mod dump;
pub mod effects;
pub mod errors;
pub mod exec;
pub mod host;
pub mod interp;
pub mod json;
pub mod lexer;
pub mod loader;
pub mod nodes;
pub mod parser;
pub mod pyjson;
pub mod pypath;
pub mod pyrepr;
pub mod receipt;
pub mod run_dump;
pub mod show;
pub mod source;
pub mod tables;
pub mod termination;
pub mod text;
pub mod types;
pub mod unicode_digit;
pub mod unicode_nd;
pub mod unicode_text;
pub mod value;

pub use errors::{Answer, SablineError};
pub use lexer::{lex, Token};
pub use nodes::Program;
pub use parser::Parser;

/// The crate's version, which is the alpha's version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Read a source text and answer the canonical dump document for it.
///
/// The text is what `source::decode` gives: valid UTF-8 with newlines
/// already translated the way CPython's text mode translates them.
pub fn dump_source(text: &str) -> json::Json {
    match lex(text, false).and_then(|tokens| Parser::new(tokens).parse_program()) {
        Ok(program) => dump::program_document(&program),
        Err(refused) => dump::error_document(&refused),
    }
}

/// Read a file's bytes and answer the canonical dump document for them.
pub fn dump_bytes(bytes: &[u8], path: &str) -> json::Json {
    match source::decode(bytes, path) {
        Ok(text) => dump_source(&text),
        Err(refused) => dump::error_document(&refused),
    }
}

/// The stack a parse runs on, and the reason there is one.
///
/// The parser is recursive, and its caps let a program nest 4,000 blocks
/// and 1,000 expressions deep before E102 - deeper than a default thread
/// stack carries, and deeper than the 8 MB a main thread usually gets.
/// The reference does the same thing for the same reason: `load_program`
/// raises CPython's recursion limit to 20,000 before it parses.
///
/// A stack overflow is not a panic: it is the process going away with no
/// message, which is worse than any refusal. So it is not enough for the
/// parser to be correct - every entry point that parses runs the parse
/// here, and `tests/limits.rs` measures the deepest program the parser
/// accepts against this number. The measurement on the machine that wrote
/// this was 8 MB for a release build and 32 MB for a debug one, so the
/// number below is four times the worse of the two.
pub const PARSE_STACK: usize = 128 * 1024 * 1024;

/// Run `work` on a thread with [`PARSE_STACK`] bytes of stack.
///
/// Every value `work` builds is dropped inside it, because dropping a
/// deeply nested tree is as recursive as building one.
///
/// # Panics
///
/// Panics only if the thread cannot be started, or if `work` itself
/// panicked - which is a defect in this crate, never an answer to an
/// input.
pub fn on_parse_stack<T, F>(work: F) -> T
where
    F: FnOnce() -> T + Send + 'static,
    T: Send + 'static,
{
    std::thread::Builder::new()
        .stack_size(PARSE_STACK)
        .spawn(work)
        .expect("a thread for the parse")
        .join()
        .expect("the parse thread did not panic")
}
