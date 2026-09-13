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
the same on the full and minimal CI legs; the cache cases that depend on
the prover say so and adapt when z3 is absent (the cache is never even
consulted without it).

    python check_adversarial.py
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = str(HERE / "velaris.py")
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

PASS = 0
FAIL = 0


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        FAIL += 1
        print(f"FAIL  {label}   {detail}")


def run(args, cwd=None, env=None, stdin=None, timeout=60):
    """Run velaris; return (exit_code, combined_output, seconds)."""
    import time
    e = dict(os.environ)
    if env:
        e.update(env)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, VELARIS] + args,
                           capture_output=True, text=True, cwd=cwd, env=e,
                           input=stdin, timeout=timeout)
        return r.returncode, r.stdout + r.stderr, time.perf_counter() - t0
    except subprocess.TimeoutExpired as ex:
        return -99, (ex.stdout or "") + (ex.stderr or "") + \
            f"\n[TIMEOUT {timeout}s]", time.perf_counter() - t0


def prog(d, text, name="p.vel"):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return name


# A per-user cache under a temp dir, so no case touches the real one and
# CI stays clean. Both env names cover Windows and POSIX.
def _cache_env():
    ch = tempfile.mkdtemp(prefix="veladvcache_")
    return {"LOCALAPPDATA": ch, "XDG_CACHE_HOME": ch}, ch


# ---------------------------------------------------------------------------
# HOLE #1 (target 5): a poisoned project-local .velaris/proofs.json must be
# ignored, so a false `ensures` is never reported or enforced as proven.
# ---------------------------------------------------------------------------
FALSE = ("fn double(n: Int) -> Int\n"
         "  ensures result == n + n\n"
         "{ return n + 1000000 }\n"
         "fn main() uses io { print(to_text(double(5))) }\n")


def poison_local(d):
    """Write the exact ./.velaris/proofs.json the pass used, with the real
    proof_key, claiming the false `double` is proven."""
    funcs, records = velaris.load_program(os.path.join(d, "p.vel"))
    table = {f.name: f for f in funcs}
    keys = [velaris.proof_key(f, table, records) for f in funcs if f.ensures]
    os.makedirs(os.path.join(d, ".velaris"), exist_ok=True)
    with open(os.path.join(d, ".velaris", "proofs.json"), "w") as f:
        json.dump({k: {"proven": True, "errors": []} for k in keys}, f)


def cache_cases():
    env, _ = _cache_env()
    d = tempfile.mkdtemp()
    prog(d, FALSE)
    poison_local(d)
    # RUN must never accept the false promise, prover or not: E700 (proved
    # false before running) with z3, E601 (runtime promise check) without.
    # The refusal message may quote the offending value; what must never
    # happen is a clean exit 0 having produced it as output.
    for mode, label in (([], "native"), (["--no-native"], "--no-native")):
        code, out, _ = run(["p.vel", "--allow", "io"] + mode, cwd=d, env=env)
        ok(f"CACHE-1 poisoned run {label} refused (E700/E601, not exit 0)",
           code != 0 and ("E700" in out or "E601" in out), out[:160])
    if HAVE_Z3:
        for cmd in ("check", "proofs", "audit", "explain"):
            code, out, _ = run([cmd, "p.vel"], cwd=d, env=env)
            refused = code != 0 and "1000005" not in out
            ok(f"CACHE-1 poisoned {cmd} refused (z3)", refused, out[:160])
        code, out, _ = run(["check", "p.vel"], cwd=d, env=env)
        ok("CACHE-1 poisoned check reports E700 (z3)", "E700" in out, out[:160])
    # audit notes the ignored project-local cache, for a program that compiles
    dv = tempfile.mkdtemp()
    prog(dv, "fn add1(n: Int) -> Int ensures result == n + 1 "
             "{ return n + 1 }\nfn main() uses io { print(to_text(add1(1))) }\n")
    os.makedirs(os.path.join(dv, ".velaris"))
    open(os.path.join(dv, ".velaris", "proofs.json"), "w").write("{}")
    code, out, _ = run(["audit", "p.vel"], cwd=dv, env=env)
    ok("CACHE-1 audit notes 'ignored: ./.velaris/'",
       "ignored: ./.velaris" in out, out[:160])

    # the per-user cache is written and bound to the source; a tampered
    # header is rejected, so a hand-edited entry is re-proved not trusted.
    # (Only the prover writes a proof cache; without z3 there is none.)
    if HAVE_Z3:
        env2, ch2 = _cache_env()
        d2 = tempfile.mkdtemp()
        prog(d2, "fn f(x: Int) -> Int requires x > 0 ensures result > x "
                 "{ return x + 1 }\nfn main() uses io { print(to_text(f(1))) }\n")
        run(["check", "p.vel"], cwd=d2, env=env2)
        files = glob.glob(os.path.join(ch2, "velaris", "proofs", "*.json"))
        ok("CACHE-2 per-user cache written outside the program directory",
           len(files) == 1
           and not os.path.isdir(os.path.join(d2, ".velaris")), str(files))
        if files:
            doc = json.load(open(files[0]))
            good = (doc.get("version") == velaris.VERSION
                    and isinstance(doc.get("proofs"), dict)
                    and doc.get("content_sha256"))
            ok("CACHE-2 cache entry is bound to path+version+content", good,
               str(doc)[:120])
            # corrupt the content hash: the entry must be rejected and
            # re-proved, and the result must still be correct
            doc["content_sha256"] = "0" * 64
            json.dump(doc, open(files[0], "w"))
            code, out, _ = run(["check", "p.vel"], cwd=d2, env=env2)
            ok("CACHE-2 tampered cache header is rejected (still checks ok)",
               code == 0, out[:160])


# ---------------------------------------------------------------------------
# #3 (target 6): non-terminating recursion reaches E609 in BOTH modes, fast,
# on every platform - native codegen no longer hides the depth guard.
# ---------------------------------------------------------------------------
def recursion_cases():
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
def compiler_limits_cases():
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


def secret_cases():
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
def _read_prog(pathexpr):
    return ('fn main() uses fs, io {\n'
            f'  check read_file({pathexpr}) {{ ok v {{ print("LEAK:" + v) }} '
            'fail w { print("fail") } }\n}\n')


def sandbox_cases():
    base = tempfile.mkdtemp()
    allowed = os.path.join(base, "allowed")
    os.makedirs(allowed)
    open(os.path.join(base, "secret.txt"), "w").write("TOPSECRET")
    grant = "fs:read:" + allowed + ",io"

    def vq(s):
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


def ffi_cases():
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
def self_influence_cases():
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
# Target 1 - `velaris trace` prints <secret>, never the plaintext.
# ---------------------------------------------------------------------------
def trace_cases():
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
def witness_cases():
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
def pool_cases():
    pool = velaris.Pool(allow={"io"}, timeout=10)
    try:
        a = pool.run('fn main() uses io { print("A:" + to_text(length(args()))) }\n',
                     args=["LEAKED"])
        b = pool.run('fn main() uses io { print("B:" + to_text(length(args()))) }\n')
        ok("POOL args do not leak from run A to run B",
           a.ok and b.ok and "A:1" in a.output and "B:0" in b.output,
           f"{a.output!r} {b.output!r}")
    finally:
        pool.close()


def main():
    cache_cases()
    recursion_cases()
    compiler_limits_cases()
    secret_cases()
    sandbox_cases()
    ffi_cases()
    self_influence_cases()
    trace_cases()
    witness_cases()
    pool_cases()
    print(f"\n{PASS}/{PASS + FAIL} passed" + (f"  ({FAIL} FAILED)" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
