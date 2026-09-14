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
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = str(HERE / "velaris.py")
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_adversarial")   # and its own proof cache

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


def run(args, cwd=None, env=None, stdin=None, timeout=60, unset=()):
    """Run velaris; return (exit_code, combined_output, seconds). `unset`
    names variables the child does not inherit."""
    import time
    e = dict(os.environ)
    if env:
        e.update(env)
    for name in unset:
        e.pop(name, None)
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
    ch = tempfile.mkdtemp(prefix="veladvcache_", dir=WORK)
    # VELARIS_CACHE_DIR (8.1) wins over the other two, and the suite sets it
    # for everything it starts, so the case names its own
    return {"LOCALAPPDATA": ch, "XDG_CACHE_HOME": ch,
            "VELARIS_CACHE_DIR": ch}, ch


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
# 8.1.1: the per-user cache cannot lie either. Two outside assessments of
# 8.0.0 planted a per-user entry - the real proof_key, the cache moved with
# XDG_CACHE_HOME (LOCALAPPDATA on Windows) - and a false ensures was
# reported proven by check, proofs and audit and, compiled to native code,
# ran unchecked (advisory-proof-cache-2.md). Nothing in the cache is
# believed now. The file planted below is one this loader accepts, so the
# refusals show the design, not a file rejected for its shape.
# ---------------------------------------------------------------------------
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

_CACHE_VARS = ("VELARIS_CACHE_DIR", "XDG_CACHE_HOME", "LOCALAPPDATA")


class _redirected:
    """In this process, the environment the outside pass ran velaris in: no
    VELARIS_CACHE_DIR, and the per-user cache moved under `base`."""

    def __init__(self, base):
        self.base = base

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in _CACHE_VARS}
        os.environ.pop("VELARIS_CACHE_DIR", None)
        os.environ["XDG_CACHE_HOME"] = self.base
        os.environ["LOCALAPPDATA"] = self.base

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def plant_user_cache(d, base, fn_name):
    """The outside pass's plant: the per-user cache file velaris reads for
    d/p.vel with the cache moved under `base`, its header naming the file's
    real path, bytes and version, and one entry under the real proof_key of
    `fn_name` claiming it proven. Returns (that file, what this velaris's
    loader reads from it)."""
    path = os.path.join(d, "p.vel")
    with _redirected(base):
        funcs, records = velaris.load_program(path)
        table = {f.name: f for f in funcs}
        key = velaris.proof_key(table[fn_name], table, records)
        ref = velaris._proof_cache_ref(path, None)
        cache_file, ap, ch = ref
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"schema": "velaris.proofcache/1", "path": ap,
                       "version": velaris.VERSION, "content_sha256": ch,
                       "proofs": {key: {"proven": True, "errors": []}}}, f)
        if os.name == "posix":
            os.chmod(cache_file, 0o600)
        return cache_file, velaris._cache_load(ref)


def _says_proven(out):
    """Whether check, proofs --sarif, audit or explain output calls one
    promise proven."""
    return any(s in out for s in ("1 with proven", "[proven", '"proven": 1'))


def user_cache_cases():
    base = os.path.realpath(tempfile.mkdtemp(prefix="redirect_", dir=WORK))
    moved = {"XDG_CACHE_HOME": base, "LOCALAPPDATA": base}
    unset = ("VELARIS_CACHE_DIR",)

    # CACHE-3: the exact reproduction, under every command that reports a
    # promise and both ways of running
    d = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d, FALSE)
    planted, loaded = plant_user_cache(d, base, "double")
    ok("CACHE-3 the plant is a file this loader accepts - what follows is "
       "the design refusing it, not a file rejected", len(loaded) == 1,
       str(loaded))
    for label, args in (("check", ["check", "p.vel"]),
                        ("proofs", ["proofs", "p.vel", "--sarif"]),
                        ("audit", ["audit", "p.vel"]),
                        ("explain", ["explain", "p.vel"]),
                        ("run", ["p.vel", "--allow", "io"]),
                        ("run --no-native",
                         ["p.vel", "--allow", "io", "--no-native"])):
        code, out, _ = run(args, cwd=d, env=moved, unset=unset)
        if HAVE_Z3:
            said = '"ruleId": "E700"' if label == "proofs" else "E700"
            ok(f"CACHE-3 a planted per-user entry for a false ensures, "
               f"{label}: E700 (z3)",
               code != 0 and said in out and "1000005" not in out,
               out[:200])
        elif label.startswith("run"):
            ok(f"CACHE-3 a planted per-user entry for a false ensures, "
               f"{label}: E601 (no z3)", code != 0 and "E601" in out,
               out[:200])
        else:
            ok(f"CACHE-3 a planted per-user entry for a false ensures, "
               f"{label}: not proven (no z3)",
               code == 0 and not _says_proven(out), out[:200])
    if HAVE_Z3:
        doc = json.load(open(planted, encoding="utf-8"))
        entry = next(iter(doc.get("proofs", {}).values()), {})
        ok("CACHE-3 ...and those runs read that very file: they wrote it back "
           "with the time of their own proof", "seconds" in entry,
           str(doc)[:160])

    # CACHE-4: the strongest plant - a lie no prover refutes, which only the
    # runtime check can catch, so a believed entry was the whole defence
    d2 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d2, LOOP_LIE)
    _, loaded2 = plant_user_cache(d2, base, "count")
    path2 = os.path.join(d2, "p.vel")
    with _redirected(base):
        funcs, records = velaris.load_program(path2)
        proven, errs = set(), []
        velaris.check_proofs(funcs, records, errs, proven, use_cache=True,
                             source_path=path2)
    ok("CACHE-4 a planted entry for a lie no prover refutes is read, and "
       "check_proofs neither calls it proven nor makes native code of it",
       len(loaded2) == 1 and "count" not in proven
       and "count" not in velaris.native_eligible(funcs, proven),
       f"{loaded2} {proven}")
    for label, args in (("run", ["p.vel", "--allow", "io"]),
                        ("run --no-native",
                         ["p.vel", "--allow", "io", "--no-native"])):
        code, out, _ = run(args, cwd=d2, env=moved, unset=unset)
        ok(f"CACHE-4 ...{label} stops at the runtime check (E601) rather "
           f"than print 5 and exit 0", code != 0 and "E601" in out,
           out[:200])
    for label in ("check", "audit"):
        code, out, _ = run([label, "p.vel"], cwd=d2, env=moved, unset=unset)
        ok(f"CACHE-4 ...{label} does not report it proven",
           code == 0 and not _says_proven(out), out[:200])

    # CACHE-5: an honest entry costs nothing in what it reports
    if HAVE_Z3:
        env5, ch5 = _cache_env()
        d5 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
        prog(d5, TRUE)
        first = run(["check", "p.vel"], cwd=d5, env=env5)
        second = run(["check", "p.vel"], cwd=d5, env=env5)
        ok("CACHE-5 a true promise is proven by the second check as by the "
           "first, its entry proved again rather than believed",
           first[0] == 0 and second[0] == 0 and "1 with proven" in first[1]
           and "1 with proven" in second[1], second[1][:160])
        files = glob.glob(os.path.join(ch5, "velaris", "proofs", "*.json"))
        if files:
            blob = open(files[0], "rb").read()
            open(files[0], "wb").write(blob[:len(blob) // 2])
            code, out, _ = run(["check", "p.vel"], cwd=d5, env=env5)
            try:
                whole = isinstance(
                    json.load(open(files[0], encoding="utf-8")), dict)
            except ValueError:
                whole = False
            ok("CACHE-6 a torn cache file on disk: the check proves as with "
               "none, and the file is written whole again",
               code == 0 and "1 with proven" in out and whole, out[:160])
            if os.name == "posix":
                import stat
                modes = [stat.S_IMODE(os.stat(p).st_mode) for p in (
                    os.path.join(ch5, "velaris"),
                    os.path.join(ch5, "velaris", "proofs"), files[0])]
                ok("CACHE-7 the cache directories are made 0700 and a cache "
                   "file 0600 (POSIX)", modes == [0o700, 0o700, 0o600],
                   str([oct(m) for m in modes]))

    # CACHE-6: a torn file, or one a save would not write, is rejected whole
    d6 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
    prog(d6, TRUE)
    path6 = os.path.join(d6, "p.vel")
    with _redirected(base):
        ref6 = velaris._proof_cache_ref(path6, None)
    cache_file, ap, ch = ref6
    good = {"schema": velaris.PROOF_CACHE_SCHEMA, "path": ap,
            "version": velaris.VERSION, "content_sha256": ch,
            "proofs": {"a" * 64: {"proven": False, "errors": [],
                                  "seconds": 0.5}}}
    raw = json.dumps(good).encode("utf-8")

    def with_entry(entry, key="a" * 64):
        return json.dumps(dict(good, proofs={key: entry})).encode("utf-8")

    ok("CACHE-6 a whole file with this source's header is read",
       velaris._cache_document(raw, ap, ch) is not None)
    for label, blob in (
            ("cut in half", raw[:len(raw) // 2]),
            ("bytes that are not UTF-8", b"\xff\xfe" + raw),
            ("another schema", json.dumps(
                dict(good, schema="velaris.proofcache/0")).encode("utf-8")),
            ("another path's header", json.dumps(
                dict(good, path=ap + "x")).encode("utf-8")),
            ("a key that is not a sha256", with_entry({"proven": True},
                                                      key="double")),
            ("an entry that is not an object", with_entry([True])),
            ("seconds NaN", with_entry({"seconds": float("nan")})),
            ("seconds infinite", with_entry({"seconds": float("inf")})),
            ("seconds negative", with_entry({"seconds": -1})),
            ("seconds past a day", with_entry({"seconds": 1e308})),
            ("seconds true", with_entry({"seconds": True})),
            ("seconds as text", with_entry({"seconds": "1"}))):
        ok(f"CACHE-6 a cache file with {label} is rejected whole",
           velaris._cache_document(blob, ap, ch) is None)

    # CACHE-7: foreign files and directories (POSIX: ownership and modes;
    # links anywhere they can be made without privileges)
    if os.name == "posix":
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "wb") as f:
            f.write(raw)
        os.chmod(cache_file, 0o600)
        ok("CACHE-7 a file of this user's that no one else may write is read "
           "(POSIX)", velaris._cache_load(ref6) != {})
        os.chmod(cache_file, 0o666)
        ok("CACHE-7 a cache file another user may write is foreign and "
           "rejected (POSIX)", velaris._cache_load(ref6) == {})
        os.chmod(cache_file, 0o600)
        real = os.path.join(WORK, f"real-{os.getpid()}.json")
        os.replace(cache_file, real)
        os.symlink(real, cache_file)
        ok("CACHE-7 a cache file that is a link is foreign and rejected "
           "(POSIX)", velaris._cache_load(ref6) == {})
        os.unlink(cache_file)
        os.replace(real, cache_file)
        proofs_dir = os.path.dirname(cache_file)
        os.rename(proofs_dir, proofs_dir + "-real")
        os.symlink(proofs_dir + "-real", proofs_dir)
        ok("CACHE-7 a cache directory that is a link is foreign and rejected "
           "(POSIX)", velaris._cache_load(ref6) == {})
        os.unlink(proofs_dir)
        os.rename(proofs_dir + "-real", proofs_dir)

    # CACHE-8: a relative XDG_CACHE_HOME or LOCALAPPDATA would have put the
    # cache in the directory velaris runs in - the program's
    if HAVE_Z3:
        d8 = os.path.realpath(tempfile.mkdtemp(dir=WORK))
        home = os.path.realpath(tempfile.mkdtemp(prefix="home_", dir=WORK))
        prog(d8, TRUE)
        code, out, _ = run(["check", "p.vel"], cwd=d8,
                           env={"XDG_CACHE_HOME": ".", "LOCALAPPDATA": ".",
                                "HOME": home, "USERPROFILE": home},
                           unset=unset)
        ok("CACHE-8 a relative XDG_CACHE_HOME or LOCALAPPDATA is ignored: no "
           "cache under the program's directory",
           code == 0 and not os.path.exists(os.path.join(d8, "velaris")),
           out[:160])

    # CACHE-9: the library and the language server never read it
    text = LOOP_LIE
    with _redirected(base):
        c = velaris.check(text, path=path2, timeout=None, max_memory_mb=None)
        where = path2.replace(os.sep, "/")
        uri = "file://" + ("" if where.startswith("/") else "/") + where
        lenses = velaris.editor_answer("textDocument/codeLens", {}, text, uri)
    ok("CACHE-9 the library does not report the planted lie proven",
       "count" not in c.proven, str(c.proven))
    titles = [lens["command"]["title"] for lens in lenses or []]
    ok("CACHE-9 the language server's lens does not call it proven",
       bool(titles) and not any("proven" in t for t in titles), str(titles))

    # CACHE-10: the Action proves nothing with the cache
    action = (HERE / "action.yml").read_text(encoding="utf-8")
    proving = [ln.strip() for ln in action.splitlines()
               if re.search(r"\bvelaris (check|proofs|review|audit)\b", ln)
               and not ln.strip().startswith(("#", "description:"))]
    ok("CACHE-10 every command in the Action that proves passes --no-cache",
       bool(proving) and all("--no-cache" in ln for ln in proving),
       str(proving))


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


# ---------------------------------------------------------------------------
# The 8.0 breaks, kept closed. Each is an attempt from the 8.0 adversarial
# pass that must stay refused (or, for the honest halves, stay allowed).
# ---------------------------------------------------------------------------
def _listener():
    """A one-shot socket that records the request it receives. Stands in
    for an un-granted proxy: nothing granted may reach it."""
    import socket
    import threading
    got = {}
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
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


def proxy_break_cases():
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


def builtin_shadow_cases():
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


def credential_break_cases():
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


def add_redirect_cases():
    """Break 4: velaris add refuses a redirect from https to http and to a
    host outside the URL's origin. Tested against the opener's own
    redirect handler, so it needs no TLS server."""
    class _Resp:
        headers = {}

        def geturl(self):
            return ""

    def outcome(origin, newurl):
        import urllib.request
        op = velaris._add_opener(origin)
        handler = next(h for h in op.handlers
                       if h.__class__.__name__ == "AddGuard")
        try:
            handler.redirect_request(urllib.request.Request(origin), _Resp(),
                                     302, "Found", {}, newurl)
            return "allowed"
        except velaris._RedirectRefused as e:
            return f"refused: {e.why}"

    ok("B4 velaris add refuses an https->http redirect",
       "refused" in outcome("https://example.com/lib.vel",
                            "http://example.com/lib.vel"))
    ok("B4 velaris add refuses a redirect to a host outside the origin",
       "refused" in outcome("https://example.com/lib.vel",
                            "https://evil.com/lib.vel"))
    ok("B4 velaris add allows a same-origin https redirect",
       outcome("https://example.com/a.vel", "https://example.com/b.vel")
       == "allowed")


# ---------------------------------------------------------------------------
# The 8.1 pass, kept closed: the prover's names, imports, receipts, eject,
# and the door's rate limit. Each is an attempt from that pass.
# ---------------------------------------------------------------------------
def prover_name_cases():
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
    c = velaris.check(lie, timeout=None, max_memory_mb=None)
    ok("P1 ...and check does not report f proven", "f" not in c.proven,
       str(c.proven))
    boxed = ("record Box { xs: List of Int  xs__n: Int }\n"
             "fn f(b: Box) -> Int\n  requires b.xs__n == 5\n"
             "  ensures result == 5\n{ return length(b.xs) }\n"
             "fn main() uses io { print(to_text(f(Box(xs: [1], xs__n: 5)))) }\n")
    c = velaris.check(boxed, timeout=None, max_memory_mb=None)
    ok("P2 a record field named xs__n is not the length of xs",
       "f" not in c.proven, str(c.proven))


def import_read_cases():
    """I1/I2: an import of a file that is not Velaris source quoted what it
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
            "check": velaris.check(src, timeout=None,
                                   max_memory_mb=None).problems,
            "audit": velaris.audit(src, timeout=None,
                                   max_memory_mb=None).problems,
            "run": velaris.run(src, allow={"io"}).problems}
        for how, problems in said.items():
            text = " ".join(p.message for p in problems)
            ok(f"I1 {how} of a program importing {name} names the file and "
               f"not what it holds", problems and token not in text,
               text[:160])
    root = tempfile.mkdtemp(dir=WORK)
    present = (f'import "{os.path.join(d, "notes.txt").replace(os.sep, "/")}"'
               f'\nfn main() uses io {{ print("x") }}\n')
    missing = present.replace("notes.txt", "no-such-file.txt")
    got = [velaris.check(s, import_root=root).problems
           for s in (present, missing)]
    ok("I2 with import_root, an import outside it is E515 whether or not the "
       "file exists - so nothing about it is told",
       [[p.code for p in g] for g in got] == [["E515"], ["E515"]],
       [[(p.code, p.message[:60]) for p in g] for g in got])


def receipt_leak_cases():
    """R1-R5: a secret value into a receipt - declassified and printed, into
    a refused host and a refused path, before a kill, and a forged receipt
    file written by the program itself."""
    key = "RK" + os.urandom(6).hex()
    os.environ["ADV_RECEIPT_KEY"] = key

    def leaks(doc):
        return key.lower() in json.dumps(doc).lower()

    pre = 'fn main() uses io, env, declassify'
    printed = velaris.run(
        pre + ' {\n    print(declassify(env("ADV_RECEIPT_KEY", ""), "shown"))\n}\n',
        allow={"io", "env", "declassify"})
    ok("R1 a declassified secret the program printed is not in its receipt",
       key in printed.output and not leaks(printed.receipt))
    host = velaris.run(
        pre + ', net {\n'
        '    let h = declassify(env("ADV_RECEIPT_KEY", ""), "a host")\n'
        '    check fetch("https://" + h + ".example.org/") {\n'
        '        ok b { print("x") }\n        fail w { print("no") }\n    }\n}\n',
        allow={"io", "env", "declassify", "net:api.example.com"})
    ok("R2 a refused host built from the secret: E314 in the receipt, the "
       "host not", host.refused_effect and not leaks(host.receipt)
       and host.receipt["predicate"]["refusals"][0]["code"] == "E314",
       str(host.receipt["predicate"]["refusals"]))
    path = velaris.run(
        pre + ', fs {\n'
        '    let p = declassify(env("ADV_RECEIPT_KEY", ""), "a path")\n'
        '    write_file(p + ".txt", "x")\n}\n',
        allow={"io", "env", "declassify",
               f"fs:write:{tempfile.mkdtemp(dir=WORK)}"})
    ok("R3 a refused path built from the secret: E313 in the receipt, the "
       "path not", path.refused_effect and not leaks(path.receipt)
       and path.receipt["predicate"]["refusals"][0]["code"] == "E313",
       str(path.receipt["predicate"]["refusals"]))
    killed = velaris.run(
        pre + ' {\n'
        '    let k = declassify(env("ADV_RECEIPT_KEY", ""), "before the kill")\n'
        '    let i = 0\n    while i >= 0 {\n        i = i + 1\n'
        '        if i > 1000000 { i = 0 }\n    }\n    print(k)\n}\n',
        allow={"io", "env", "declassify"}, timeout=2)
    ok("R4 a run killed by the clock keeps the declassification it made, and "
       "not the value", killed.timed_out and not leaks(killed.receipt)
       and killed.receipt["predicate"]["declassifications"][0]["reason"]
       == "before the kill", str(killed.receipt["predicate"])[:200])
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
       and doc.get("predicateType") == velaris.RECEIPT_PREDICATE_TYPE,
       f"{code} {str(doc)[:120]}")


def eject_widening_cases():
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
    runtime = os.path.join(target, "runtime", "velaris.py")
    original = open(runtime, "rb").read()
    open(runtime, "wb").write(original.replace(
        b"def spend(", b"def _spend_was(", 1)
        + b"\ndef spend(effect, what, line):\n    return None\n")
    done = subprocess.run([sys.executable, "-I", launcher, "--changed-ok"],
                          capture_output=True, text=True, cwd=d, timeout=120)
    open(runtime, "wb").write(original)
    ok("E2 a runtime with its budget check removed is never run, "
       "--changed-ok or not", done.returncode == 2
       and "runtime/velaris.py" in done.stderr, done.stderr[-160:])
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
    open(os.path.join(drop, "velaris.py"), "w").write(
        f"open(r'{marker}', 'w').write('shadowed')\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env["PYTHONPATH"] = drop
    done = subprocess.run([sys.executable, launcher], capture_output=True,
                          text=True, cwd=drop, env=env, timeout=120)
    ok("E6 a velaris.py planted on PYTHONPATH, or in the working directory, "
       "is not the runtime the launcher runs",
       done.returncode == 0 and "hello" in done.stdout
       and not os.path.exists(marker), done.stderr[-160:])


def door_rate_cases():
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
    door = subprocess.Popen([sys.executable, VELARIS, "serve", "--port",
                             str(port), "--rate-limit", "4"],
                            env=dict(os.environ, VELARIS_TOKEN=token),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    def status(headers):
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


def main():
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
