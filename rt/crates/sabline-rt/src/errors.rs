//! `SablineError`, the one shape a refusal takes.
//!
//! The mirror of `sabline/errors.py`'s class: a code, a message, the line
//! it is about, the fixes offered under it, and - once the loader or a
//! checker has said so - the file it is about. The lexer and the parser
//! give E000, E001, E002, E100, E101, E102, E407, E511, E512 and E562; the
//! loader and the checkers (9.0, M2) give the rest of what `sabline check`
//! reports.

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
    /// The file it is about, when a stage has said; `None` means the file
    /// the caller asked about, which is what `err.file or path` reads in
    /// Python.
    pub file: Option<String>,
}

impl SablineError {
    /// A refusal with no fixes offered.
    pub fn new(code: &'static str, message: impl Into<String>, line: u32) -> Self {
        Self { code, message: message.into(), line, fixes: Vec::new(), file: None }
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
            file: None,
        }
    }

    /// A refusal whose fixes are built at run time, in Python's order.
    pub fn with_owned_fixes(
        code: &'static str,
        message: impl Into<String>,
        line: u32,
        fixes: Vec<String>,
    ) -> Self {
        Self { code, message: message.into(), line, fixes, file: None }
    }

    /// The same refusal, about `file`.
    pub fn in_file(mut self, file: impl Into<String>) -> Self {
        self.file = Some(file.into());
        self
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
