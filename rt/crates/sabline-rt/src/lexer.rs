//! Stage 1, the lexer: source text into tokens.
//!
//! `sabline/lexer.py` is one `re` alternation matched at each position, and
//! `re` takes the **first** branch that matches, not the longest. This is
//! that alternation, in that order, written out:
//!
//! | branch | pattern |
//! |---|---|
//! | `COMMENT` | `//[^\n]*` |
//! | `NEWLINE` | `\n` |
//! | `SKIP` | `[ \t\r]+` |
//! | `ARROW` | `->` |
//! | `FLOAT` | `\d+\.\d+` |
//! | `NUMBER` | `\d+` |
//! | `STRING` | `"(?:\\.|[^"\\\n])*"` |
//! | `IDENT` | `[A-Za-z_][A-Za-z0-9_]*` |
//! | `OP` | `==\|!=\|<=\|>=\|[+\-*/%<>=(){},:\[\].]` |
//!
//! Two of those are not what a reader would guess and are the reason this
//! file is written out rather than driven by a regex crate:
//!
//! - `\d` in a `str` pattern is **every Unicode decimal digit**, so
//!   `let x = ١٢` is `Num(12)` in Python, because `int()` converts by each
//!   character's decimal value. `unicode_nd.rs` carries that set.
//! - `[A-Za-z_]` is ASCII, so a non-ASCII letter is E000 and not an
//!   identifier. The two rules disagree about what "a character" is, and
//!   both are copied here rather than reconciled.

use crate::errors::{Answer, SablineError};
use crate::pyrepr::ascii_char;
use crate::unicode_nd::is_digit;

/// The keywords, exactly `sabline/lexer.py`'s `KEYWORDS`.
///
/// `ok`, `as`, `any`, `in`, `to` and `of` are **not** here: each is an
/// ordinary identifier that one grammar rule happens to require, so a
/// program may still use them as names.
pub const KEYWORDS: [&str; 21] = [
    "fn",
    "let",
    "return",
    "if",
    "else",
    "uses",
    "true",
    "false",
    "while",
    "requires",
    "ensures",
    "and",
    "or",
    "not",
    "invariant",
    "record",
    "import",
    "fail",
    "check",
    "try",
    "for",
];

/// What a token is, spelled as `sabline/lexer.py` spells `Token.kind`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// `//` to the end of the line; kept only with trivia.
    Comment,
    /// One `\n`; kept only with trivia.
    Newline,
    /// A number with no decimal point.
    Number,
    /// A number with a decimal point.
    Float,
    /// A text literal, quotes included.
    Str,
    /// A name that is not a keyword.
    Ident,
    /// A name that is.
    Keyword,
    /// An operator or a bracket.
    Op,
    /// `->`.
    Arrow,
    /// The end of the token list.
    Eof,
}

impl Kind {
    /// The spelling `Token.kind` has in Python, which is what an E100
    /// message falls back to when no text is asked for.
    pub fn name(self) -> &'static str {
        match self {
            Kind::Comment => "COMMENT",
            Kind::Newline => "NEWLINE",
            Kind::Number => "NUMBER",
            Kind::Float => "FLOAT",
            Kind::Str => "STRING",
            Kind::Ident => "IDENT",
            Kind::Keyword => "KEYWORD",
            Kind::Op => "OP",
            Kind::Arrow => "ARROW",
            Kind::Eof => "EOF",
        }
    }
}

/// One token: what it is, the source text it was made of, and its line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Token {
    /// What it is.
    pub kind: Kind,
    /// Its source text. Empty for `NEWLINE` and `EOF`.
    pub text: String,
    /// The line it starts on, counting from one.
    pub line: u32,
}

impl Token {
    fn new(kind: Kind, text: impl Into<String>, line: u32) -> Self {
        Self { kind, text: text.into(), line }
    }
}

fn is_keyword(text: &str) -> bool {
    KEYWORDS.contains(&text)
}

fn ident_start(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}

fn ident_rest(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// Turn source text into tokens, as `lex(source, keep_trivia)` does.
///
/// The source is a slice of code points because Python indexes a `str` by
/// code point, and E000 names `source[pos]`.
pub fn lex(source: &str, keep_trivia: bool) -> Answer<Vec<Token>> {
    let chars: Vec<char> = source.chars().collect();
    let mut tokens: Vec<Token> = Vec::new();
    let mut line: u32 = 1;
    let mut pos = 0usize;
    while pos < chars.len() {
        let c = chars[pos];
        let next = chars.get(pos + 1).copied();

        // COMMENT: //[^\n]*
        if c == '/' && next == Some('/') {
            let start = pos;
            while pos < chars.len() && chars[pos] != '\n' {
                pos += 1;
            }
            if keep_trivia {
                let text: String = chars[start..pos].iter().collect();
                tokens.push(Token::new(Kind::Comment, text.trim_end(), line));
            }
            continue;
        }
        // NEWLINE: \n
        if c == '\n' {
            if keep_trivia {
                tokens.push(Token::new(Kind::Newline, "", line));
            }
            line += 1;
            pos += 1;
            continue;
        }
        // SKIP: [ \t\r]+
        if matches!(c, ' ' | '\t' | '\r') {
            while pos < chars.len() && matches!(chars[pos], ' ' | '\t' | '\r') {
                pos += 1;
            }
            continue;
        }
        // ARROW: ->
        if c == '-' && next == Some('>') {
            tokens.push(Token::new(Kind::Arrow, "->", line));
            pos += 2;
            continue;
        }
        // FLOAT: \d+\.\d+ , then NUMBER: \d+
        //
        // `\d+` cannot usefully give ground: shortening it puts a digit
        // where `\.` must match, so FLOAT matches exactly when the run of
        // digits is followed by a dot and then one more digit.
        if is_digit(c) {
            let start = pos;
            while pos < chars.len() && is_digit(chars[pos]) {
                pos += 1;
            }
            let dot = pos;
            if chars.get(dot) == Some(&'.')
                && chars.get(dot + 1).copied().is_some_and(is_digit)
            {
                pos = dot + 1;
                while pos < chars.len() && is_digit(chars[pos]) {
                    pos += 1;
                }
                let text: String = chars[start..pos].iter().collect();
                tokens.push(Token::new(Kind::Float, text, line));
            } else {
                let text: String = chars[start..pos].iter().collect();
                tokens.push(Token::new(Kind::Number, text, line));
            }
            continue;
        }
        // STRING: "(?:\\.|[^"\\\n])*"
        //
        // Greedy, and giving ground never helps: every position the scan
        // passes holds something other than a quote, except a quote that
        // `\\.` took, and giving that back leaves a backslash where the
        // closing quote must be. So an unterminated literal is not a
        // shorter match - it is no match, and the opening quote falls
        // through to E000, which is what Python does.
        if c == '"' {
            if let Some(end) = string_end(&chars, pos) {
                let text: String = chars[pos..end].iter().collect();
                tokens.push(Token::new(Kind::Str, text, line));
                pos = end;
                continue;
            }
        }
        // IDENT: [A-Za-z_][A-Za-z0-9_]*  (ASCII)
        if ident_start(c) {
            let start = pos;
            while pos < chars.len() && ident_rest(chars[pos]) {
                pos += 1;
            }
            let text: String = chars[start..pos].iter().collect();
            let kind = if is_keyword(&text) { Kind::Keyword } else { Kind::Ident };
            tokens.push(Token::new(kind, text, line));
            continue;
        }
        // OP: ==|!=|<=|>=|[+\-*/%<>=(){},:\[\].]
        if let Some(second) = next {
            let two = matches!((c, second), ('=', '=') | ('!', '=') | ('<', '=') | ('>', '='));
            if two {
                let text: String = [c, second].iter().collect();
                tokens.push(Token::new(Kind::Op, text, line));
                pos += 2;
                continue;
            }
        }
        if matches!(
            c,
            '+' | '-'
                | '*'
                | '/'
                | '%'
                | '<'
                | '>'
                | '='
                | '('
                | ')'
                | '{'
                | '}'
                | ','
                | ':'
                | '['
                | ']'
                | '.'
        ) {
            tokens.push(Token::new(Kind::Op, c.to_string(), line));
            pos += 1;
            continue;
        }
        return Err(SablineError::with_fixes(
            "E000",
            format!("unexpected character {}", ascii_char(c)),
            line,
            &["remove or replace this character"],
        ));
    }
    tokens.push(Token::new(Kind::Eof, "", line));
    Ok(tokens)
}

/// Where the text literal starting at `open` ends, one past its closing
/// quote; `None` when it does not end.
fn string_end(chars: &[char], open: usize) -> Option<usize> {
    let mut i = open + 1;
    while i < chars.len() {
        match chars[i] {
            '"' => return Some(i + 1),
            '\n' => return None,
            '\\' => {
                // `\\.` takes the backslash and one character that is not a
                // newline; `.` does not match `\n` and the class cannot
                // take a backslash, so this is where it ends.
                match chars.get(i + 1) {
                    Some('\n') | None => return None,
                    Some(_) => i += 2,
                }
            }
            _ => i += 1,
        }
    }
    None
}

/// The escapes a text literal knows, as `sabline/lexer.py`'s `ESCAPES`.
fn escape_of(c: char) -> Option<char> {
    match c {
        'n' => Some('\n'),
        't' => Some('\t'),
        '"' => Some('"'),
        '\\' => Some('\\'),
        _ => None,
    }
}

/// Read a text literal's contents, as `unescape(raw, line)` does.
///
/// `raw` is the literal without its quotes.
pub fn unescape(raw: &str, line: u32) -> Answer<String> {
    let chars: Vec<char> = raw.chars().collect();
    let mut out = String::with_capacity(raw.len());
    let mut i = 0usize;
    while i < chars.len() {
        if chars[i] == '\\' {
            i += 1;
            // Python reads one past the end as the empty string, and the
            // empty string is not a known escape.
            let e = chars.get(i).copied();
            match e.and_then(escape_of) {
                Some(value) => out.push(value),
                None => {
                    let shown = e.map(String::from).unwrap_or_default();
                    return Err(SablineError::with_fixes(
                        "E002",
                        format!("unknown escape '\\{shown}' in text"),
                        line,
                        &["known escapes: \\n (newline), \\t (tab), \
                             \\\" (quote), \\\\ (backslash)"],
                    ));
                }
            }
        } else {
            out.push(chars[i]);
        }
        i += 1;
    }
    Ok(out)
}

/// `fmt_fn_type(param_types, ret)`: a function type as one string.
pub fn fmt_fn_type(params: &[String], ret: Option<&str>) -> String {
    let mut s = format!("fn({})", params.join(", "));
    match ret {
        Some(r) if r != "Unit" => {
            s.push_str(" -> ");
            s.push_str(r);
        }
        _ => {}
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kinds(source: &str) -> Vec<(Kind, String)> {
        lex(source, false).expect("lexes").into_iter().map(|t| (t.kind, t.text)).collect()
    }

    #[test]
    fn keyword_list_matches_python() {
        assert_eq!(KEYWORDS.len(), 21);
        for w in KEYWORDS {
            assert!(is_keyword(w), "{w} is a keyword");
        }
        assert!(!is_keyword("ok"), "'ok' is an identifier, not a keyword");
        assert!(!is_keyword("as"), "'as' is an identifier, not a keyword");
        assert!(!is_keyword("any"), "'any' is an identifier");
        assert!(!is_keyword("in"), "'in' is an identifier");
        assert!(!is_keyword("to"), "'to' is an identifier");
        assert!(!is_keyword("of"), "'of' is an identifier");
    }

    #[test]
    fn float_needs_a_digit_after_the_dot() {
        assert_eq!(
            kinds("12.34"),
            vec![(Kind::Float, "12.34".into()), (Kind::Eof, String::new())]
        );
        assert_eq!(
            kinds("12."),
            vec![
                (Kind::Number, "12".into()),
                (Kind::Op, ".".into()),
                (Kind::Eof, String::new())
            ]
        );
        assert_eq!(
            kinds("12..3"),
            vec![
                (Kind::Number, "12".into()),
                (Kind::Op, ".".into()),
                (Kind::Op, ".".into()),
                (Kind::Number, "3".into()),
                (Kind::Eof, String::new())
            ]
        );
        assert_eq!(
            kinds("12.34.56"),
            vec![
                (Kind::Float, "12.34".into()),
                (Kind::Op, ".".into()),
                (Kind::Number, "56".into()),
                (Kind::Eof, String::new())
            ]
        );
    }

    #[test]
    fn unicode_digits_are_numbers_and_ascii_letters_are_not_identifiers() {
        assert_eq!(kinds("\u{661}\u{662}")[0], (Kind::Number, "\u{661}\u{662}".into()));
        let refused = lex("\u{b2}", false).expect_err("superscript two is not a digit");
        assert_eq!(refused.code, "E000");
        assert_eq!(refused.message, "unexpected character '\\xb2'");
        let refused =
            lex("caf\u{e9}", false).expect_err("a non-ASCII letter is not an identifier");
        assert_eq!(refused.code, "E000");
        assert_eq!(refused.message, "unexpected character '\\xe9'");
    }

    #[test]
    fn an_unterminated_literal_is_e000_on_its_opening_quote() {
        for source in ["\"abc", "\"ab\nc\"", "\"\\", "\"\\\""] {
            let refused = lex(source, false).expect_err("does not lex");
            assert_eq!(refused.code, "E000", "{source:?}");
            assert_eq!(refused.message, "unexpected character '\"'", "{source:?}");
        }
    }

    #[test]
    fn an_escaped_quote_stays_inside_the_literal() {
        assert_eq!(
            kinds("\"a\\\"b\""),
            vec![(Kind::Str, "\"a\\\"b\"".into()), (Kind::Eof, String::new())]
        );
    }

    #[test]
    fn comments_and_newlines_move_the_line() {
        let tokens = lex("// one\nlet\n\nx", false).expect("lexes");
        assert_eq!(tokens[0].line, 2);
        assert_eq!(tokens[1].line, 4);
        assert_eq!(tokens[2].kind, Kind::Eof);
        assert_eq!(tokens[2].line, 4);
    }

    #[test]
    fn bang_alone_is_not_an_operator() {
        let refused = lex("!", false).expect_err("'!' alone is no token");
        assert_eq!(refused.code, "E000");
        assert_eq!(refused.message, "unexpected character '!'");
        assert_eq!(kinds("!=")[0], (Kind::Op, "!=".into()));
    }

    #[test]
    fn unescape_reads_the_four_escapes_and_refuses_the_rest() {
        assert_eq!(unescape("a\\nb", 1).expect("reads"), "a\nb");
        assert_eq!(unescape("a\\\\b", 1).expect("reads"), "a\\b");
        let refused = unescape("a\\qb", 3).expect_err("\\q is unknown");
        assert_eq!(refused.code, "E002");
        assert_eq!(refused.message, "unknown escape '\\q' in text");
        assert_eq!(refused.line, 3);
    }
}
