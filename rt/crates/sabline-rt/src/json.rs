//! A canonical JSON writer, and a reader for what the gate sends.
//!
//! The AST dump is compared byte for byte against what CPython's `json`
//! module writes, so the writer is specified against that module rather
//! than against the JSON grammar:
//!
//! - keys sorted by code point, as `sort_keys=True`;
//! - no whitespace at all - `,` between items and `:` after a key, and
//!   `[]` and `{}` for an empty container - as
//!   `separators=(",", ":")`;
//! - every character outside `\x20` to `\x7e` escaped, as
//!   `ensure_ascii=True`: `\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t` by name
//!   and everything else as `\uxxxx` in lowercase hex, a character past
//!   the basic plane as the two `\uxxxx` of its surrogate pair.
//!
//! **No indentation**, and that is a decision rather than a default. Two
//! spaces a level makes a document O(depth squared): the dump of the
//! deepest program the parser accepts - 40 KB of source, and a case the
//! adversarial corpus holds on purpose - was 352 MB of mostly spaces, and
//! the gate writes it twice on every leg of CI. Compact, the same document
//! is 1 MB.
//!
//! Writing it here rather than taking a crate is the cheapest way to hold
//! that contract: a general JSON library is free to spell any of it
//! differently, and the difference would read as a difference between two
//! parsers.
//!
//! The reader ([`Json::parse`]) is for input that is data, not a program:
//! the budgets the agreement gate and `sabline conformance --runtime rust`
//! hand over, one JSON document a line, so that a budget holding a tab, a
//! comma or a character past ASCII reaches sabline-rt exactly as it reached
//! the Python package. It reads what CPython's `json.dumps` writes. A
//! number with a fraction or an exponent, a lone surrogate and a document
//! nested deeper than [`MAX_DEPTH`] are refused: nothing the gate sends
//! holds one.

use std::collections::BTreeMap;

/// A JSON value.
#[derive(Debug, Clone, PartialEq)]
pub enum Json {
    /// `null`.
    Null,
    /// `true` or `false`.
    Bool(bool),
    /// A whole number.
    Int(i64),
    /// A whole number of any size, as its decimal digits: what a count in
    /// a budget is, since CPython's `int()` has no upper bound.
    Num(String),
    /// A string.
    Str(String),
    /// An array.
    List(Vec<Json>),
    /// An object, whose keys are written in sorted order.
    Obj(BTreeMap<String, Json>),
    /// A string that may hold a lone surrogate: a Text a program made,
    /// written as CPython writes a `str` (9.0, M3).
    Text(crate::text::Text),
}

impl Json {
    /// An object from its pairs.
    pub fn obj<const N: usize>(pairs: [(&str, Json); N]) -> Json {
        Json::Obj(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
    }

    /// A string.
    pub fn text(s: impl Into<String>) -> Json {
        Json::Str(s.into())
    }

    /// The document, as CPython's `json.dumps(..., sort_keys=True,
    /// separators=(",", ":"))` writes it, with no trailing newline.
    pub fn canonical(&self) -> String {
        let mut out = String::new();
        write_value(&mut out, self);
        out
    }
}

fn write_value(out: &mut String, value: &Json) {
    match value {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Int(n) => out.push_str(&n.to_string()),
        Json::Num(digits) => out.push_str(digits),
        Json::Str(s) => write_string(out, s),
        Json::Text(t) => t.write_json_ascii(out),
        Json::List(items) => {
            if items.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_value(out, item);
            }
            out.push(']');
        }
        Json::Obj(pairs) => {
            if pairs.is_empty() {
                out.push_str("{}");
                return;
            }
            out.push('{');
            for (i, (key, item)) in pairs.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_string(out, key);
                out.push(':');
                write_value(out, item);
            }
            out.push('}');
        }
    }
}

fn write_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ if (' '..='~').contains(&c) => out.push(c),
            _ => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
        }
    }
    out.push('"');
}

/// How deep [`Json::parse`] reads before it refuses.
pub const MAX_DEPTH: usize = 64;

impl Json {
    /// Read one JSON document. `Err` says where it stopped and why.
    pub fn parse(text: &str) -> Result<Json, String> {
        let chars: Vec<char> = text.chars().collect();
        let mut reader = Reader { chars: &chars, at: 0 };
        reader.blank();
        let value = reader.value(0)?;
        reader.blank();
        if reader.at != chars.len() {
            return Err(format!("JSON: something after the document, at {}", reader.at));
        }
        Ok(value)
    }
}

struct Reader<'a> {
    chars: &'a [char],
    at: usize,
}

impl Reader<'_> {
    fn peek(&self) -> Option<char> {
        self.chars.get(self.at).copied()
    }

    fn blank(&mut self) {
        while matches!(self.peek(), Some(' ' | '\t' | '\n' | '\r')) {
            self.at += 1;
        }
    }

    fn word(&mut self, word: &str, value: Json) -> Result<Json, String> {
        for want in word.chars() {
            if self.peek() != Some(want) {
                return Err(format!("JSON: expected {word} at {}", self.at));
            }
            self.at += 1;
        }
        Ok(value)
    }

    fn value(&mut self, depth: usize) -> Result<Json, String> {
        if depth > MAX_DEPTH {
            return Err(format!("JSON: nested deeper than {MAX_DEPTH}"));
        }
        match self.peek() {
            Some('n') => self.word("null", Json::Null),
            Some('t') => self.word("true", Json::Bool(true)),
            Some('f') => self.word("false", Json::Bool(false)),
            Some('"') => self.string().map(Json::Str),
            Some('[') => self.list(depth),
            Some('{') => self.object(depth),
            Some(c) if c == '-' || c.is_ascii_digit() => self.number(),
            _ => Err(format!("JSON: no value at {}", self.at)),
        }
    }

    fn list(&mut self, depth: usize) -> Result<Json, String> {
        self.at += 1;
        let mut items = Vec::new();
        self.blank();
        if self.peek() == Some(']') {
            self.at += 1;
            return Ok(Json::List(items));
        }
        loop {
            self.blank();
            items.push(self.value(depth + 1)?);
            self.blank();
            match self.peek() {
                Some(',') => self.at += 1,
                Some(']') => {
                    self.at += 1;
                    return Ok(Json::List(items));
                }
                _ => return Err(format!("JSON: expected , or ] at {}", self.at)),
            }
        }
    }

    fn object(&mut self, depth: usize) -> Result<Json, String> {
        self.at += 1;
        let mut pairs = BTreeMap::new();
        self.blank();
        if self.peek() == Some('}') {
            self.at += 1;
            return Ok(Json::Obj(pairs));
        }
        loop {
            self.blank();
            if self.peek() != Some('"') {
                return Err(format!("JSON: expected a key at {}", self.at));
            }
            let key = self.string()?;
            self.blank();
            if self.peek() != Some(':') {
                return Err(format!("JSON: expected : at {}", self.at));
            }
            self.at += 1;
            self.blank();
            let item = self.value(depth + 1)?;
            pairs.insert(key, item);
            self.blank();
            match self.peek() {
                Some(',') => self.at += 1,
                Some('}') => {
                    self.at += 1;
                    return Ok(Json::Obj(pairs));
                }
                _ => return Err(format!("JSON: expected , or }} at {}", self.at)),
            }
        }
    }

    fn number(&mut self) -> Result<Json, String> {
        let start = self.at;
        self.at += 1;
        while self.peek().is_some_and(|c| c.is_ascii_digit()) {
            self.at += 1;
        }
        if matches!(self.peek(), Some('.' | 'e' | 'E')) {
            return Err(format!("JSON: only whole numbers are read, at {start}"));
        }
        let digits: String = self.chars[start..self.at].iter().collect();
        if digits == "-" {
            return Err(format!("JSON: a lone - at {start}"));
        }
        Ok(match digits.parse::<i64>() {
            Ok(n) => Json::Int(n),
            Err(_) => Json::Num(digits),
        })
    }

    fn hex4(&mut self) -> Result<u32, String> {
        let mut n = 0;
        for _ in 0..4 {
            let Some(d) = self.peek().and_then(|c| c.to_digit(16)) else {
                return Err(format!("JSON: an escape wants four hex digits, at {}", self.at));
            };
            n = n * 16 + d;
            self.at += 1;
        }
        Ok(n)
    }

    fn escape(&mut self) -> Result<char, String> {
        let Some(e) = self.peek() else {
            return Err("JSON: a string that does not end".to_string());
        };
        self.at += 1;
        let simple = match e {
            '"' => '"',
            '\\' => '\\',
            '/' => '/',
            'b' => '\u{8}',
            'f' => '\u{c}',
            'n' => '\n',
            'r' => '\r',
            't' => '\t',
            'u' => return self.unicode_escape(),
            _ => return Err(format!("JSON: {e:?} is not an escape, at {}", self.at)),
        };
        Ok(simple)
    }

    fn unicode_escape(&mut self) -> Result<char, String> {
        let lone = |at: usize| format!("JSON: a lone surrogate at {at}");
        let unit = self.hex4()?;
        let code = if (0xD800..0xDC00).contains(&unit) {
            if self.peek() != Some('\\') {
                return Err(lone(self.at));
            }
            self.at += 1;
            if self.peek() != Some('u') {
                return Err(lone(self.at));
            }
            self.at += 1;
            let low = self.hex4()?;
            if !(0xDC00..0xE000).contains(&low) {
                return Err(lone(self.at));
            }
            0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00)
        } else {
            unit
        };
        char::from_u32(code).ok_or_else(|| lone(self.at))
    }

    fn string(&mut self) -> Result<String, String> {
        self.at += 1;
        let mut out = String::new();
        loop {
            let Some(c) = self.peek() else {
                return Err("JSON: a string that does not end".to_string());
            };
            self.at += 1;
            match c {
                '"' => return Ok(out),
                '\\' => out.push(self.escape()?),
                _ => out.push(c),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn what_it_writes_it_reads_back() {
        let doc = Json::obj([
            ("a", Json::List(vec![Json::Null, Json::Bool(true), Json::Int(-7)])),
            ("b", Json::text("tab\there, caf\u{e9}, \u{1f600}, \"q\" \\ /")),
            ("c", Json::Num("123456789012345678901234567890".to_string())),
        ]);
        assert_eq!(Json::parse(&doc.canonical()), Ok(doc));
        assert_eq!(
            Json::parse(" [ \"x\" , null, {} ] "),
            Ok(Json::List(vec![Json::text("x"), Json::Null, Json::Obj(BTreeMap::new())]))
        );
    }

    #[test]
    fn what_it_will_not_read() {
        for bad in [
            "1.5",
            "1e3",
            "\"\\ud800\"",
            "\"\\udc00\"",
            "[1,]",
            "{\"a\" 1}",
            "\"x",
            "-",
            "[] []",
            "\"\\q\"",
        ] {
            assert!(Json::parse(bad).is_err(), "{bad}");
        }
        let deep = format!("{}{}", "[".repeat(MAX_DEPTH + 2), "]".repeat(MAX_DEPTH + 2));
        assert!(Json::parse(&deep).is_err());
    }

    #[test]
    fn an_empty_container_is_written_flat() {
        let doc = Json::obj([("a", Json::Obj(BTreeMap::new())), ("b", Json::List(vec![]))]);
        assert_eq!(doc.canonical(), "{\"a\":{},\"b\":[]}");
    }

    #[test]
    fn keys_are_sorted_and_nothing_is_written_between_items() {
        let doc = Json::obj([
            ("c", Json::List(vec![Json::Int(1), Json::List(vec![Json::Int(2)])])),
            ("a", Json::Null),
        ]);
        assert_eq!(doc.canonical(), "{\"a\":null,\"c\":[1,[2]]}");
    }

    #[test]
    fn a_deep_document_grows_with_its_depth_and_not_with_its_square() {
        // Two spaces a level would make this one O(depth squared); the
        // adversarial corpus holds a program 4,000 levels deep on purpose,
        // and the gate writes its dump twice on every leg of CI.
        let mut doc = Json::Int(1);
        for _ in 0..2000 {
            doc = Json::obj([("k", doc)]);
        }
        let text = doc.canonical();
        assert!(text.len() < 2000 * 8, "{} bytes for 2,000 levels", text.len());
    }

    #[test]
    fn escaping_matches_cpythons_ensure_ascii() {
        // Every row was read from CPython 3.13: `json.dumps(s)`.
        let rows: &[(&str, &str)] = &[
            ("\u{7f}", "\"\\u007f\""),
            ("\u{e9}", "\"\\u00e9\""),
            ("\u{1f600}", "\"\\ud83d\\ude00\""),
            ("\u{8}\u{c}", "\"\\b\\f\""),
            ("a\"b\\c", "\"a\\\"b\\\\c\""),
            ("\n\r\t", "\"\\n\\r\\t\""),
            ("\u{0}", "\"\\u0000\""),
            (" ~", "\" ~\""),
        ];
        for (raw, want) in rows {
            assert_eq!(&Json::text(*raw).canonical(), want, "{raw:?}");
        }
    }
}
