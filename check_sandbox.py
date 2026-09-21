#!/usr/bin/env python3
"""The runtime must refuse effects the person running did not allow.

The compiler checks that a function declares what it does. This checks
the other half: that `--allow` and `--deny` are enforced while the
program runs, whatever the source claims about itself - so someone can
run a program they have not read.

Needs no theorem prover: every case here is about the runtime, so this
behaves identically with and without z3.

Every case is data, and sabline-spec's conformance corpus is written
from it (build_conformance.py writes sabline-spec tests/L2): the
budget, the program, the code the refusal must carry, and what must
not happen. A case this implementation passes, another implementation
can run from the corpus without reading this file - except the ones
marked `not_in_corpus`, which say why.

Paths and ports are placeholders the fixture fills in, the same here
and in any runner of the corpus:

    {ROOT}      a fresh directory, the run's working directory
    {DATA}      {ROOT}/box/data, holding a.txt ("inside\\n")
    {OUT}       {ROOT}/box/out, empty
    {OUTSIDE}   {ROOT}/outside.txt ("outside\\n")
    {PORT_A}    a local HTTP server: GET /go answers 302 to
                http://localhost:{PORT_B}/landed, anything else 200 "hello"
    {PORT_B}    a second server, answering the same way

Paths are written with "/" on every platform.

    python check_sandbox.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
SABLINE = HERE / "sabline.py"
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

isolate("check_sandbox")              # its own directory

# words a program prints only if it got past the refusal
MARKERS = ("READ IT", "WROTE IT", "REACHED IT", "CALLED IT", "OPENED IT",
           "GOT THROUGH", "CARRIED ON", "SWALLOWED THE REFUSAL",
           "FOLLOWED IT")

# Why the attribute-chain cases are not in the corpus: each one depends
# on Python's object model - which module owns codecs.encode, that
# os.system lives in nt or posix, what __globals__ holds. The rule they
# test (sabline-spec 5.3) binds every implementation, but the cases can
# only be written against one host language.
PYTHON_REACH = ("depends on Python's object model (which module a Python "
                "attribute belongs to); sabline-spec 5.3 binds every "
                "implementation, but this case is written against Python")
PYTHON_HOST = ("needs a Python host to run the granted call; the corpus "
               "runs no host code")


def _read(path: Any) -> str:
    return (
        "fn main() uses io, fs {\n"
        f'    check read_file("{path}") {{\n'
        "        ok t {\n            print(\"READ IT\")\n        }\n"
        "        fail w {\n            print(\"failed\")\n        }\n"
        "    }\n}\n")


def _write(path: Any) -> str:
    return (
        "fn main() uses io, fs {\n"
        f'    write_file("{path}", "escaped")\n'
        "    print(\"WROTE IT\")\n}\n")


def _fetch(url: Any) -> str:
    return (
        "fn main() uses io, net {\n"
        f'    check fetch("{url}") {{\n'
        "        ok b {\n            print(\"REACHED IT\")\n        }\n"
        "        fail w {\n            print(\"failed\")\n        }\n"
        "    }\n}\n")


def escape(id: Any, name: Any, source: Any, *, allow: Any = None, deny: Any = None, refused: Any,
           creates: Any = None, stdout: Any = (), stderr: Any = (), requires: Any = (), spec: Any = (),
           not_in_corpus: Any = None) -> Any:
    """A program that must be refused with `refused`, print none of
    MARKERS, create nothing at `creates`, and print each of `stdout`
    before the refusal.

    `stderr` holds words the refusal itself must carry. It is about
    this implementation's messages, which STABILITY.md does not hold
    stable and the corpus never compares, so a case using it says so
    with `not_in_corpus`."""
    return dict(id=id, name=name, source=source.lstrip(), allow=allow,
                deny=deny, args=[], refused=refused, creates=creates,
                stdout=list(stdout), stderr=list(stderr),
                requires=list(requires),
                spec=list(spec), not_in_corpus=not_in_corpus)


def honest(id: Any, name: Any, source: Any, *, allow: Any = None, deny: Any = None, args: Any = (), stdout: Any = (),
           stderr: Any = (), requires: Any = (), spec: Any = (), not_in_corpus: Any = None) -> Any:
    """A program that must run to its end and print each of `stdout`."""
    return dict(id=id, name=name, source=source.lstrip(), allow=allow,
                deny=deny, args=list(args), refused=None, creates=None,
                stdout=list(stdout), stderr=list(stderr),
                requires=list(requires),
                spec=list(spec), not_in_corpus=not_in_corpus)


ESCAPES = [
    escape("read-under-io", "reading a file", '''
fn peek(path: Text) -> Text uses fs or fail {
    return try read_file(path)
}

fn main() uses io, fs {
    check peek("{DATA}/a.txt") {
        ok body {
            print("READ IT")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io", refused="E310", spec=["6 G2", "6 G5"]),
    escape("write-under-io", "writing a file", '''
fn main() uses io, fs {
    write_file("{ROOT}/wrote.txt", "escaped")
    print("WROTE IT")
}
''', allow="io", refused="E310", creates="{ROOT}/wrote.txt",
        spec=["6 G2"]),
    escape("net-under-io", "reaching the network", '''
fn main() uses io, net {
    check fetch_status("https://example.com") {
        ok code {
            print("REACHED IT")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io", refused="E310", spec=["6 G2"]),
    escape("ffi-under-io", "calling Python", '''
fn main() uses io, ffi {
    check py("os", "getcwd", ["x"]) {
        ok out {
            print("CALLED IT")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io", refused="E310", spec=["6 G2"]),
    escape("ffi-handle-under-io", "opening a database through a handle", '''
fn main() uses io, ffi {
    check py_new("sqlite3", "connect", "[\\":memory:\\"]") {
        ok conn {
            print("OPENED IT")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io", refused="E310", spec=["6 G2"]),
    escape("clock-under-io", "asking the clock", '''
fn main() uses io, clock {
    print(now())
}
''', allow="io", refused="E310", spec=["6 G2"]),
    escape("rand-under-io", "asking for randomness", '''
fn main() uses io, rand {
    print(random(6))
}
''', allow="io", refused="E310", spec=["6 G2"]),
    escape("effect-behind-two-helpers", "hiding the effect behind a helper",
           '''
fn helper(path: Text) -> Int uses fs or fail {
    let body = try read_file(path)
    return length(body)
}

fn wrapper(path: Text) -> Int uses fs or fail {
    return try helper(path)
}

fn main() uses io, fs {
    check wrapper("{DATA}/a.txt") {
        ok n {
            print("GOT THROUGH")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io", refused="E310", spec=["6 G2", "6 G5"]),
    escape("refusal-cannot-be-caught",
           "catching the refusal to carry on anyway", '''
fn peek(path: Text) -> Text uses fs or fail {
    return try read_file(path)
}

fn main() uses io, fs {
    check peek("{DATA}/a.txt") {
        ok body {
            print("READ IT")
        }
        fail why {
            print("SWALLOWED THE REFUSAL")
        }
    }
    print("CARRIED ON")
}
''', allow="io", refused="E310", spec=["6 G3"]),
    # ---- the default budget (5.0). A run with no --allow gets io;
    # before 5.0 it got all seven effects and none of these was refused.
    escape("default-refuses-fs", "a program that writes a file, with no "
           "--allow at all", '''
fn main() uses io, fs {
    write_file("{ROOT}/wrote.txt", "escaped")
    print("WROTE IT")
}
''', refused="E310", creates="{ROOT}/wrote.txt",
        not_in_corpus="a run given no budget is outside the format "
                      "(sabline-spec 4.6); what it grants is the "
                      "reference's choice, which from 5.0 is io"),
    escape("default-refusal-names-the-effect-and-the-flag", "the refusal "
           "under the default says which effect and how to grant it", '''
fn main() uses io, fs {
    write_file("{ROOT}/wrote.txt", "escaped")
    print("WROTE IT")
}
''', refused="E310", creates="{ROOT}/wrote.txt",
        stderr=["needs the 'fs' effect", "it allows: io",
                "--allow io,fs"],
        not_in_corpus="about the wording of this implementation's "
                      "messages, which STABILITY.md does not hold "
                      "stable and the corpus never compares"),
    escape("default-refuses-net", "a program that reaches the network, "
           "with no --allow at all", '''
fn main() uses io, net {
    check fetch_status("http://127.0.0.1:{PORT_A}/") {
        ok code {
            print("REACHED IT")
        }
        fail why {
            print("SWALLOWED THE REFUSAL")
        }
    }
}
''', refused="E310",
        not_in_corpus="a run given no budget is outside the format "
                      "(sabline-spec 4.6); what it grants is the "
                      "reference's choice, which from 5.0 is io"),
    escape("deny-one", "denying one effect while allowing the rest", '''
fn main() uses io, fs {
    write_file("{ROOT}/wrote.txt", "escaped")
    print("WROTE IT")
}
''', allow="io,fs", deny="fs", refused="E310",
        creates="{ROOT}/wrote.txt", spec=["4.4", "6 G2"]),
    escape("deny-narrows-the-default", "--deny narrows what the default "
           "granted; it does not widen it back to every effect", '''
fn main() uses io, fs {
    write_file("{ROOT}/wrote.txt", "escaped")
    print("WROTE IT")
}
''', deny="net", refused="E310", creates="{ROOT}/wrote.txt",
        not_in_corpus="a denial with no grants narrows the runtime's "
                      "default budget (sabline-spec 4.4, 4.6), which "
                      "the format leaves to the runtime"),
    escape("ffi-module-outside-list",
           "reaching a module outside the ffi allow-list", '''
fn main() uses io, ffi {
    let none: List of Text = []
    check py("os", "getcwd", none) {
        ok d {
            print("GOT THROUGH")
        }
        fail w {
            print("failed")
        }
    }
}
''', allow="io,ffi:math", refused="E311", spec=["5.3", "6 G2"]),
    escape("ffi-submodule-path",
           "dodging the allow-list with a submodule path", '''
fn main() uses io, ffi {
    let none: List of Text = []
    check py("os.path", "getcwd", none) {
        ok d {
            print("GOT THROUGH")
        }
        fail w {
            print("failed")
        }
    }
}
''', allow="io,ffi:math", refused="E311", spec=["5.3"]),
    escape("ffi-through-py-json",
           "dodging the allow-list through py_json", '''
fn main() uses io, ffi {
    check py_json("subprocess", "getoutput", "[\\"echo GOT THROUGH\\"]") {
        ok d {
            print("GOT THROUGH")
        }
        fail w {
            print("failed")
        }
    }
}
''', allow="io,ffi:math", refused="E311", spec=["5.3"]),
    escape("ffi-through-handle",
           "dodging the allow-list through a handle", '''
fn main() uses io, ffi {
    check py_new("subprocess", "Popen", "[[\\"echo\\"]]") {
        ok h {
            print("GOT THROUGH")
        }
        fail w {
            print("failed")
        }
    }
}
''', allow="io,ffi:math", refused="E311", spec=["5.3"]),
    escape("deny-several", "denying several at once", '''
fn main() uses io, net {
    check fetch_status("https://example.com") {
        ok code {
            print("REACHED IT")
        }
        fail why {
            print("failed")
        }
    }
}
''', allow="io,fs,net,ffi", deny="fs,net,ffi", refused="E310",
        spec=["4.4", "6 G2"]),
    # 3.3: an ffi:M grant is bounded to the module a call actually
    # reaches, not merely the one it names. The attribute chain is checked
    # step by step; an object owned by a module outside the grants is
    # E311, naming that module, and an owner that cannot be placed is
    # refused rather than allowed. These are the escapes that step 2.2's
    # module-name-only check let through until 3.3.
    escape("ffi-reach-codecs-through-json",
           "reaching codecs through a granted json", '''
fn main() uses io, ffi {
    check py("json", "codecs.encode", ["x"]) {
        ok o { print("GOT THROUGH") }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:json", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),
    escape("ffi-reach-os-system-through-os",
           "reaching os.system through a granted os, subprocess-free", '''
fn main() uses io, ffi {
    check py_int("os", "system", ["echo GOT THROUGH"]) {
        ok n { print("GOT THROUGH") }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:os", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),
    escape("ffi-reach-importlib",
           "using a granted importlib to reach another module", '''
fn main() uses io, ffi {
    check py_json("importlib", "import_module", "[\\"os\\"]") {
        ok o { print("GOT THROUGH") }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:importlib", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),
    escape("ffi-reach-builtins-type",
           "reaching a builtins type through a granted module's value", '''
fn main() uses io, ffi {
    let none: List of Text = []
    check py("math", "pi.__class__", none) {
        ok o { print("GOT THROUGH") }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:math", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),
    escape("ffi-reach-globals",
           "laundering through __globals__ to reach builtins", '''
fn main() uses io, ffi {
    let none: List of Text = []
    check py("json", "dumps.__globals__.__class__", none) {
        ok o { print("GOT THROUGH") }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:json", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),
    escape("ffi-reach-handle-foreign-object",
           "a handle exposing an object from another module", '''
fn main() uses io, ffi {
    check py_new("json", "decoder.JSONDecoder", "[]") {
        ok h {
            check py_field(h, "scan_once") {
                ok f { print("GOT THROUGH") }
                fail w { print("failed") }
            }
        }
        fail w { print("failed") }
    }
}
''', allow="io,ffi:json", refused="E311", spec=["5.3"],
        not_in_corpus=PYTHON_REACH),

    # ---- scoped grants (3.0): paths, hosts, counts, and env on its own
    escape("fs-read-outside-prefix", "reading outside the granted prefix",
           _read("{OUTSIDE}"), allow="io,fs:read:{DATA}", refused="E313",
           spec=["5.1", "6 G2"]),
    escape("fs-write-under-read-grant", "writing with only read granted",
           _write("{DATA}/new.txt"), allow="io,fs:read:{DATA}",
           refused="E313", creates="{DATA}/new.txt", spec=["5.1"]),
    escape("fs-dotdot-escape", "escaping the prefix with ..",
           _read("{DATA}/../../outside.txt"), allow="io,fs:read:{DATA}",
           refused="E313", spec=["5.1"]),
    escape("net-host-not-in-list", "a host not in the list",
           _fetch("http://localhost:{PORT_A}/"),
           allow="io,net:127.0.0.1:{PORT_A}", refused="E314",
           spec=["5.2"]),
    escape("net-wildcard-parent-domain",
           "a wildcard must not match the parent domain",
           _fetch("http://example.com/"), allow="io,net:*.example.com",
           refused="E314", spec=["5.2"]),
    escape("net-port-not-in-list", "a port not in the list",
           _fetch("http://127.0.0.1:{PORT_B}/"),
           allow="io,net:127.0.0.1:{PORT_A}", refused="E314",
           spec=["5.2"]),
    escape("fs-count-reached", "the file operation count reached", '''
fn main() uses io, fs {
    let i = 0
    while i < 3 {
        if file_exists("{DATA}/a.txt") {
            print("looked")
        }
        i = i + 1
    }
    print("GOT THROUGH")
}
''', allow="io,fs:read:{DATA}@2", refused="E315", stdout=["looked"],
        spec=["5.4"]),
    escape("net-count-reached", "the network operation count reached", '''
fn main() uses io, net {
    let i = 0
    while i < 3 {
        check fetch_status("http://127.0.0.1:{PORT_A}/") {
            ok c {
                print("asked")
            }
            fail w {
                print("failed")
            }
        }
        i = i + 1
    }
    print("GOT THROUGH")
}
''', allow="io,net:127.0.0.1:{PORT_A}@2", refused="E315", stdout=["asked"],
        spec=["5.4"]),
    escape("env-under-io", "env() with only io granted", '''
fn main() uses io, env {
    let path = env("PATH", "")
    print("READ IT")
}
''', allow="io", refused="E310", spec=["3.1", "6 G2"]),
    # 6.0: the runtime half of the declassify effect. The compiler keeps
    # a Secret away from every sink; this keeps the one way out behind
    # the operator's budget, so a program that says it declassifies can
    # still be run without being allowed to.
    escape("declassify-not-granted",
           "declassify() with env and io granted but not declassify", '''
fn main() uses io, env, declassify {
    let key = env("PATH", "")
    print("READ IT " + declassify(key, "this demo prints it"))
}
''', allow="io,env", refused="E310", spec=["3.1", "6 G2"]),
    escape("fs-symlink-escape", "escaping the prefix through a symlink",
           _read("{DATA}/link.txt"), allow="io,fs:read:{DATA}",
           refused="E313", requires=["symlink"], spec=["5.1"]),
    # 4.1: three rules sabline-spec 0.3 listed as untested (Q9)
    escape("fs-count-zero", "@0 grants the effect and permits no operation",
           '''
fn main() uses io, fs {
    if file_exists("{DATA}/a.txt") {
        print("GOT THROUGH")
    }
}
''', allow="io,fs:read:{DATA}@0", refused="E315", spec=["5.4"]),
    escape("fs-count-spent-by-failed-operation",
           "an operation that fails has still spent its count", '''
fn main() uses io, fs {
    check read_file("{DATA}/missing.txt") {
        ok t {
            print("READ IT")
        }
        fail w {
            print("missing")
        }
    }
    if file_exists("{DATA}/a.txt") {
        print("GOT THROUGH")
    }
}
''', allow="io,fs:read:{DATA}@1", refused="E315", stdout=["missing"],
        spec=["5.4"]),
    escape("net-no-scheme-is-https",
           "a URL with no scheme is HTTPS at port 443, outside a port-80 "
           "grant", _fetch("example.com/"), allow="io,net:example.com:80",
           refused="E314", spec=["5.2"]),
]

# things that must still work: a budget must not break honest programs
HONEST = [
    honest("pure-under-empty-budget", "pure work with no permission at all",
           '''
import "std.vel"

fn total(n: Int) -> Int
    requires n >= 0
    ensures result >= 0
{
    let sum = 0
    for i in 0 to n {
        sum = sum + i
    }
    return sum
}

fn main() {
    let answer = total(10)
    let sorted = sort([3, 1, 2])
}
''', allow="", requires=["stdlib"], spec=["6 G5"]),
    honest("io-under-io", "printing when io is allowed", '''
fn main() uses io {
    print("hello")
}
''', allow="io", stdout=["hello"], spec=["4.1"]),
    honest("clock-under-clock", "the clock when clock is allowed", '''
fn main() uses io, clock {
    if now() > 0 {
        print("time moves")
    }
}
''', allow="io,clock", stdout=["time moves"], spec=["4.1"]),
    # 6.0: the two honest halves of Secret. A program may read the
    # environment and compare what it got without any grant beyond env;
    # and one granted declassify may let a value out, which is the only
    # way a secret becomes an ordinary value.
    honest("secret-kept-under-env", "a secret read and held, never let out",
           '''
fn main() uses io, env {
    let key = env("SABLINE_NOT_SET", "")
    print("a key was read, and this program could not print it")
}
''', allow="io,env",
        stdout=["a key was read, and this program could not print it"],
        spec=["3.1"]),
    honest("declassify-granted", "declassify when declassify is allowed",
           '''
fn main() uses io, env, declassify {
    let key = env("SABLINE_NOT_SET", "opened")
    print(declassify(key, "this demo shows what declassify does"))
}
''', allow="io,env,declassify", stdout=["opened"], spec=["3.1"]),
    honest("ffi-granted-module", "an allowed module works under the allow-list",
           '''
fn main() uses io, ffi {
    check py_float("math", "sqrt", ["16"]) {
        ok r {
            print("root ok")
        }
        fail w {
            print(w)
        }
    }
}
''', allow="io,ffi:math", stdout=["root ok"], not_in_corpus=PYTHON_HOST),
    # 5.0: a run with no --allow gets io - print and read a line, and
    # nothing else. Before 5.0 it got all seven effects, and this case
    # asserted that it did.
    honest("default-budget-is-io", "a run with no --allow may print", '''
fn main() uses io {
    print("all fine")
}
''', stdout=["all fine"],
        not_in_corpus="a run given no budget is outside the format "
                      "(sabline-spec 4.6); what it grants is the "
                      "reference's choice, which from 5.0 is io"),
    honest("allow-all-still-grants-everything", "--allow all grants what "
           "a run with no budget used to get", '''
fn main() uses io, clock, rand {
    if now() > 0 and random(6) >= 0 {
        print("all fine")
    }
}
''', allow="all", stdout=["all fine"],
        stderr=["--allow all grants every effect"],
        not_in_corpus="`all` is this command line's shorthand, not part "
                      "of the budget grammar the corpus tests"),
    # 3.3: the reach check must not break honest deep access inside a
    # granted module, and must let a grant of two modules use both.
    honest("ffi-deep-attribute-inside-grant",
           "a legitimate deep attribute inside the granted module still works",
           '''
fn main() uses io, ffi {
    check py_new("json", "decoder.JSONDecoder", "[]") {
        ok h { print("made a decoder") }
        fail w { print(w) }
    }
}
''', allow="io,ffi:json", stdout=["made a decoder"],
        not_in_corpus=PYTHON_HOST),
    honest("ffi-two-module-grant", "a two-module grant, each module used "
           "correctly", '''
fn main() uses io, ffi {
    check py_float("math", "sqrt", ["16"]) {
        ok r {
            check py("base64", "b64encode", ["aGk="]) {
                ok b { print("both modules ok") }
                fail w { print(w) }
            }
        }
        fail w { print(w) }
    }
}
''', allow="io,ffi:math,ffi:base64", stdout=["both modules ok"],
        not_in_corpus=PYTHON_HOST),
    # 3.3: ffi is additive like fs and net (spec v0.2, Q2). A plain ffi
    # grants every module, so ffi,ffi:math is every module - the wider
    # grant wins, in either order, and a module other than math works.
    honest("ffi-additive", "additive ffi: a plain ffi widens a named-module "
           "grant", '''
fn main() uses io, ffi {
    let none: List of Text = []
    check py("os", "getcwd", none) {
        ok d { print("wider ffi wins") }
        fail w { print(w) }
    }
}
''', allow="io,ffi,ffi:math", stdout=["wider ffi wins"],
        not_in_corpus=PYTHON_HOST + "; sabline-spec tests/L1 holds the "
                      "parse of io,ffi,ffi:math"),
    # until 2.62 `--allow io` leaked into args() as two extra words
    honest("args-not-budget", "args() carries the program's arguments, not "
           "the budget", '''
fn main() uses io {
    print(format("args: {}", args()))
}
''', allow="io", args=["7", "eight"], stdout=["args: [7, eight]"],
        not_in_corpus="about this command line's flags: the corpus gives "
                      "a run its budget and its arguments separately"),
    honest("args-not-deny", "args() is clean under --deny as well", '''
fn main() uses io {
    print(format("args: {}", args()))
}
''', allow="io", deny="fs,net", args=["only"], stdout=["args: [only]"],
        not_in_corpus="about this command line's flags: the corpus gives "
                      "a run its budget and its arguments separately"),

    # ---- scoped grants (3.0)
    honest("scoped-exact-grants", "an honest program using exactly its grants",
           '''
fn main() uses io, env, fs, net, declassify {
    check read_file("{DATA}/a.txt") {
        ok t {
            write_file("{OUT}/copy.txt", t)
            check fetch_status("http://127.0.0.1:{PORT_A}/") {
                ok c {
                    let path = declassify(env("PATH", ""),
                    "whether PATH is set at all is not its contents")
                    print(format("all grants used, status {}, path set: {}",
                                 c, length(path) > 0))
                }
                fail w {
                    print("fetch failed: " + w)
                }
            }
        }
        fail w {
            print("read failed: " + w)
        }
    }
}
''', allow="declassify,io,env,fs:read:{DATA},fs:write:{OUT}@5,"
           "net:127.0.0.1:{PORT_A}@5",
        stdout=["all grants used, status 200"], spec=["5.1", "5.2", "5.4"]),
    honest("redirect-to-ungranted-host-is-a-failure",
           "a redirect to an ungranted host is a failure the program sees",
           '''
fn main() uses io, net {
    check fetch("http://127.0.0.1:{PORT_A}/go") {
        ok b {
            print("FOLLOWED IT")
        }
        fail w {
            print("caught: " + w)
        }
    }
}
''', allow="io,net:127.0.0.1:{PORT_A}",
        stdout=["caught: ", "localhost:{PORT_B}"], spec=["5.2", "6 G4"]),
    honest("redirect-to-granted-host-is-followed",
           "a redirect to a granted host is followed", '''
fn main() uses io, net {
    check fetch("http://127.0.0.1:{PORT_A}/go") {
        ok b {
            print("landed: " + b)
        }
        fail w {
            print("caught: " + w)
        }
    }
}
''', allow="io,net:127.0.0.1:{PORT_A},net:localhost:{PORT_B}",
        stdout=["landed: hello"], spec=["5.2"]),
    # fs is additive: fs:read:D and fs:write:D grant both directions, and
    # the program uses each. net is additive: two host grants grant both.
    honest("fs-additive", "additive fs: read and write grants both apply", '''
fn main() uses io, fs {
    check read_file("{DATA}/a.txt") {
        ok t {
            write_file("{OUT}/copy.txt", t)
            print("fs additive ok")
        }
        fail w { print("read failed: " + w) }
    }
}
''', allow="io,fs:read:{DATA},fs:write:{OUT}", stdout=["fs additive ok"],
        spec=["4.3"]),
    honest("net-additive", "additive net: two host grants both apply", '''
fn main() uses io, net {
    check fetch_status("http://127.0.0.1:{PORT_A}/") {
        ok a {
            check fetch_status("http://localhost:{PORT_B}/") {
                ok b { print("net additive ok") }
                fail w { print("second failed: " + w) }
            }
        }
        fail w { print("first failed: " + w) }
    }
}
''', allow="io,net:127.0.0.1:{PORT_A},net:localhost:{PORT_B}",
        stdout=["net additive ok"], spec=["4.3"]),
    # 4.1: sabline-spec 0.3 Q9 - untested until now
    honest("fs-exists-under-write-grant",
           "an existence check is permitted by a write grant alone", '''
fn main() uses io, fs {
    print(format("exists: {}", file_exists("{DATA}/a.txt")))
}
''', allow="io,fs:write:{DATA}", stdout=["exists: true"], spec=["5.1", "7"]),
]


def fixture(root: Path, ports: tuple[Any, ...], symlink: bool) -> dict[str, Any]:
    """Make the directories and files the placeholders name, and return
    the placeholders' values. `symlink` asks for {DATA}/link.txt, a
    symbolic link to {OUTSIDE}; False when the system cannot make one."""
    data, out = root / "box" / "data", root / "box" / "out"
    data.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (data / "a.txt").write_text("inside\n", encoding="utf-8")
    (root / "outside.txt").write_text("outside\n", encoding="utf-8")
    made_link = False
    if symlink:
        try:
            (data / "link.txt").symlink_to(root / "outside.txt")
            made_link = True
        except (OSError, NotImplementedError):
            made_link = False
    return {"{ROOT}": root.as_posix(), "{DATA}": data.as_posix(),
            "{OUT}": out.as_posix(), "{OUTSIDE}": (root / "outside.txt")
            .as_posix(), "{PORT_A}": str(ports[0]),
            "{PORT_B}": str(ports[1]), "_symlink": made_link}


def fill(text: Any, values: dict[Any, Any]) -> Any:
    if text is None:
        return None
    for key, value in values.items():
        if key.startswith("{"):
            text = text.replace(key, value)
    return text


def local_servers() -> tuple[Any, ...]:
    """Two local http servers: the first redirects /go to the second."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    ports: dict[str, int] = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/go"):
                self.send_response(302)
                self.send_header("Location",
                                 f"http://localhost:{ports['other']}/landed")
                self.end_headers()
                return
            body = b"hello"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: Any) -> None:
            pass

    a = HTTPServer(("127.0.0.1", 0), H)
    b = HTTPServer(("127.0.0.1", 0), H)
    ports["granted"] = a.server_address[1]
    ports["other"] = b.server_address[1]
    for srv in (a, b):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return a, b, ports["granted"], ports["other"]


def run(case: dict[Any, Any], values: dict[Any, Any], root: Path) -> tuple[Any, ...]:
    """(exit code, stdout, stderr) of the case run from the command line,
    in the fixture's root."""
    prog = root / "_sandbox_check.vel"
    prog.write_text(fill(case["source"], values), encoding="utf-8")
    flags = []
    if case["allow"] is not None:
        flags += ["--allow", fill(case["allow"], values)]
    if case["deny"] is not None:
        flags += ["--deny", fill(case["deny"], values)]
    done = subprocess.run(
        [sys.executable, str(SABLINE), str(prog)] + flags
        + [fill(a, values) for a in case["args"]],
        capture_output=True, text=True, timeout=300, cwd=root)
    return done.returncode, done.stdout or "", done.stderr or ""


def refusal_code(stderr: str) -> Any:
    import re
    m = re.search(r"error\[(E\d{3})\]", stderr)
    return m.group(1) if m else None


def main() -> int:
    passed = failed = 0
    root = Path(tempfile.mkdtemp(prefix="sabline-sandbox-"))
    srv_a, srv_b, port_a, port_b = local_servers()
    values = fixture(root, (port_a, port_b), symlink=True)
    cases = [c for c in ESCAPES
             if "symlink" not in c["requires"] or values["_symlink"]]
    if len(cases) < len(ESCAPES):
        print("  skip: the symlink escape case needs a file system that "
              "can make a symbolic link here")
    print(f"{len(cases)} escape attempts that must be refused")
    print("-" * 62)
    for case in cases:
        creates = fill(case["creates"], values)
        if creates:
            Path(creates).unlink(missing_ok=True)
        code, out, err = run(case, values, root)
        got = refusal_code(err)
        escaped = creates is not None and Path(creates).exists()
        shouted = [w for w in MARKERS if w in out]
        missing = [s for s in case["stdout"]
                   if fill(s, values) not in out]
        missing += [s for s in case["stderr"] if fill(s, values) not in err]
        if escaped:
            print(f"  ESCAPED      {case['name']} (it created the file)")
            failed += 1
        elif shouted:
            print(f"  ESCAPED      {case['name']} (the program carried on: "
                  f"{shouted[0]})")
            failed += 1
        elif code != 0 and got == case["refused"] and not missing:
            print(f"  ok refused   {case['name']} ({got})")
            passed += 1
        else:
            print(f"  WRONG        {case['name']}")
            print(f"               expected {case['refused']}, got "
                  f"{got or 'no refusal'} (exit {code})"
                  + (f"; missing output {missing}" if missing else "")
                  + f": {(err or out).strip().splitlines()[:1]}")
            failed += 1
        if creates:
            Path(creates).unlink(missing_ok=True)

    print()
    print(f"{len(HONEST)} honest programs that must still run")
    print("-" * 62)
    for case in HONEST:
        code, out, err = run(case, values, root)
        missing = [s for s in case["stdout"] if fill(s, values) not in out]
        missing += [s for s in case["stderr"] if fill(s, values) not in err]
        if code == 0 and not missing:
            print(f"  ok runs      {case['name']}")
            passed += 1
        else:
            print(f"  BROKEN       {case['name']}")
            print(f"               exit {code}: "
                  f"{(err or out).strip().splitlines()[:1]}"
                  + (f"; missing output {missing}" if missing else ""))
            failed += 1

    import shutil
    shutil.rmtree(root, ignore_errors=True)
    for srv in (srv_a, srv_b):
        srv.shutdown()
    print("-" * 62)
    print(f"{passed} correct, {failed} wrong")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
