"""Stage 3, the loader, alone: velaris.loader.load_program.

SPEC.md 10: imports resolve relative to the importing file with the
standard library searched last; a plain import merges names and rejects
duplicates (E513); a named import prefixes the file's functions and
rewrites the library's references to them; cycles are rejected; under an
import root only .vel files inside it and the standard library may be
imported (E515, before the file is read); and an error inside an
imported file that is not .vel shows nothing of its content. SPEC.md
10.1: a builtin a program's own function hides is still the builtin
inside a library imported with a name.
"""
import dataclasses
import os
import shutil
import tempfile
import unittest

import _support
from velaris import state
from velaris.errors import VelarisError
from velaris.loader import load_program
from velaris.nodes import Call, Var
from typing import Any

STAGE = "loader"


def path(*parts: str) -> str:
    return _support.fixture(STAGE, *parts)


def names(funcs: Any) -> set[Any]:
    return {f.name for f in funcs}


def by_name(funcs: Any) -> dict[Any, Any]:
    return {f.name: f for f in funcs}


def referenced(tree: Any) -> list[Any]:
    """The names of every call and variable in a tree, in order."""
    out = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not dataclasses.is_dataclass(node):
            return
        if isinstance(node, (Call, Var)):
            out.append(node.name)
        for f in dataclasses.fields(node):
            walk(getattr(node, f.name))

    walk(tree)
    return out


class LoaderTest(unittest.TestCase):

    def setUp(self) -> None:
        self._root = state.IMPORT_ROOT
        state.IMPORT_ROOT = None

    def tearDown(self) -> None:
        state.IMPORT_ROOT = self._root

    def refused(self, entry: str, **kw: Any) -> VelarisError:
        with self.assertRaises(VelarisError) as caught:
            load_program(entry, **kw)
        return caught.exception

    def assertSamePath(self, a: Any, b: Any) -> None:
        self.assertTrue(_support.same_path(a, b), f"{a!r} is not {b!r}")


class Resolution(LoaderTest):

    def test_entry_and_its_imports_become_one_program(self) -> None:
        funcs, records = load_program(path("relative", "main.vel"))
        self.assertEqual(names(funcs), {"main", "double", "helper_add"})
        self.assertEqual(records, [])

    def test_import_resolves_beside_the_importing_file(self) -> None:
        funcs, _ = load_program(path("relative", "main.vel"))
        self.assertNotIn("decoy_helper", names(funcs))
        self.assertSamePath(by_name(funcs)["helper_add"].src_file,
                            path("relative", "lib", "helper.vel"))

    def test_each_function_remembers_its_file(self) -> None:
        funcs, _ = load_program(path("relative", "main.vel"))
        fns = by_name(funcs)
        self.assertSamePath(fns["main"].src_file, path("relative", "main.vel"))
        self.assertSamePath(fns["double"].src_file,
                            path("relative", "lib", "util.vel"))

    def test_files_are_listed_in_the_order_read(self) -> None:
        loaded: list[str] = []
        load_program(path("relative", "main.vel"), loaded=loaded)
        self.assertEqual(len(loaded), 3)
        for got, want in zip(loaded, [("main.vel",), ("lib", "util.vel"),
                                      ("lib", "helper.vel")]):
            self.assertSamePath(got, path("relative", *want))

    def test_a_file_two_imports_share_is_loaded_once(self) -> None:
        loaded: list[str] = []
        funcs, _ = load_program(path("diamond", "main.vel"), loaded=loaded)
        self.assertEqual(sorted(f.name for f in funcs),
                         ["left", "main", "right", "shared"])
        self.assertEqual(sum(os.path.basename(p) == "shared.vel"
                             for p in loaded), 1)

    def test_standard_library_is_searched_last(self) -> None:
        funcs, _ = load_program(path("stdlib", "main.vel"))
        first = by_name(funcs)["first"]
        self.assertTrue(os.path.normcase(os.path.realpath(first.src_file))
                        .startswith(os.path.normcase(
                            os.path.realpath(_support.STDLIB)) + os.sep))

    def test_a_file_beside_the_importer_comes_before_the_standard_library(self) -> None:
        funcs, _ = load_program(path("local_std", "main.vel"))
        self.assertIn("local_std_marker", names(funcs))
        self.assertNotIn("first", names(funcs))

    def test_entry_source_stands_in_for_the_entry_file(self) -> None:
        virtual = path("relative", "not_on_disk.vel")
        loaded: list[str] = []
        funcs, _ = load_program(
            virtual, 'import "lib/util.vel"\n\nfn main() uses io {\n'
                     '    print(double(1))\n}\n', loaded=loaded)
        self.assertEqual(names(funcs), {"main", "double", "helper_add"})
        self.assertEqual(loaded[0], virtual)

    def test_missing_entry_is_E001(self) -> None:
        e = self.refused(path("relative", "no_such_entry.vel"))
        self.assertEqual((e.code, e.line), ("E001", 1))

    def test_missing_import_is_E512_at_the_import(self) -> None:
        e = self.refused(path("missing", "main.vel"))
        self.assertEqual((e.code, e.line), ("E512", 1))
        self.assertSamePath(e.file, path("missing", "main.vel"))
        self.assertIn("not_here.vel", e.message)

    def test_error_inside_an_imported_file_names_that_file(self) -> None:
        e = self.refused(path("broken", "main.vel"))
        self.assertEqual((e.code, e.line), ("E100", 1))
        self.assertSamePath(e.file, path("broken", "bad.vel"))

    def test_import_that_is_not_utf8_is_E512(self) -> None:
        d = tempfile.mkdtemp(prefix="velaris-unit-loader-")
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, "main.vel"), "w", encoding="utf-8") as f:
            f.write('import "blob.vel"\n\nfn main() uses io {\n    print(1)\n}\n')
        with open(os.path.join(d, "blob.vel"), "wb") as f:
            f.write(b"\xff\xfe\x00 fn \x81\x82")
        e = self.refused(os.path.join(d, "main.vel"))
        self.assertEqual((e.code, e.line), ("E512", 1))
        self.assertIn("not UTF-8", e.message)


class NamedImports(LoaderTest):

    def setUp(self) -> None:
        super().setUp()
        self.funcs, self.records = load_program(path("named", "main.vel"))
        self.fns = by_name(self.funcs)

    def test_the_file_s_functions_carry_the_prefix(self) -> None:
        self.assertEqual(names(self.funcs),
                         {"main", "geo.mul", "geo.area", "geo.pick"})

    def test_the_library_s_references_to_itself_carry_it_too(self) -> None:
        self.assertEqual(referenced(self.fns["geo.area"].body),
                         ["geo.mul", "w", "h"])
        self.assertEqual(referenced(self.fns["geo.pick"].body), ["geo.mul"])

    def test_the_importer_calls_through_the_prefix(self) -> None:
        self.assertIn("geo.area", referenced(self.fns["main"].body))

    def test_records_keep_their_names(self) -> None:
        self.assertEqual([r.name for r in self.records], ["Size"])
        self.assertSamePath(self.records[0].src_file, path("named", "geo.vel"))

    def test_a_builtin_the_program_hides_is_still_the_builtin_in_the_library(self) -> None:
        funcs, _ = load_program(path("give_way", "main.vel"))
        fns = by_name(funcs)
        split = fns["money.split"]
        library_calls = referenced([split.body, split.requires, split.ensures])
        self.assertIn("@units_of", library_calls)
        self.assertNotIn("units_of", library_calls)
        self.assertIn("with_units", library_calls)     # not hidden: as parsed
        self.assertIn("units_of", referenced(fns["main"].body))
        self.assertNotIn("@units_of", referenced(fns["main"].body))

    def test_without_a_clash_the_library_is_left_as_parsed(self) -> None:
        funcs, _ = load_program(path("give_way", "plain.vel"))
        split = by_name(funcs)["money.split"]
        calls = referenced([split.body, split.requires, split.ensures])
        self.assertIn("units_of", calls)
        self.assertFalse(any(n.startswith("@") for n in calls))


def setUpModule() -> None:
    _support.quiet_unclosed_source_files()


class Cycles(LoaderTest):
    """SPEC.md 10: an import cycle loads, and each file in it is read once,
    as a file two imports reach is. Until 8.2 SPEC.md said cycles were
    rejected; the loader never did that, and the document now says so."""

    def test_two_files_importing_each_other_load_once_each(self) -> None:
        read: list[Any] = []
        load_program(path("cycle", "a.vel"), loaded=read)
        self.assertEqual(sorted(os.path.basename(p) for p in read),
                         ["a.vel", "b.vel"])

    def test_a_file_importing_itself_loads_once(self) -> None:
        read: list[Any] = []
        load_program(path("cycle", "self.vel"), loaded=read)
        self.assertEqual([os.path.basename(p) for p in read], ["self.vel"])


class Duplicates(LoaderTest):

    def test_function_defined_in_two_files_is_E513(self) -> None:
        main = path("dup_files", "main.vel")
        e = self.refused(main)
        self.assertEqual((e.code, e.line), ("E513", 3))
        self.assertSamePath(e.file, main)
        self.assertIn("'total'", e.message)
        self.assertIn("other.vel", e.message)
        self.assertIn("main.vel", e.message)

    def test_function_defined_twice_in_one_file_is_E513(self) -> None:
        e = self.refused(path("dup_same", "main.vel"))
        self.assertEqual((e.code, e.line), ("E513", 5))
        self.assertIn("twice in", e.message)

    def test_record_defined_in_two_files_is_E513(self) -> None:
        e = self.refused(path("dup_record", "main.vel"))
        self.assertEqual((e.code, e.line), ("E513", 3))
        self.assertIn("record 'Point'", e.message)


class ImportRoot(LoaderTest):
    """SPEC.md 10, from 8.1: a program compiled under an import root."""

    def setUp(self) -> None:
        super().setUp()
        state.IMPORT_ROOT = path("served", "root")

    def test_import_outside_the_root_is_E515(self) -> None:
        entry = path("served", "root", "escape.vel")
        e = self.refused(entry)
        self.assertEqual((e.code, e.line), ("E515", 1))
        self.assertSamePath(e.file, entry)
        self.assertIn("outside the directory", e.message)

    def test_refused_before_the_file_is_read(self) -> None:
        # a file that does not exist is refused the same way, so a
        # refusal does not tell whether it exists
        e = self.refused(path("served", "root", "ghost.vel"))
        self.assertEqual((e.code, e.line), ("E515", 1))

    def test_non_vel_file_inside_the_root_is_E515(self) -> None:
        e = self.refused(path("served", "root", "reads_notes.vel"))
        self.assertEqual((e.code, e.line), ("E515", 1))
        self.assertIn("not a .vel file", e.message)

    def test_vel_files_at_or_under_the_root_and_the_standard_library(self) -> None:
        funcs, _ = load_program(path("served", "root", "inside.vel"))
        self.assertTrue({"main", "inner", "other", "first"} <= names(funcs))

    def test_without_a_root_nothing_of_this_is_checked(self) -> None:
        state.IMPORT_ROOT = None
        funcs, _ = load_program(path("served", "root", "escape.vel"))
        self.assertIn("outside", names(funcs))
        funcs, _ = load_program(path("served", "root", "reads_notes.vel"))
        self.assertIn("notes", names(funcs))


class NonVelarisImports(LoaderTest):
    """SPEC.md 10: an error inside an imported file that is not a .vel
    file names the file and shows nothing of its content."""

    def assert_reveals_nothing(self, entry: Any, imported: Any, content_bits: Any) -> Any:
        e = self.refused(entry)
        shown = " ".join([e.message] + list(e.fixes))
        for bit in content_bits:
            self.assertNotIn(bit, shown)
        self.assertIn(imported, e.message)
        self.assertSamePath(e.file, entry)
        self.assertEqual(e.line, 1)
        return e

    def test_a_parse_error_shows_nothing_of_the_file(self) -> None:
        e = self.assert_reveals_nothing(path("nonvel", "main.vel"),
                                        "settings.env",
                                        ["API_KEY", "unit-fixture-value"])
        self.assertEqual(e.code, "E100")
        self.assertIn("not shown", e.message)

    def test_a_lexer_error_shows_nothing_of_the_file(self) -> None:
        e = self.assert_reveals_nothing(path("nonvel", "lexes.vel"),
                                        "token.txt",
                                        ["$", "ecret", "token-for"])
        self.assertEqual(e.code, "E000")

    def test_under_a_root_it_is_refused_unread(self) -> None:
        state.IMPORT_ROOT = path("nonvel")
        e = self.refused(path("nonvel", "main.vel"))
        self.assertEqual(e.code, "E515")
        self.assertNotIn("API_KEY", e.message)


if __name__ == "__main__":
    unittest.main()
