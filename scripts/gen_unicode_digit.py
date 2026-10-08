r"""Write rt/crates/sabline-rt/src/unicode_digit.rs from this Python's own
`str.isdigit()`.

`str.isdigit()` is true for every decimal digit (category Nd, which
unicode_nd.rs already holds) and for the digits that are not decimal -
Numeric_Type=Digit: superscripts, circled and parenthesised digits, and the
like. The budget parser asks it of each label of a wildcard host
(`net:*.1.²` is a wildcard over an IP literal), so sabline-rt has to answer
the same, and Rust's standard library has no such set. The second half is
generated here and committed, beside the first.

The set follows the Unicode version of the CPython that generated it,
which is written into the file. rt/README.md says what that means when
another CPython disagrees.

    python scripts/gen_unicode_digit.py
"""
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / \
    "rt/crates/sabline-rt/src/unicode_digit.rs"


def points() -> list[int]:
    return [c for c in range(0x110000)
            if chr(c).isdigit() and not chr(c).isdecimal()]


def main() -> int:
    found = points()
    lines = [
        "//! Every Unicode digit that is not a decimal digit, generated from",
        "//! CPython's own `str.isdigit()`. Do not edit by hand:",
        "//! scripts/gen_unicode_digit.py writes it.",
        "//!",
        "//! `str.isdigit()` is true for a decimal digit (unicode_nd.rs) and",
        "//! for these: Numeric_Type=Digit, such as superscripts and circled",
        "//! digits. [`py_isdigit`] is the two together.",
        "//!",
        f"//! Unicode {unicodedata.unidata_version}, from CPython "
        f"{'.'.join(str(p) for p in sys.version_info[:3])}.",
        "",
        "/// The Unicode version this table was generated from.",
        f'pub const UNICODE_VERSION: &str = "{unicodedata.unidata_version}";',
        "",
        "/// Every code point `str.isdigit()` accepts and `str.isdecimal()` "
        "does not.",
        f"pub const DIGITS_NOT_DECIMAL: [u32; {len(found)}] = [",
    ]
    row: list[str] = []
    for c in found:
        row.append(f"0x{c:04X},")
        if len(row) == 10:
            lines.append("    " + " ".join(row))
            row = []
    if row:
        lines.append("    " + " ".join(row))
    lines += [
        "];",
        "",
        "/// `c.isdigit()`, as CPython answers it for one character.",
        "pub fn py_isdigit(c: char) -> bool {",
        "    crate::unicode_nd::decimal_value(c).is_some()",
        "        || DIGITS_NOT_DECIMAL.binary_search(&(c as u32)).is_ok()",
        "}",
        "",
        "#[cfg(test)]",
        "mod tests {",
        "    use super::*;",
        "",
        "    #[test]",
        "    fn digits_that_are_not_decimal_count() {",
        "        for c in ['0', '9', '\\u{663}', '\\u{b2}', '\\u{2460}', '\\u{2081}'] {",
        "            assert!(py_isdigit(c), \"{c:?}\");",
        "        }",
        "        for c in ['a', '\\u{bd}', '\\u{2167}', ' ', '-'] {",
        "            assert!(!py_isdigit(c), \"{c:?}\");",
        "        }",
        "    }",
        "}",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: {len(found)} code points, Unicode "
          f"{unicodedata.unidata_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
