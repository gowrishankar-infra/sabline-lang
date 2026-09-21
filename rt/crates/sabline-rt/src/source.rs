//! Turning a file's bytes into the text the lexer sees.
//!
//! This is the stage that is easiest to get wrong by not writing it down,
//! because in Python it is not a stage at all - it is the default
//! arguments of `open`. `sabline/loader.py` opens a program with
//! `open(path, encoding="utf-8")`, and that one line decides three things
//! the lexer then depends on:
//!
//! 1. **UTF-8, strictly.** A byte sequence that is not UTF-8 raises
//!    `UnicodeDecodeError`, which the loader turns into E512 - and it
//!    says "cannot import" even for the file the user named on the
//!    command line, because the entry file goes through the same branch.
//!    That wording is the reference's, so it is this crate's too.
//! 2. **Universal newlines.** `\r\n` and a lone `\r` both become `\n`
//!    before the lexer sees them, so a file whose lines end in a lone `\r`
//!    has as many lines as it looks like it has. The lexer's own
//!    `[ \t\r]+` never sees a `\r` from a file - only from a program
//!    handed to the library as text.
//! 3. **The byte-order mark stays.** `encoding="utf-8"` is not
//!    `utf-8-sig`, so a file that starts with a BOM starts with U+FEFF,
//!    which no token pattern matches, and the program is E000 on line 1.
//!    That is a real Sabline behaviour and not an accident of this port.

use crate::errors::{Answer, SablineError};

/// The text the lexer sees, from a file's bytes.
///
/// `path` is only for the message, and is spelled into it exactly as the
/// reference spells the path it was given.
pub fn decode(bytes: &[u8], path: &str) -> Answer<String> {
    let text = std::str::from_utf8(bytes).map_err(|_| {
        SablineError::with_fixes(
            "E512",
            format!(
                "cannot import '{path}': it is not UTF-8 text, so it is not \
                 Sabline source"
            ),
            1,
            &["an import names a .vel file"],
        )
    })?;
    Ok(translate_newlines(text))
}

/// The refusal for a file that cannot be opened, as the loader gives it
/// for the entry program.
pub fn not_found(path: &str) -> SablineError {
    SablineError::with_fixes(
        "E001",
        format!("cannot find file '{path}'"),
        1,
        &["check the file name spelling", "make sure you are in the folder that contains it"],
    )
}

/// CPython's universal newlines: `\r\n` and a lone `\r` both become `\n`.
pub fn translate_newlines(text: &str) -> String {
    if !text.contains('\r') {
        return text.to_string();
    }
    let mut out = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\r' {
            if chars.peek() == Some(&'\n') {
                chars.next();
            }
            out.push('\n');
        } else {
            out.push(c);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newlines_are_translated_the_way_python_text_mode_translates_them() {
        assert_eq!(translate_newlines("a\r\nb"), "a\nb");
        assert_eq!(translate_newlines("a\rb"), "a\nb");
        assert_eq!(translate_newlines("a\r\r\nb"), "a\n\nb");
        assert_eq!(translate_newlines("a\nb"), "a\nb");
        assert_eq!(translate_newlines("a\n\rb"), "a\n\nb");
    }

    #[test]
    fn a_byte_order_mark_is_kept_and_becomes_e000_at_the_lexer() {
        let text = decode("\u{feff}fn main() { }".as_bytes(), "x.vel").expect("decodes");
        let refused = crate::lex(&text, false).expect_err("U+FEFF is no token");
        assert_eq!(refused.code, "E000");
        assert_eq!(refused.message, "unexpected character '\\ufeff'");
        assert_eq!(refused.line, 1);
    }

    #[test]
    fn bytes_that_are_not_utf8_are_e512_with_the_loaders_wording() {
        let refused = decode(b"fn main() { \xff }", "x.vel").expect_err("not UTF-8");
        assert_eq!(refused.code, "E512");
        assert_eq!(
            refused.message,
            "cannot import 'x.vel': it is not UTF-8 text, so it is not Sabline source"
        );
        assert_eq!(refused.line, 1);
    }
}
