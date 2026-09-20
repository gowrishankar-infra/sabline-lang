#!/usr/bin/env python3
"""The capability ratchet: a widening must never pass, and a change that
does not widen must never fail.

`sabline capabilities check` holds a tree to the surface declared in
sabline.capabilities. The point of it is gradual change - capability
assembled across many commits, each of which looks fine on its own -
and that is only caught if every commit is compared with the declared
baseline, never with the commit before it. So this suite does not
assert that the check catches a widening in one diff; it builds real
git histories and asserts what the check says at every commit of them,
and it holds a previous-commit comparison beside it to show where that
one goes blind.

The scenarios are data (4.1). Every entry of DERIVE, CHECKS, SEQUENCES,
WRITE_GUARD, COVERING, REDUCE and BOUNDS is also a case in sabline-spec's
conformance corpus (tests/L3), written out by build_conformance.py, with
the expectation written here; main() runs each against this
implementation first, then asserts what only this implementation
reports - the call chain, the review, the SARIF.

Every case runs the command line in a scratch directory. Nothing here
needs the prover or the network.

    python check_ratchet.py
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).parent
SABLINE = HERE / "sabline.py"
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_ratchet")              # its own directory

try:
    from jsonschema import Draft4Validator
except ImportError:                        # the SARIF case says it skipped
    Draft4Validator = None  # type: ignore[assignment, misc]  # jsonschema is optional

HAVE_GIT = shutil.which("git") is not None

# For the check ceiling (8.2.1): a program that needs io, and one built to
# stall the type checker - a map literal nested 22 deep, whose check time
# grows with every level (14 take about 27 seconds).
# tests/error_messages/golden.json holds the same program for E613.
HELLO = 'fn main() uses io {\n    print("hi")\n}\n'
STALL = ('fn main() uses io {\n    let m = ' + '{"a": ' * 22 + "1" + "}" * 22
         + '\n    print("built")\n}\n')


class Tree:
    """A scratch directory of .vel files, optionally a git repository."""

    def __init__(self, files: dict[Any, Any], git: bool = False) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="sabline-ratchet-"))
        self.git_repo = git
        if git:
            self.git("init", "-q")
            for key, value in (("user.name", "ratchet"),
                               ("user.email", "ratchet@example.invalid"),
                               ("commit.gpgsign", "false"),
                               ("core.autocrlf", "false")):
                self.git("config", key, value)
        self.write(files)

    def write(self, files: dict[Any, Any]) -> None:
        for name, text in files.items():
            path = self.root / name
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    def sabline(self, *words: Any) -> Any:
        return subprocess.run([sys.executable, str(SABLINE), *words],
                              cwd=str(self.root), capture_output=True,
                              text=True, encoding="utf-8", timeout=600)

    def init(self, *more: Any, root: str = ".") -> Any:
        return self.sabline("capabilities", "init", root, *more)

    def check(self, root: str = ".") -> tuple[Any, ...]:
        """(exit code, the JSON result, or {})"""
        done = self.sabline("capabilities", "check", root, "--json")
        try:
            return done.returncode, json.loads(done.stdout)
        except ValueError:
            return done.returncode, {"_stdout": done.stdout,
                                     "_stderr": done.stderr}

    def review(self, ref: Any) -> Any:
        done = self.sabline("review", "--against", ref, "--json")
        try:
            return json.loads(done.stdout)
        except ValueError:
            return {"_stderr": done.stderr, "_stdout": done.stdout}

    def git(self, *words: Any) -> Any:
        return subprocess.run(["git", *words], cwd=str(self.root),
                              capture_output=True, text=True, timeout=120)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def baseline_path(self, root: str = ".") -> Path:
        return self.root / root / "sabline.capabilities"

    def baseline(self, root: str = ".") -> dict[Any, Any]:
        return cast("dict[Any, Any]", json.loads(
            self.baseline_path(root).read_text(encoding="utf-8")))

    def set_baseline(self, doc: dict[Any, Any], root: str = ".") -> None:
        self.baseline_path(root).write_text(
            sabline.capabilities_text(doc), encoding="utf-8", newline="\n")

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def kinds(result: dict[Any, Any]) -> list[Any]:
    return sorted((f["kind"], f.get("grant") or f.get("effect")
                   or f.get("function")) for f in result.get("findings", []))


def grant_finding(result: dict[Any, Any], grant: str) -> dict[Any, Any]:
    return next((f for f in result.get("findings", [])
                 if f["kind"] == "grant" and f["grant"] == grant), {})


# ---- what a scenario expects, in the corpus's words -------------------------
#
# A widening is reported as sabline-spec 9.6 requires: the grant, count or
# function, the program, and which of W1 to W5 it fails. Nothing else in
# a check's report is part of a case.

def grant(g: str, rules: Any, *programs: Any) -> dict[str, Any]:
    return {"kind": "grant", "grant": g, "rules": list(rules),
            "programs": sorted(programs)}


def count(effect: str, program: str, current: Any, rules: Any) -> dict[str, Any]:
    return {"kind": "count", "effect": effect, "program": program,
            "current": current, "rules": list(rules)}


def gained(program: str, function: str, effects: Any) -> dict[str, Any]:
    return {"kind": "function", "program": program, "function": function,
            "gained": sorted(effects), "rules": ["W5"]}


def widened(*findings: Any) -> dict[str, Any]:
    return {"verdict": "widened", "widenings": list(findings)}


PASS = {"verdict": "pass", "widenings": []}
CANNOT = {"verdict": "cannot-compare"}


def widenings_of(result: dict[Any, Any]) -> list[Any]:
    """A `capabilities check --json` result's findings, as the corpus
    writes them."""
    out = []
    for f in result.get("findings", []):
        if f["kind"] == "grant":
            out.append(grant(f["grant"], f["rules"],
                             *[q["file"] for q in f["programs"]]))
        elif f["kind"] == "count":
            out.append(count(f["effect"], f["file"], f["current"],
                             f["rules"]))
        else:
            out.append(gained(f["file"], f["function"], f["gained"]))
    return out


def same_widenings(a: list[Any], b: list[Any]) -> bool:
    def key(x: Any) -> Any:
        return json.dumps(x, sort_keys=True)
    return sorted(a, key=key) == sorted(b, key=key)


# ---- the programs the cases are built from ---------------------------------

GREETER = '''import "lib/text.vel"

fn main() uses io {
    print(greeting("world"))
}
'''

TEXT_LIB = '''fn greeting(who: Text) -> Text {
    return "hello, " + who
}
'''

PINGER = '''fn ping() -> Int uses net or fail {
    return try fetch_status("https://api.example.com/ping")
}

fn main() uses io, net {
    for i in 0 to {N} {
        check ping() {
            ok code {
                print(to_text(code))
            }
            fail why {
                print(why)
            }
        }
    }
}
'''


def pinger(n: Any, host: str = "api.example.com", note: str = "") -> str:
    return (PINGER.replace("{N}", str(n))
            .replace("api.example.com", host)
            .replace("fn main() uses io, net {",
                     "fn main() uses io, net {" + (
                         f'\n    print("{note}")' if note else "")))


READER = '''fn main() uses io, fs {
    check read_file("{PATH}") {
        ok text {
            print(text)
        }
        fail why {
            print(why)
        }
    }
}
'''


def reader(path: str) -> str:
    return READER.replace("{PATH}", path)


STORE = ('fn save(line: Text) uses fs {\n'
         '    write_file("out/log.txt", line)\n}\n')

UNBOUNDED_READER = (
    'fn load(path: Text) -> Text uses fs or fail {\n'
    '    return try read_file(path)\n}\n\n'
    'fn show(line: Text) -> Text {\n'
    '    return "> " + line\n}\n\n'
    'fn main() uses io, fs {\n'
    '    for a in args() {\n'
    '        check load(a) {\n'
    '            ok text {\n'
    '                print(show(text))\n'
    '            }\n'
    '            fail why {\n'
    '                print(why)\n'
    '            }\n'
    '        }\n'
    '    }\n}\n')

PY_PROG = ('fn root(n: Text) -> Text uses ffi or fail {\n'
           '    let args = [n]\n'
           '    return try py("{MOD}", "sqrt", args)\n}\n\n'
           'fn main() uses io, ffi {\n'
           '    check root("16") {\n'
           '        ok v {\n'
           '            print(v)\n'
           '        }\n'
           '        fail why {\n'
           '            print(why)\n'
           '        }\n'
           '    }\n}\n')

COMPUTED_MODULE = PY_PROG.replace('py("{MOD}"', 'py(lower("MATH")')

RECURSIVE = ('fn poll(n: Int) -> Int uses net {\n'
             '    if n <= 0 {\n'
             '        return 0\n'
             '    }\n'
             '    check fetch_status("https://api.example.com") {\n'
             '        ok s {\n'
             '            return poll(n - 1)\n'
             '        }\n'
             '        fail why {\n'
             '            return 0\n'
             '        }\n'
             '    }\n}\n\n'
             'fn main() uses io, net {\n'
             '    print(to_text(poll(5)))\n}\n')

LOOPING = pinger(3).replace("for i in 0 to 3 {", "for h in args() {")

MULTI = ('import "lib/text.vel"\n'
         'import "lib/store.vel"\n\n'
         'fn helper(n: Int) -> Int {\n'
         '    return n + 1\n}\n\n'
         'fn main() uses io, fs {\n'
         '    let total = helper(1)\n'
         '    let g = greeting("x")\n'
         '    save(g)\n'
         '    for i in 0 to 4 {\n'
         '        print(to_text(file_exists("data/in.csv")))\n'
         '    }\n'
         '    print(to_text(total))\n}\n')

SHUFFLED = ('// the same program, rearranged\n'
            'import "lib/store.vel"\n'
            'import "lib/text.vel"\n\n\n'
            'fn main() uses fs, io {\n'
            '    let g   =   greeting("x")\n'
            '    let sum = helper(1)      // renamed local\n'
            '    for i in 0 to 4 {\n'
            '        print(to_text(file_exists("data/in.csv")))\n'
            '    }\n'
            '    save(g)\n'
            '    print(to_text(sum))\n}\n\n'
            'fn helper(n: Int) -> Int {\n'
            '    return n + 1\n}\n')

COUNTER = ('fn main() uses io, fs {\n'
           '    let i = 0\n'
           '    while i < 4 {\n'
           '        print(to_text(file_exists("data/in.csv")))\n'
           '        i = i + 1\n'
           '    }\n}\n')

HELLO = 'fn main() uses io {\n    print("hi")\n}\n'

MULTI_TREE = {"app.vel": MULTI, "lib/text.vel": TEXT_LIB,
              "lib/store.vel": STORE}

FIXED_TEXT = {"poll.vel": pinger(3).replace(
    'return try fetch_status("https://api.example.com/ping")',
    'let base = "https://api.example.com"\n'
    '    let url = base + "/ping"\n'
    '    return try fetch_status(url)'),
    "read.vel": reader("data/in.csv").replace(
        'check read_file("data/in.csv")',
        'let where = "data/in.csv"\n'
        '    check read_file(where)')}

GRADUAL_STEPS = [
    ("1: a text helper, pure", {
        "lib/tidy.vel": 'fn tidy(t: Text) -> Text {\n'
                        '    return lower(t)\n}\n'}),
    ("2: the greeting uses it", {
        "lib/text.vel": 'import "tidy.vel"\n\n'
                        'fn greeting(who: Text) -> Text {\n'
                        '    return "hello, " + tidy(who)\n}\n'}),
    ("3: a summary of lines, pure", {
        "lib/summary.vel": 'fn summary(lines: List of Text) '
                           '-> Text {\n'
                           '    return to_text(length(lines)) + " lines"\n}\n'}),
    ("4: main prints a summary", {
        "app.vel": 'import "lib/text.vel"\n'
                   'import "lib/summary.vel"\n\n'
                   'fn main() uses io {\n'
                   '    print(greeting("world"))\n'
                   '    print(summary(["a", "b"]))\n}\n'}),
    ("5: an address, as text", {
        "lib/summary.vel": 'fn summary(lines: List of Text) '
                           '-> Text {\n'
                           '    return to_text(length(lines)) + " lines"\n}\n\n'
                           'fn endpoint() -> Text {\n'
                           '    return "https://collector.'
                           'example.net/v1"\n}\n'}),
    ("6: the summary is delivered, three calls down", {
        "lib/deliver.vel": 'fn send(body: Text) -> Text '
                           'uses net or fail {\n'
                           '    return try post("https://'
                           'collector.example.net/v1", body)\n'
                           '}\n\n'
                           'fn deliver(body: Text) -> Text '
                           'uses net {\n'
                           '    check send(body) {\n'
                           '        ok r {\n'
                           '            return r\n'
                           '        }\n'
                           '        fail why {\n'
                           '            return why\n'
                           '        }\n'
                           '    }\n}\n',
        "lib/summary.vel": 'import "deliver.vel"\n\n'
                           'fn summary(lines: List of Text) '
                           '-> Text uses net {\n'
                           '    return deliver(to_text(length(lines)))\n}\n\n'
                           'fn endpoint() -> Text {\n'
                           '    return "https://collector.'
                           'example.net/v1"\n}\n',
        "app.vel": 'import "lib/text.vel"\n'
                   'import "lib/summary.vel"\n\n'
                   'fn main() uses io, net {\n'
                   '    print(greeting("world"))\n'
                   '    print(summary(["a", "b"]))\n}\n'}),
]


def step(description: Any, change: Any = None, expect: Any = PASS, **more: Any) -> dict[Any, Any]:
    return dict(description=description, change=change or {},
                edit=more.get("edit"), rewrite=more.get("rewrite", False),
                delete_baseline=more.get("delete_baseline", False),
                expect=expect)


# ---- SEQUENCES: one baseline, a series of changes, each checked against it --
#
# The baseline is written once, from `tree`; each step changes the tree
# further, and is checked against that same baseline, never against the
# step before. A step may edit the baseline (a person accepting a
# widening), write it again from the tree (`rewrite`), or delete it.

SEQUENCES: list[dict[str, Any]] = [
    dict(id="gradual-widening", spec=["9.1", "9.6"],
         description="six changes, each harmless on its own: the first "
         "five pass, the sixth sends a summary to a host three calls below "
         "main and fails, and the check passes again once the baseline is "
         "written again from the tree",
         tree={"app.vel": GREETER, "lib/text.vel": TEXT_LIB},
         steps=[step(m, files) for m, files in GRADUAL_STEPS[:5]] + [
             step(GRADUAL_STEPS[5][0], GRADUAL_STEPS[5][1], widened(
                 grant("net:collector.example.net", ["W1", "W3"],
                       "app.vel", "lib/deliver.vel", "lib/summary.vel"),
                 gained("app.vel", "main", ["net"]))),
             step("7: the baseline written again from this tree, as a "
                  "change of its own", rewrite=True)]),
    dict(id="merged-widening-keeps-failing", spec=["9.1", "9.6"],
         description="a count widened and merged anyway fails at every "
         "later step until the baseline is edited; seven small steps from "
         "10 are reported against the declared 10; deleting the baseline "
         "makes the check fail, not pass",
         tree={"poll.vel": pinger(10)},
         steps=[step("twenty requests a run", {"poll.vel": pinger(20)},
                     widened(count("net", "poll.vel", 20, ["W2", "W4"]))),
                step("an unrelated change after the widening was merged",
                     {"poll.vel": pinger(20, note="polling")},
                     widened(count("net", "poll.vel", 20, ["W2", "W4"])))]
         + [step(f"{n} requests a run", {"poll.vel": pinger(n)},
                 widened(count("net", "poll.vel", n, ["W2", "W4"])))
            for n in (40, 80, 160, 320, 640, 1000)]
         + [step("the baseline edited to accept 1000 requests a run",
                 edit={"surface": {"counts": {"net": 1000}},
                       "programs": {"poll.vel": {"counts": {"net": 1000}}}}),
            step("sabline.capabilities deleted", delete_baseline=True,
                 expect=CANNOT)]),
]


# ---- CHECKS: a tree, its baseline, one change, the verdict ------------------
#
# The baseline is written from `tree` (then `edit` applied, when there is
# one), or given as `baseline` - {"absent": true} or {"text": ...} for one
# that cannot be read. `change` maps files to their new text, None to
# delete. `root` is the directory checked, when it is not the tree's.

def case(id: Any, description: Any, tree: Any, change: Any = None, expect: Any = PASS, *, edit: Any = None,
         baseline: Any = None, root: str = ".", spec: Any = (), requires: Any = (), known_limit: Any = None) -> dict[str, Any]:
    return dict(id=id, description=description, tree=tree,
                change=change or {}, expect=expect, edit=edit,
                baseline=baseline, root=root, spec=list(spec),
                requires=list(requires), known_limit=known_limit)


PREFIX_EDIT = {"surface": {"grants": ["fs:read:data", "io"]},
               "programs": {"read.vel": {"grants": ["fs:read:data", "io"]}}}


def host_edit(g: str) -> dict[str, Any]:
    return {"surface": {"grants": ["io", g]},
            "programs": {"poll.vel": {"grants": ["io", g]}}}


CHECKS = [
    # ---- widenings, each by another route
    case("import-widens-entry-not-surface", "app.vel now writes through "
         "lib/store.vel: the surface already had that write, app.vel's "
         "entry did not, so it fails under W3 and not W1, and main is named "
         "as the function that gained fs",
         {"app.vel": GREETER, "lib/text.vel": TEXT_LIB,
          "lib/store.vel": STORE},
         {"app.vel": 'import "lib/text.vel"\n'
                     'import "lib/store.vel"\n\n'
                     'fn main() uses io, fs {\n'
                     '    let g = greeting("world")\n'
                     '    save(g)\n'
                     '    print(g)\n}\n'},
         widened(grant("fs:write:out/log.txt", ["W3"], "app.vel"),
                 gained("app.vel", "main", ["fs"])), spec=["9.6 W3", "W5"]),
    case("stdlib-module-brings-net", "the standard library's http.vel "
         "brings net, unscoped because its URL is a parameter",
         {"app.vel": GREETER, "lib/text.vel": TEXT_LIB},
         {"app.vel": 'import "lib/text.vel"\n'
                     'import "http.vel" as http\n\n'
                     'fn main() uses io, net {\n'
                     '    check http.get("https://api.example.com") {\n'
                     '        ok body {\n'
                     '            print(body)\n'
                     '        }\n'
                     '        fail why {\n'
                     '            print(greeting(why))\n'
                     '        }\n'
                     '    }\n}\n'},
         widened(grant("net", ["W1", "W3"], "app.vel"),
                 gained("app.vel", "main", ["net"])),
         spec=["9.3", "9.6"], requires=["stdlib"]),
    case("path-prefix-widened", "a path widened from ./data to ./ fails, "
         "naming fs:read:./",
         {"peek.vel": 'fn main() uses io, fs {\n'
                      '    print(to_text(file_exists("./data")))\n}\n'},
         {"peek.vel": 'fn main() uses io, fs {\n'
                      '    print(to_text(file_exists("./")))\n}\n'},
         widened(grant("fs:read:./", ["W1", "W3"], "peek.vel")),
         spec=["9.5", "9.6"]),
    case("count-raised", "a count raised from 10 to 1000 fails under W2 "
         "and W4", {"poll.vel": pinger(10)}, {"poll.vel": pinger(1000)},
         widened(count("net", "poll.vel", 1000, ["W2", "W4"])),
         spec=["9.4", "9.6"]),
    case("url-star-is-any-host", "a host changed from api.example.com to "
         "*.example.com in a URL: a star in a URL is taken as any host",
         {"poll.vel": pinger(3)}, {"poll.vel": pinger(3,
                                                      host="*.example.com")},
         widened(grant("net", ["W1", "W3"], "poll.vel")), spec=["9.3"]),
    case("function-gains-effect-grants-unchanged", "an effect added to a "
         "function that had none, while the program's grants and counts "
         "stay exactly as they were, is still reported (W5)",
         {"cat.vel": UNBOUNDED_READER},
         {"cat.vel": UNBOUNDED_READER.replace(
             'fn show(line: Text) -> Text {\n'
             '    return "> " + line\n}\n',
             'fn show(line: Text) -> Text uses fs {\n'
             '    if file_exists(line) {\n'
             '        return "> " + line\n'
             '    }\n'
             '    return line\n}\n')},
         widened(gained("cat.vel", "show", ["fs"])), spec=["9.6 W5"]),
    case("url-built-while-running", "a URL built while running makes net "
         "unscoped, and fails against a baseline naming the host",
         {"poll.vel": pinger(3)},
         {"poll.vel": PINGER.replace("{N}", "3").replace(
             '"https://api.example.com/ping"',
             'lower("HTTPS://API.EXAMPLE.COM/PING")')},
         widened(grant("net", ["W1", "W3"], "poll.vel")), spec=["9.3"]),
    case("path-built-while-running", "a path built while running makes "
         "fs:read unscoped, and fails",
         {"read.vel": reader("data/in.csv")},
         {"read.vel": reader("data/in.csv").replace(
             'check read_file("data/in.csv")',
             'check read_file(lower("DATA/IN.CSV"))')},
         widened(grant("fs:read", ["W1", "W3"], "read.vel")), spec=["9.3"]),
    case("new-direction", "a write added to a path that was only read fails, "
         "naming fs:write:data/in.csv, and the second operation raises the "
         "count", {"read.vel": reader("data/in.csv")},
         {"read.vel": reader("data/in.csv").replace(
             "fn main() uses io, fs {",
             "fn main() uses io, fs {\n    write_file(\"data/in.csv\", \"x\")")},
         widened(grant("fs:write:data/in.csv", ["W1", "W3"], "read.vel"),
                 count("fs", "read.vel", 2, ["W2", "W4"])), spec=["9.6"]),
    case("new-module", "a new Python module fails, naming ffi:cmath",
         {"root.vel": PY_PROG.replace("{MOD}", "math")},
         {"root.vel": PY_PROG.replace("{MOD}", "cmath")},
         widened(grant("ffi:cmath", ["W1", "W3"], "root.vel")),
         spec=["9.6"]),
    case("module-built-while-running", "a module named by a value built "
         "while running (ffi_any, 4.0) makes ffi unscoped, and does not pass "
         "a baseline listing ffi:math",
         {"root.vel": PY_PROG.replace("{MOD}", "math")},
         {"root.vel": COMPUTED_MODULE},
         widened(grant("ffi", ["W1", "W3"], "root.vel")),
         spec=["8.2 ffi_any", "9.3"]),
    case("entry-narrower-than-surface", "a recorded program reaching a host "
         "another program already had fails: the surface is unchanged, its "
         "own entry is not (W3)",
         {"a.vel": pinger(3), "b.vel": pinger(3, host="cdn.example.org")},
         {"b.vel": pinger(3, host="api.example.com")},
         widened(grant("net:api.example.com", ["W3"], "b.vel")),
         spec=["9.6 W3"]),
    case("loop-without-fixed-turns", "a loop with no fixed number of turns "
         "has no bound, and fails against a count of 3",
         {"poll.vel": pinger(3)}, {"poll.vel": LOOPING},
         widened(count("net", "poll.vel", None, ["W2", "W4"])),
         spec=["9.4"]),
    case("recursion-has-no-bound", "recursion has no bound either",
         {"poll.vel": pinger(3)}, {"poll.vel": RECURSIVE},
         widened(count("net", "poll.vel", None, ["W2", "W4"])),
         spec=["9.4"]),
    case("main-imported-from-outside", "a program whose main is imported "
         "from outside the checked directory needs what that main does, and "
         "fails when that widens",
         {"repo/run.vel": 'import "../ext/app.vel"\n', "ext/app.vel": HELLO},
         {"ext/app.vel": 'fn main() uses io, net {\n'
                         '    check fetch("https://x.example.org") {\n'
                         '        ok b {\n'
                         '            print(b)\n'
                         '        }\n'
                         '        fail w {\n'
                         '            print(w)\n'
                         '        }\n'
                         '    }\n}\n'},
         widened(grant("net:x.example.org", ["W1", "W3"], "run.vel")),
         root="repo", spec=["9.3"]),
    case("hidden-directory", "a program in a hidden directory is part of "
         "the repository, and its widening fails",
         {".ci/deploy.vel": HELLO}, {".ci/deploy.vel": pinger(1)},
         widened(grant("net:api.example.com", ["W1", "W3"],
                       ".ci/deploy.vel"),
                 gained(".ci/deploy.vel", "main", ["net"])), spec=["9.3"]),
    case("backslash-climbs-out", "a path that climbs out with backslashes "
         "is not taken as inside a prefix: on Windows data/..\\..\\x leaves "
         "data", {"read.vel": reader("data/in.csv")},
         {"read.vel": reader("data/..\\\\..\\\\secret.txt")},
         widened(grant("fs:read:data/..\\..\\secret.txt", ["W1", "W3"],
                       "read.vel")), edit=PREFIX_EDIT, spec=["9.5"]),
    case("new-effect", "an effect the surface has no grant of is a new "
         "effect", {"app.vel": HELLO},
         {"app.vel": 'fn main() uses io, clock {\n'
                     '    print(to_text(now()))\n}\n'},
         widened(grant("clock", ["W1", "W3"], "app.vel"),
                 gained("app.vel", "main", ["clock"])), spec=["9.6"]),
    case("new-program-outside-surface", "a program the baseline does not "
         "record is held to the surface alone, and fails W1 when it reaches "
         "a new host", {"poll.vel": pinger(3)},
         {"other.vel": pinger(3, host="cdn.example.org")},
         widened(grant("net:cdn.example.org", ["W1"], "other.vel")),
         spec=["9.6 W1"]),
    case("fs-declared-without-operation", "a program that declares fs and "
         "names no file needs plain fs, which a baseline of paths does not "
         "cover", {"read.vel": reader("data/in.csv")},
         {"read.vel": 'fn main() uses io, fs {\n    print("no file")\n}\n'},
         widened(grant("fs", ["W1", "W3"], "read.vel")), spec=["9.3"]),
    case("rules-named", "each widening names the rules it fails: a new host "
         "is outside the surface (W1) and the program's entry (W3)",
         {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3, host="evil.example.net")},
         widened(grant("net:evil.example.net", ["W1", "W3"], "poll.vel")),
         spec=["9.6"]),

    # ---- changes that do not widen must pass
    case("literal-into-variable", "a literal URL or path moved into a "
         "variable bound once is still a fixed host and path",
         {"poll.vel": pinger(3), "read.vel": reader("data/in.csv")},
         FIXED_TEXT, spec=["9.3"]),
    case("loop-over-list-variable", "a loop over a list held in a variable "
         "keeps its bound of 3", {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3).replace(
             "for i in 0 to 3 {", 'let hosts = ["a", "b", "c"]\n'
                                  '    for h in hosts {')}, spec=["9.4"]),
    case("narrowing", "a lower count, an effect dropped and a program "
         "removed are narrowing, which never fails",
         {"poll.vel": pinger(1000), "read.vel": reader("data/in.csv"),
          "b.vel": pinger(3, host="cdn.example.org")},
         {"poll.vel": pinger(10),
          "read.vel": 'fn main() uses io {\n    print("no file")\n}\n',
          "b.vel": None}, spec=["9.6"]),
    case("reorder-and-reformat", "reordering functions, imports, uses "
         "clauses and statements, renaming locals and reformatting",
         MULTI_TREE, {"app.vel": SHUFFLED}, spec=["9.6"]),
    case("file-without-effects", "a file added with no effects",
         {"poll.vel": pinger(3)},
         {"lib/math.vel": 'fn twice(n: Int) -> Int {\n'
                          '    return n * 2\n}\n'}, spec=["9.6"]),
    case("new-program-inside-surface", "a new program that stays inside "
         "the declared surface - the same host, no more requests a run",
         {"poll.vel": pinger(3)}, {"other.vel": pinger(2)}, spec=["9.6"]),
    case("statements-before-loop", "statements added between a counter's "
         "start and its loop keep the bound of 4", {"count.vel": COUNTER},
         {"count.vel": COUNTER.replace(
             "    let i = 0\n",
             "    let i = 0\n"
             "    let noise = 2 * 3\n"
             '    print("starting")\n'
             "    print(to_text(noise))\n")}, spec=["9.4"]),
    case("function-renamed", "a function renamed, its effects unchanged",
         MULTI_TREE, {"app.vel": MULTI.replace("helper", "plus_one")},
         spec=["9.6"]),
    case("function-moved", "a function moved to another file", MULTI_TREE,
         {"app.vel": MULTI.replace(
             "fn helper(n: Int) -> Int {\n    return n + 1\n}\n\n", "")
          .replace('import "lib/text.vel"\n',
                   'import "lib/text.vel"\nimport "lib/helper.vel"\n'),
          "lib/helper.vel": 'fn helper(n: Int) -> Int {\n'
                            '    return n + 1\n}\n'}, spec=["9.6"]),
    case("stops-compiling", "a program that stops compiling adds nothing "
         "until it compiles again", MULTI_TREE,
         {"app.vel": MULTI.replace("fn main() uses io, fs {",
                                   "fn main() uses io {")}, spec=["9.6"]),
    case("another-spelling-of-a-path", "./data/in.csv is data/in.csv",
         {"read.vel": reader("data/in.csv")},
         {"read.vel": reader("./data/in.csv")}, spec=["9.5"]),
    case("port-under-portless-grant", "a URL writing a port, where the "
         "baseline holds the host without one",
         {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3, host="api.example.com:443")},
         spec=["9.5"]),

    # ---- the declared surface is the operator's to widen
    case("declared-prefix-covers-under", "a hand-written prefix covers any "
         "path under it", {"read.vel": reader("data/sub/x.csv")},
         {"read.vel": reader("data/other/y.csv")}, edit=PREFIX_EDIT,
         spec=["9.5"]),
    case("declared-prefix-not-outside", "...and nothing outside it",
         {"read.vel": reader("data/sub/x.csv")},
         {"read.vel": reader("config.csv")},
         widened(grant("fs:read:config.csv", ["W1", "W3"], "read.vel")),
         edit=PREFIX_EDIT, spec=["9.5"]),
    case("declared-wildcard-covers-label", "a declared wildcard covers one "
         "label under it", {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3, host="cdn.example.com")},
         edit=host_edit("net:*.example.com"), spec=["9.5"]),
    case("declared-wildcard-not-parent", "...not the domain itself",
         {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3, host="example.com")},
         widened(grant("net:example.com", ["W1", "W3"], "poll.vel")),
         edit=host_edit("net:*.example.com"), spec=["9.5"]),
    case("declared-port-not-portless", "a grant with a port does not cover "
         "a URL that writes none", {"poll.vel": pinger(3)}, {},
         widened(grant("net:api.example.com", ["W1", "W3"], "poll.vel")),
         edit=host_edit("net:api.example.com:443"), spec=["9.5"]),
    case("declared-port-covers-port", "...and covers one that writes that "
         "port", {"poll.vel": pinger(3)},
         {"poll.vel": pinger(3, host="api.example.com:443")},
         edit=host_edit("net:api.example.com:443"), spec=["9.5"]),

    # ---- versions, and baselines that cannot be read
    case("older-baseline-version", "a baseline from an older producer is "
         "compared, not refused", {"poll.vel": pinger(3)},
         edit={"sabline_version": "1.0.0"}, spec=["9.2", "9.6"]),
    case("newer-baseline-version", "...and one from another version the "
         "same way", {"poll.vel": pinger(3)},
         edit={"sabline_version": "99.0.0"}, spec=["9.2"]),
    case("version-never-hides-widening", "...but another version never "
         "hides a widening", {"poll.vel": pinger(3)},
         {"poll.vel": pinger(4)},
         widened(count("net", "poll.vel", 4, ["W2", "W4"])),
         edit={"sabline_version": "1.0.0"}, spec=["9.6"]),
    case("baseline-deleted", "with sabline.capabilities deleted the check "
         "fails rather than passing: deleting the file does not turn the "
         "check off", {"poll.vel": pinger(3)}, expect=CANNOT,
         baseline={"absent": True}, spec=["9.6"]),
    case("baseline-provisional-v0", "a sabline.capabilities/0 baseline "
         "cannot be compared", {"poll.vel": pinger(3)}, expect=CANNOT,
         baseline={"text": '{"schema": "sabline.capabilities/0", '
                           '"programs": []}\n'}, spec=["9", "9.6"]),
    case("baseline-not-json", "a baseline that is not JSON cannot be "
         "compared", {"poll.vel": pinger(3)}, expect=CANNOT,
         baseline={"text": "{ not json\n"}, spec=["9.6"]),
    case("baseline-count-in-grant", "a baseline holding a count in a grant "
         "cannot be compared", {"poll.vel": pinger(3)}, expect=CANNOT,
         baseline={"text": json.dumps(
             {"schema": "sabline.capabilities/1", "sabline_version": "4.1.0",
              "date": "2026-09-11",
              "surface": {"grants": ["net:h.example@3"], "counts": {}},
              "programs": []}) + "\n"}, spec=["9.2", "9.6"]),

    # ---- known limits (CHANGELOG 4.0, "What the ratchet cannot do"),
    # each recorded with what the check does today, not what a perfect
    # one would do, so another implementation matches it rather than
    # guessing
    case("known-limit-rename-while-gaining", "a pure helper renamed in the "
         "same change that gives it an effect its program already had "
         "passes: the renamed function is new to the baseline",
         {"app.vel": 'fn tidy(t: Text) -> Text {\n'
                     '    return lower(t)\n}\n\n'
                     'fn main() uses io, fs {\n'
                     '    print(tidy("A"))\n'
                     '    print(to_text(file_exists("data/x")))\n}\n'},
         {"app.vel": 'fn tidy2(t: Text) -> Text uses fs {\n'
                     '    if file_exists("data/x") {\n'
                     '        return lower(t)\n'
                     '    }\n'
                     '    return t\n}\n\n'
                     'fn main() uses io, fs {\n'
                     '    print(tidy2("A"))\n}\n'},
         PASS, spec=["9.8"],
         known_limit="A widening that passes. The declared surface did not "
         "widen - the program's grants and count are what they were - but "
         "a function that declared nothing now declares fs, and W5 does "
         "not see it: a function is known by its file and name, so tidy2 "
         "is a new function, held to its program's entry and the surface, "
         "not to what tidy declared."),
    case("known-limit-granted-module-behaviour", "a program that newly "
         "calls os.system through a module the baseline already grants "
         "passes: the baseline records modules, not what they do",
         {"cwd.vel": 'fn cwd() -> Text uses ffi or fail {\n'
                     '    let none: List of Text = []\n'
                     '    return try py("os", "getcwd", none)\n}\n\n'
                     'fn main() uses io, ffi {\n'
                     '    check cwd() {\n'
                     '        ok d {\n'
                     '            print(d)\n'
                     '        }\n'
                     '        fail w {\n'
                     '            print(w)\n'
                     '        }\n'
                     '    }\n}\n'},
         {"cwd.vel": 'fn cwd() -> Text uses ffi or fail {\n'
                     '    let none: List of Text = []\n'
                     '    return try py("os", "getcwd", none)\n}\n\n'
                     'fn main() uses io, ffi {\n'
                     '    check py_int("os", "system", ["echo hi"]) {\n'
                     '        ok n {\n'
                     '            print(to_text(n))\n'
                     '        }\n'
                     '        fail w {\n'
                     '            print(w)\n'
                     '        }\n'
                     '    }\n'
                     '    check cwd() {\n'
                     '        ok d {\n'
                     '            print(d)\n'
                     '        }\n'
                     '        fail w {\n'
                     '            print(w)\n'
                     '        }\n'
                     '    }\n}\n'},
         PASS, spec=["9.8", "7"],
         known_limit="A widening that passes. What a granted module does "
         "is outside the program's text: ffi:os in a baseline is the "
         "operating system, and a new call into it is inside the surface."),
    case("known-limit-bound-behind-call", "a loop bound moved behind a "
         "function call loses its bound and is reported as unbounded",
         {"scan.vel": 'fn main() uses io, fs {\n'
                      '    for i in 0 to 3 {\n'
                      '        print(to_text(file_exists("data/x")))\n'
                      '    }\n}\n'},
         {"scan.vel": 'fn limit() -> Int {\n'
                      '    return 3\n}\n\n'
                      'fn main() uses io, fs {\n'
                      '    for i in 0 to limit() {\n'
                      '        print(to_text(file_exists("data/x")))\n'
                      '    }\n}\n'},
         widened(count("fs", "scan.vel", None, ["W2", "W4"])), spec=["9.4"],
         known_limit="A change that does not widen, reported as one. The "
         "loop still turns three times, but the bound comes from fixed "
         "rules that read a limit only from literals and variables the "
         "text fixes, not from what a function returns."),
    case("known-limit-path-as-parameter", "a path passed to a helper as a "
         "parameter is taken as unscoped, even when every caller passes a "
         "literal", {"read.vel": reader("data/in.csv")},
         {"read.vel": 'fn load(path: Text) -> Text uses fs or fail {\n'
                      '    return try read_file(path)\n}\n\n'
                      'fn main() uses io, fs {\n'
                      '    check load("data/in.csv") {\n'
                      '        ok text {\n'
                      '            print(text)\n'
                      '        }\n'
                      '        fail why {\n'
                      '            print(why)\n'
                      '        }\n'
                      '    }\n}\n'},
         widened(grant("fs:read", ["W1", "W3"], "read.vel")), spec=["9.3"],
         known_limit="A change that does not widen, reported as one. The "
         "program reads data/in.csv as before, but a parameter is not "
         "fixed text (sabline-spec 9.3 step 4), so the grant it needs is "
         "fs:read, any path."),
    case("known-limit-backslash-path", "a path written with a backslash is "
         "covered only by the same text, so data\\in.csv is outside a "
         "recorded prefix data even where \\ separates directories",
         {"read.vel": reader("data/in.csv")},
         {"read.vel": reader("data\\\\in.csv")},
         widened(grant("fs:read:data\\in.csv", ["W1", "W3"], "read.vel")),
         edit=PREFIX_EDIT, spec=["9.5", "Q7"],
         known_limit="A change that does not widen, reported as one, on "
         "Windows. A path holding a backslash is compared whole, because "
         "on Windows data/..\\..\\x leaves data; the price is that "
         "data\\in.csv, which is inside data there, is reported too "
         "(sabline-spec open question Q7)."),
]


# ---- DERIVE: the baseline a tree needs (sabline-spec 9.3) --------------------
#
# What a writer must record for `tree`: the surface and every program's
# entry. sabline_version and date are the writer's own.

def entry(file: Any, grants: Any, counts: Any, functions: Any) -> dict[str, Any]:
    return {"file": file, "grants": list(grants), "counts": dict(counts),
            "functions": dict(sorted(functions.items()))}


def broken(file: Any) -> dict[str, Any]:
    return {"file": file, "compiles": False}


def baseline(grants: Any, counts: Any, *programs: Any) -> dict[str, Any]:
    return {"surface": {"grants": list(grants), "counts": dict(counts)},
            "programs": sorted(programs, key=lambda p: p["file"])}


DERIVE: list[dict[str, Any]] = [
    dict(id="library-file-is-a-program", description="every .vel file is "
         "a program; one with no main and no effects needs nothing",
         tree={"app.vel": GREETER, "lib/text.vel": TEXT_LIB},
         expect=baseline(["io"], {},
                         entry("app.vel", ["io"], {}, {"main": ["io"]}),
                         entry("lib/text.vel", [], {},
                               {"greeting": []})), spec=["9.3"]),
    dict(id="host-and-count", description="a literal host, and a loop whose "
         "turns the text fixes: at most 10 requests a run",
         tree={"poll.vel": pinger(10)},
         expect=baseline(["io", "net:api.example.com"], {"net": 10},
                         entry("poll.vel", ["io", "net:api.example.com"],
                               {"net": 10},
                               {"main": ["io", "net"], "ping": ["net"]})),
         spec=["9.3", "9.4"]),
    dict(id="imports-and-counts", description="fs operations through an "
         "import and a loop add up; the imported library files are programs "
         "of their own", tree=MULTI_TREE,
         expect=baseline(["fs:read:data/in.csv", "fs:write:out/log.txt",
                          "io"], {"fs": 5},
                         entry("app.vel", ["fs:read:data/in.csv",
                                           "fs:write:out/log.txt", "io"],
                               {"fs": 5}, {"helper": [],
                                           "main": ["fs", "io"]}),
                         entry("lib/store.vel", ["fs:write:out/log.txt"],
                               {"fs": 1}, {"save": ["fs"]}),
                         entry("lib/text.vel", [], {}, {"greeting": []})),
         spec=["9.3", "9.4"]),
    dict(id="rearranged-is-identical", description="the same program "
         "rearranged and reformatted needs exactly the same",
         tree={"app.vel": SHUFFLED, "lib/text.vel": TEXT_LIB,
               "lib/store.vel": STORE},
         expect=baseline(["fs:read:data/in.csv", "fs:write:out/log.txt",
                          "io"], {"fs": 5},
                         entry("app.vel", ["fs:read:data/in.csv",
                                           "fs:write:out/log.txt", "io"],
                               {"fs": 5}, {"helper": [],
                                           "main": ["fs", "io"]}),
                         entry("lib/store.vel", ["fs:write:out/log.txt"],
                               {"fs": 1}, {"save": ["fs"]}),
                         entry("lib/text.vel", [], {}, {"greeting": []})),
         spec=["9.3"]),
    dict(id="fixed-text", description="a literal bound once by let, and + "
         "of two fixed texts, are fixed text",
         tree=FIXED_TEXT,
         expect=baseline(["fs:read:data/in.csv", "io",
                          "net:api.example.com"], {"fs": 1, "net": 3},
                         entry("poll.vel", ["io", "net:api.example.com"],
                               {"net": 3},
                               {"main": ["io", "net"], "ping": ["net"]}),
                         entry("read.vel", ["fs:read:data/in.csv", "io"],
                               {"fs": 1}, {"main": ["fs", "io"]})),
         spec=["9.3"]),
    dict(id="parameter-is-not-fixed", description="a path that arrives as a "
         "parameter is built while running: the direction, any path",
         tree={"cat.vel": UNBOUNDED_READER},
         expect=baseline(["fs:read", "io"], {"fs": None},
                         entry("cat.vel", ["fs:read", "io"], {"fs": None},
                               {"load": ["fs"], "main": ["fs", "io"],
                                "show": []})), spec=["9.3", "9.4"]),
    dict(id="does-not-compile", description="a file that does not compile "
         "is recorded as such and adds nothing to the surface",
         tree={"ok.vel": HELLO,
               "bad.vel": 'fn main() {\n    print("x")\n}\n'},
         expect=baseline(["io"], {}, broken("bad.vel"),
                         entry("ok.vel", ["io"], {}, {"main": ["io"]})),
         spec=["9.2", "9.3"]),
    dict(id="imported-main", description="a file that imports its main "
         "needs what that main does, and records no functions of its own",
         tree={"repo/run.vel": 'import "../ext/app.vel"\n',
               "ext/app.vel": HELLO}, root="repo",
         expect=baseline(["io"], {}, entry("run.vel", ["io"], {}, {})),
         spec=["9.3"]),
    dict(id="surface-union-and-no-bound", description="the surface is the "
         "union of the programs' grants, and a program with no bound makes "
         "the surface's count null",
         tree={"a.vel": pinger(3), "b.vel": LOOPING.replace(
             "api.example.com", "cdn.example.org")},
         expect=baseline(["io", "net:api.example.com", "net:cdn.example.org"],
                         {"net": None},
                         entry("a.vel", ["io", "net:api.example.com"],
                               {"net": 3},
                               {"main": ["io", "net"], "ping": ["net"]}),
                         entry("b.vel", ["io", "net:cdn.example.org"],
                               {"net": None},
                               {"main": ["io", "net"], "ping": ["net"]})),
         spec=["9.3", "9.4"]),
    dict(id="grants-reduced", description="a path under another named path "
         "is dropped, and of two spellings of one path the first in "
         "code-point order is kept",
         tree={"read.vel": 'fn main() uses io, fs {\n'
                           '    print(to_text(file_exists("data")))\n'
                           '    print(to_text(file_exists("./data")))\n'
                           '    print(to_text(file_exists("data/x.csv")))\n'
                           '}\n'},
         expect=baseline(["fs:read:./data", "io"], {"fs": 3},
                         entry("read.vel", ["fs:read:./data", "io"],
                               {"fs": 3}, {"main": ["fs", "io"]})),
         spec=["9.2", "9.3"]),
    dict(id="unwritable-path-is-unscoped", description="a path holding a "
         "comma cannot be a baseline grant, so the direction is recorded "
         "unscoped", tree={"read.vel": reader("a,b.csv")},
         expect=baseline(["fs:read", "io"], {"fs": 1},
                         entry("read.vel", ["fs:read", "io"], {"fs": 1},
                               {"main": ["fs", "io"]})), spec=["9.3"]),
    dict(id="declared-fs-without-operation", description="fs declared and "
         "no file named is plain fs; the count is 0",
         tree={"read.vel": 'fn main() uses io, fs {\n'
                           '    print("no file")\n}\n'},
         expect=baseline(["fs", "io"], {"fs": 0},
                         entry("read.vel", ["fs", "io"], {"fs": 0},
                               {"main": ["fs", "io"]})), spec=["9.3"]),
    dict(id="dotted-module", description="a module named with a dot is "
         "recorded up to its first dot",
         tree={"base.vel": 'fn main() uses io, ffi {\n'
                           '    check py("os.path", "basename", ["a/b"]) {\n'
                           '        ok b {\n'
                           '            print(b)\n'
                           '        }\n'
                           '        fail w {\n'
                           '            print(w)\n'
                           '        }\n'
                           '    }\n}\n'},
         expect=baseline(["ffi:os", "io"], {},
                         entry("base.vel", ["ffi:os", "io"], {},
                               {"main": ["ffi", "io"]})), spec=["9.3"]),
    dict(id="counter-bound", description="a counter started by let and "
         "moved one step toward a fixed limit bounds its loop",
         tree={"count.vel": COUNTER},
         expect=baseline(["fs:read:data/in.csv", "io"], {"fs": 4},
                         entry("count.vel", ["fs:read:data/in.csv", "io"],
                               {"fs": 4}, {"main": ["fs", "io"]})),
         spec=["9.4"]),
]


# ---- WRITE_GUARD: a writer does not replace a baseline unasked --------------

WRITE_GUARD: list[dict[str, Any]] = [
    dict(id="writer-refuses-to-widen-unasked", description="asked to write "
         "the baseline again where one exists and the tree now needs more, "
         "without being told in so many words to replace it, the writer "
         "refuses and leaves the file as it was",
         tree={"poll.vel": pinger(3)}, change={"poll.vel": pinger(4)},
         spec=["9.6"]),
]


# ---- the rules underneath (sabline-spec 9.4, 9.5, 9.2 rule 5) ----------------

COVERING = [
    ("fs:read:data", "fs:read:data/x.csv", True),
    ("fs:read:./data/", "fs:read:data", True),
    ("fs:read:data", "fs:read:database", False),
    ("fs:read:data", "fs:read:data/../secret", False),
    ("fs:read:.", "fs:read:../x", False),
    ("fs:read:.", "fs:read:x/y", True),
    ("fs:read:.", "fs:read:/etc", False),
    ("fs:read:/", "fs:read:/etc/passwd", True),
    ("fs:read:a/../b", "fs:read:b/c", True),
    ("fs:read:data", "fs:read:data\\x", False),
    ("fs:read:data\\x", "fs:read:data\\x", True),
    ("fs:read", "fs:read:/etc/passwd", True),
    ("fs:read", "fs:write:x", False),
    ("fs:read:data", "fs:write:data", False),
    ("fs", "fs:write:x", True),
    ("fs:write:out", "fs:write", False),
    ("net", "net:a.example.com", True),
    ("net:a.example.com", "net", False),
    ("net:*.example.com", "net:a.example.com", True),
    ("net:*.example.com", "net:a.b.example.com", False),
    ("net:*.example.com", "net:*.b.example.com", False),
    ("net:*.example.com", "net:example.com", False),
    ("net:api.example.com", "net:*.example.com", False),
    ("net:h.example:443", "net:h.example", False),
    ("net:h.example", "net:h.example:443", True),
    ("net:[::1]", "net:[::1]:8080", True),
    ("net:[::1]:8080", "net:[::1]", False),
    ("ffi", "ffi:os", True),
    ("ffi:math", "ffi:os", False),
    ("ffi:math", "ffi", False),
    ("io", "io", True),
    ("env", "io", False),
]

REDUCE = [
    (["fs:read:./data/", "fs:read:data", "fs:read:data/x", "io", "io"],
     ["fs:read:./data/", "io"]),
    (["net:*.example.com", "net:a.example.com", "net:b.example.org"],
     ["net:*.example.com", "net:b.example.org"]),
    (["ffi:math", "ffi", "fs:write:out", "fs"], ["ffi", "fs"]),
]

BOUNDS = [
    ("nested-loops-multiply", "nested loops multiply",
     'fn main() uses fs {\n'
     '    for i in 0 to 3 {\n'
     '        for j in 1 to 5 {\n'
     '            let e = file_exists("x")\n'
     '        }\n    }\n}\n', {"fs": 12, "net": 0}),
    ("larger-branch", "the larger branch of an if counts",
     'fn main() uses fs {\n'
     '    if file_exists("a") {\n'
     '        let x = file_exists("b")\n'
     '        let y = file_exists("c")\n'
     '    } else {\n'
     '        let z = file_exists("d")\n'
     '    }\n}\n', {"fs": 3, "net": 0}),
    ("list-literal", "a loop over a list literal turns once per item",
     'fn main() uses fs {\n'
     '    for p in ["a", "b", "c"] {\n'
     '        let e = file_exists(p)\n'
     '    }\n}\n', {"fs": 3, "net": 0}),
    ("counter-from-let", "a hand-written counter, started by a let",
     'fn main() uses fs {\n'
     '    let i = 2\n'
     '    while i <= 6 {\n'
     '        let e = file_exists("x")\n'
     '        i = i + 1\n'
     '    }\n}\n', {"fs": 5, "net": 0}),
    ("called-twice", "a function called twice counts twice",
     'fn one() -> Bool uses fs {\n'
     '    return file_exists("x")\n}\n\n'
     'fn main() uses fs {\n'
     '    let a = one()\n'
     '    let b = one()\n}\n', {"fs": 2, "net": 0}),
    ("counter-changed-by-loop", "a counter that a loop body changes is not a "
     "fixed start",
     'fn main() uses fs {\n'
     '    let i = 0\n'
     '    while i < 3 {\n'
     '        i = i + 1\n'
     '    }\n'
     '    while i < 5 {\n'
     '        let e = file_exists("x")\n'
     '        i = i + 1\n'
     '    }\n}\n', {"fs": None, "net": 0}),
]


def apply_edit(doc: dict[Any, Any], edit: dict[Any, Any]) -> dict[Any, Any]:
    """A baseline as a person edits it: each key of `surface` and of a
    program's entry replaced, and sabline_version when given."""
    doc = copy.deepcopy(doc)
    if "sabline_version" in edit:
        doc["sabline_version"] = edit["sabline_version"]
    doc["surface"].update(edit.get("surface", {}))
    for file, fields in edit.get("programs", {}).items():
        next(p for p in doc["programs"] if p["file"] == file).update(fields)
    return doc


def verdict(code: int) -> str:
    return {0: "pass", 1: "widened", 2: "cannot-compare"}.get(code,
                                                             f"exit {code}")


def main() -> int:
    passed = failed = 0
    trees = []

    def ok(label: Any, condition: Any, detail: object = "") -> None:
        nonlocal passed, failed
        if condition:
            print(f"  ok       {label}")
            passed += 1
        else:
            print(f"  BROKEN   {label}")
            if detail:
                print(f"           {str(detail)[:600]}")
            failed += 1

    def skip(label: Any, why: Any) -> None:
        print(f"  skip     {label} ({why})")

    def tree(files: Any, git: bool = False) -> Any:
        t = Tree(files, git)
        trees.append(t)
        return t

    def meets(expect: dict[Any, Any], code: int, result: dict[Any, Any]) -> tuple[Any, ...]:
        """(does the check's answer meet the expectation, why not)"""
        if verdict(code) != expect["verdict"]:
            return False, (f"{verdict(code)}, expected {expect['verdict']}: "
                           f"{widenings_of(result) or result}")
        if expect["verdict"] == "cannot-compare":
            return True, ""
        got = widenings_of(result)
        if not same_widenings(got, expect["widenings"]):
            return False, f"widenings {got}"
        return True, ""

    runs: dict[str, tuple[Any, ...]] = {}  # case id -> (tree, exit code, result)
    reviews = {}          # sequence id -> [risk of each step's review]
    try:
        # ------------------------------------------------------------------
        print("sequences: one baseline, many changes, each checked against it")
        print("-" * 62)
        for s in SEQUENCES:
            t = tree(s["tree"], git=HAVE_GIT)
            t.init()
            if HAVE_GIT:
                t.commit("the tree, and its declared surface")
            risks, results = [], []
            for n, st in enumerate(s["steps"], 1):
                t.write(st["change"])
                if st["edit"]:
                    t.set_baseline(apply_edit(t.baseline(), st["edit"]))
                if st["rewrite"]:
                    t.init("--force")
                if st["delete_baseline"]:
                    t.baseline_path().unlink()
                if HAVE_GIT:
                    t.commit(st["description"])
                code, r = t.check()
                results.append((code, r))
                good, why = meets(st["expect"], code, r)
                ok(f"{s['id']} {n}: {st['description']}", good, why)
                if HAVE_GIT:
                    risks.append(t.review("HEAD~1"))
            runs[s["id"]] = (t, results)
            reviews[s["id"]] = risks

        # ------------------------------------------------------------------
        print()
        print("changes, each checked against the baseline its tree declared")
        print("-" * 62)
        for c in CHECKS:
            t = tree(c["tree"])
            root = c["root"]
            if c["baseline"] is None:
                t.init(root=root)
                if c["edit"]:
                    t.set_baseline(apply_edit(t.baseline(root), c["edit"]),
                                   root)
            elif "text" in c["baseline"]:
                t.baseline_path(root).write_text(c["baseline"]["text"],
                                                 encoding="utf-8")
            t.write(c["change"])
            code, r = t.check(root)
            runs[c["id"]] = (t, code, r)
            good, why = meets(c["expect"], code, r)
            ok(("known limit, recorded as it is: " if c["known_limit"]
                else "") + c["description"], good, why)

        # ------------------------------------------------------------------
        print()
        print("what a writer records for a tree")
        print("-" * 62)
        for d in DERIVE:
            t = tree(d["tree"])
            root = d.get("root", ".")
            done = t.init(root=root)
            doc = t.baseline(root) if done.returncode == 0 else {}
            got: dict[str, Any] | str = {"surface": doc.get("surface"),
                                         "programs": doc.get("programs")}
            ok(f"derive: {d['description']}", got == d["expect"],
               json.dumps(got))
            runs[d["id"]] = (t, doc)
        for w in WRITE_GUARD:
            t = tree(w["tree"])
            first = t.init()
            text = t.baseline_path().read_text(encoding="utf-8")
            t.write(w["change"])
            again = t.init()
            ok(f"write: {w['description']}", first.returncode == 0
               and again.returncode != 0
               and t.baseline_path().read_text(encoding="utf-8") == text,
               again.stderr)
            runs[w["id"]] = (t, again)

        # ------------------------------------------------------------------
        print()
        print("the rules underneath")
        print("-" * 62)
        gp = sabline._grant_parts
        wrong: list[tuple[Any, ...]] = [(b, c, want) for b, c, want in COVERING
                                        if sabline._covers(gp(b), gp(c)) != want]
        ok(f"{len(COVERING)} covering cases: paths by whole components, "
           f"backslashes whole, wildcards one label deep, ports, modules",
           not wrong, wrong)
        wrong = [(given, want, sabline._reduce_grants(given))
                 for given, want in REDUCE
                 if sabline._reduce_grants(given) != want]
        ok(f"{len(REDUCE)} reduced grant lists keep one spelling of a path "
           f"and drop what another grant covers", not wrong, wrong)

        def bound(source: Any) -> dict[Any, Any]:
            funcs, _ = sabline.load_program("_bound.vel", source)
            b, _ = sabline._operation_bounds(funcs)
            return {k: sabline._as_count(v) for k, v in b["main"].items()}

        wrong = []
        for _, label, source, want in BOUNDS:
            try:
                got = bound(source)
            except sabline.SablineError as e:
                got = f"does not compile: {e.message}"
            if got != want:
                wrong.append((label, got, want))
        ok(f"{len(BOUNDS)} bounds on the operations of a run: nested "
           f"loops, branches, list literals, counters, calls - and no "
           f"bound where the text does not fix one", not wrong, wrong)

        # ------------------------------------------------------------------
        print()
        print("what this implementation says beyond the verdict")
        print("-" * 62)
        t, results = runs["gradual-widening"]
        r6 = results[5][1]
        net = grant_finding(r6, "net:collector.example.net")
        ok("the sixth change is named as a new effect, outside the surface",
           net.get("new_effect") is True
           and net.get("outside_surface") is True, net)
        prog: dict[str, Any] = next((q for q in net.get("programs", [])
                                     if q["file"] == "app.vel"), {})
        origin = (prog.get("origins") or [{}])[0]
        ok("...with the file, function and line that introduced it, and "
           "the three calls from main that reach it",
           origin.get("file") == "lib/deliver.vel"
           and origin.get("function") == "send"
           and origin.get("line") == 2 and origin.get("call") == "post"
           and prog.get("reached_from")
           == ["main", "summary", "deliver", "send"], prog)
        if not HAVE_GIT:
            skip("the reviews of each change against the one before",
                 "git is not installed")
        else:
            risks = [rv.get("risk") for rv in reviews["gradual-widening"]]
            ok("a review of each change against the one before it calls "
               "1 to 5 low and 6 high", risks[:6] == ["low"] * 5 + ["high"],
               risks)
            rv = reviews["merged-widening-keeps-failing"]
            ok("a review against the previous commit calls the widening "
               "high, and one commit later sees nothing",
               rv[0].get("risk") == "high" and rv[1].get("risk") == "low"
               and not rv[1].get("surface", {}).get("widened"), rv[1])
            step_: dict[str, Any] = next((f for f in rv[7].get("surface", {})
                                          .get("widened", []) if f["kind"] == "count"), {})
            ok("...and of seven small steps shows only the last, 640 to "
               "1000, where the check reports 1000 against the declared 10",
               step_.get("current") == 1000
               and step_.get("surface_allows") == 640, step_)
            accepted = rv[8]
            ok("accepting it is an edit to the baseline, and a review names "
               "that edit and calls it high",
               accepted.get("risk") == "high"
               and accepted.get("declared", {}).get("widened")
               == ["net count 10 -> 1000"], accepted.get("declared"))
            removed = rv[9]
            ok("removing the baseline, a review says so and calls it high",
               removed.get("risk") == "high"
               and removed.get("declared", {}).get("removed") is True,
               removed.get("declared"))
        _, results = runs["merged-widening-keeps-failing"]
        c1000: dict[str, Any] = next((f for f in results[7][1].get("findings", [])
                                      if f["kind"] == "count"), {})
        ok("the check reports 1000 against the declared 10",
           c1000.get("current") == 1000 and c1000.get("surface_allows") == 10,
           c1000)

        _, code, r = runs["stdlib-module-brings-net"]
        origins = [s["file"] for q in grant_finding(r, "net").get(
            "programs", []) for s in q["origins"]]
        ok("a widening through the standard library names the module it "
           "came through", any(o.startswith("<stdlib>/http.vel")
                               for o in origins), origins)
        _, code, r = runs["count-raised"]
        c = next((f for f in r.get("findings", []) if f["kind"] == "count"),
                 {})
        ok("a count finding names the loop that sets it",
           "turns at most 1000" in (c.get("why") or ""), c)
        _, code, r = runs["new-direction"]
        ok("a new direction on a path is not a new effect",
           grant_finding(r, "fs:write:data/in.csv").get("new_effect")
           is False, r.get("findings"))
        ok("a module built while running is flagged by the audit too "
           "(ffi_any)", sabline.audit(COMPUTED_MODULE).ffi_any is True)
        _, code, r = runs["loop-without-fixed-turns"]
        c = next((f for f in r.get("findings", []) if f["kind"] == "count"),
                 {})
        ok("...the finding says which loop has no fixed number of turns",
           "no fixed number of turns" in (c.get("why") or ""), c)
        _, code, r = runs["recursion-has-no-bound"]
        c = next((f for f in r.get("findings", []) if f["kind"] == "count"),
                 {})
        ok("...and says recursion", "call itself" in (c.get("why") or ""),
           c)
        _, code, r = runs["narrowing"]
        ok("narrowing is reported as narrowing", bool(r.get("narrowed"))
           and any("no longer needed" in n for n in r["narrowed"]), r)
        t, code, r = runs["reorder-and-reformat"]
        ok("reordering reports nothing at all, not even narrowing",
           not r.get("narrowed"), r.get("narrowed"))
        fmt = t.sabline("fmt", "app.vel")
        code, r = t.check()
        ok("sabline fmt on it changes nothing either", fmt.returncode == 0
           and code == 0 and not r.get("findings"), fmt.stderr or r)
        ok("the rearranged tree's baseline is the original's, bar the date",
           runs["imports-and-counts"][1]["surface"]
           == runs["rearranged-is-identical"][1]["surface"]
           and runs["imports-and-counts"][1]["programs"]
           == runs["rearranged-is-identical"][1]["programs"])
        _, code, r = runs["stops-compiling"]
        ok("a program that stops compiling is noted", any(
            "does not compile" in n for n in r.get("notes", [])), r)
        _, code, r = runs["older-baseline-version"]
        ok("a baseline from an older Sabline warns",
           any("older" in w for w in r.get("warnings", [])),
           r.get("warnings"))
        for vid in ("newer-baseline-version", "version-never-hides-widening"):
            _, code, r = runs[vid]
            ok(f"...{vid.replace('-', ' ')}: warned", bool(r.get("warnings")),
               r.get("warnings"))
        t, code, r = runs["baseline-deleted"]
        none = t.sabline("capabilities", "check", ".")
        ok("check with no baseline says how to write one",
           none.returncode == 2 and "capabilities init" in none.stderr,
           none.stderr)
        t, again = runs["writer-refuses-to-widen-unasked"]
        ok("init without --force refuses even an unchanged tree, and "
           "--force records it", t.init("--force").returncode == 0
           and t.init().returncode == 1, again.stderr)
        t, code, r = runs["rules-named"]
        g = grant_finding(r, "net:evil.example.net")
        ok("--json is sabline.capabilities-check/1, naming the edit that "
           "would accept each widening",
           r.get("schema") == "sabline.capabilities-check/1"
           and r.get("widened") is True
           and 'add "net:evil.example.net" to surface.grants'
           in g.get("accept", []), g)
        sarif = t.sabline("capabilities", "check", ".", "--sarif")
        try:
            log = json.loads(sarif.stdout)
        except ValueError:
            log = {}
        results = (log.get("runs") or [{}])[0].get("results", [])
        hit: dict[str, Any] = next((x for x in results
                                    if x["ruleId"] == "capability-widened"), {})
        region = (hit.get("locations") or [{}])[0].get(
            "physicalLocation", {})
        ok("--sarif lands each widening as an error at the line that "
           "introduced it",
           sarif.returncode == 1 and hit.get("level") == "error"
           and region.get("artifactLocation", {}).get("uri", "")
           .endswith("poll.vel")
           and region.get("region", {}).get("startLine") == 2, hit)
        if Draft4Validator is None:
            skip("...and the log validates against SARIF 2.1.0",
                 "jsonschema is not installed")
        else:
            schema = json.loads((HERE / "tests" / "sarif-schema-2.1.0.json")
                                .read_text(encoding="utf-8"))
            errs = list(Draft4Validator(schema).iter_errors(log))
            ok("...and the log validates against SARIF 2.1.0", log
               and not errs, [e.message for e in errs[:2]])

        # ------------------------------------------------------------------
        print()
        print("capabilities check stops at the check ceiling (8.2.1)")
        print("-" * 62)
        # Until 8.2.1 it compiled every program under the directory in its
        # own process, with no ceiling: a program built to stall the type
        # checker held it, and the Action's ratchet step with it, until the
        # job's own timeout. It now runs under check's and audit's ceiling.
        t = tree({"app.vel": HELLO})
        made = t.init()
        given = t.sabline("capabilities", "check", ".", "--json",
                          "--check-timeout", "120", "--check-memory-mb", "4096")
        try:
            given_doc = json.loads(given.stdout)
        except ValueError:
            given_doc = {}
        ok("with --check-timeout and --check-memory-mb given, a tree inside "
           "its surface passes, and --json is still the result",
           made.returncode == 0 and given.returncode == 0
           and given_doc.get("schema") == "sabline.capabilities-check/1"
           and given_doc.get("widened") is False,
           given.stderr or given.stdout)
        unbounded = t.sabline("capabilities", "check", ".",
                              "--no-check-ceiling")
        ok("--no-check-ceiling is accepted, as by check and audit",
           unbounded.returncode == 0 and "no widening" in unbounded.stdout,
           unbounded.stderr)
        bad = t.sabline("capabilities", "check", ".", "--check-timeout", "0")
        ok("--check-timeout 0 is refused, as by check",
           bad.returncode == 2
           and "--check-timeout needs a whole number" in bad.stderr, bad.stderr)
        t.write({"stall.vel": STALL})
        for seconds in (2, 5):
            began = time.monotonic()
            done = t.sabline("capabilities", "check", ".", "--json",
                             "--check-timeout", str(seconds))
            took = time.monotonic() - began
            ok(f"a program built to stall the type checker is stopped after "
               f"--check-timeout {seconds}: E613, exit 2, nothing on stdout",
               done.returncode == 2 and not done.stdout.strip()
               and f"error[E613] capabilities check did not finish within "
                   f"{seconds} second(s)" in done.stderr
               and seconds <= took < seconds + 45,
               f"exit {done.returncode} after {took:.1f}s: "
               f"{done.stderr.strip()[-300:]}")

        # ------------------------------------------------------------------
        print()
        print("review from a path spelled unlike git's own")
        print("-" * 62)
        # The working directory's path and the one git reports for the
        # repository can be spelled differently - a Windows short name
        # (RUNNER~1 on CI), a junction, a symbolic link (macOS's /var is
        # /private/var). 4.0.0 compared the two as text and read the ref's
        # files from the wrong place; review must ask git.
        if not HAVE_GIT:
            skip("review from a junction or link", "git is not installed")
        else:
            t = tree({"sub/app.vel": GREETER, "sub/lib/text.vel": TEXT_LIB},
                     git=True)
            t.commit("a tree under a subdirectory")
            # uncommitted: the working tree now needs net, the ref does not,
            # so only a review that really reads the ref's files sees a
            # widening
            t.write({"sub/app.vel": GREETER.replace(
                "fn main() uses io {",
                "fn main() uses io, net {\n"
                '    check fetch_status("https://x.example.org") {\n'
                "        ok s {\n"
                "            print(to_text(s))\n"
                "        }\n"
                "        fail w {\n"
                "            print(w)\n"
                "        }\n"
                "    }")})
            link = Path(tempfile.mkdtemp(prefix="sabline-link-")) / "repo"
            made = False
            try:
                if os.name == "nt":
                    made = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(link),
                         str(t.root)], capture_output=True).returncode == 0
                else:
                    os.symlink(t.root, link, target_is_directory=True)
                    made = True
            except OSError:
                made = False
            if not made:
                skip("review from a path spelled unlike git's",
                     "cannot make a junction or link here")
            else:
                done = subprocess.run(
                    [sys.executable, str(SABLINE), "review", "--against",
                     "HEAD", ".", "--json"], cwd=str(link / "sub"),
                    capture_output=True, text=True, encoding="utf-8",
                    timeout=600)
                try:
                    rev = json.loads(done.stdout)
                except ValueError:
                    rev = {"_stderr": done.stderr}
                ok("review from a path spelled unlike git's own reads the "
                   "ref's files, not the working tree: io before, net "
                   "after, high",
                   rev.get("risk") == "high"
                   and rev.get("surface", {}).get("before", {})
                   .get("grants") == ["io"]
                   and "net:x.example.org" in rev.get("surface", {})
                   .get("after", {}).get("grants", []), rev)
                if os.name == "nt":
                    os.rmdir(link)             # the junction, not its target
                else:
                    link.unlink()
    finally:
        for t in trees:
            t.close()

    print("-" * 62)
    print(f"{passed} correct, {failed} wrong")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
