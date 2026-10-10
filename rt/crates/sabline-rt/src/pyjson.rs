//! What CPython's `json.loads`, `json.dumps(..., ensure_ascii=False)`,
//! `int(str)` and `float(str)` do, for the `json_` builtins and `json_of`.
//!
//! `sabline/runtime.py` reads a document with `json.loads` and writes one
//! with `json.dumps`, and what a program sees of both is CPython's: which
//! texts parse, the value each gives (`1.0` a float, `1` an int, a key
//! given twice keeping its first place and its last value), and - since a
//! failed read is a failure whose reason the program can print - the
//! decoder's message, word for word, with its line, column and character.
//! The decoder here is a transliteration of `_json.c`'s scanner, as it is
//! in CPython 3.10 to 3.12.
//!
//! Two things CPython words by version, and the reference words as 3.12
//! does on every CPython (`values.read_json`, 9.0 M3), so this copies
//! 3.12: from 3.13 a comma before a closing bracket is "Illegal trailing
//! comma before end of object/array" at the comma, where 3.12 says
//! "Expecting property name enclosed in double quotes" or "Expecting
//! value" at the bracket; and a whole number past 4,300 digits, which 3.10
//! refuses "(4300)" and 3.12 "(4300 digits)".

use std::rc::Rc;

use crate::bigint::BigInt;
use crate::pyrepr::py_float_repr;
use crate::text::{is_surrogate, isspace, Text};
use crate::unicode_nd::decimal_value;
use crate::value::{fresh_float, Dict, Value};

/// CPython's default `sys.get_int_max_str_digits()`.
const INT_MAX_STR_DIGITS: usize = 4300;

/// Why `json.loads` refused a text: `str(JSONDecodeError)`.
fn decode_error(msg: &str, doc: &[u32], pos: usize) -> String {
    let lineno = doc[..pos].iter().filter(|&&c| c == 0x0A).count() + 1;
    let colno = match doc[..pos].iter().rposition(|&c| c == 0x0A) {
        Some(nl) => pos - nl,
        None => pos + 1,
    };
    format!("{msg}: line {lineno} column {colno} (char {pos})")
}

struct Scanner<'a> {
    s: &'a [u32],
}

/// What stopped a scan: the decoder's message, or the `StopIteration` of
/// "no value here", which the caller turns into "Expecting value".
enum Halt {
    Error(String),
    NoValue(usize),
}

fn is_ws(c: u32) -> bool {
    matches!(c, 0x20 | 0x09 | 0x0A | 0x0D)
}

fn is_digit(c: u32) -> bool {
    (0x30..=0x39).contains(&c)
}

impl Scanner<'_> {
    fn at(&self, i: usize) -> u32 {
        self.s[i]
    }

    fn skip_ws(&self, mut idx: usize) -> usize {
        while idx < self.s.len() && is_ws(self.at(idx)) {
            idx += 1;
        }
        idx
    }

    fn err(&self, msg: &str, pos: usize) -> Halt {
        Halt::Error(decode_error(msg, self.s, pos))
    }

    fn word(&self, idx: usize, word: &str) -> bool {
        let w: Vec<u32> = word.chars().map(|c| c as u32).collect();
        idx + w.len() <= self.s.len() && self.s[idx..idx + w.len()] == w[..]
    }

    fn scan_once(&self, idx: usize) -> Result<(Value, usize), Halt> {
        let length = self.s.len();
        if idx >= length {
            return Err(Halt::NoValue(idx));
        }
        match self.at(idx) {
            0x22 => return self.scanstring(idx + 1).map(|(t, end)| (Value::Text(t), end)),
            0x7B => return self.parse_object(idx + 1),
            0x5B => return self.parse_array(idx + 1),
            0x6E if self.word(idx, "null") => return Ok((Value::None, idx + 4)),
            0x74 if self.word(idx, "true") => return Ok((Value::Bool(true), idx + 4)),
            0x66 if self.word(idx, "false") => return Ok((Value::Bool(false), idx + 5)),
            0x4E if self.word(idx, "NaN") => {
                return Ok((Value::Float(fresh_float(f64::NAN)), idx + 3))
            }
            0x49 if self.word(idx, "Infinity") => {
                return Ok((Value::Float(f64::INFINITY), idx + 8))
            }
            0x2D if self.word(idx, "-Infinity") => {
                return Ok((Value::Float(f64::NEG_INFINITY), idx + 9))
            }
            _ => {}
        }
        self.match_number(idx)
    }

    fn match_number(&self, start: usize) -> Result<(Value, usize), Halt> {
        let end_idx = self.s.len() - 1;
        let mut idx = start;
        if self.at(idx) == 0x2D {
            idx += 1;
            if idx > end_idx {
                return Err(Halt::NoValue(start));
            }
        }
        if (0x31..=0x39).contains(&self.at(idx)) {
            idx += 1;
            while idx <= end_idx && is_digit(self.at(idx)) {
                idx += 1;
            }
        } else if self.at(idx) == 0x30 {
            idx += 1;
        } else {
            return Err(Halt::NoValue(start));
        }
        let mut is_float = false;
        if idx < end_idx && self.at(idx) == 0x2E && is_digit(self.at(idx + 1)) {
            is_float = true;
            idx += 2;
            while idx <= end_idx && is_digit(self.at(idx)) {
                idx += 1;
            }
        }
        if idx < end_idx && (self.at(idx) == 0x65 || self.at(idx) == 0x45) {
            let e_start = idx;
            idx += 1;
            if idx < end_idx && (self.at(idx) == 0x2D || self.at(idx) == 0x2B) {
                idx += 1;
            }
            while idx <= end_idx && is_digit(self.at(idx)) {
                idx += 1;
            }
            if is_digit(self.at(idx - 1)) {
                is_float = true;
            } else {
                idx = e_start;
            }
        }
        let text: String =
            self.s[start..idx].iter().map(|&c| char::from_u32(c).unwrap_or('?')).collect();
        if is_float {
            let x: f64 = text.parse().unwrap_or(f64::NAN);
            return Ok((Value::Float(x), idx));
        }
        let digits = text.trim_start_matches('-').len();
        if digits > INT_MAX_STR_DIGITS {
            return Err(Halt::Error(format!(
                "Exceeds the limit ({INT_MAX_STR_DIGITS} digits) for integer string conversion: \
                 value has {digits} digits; use sys.set_int_max_str_digits() to increase the limit"
            )));
        }
        Ok((Value::int(BigInt::parse(&text).unwrap_or_default()), idx))
    }

    fn scanstring(&self, mut end: usize) -> Result<(Text, usize), Halt> {
        let len = self.s.len();
        let begin = end - 1;
        let mut out: Vec<u32> = Vec::new();
        loop {
            let mut next = end;
            let mut c = 0;
            while next < len {
                c = self.at(next);
                if c == 0x22 || c == 0x5C {
                    break;
                }
                if c <= 0x1F {
                    return Err(self.err("Invalid control character at", next));
                }
                next += 1;
            }
            if next >= len || (c != 0x22 && c != 0x5C) {
                return Err(self.err("Unterminated string starting at", begin));
            }
            out.extend_from_slice(&self.s[end..next]);
            next += 1;
            if c == 0x22 {
                end = next;
                break;
            }
            if next == len {
                return Err(self.err("Unterminated string starting at", begin));
            }
            c = self.at(next);
            if c != 0x75 {
                end = next + 1;
                let got = match c {
                    0x22 | 0x5C | 0x2F => c,
                    0x62 => 0x08,
                    0x66 => 0x0C,
                    0x6E => 0x0A,
                    0x72 => 0x0D,
                    0x74 => 0x09,
                    _ => return Err(self.err("Invalid \\escape", end - 2)),
                };
                out.push(got);
                continue;
            }
            next += 1;
            end = next + 4;
            if end >= len {
                return Err(self.err("Invalid \\uXXXX escape", next - 1));
            }
            let mut cp = 0u32;
            while next < end {
                let Some(d) = char::from_u32(self.at(next)).and_then(|ch| ch.to_digit(16))
                else {
                    return Err(self.err("Invalid \\uXXXX escape", end - 5));
                };
                cp = (cp << 4) | d;
                next += 1;
            }
            if (0xD800..=0xDBFF).contains(&cp)
                && end + 6 < len
                && self.at(next) == 0x5C
                && {
                    next += 1;
                    true
                }
                && self.at(next) == 0x75
            {
                next += 1;
                let mut c2 = 0u32;
                end += 6;
                while next < end {
                    let Some(d) = char::from_u32(self.at(next)).and_then(|ch| ch.to_digit(16))
                    else {
                        return Err(self.err("Invalid \\uXXXX escape", end - 5));
                    };
                    c2 = (c2 << 4) | d;
                    next += 1;
                }
                if (0xDC00..=0xDFFF).contains(&c2) {
                    cp = 0x10000 + (((cp - 0xD800) << 10) | (c2 - 0xDC00));
                } else {
                    end -= 6;
                }
            }
            out.push(cp);
        }
        Ok((Text::from(out), end))
    }

    fn parse_object(&self, mut idx: usize) -> Result<(Value, usize), Halt> {
        let len = self.s.len();
        let mut d = Dict::new();
        idx = self.skip_ws(idx);
        if idx >= len || self.at(idx) != 0x7D {
            loop {
                if idx >= len || self.at(idx) != 0x22 {
                    return Err(
                        self.err("Expecting property name enclosed in double quotes", idx)
                    );
                }
                let (key, next) = self.scanstring(idx + 1)?;
                idx = self.skip_ws(next);
                if idx >= len || self.at(idx) != 0x3A {
                    return Err(self.err("Expecting ':' delimiter", idx));
                }
                idx = self.skip_ws(idx + 1);
                let (val, next) = self.scan_once(idx)?;
                let _ = d.set(Value::Text(key), val);
                idx = self.skip_ws(next);
                if idx < len && self.at(idx) == 0x7D {
                    break;
                }
                if idx >= len || self.at(idx) != 0x2C {
                    return Err(self.err("Expecting ',' delimiter", idx));
                }
                idx = self.skip_ws(idx + 1);
            }
        }
        Ok((Value::Map(Rc::new(d)), idx + 1))
    }

    fn parse_array(&self, mut idx: usize) -> Result<(Value, usize), Halt> {
        let len = self.s.len();
        let mut items = Vec::new();
        idx = self.skip_ws(idx);
        if idx >= len || self.at(idx) != 0x5D {
            loop {
                let (val, next) = self.scan_once(idx)?;
                items.push(val);
                idx = self.skip_ws(next);
                if idx < len && self.at(idx) == 0x5D {
                    break;
                }
                if idx >= len || self.at(idx) != 0x2C {
                    return Err(self.err("Expecting ',' delimiter", idx));
                }
                idx = self.skip_ws(idx + 1);
            }
        }
        Ok((Value::list(items), idx + 1))
    }
}

/// `json.loads(text)`, or `str(e)` of the exception it raised.
pub fn loads(doc: &Text) -> Result<Value, String> {
    let s = doc.points();
    if s.first() == Some(&0xFEFF) {
        return Err(decode_error("Unexpected UTF-8 BOM (decode using utf-8-sig)", s, 0));
    }
    let scanner = Scanner { s };
    let start = scanner.skip_ws(0);
    let (value, end) = match scanner.scan_once(start) {
        Ok(found) => found,
        Err(Halt::NoValue(at)) => return Err(decode_error("Expecting value", s, at)),
        Err(Halt::Error(message)) => return Err(message),
    };
    let end = scanner.skip_ws(end);
    if end != s.len() {
        return Err(decode_error("Extra data", s, end));
    }
    Ok(value)
}

/// Why `json.dumps` refused a value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DumpError {
    /// `TypeError`: a value JSON has no form for.
    Type,
    /// `ValueError`: an integer past `sys.get_int_max_str_digits()`.
    Value,
}

/// `json.dumps(value, ensure_ascii=False)`: `", "` and `": "` between
/// items, keys in the dict's order.
pub fn dumps(value: &Value) -> Result<Text, DumpError> {
    let mut out: Vec<u32> = Vec::new();
    dump_into(&mut out, value)?;
    Ok(Text::from(out))
}

fn push(out: &mut Vec<u32>, s: &str) {
    out.extend(s.chars().map(|c| c as u32));
}

fn dump_string(out: &mut Vec<u32>, t: &Text) {
    out.push(0x22);
    for &c in t.points() {
        match c {
            0x22 => push(out, "\\\""),
            0x5C => push(out, "\\\\"),
            0x0A => push(out, "\\n"),
            0x0D => push(out, "\\r"),
            0x09 => push(out, "\\t"),
            0x08 => push(out, "\\b"),
            0x0C => push(out, "\\f"),
            _ if c < 0x20 => push(out, &format!("\\u{c:04x}")),
            _ => out.push(c),
        }
    }
    out.push(0x22);
}

fn float_json(x: f64) -> String {
    if x.is_nan() {
        "NaN".to_string()
    } else if x.is_infinite() {
        if x > 0.0 { "Infinity" } else { "-Infinity" }.to_string()
    } else {
        py_float_repr(x)
    }
}

fn dump_into(out: &mut Vec<u32>, value: &Value) -> Result<(), DumpError> {
    match value {
        Value::None => push(out, "null"),
        Value::Bool(b) => push(out, if *b { "true" } else { "false" }),
        Value::Int(n) => push(out, &n.to_string()),
        Value::Big(b) => {
            if b.digits() > INT_MAX_STR_DIGITS {
                return Err(DumpError::Value);
            }
            push(out, &b.to_decimal());
        }
        Value::Float(x) => push(out, &float_json(*x)),
        Value::Text(t) => dump_string(out, t),
        Value::List(xs) => {
            out.push(0x5B);
            for (i, x) in xs.iter().enumerate() {
                if i > 0 {
                    push(out, ", ");
                }
                dump_into(out, x)?;
            }
            out.push(0x5D);
        }
        Value::Map(d) => {
            out.push(0x7B);
            for (i, (k, x)) in d.entries().iter().enumerate() {
                if i > 0 {
                    push(out, ", ");
                }
                match k {
                    Value::Text(t) => dump_string(out, t),
                    // json.dumps writes a non-text key as text, which
                    // json_of never hands it: plain() made every key str
                    Value::Bool(b) => {
                        dump_string(out, &Text::from(if *b { "true" } else { "false" }))
                    }
                    Value::Int(n) => dump_string(out, &Text::from(n.to_string())),
                    Value::Float(f) => dump_string(out, &Text::from(float_json(*f))),
                    Value::None => dump_string(out, &Text::from("null")),
                    _ => return Err(DumpError::Type),
                }
                push(out, ": ");
                dump_into(out, x)?;
            }
            out.push(0x7D);
        }
        _ => return Err(DumpError::Type),
    }
    Ok(())
}

/// CPython's `_PyUnicode_TransformDecimalAndSpaceToASCII`: what `int()`
/// and `float()` read a text as. A Unicode decimal digit becomes its
/// ASCII digit and Unicode white space a space; any other character past
/// ASCII (DEL among them) ends the text as a `?`.
fn to_ascii(t: &Text) -> String {
    let mut out = String::with_capacity(t.len());
    for &c in t.points() {
        if c < 127 {
            out.push(char::from_u32(c).unwrap_or('?'));
        } else if isspace(c) {
            out.push(' ');
        } else if let Some(d) = char::from_u32(c).and_then(decimal_value) {
            out.push(char::from_digit(d, 10).unwrap_or('?'));
        } else {
            out.push('?');
            break;
        }
    }
    out
}

fn py_ascii_space(c: char) -> bool {
    matches!(c, ' ' | '\t' | '\n' | '\r' | '\x0b' | '\x0c')
}

/// CPython's underscore rule for a number in a text: an underscore only
/// between two digits. The text without them, or `None`.
fn without_underscores(s: &str) -> Option<String> {
    if !s.contains('_') {
        return Some(s.to_string());
    }
    let mut out = String::with_capacity(s.len());
    let mut prev = '\0';
    for c in s.chars() {
        if c == '_' {
            if !prev.is_ascii_digit() {
                return None;
            }
        } else {
            if prev == '_' && !c.is_ascii_digit() {
                return None;
            }
            out.push(c);
        }
        prev = c;
    }
    if prev == '_' {
        return None;
    }
    Some(out)
}

/// `int(text)` in base 10, or `None` for its `ValueError`.
pub fn py_int_of_text(t: &Text) -> Option<BigInt> {
    if t.points().contains(&0) || t.points().iter().any(|&c| is_surrogate(c)) {
        return None;
    }
    let ascii = to_ascii(t);
    let s = ascii.trim_matches(py_ascii_space);
    let (neg, body) = match s.as_bytes().first() {
        Some(b'-') => (true, &s[1..]),
        Some(b'+') => (false, &s[1..]),
        _ => (false, s),
    };
    if body.starts_with('_') {
        return None;
    }
    let digits = without_underscores(body)?;
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    if digits.len() > INT_MAX_STR_DIGITS {
        return None;
    }
    let n = BigInt::parse(&digits)?;
    Some(if neg { n.neg() } else { n })
}

/// `float(text)`, or `None` for its `ValueError`.
pub fn py_float_of_text(t: &Text) -> Option<f64> {
    if t.points().iter().any(|&c| is_surrogate(c)) {
        return None;
    }
    let ascii = to_ascii(t);
    let s = ascii.trim_matches(py_ascii_space);
    if s.is_empty() || s.contains('\0') {
        return None;
    }
    let s = without_underscores(s)?;
    let lower = s.to_ascii_lowercase();
    let unsigned = lower.trim_start_matches(['+', '-']);
    if lower.len() - unsigned.len() > 1 {
        return None;
    }
    if matches!(unsigned, "inf" | "infinity" | "nan") {
        let x = if unsigned == "nan" { f64::NAN } else { f64::INFINITY };
        return Some(if lower.starts_with('-') { -x } else { x });
    }
    // what is left is a decimal: digits, a point, an exponent - which
    // Rust's parser reads exactly as CPython's dtoa does, but which it
    // also reads "infinity" in, ruled out above
    if !unsigned.bytes().all(|b| b.is_ascii_digit() || matches!(b, b'.' | b'e' | b'+' | b'-'))
    {
        return None;
    }
    s.parse::<f64>().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(s: &str) -> Text {
        Text::from(s)
    }

    fn err(s: &str) -> String {
        loads(&t(s)).unwrap_err()
    }

    #[test]
    fn messages_are_cpythons() {
        assert_eq!(err(""), "Expecting value: line 1 column 1 (char 0)");
        assert_eq!(err("[1,]"), "Expecting value: line 1 column 4 (char 3)");
        assert_eq!(err("{\"a\" 1}"), "Expecting ':' delimiter: line 1 column 6 (char 5)");
        assert_eq!(
            err("{\"a\": 1,}"),
            "Expecting property name enclosed in double quotes: line 1 column 9 (char 8)"
        );
        assert_eq!(err("[1 2]"), "Expecting ',' delimiter: line 1 column 4 (char 3)");
        assert_eq!(err("\"abc"), "Unterminated string starting at: line 1 column 1 (char 0)");
        assert_eq!(err("\"a\\q\""), "Invalid \\escape: line 1 column 3 (char 2)");
        assert_eq!(err("\"\\u12\""), "Invalid \\uXXXX escape: line 1 column 3 (char 2)");
        assert_eq!(
            err("\"\\ud800\\u12\""),
            "Invalid \\uXXXX escape: line 1 column 9 (char 8)"
        );
        assert_eq!(err("{\"a\""), "Expecting ':' delimiter: line 1 column 5 (char 4)");
        assert_eq!(
            err("{"),
            "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
        );
        assert_eq!(err("[-]"), "Expecting value: line 1 column 2 (char 1)");
        assert_eq!(err("1.e5"), "Extra data: line 1 column 2 (char 1)");
        assert_eq!(
            err("\u{feff}1"),
            "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)"
        );
        assert_eq!(err("1 2"), "Extra data: line 1 column 3 (char 2)");
        assert_eq!(err("\n\n  x"), "Expecting value: line 3 column 3 (char 4)");
        assert_eq!(
            err("\"a\u{1}\""),
            "Invalid control character at: line 1 column 3 (char 2)"
        );
    }

    #[test]
    fn values_are_cpythons() {
        let v = loads(&t(
            "{\"a\": 1, \"a\": 2.5, \"b\": [true, null, \"\\ud800\\ud83d\\ude00\"]}",
        ))
        .unwrap();
        let text = dumps(&v).unwrap();
        assert_eq!(
            text,
            Text::from(vec![]).concat(&Text::from(
                "{\"a\": 2.5, \"b\": [true, null, \""
                    .chars()
                    .map(|c| c as u32)
                    .chain([0xD800, 0x1F600])
                    .chain("\"]}".chars().map(|c| c as u32))
                    .collect::<Vec<u32>>()
            ))
        );
        assert!(matches!(loads(&t("-0")), Ok(Value::Int(0))));
        assert!(matches!(loads(&t("1e400")), Ok(Value::Float(x)) if x.is_infinite()));
    }

    #[test]
    fn int_and_float_of_text_are_cpythons() {
        assert_eq!(py_int_of_text(&t(" -1_000 ")).and_then(|b| b.to_i64()), Some(-1000));
        assert_eq!(py_int_of_text(&t("\u{663}\u{664}")).and_then(|b| b.to_i64()), Some(34));
        assert!(py_int_of_text(&t("1__0")).is_none());
        assert!(py_int_of_text(&t("_1")).is_none());
        assert!(py_int_of_text(&t("1.0")).is_none());
        assert_eq!(py_float_of_text(&t(" 1_0.5 ")), Some(10.5));
        assert_eq!(py_float_of_text(&t("-Infinity")), Some(f64::NEG_INFINITY));
        assert_eq!(py_float_of_text(&t(".5")), Some(0.5));
        assert_eq!(py_float_of_text(&t("5.")), Some(5.0));
        assert!(py_float_of_text(&t("1e")).is_none());
        assert!(py_float_of_text(&t("--1")).is_none());
        assert!(py_float_of_text(&t("0x10")).is_none());
    }
}
