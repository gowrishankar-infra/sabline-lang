"""Stage 3, the loader: imports resolved into one program, each function
remembering the file it came from.
"""
import os
import sys

from . import state as _state
from .version import _INSTALL_DIR
from .errors import SablineError
from .lexer import lex
from .nodes import Call, Var
from .parser import Parser
from .tables import BUILTINS, NEW_BUILTINS
from typing import Any

# ---------------------------------------------------------------------------
# 3b. LOADER — resolve imports into one program, remembering which file
#     every function and record came from.
# ---------------------------------------------------------------------------


def qualify(fs: list[Any], alias: str) -> None:
    """Rename a library's functions to alias.name, in place.

    References the library makes to its own functions are renamed too,
    so a namespaced import behaves exactly like the flat one from the
    inside - only the importer sees the prefix.
    """
    import dataclasses
    local = {f.name for f in fs}
    new_name = {n: f"{alias}.{n}" for n in local}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for x in node:
                walk(x)
            return
        if isinstance(node, tuple):
            for x in node:
                walk(x)
            return
        if not dataclasses.is_dataclass(node):
            return
        # A call to a name that is a builtin older than 4.3 reaches the
        # builtin, in a flat import and so here too: only the shipped
        # library may define such a name (E204), and until 8.5 http.vel's
        # own `get` took every `get(list, i)` written inside http.vel once
        # it was imported with a name - a `for` loop's included.
        if isinstance(node, Call) and node.name in BUILTINS                 and node.name not in NEW_BUILTINS:
            pass
        elif isinstance(node, (Call, Var)) and node.name in new_name:
            node.name = new_name[node.name]
        for fld in dataclasses.fields(node):
            if fld.name == "name":
                continue
            walk(getattr(node, fld.name))

    for f in fs:
        walk(f.body)
        walk([e for e, _ in f.requires])
        walk([e for e, _ in f.ensures])
    for f in fs:
        f.name = new_name[f.name]


def unknown_function(name: str, line: int, known: Any) -> SablineError:
    """One clear message for an unknown name, namespace-aware."""
    if "." in name:
        ns, _, fname = name.partition(".")
        spaces = sorted({n.split(".")[0] for n in known if "." in n})
        if ns in spaces:
            near = sorted(n.split(".", 1)[1] for n in known
                          if n.startswith(ns + "."))
            return SablineError("E200",
                f"'{ns}' has no function called '{fname}'", line,
                fixes=[f"available in '{ns}': {', '.join(near[:8])}"
                       + (" ..." if len(near) > 8 else ""),
                       "check the spelling of the name"])
        return SablineError("E200", f"no import is named '{ns}'", line,
            fixes=[f'name an import: import "lib.vel" as {ns}',
                   (f"names in scope: {', '.join(spaces)}" if spaces
                    else "an import only gets a name if you write 'as'")])
    return SablineError("E200", f"unknown function '{name}'", line,
                        fixes=[f"define 'fn {name}(...)' somewhere",
                               "check the spelling of the name"])


def _stdlib_dir() -> str:
    return os.path.normcase(os.path.realpath(
        os.path.join(_INSTALL_DIR, "stdlib")))


def _import_refusal(path: str, root: str) -> str | None:
    """Why `path` may not be imported under `root`, or None when it may."""
    shown, shown_top = os.path.realpath(path), os.path.realpath(root)
    real, top = os.path.normcase(shown), os.path.normcase(shown_top)
    std = _stdlib_dir()
    inside = (real == top or real.startswith(top.rstrip(os.sep) + os.sep)
              or real.startswith(std + os.sep))
    if not inside:
        return (f"it resolves to {shown}, outside the directory this "
                f"program is served from ({shown_top})")
    if not real.endswith(os.path.normcase(".vel")):
        return "it is not a .vel file"
    return None


def load_program(entry: str, entry_source: str | None = None,
                 loaded: list[Any] | None = None) -> tuple[Any, ...]:
    """(functions, records) of the entry file and everything it imports.
    `loaded`, when given, gets the path of each file read, in the order
    they were read - the entry first."""
    # Every later stage walks the AST recursively; the parser caps how deep
    # an expression can nest (EXPR_NEST_LIMIT / EXPR_CHAIN_LIMIT), and this
    # lifts Python's own limit so a tree up to that depth walks without a
    # traceback (the interpreter raises it too, for deep calls). 7.1.2.
    if sys.getrecursionlimit() < 20000:
        try:
            sys.setrecursionlimit(20000)
        except Exception:
            pass
    funcs, records = [], []
    fn_src: dict[str, str] = {}
    rec_src: dict[str, str] = {}
    visited = set()

    def load(path: str, importer: str | None, iline: int = 1,
             alias: str | None = None) -> Any:
        ap = os.path.abspath(path)
        if ap in visited:
            return                       # already loaded (diamond or cycle)
        visited.add(ap)
        source = None
        if importer is None and entry_source is not None:
            source = entry_source
        if importer is not None and _state.IMPORT_ROOT is not None:
            why = _import_refusal(path, _state.IMPORT_ROOT)
            if why is not None:
                raise SablineError("E515",
                    f"cannot import '{path}': {why}", iline,
                    fixes=["import a .vel file inside the served directory, "
                           "or a file of the standard library"],
                    file=importer)
        try:
            if source is None:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
        except OSError:
            if importer is not None:
                shipped = os.path.join(
                    _INSTALL_DIR,
                    "stdlib", os.path.basename(path))
                if os.path.exists(shipped):
                    visited.discard(ap)
                    return load(shipped, importer, iline, alias)
            if importer is None:
                raise SablineError("E001", f"cannot find file '{path}'", 1,
                    fixes=["check the file name spelling",
                           "make sure you are in the folder that contains it"])
            raise SablineError("E512",
                f"cannot find imported file '{path}'", iline,
                fixes=["check the path in the import line",
                       "paths are relative to the importing file"],
                file=importer)
        except UnicodeDecodeError:
            raise SablineError("E512",
                f"cannot import '{path}': it is not UTF-8 text, so it is not "
                f"Sabline source", iline,
                fixes=["an import names a .vel file"], file=importer)
        if loaded is not None:
            loaded.append(path)
        try:
            tokens = lex(source)
            fs, rs, imports = Parser(tokens).parse_program()
        except SablineError as e:
            if importer is not None and not os.path.normcase(path).endswith(
                    os.path.normcase(".vel")):
                # a lexer or parser error quotes what it found, and in a
                # file that is not Sabline source what it found is the
                # file's content: `import "/home/me/.env"` answered
                # "expected 'fn' but found 'API_KEY'". Until 8.1 that went
                # to whoever sent the program - through the HTTP door and
                # the MCP server included. The error now names the file
                # and says nothing about what is in it.
                raise SablineError(e.code,
                    f"'{path}' is imported, and it is not Sabline source; "
                    f"what it holds is not shown", iline,
                    fixes=["an import names a .vel file"], file=importer)
            e.file = e.file or path
            raise
        base = os.path.dirname(path)
        for ipath, iline, ialias in imports:   # ialias: don't shadow alias
            load(os.path.join(base, ipath) if base else ipath, path, iline,
                 ialias)
        if alias:
            qualify(fs, alias)
        for f in fs:
            f.src_file = path
            if f.name in fn_src:
                where = (f"twice in '{path}'" if fn_src[f.name] == path
                         else f"in both '{fn_src[f.name]}' and '{path}'")
                raise SablineError("E513",
                    f"function '{f.name}' is defined {where}", f.line,
                    fixes=["rename one of them"], file=path)
            fn_src[f.name] = path
            funcs.append(f)
        for r in rs:
            r.src_file = path
            if r.name in rec_src:
                where = (f"twice in '{path}'" if rec_src[r.name] == path
                         else f"in both '{rec_src[r.name]}' and '{path}'")
                raise SablineError("E513",
                    f"record '{r.name}' is defined {where}", r.line,
                    fixes=["rename one of them"], file=path)
            rec_src[r.name] = path
            records.append(r)

    load(entry, None)
    _bind_new_builtins(funcs)
    return funcs, records


def _bind_new_builtins(funcs: list[Any]) -> None:
    """A builtin added from 4.3 on gives way to a program's own function
    of the same name (SPEC.md 10.1). Inside a library imported with a
    name, though, a call can only mean the builtin: the library's own
    functions carry its prefix, and it was not written against the
    program that imports it. When the program's plain names hide such a
    builtin, the library's calls to it are bound to it here, as '@name'.
    Programs with no such clash are left exactly as parsed."""
    hidden = NEW_BUILTINS & {f.name for f in funcs if "." not in f.name}
    if not hidden:
        return
    import dataclasses as _dc

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call) and node.name in hidden:
            node.name = "@" + node.name
        for fl in _dc.fields(node):
            walk(getattr(node, fl.name))

    for f in funcs:
        if "." in f.name:
            walk(f.body)
            walk(f.requires)
            walk(f.ensures)


def blame(fn_or_rec: Any, err: SablineError) -> SablineError:
    """Attach the true source file to an error, innermost wins."""
    err.file = err.file or fn_or_rec.src_file or None
    return err
