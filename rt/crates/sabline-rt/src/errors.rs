//! `SablineError`, the one shape a refusal takes.
//!
//! The mirror of `sabline/errors.py`'s class: a code, a message, the line
//! it is about, and the fixes offered under it. The codes this alpha can
//! give are E000, E001, E002, E100, E101, E102, E407, E511, E512 and
//! E562: every code `sabline/lexer.py` and `sabline/parser.py` raise,
//! plus the two the loader gives for an entry file it cannot read.

use std::fmt;

/// A refusal, with the code and the message the Python implementation
/// gives for the same input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SablineError {
    /// The error code, as `sabline/errors.py`'s `ERROR_TABLE` lists it.
    pub code: &'static str,
    /// The message, character for character what Python writes.
    pub message: String,
    /// The line the error is about, counting from one.
    pub line: u32,
    /// What to do about it, in the order Python offers them.
    pub fixes: Vec<String>,
}

impl SablineError {
    /// A refusal with no fixes offered.
    pub fn new(code: &'static str, message: impl Into<String>, line: u32) -> Self {
        Self { code, message: message.into(), line, fixes: Vec::new() }
    }

    /// A refusal with the fixes Python offers under it, in Python's order.
    pub fn with_fixes(
        code: &'static str,
        message: impl Into<String>,
        line: u32,
        fixes: &[&str],
    ) -> Self {
        Self {
            code,
            message: message.into(),
            line,
            fixes: fixes.iter().map(|f| (*f).to_string()).collect(),
        }
    }
}

impl fmt::Display for SablineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "error[{}] {} (line {})", self.code, self.message, self.line)
    }
}

impl std::error::Error for SablineError {}

/// What a stage answers: a value, or the one refusal that stopped it.
pub type Answer<T> = Result<T, SablineError>;
