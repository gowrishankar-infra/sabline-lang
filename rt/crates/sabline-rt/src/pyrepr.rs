//! The two places a message or a dump has to be spelled the way CPython
//! spells it.
//!
//! **`ascii_char`** is CPython's `ascii()` of a one-character string, which
//! is what `sabline/lexer.py` writes into E000: `unexpected character
//! {source[pos]!a}`. It was `{...!r}` until 9.0.0-alpha.1; `repr` emits a
//! printable non-ASCII character raw, and which characters are printable
//! comes from the Unicode database of whichever CPython is running, so the
//! same program gave two different messages on two supported Pythons.
//! `ascii()` escapes every non-ASCII character and depends on no table.
//!
//! **`canonical_float`** is the AST dump's form for a float: the shortest
//! decimal that reads back as the same double, written as `d[.ddd]eE`.
//! That is what Rust's `{:e}` writes, and `sabline/ast_dump.py` writes the
//! same string from CPython's own shortest form. rt/README.md states the
//! form; the point of choosing one is that neither language's default
//! printing is the other's.

/// CPython's `ascii()` of the one-character string `c`, quotes included.
///
/// The quote is `'`, or `"` when the character is `'` - the rule CPython
/// uses for any string that holds a single quote and no double quote.
pub fn ascii_char(c: char) -> String {
    let quote = if c == '\'' { '"' } else { '\'' };
    let mut out = String::with_capacity(12);
    out.push(quote);
    escape_into(&mut out, c, quote);
    out.push(quote);
    out
}

fn escape_into(out: &mut String, c: char, quote: char) {
    let cp = c as u32;
    match c {
        '\\' => out.push_str("\\\\"),
        '\t' => out.push_str("\\t"),
        '\n' => out.push_str("\\n"),
        '\r' => out.push_str("\\r"),
        _ if c == quote => {
            out.push('\\');
            out.push(c);
        }
        _ if (0x20..0x7f).contains(&cp) => out.push(c),
        _ if cp < 0x100 => out.push_str(&format!("\\x{cp:02x}")),
        _ if cp < 0x10000 => out.push_str(&format!("\\u{cp:04x}")),
        _ => out.push_str(&format!("\\U{cp:08x}")),
    }
}

/// The AST dump's form for a float: `d[.ddd]eE`, shortest round-trip.
///
/// `1.0` is `1e0`, `1.5` is `1.5e0`, `0.00001` is `1e-5`, `100.0` is `1e2`.
/// Rust's `{:e}` is already that form; this function exists so the choice
/// has a name and a test rather than being a formatting string somewhere.
pub fn canonical_float(x: f64) -> String {
    format!("{x:e}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ascii_char_matches_cpython() {
        // Every row was read from CPython 3.13: `ascii(chr(n))`.
        let rows: &[(char, &str)] = &[
            ('\'', "\"'\""),
            ('"', "'\"'"),
            ('\\', "'\\\\'"),
            ('\n', "'\\n'"),
            ('\t', "'\\t'"),
            ('\r', "'\\r'"),
            ('\u{0}', "'\\x00'"),
            ('\u{1f}', "'\\x1f'"),
            ('\u{7f}', "'\\x7f'"),
            ('\u{80}', "'\\x80'"),
            ('\u{a0}', "'\\xa0'"),
            ('\u{100}', "'\\u0100'"),
            ('\u{2028}', "'\\u2028'"),
            ('\u{1f600}', "'\\U0001f600'"),
            ('\u{feff}', "'\\ufeff'"),
            ('$', "'$'"),
            (' ', "' '"),
            ('\u{b}', "'\\x0b'"),
            ('\u{c}', "'\\x0c'"),
            ('\u{7}', "'\\x07'"),
        ];
        for (c, want) in rows {
            assert_eq!(&ascii_char(*c), want, "ascii({c:?})");
        }
    }

    #[test]
    fn canonical_float_round_trips() {
        for text in [
            "0.0",
            "1.0",
            "1.5",
            "100.0",
            "0.00001",
            "0.0001",
            "99999999999999999999.0",
            "123456789012345678.0",
            "0.1",
            "3.14159265358979",
            "1.7976931348623157",
            "0.000000000000000000001",
            "12345678901234567890123456789.0",
        ] {
            let x: f64 = text.parse().expect("a float literal parses");
            let canon = canonical_float(x);
            let back: f64 = canon.parse().expect("the canonical form parses");
            assert_eq!(x.to_bits(), back.to_bits(), "{text} -> {canon}");
        }
    }

    #[test]
    fn canonical_float_is_normalised_scientific() {
        assert_eq!(canonical_float(0.0), "0e0");
        assert_eq!(canonical_float(1.0), "1e0");
        assert_eq!(canonical_float(1.5), "1.5e0");
        assert_eq!(canonical_float(100.0), "1e2");
        assert_eq!(canonical_float(0.00001), "1e-5");
        assert_eq!(canonical_float(0.0001), "1e-4");
    }
}
