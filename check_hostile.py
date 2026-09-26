#!/usr/bin/env python3
"""Hostile resource use must end in a coded error, never a traceback.

Release 8.2, item 13. Each case runs the real command line (or the
library) against a program built to abuse a resource - the stack, file
descriptors, the disk, memory, the console encoding, the path length, the
size of a single function - and asserts three things:

  * a known Sabline E-code, or a clean success where success is right;
  * no "Traceback" anywhere in stdout or stderr - a Python traceback
    reaching the user, or a process that dies with no Sabline error, is
    a bug;
  * an exit code that says what happened.

A case that shows a traceback or a silent death fails, and is named in
the summary as a FINDING - a defect to fix in the compiler, not something
to work around in the test. The five this suite found when it was written
(a value nested too deeply, blocks nested too deeply, a NUL in a path, a
cp1252 console, a native compile that never ended) are fixed in 8.2, so
every case passes; the count of findings is printed at the end.

    python check_hostile.py

The POSIX-only cases (a low RLIMIT_NOFILE) run only under an os.name ==
"posix" Python - run it once under WSL for those. The Windows-only cases
(paths over 260 characters) run only on Windows. Each skipped case says
why. Keep the whole suite under about five minutes.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import IO, Any, cast

HERE = Path(__file__).resolve().parent
SABLINE = HERE / "sabline.py"
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_hostile")

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
    del z3
except ImportError:
    HAVE_Z3 = False

PASS = 0
FAIL = 0
SKIP = 0
FINDINGS = []          # (label, detail) of every case that showed a defect


def _a(s: Any) -> Any:
    """ASCII-only, so the suite's own output never itself trips a cp1252
    console (captured program output can hold non-ASCII or U+FFFD)."""
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


def ok(label: Any, cond: Any, detail: str = "", finding: bool = False) -> None:
    """Record one case. When it fails and `finding` is set, it is a
    compiler defect this suite deliberately keeps failing."""
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok    %s" % _a(label))
    else:
        FAIL += 1
        tag = "FINDING" if finding else "FAIL   "
        print("  %s %s   %s" % (tag, _a(label), _a(detail)[:150]))
        if finding:
            FINDINGS.append((_a(label), _a(detail)))


def skip(label: Any, why: Any) -> None:
    global SKIP
    SKIP += 1
    print("  skip  %s (%s)" % (_a(label), _a(why)))


def new_dir(name: Any) -> Any:
    d = Path(WORK) / (name + "-" + str(len(os.listdir(WORK))))
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(d: Any, source: Any, name: str = "p.vel") -> Any:
    p = Path(d) / name
    p.write_text(source, encoding="utf-8")
    return p


def run_cli(args: Any, cwd: Any = None, env: Any = None, stdin: Any = None, timeout: int = 120, preexec: Any = None) -> tuple[Any, ...]:
    """Run sabline. Returns (exit_code, combined_text, seconds). A timeout
    is reported as exit -99 and a [TIMEOUT] marker; the raw bytes are
    decoded with errors=replace so a cp1252 crash still shows as one."""
    e = dict(os.environ)
    if env:
        e.update(env)
    kw = {}
    if preexec is not None and os.name == "posix":
        kw["preexec_fn"] = preexec
    t0 = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, str(SABLINE)] + args,
                           capture_output=True, cwd=cwd, env=e,
                           input=stdin, timeout=timeout, **kw)
        out = (r.stdout or b"").decode("utf-8", "replace") + \
              (r.stderr or b"").decode("utf-8", "replace")
        return r.returncode, out, time.perf_counter() - t0
    except subprocess.TimeoutExpired as ex:
        got = b""
        for part in (ex.stdout, ex.stderr):
            if part:
                got += part if isinstance(part, bytes) else part.encode()
        return -99, got.decode("utf-8", "replace") + \
            ("\n[TIMEOUT %ds]" % timeout), time.perf_counter() - t0


def codes(out: Any) -> list[Any]:
    return sorted(set(re.findall(r"E\d{3}", out)))


def clean(out: Any) -> bool:
    return "Traceback" not in out


# ---------------------------------------------------------------------------
# Programs used across the cases
# ---------------------------------------------------------------------------

# A record whose field is a list of itself: build(depth) makes a value
# nested `depth` deep, with the flat type `Node`. Standing in for "a list
# nested 10,000 deep built in a loop" - a genuinely nested runtime shape a
# static list type cannot express directly.
DEEP_RECORD = (
    "record Node {\n"
    "    v: Int\n"
    "    kids: List of Node\n"
    "}\n"
    "\n"
    "fn build(depth: Int) -> Node {\n"
    "    let empty: List of Node = []\n"
    "    let n = Node(v: 0, kids: empty)\n"
    "    let i = 0\n"
    "    while i < depth {\n"
    "        n = Node(v: i, kids: [n])\n"
    "        i = i + 1\n"
    "    }\n"
    "    return n\n"
    "}\n"
    "\n")

DEEP_N = 10000


def deep_value_prog(op: Any) -> str:
    """A program that builds a DEEP_N-deep value and then does `op` to it."""
    ops = {
        "print":   "    print(build(%d))\n" % DEEP_N,
        "eq":      "    let a = build(%d)\n    let b = build(%d)\n"
                   "    print(a == b)\n" % (DEEP_N, DEEP_N),
        "to_text": "    let t = to_text(build(%d))\n    print(length(t))\n"
                   % DEEP_N,
        "json_of": "    let t = json_of(build(%d))\n    print(length(t))\n"
                   % DEEP_N,
        "format":  "    let t = format(\"{}\", build(%d))\n"
                   "    print(length(t))\n" % DEEP_N,
    }
    return DEEP_RECORD + "fn main() uses io {\n" + ops[op] + "}\n"


def nested_blocks(kind: Any, depth: Any) -> str:
    """A function whose body nests `if`, `while`, or `else if` `depth`
    deep. Statement nesting is not capped the way expression nesting is."""
    if kind == "if":
        body = "        x = x + 1\n"
        for _ in range(depth):
            body = "    if x >= 0 {\n" + body + "    }\n"
        return ("fn f() -> Int {\n    let x = 0\n" + body
                + "    return x\n}\nfn main() uses io { print(f()) }\n")
    if kind == "while":
        body = "        x = x + 1\n"
        for _ in range(depth):
            body = "    while x < 0 {\n" + body + "    }\n"
        return ("fn f() -> Int {\n    let x = 0\n" + body
                + "    return x\n}\nfn main() uses io { print(f()) }\n")
    # else if chain
    parts = ["    if x == 0 { x = 1 }"]
    parts += ["    else if x == %d { x = %d }" % (i, i + 1)
              for i in range(1, depth)]
    parts += ["    else { x = 0 }"]
    return ("fn f() -> Int {\n    let x = 5\n" + "\n".join(parts)
            + "\n    return x\n}\nfn main() uses io { print(f()) }\n")


NEST = sabline.EXPR_NEST_LIMIT      # 1000; the parser stops past it (E102)
OVER = NEST + 20


def nested_expr(kind: Any) -> str:
    """An expression nested/chained just past the parser's limit."""
    if kind == "paren":
        return ("fn f() -> Int { return " + "(" * OVER + "1" + ")" * OVER
                + " }\nfn main() uses io { print(f()) }\n")
    if kind == "chain":
        return ("fn f(n: Int) -> Int { return " + " + ".join(["n"] * OVER)
                + " }\nfn main() uses io { print(f(1)) }\n")
    if kind == "calls":
        return ("fn g(n: Int) -> Int { return n + 1 }\n"
                "fn f() -> Int { return " + "g(" * OVER + "1" + ")" * OVER
                + " }\nfn main() uses io { print(f()) }\n")
    if kind == "list":
        t = "List of " * OVER + "Int"
        return ("fn main() uses io {\n    let x: " + t + " = "
                + "[" * OVER + "1" + "]" * OVER
                + "\n    print(length(x))\n}\n")
    if kind == "map":
        t = "Map of Text to " * OVER + "Int"
        return ("fn main() uses io {\n    let x: " + t + " = "
                + '{"a": ' * OVER + "1" + "}" * OVER
                + "\n    print(length(x))\n}\n")
    if kind == "record":
        return (DEEP_RECORD + "fn main() uses io {\n    let e: List of "
                "Node = []\n    let x = " + "Node(v: 1, kids: [" * OVER
                + "Node(v: 0, kids: e)" + "])" * OVER
                + "\n    print(x.v)\n}\n")
    raise KeyError(kind)


# ---------------------------------------------------------------------------
# 1. RecursionError in every path
# ---------------------------------------------------------------------------

def lsp_answers(source: Any, requests: Any) -> tuple[Any, ...]:
    """Drive the language server (as check_api does): open a document and
    ask each (id, method, extra-params). Returns (exit_code, saw_traceback,
    {name: 'answered'|'no answer'|'died'}). Positions point at line 0."""
    import json
    import queue
    import threading
    d = new_dir("lsp")
    path = write(d, source)
    p = str(path).replace("\\", "/")
    uri = "file://" + ("" if p.startswith("/") else "/") + p
    srv = subprocess.Popen([sys.executable, str(SABLINE), "lsp"],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, cwd=str(d))
    got: queue.Queue[Any] = queue.Queue()

    def reader() -> None:
        out = cast("IO[bytes]", srv.stdout)
        while True:
            length = None
            while True:
                line = out.readline()
                if not line:
                    got.put(None)
                    return
                line = line.strip()
                if not line:
                    break
                key, _, val = line.partition(b":")
                if key.lower() == b"content-length":
                    length = int(val)
            if length is None:
                got.put(None)
                return
            got.put(json.loads(out.read(length)))

    threading.Thread(target=reader, daemon=True).start()

    def send(m: Any) -> None:
        b = json.dumps(m).encode("utf-8")
        try:
            cast("IO[bytes]", srv.stdin).write(
                b"Content-Length: %d\r\n\r\n" % len(b) + b)
            cast("IO[bytes]", srv.stdin).flush()
        except OSError:
            pass

    def ask(n: Any, method: Any, params: Any) -> str:
        send({"jsonrpc": "2.0", "id": n, "method": method, "params": params})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                m = got.get(timeout=2)
            except queue.Empty:
                continue
            if m is None:
                return "died"
            if m.get("id") == n:
                return "answered"
        return "no answer"

    result = {}
    result["initialize"] = ask(1, "initialize", {"capabilities": {}})
    send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
          "params": {"textDocument": {"uri": uri, "languageId": "sabline",
                                      "version": 1, "text": source}}})
    at = {"textDocument": {"uri": uri}, "position": {"line": 0,
                                                     "character": 4}}
    for n, name, params in ((2, "hover", at),
                            (3, "codeLens", {"textDocument": {"uri": uri}})):
        result[name] = ask(n, "textDocument/" + name, params)
    send({"jsonrpc": "2.0", "id": 9, "method": "shutdown", "params": {}})
    send({"jsonrpc": "2.0", "method": "exit"})
    try:
        srv.wait(timeout=8)
    except subprocess.TimeoutExpired:
        srv.kill()
    noise = (cast("IO[bytes]", srv.stderr).read() or b"").decode("utf-8",
                                                                  "replace")
    return srv.returncode, "Traceback" in noise, result


# Each command, and what it must do on a program that does not compile.
# "e102": must name E102 and exit non-zero; "fail": non-zero exit, no code
# required (proofs summarises, not by code); "any": any exit (fmt reformats
# tokens without parsing; capabilities check wants a baseline first) - the
# one invariant everywhere is: no traceback.
WALK_COMMANDS = [
    ("check", ["check", "p.vel"], "e102"),
    ("audit", ["audit", "p.vel"], "e102"),
    ("explain", ["explain", "p.vel"], "e102"),
    ("proofs", ["proofs", "p.vel"], "fail"),
    ("audit --sarif", ["audit", "p.vel", "--sarif"], "e102"),
    ("fmt", ["fmt", "p.vel", "--check"], "any"),
    ("capabilities check", ["capabilities", "check", "."], "any"),
    ("run", ["p.vel", "--allow", "io"], "e102"),
    ("run --no-native", ["p.vel", "--allow", "io", "--no-native"], "e102"),
]


def _stage_verdict(mode: Any, code: Any, out: Any) -> tuple[Any, ...]:
    """(ok?, why) for one command's output under `mode`. Every mode
    requires no traceback."""
    if not clean(out):
        return False, "traceback"
    if mode == "e102":
        return ("E102" in out and code != 0), "code=%s %s" % (code, codes(out))
    if mode == "fail":
        return code != 0, "code=%s" % code
    return True, ""


def recursion_expr_cases() -> None:
    """A giant expression, past the parser's nest/chain limit, is a clean
    E102 through every command that walks it - not a traceback. The parser
    stops at the limit, so every stage fails identically at parse. One
    representative shape is run through all nine commands; each other shape
    through check, audit and a run."""
    print("1. RecursionError - expressions past the parser limit (E102)")
    d = new_dir("expr_chain")
    write(d, nested_expr("chain"))
    worst, traced = [], False
    for label, args, mode in WALK_COMMANDS:
        code, out, _ = run_cli(args, cwd=str(d), timeout=60)
        good, why = _stage_verdict(mode, code, out)
        if not good:
            worst.append("%s:%s" % (label, why))
            traced = traced or why == "traceback"
    ok("giant '+' chain -> no traceback through all nine commands",
       not worst, "; ".join(worst), finding=traced)
    for kind in ("paren", "calls", "list", "map", "record"):
        d = new_dir("expr_" + kind)
        write(d, nested_expr(kind))
        worst, traced = [], False
        for label, args, mode in (("check", ["check", "p.vel"], "e102"),
                                  ("audit", ["audit", "p.vel"], "e102"),
                                  ("run", ["p.vel", "--allow", "io"], "e102")):
            code, out, _ = run_cli(args, cwd=str(d), timeout=60)
            good, why = _stage_verdict(mode, code, out)
            if not good:
                worst.append("%s:%s" % (label, why))
                traced = traced or why == "traceback"
        ok("expr nest '%s' -> E102 on check/audit/run, no traceback" % kind,
           not worst, "; ".join(worst), finding=traced)


def recursion_runtime_cases() -> None:
    """A DEEP_N-deep runtime value, walked by print / == / to_text /
    json_of / format. Each walks the value in Python with no depth guard,
    so it overflows with a RecursionError traceback (the DEPTH_LIMIT guard
    counts Sabline call frames, not value traversal)."""
    print("1. RecursionError - a %d-deep runtime value" % DEEP_N)
    for op in ("print", "eq", "to_text", "json_of", "format"):
        d = new_dir("deepval_" + op)
        write(d, deep_value_prog(op))
        code, out, secs = run_cli(["p.vel", "--allow", "io"], cwd=str(d),
                                  timeout=60)
        traced = not clean(out)
        detail = ("traceback: %s" % out.strip().splitlines()[-1][:80]
                  if traced else "code=%s %s" % (code, codes(out)))
        # a coded error, or - where the Python underneath walks the value
        # without running out of stack, as 3.14 compares and encodes it - the
        # program's own answer; never a traceback and never a hang
        answered = code == 0 and bool(out.strip())
        ok("a %d-deep value, %s -> a coded error or the answer, no traceback"
           % (DEEP_N, op),
           clean(out) and code != -99 and (answered or (code != 0
                                                        and bool(codes(out)))),
           detail, finding=traced or code == -99)


def recursion_depth_cases() -> None:
    """Deep recursion (E609) and mutual recursion (E609), native and
    interpreted - these are handled: a coded stop, not a crash."""
    print("1. RecursionError - deep and mutual recursion (E609)")
    progs = {
        "runaway recursion":
            "fn rec(n: Int) -> Int { return rec(n + 1) }\n"
            "fn main() uses io { print(rec(0)) }\n",
        "mutual recursion":
            "fn even(n: Int) -> Bool {\n    if n == 0 { return true }\n"
            "    return odd(n - 1)\n}\n"
            "fn odd(n: Int) -> Bool {\n    if n == 0 { return false }\n"
            "    return even(n - 1)\n}\n"
            "fn main() uses io { print(even(100000)) }\n"}
    for name, src in progs.items():
        d = new_dir("rec")
        write(d, src)
        for mode, extra in (("native", []), ("--no-native", ["--no-native"])):
            code, out, secs = run_cli(["p.vel", "--allow", "io"] + extra,
                                      cwd=str(d), timeout=30)
            ok("%s (%s) -> E609, no traceback/hang" % (name, mode),
               "E609" in out and code == 1 and clean(out) and secs < 20,
               "code=%s %.1fs %s" % (code, secs, codes(out)),
               finding=not clean(out))


def recursion_blocks_cases() -> None:
    """Deeply nested if / while / else if blocks. Statement nesting has no
    E102 cap, so past a point the AST walk overflows Python's recursion
    limit. check and audit run under the ceiling and come back E000
    naming the RecursionError (no bare traceback); a plain run, and the
    library and the language server, hit the RecursionError directly."""
    print("1. RecursionError - deeply nested if / while / else if blocks")
    # a depth the walk survives: the intended clean path
    for kind in ("if", "while", "elseif"):
        d = new_dir("blk_ok_" + kind)
        write(d, nested_blocks(kind, 3000))
        code, out, _ = run_cli(["p.vel", "--allow", "io"], cwd=str(d),
                               timeout=90)
        ok("nested %s x3000 runs cleanly" % kind,
           code == 0 and clean(out), "code=%s %s" % (code, out[-80:]),
           finding=not clean(out))
    # a depth the walk does not survive. Statement nesting has no E102 cap,
    # so the tree parses and a later walk overflows Python's recursion
    # limit. Sweep every command that walks it; the invariant is no bare
    # traceback and a coded stop.
    DEEP = 12000
    d = new_dir("blk_deep_if")
    write(d, nested_blocks("if", DEEP))
    for label, args in (("check", ["check", "p.vel"]),
                        ("audit", ["audit", "p.vel"]),
                        ("explain", ["explain", "p.vel"]),
                        ("proofs", ["proofs", "p.vel"]),
                        ("audit --sarif", ["audit", "p.vel", "--sarif"]),
                        ("fmt", ["fmt", "p.vel", "--check"]),
                        ("capabilities init", ["capabilities", "init", "."]),
                        ("run", ["p.vel", "--allow", "io"]),
                        ("run --no-native",
                         ["p.vel", "--allow", "io", "--no-native"])):
        code, out, _ = run_cli(args, cwd=str(d), timeout=90)
        last = out.strip().splitlines()[-1][:70] if out.strip() else ""
        ok("nested if x%d, %s -> no traceback" % (DEEP, label),
           clean(out), "code=%s %s :: %s" % (code, codes(out), last),
           finding=not clean(out))
    # the long else-if chain overflows the same way, on a run
    d2 = new_dir("blk_deep_elseif")
    write(d2, nested_blocks("elseif", DEEP))
    code, out, _ = run_cli(["p.vel", "--allow", "io"], cwd=str(d2), timeout=60)
    ok("else-if chain x%d, run -> no traceback" % DEEP, clean(out),
       "code=%s %s :: %s" % (code, codes(out),
                             out.strip().splitlines()[-1][:70]
                             if out.strip() else ""),
       finding=not clean(out))
    # the library, in this process, has no ceiling child to absorb it
    d = new_dir("blk_lib")
    src = nested_blocks("if", DEEP)
    try:
        c = sabline.check(src, timeout=None, max_memory_mb=None)
        raised = None
        libclean = True
    except BaseException as e:      # noqa: BLE001 - a crash is the finding
        raised = type(e).__name__
        libclean = raised == "SablineError"
    ok("nested if x%d, sabline.check(timeout=None) -> SablineError, "
       "not a Python exception" % DEEP, libclean,
       "raised %s" % raised if raised else "returned ok=%s"
       % getattr(c, "ok", "?"), finding=not libclean)
    # the language server
    lsp_code, lsp_traced, lsp_res = lsp_answers(nested_blocks("if", DEEP),
                                                None)
    ok("nested if x%d, the language server survives hover/codeLens" % DEEP,
       not lsp_traced and lsp_res.get("hover") == "answered"
       and lsp_res.get("codeLens") == "answered",
       "traceback=%s answers=%s" % (lsp_traced, lsp_res),
       finding=lsp_traced or "died" in lsp_res.values())
    # the language server on a giant EXPRESSION (E102) stays clean: null
    # hover, empty lenses, no traceback
    _, e_traced, e_res = lsp_answers(nested_expr("paren"), None)
    ok("giant expression, the language server answers without a traceback",
       not e_traced and e_res.get("hover") == "answered"
       and e_res.get("codeLens") == "answered",
       "traceback=%s answers=%s" % (e_traced, e_res), finding=e_traced)


# ---------------------------------------------------------------------------
# 2. File descriptors
# ---------------------------------------------------------------------------

FD_HANDLES = (
    "fn main() uses io, ffi, fs {\n"
    "    let i = 0\n"
    "    let opened = 0\n"
    "    let refused = 0\n"
    "    while i < %d {\n"
    "        check py_new(\"tempfile\", \"TemporaryFile\", \"[]\") {\n"
    "            ok h { opened = opened + 1 }\n"
    "            fail w { refused = refused + 1 }\n"
    "        }\n"
    "        i = i + 1\n"
    "    }\n"
    "    print(format(\"opened {} refused {}\", opened, refused))\n"
    "}\n")

FD_RW = (
    "fn main() uses io, fs {\n"
    "    let i = 0\n"
    "    let n = 0\n"
    "    while i < %d {\n"
    "        write_file(\"%s/rw.txt\", to_text(i))\n"
    "        check read_file(\"%s/rw.txt\") {\n"
    "            ok t { n = n + 1 }\n"
    "            fail w { n = n }\n"
    "        }\n"
    "        i = i + 1\n"
    "    }\n"
    "    print(n)\n"
    "}\n")


def fd_cases() -> None:
    print("2. File descriptors")
    # unclosed py_new handles, opened in a loop, never closed
    d = new_dir("fd_handles")
    write(d, FD_HANDLES % 12000)
    code, out, secs = run_cli(["p.vel", "--allow", "io,ffi,fs"], cwd=str(d),
                              timeout=90)
    ok("12000 unclosed py_new handles -> caught as failures, exit 0, "
       "no traceback",
       code == 0 and clean(out) and "opened" in out,
       "code=%s %.1fs %s" % (code, secs, out.strip()[-70:]),
       finding=not clean(out))
    # read_file / write_file in a loop
    d2 = new_dir("fd_rw")
    dm = str(d2).replace("\\", "/")
    write(d2, FD_RW % (3000, dm, dm))
    code, out, secs = run_cli(
        ["p.vel", "--allow", "io,fs:read:%s,fs:write:%s" % (dm, dm)],
        cwd=str(d2), timeout=90)
    ok("3000x write_file+read_file in a loop -> exit 0, no traceback",
       code == 0 and clean(out) and out.strip().endswith("3000"),
       "code=%s %.1fs %s" % (code, secs, out.strip()[-40:]),
       finding=not clean(out))
    # POSIX: the same under a low RLIMIT_NOFILE, set in a preexec_fn
    if os.name != "posix":
        skip("low RLIMIT_NOFILE for the handle loop", "POSIX only")
        skip("low RLIMIT_NOFILE for the read/write loop", "POSIX only")
        return
    import resource

    def cap() -> None:
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))

    d3 = new_dir("fd_nofile")
    write(d3, FD_HANDLES % 300)
    code, out, secs = run_cli(["p.vel", "--allow", "io,ffi,fs"], cwd=str(d3),
                              timeout=60, preexec=cap)
    ok("handle loop under RLIMIT_NOFILE=32 -> caught, exit 0, no traceback",
       code == 0 and clean(out) and "opened" in out,
       "code=%s %s" % (code, out.strip()[-70:]), finding=not clean(out))
    dm3 = str(d3).replace("\\", "/")
    write(d3, FD_RW % (500, dm3, dm3), name="rw.vel")
    code, out, secs = run_cli(
        ["rw.vel", "--allow", "io,fs:read:%s,fs:write:%s" % (dm3, dm3)],
        cwd=str(d3), timeout=60, preexec=cap)
    ok("read/write loop under RLIMIT_NOFILE=32 -> exit 0, no traceback",
       code == 0 and clean(out), "code=%s %s" % (code, out.strip()[-40:]),
       finding=not clean(out))


# ---------------------------------------------------------------------------
# 3. Disk
# ---------------------------------------------------------------------------

def disk_cases() -> None:
    print("3. Disk")
    # write_file in a loop under a count: stops at N with E315, <= N files
    d = new_dir("disk_count")
    out_dir = Path(d) / "out"
    out_dir.mkdir()
    om = str(out_dir).replace("\\", "/")
    src = ("fn main() uses io, fs {\n    let i = 0\n"
           "    while i < 50 {\n"
           "        write_file(format(\"%s/f{}.txt\", i), \"x\")\n"
           "        i = i + 1\n    }\n    print(\"done\")\n}\n" % om)
    write(d, src)
    code, out, _ = run_cli(["p.vel", "--allow", "io,fs:write:%s@5" % om],
                           cwd=str(d), timeout=60)
    made = len(list(out_dir.glob("*.txt")))
    ok("write_file loop under fs:write@5 -> E315, at most 5 files",
       "E315" in out and code != 0 and clean(out) and made <= 5,
       "code=%s files=%d %s" % (code, made, codes(out)),
       finding=not clean(out))
    # write to a directory, a read-only file, a path that cannot exist
    target = Path(d) / "adir"
    target.mkdir()
    ro = Path(d) / "ro.txt"
    ro.write_text("x", encoding="utf-8")
    try:
        os.chmod(ro, 0o444)
        if os.name == "nt":
            subprocess.run(["attrib", "+r", str(ro)], capture_output=True)
    except OSError:
        pass
    grant = "io,fs:write:%s" % str(d).replace("\\", "/")
    bad = {"a directory": str(target).replace("\\", "/"),
           "a read-only file": str(ro).replace("\\", "/"),
           "a path that cannot exist":
               str(Path(d) / "no" / "such" / "x.txt").replace("\\", "/")}
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0:
        # root ignores file permission bits, so a "read-only" file is
        # writable and the case would not test what it means to
        del bad["a read-only file"]
        skip("write_file to a read-only file", "running as root")
    for name, path in bad.items():
        write(d, "fn main() uses io, fs {\n    write_file(\"%s\", \"x\")\n"
                 "    print(\"wrote\")\n}\n" % path, name="w.vel")
        code, out, _ = run_cli(["w.vel", "--allow", grant], cwd=str(d),
                               timeout=30)
        ok("write_file to %s -> coded failure, no traceback" % name,
           code != 0 and clean(out) and bool(codes(out)),
           "code=%s %s :: %s" % (code, codes(out),
                                 out.strip().splitlines()[-1][:70]
                                 if out.strip() else ""),
           finding=not clean(out))
    try:
        if os.name == "nt":
            subprocess.run(["attrib", "-r", str(ro)], capture_output=True)
        os.chmod(ro, 0o644)
    except OSError:
        pass
    # a path with an embedded NUL: cannot exist, must not reach open()/stat().
    # write_file stops the run with E608, as a write that cannot happen does;
    # read_file is fallible, so its failure reaches the program's fail arm,
    # as a file that is not there does (8.2)
    dm = str(d).replace("\\", "/")
    for name, src, want in (
            ("write_file",
             "fn main() uses io, fs {\n    write_file(\"%s/a\\u0000b\", "
             "\"x\")\n    print(\"wrote\")\n}\n", "E608"),
            ("read_file",
             "fn main() uses io, fs {\n"
             "    check read_file(\"%s/a\\u0000b\") {\n"
             "        ok t { print(t) }\n        fail w { print(\"f\") }\n"
             "    }\n}\n", "a failure the program handles")):
        # NUL is not a Sabline escape, so place the byte in the source here
        text = (src % dm).replace("\\u0000", chr(0))
        write(d, text, name="nul.vel")
        code, out, _ = run_cli(
            ["nul.vel", "--allow", "io,fs:read:%s,fs:write:%s" % (dm, dm)],
            cwd=str(d), timeout=30)
        good = (code != 0 and want in codes(out)) if want.startswith("E") \
            else (code == 0 and out.strip().splitlines()[-1:] == ["f"])
        ok("%s with an embedded NUL in the path -> %s, no traceback"
           % (name, want), clean(out) and good,
           "code=%s %s :: %s" % (code, codes(out),
                                 out.strip().splitlines()[-1][:80]
                                 if out.strip() else ""),
           finding=not clean(out))


# ---------------------------------------------------------------------------
# 4. A multi-GB read
# ---------------------------------------------------------------------------

def big_read_cases() -> None:
    print("4. A 3 GB sparse file, read under the default ceiling (E316)")
    d = new_dir("bigread")
    big = Path(d) / "huge.bin"
    size = 3 * 1024 ** 3
    try:
        with open(big, "wb") as fh:
            if os.name == "nt":
                import ctypes
                import msvcrt
                from ctypes import wintypes
                h = msvcrt.get_osfhandle(fh.fileno())  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
                ret = wintypes.DWORD()
                ctypes.windll.kernel32.DeviceIoControl(  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
                    wintypes.HANDLE(h), 0x000900C4, None, 0, None, 0,
                    ctypes.byref(ret), None)     # FSCTL_SET_SPARSE
            fh.seek(size - 1)
            fh.write(b"\0")
        real = big.stat().st_size
    except OSError as e:
        skip("3 GB sparse read (E316)", "cannot make a sparse file: %s" % e)
        return
    if real < size:
        skip("3 GB sparse read (E316)", "sparse file is only %d bytes" % real)
        big.unlink(missing_ok=True)
        return
    dm = str(d).replace("\\", "/")
    write(d, "fn main() uses io, fs {\n"
             "    check read_file(\"%s/huge.bin\") {\n"
             "        ok t { print(length(t)) }\n"
             "        fail w { print(\"f\") }\n    }\n}\n" % dm)
    code, out, secs = run_cli(["p.vel", "--allow", "io,fs:read:%s" % dm],
                              cwd=str(d), timeout=30)
    ok("read_file on a 3 GB file -> E316, fast (< 10s), not read into memory",
       "E316" in out and code != 0 and clean(out) and secs < 10,
       "code=%s %.1fs %s" % (code, secs, codes(out)),
       finding=not clean(out))
    big.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 5. Windows paths over 260 characters
# ---------------------------------------------------------------------------

def long_path_cases() -> None:
    print("5. Windows paths over 260 characters")
    if os.name != "nt":
        skip("paths over 260 characters", "Windows only")
        return
    base = Path(WORK) / "lp"
    d = base
    i = 0
    while len(str(d)) < 300:
        d = d / ("a_rather_long_directory_name_%02d" % i)
        i += 1
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        skip("paths over 260 characters", "cannot create the directory: %s"
             % e)
        return
    fp = str(d).replace("\\", "/")
    p = write(d, "fn main() uses io {\n    print(\"hi\")\n}\n")
    ok("the program's path is over 260 characters",
       len(str(p)) > 260, "len=%d" % len(str(p)))
    for label, args in (("check", ["check", str(p)]),
                        ("audit", ["audit", str(p)]),
                        ("run", [str(p), "--allow", "io"]),
                        ("run --no-native",
                         [str(p), "--no-native", "--allow", "io"])):
        code, out, _ = run_cli(args, timeout=60)
        ok("a >260-char path, %s -> no traceback" % label,
           clean(out) and code in (0, 1), "code=%s %s" % (code, out[-70:]),
           finding=not clean(out))
    # read and write a file there under an fs grant
    rw = write(d, "fn main() uses io, fs {\n"
                  "    write_file(\"%s/data.txt\", \"hello\")\n"
                  "    check read_file(\"%s/data.txt\") {\n"
                  "        ok t { print(t) }\n"
                  "        fail w { print(\"f: \" + w) }\n    }\n}\n"
                  % (fp, fp), name="rw.vel")
    code, out, _ = run_cli([str(rw), "--allow",
                            "io,fs:read:%s,fs:write:%s" % (fp, fp)],
                           timeout=60)
    ok("read+write a file at a >260-char path -> exit 0, no traceback",
       code == 0 and clean(out) and "hello" in out,
       "code=%s %s" % (code, out.strip()[-60:]), finding=not clean(out))


# ---------------------------------------------------------------------------
# 6. cp1252 consoles
# ---------------------------------------------------------------------------

CP = {"PYTHONIOENCODING": "cp1252"}
NONASCII = "café 日本 \U0001f600"   # accents, CJK, emoji


def cp1252_cases() -> None:
    print("6. cp1252 consoles (PYTHONIOENCODING=cp1252)")
    d = new_dir("cp")
    # a program that prints non-ASCII text
    write(d, "fn main() uses io {\n    print(\"%s\")\n}\n" % NONASCII)
    code, out, _ = run_cli(["p.vel", "--allow", "io"], cwd=str(d), env=CP,
                           timeout=30)
    ok("a program printing non-ASCII text -> no UnicodeEncodeError traceback",
       clean(out), "code=%s %s" % (code, out.strip().splitlines()[-1][:80]
                                   if out.strip() else ""),
       finding=not clean(out))
    # check on a file whose error message quotes non-ASCII source
    write(d, "fn main() uses io {\n    let %s = 1\n}\n" % "日", name="e.vel")
    code, out, _ = run_cli(["check", "e.vel"], cwd=str(d), env=CP, timeout=30)
    ok("check quoting non-ASCII source -> no traceback",
       clean(out) and bool(codes(out)), "code=%s %s" % (code, codes(out)),
       finding=not clean(out))
    # audit, explain, --help, stats --ffi on a directory of such files
    good = new_dir("cp_dir")
    write(good, "fn main() uses io {\n    print(\"ok\")\n}\n",
          name="café_日本.vel")
    for label, args in (("audit", ["audit", "café_日本.vel"]),
                        ("explain .", ["explain", "."]),
                        ("audit . --sarif", ["audit", ".", "--sarif"]),
                        ("--help", ["--help"]),
                        ("stats --ffi", ["stats", "--ffi", "."])):
        code, out, _ = run_cli(args, cwd=str(good), env=CP, timeout=60)
        ok("cp1252: %s over non-ASCII file names -> no traceback" % label,
           clean(out), "code=%s %s" % (code, out.strip().splitlines()[-1][:70]
                                       if out.strip() else ""),
           finding=not clean(out))


# ---------------------------------------------------------------------------
# 7. A 10,000-line file
# ---------------------------------------------------------------------------

def big_file_cases() -> None:
    print("7. A valid 10,000-line program")
    lines = ["// a generated 10,000-line program", ""]
    i = 0
    while len(lines) < 7000:
        if i % 3 == 0:                     # a function with a contract
            lines += ["fn f%d(n: Int) -> Int" % i,
                      "    requires n >= 0",
                      "    ensures result >= n",
                      "{",
                      "    if n > 1000000 { return n }",
                      "    return n + %d" % (i % 5),
                      "}", ""]
        else:
            lines += ["fn f%d(n: Int) -> Int {" % i,
                      "    let x = n * 2",
                      "    return x - n + %d" % (i % 7),
                      "}", ""]
        i += 1
    nfuncs = i
    lines += ["fn main() uses io {", "    let total = 0"]
    k = 0
    while len(lines) < 9998:
        lines.append("    total = f%d(%d) %% 1000" % (k % nfuncs, k % 40))
        k += 1
    lines += ["    print(total)", "}"]
    text = "\n".join(lines) + "\n"
    d = new_dir("big10k")
    write(d, text)
    n = text.count("\n")
    ok("generated a %d-line program (%d functions)" % (n, nfuncs + 1),
       n >= 10000 or len(lines) >= 10000, "lines=%d" % n)
    # A check or an audit has a ceiling of its own - 60 seconds
    # (CHECK_TIMEOUT_DEFAULT) - and a program this size can reach it on a
    # slow machine, where the answer is E613 and exit 2. That is the
    # designed answer and not a crash, so it passes here: what this case
    # holds is that a big valid program never ends in a traceback, a hang
    # or an uncoded exit. 8.7.0 found this on the macos-15-intel leg, where
    # the check took 60.4s against a ceiling of 60 and the suite called the
    # refusal a failure; audit took 59.7s on the same machine and passed,
    # which is how narrow it was. `fmt` and `run` have no such ceiling.
    CEILING = ("E613", "E614")            # the time and memory ceilings

    def held(code: Any, out: Any, may_hit_the_ceiling: bool) -> bool:
        if code in (0, 1):
            return True
        return (may_hit_the_ceiling and code == 2
                and any("error[%s]" % c in out for c in CEILING))

    for label, args, limit, ceiling in (
            ("check", ["check", "p.vel"], 180, True),
            ("audit", ["audit", "p.vel"], 180, True),
            ("fmt --check", ["fmt", "p.vel", "--check"], 60, False),
            ("run", ["p.vel", "--allow", "io"], 180, False)):
        code, out, secs = run_cli(args, cwd=str(d), timeout=limit)
        ok("10,000-line program, %s in %.1fs -> no traceback, and it "
           "finished or was stopped by its own ceiling" % (label, secs),
           clean(out) and held(code, out, ceiling) and secs < limit,
           "code=%s %.1fs %s" % (code, secs, out.strip().splitlines()[-1][:60]
                                 if out.strip() else ""),
           finding=not clean(out))
    # ...and the ceiling branch above, pinned: forced to fire, rather than
    # waited for on a machine slow enough. Without this the branch is only
    # ever taken on the runner that made this case fail, so it would rot.
    code, out, secs = run_cli(["check", "p.vel", "--check-timeout", "1"],
                              cwd=str(d), timeout=120)
    ok("...and a check stopped at its ceiling is E613, exit 2, no traceback "
       "- which the case above accepts",
       clean(out) and code == 2 and "error[E613]" in out
       and held(code, out, True),
       "code=%s %.1fs %s" % (code, secs, out.strip().splitlines()[-1][:60]
                             if out.strip() else ""))
    ok("...and that same answer is not accepted where there is no ceiling "
       "to reach", not held(2, out, False), "exit 2 with E613 was allowed "
       "for fmt or run")


# ---------------------------------------------------------------------------
# 8. A function with 500 parameters, and a call with 500 arguments
# ---------------------------------------------------------------------------

def wide_function_cases() -> None:
    print("8. A function with 500 parameters, called with 500 arguments")
    n = 500
    params = ", ".join("a%d: Int" % i for i in range(n))
    args = ", ".join(str(i % 5) for i in range(n))
    # a provable contract, so check is a clean success, and a short body,
    # so the interpreter is instant
    src = ("fn wide(%s) -> Int\n"
           "    requires a0 >= 0\n"
           "    ensures result >= 0\n"
           "{\n    return a0\n}\n\n"
           "fn main() uses io {\n    print(wide(%s))\n}\n" % (params, args))
    d = new_dir("wide")
    write(d, src)
    code, out, secs = run_cli(["check", "p.vel"], cwd=str(d), timeout=90)
    note = "" if HAVE_Z3 else " (no z3)"
    ok("500-parameter function, check%s -> exit 0, no traceback" % note,
       code == 0 and clean(out) and secs < 60,
       "code=%s %.1fs %s" % (code, secs, out.strip()[-60:]),
       finding=not clean(out))
    code, out, secs = run_cli(["audit", "p.vel"], cwd=str(d), timeout=90)
    ok("500-parameter function, audit -> exit 0, no traceback",
       code == 0 and clean(out) and secs < 60,
       "code=%s %.1fs" % (code, secs), finding=not clean(out))
    # a run with the interpreter: instant and correct
    code, out, secs = run_cli(["p.vel", "--no-native", "--allow", "io"],
                              cwd=str(d), timeout=60)
    ok("500-argument call, run --no-native -> exit 0, no traceback",
       code == 0 and clean(out) and secs < 30,
       "code=%s %.1fs %s" % (code, secs, out.strip()[-30:]),
       finding=not clean(out))
    # a run with native codegen on: LLVM codegen for a many-parameter
    # function is very slow. Bounded here; a timeout is the finding.
    NATIVE_LIMIT = 45
    code, out, secs = run_cli(["p.vel", "--allow", "io"], cwd=str(d),
                              timeout=NATIVE_LIMIT)
    ok("500-argument call, run with native code -> finishes cleanly "
       "(< %ds)" % NATIVE_LIMIT,
       code == 0 and clean(out) and code != -99,
       "code=%s %.1fs %s" % (code, secs,
                             "[did not finish]" if code == -99
                             else out.strip()[-20:]),
       finding=(code == -99 or not clean(out)))


# ---------------------------------------------------------------------------
# 1b. Native codegen of a modest arithmetic chain
# ---------------------------------------------------------------------------

def native_chain_cases() -> None:
    """A pure Int function whose body is a chain of a few dozen additions -
    far below the parser's E102 nesting cap, so it reaches native codegen.
    LLVM codegen for it is exponential in the chain length (10 terms ~1.6s,
    15 ~31s, 20+ does not finish), so `--no-native` is instant while native
    hangs. Bounded here; a timeout is the finding."""
    print("1b. Native codegen of a modest arithmetic chain")
    depth = 24
    src = ("fn f(n: Int) -> Int { return " + " + ".join(["n"] * depth)
           + " }\nfn main() uses io { print(f(1)) }\n")
    d = new_dir("native_chain")
    write(d, src)
    code, out, secs = run_cli(["p.vel", "--no-native", "--allow", "io"],
                              cwd=str(d), timeout=30)
    ok("a %d-term '+' chain, run --no-native -> exit 0, no traceback"
       % depth,
       code == 0 and clean(out) and out.strip().endswith(str(depth)),
       "code=%s %.1fs %s" % (code, secs, out.strip()[-20:]),
       finding=not clean(out))
    LIMIT = 30
    code, out, secs = run_cli(["p.vel", "--allow", "io"], cwd=str(d),
                              timeout=LIMIT)
    ok("a %d-term '+' chain, run with native code -> finishes cleanly "
       "(< %ds)" % (depth, LIMIT),
       code == 0 and clean(out) and code != -99,
       "code=%s %.1fs %s" % (code, secs,
                             "[did not finish - native codegen hangs]"
                             if code == -99 else out.strip()[-20:]),
       finding=(code == -99 or not clean(out)))


# ---------------------------------------------------------------------------
# 1c. A counterexample that cannot name a value
# ---------------------------------------------------------------------------

# fuzz_parsers.py found this on 8.2.0 (its fixed seeds 493132804 and
# 769080785), as generated. caller passes f0 put(...) of a map, which the
# prover does not translate, and f0 requires false: E701 is decided, and
# printing the counterexample then asked Z3 to evaluate nothing. check,
# proofs, audit and the library each ended in an AttributeError traceback.
# From 8.2.1 the value is shown as <unknown>.
UNNAMED_VALUE = (
    "record Pt {\n"
    "    x: Int\n"
    "    y: Int\n"
    "}\n"
    "\n"
    "fn is_pos(n: Int) -> Bool {\n"
    "    return n > 0\n"
    "}\n"
    "\n"
    "fn abs_of(n: Int) -> Int\n"
    "    ensures result >= 0\n"
    "{\n"
    "    if n < 0 {\n"
    "        return 0 - n\n"
    "    }\n"
    "    return n\n"
    "}\n"
    "\n"
    "fn f0(p0: Map of Text to Int)\n"
    "    requires false\n"
    "    requires (all_of([0, 2], is_pos) or not contains(\"\\n\", \"\u00e9\"))\n"
    "    ensures contains(\"\u00e9\", (to_text(9223372036854775807) + "
    "get([\"a\"], 9223372036854775807)))\n"
    "{\n"
    "    let i = 0\n"
    "    while i < (get([1, 2, 3], units_of(money(100, \"INR\"))) % -100)\n"
    "        invariant i >= 0\n"
    "    {\n"
    "        i = i + 1\n"
    "    }\n"
    "}\n"
    "\n"
    "fn caller(a: Int, t: Text, xs: List of Int) -> Int\n"
    "    requires all_of(push([a, a], code_at(t, a)), is_pos)\n"
    "{\n"
    "    f0(put({\"a\": 1, \"b\": 2}, t, units_of(money(1, \"INR\"))))\n"
    "    return 0\n"
    "}\n")


def counterexample_cases() -> None:
    print("1c. A counterexample that cannot name a value")
    d = new_dir("unnamed_value")
    write(d, UNNAMED_VALUE)
    code, out, secs = run_cli(["check", "p.vel"], cwd=str(d))
    if HAVE_Z3:
        ok("check -> E701, the value it cannot name shown as <unknown>, "
           "no traceback",
           code == 1 and clean(out) and codes(out) == ["E701"]
           and "'caller' can call it with p0 = <unknown>" in out,
           "code=%s %s" % (code, out.strip()[-160:]), finding=not clean(out))
    else:
        ok("check, no prover -> no traceback", clean(out) and code in (0, 1),
           "code=%s %s" % (code, out.strip()[-160:]), finding=not clean(out))
    # what is reported proven: abs_of, and neither function of the call
    code, out, secs = run_cli(["proofs", "p.vel", "--detail"], cwd=str(d))
    marks = re.findall(r"\[(proven |runtime|timeout)\] (\w+)", out)
    proven = sorted(name for mark, name in marks if mark == "proven ")
    ok("proofs -> no traceback; f0 and caller are not reported proven",
       clean(out) and ("runtime", "caller") in marks
       and proven == (["abs_of"] if HAVE_Z3 else []),
       "code=%s marks=%s %s" % (code, marks, out.strip()[-120:]),
       finding=not clean(out))
    code, out, secs = run_cli(["audit", "p.vel"], cwd=str(d))
    ok("audit -> no traceback%s" % (", and the E701" if HAVE_Z3 else ""),
       clean(out) and (("E701" in out and code == 1) if HAVE_Z3 else True),
       "code=%s %s" % (code, out.strip()[-160:]), finding=not clean(out))
    try:
        result = sabline.check(UNNAMED_VALUE, path=str(d / "p.vel"),
                               timeout=None, max_memory_mb=None)
        got = [(p.code, p.line) for p in result.problems]
        said = " ".join(p.message for p in result.problems)
        raised = ""
    except Exception as e:                  # the defect: reported, not raised
        got, said, raised = [], "", "%s: %s" % (type(e).__name__, e)
    ok("sabline.check() -> %s, no exception"
       % ("E701 at line 35, p0 = <unknown>" if HAVE_Z3 else "no E701"),
       not raised and ((got == [("E701", 35)] and "p0 = <unknown>" in said)
                       if HAVE_Z3 else ("E701", 35) not in got),
       raised or "%s %s" % (got, said[:120]), finding=bool(raised))


# ---------------------------------------------------------------------------

def main() -> Any:
    t0 = time.perf_counter()
    print("=" * 70)
    print("check_hostile: hostile resource use must end in a coded error")
    print("Python %d.%d.%d on %s, prover %s" % (
        sys.version_info[0], sys.version_info[1], sys.version_info[2],
        os.name, "yes" if HAVE_Z3 else "no"))
    print("=" * 70)
    recursion_expr_cases()
    recursion_runtime_cases()
    recursion_depth_cases()
    recursion_blocks_cases()
    native_chain_cases()
    counterexample_cases()
    fd_cases()
    disk_cases()
    big_read_cases()
    long_path_cases()
    cp1252_cases()
    big_file_cases()
    wide_function_cases()
    secs = time.perf_counter() - t0
    print("=" * 70)
    print("%d passed, %d failed, %d skipped in %.0fs"
          % (PASS, FAIL, SKIP, secs))
    if FINDINGS:
        print("\n%d FINDING(S) - a traceback or silent death reached the "
              "user (fix in the compiler):" % len(FINDINGS))
        for label, detail in FINDINGS:
            print("  - %s" % label)
            if detail:
                print("      %s" % detail[:140])
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
