r"""Write rt/crates/sabline-rt/src/unicode_nd.rs from this Python's own
`\d`.

The Python lexer's NUMBER and FLOAT patterns are `\d+` and `\d+\.\d+`,
and `\d` in a `str` pattern is every Unicode decimal digit - category Nd -
not the ten ASCII ones. `int()` and `float()` convert them by each
character's decimal value. sabline-rt has to do the same, and Rust's
standard library carries no Unicode categories, so the set is generated
here and committed.

The set follows the Unicode version of the CPython that generated it,
which is written into the file. rt/README.md says what that means when
another CPython disagrees.

    python scripts/gen_unicode_nd.py
"""
import re
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / \
    "rt/crates/sabline-rt/src/unicode_nd.rs"


def ranges() -> list[tuple[int, int]]:
    digit = re.compile(r"\d")
    points = [c for c in range(0x110000) if digit.fullmatch(chr(c))]
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(points):
        start = j = i
        while (j + 1 < len(points) and points[j + 1] == points[j] + 1
               and points[j + 1] - points[start] <= 9):
            j += 1
        out.append((points[start], points[j]))
        i = j + 1
    for first, last in out:
        if last - first != 9:
            raise SystemExit(f"U+{first:04X}..U+{last:04X} is not a run of "
                             f"ten: the table's shape assumes one")
        for c in range(first, last + 1):
            if unicodedata.decimal(chr(c)) != c - first:
                raise SystemExit(f"U+{c:04X} is not worth {c - first}: the "
                                 f"table's value rule assumes it is")
    return out


def main() -> int:
    rows = ranges()
    lines = [
        "//! Every Unicode decimal digit, generated from CPython's own",
        r"//! `\d`. Do not edit by hand: scripts/gen_unicode_nd.py writes it.",
        "//!",
        r"//! `\d` in a `str` pattern is category Nd, which is what the",
        "//! Python lexer's NUMBER and FLOAT patterns match, and `int()` and",
        "//! `float()` read each of them by its decimal value. Each range",
        "//! here is ten code points and a digit's value is its distance from",
        "//! the start of its range; the generator refuses to write a table",
        "//! where that is not true.",
        "//!",
        f"//! Unicode {unicodedata.unidata_version}, from CPython "
        f"{'.'.join(str(p) for p in sys.version_info[:3])}.",
        "",
        "/// The Unicode version this table was generated from.",
        f'pub const UNICODE_VERSION: &str = "{unicodedata.unidata_version}";',
        "",
        "/// The first code point of each run of ten decimal digits.",
        f"pub const DIGIT_RUNS: [u32; {len(rows)}] = [",
    ]
    for first, _ in rows:
        lines.append(f"    0x{first:04X},")
    lines += [
        "];",
        "",
        "/// The digit's value when `c` is a Unicode decimal digit.",
        "pub fn decimal_value(c: char) -> Option<u32> {",
        "    let cp = c as u32;",
        "    match DIGIT_RUNS.binary_search(&cp) {",
        "        Ok(_) => Some(0),",
        "        Err(0) => None,",
        "        Err(i) => {",
        "            let start = DIGIT_RUNS[i - 1];",
        "            if cp - start <= 9 { Some(cp - start) } else { None }",
        "        }",
        "    }",
        "}",
        "",
        r"/// Whether `c` is what the Python lexer's `\d` matches.",
        "pub fn is_digit(c: char) -> bool {",
        "    decimal_value(c).is_some()",
        "}",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{OUT}: {len(rows)} runs, {len(rows) * 10} digits, Unicode "
          f"{unicodedata.unidata_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
