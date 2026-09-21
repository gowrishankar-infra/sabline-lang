//! A canonical JSON writer, and nothing else.
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
    /// A string.
    Str(String),
    /// An array.
    List(Vec<Json>),
    /// An object, whose keys are written in sorted order.
    Obj(BTreeMap<String, Json>),
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
        Json::Str(s) => write_string(out, s),
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

#[cfg(test)]
mod tests {
    use super::*;

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
