#!/usr/bin/env python3
"""What cannot occur in a Sabline program, each claim held by a program that
tries it (8.3). docs/structurally-impossible.md is held to this file: a
class with no test here is not on that page, and the page lists no class
that is not tested here.

    python check_impossible.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_impossible")
PAGE = HERE / "docs" / "structurally-impossible.md"
PASSED = FAILED = 0


def ok(label: str, good: bool, detail: Any = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok      {label}")
    else:
        FAILED += 1
        print(f"  WRONG   {label}")
        if detail:
            print(f"          {str(detail)[:600]}")


def compiles(source: str) -> Any:
    return sabline.check(source, prove=False, timeout=None,
                         max_memory_mb=None)


def refused_before_running(label: str, source: str,
                           codes: tuple[str, ...] = ()) -> None:
    got = compiles(source)
    found = [p.code for p in got.problems]
    ok(label, not got.ok and (not codes or any(c in codes for c in found)),
       [(p.code, p.message[:120]) for p in got.problems])


def main_of(body: str, uses: str = "io") -> str:
    return f"fn main() uses {uses} {{\n{body}\n}}\n"


# ---- CWE-78: OS command injection ------------------------------------------

def cwe_78() -> None:
    print("CWE-78: no program starts a process or builds a command line")
    print("-" * 62)
    words = ("system", "shell", "exec", "spawn", "popen", "run_command",
             "subprocess", "command", "execute", "sh")
    ok("no builtin is named for starting a process",
       not set(words) & set(sabline.BUILTINS), set(words) & set(sabline.BUILTINS))
    for word in ("system", "shell", "exec", "spawn", "popen"):
        refused_before_running(
            f"{word}(\"rm -rf /tmp/x\") does not compile: there is no such "
            f"function", main_of(f'    {word}("rm -rf /tmp/x")'))
    run = sabline.run(main_of('    check py("subprocess", "run", ["whoami"]) '
                              '{\n        ok r {\n            print(r)\n'
                              '        }\n        fail w {\n'
                              '            print(w)\n        }\n    }',
                              uses="io, ffi"), allow="io")
    ok("reaching subprocess through py is refused without an ffi grant "
       "(E310), and nothing is started", not run.ok
       and [p.code for p in run.problems] == ["E310"], run.problems)
    run = sabline.run(main_of('    check py("os", "system", ["whoami"]) {\n'
                              '        ok r {\n            print(r)\n'
                              '        }\n        fail w {\n'
                              '            print(w)\n        }\n    }',
                              uses="io, ffi"), allow="io,ffi:json")
    ok("...and through a module the grant does not name (E311)",
       not run.ok and [p.code for p in run.problems] == ["E311"],
       run.problems)


# ---- CWE-95 and CWE-94: eval and code injection --------------------------

def cwe_95() -> None:
    print()
    print("CWE-95 and CWE-94: no text is run as code")
    print("-" * 62)
    words = ("eval", "compile", "load", "run_source", "exec", "import_text",
             "parse", "interpret")
    ok("no builtin evaluates text", not set(words) & set(sabline.BUILTINS),
       set(words) & set(sabline.BUILTINS))
    for word in ("eval", "compile", "load"):
        refused_before_running(
            f"{word}(\"print(1)\") does not compile",
            main_of(f'    {word}("fn main() uses io {{ print(1) }}")'))
    refused_before_running(
        "import takes a written string, not a value: import of a variable "
        "does not parse",
        'let where = "lib.vel"\nimport where as lib\n' + main_of('    print("x")'))
    refused_before_running(
        "...nor an expression",
        'import "li" + "b.vel" as lib\n' + main_of('    print("x")'))
    run = sabline.run(main_of('    let text = format("{}", "fn main() uses io { print(1) }")\n'
                              '    print(text)'), allow="io")
    ok("text that holds a program is printed as text, not run",
       run.ok and "fn main()" in run.output and run.output.count("\n") == 1,
       run.output)


# ---- CWE-502: deserialization of untrusted data --------------------------

def cwe_502() -> None:
    print()
    print("CWE-502: reading data gives data, never code or an object")
    print("-" * 62)
    doc = '{\\"__class__\\": \\"os.system\\", \\"py/object\\": \\"subprocess.Popen\\"}'
    run = sabline.run(main_of(
        f'    check json_get("{doc}", "__class__") {{\n'
        '        ok v {\n            print(v)\n        }\n'
        '        fail w {\n            print(w)\n        }\n    }'),
        allow="io")
    ok("a JSON document naming a class gives back that text, and nothing is "
       "constructed", run.ok and run.output.strip() == "os.system",
       (run.output, run.problems))
    ok("every JSON builtin returns Text, Int, Float or Bool",
       all(sabline.BUILTINS[n]["ret"] in ("Text", "Int", "Float", "Bool")
           for n in ("json_get", "json_int", "json_float", "json_len",
                     "json_has", "json_of")),
       {n: sabline.BUILTINS[n]["ret"] for n in sabline.BUILTINS
        if n.startswith("json_")})
    run = sabline.run(main_of(
        '    check py_json("pickle", "loads", "[]") {\n'
        '        ok r {\n            print(r)\n        }\n'
        '        fail w {\n            print(w)\n        }\n    }',
        uses="io, ffi"), allow="io")
    ok("reaching pickle through py_json is refused without an ffi grant "
       "(E310)", not run.ok and [p.code for p in run.problems] == ["E310"],
       run.problems)


# ---- CWE-200: a path built from a secret ---------------------------------

def cwe_200() -> None:
    print()
    print("CWE-200 (one route to it): no path, file name or file content is "
          "built from a Secret")
    print("-" * 62)
    uses = "io, env, fs"
    for label, body in [
            ("read_file of a secret",
             '    check read_file(env("TOKEN", "")) {\n        ok t {\n'
             '            print("read")\n        }\n        fail w {\n'
             '            print("no")\n        }\n    }'),
            ("read_file of a path joined with a secret",
             '    check read_file("data/" + env("TOKEN", "")) {\n'
             '        ok t {\n            print("read")\n        }\n'
             '        fail w {\n            print("no")\n        }\n    }'),
            ("write_file to a path holding a secret",
             '    write_file(env("TOKEN", "") + ".txt", "x")'),
            ("write_file of a secret's text",
             '    write_file("out.txt", env("TOKEN", ""))'),
            ("file_exists of a secret",
             '    if file_exists(env("HOME", "")) {\n        print("x")\n    }')]:
        refused_before_running(f"{label} does not compile (E560)",
                               main_of(body, uses=uses), ("E560",))


# ---- CWE-117: log injection ----------------------------------------------

LOG_CALLS = (("log", 'log(bad)'), ("log.info", 'log.info(bad)'),
             ("log.warn", 'log.warn(bad)'), ("log.error", 'log.error(bad)'),
             ("log.event", 'log.event("name", bad)'),
             ("log.die", 'log.die(bad)'), ("log.fail_with", 'log.fail_with(bad)'))


def cwe_117() -> None:
    print()
    print("CWE-117: a value cannot forge a line of the log (8.3)")
    print("-" * 62)
    stdlib = HERE / "stdlib" / "log.vel"
    (WORK / "log.vel").write_text(stdlib.read_text(encoding="utf-8"),
                                  encoding="utf-8")
    # Sabline text writes a line feed as \n and has no escape for the other
    # three, so those arrive on standard input, the way a value from outside
    # would
    for char, shown, typed in (("LF", "\\n", None), ("CR", "\\r", "\r"),
                               ("ESC", "\\x1b", "\x1b"),
                               ("NUL", "\\x00", "\x00")):
        for name, call in LOG_CALLS:
            if typed is None:
                make, stdin = '    let bad = "ok\\nERROR forged line"', ""
            else:
                make = "    let bad = read_line()"
                stdin = f"ok{typed}ERROR forged line\n"
            source = 'import "log.vel" as log\n\n' + main_of(
                make + "\n    " + call)
            path = WORK / "logs.vel"
            path.write_text(source, encoding="utf-8")
            run = sabline.run(source, path=str(path), allow="io", stdin=stdin)
            lines = [x for x in run.logs.split("\n") if x]
            ok(f"{name} of a value holding {char} writes one line, the "
               f"character escaped", len(lines) == 1 and shown in lines[0]
               and "ERROR forged line" in lines[0],
               (run.logs, run.problems))


# a way to make a text holding any character, in Sabline as it is
CHARS_OF = """fn chars_of(code: Int) -> Text {
    check py("builtins", "chr", [to_text(code)]) {
        ok c {
            return c
        }
        fail w {
            return ""
        }
    }
}

"""


# ---- not structurally impossible: SQL injection through db.vel ---------

def not_cwe_89() -> None:
    print()
    print("CWE-89 is NOT impossible: stdlib/db.vel builds SQL from text")
    print("-" * 62)
    db = (HERE / "stdlib" / "db.vel").read_text(encoding="utf-8")
    ok("db.vel's run takes the SQL as one text, with no parameters",
       "fn run(conn: Handle, sql: Text)" in db)
    ok("...and its count writes a table name into the SQL with format",
       'format("select count(*) from {}", table)' in db)


TESTS: dict[str, Callable[[], None]] = {
    "CWE-78": cwe_78, "CWE-95": cwe_95, "CWE-94": cwe_95,
    "CWE-502": cwe_502, "CWE-200": cwe_200, "CWE-117": cwe_117}
NOT_IMPOSSIBLE: dict[str, Callable[[], None]] = {"CWE-89": not_cwe_89}


def page() -> None:
    print()
    print("docs/structurally-impossible.md and this suite agree")
    print("-" * 62)
    text = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
    impossible, _sep, rest = text.partition("## Not structurally impossible")
    claimed = set(re.findall(r"\bCWE-\d+\b", impossible))
    not_claimed = set(re.findall(r"\bCWE-\d+\b", rest))
    ok("every class the page says cannot occur has a test here",
       claimed <= set(TESTS), sorted(claimed - set(TESTS)))
    ok("...and every class tested here is on the page",
       set(TESTS) <= claimed, sorted(set(TESTS) - claimed))
    ok("the classes the page says are not impossible are the ones this "
       "suite shows are not", not_claimed == set(NOT_IMPOSSIBLE),
       (sorted(not_claimed), sorted(NOT_IMPOSSIBLE)))


def main() -> int:
    seen = set()
    for fn in list(TESTS.values()) + list(NOT_IMPOSSIBLE.values()):
        if fn not in seen:
            seen.add(fn)
            fn()
    page()
    print("-" * 62)
    print(f"{PASSED} correct, {FAILED} wrong")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
