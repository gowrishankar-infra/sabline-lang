//! A Sabline `Text` while a program runs: what CPython's `str` is.
//!
//! The reference runtime holds a Text in a Python `str`, which is a
//! sequence of code points - any of U+0000 to U+10FFFF, a lone surrogate
//! included - and every text builtin counts and compares in those:
//! `length` is how many code points, `code_at` gives one, `"b" < "ä"`
//! compares them one by one. Rust's `String` is UTF-8 bytes and cannot
//! hold a lone surrogate at all, and a lone surrogate reaches a program
//! the moment it reads `"\ud800"` out of a JSON document. So a [`Text`]
//! is a sequence of code points too, and every algorithm here is
//! CPython's, written against that sequence (plan/9.0.md, M3: the text
//! builtins come first, because this is where two runtimes differ).
//!
//! Where CPython reads its Unicode database - `upper`, `lower`, which
//! characters `repr` leaves alone - the answer comes from tables generated
//! from CPython (`unicode_text.rs`, `scripts/gen_unicode_text.py`), never
//! from Rust's own, which follow a different Unicode version.

use std::fmt;
use std::rc::Rc;

use crate::pyrepr::py_isspace;
use crate::unicode_nd::decimal_value;
use crate::unicode_text::{CASED, CASE_IGNORABLE, LOWER, PRINTABLE, UPPER};

/// A Text: code points, shared, never changed in place.
#[derive(Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Default)]
pub struct Text(Rc<[u32]>);

impl fmt::Debug for Text {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.repr())
    }
}

impl From<&str> for Text {
    fn from(s: &str) -> Self {
        Text(s.chars().map(|c| c as u32).collect())
    }
}

impl From<String> for Text {
    fn from(s: String) -> Self {
        Text::from(s.as_str())
    }
}

impl From<Vec<u32>> for Text {
    fn from(v: Vec<u32>) -> Self {
        Text(v.into())
    }
}

/// Whether a code point is a surrogate, which no `char` can be.
pub fn is_surrogate(c: u32) -> bool {
    (0xD800..=0xDFFF).contains(&c)
}

/// CPython's `str.isspace()` of one code point.
pub fn isspace(c: u32) -> bool {
    char::from_u32(c).is_some_and(py_isspace)
}

fn in_ranges(table: &[(u32, u32)], c: u32) -> bool {
    match table.binary_search_by(|&(a, _)| a.cmp(&c)) {
        Ok(_) => true,
        Err(0) => false,
        Err(i) => c <= table[i - 1].1,
    }
}

fn mapped(table: &[(u32, [u32; 3])], c: u32, out: &mut Vec<u32>) {
    match table.binary_search_by(|&(a, _)| a.cmp(&c)) {
        Ok(i) => out.extend(table[i].1.iter().copied().filter(|&m| m != 0)),
        Err(_) => out.push(c),
    }
}

/// CPython's `str.isprintable()` of one code point: what `repr()` writes
/// as itself.
pub fn isprintable(c: u32) -> bool {
    in_ranges(&PRINTABLE, c)
}

impl Text {
    /// The code points.
    pub fn points(&self) -> &[u32] {
        &self.0
    }

    /// How many code points: `len(s)`.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether it is `""`.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// `a + b`.
    pub fn concat(&self, other: &Text) -> Text {
        if other.is_empty() {
            return self.clone();
        }
        if self.is_empty() {
            return other.clone();
        }
        // collected straight into the shared buffer: one allocation and one
        // copy, where a Vec and then an Rc would be two of each
        Text(self.0.iter().chain(other.0.iter()).copied().collect())
    }

    /// `s[start:stop]`, for indexes already in range.
    pub fn slice(&self, start: usize, stop: usize) -> Text {
        Text(Rc::from(&self.0[start..stop]))
    }

    /// The text as a Rust string, when it holds no lone surrogate.
    pub fn to_str(&self) -> Option<String> {
        self.0.iter().map(|&c| char::from_u32(c)).collect()
    }

    /// The text as a Rust string with each lone surrogate written as
    /// U+FFFD: for a place where only a valid string will do and the
    /// difference cannot be observed.
    pub fn to_string_lossy(&self) -> String {
        self.0.iter().map(|&c| char::from_u32(c).unwrap_or('\u{fffd}')).collect()
    }

    /// The first index at or after `from` where `needle` starts.
    pub fn find(&self, needle: &Text, from: usize) -> Option<usize> {
        let (h, n) = (&self.0[..], &needle.0[..]);
        if n.is_empty() {
            return (from <= h.len()).then_some(from);
        }
        if n.len() > h.len() {
            return None;
        }
        (from..=h.len() - n.len()).find(|&i| h[i..i + n.len()] == *n)
    }

    /// `needle in s`.
    pub fn contains(&self, needle: &Text) -> bool {
        self.find(needle, 0).is_some()
    }

    /// `s.startswith(prefix)`.
    pub fn starts_with(&self, prefix: &str) -> bool {
        let mut it = self.0.iter();
        prefix.chars().all(|c| it.next() == Some(&(c as u32)))
    }

    /// `s.split(sep)` for a `sep` that is not empty.
    pub fn split(&self, sep: &Text) -> Vec<Text> {
        let mut out = Vec::new();
        let mut at = 0;
        while let Some(i) = self.find(sep, at) {
            out.push(self.slice(at, i));
            at = i + sep.len();
        }
        out.push(self.slice(at, self.len()));
        out
    }

    /// `list(s)`: one Text of one code point each.
    pub fn chars(&self) -> Vec<Text> {
        self.0.iter().map(|&c| Text::from(vec![c])).collect()
    }

    /// `s.upper()`.
    pub fn upper(&self) -> Text {
        let mut out = Vec::with_capacity(self.len());
        for &c in self.0.iter() {
            mapped(&UPPER, c, &mut out);
        }
        Text::from(out)
    }

    /// `s.lower()`, with the capital sigma written as CPython's
    /// `handle_capital_sigma` decides: `ς` after a cased letter and not
    /// before one, looking through case-ignorable characters both ways.
    pub fn lower(&self) -> Text {
        let s = &self.0;
        let mut out = Vec::with_capacity(self.len());
        for (i, &c) in s.iter().enumerate() {
            if c == 0x3A3 {
                out.push(if final_sigma(s, i) { 0x3C2 } else { 0x3C3 });
            } else {
                mapped(&LOWER, c, &mut out);
            }
        }
        Text::from(out)
    }

    /// `s.strip()`: CPython's white space off both ends.
    pub fn strip(&self) -> Text {
        self.strip_by(isspace)
    }

    /// `s.strip(chars)`.
    pub fn strip_chars(&self, chars: &str) -> Text {
        self.strip_by(|c| chars.chars().any(|k| k as u32 == c))
    }

    fn strip_by(&self, drop: impl Fn(u32) -> bool) -> Text {
        let s = &self.0;
        let start = s.iter().position(|&c| !drop(c)).unwrap_or(s.len());
        let stop = s.iter().rposition(|&c| !drop(c)).map_or(start, |i| i + 1);
        if start == 0 && stop == s.len() {
            return self.clone();
        }
        self.slice(start, stop.max(start))
    }

    /// `s.rstrip("\n")`.
    pub fn rstrip_newlines(&self) -> Text {
        let s = &self.0;
        let stop = s.iter().rposition(|&c| c != 0x0A).map_or(0, |i| i + 1);
        if stop == s.len() {
            return self.clone();
        }
        self.slice(0, stop)
    }

    /// `s.isdecimal()`.
    pub fn isdecimal(&self) -> bool {
        !self.is_empty()
            && self.0.iter().all(|&c| char::from_u32(c).and_then(decimal_value).is_some())
    }

    /// `s.isascii()`.
    pub fn isascii(&self) -> bool {
        self.0.iter().all(|&c| c < 0x80)
    }

    /// The decimal value of a text `isdecimal()` is true of, when it fits
    /// in 128 bits.
    pub fn decimal_value(&self) -> Option<i128> {
        let mut n: i128 = 0;
        for &c in self.0.iter() {
            let d = char::from_u32(c).and_then(decimal_value)?;
            n = n.checked_mul(10)?.checked_add(i128::from(d))?;
        }
        Some(n)
    }

    /// CPython's `repr()` of a str: single quotes unless the text holds a
    /// `'` and no `"`; backslash, the quote, tab, line feed and carriage
    /// return escaped by name; other controls and DEL as `\xhh`; a
    /// character past ASCII as itself when it is printable, else as
    /// `\xhh`, `\uhhhh` or `\Uhhhhhhhh`.
    pub fn repr(&self) -> String {
        let s = &self.0;
        let squote = s.contains(&0x27);
        let dquote = s.contains(&0x22);
        let quote = if squote && !dquote { '"' } else { '\'' };
        let mut out = String::with_capacity(s.len() + 2);
        out.push(quote);
        for &c in s.iter() {
            match c {
                _ if c == quote as u32 || c == 0x5C => {
                    out.push('\\');
                    out.push(char::from_u32(c).unwrap_or('?'));
                }
                0x09 => out.push_str("\\t"),
                0x0A => out.push_str("\\n"),
                0x0D => out.push_str("\\r"),
                _ if c < 0x20 || c == 0x7F => out.push_str(&format!("\\x{c:02x}")),
                _ if c < 0x7F => out.push(char::from_u32(c).unwrap_or('?')),
                _ if isprintable(c) => out.push(char::from_u32(c).unwrap_or('?')),
                _ if c <= 0xFF => out.push_str(&format!("\\x{c:02x}")),
                _ if c <= 0xFFFF => out.push_str(&format!("\\u{c:04x}")),
                _ => out.push_str(&format!("\\U{c:08x}")),
            }
        }
        out.push(quote);
        out
    }

    /// The text as CPython's `json` writes a string with
    /// `ensure_ascii=True` (`encode_basestring_ascii`), quotes included: a
    /// character past the basic plane as its surrogate pair, a lone
    /// surrogate as itself.
    pub fn write_json_ascii(&self, out: &mut String) {
        out.push('"');
        for &c in self.0.iter() {
            match c {
                0x22 => out.push_str("\\\""),
                0x5C => out.push_str("\\\\"),
                0x08 => out.push_str("\\b"),
                0x0C => out.push_str("\\f"),
                0x0A => out.push_str("\\n"),
                0x0D => out.push_str("\\r"),
                0x09 => out.push_str("\\t"),
                0x20..=0x7E => out.push(char::from_u32(c).unwrap_or('?')),
                0x10000.. => {
                    let v = c - 0x10000;
                    let hi = 0xD800 + (v >> 10);
                    let lo = 0xDC00 + (v & 0x3FF);
                    out.push_str(&format!("\\u{hi:04x}\\u{lo:04x}"));
                }
                _ => out.push_str(&format!("\\u{c:04x}")),
            }
        }
        out.push('"');
    }
}

fn final_sigma(s: &[u32], i: usize) -> bool {
    let ignorable = |c: u32| in_ranges(&CASE_IGNORABLE, c);
    let cased = |c: u32| in_ranges(&CASED, c);
    let before = s[..i].iter().rev().find(|&&c| !ignorable(c));
    if !before.is_some_and(|&c| cased(c)) {
        return false;
    }
    match s[i + 1..].iter().find(|&&c| !ignorable(c)) {
        None => true,
        Some(&c) => !cased(c),
    }
}

/// A Text being built a piece at a time.
#[derive(Default, Debug, Clone)]
pub struct TextBuf(Vec<u32>);

impl TextBuf {
    /// An empty one.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a Rust string.
    pub fn str(mut self, s: &str) -> Self {
        self.push_str(s);
        self
    }

    /// Add a Text.
    pub fn text(mut self, t: &Text) -> Self {
        self.push_text(t);
        self
    }

    /// Add a Rust string, in place.
    pub fn push_str(&mut self, s: &str) {
        self.0.extend(s.chars().map(|c| c as u32));
    }

    /// Add a Text, in place.
    pub fn push_text(&mut self, t: &Text) {
        self.0.extend_from_slice(t.points());
    }

    /// What has been built.
    pub fn done(self) -> Text {
        Text::from(self.0)
    }

    /// How many code points so far.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether nothing has been added.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

/// Where a value is written out: a [`TextBuf`], which keeps what is
/// written, or a [`Measure`], which only counts it. The writers in
/// `value.rs` write to either, so what a Measure counts is what a TextBuf
/// would hold, by construction (9.0, M3: the size limit counts what an
/// operation writes out before it is made).
pub trait Sink {
    /// Add a Rust string.
    fn push_str(&mut self, s: &str);
    /// Add a Text.
    fn push_text(&mut self, t: &Text);
    /// Whether nothing more need be written: a Measure past its room.
    fn full(&self) -> bool {
        false
    }
}

impl Sink for TextBuf {
    fn push_str(&mut self, s: &str) {
        TextBuf::push_str(self, s);
    }

    fn push_text(&mut self, t: &Text) {
        TextBuf::push_text(self, t);
    }
}

/// A code point's UTF-8 bytes, a lone surrogate three, as
/// `runtime.size_of` counts them.
pub fn utf8_bytes(c: u32) -> u64 {
    match c {
        0..=0x7F => 1,
        0x80..=0x7FF => 2,
        0x800..=0xFFFF => 3,
        _ => 4,
    }
}

/// Whether a log line writes `c` as an escape: `values._LOG_CONTROL`, every
/// C0 control but tab, DEL, C1, and the two Unicode separators.
pub fn log_control(c: u32) -> bool {
    c <= 0x08
        || (0x0A..=0x1F).contains(&c)
        || (0x7F..=0x9F).contains(&c)
        || c == 0x2028
        || c == 0x2029
}

/// What a log line makes of `c`, in bytes: `\n` and `\r` two, `\xNN` four,
/// `\uNNNN` six, and anything else its UTF-8.
pub fn log_bytes(c: u32) -> u64 {
    if !log_control(c) {
        utf8_bytes(c)
    } else if c == 0x0A || c == 0x0D {
        2
    } else if c < 0x100 {
        4
    } else {
        6
    }
}

/// A [`Sink`] that counts the UTF-8 bytes written - or, made with
/// [`Measure::log`], the bytes `log_line` would make of them - and is full
/// once the count is past its room, so that measuring a value that writes
/// out far past the size limit costs no more than the limit.
pub struct Measure {
    bytes: u64,
    room: u64,
    log: bool,
}

impl Measure {
    /// Counting UTF-8 bytes, full past `room`.
    pub fn new(room: u64) -> Self {
        Measure { bytes: 0, room, log: false }
    }

    /// Counting what a log line makes, full past `room`.
    pub fn log(room: u64) -> Self {
        Measure { bytes: 0, room, log: true }
    }

    /// What has been counted: exact while it is no more than the room.
    pub fn bytes(&self) -> u64 {
        self.bytes
    }

    fn add(&mut self, c: u32) {
        self.bytes += if self.log { log_bytes(c) } else { utf8_bytes(c) };
    }
}

impl Sink for Measure {
    fn push_str(&mut self, s: &str) {
        for c in s.chars() {
            self.add(c as u32);
        }
    }

    fn push_text(&mut self, t: &Text) {
        for &c in t.points() {
            self.add(c);
        }
    }

    fn full(&self) -> bool {
        self.bytes > self.room
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(s: &str) -> Text {
        Text::from(s)
    }

    #[test]
    fn case_follows_cpython() {
        assert_eq!(t("straße").upper(), t("STRASSE"));
        assert_eq!(t("ﬁ").upper(), t("FI"));
        assert_eq!(t("İ").lower(), t("i\u{307}"));
        assert_eq!(t("ΟΔΟΣ").lower(), t("οδος"));
        assert_eq!(t("ΟΔΟΣ ΑΣ").lower(), t("οδος ας"));
        assert_eq!(t("Σ").lower(), t("σ"));
        assert_eq!(t("ΑΣΑ").lower(), t("ασα"));
        assert_eq!(t("Α'Σ").lower(), t("α'ς"));
        let lone = Text::from(vec![0xD800, 0x61]);
        assert_eq!(lone.upper(), Text::from(vec![0xD800, 0x41]));
    }

    #[test]
    fn repr_follows_cpython() {
        assert_eq!(t("a").repr(), "'a'");
        assert_eq!(t("it's").repr(), "\"it's\"");
        assert_eq!(t("'\"").repr(), "'\\'\"'");
        assert_eq!(t("a\nb\t\\").repr(), "'a\\nb\\t\\\\'");
        assert_eq!(t("\u{0}\u{7f}é\u{85}\u{a0}").repr(), "'\\x00\\x7fé\\x85\\xa0'");
        assert_eq!(Text::from(vec![0xDC80]).repr(), "'\\udc80'");
        assert_eq!(t("\u{e000}😀").repr(), "'\\ue000😀'");
    }

    #[test]
    fn split_and_strip_follow_cpython() {
        assert_eq!(t("a,,b,").split(&t(",")), vec![t("a"), t(""), t("b"), t("")]);
        assert_eq!(t("aaa").split(&t("aa")), vec![t(""), t("a")]);
        assert_eq!(t("\u{1c} x \u{3000}").strip(), t("x"));
        assert_eq!(t("x\n\n").rstrip_newlines(), t("x"));
        assert!(t("").contains(&t("")));
    }

    #[test]
    fn json_ascii_is_encode_basestring_ascii() {
        let mut out = String::new();
        Text::from(vec![0x22, 0x7F, 0xE9, 0x1F600, 0xD800]).write_json_ascii(&mut out);
        assert_eq!(out, "\"\\\"\\u007f\\u00e9\\ud83d\\ude00\\ud800\"");
    }
}
