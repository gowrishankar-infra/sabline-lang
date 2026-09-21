"""The canonical AST dump, alone: sabline.ast_dump (9.0.0-alpha.1).

`check_agreement.py` compares this document with sabline-rt's over some
thousands of programs, on every commit. What is here is the part about the
Python side alone: that the document is what rt/README.md says it is, that
the places where two implementations could differ without either being
wrong are decided rather than left to chance, and that the four things the
reference does which SPEC.md does not state are still what they were -
because sabline-rt copies three of them and a change here without a change
there is a difference the gate would find.

The dump is not a stable interface. STABILITY.md's "anything else in the
package" clause covers it, and nothing but the gate reads it.
"""
import json
import re
import tempfile
import unicodedata
import unittest
from pathlib import Path

import _support
from sabline.ast_dump import (
    DUMP_VERSION,
    canonical,
    canonical_float,
    dump_file,
    dump_source,
)
from sabline.lexer import lex
from sabline.parser import Parser
from typing import Any

STAGE = "ast_dump"

REPO = Path(_support.REPO)
NDTABLE = REPO / "rt" / "crates" / "sabline-rt" / "src" / "unicode_nd.rs"


class TheDocument(unittest.TestCase):
    """What one program's dump holds."""

    def test_a_program_that_parses_is_its_tree(self) -> None:
        doc = dump_source('fn main() uses io {\n    print("hi")\n}\n')
        self.assertEqual(doc["dump"], DUMP_VERSION)
        self.assertIs(doc["ok"], True)
        self.assertEqual(set(doc["program"]), {"funcs", "records", "imports"})
        one = doc["program"]["funcs"][0]
        self.assertEqual(one["kind"], "Function")
        self.assertEqual(one["name"], "main")
        self.assertEqual(one["effects"], ["io"])
        self.assertEqual(one["line"], 1)

    def test_a_refusal_is_the_code_message_fixes_and_line(self) -> None:
        doc = dump_source("fn main() {\n    let x = 5 $ 2\n}\n")
        self.assertIs(doc["ok"], False)
        self.assertEqual(doc["error"]["code"], "E000")
        self.assertEqual(doc["error"]["message"],
                         "unexpected character '$'")
        self.assertEqual(doc["error"]["line"], 2)
        self.assertEqual(doc["error"]["fixes"],
                         ["remove or replace this character"])

    def test_for_is_already_a_while_and_a_lambda_is_already_lifted(self) -> None:
        doc = dump_source("fn main() { for i in 0 to 3 { } "
                          "let f = fn(x: Int) -> Int { return x } }")
        funcs = doc["program"]["funcs"]
        self.assertEqual([f["name"] for f in funcs], ["fn#1", "main"])
        self.assertIs(funcs[0]["is_lambda"], True)
        kinds = [s["kind"] for s in funcs[1]["body"]]
        self.assertEqual(kinds, ["Let", "While", "Let"])


class TheCanonicalForm(unittest.TestCase):
    """How the document is written, which is half of what makes it
    comparable byte for byte."""

    def test_it_is_what_json_dumps_writes(self) -> None:
        # The writer does not recurse, so that a program 4,000 levels deep
        # can be dumped; it must still write exactly what the standard
        # library writes for anything the standard library can write.
        documents: tuple[Any, ...] = (
            {"b": [], "a": {}, "c": [1, [2, {"x": None, "y": True}]]},
            1, "hi", [], {}, {"k": "café \U0001f600"},
            {"z": [[[1]]], "a": "\x00\x7f\\\"\n"})
        for doc in documents:
            want = json.dumps(doc, sort_keys=True, ensure_ascii=True,
                              separators=(",", ":"))
            self.assertEqual(canonical(doc), want, repr(doc))

    def test_a_deep_document_grows_with_depth_not_with_its_square(self) -> None:
        # Two spaces a level would make a document O(depth squared): the
        # dump of the deepest program the parser accepts was 352 MB of
        # mostly spaces, and the gate writes it twice on every leg of CI.
        doc: Any = 1
        for _ in range(2000):
            doc = {"k": doc}
        self.assertLess(len(canonical(doc)), 2000 * 8)

    def test_a_document_is_ascii_so_two_encodings_cannot_differ(self) -> None:
        doc = dump_source(
            'fn main() uses io { print("café \U0001f600 中") }')
        text = canonical(doc)
        self.assertTrue(text.isascii())
        self.assertIn("\\u00e9", text)
        self.assertIn("\\ud83d\\ude00", text)

    def test_the_deepest_program_the_parser_accepts_can_be_dumped(self) -> None:
        depth = 3999                 # the function's own body is the 4,000th
        source = "fn main() {" + "if true {" * depth + "}" * depth + "}"
        doc = _support.on_big_stack(lambda: dump_source(source))
        self.assertIs(doc["ok"], True)
        text = _support.on_big_stack(lambda: canonical(doc))
        self.assertTrue(text.startswith("{") and text.endswith("}"))
        self.assertEqual(text.count('"kind":"If"'), depth)
        # and it is a document, not a field of spaces
        self.assertLess(len(text), 2_000_000, "the dump of 40 KB of source")


class WhereTwoImplementationsCouldDiffer(unittest.TestCase):
    """Three things neither language writes the way the other does."""

    def test_a_whole_number_is_decimal_text_with_no_leading_zeros(self) -> None:
        # Num(int(t.text)) is arbitrary precision: no machine word holds one
        doc = dump_source("fn main() { let a = 007 let b = 0 let c = "
                          + "9" * 30 + " }")
        values = [s["value"]["value"]
                  for s in doc["program"]["funcs"][0]["body"]]
        self.assertEqual(values, ["7", "0", "9" * 30])

    def test_a_float_is_the_shortest_decimal_as_d_dot_ddd_e_e(self) -> None:
        rows = {"1.0": "1e0", "1.5": "1.5e0", "100.0": "1e2",
                "0.00001": "1e-5", "0.0001": "1e-4", "0.1": "1e-1",
                "123456789012345678.0": "1.2345678901234568e17"}
        for text, want in rows.items():
            got = canonical_float(float(text))
            self.assertEqual(got, want, text)
            self.assertEqual(float(got), float(text), got)
        # a literal cannot be negative - the parser wraps a minus sign in
        # Neg - and cannot be an infinity, but the form is written anyway,
        # because a dump that raised on a value it did not expect would be
        # a dump that hid a difference
        self.assertEqual(canonical_float(0.0), "0e0")
        self.assertEqual(canonical_float(-0.0), "-0e0")
        self.assertEqual(canonical_float(float("inf")), "inf")

    def test_effects_are_sorted_because_the_parser_holds_a_set(self) -> None:
        doc = dump_source("fn main() uses net, io, clock, fs { }")
        self.assertEqual(doc["program"]["funcs"][0]["effects"],
                         ["clock", "fs", "io", "net"])


class WhatTheReferenceDoesThatTheSpecDoesNotSay(unittest.TestCase):
    """Four of them. sabline-rt copies three; the fourth was changed here,
    in 9.0.0-alpha.1, because it was not stable across the CPythons this
    project supports."""

    def test_every_unicode_decimal_digit_is_a_number(self) -> None:
        # `\d` in a `str` pattern is category Nd, so a literal written in
        # Arabic-Indic or Devanagari digits is a number and int() converts
        # it. sabline-rt carries the same set (unicode_nd.rs).
        doc = dump_source("fn main() { let x = ١٢ "
                          "let y = ०१ let z = ١.٢ }")
        body = doc["program"]["funcs"][0]["body"]
        self.assertEqual(body[0]["value"], {"kind": "Num", "value": "12"})
        self.assertEqual(body[1]["value"], {"kind": "Num", "value": "1"})
        self.assertEqual(body[2]["value"],
                         {"kind": "FloatNum", "value": "1.2e0"})
        # and a non-ASCII letter is not an identifier, because the same
        # regular expression spells that rule `[A-Za-z_]`
        self.assertEqual(dump_source("fn main() { let café = 1 }")
                         ["error"]["code"], "E000")

    def test_e000_names_a_character_the_same_way_on_every_python(self) -> None:
        # It was `{...!r}`, and repr writes a character raw when the Unicode
        # database calls it printable - so the same program gave two
        # messages on two supported CPythons. `!a` asks the database
        # nothing. The agreement gate found this one.
        for char, want in (("$", "'$'"), ("!", "'!'"), ("é", "'\\xe9'"),
                           ("中", "'\\u4e2d'"),
                           ("\U0001f600", "'\\U0001f600'"),
                           ("́", "'\\u0301'"),
                           ("﻿", "'\\ufeff'"), ("\x00", "'\\x00'")):
            doc = dump_source("fn main() { let x = " + char + " }")
            self.assertEqual(doc["error"]["code"], "E000", char)
            self.assertEqual(doc["error"]["message"],
                             f"unexpected character {want}", char)

    def test_the_committed_digit_table_is_this_pythons_digits(self) -> None:
        # The table sabline-rt carries follows the Unicode version of the
        # CPython that generated it, which its header names. Where another
        # CPython disagrees, the two runtimes genuinely disagree about what
        # a digit is, and this says so rather than hiding it.
        if not NDTABLE.exists():
            self.skipTest(f"{NDTABLE} is not in this tree")
        table = NDTABLE.read_text(encoding="utf-8")
        said = re.search(r'UNICODE_VERSION: &str = "([^"]+)"', table)
        self.assertIsNotNone(said, "the table says which Unicode it is")
        runs = re.search(r"DIGIT_RUNS: \[u32; \d+\] = \[(.*?)\];",
                         table, re.S)
        self.assertIsNotNone(runs, "the table has a DIGIT_RUNS array")
        starts = [int(m, 16) for m in
                  re.findall(r"0x([0-9A-Fa-f]+)", runs.group(1) if runs else "")]
        self.assertTrue(starts, "the table has runs in it")
        theirs = {c for start in starts for c in range(start, start + 10)}
        digit = re.compile(r"\d")
        mine = {c for c in range(0x110000) if digit.fullmatch(chr(c))}
        if mine == theirs:
            return
        version = said.group(1) if said else "?"
        self.assertNotEqual(
            version, unicodedata.unidata_version,
            f"the table says Unicode {version}, which is this CPython's, "
            f"and yet {len(mine ^ theirs)} code points differ - so it was "
            f"not generated by scripts/gen_unicode_nd.py from this tree")
        differ = sorted(mine ^ theirs)[:10]
        print(f"\n    note: this CPython is Unicode "
              f"{unicodedata.unidata_version} and unicode_nd.rs is "
              f"{version}; {len(mine ^ theirs)} code points differ, the "
              f"first being " + ", ".join(f"U+{c:04X}" for c in differ)
              + ". That is a real difference between the two runtimes about "
                "what a digit is; no program in any corpus holds one.")

    def test_the_dump_resets_the_counter_the_parser_never_resets(self) -> None:
        # Parser.lambda_n is a class attribute nothing resets, so `fn#N`
        # depends on how many function values the process has parsed. The
        # dump sets it to zero per file, so a dump of one file is a
        # function of that file.
        source = "fn main() { let f = fn(x: Int) -> Int { return x } }"
        Parser.lambda_n = 700
        first = dump_source(source)
        second = dump_source(source)
        self.assertEqual(first, second)
        self.assertEqual(first["program"]["funcs"][0]["name"], "fn#1")
        # and without the reset it would not be, which is what makes the
        # reset load-bearing rather than tidy
        Parser.lambda_n = 700
        funcs, _, _ = Parser(lex(source)).parse_program()
        self.assertEqual(funcs[0].name, "fn#701")
        Parser.lambda_n = 0


class AFileIsReadTheWayTheLoaderReadsOne(unittest.TestCase):
    """`open(path, encoding="utf-8")` decides three things the lexer then
    depends on, and none of them is written in the lexer."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="sabline-ast-dump-")
        self.here = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, name: str, payload: bytes) -> str:
        path = self.here / name
        path.write_bytes(payload)
        return str(path)

    def test_a_byte_order_mark_stays_and_is_e000(self) -> None:
        # encoding="utf-8" is not "utf-8-sig"
        doc = dump_file(self.write("bom.vel",
                                   b"\xef\xbb\xbffn main() { }\n"))
        self.assertEqual(doc["error"]["code"], "E000")
        self.assertEqual(doc["error"]["message"],
                         "unexpected character '\\ufeff'")
        self.assertEqual(doc["error"]["line"], 1)

    def test_a_lone_carriage_return_is_a_newline(self) -> None:
        # universal newlines, so the line count is what the file looks
        # like; the lexer's own [ \t\r]+ never sees a \r from a file
        doc = dump_file(self.write("cr.vel", b"fn main() {\r  let x = $\r}\r"))
        self.assertEqual(doc["error"]["code"], "E000")
        self.assertEqual(doc["error"]["line"], 2)

    def test_bytes_that_are_not_utf8_are_e512(self) -> None:
        # with the loader's wording, which says "cannot import" about a
        # file nobody imported, because the entry goes through that branch
        doc = dump_file(self.write("bad.vel",
                                   b'fn main() { let x = "a\xffb" }\n'))
        self.assertEqual(doc["error"]["code"], "E512")
        self.assertIn("it is not UTF-8 text", doc["error"]["message"])

    def test_a_path_that_is_not_a_file_is_e001(self) -> None:
        doc = dump_file(str(self.here / "nothing.vel"))
        self.assertEqual(doc["error"]["code"], "E001")
        self.assertTrue(doc["error"]["message"].startswith("cannot find file "))
