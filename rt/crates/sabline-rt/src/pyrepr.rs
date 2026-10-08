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

/// CPython's `str.isspace()` for one character.
///
/// A character whose general category is Zs or whose bidirectional class
/// is WS, B or S. That is Rust's `White_Space` and four more: U+001C to
/// U+001F, the information separators, which Unicode does not call white
/// space and CPython does.
pub fn py_isspace(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// CPython's `str.strip()` with no argument.
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(py_isspace)
}

/// CPython's `repr()` of a float, which is what `str()` of one gives and
/// what `expr_str` writes for a float literal in a message.
///
/// The digits are the shortest that read back as the same double - what
/// Rust's `{:e}` gives too - and the form is CPython's: fixed notation
/// with at least one digit after the point while the decimal point falls
/// between 4 places before the first digit and 16 after it, and
/// `d[.ddd]e±XX` outside that, with at least two exponent digits.
pub fn py_float_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_string();
    }
    let sci = format!("{x:e}");
    let (sign, sci) = match sci.strip_prefix('-') {
        Some(rest) => ("-", rest.to_string()),
        None => ("", sci),
    };
    let (mantissa, exp) = sci.split_once('e').unwrap_or((sci.as_str(), "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
    // the value is 0.DIGITS times ten to the power decpt
    let decpt = exp + 1;
    let n = i32::try_from(digits.len()).unwrap_or(i32::MAX);
    let body = if decpt <= -4 || decpt > 16 {
        let (first, rest) = digits.split_at(1);
        let e = decpt - 1;
        let e_sign = if e < 0 { '-' } else { '+' };
        let point = if rest.is_empty() { String::new() } else { format!(".{rest}") };
        format!("{first}{point}e{e_sign}{:02}", e.unsigned_abs())
    } else if decpt <= 0 {
        format!("0.{}{digits}", "0".repeat(decpt.unsigned_abs() as usize))
    } else if decpt >= n {
        format!("{digits}{}.0", "0".repeat((decpt - n) as usize))
    } else {
        let (whole, frac) = digits.split_at(decpt as usize);
        format!("{whole}.{frac}")
    };
    format!("{sign}{body}")
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
    fn py_isspace_is_cpythons_set_and_no_other() {
        // Every character CPython 3.13 says `isspace()` of, and nothing else.
        let cpython: Vec<u32> = vec![
            0x9, 0xa, 0xb, 0xc, 0xd, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000,
            0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a,
            0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
        ];
        let ours: Vec<u32> = (0..=0x10ffffu32)
            .filter_map(char::from_u32)
            .filter(|c| py_isspace(*c))
            .map(u32::from)
            .collect();
        assert_eq!(ours, cpython);
        assert_eq!(py_strip("\u{1c} a \u{1f}"), "a");
    }

    #[test]
    fn py_float_repr_matches_cpython() {
        // Every row was read from CPython 3.13: `repr(float(text))`.
        let rows: &[(f64, &str)] = &[
            (0.0, "0.0"),
            (-0.0, "-0.0"),
            (1.0, "1.0"),
            (1.5, "1.5"),
            (100.0, "100.0"),
            (0.1, "0.1"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (0.000015, "1.5e-05"),
            (1e15, "1000000000000000.0"),
            (1e16, "1e+16"),
            (1.5e16, "1.5e+16"),
            (123.456, "123.456"),
            (1.23456789012345, "1.23456789012345"),
            (1.7976931348623157e308, "1.7976931348623157e+308"),
            (5e-324, "5e-324"),
            (1234567890123456.7, "1234567890123456.8"),
            (12345678901234567.0, "1.2345678901234568e+16"),
        ];
        for (x, want) in rows {
            assert_eq!(&py_float_repr(*x), want, "repr({x:?})");
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
