r"""Write rt/crates/sabline-rt/src/unicode_text.rs from this Python's own
`str.upper()`, `str.lower()` and `str.isprintable()`.

A Sabline Text is CPython's `str`, so `upper`, `lower` and the text a
broken promise's message quotes have to come out as CPython makes them,
and those three answers are read from a database that is CPython's, not
Rust's. They are generated here and committed, as unicode_digit.rs is:

- **upper** and **lower**, each character's full mapping - one to three
  characters, `'ß'.upper()` is `'SS'` - which is what CPython applies one
  character at a time;
- the two properties `lower()` reads around a capital sigma, which it
  writes as `ς` at the end of a word and `σ` elsewhere (CPython's
  `handle_capital_sigma`). Python exposes neither property, so they are
  read off `lower()` itself: a character is *case-ignorable* when the
  sigma looks through it to the letter before, and *cased* when, not
  being ignorable, it counts as that letter;
- **printable**, the ranges where `isprintable()` is true, which is what
  `repr()` of a text leaves unescaped.

The tables follow the Unicode version of the CPython that generated them,
which is written into the file. rt/README.md says what that means when
another CPython disagrees.

    python scripts/gen_unicode_text.py
"""
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / \
    "rt/crates/sabline-rt/src/unicode_text.rs"
SIGMA = "Σ"
FINAL = "ς"


def mappings(fn: str) -> list[tuple[int, list[int]]]:
    out = []
    for c in range(0x110000):
        ch = chr(c)
        if 0xD800 <= c <= 0xDFFF:
            continue                      # a lone surrogate maps to itself
        got = getattr(ch, fn)()
        if got != ch:
            assert 1 <= len(got) <= 3, (hex(c), got)
            out.append((c, [ord(x) for x in got]))
    return out


def ranges(pred: object) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start = None
    for c in range(0x110001):
        hit = c < 0x110000 and pred(c)       # type: ignore[operator]
        if hit and start is None:
            start = c
        elif not hit and start is not None:
            out.append((start, c - 1))
            start = None
    return out


def ignorable(c: int) -> bool:
    # "A" + c + SIGMA ends in the final form when the sigma reaches the A
    # through c, or when c is itself cased; c + SIGMA, when c is cased and
    # not looked through. Ignorable is the first without the second.
    ch = chr(c)
    through = ("A" + ch + SIGMA).lower()[-1] == FINAL
    itself = (ch + SIGMA).lower()[-1] == FINAL
    return through and not itself


def cased(c: int) -> bool:
    ch = chr(c)
    return (ch + SIGMA).lower()[-1] == FINAL


def rows(name: str, doc: str, table: list[tuple[int, list[int]]]) -> list[str]:
    lines = [f"/// {doc}", f"pub static {name}: [(u32, [u32; 3]); {len(table)}] = ["]
    for c, mapped in table:
        cells = ", ".join(f"0x{m:04X}" for m in mapped + [0] * (3 - len(mapped)))
        lines.append(f"    (0x{c:04X}, [{cells}]),")
    lines.append("];")
    return lines


def spans(name: str, doc: str, table: list[tuple[int, int]]) -> list[str]:
    lines = [f"/// {doc}", f"pub static {name}: [(u32, u32); {len(table)}] = ["]
    for a, b in table:
        lines.append(f"    (0x{a:04X}, 0x{b:04X}),")
    lines.append("];")
    return lines


def main() -> int:
    upper = mappings("upper")
    lower = mappings("lower")
    # the sigma's own entry is its form in the middle of a word; the end of
    # a word is decided where it is read (text.rs)
    assert dict(lower)[0x3A3] == [0x3C3]
    ign = ranges(lambda c: not 0xD800 <= c <= 0xDFFF and ignorable(c))
    cas = ranges(lambda c: not 0xD800 <= c <= 0xDFFF and cased(c))
    printable = ranges(lambda c: chr(c).isprintable())
    version = ".".join(str(p) for p in sys.version_info[:3])
    lines = [
        "//! What CPython's `str.upper()`, `str.lower()` and `str.isprintable()`",
        "//! answer, generated from CPython itself. Do not edit by hand:",
        "//! scripts/gen_unicode_text.py writes it.",
        "//!",
        f"//! Unicode {unicodedata.unidata_version}, from CPython {version}.",
        "#![allow(clippy::unreadable_literal)]",
        "",
        "/// The Unicode version these tables were generated from.",
        f'pub const UNICODE_VERSION: &str = "{unicodedata.unidata_version}";',
        "",
    ]
    lines += rows("UPPER", "Each character `upper()` changes, and what it becomes: one to "
                  "three characters, the unused cells 0.", upper)
    lines.append("")
    lines += rows("LOWER", "Each character `lower()` changes, and what it becomes; the "
                  "capital sigma's entry is its form inside a word.", lower)
    lines.append("")
    lines += spans("CASE_IGNORABLE", "The characters a capital sigma's context looks "
                   "through, as inclusive ranges.", ign)
    lines.append("")
    lines += spans("CASED", "The characters that are cased and not ignorable, as "
                   "inclusive ranges: what a sigma's context counts as a letter.",
                   [r for r in cas])
    lines.append("")
    lines += spans("PRINTABLE", "The characters `isprintable()` is true of, as "
                   "inclusive ranges: what `repr()` writes as themselves.", printable)
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: {len(upper)} upper, {len(lower)} lower, "
          f"{len(ign)} ignorable ranges, {len(cas)} cased ranges, "
          f"{len(printable)} printable ranges; Unicode "
          f"{unicodedata.unidata_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
