"""Stage 1, the lexer, alone: sabline.lexer.lex and unescape.

SPEC.md 2 is what these hold it to: comments, identifiers, keywords and
the literal table, plus the refusals - a character the lexer cannot
read (E000), bidi and zero-width characters outside text among them
(CHANGELOG 7.1.2), and an escape it does not know (E002, raised by
unescape, which the parser calls on every text literal).
"""
import json
import unittest

import _support
from sabline.errors import SablineError
from sabline.lexer import KEYWORDS, lex, unescape
from typing import Any

STAGE = "lexer"

# SPEC.md 2, "Keywords:", word for word.
SPEC_KEYWORDS = set("fn let return if else uses true false while for "
                    "requires ensures and or not invariant record import "
                    "fail check try".split())

BIDI_CONTROLS = ["‪", "‫", "‬", "‭", "‮",
                 "⁦", "⁧", "⁨", "⁩",
                 "‎", "‏", "؜"]
ZERO_WIDTH = ["​", "‌", "‍", "⁠", "﻿"]


def triples(tokens: Any) -> list[Any]:
    return [[t.kind, t.text, t.line] for t in tokens]


def kinds(source: str) -> list[Any]:
    return [(t.kind, t.text) for t in lex(source)][:-1]    # without EOF


class TokenFixtures(unittest.TestCase):
    """Each fixtures/lexer/<name>.vel lexes to its <name>.tokens.json."""

    def assert_fixture(self, name: str) -> None:
        with open(_support.fixture(STAGE, name + ".tokens.json"),
                  encoding="utf-8") as f:
            want = json.load(f)
        source = _support.read_fixture(STAGE, name + ".vel")
        got = triples(lex(source, keep_trivia=want["keep_trivia"]))
        self.assertEqual(got, want["tokens"])

    def test_literals(self) -> None:
        self.assert_fixture("literals")

    def test_keywords_and_identifiers(self) -> None:
        self.assert_fixture("keywords")

    def test_operators(self) -> None:
        self.assert_fixture("operators")

    def test_comments_as_trivia(self) -> None:
        self.assert_fixture("comments")

    def test_program_line_numbers(self) -> None:
        self.assert_fixture("program")


class Literals(unittest.TestCase):

    def test_float_needs_digits_on_both_sides(self) -> None:
        self.assertEqual(kinds("1. .5"),
                         [("NUMBER", "1"), ("OP", "."), ("OP", "."),
                          ("NUMBER", "5")])

    def test_no_exponent_form(self) -> None:
        # SPEC.md 2 lists no exponent; 1e5 is a number then a name
        self.assertEqual(kinds("1e5"), [("NUMBER", "1"), ("IDENT", "e5")])

    def test_number_then_name_without_space(self) -> None:
        self.assertEqual(kinds("1abc"), [("NUMBER", "1"), ("IDENT", "abc")])

    def test_text_token_keeps_quotes_and_escapes_raw(self) -> None:
        (tok, _eof) = lex(r'"a\tb\\c"')
        self.assertEqual((tok.kind, tok.text), ("STRING", r'"a\tb\\c"'))

    def test_lexer_accepts_any_escape_and_unescape_judges_it(self) -> None:
        # the token is read whatever follows the backslash; E002 is
        # unescape's, when the parser turns the token into text
        self.assertEqual(kinds(r'"\q"'), [("STRING", r'"\q"')])

    def test_text_cannot_span_lines(self) -> None:
        with self.assertRaises(SablineError) as caught:
            lex('let t = "one\ntwo"')
        self.assertEqual((caught.exception.code, caught.exception.line),
                         ("E000", 1))

    def test_unterminated_text(self) -> None:
        with self.assertRaises(SablineError) as caught:
            lex('\n\nprint("never closed)')
        self.assertEqual((caught.exception.code, caught.exception.line),
                         ("E000", 3))

    def test_bool_literals_are_keywords(self) -> None:
        self.assertEqual(kinds("true false"),
                         [("KEYWORD", "true"), ("KEYWORD", "false")])


class Escapes(unittest.TestCase):
    """SPEC.md 2: escapes \\n \\t \\\\ \\", and E002 for any other."""

    def test_documented_escapes(self) -> None:
        self.assertEqual(unescape(r'a\nb\tc\\d\"e', 1), 'a\nb\tc\\d"e')

    def test_carriage_return_and_nul_are_not_escapes(self) -> None:
        """Until 8.2 SPEC.md 2 listed \\r and \\0 too; the lexer never took
        them, and the document now says so."""
        for text in (r"a\rb", r"a\0b"):
            with self.subTest(text=text):
                with self.assertRaises(SablineError) as caught:
                    unescape(text, 3)
                self.assertEqual(caught.exception.code, "E002")

    def test_unknown_escape_is_E002(self) -> None:
        with self.assertRaises(SablineError) as caught:
            unescape(r"bad \q here", 7)
        e = caught.exception
        self.assertEqual((e.code, e.line), ("E002", 7))
        self.assertIn(r"'\q'", e.message)

    def test_trailing_backslash_is_E002(self) -> None:
        with self.assertRaises(SablineError) as caught:
            unescape("ends with \\", 2)
        self.assertEqual(caught.exception.code, "E002")

    def test_text_without_escapes_is_unchanged(self) -> None:
        self.assertEqual(unescape("plain // text {}", 1), "plain // text {}")


class KeywordsAndIdentifiers(unittest.TestCase):

    def test_keywords_are_the_documented_set(self) -> None:
        self.assertEqual(set(KEYWORDS), SPEC_KEYWORDS)

    def test_every_keyword_lexes_as_a_keyword(self) -> None:
        for word in sorted(SPEC_KEYWORDS):
            with self.subTest(word=word):
                self.assertEqual(kinds(word), [("KEYWORD", word)])

    def test_identifier_characters(self) -> None:
        self.assertEqual(kinds("_a1 A_b_2 __"),
                         [("IDENT", "_a1"), ("IDENT", "A_b_2"),
                          ("IDENT", "__")])

    def test_identifiers_are_ascii(self) -> None:
        # SPEC.md 2 says "a letter"; the lexer reads ASCII letters only,
        # so a name that looks the same as another cannot be two names
        with self.assertRaises(SablineError) as caught:
            lex("let café = 1")
        self.assertEqual(caught.exception.code, "E000")


class Refusals(unittest.TestCase):

    def assert_E000(self, source: str, char: str, line: int = 1) -> None:
        with self.assertRaises(SablineError) as caught:
            lex(source)
        e = caught.exception
        self.assertEqual((e.code, e.line), ("E000", line))
        self.assertIn(repr(char), e.message)

    def test_characters_the_lexer_cannot_read(self) -> None:
        for char in "!&|@#$^~?;`'\\":
            with self.subTest(char=char):
                self.assert_E000(f"let x = 1 {char} 2", char)

    def test_bidi_controls_outside_text(self) -> None:
        for char in BIDI_CONTROLS:
            with self.subTest(char=f"U+{ord(char):04X}"):
                self.assert_E000(f"fn main() uses io {{\n  let x = 1{char}0\n}}",
                                 char, line=2)

    def test_zero_width_characters_outside_text(self) -> None:
        for char in ZERO_WIDTH:
            with self.subTest(char=f"U+{ord(char):04X}"):
                self.assert_E000(f"fn ma{char}in() uses io {{ }}", char)

    def test_bidi_and_zero_width_inside_text_are_text(self) -> None:
        for char in BIDI_CONTROLS + ZERO_WIDTH:
            with self.subTest(char=f"U+{ord(char):04X}"):
                source = f'"a{char}b"'
                self.assertEqual(kinds(source), [("STRING", source)])

    def test_refusal_names_its_line(self) -> None:
        self.assert_E000("fn f() {\n\n  let y = 2 ? 3\n}", "?", line=3)


class Trivia(unittest.TestCase):

    def test_comments_and_newlines_dropped_without_trivia(self) -> None:
        with_trivia = lex(_support.read_fixture(STAGE, "comments.vel"),
                          keep_trivia=True)
        without = lex(_support.read_fixture(STAGE, "comments.vel"))
        self.assertEqual(
            triples(without),
            [t for t in triples(with_trivia)
             if t[0] not in ("COMMENT", "NEWLINE")])

    def test_comment_ends_at_the_line_break(self) -> None:
        self.assertEqual(triples(lex("a // b c\nd")),
                         [["IDENT", "a", 1], ["IDENT", "d", 2],
                          ["EOF", "", 2]])

    def test_crlf_counts_one_line(self) -> None:
        self.assertEqual(triples(lex("a\r\nb\r\n\r\nc")),
                         [["IDENT", "a", 1], ["IDENT", "b", 2],
                          ["IDENT", "c", 4], ["EOF", "", 4]])

    def test_spaces_tabs_and_carriage_returns_separate_only(self) -> None:
        self.assertEqual(kinds("a\t b\r c"),
                         [("IDENT", "a"), ("IDENT", "b"), ("IDENT", "c")])

    def test_empty_source_is_end_of_file_on_line_one(self) -> None:
        self.assertEqual(triples(lex("")), [["EOF", "", 1]])

    def test_end_of_file_carries_the_last_line(self) -> None:
        self.assertEqual(lex("a\n\n\n")[-1].line, 4)


if __name__ == "__main__":
    unittest.main()
