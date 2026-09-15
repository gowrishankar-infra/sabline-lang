#!/usr/bin/env python3
"""A program cannot budget itself (8.2, item 14).

Nothing a program or its surroundings control may change what it is allowed
to do, or what its audit says. Five fixed programs - one reads a file under
a directory, one fetches a listener on 127.0.0.1 and then a refused host, one
calls Python through a named module, one prints (its arguments among other
things), one carries a promise and imports the standard library - are
audited and run under fixed budgets: through the command line, through the
library in this process and in a child process, and on a pool. That is the
baseline. Then one thing is varied at a time, and the audit's capability
fields (effects, fs_paths, net_hosts, ffi_modules, ffi_any, safe_command,
secrets, counts, ffi_native, each function's effects, the problems' codes)
and each run's end (exit status, refusal code, refused effect, output) are
held to it:

  A  the working directory
  B  args(): words after the program that look like Velaris flags
  C  the environment: every variable velaris/*.py reads by name, PYTHONPATH
     naming a planted velaris.py, and what the standard library reads on
     Velaris's behalf (the proxy variables, TEMP, HOME)
  D  velaris.toml, in the program's directory and in the working directory
  E  a tampered velaris.lock
  F  a library replaced with velaris add --force
  G  hidden directories: imports, and the directory scans
  H  a planted velaris.capabilities and .velaris/ beside the program

Where a variation should change nothing, that is the assertion. Where it is
meant to matter, a comment says why and the case asserts what it does. A
variation that changes what a program may do, or what its audit says, is a
finding: its case is kept, failing.

Nothing here reaches the internet: the one host fetched is a listener on
127.0.0.1, and every other host named is refused by the budget before a name
is looked up, or never called. No theorem prover is needed; with one the
promise is proven, and nothing compared depends on that.

    python check_self_budget.py
"""
import atexit
import concurrent.futures
import hashlib
import http.server
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, cast

T0 = time.perf_counter()
HERE = Path(__file__).resolve().parent
VELARIS = str(HERE / "velaris.py")
sys.path.insert(0, str(HERE))


def _scrub(env: Any) -> Any:
    """The environment without what this suite varies: Velaris's own
    variables, the proxy variables, and what points Python at other code."""
    out = {}
    for k, v in env.items():
        u = k.upper()
        if u.startswith("VELARIS_") or u.endswith("_PROXY") or u in (
                "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP",
                "SOURCE_DATE_EPOCH"):
            continue
        out[k] = v
    return out


for _name in [k for k in os.environ if k not in _scrub({k: ""})]:
    os.environ.pop(_name, None)

import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = Path(os.path.realpath(isolate("check_self_budget")))
BASE_ENV = dict(os.environ)
BASE_ENV["PYTHONIOENCODING"] = "utf-8"

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

PASS = 0
FAIL = 0
SKIP = 0


def _ascii(text: Any) -> Any:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def ok(label: Any, cond: Any, detail: object = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {_ascii(label)}")
    else:
        FAIL += 1
        print(f"FAIL  {_ascii(label)}   {_ascii(detail)[:1200]}")
    sys.stdout.flush()


def skip(label: Any, why: Any) -> None:
    global SKIP
    SKIP += 1
    print(f"SKIP  {_ascii(label)}   ({_ascii(why)})")
    sys.stdout.flush()


def section(title: Any) -> None:
    print(f"\n{title}\n" + "-" * 62)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# What is compared. The same two functions run here and in the probe (a
# child process that uses the library under a varied cwd or environment).
# ---------------------------------------------------------------------------
_SHARED = r'''
CAP_FIELDS = ("ok", "effects", "fs_paths", "net_hosts", "ffi_modules",
              "ffi_any", "safe_command", "secrets", "counts", "ffi_native")


def caps(doc):
    """What a velaris.audit/1 document says a program can touch: its
    capability fields, each function's effects, the problems' codes."""
    out = {k: doc.get(k) for k in CAP_FIELDS}
    out["functions"] = sorted([f["name"], sorted(f["effects"])]
                              for f in (doc.get("functions") or []))
    out["problems"] = sorted((p.get("code") or "")
                             for p in (doc.get("problems") or []))
    return json.loads(json.dumps(out, sort_keys=True))


def lib_outcome(r):
    """How a RunResult ended: exit status, refusal code, refused effect,
    output."""
    return [r.exit_code, r.problems[0].code if r.problems else None,
            r.refused_effect, (r.output or "").replace("\r\n", "\n")]
'''
_shared: dict[str, Any] = {"json": json}
exec(_SHARED, _shared)
caps = _shared["caps"]
lib_outcome = _shared["lib_outcome"]

PROBE = r'''
import json
import os
import sys

spec = json.load(open(sys.argv[1], encoding="utf-8"))
sys.path.insert(0, spec["here"])
import velaris
''' + _SHARED + r'''

out = {"in_child": bool(velaris.state._IN_CHILD), "programs": {}}
for name, path, allow in spec["programs"]:
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    doc = velaris.audit(src, path=path, timeout=None,
                        max_memory_mb=None).as_dict()
    run = velaris.run(src, path=path, allow=set(allow.split(",")))
    out["programs"][name] = {"lib_audit": caps(doc),
                             "lib_run": lib_outcome(run)}
if spec.get("pool"):
    with velaris.Pool(size=1, timeout=300) as pool:
        for name, path, allow in spec["programs"]:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            out["programs"][name]["pool_audit"] = caps(
                pool.audit(src, path=path).as_dict())
with open(spec["out"], "w", encoding="utf-8") as fh:
    json.dump(out, fh)
'''

PATHLESS = r'''
import json
import sys

spec = json.load(open(sys.argv[1], encoding="utf-8"))
sys.path.insert(0, spec["here"])
import tempfile
import velaris
''' + _SHARED + r'''

src = spec["source"]
out = {"tempdir": tempfile.gettempdir(),
       "audit": caps(velaris.audit(src, timeout=None,
                                   max_memory_mb=None).as_dict()),
       "pool_audit": caps(velaris.audit(src).as_dict()),
       "run": lib_outcome(velaris.run(src, allow={"io"})),
       "bounded_run": lib_outcome(velaris.run(src, allow={"io"},
                                              timeout=300))}
with open(spec["out"], "w", encoding="utf-8") as fh:
    json.dump(out, fh)
'''

_seq = itertools.count(1)


def sh(args: Any, cwd: Any, env: Any = None, timeout: int = 300) -> tuple[Any, ...]:
    """Run a command: (exit status, stdout, stderr), line ends made \\n."""
    try:
        r = subprocess.run([str(a) for a in args], cwd=str(cwd),
                           env=BASE_ENV if env is None else env,
                           capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return (r.returncode, r.stdout.replace("\r\n", "\n"),
                r.stderr.replace("\r\n", "\n"))
    except subprocess.TimeoutExpired:
        return -99, "", f"[timed out after {timeout}s]"


def vel(args: Any, cwd: Any, env: Any = None, timeout: int = 300) -> Any:
    """python velaris.py <args>, the command line from a checkout."""
    return sh([sys.executable, VELARIS] + list(args), cwd, env, timeout)


def parallel(jobs: Any) -> dict[Any, Any]:
    """{key: (function, arg, ...)} run at once; {key: its result}."""
    workers = max(1, min(8, len(jobs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {k: ex.submit(fn, *a) for k, (fn, *a) in jobs.items()}
    return {k: f.result() for k, f in futures.items()}


_ERROR = re.compile(r"error\[(E\d{3})\]\s*(.*)")


def cli_outcome(result: Any) -> list[Any]:
    """How a command-line run ended, in lib_outcome's shape: the refused
    effect is read from the refusal's message as run() reads it."""
    code, out, err = result
    m = _ERROR.search(err)
    if not m:
        return [code, None, None, out]
    return [code, m.group(1), velaris._refused_from(m.group(1), m.group(2)),
            out]


def fwd(p: Any) -> Any:
    return str(p).replace(os.sep, "/")


def write(path: Any, text: Any) -> Any:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def sha(data: Any) -> Any:
    return hashlib.sha256(data).hexdigest()


def files_under(root: Any) -> Any:
    """{relative path: bytes} of every file under root."""
    out = {}
    for dp, _, names in os.walk(root):
        for name in names:
            p = os.path.join(dp, name)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


def _delta(got: Any, want: Any) -> str:
    if not isinstance(got, dict) or not isinstance(want, dict):
        return f"{got!r} != {want!r}"
    return ", ".join(f"{k}: {got.get(k)!r} != {want.get(k)!r}"
                     for k in sorted(set(got) | set(want))
                     if got.get(k) != want.get(k))


# ---------------------------------------------------------------------------
# A listener on 127.0.0.1 - the one host a program is granted - and another
# standing in for a proxy nobody granted, which must hear nothing.
# ---------------------------------------------------------------------------
class _Answer(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        cast(Any, self.server).seen.append(f"{self.command} {self.path}")
        body = b"hi"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET
    do_CONNECT = do_GET

    def log_message(self, *args: Any) -> None:
        pass


def listener() -> tuple[Any, ...]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Answer)
    srv.daemon_threads = True
    cast(Any, srv).seen = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


SERVER, PORT = listener()
PROXY, PROXY_PORT = listener()

# ---------------------------------------------------------------------------
# The fixed programs, their fixed budgets, and what the baseline must be.
# ---------------------------------------------------------------------------
DATA = WORK / "data"
OUTSIDE = WORK / "outside"
PROG = WORK / "prog"
PLANTED = WORK / "planted"
PROBE_FILE = WORK / "probe" / "probe.py"
PATHLESS_FILE = WORK / "probe" / "pathless.py"
UNRELATED = Path(os.path.realpath(tempfile.mkdtemp(
    prefix="velaris-sb-elsewhere-")))
atexit.register(shutil.rmtree, UNRELATED, ignore_errors=True)

SOURCES = {
    "read": (
        'fn main() uses io, fs {\n'
        '    check read_file("{DATA}/a.txt") {\n'
        '        ok t { print("read: " + t) }\n'
        '        fail w { print("read failed") }\n'
        '    }\n'
        '    check read_file("{OUTSIDE}/b.txt") {\n'
        '        ok t { print("LEAK: " + t) }\n'
        '        fail w { print("outside failed") }\n'
        '    }\n'
        '}\n'),
    "net": (
        'fn main() uses io, net {\n'
        '    check fetch("http://127.0.0.1:{PORT}/granted") {\n'
        '        ok b { print("got: " + b) }\n'
        '        fail w { print("fetch failed") }\n'
        '    }\n'
        '    check fetch("http://refused.example.invalid/x") {\n'
        '        ok b { print("LEAK: " + b) }\n'
        '        fail w { print("refused failed") }\n'
        '    }\n'
        '}\n'),
    "ffi": (
        'fn main() uses io, ffi {\n'
        '    check py_json("json", "loads", "[\\"[1, 2]\\"]") {\n'
        '        ok v { print("json: " + v) }\n'
        '        fail w { print("json failed") }\n'
        '    }\n'
        '    let none: List of Text = []\n'
        '    check py("os", "getcwd", none) {\n'
        '        ok v { print("LEAK: " + v) }\n'
        '        fail w { print("os failed") }\n'
        '    }\n'
        '}\n'),
    "print": (
        'fn main() uses io, env, declassify {\n'
        '    print("hello")\n'
        '    print(format("args: {}", args()))\n'
        '    let key = env("SELF_BUDGET_KEY", "")\n'
        '    let unset = declassify(key == "",\n'
        '        "whether a key is set is not the key")\n'
        '    if unset {\n'
        '        print("no key")\n'
        '    } else {\n'
        '        print("a key")\n'
        '    }\n'
        '}\n'),
    "promise": (
        'import "std.vel"\n'
        '\n'
        'fn twice(n: Int) -> Int\n'
        '    requires n >= 0\n'
        '    ensures result == n + n\n'
        '{\n'
        '    return n * 2\n'
        '}\n'
        '\n'
        'fn main() uses io {\n'
        '    print(format("twice: {}, first: {}", twice(21),\n'
        '        first([7, 8, 9])))\n'
        '}\n'),
}
NAMES = list(SOURCES)


def fill(text: Any) -> Any:
    return (text.replace("{DATA}", fwd(DATA))
            .replace("{OUTSIDE}", fwd(OUTSIDE))
            .replace("{PORT}", str(PORT)))


BUDGETS = {"read": fill("io,fs:read:{DATA}"),
           "net": fill("io,net:127.0.0.1:{PORT}"),
           "ffi": "io,ffi:json", "print": "io", "promise": "io"}

EXPECT_RUN = {
    "read": [1, "E313", "fs:" + fwd(OUTSIDE) + "/b.txt", "read: alpha\n"],
    "net": [1, "E314", "net:refused.example.invalid", "got: hi\n"],
    "ffi": [1, "E311", "ffi:os", "json: [1, 2]\n"],
    "print": [1, "E310", "env", "hello\nargs: []\n"],
    "promise": [0, None, None, "twice: 42, first: 7\n"],
}

BASE_CAPS: dict[str, dict[str, Any]] = {}
BASE_RUN: dict[str, list[Any]] = {}
BASE_PARAMS = {}

# A standard library someone else wrote: `first` answers the last item, and
# an uncalled function names a host, so the audit shows whether it was read.
PLANTED_STD = (
    'fn first(xs: List of T) -> T for any T\n'
    '    requires length(xs) > 0\n'
    '{\n'
    '    return get(xs, length(xs) - 1)\n'
    '}\n'
    '\n'
    'fn beacon() uses net {\n'
    '    check fetch("http://planted.example.invalid/std") {\n'
    '        ok b { }\n'
    '        fail w { }\n'
    '    }\n'
    '}\n')

TOML = (
    '# planted: a wider budget, another entry, other keys\n'
    '[package]\n'
    'name = "planted"\n'
    'entry = "evil.vel"\n'
    'allow = "all"\n'
    '\n'
    '[budget]\n'
    'allow = ["io", "env", "fs", "net", "clock", "rand", "ffi", '
    '"declassify"]\n'
    'max_read = 99999\n'
    'deny = []\n'
    '\n'
    '[run]\n'
    'args = ["--allow", "all"]\n'
    'cwd = "/"\n'
    '\n'
    '[dependencies]\n'
    'geo = { source = "https://planted.example.invalid/geo.vel", sha256 = "'
    + "0" * 64 + '" }\n')

EVIL = ('fn main() uses io, env, fs, net, ffi {\n'
        '    print("the planted entry ran")\n'
        '}\n')

PLANTED_LOCK = json.dumps({
    "lockfile": "velaris.lock/1",
    "libraries": [{"name": "std", "file": "std.vel", "sha256": "0" * 64,
                   "source": "https://planted.example.invalid/std.vel",
                   "added_by": "99.0", "effects": ["io", "env", "fs", "net",
                                                   "ffi", "declassify"],
                   "capabilities": {"safe_command":
                                    "velaris <file> --allow all"}}]},
    indent=2)

PLANTED_CAPABILITIES = json.dumps({
    "schema": "velaris.capabilities/1", "velaris_version": "99.0",
    "date": "2026-01-01",
    "surface": {"grants": ["clock", "declassify", "env", "ffi", "fs", "io",
                           "net", "rand"],
                "counts": {"fs": None, "net": None}},
    "programs": [{"file": n + ".vel", "grants": ["ffi", "fs", "net"],
                  "counts": {"fs": None, "net": None},
                  "functions": {"main": ["ffi", "fs", "io", "net"]}}
                 for n in NAMES],
    "allow": "all", "budget": "all", "safe_command": "--allow all"},
    indent=2)


def plant_dotvelaris(where: Any) -> None:
    """A .velaris/ of everything a Velaris ever kept there or could be told
    to look for: proofs claimed, a budget, a standard library, a program."""
    d = Path(where) / ".velaris"
    write(d / "proofs.json", json.dumps(
        {"0" * 64: {"proven": True, "errors": []},
         "schema": "velaris.proofcache/1"}))
    write(d / "budget.json", json.dumps({"allow": "all", "deny": []}))
    write(d / "allow", "all\n")
    write(d / "std.vel", PLANTED_STD)
    write(d / "read.vel", EVIL)


def fixtures() -> None:
    write(DATA / "a.txt", "alpha")
    write(OUTSIDE / "b.txt", "OUTSIDE-BYTES")
    for n in NAMES:
        write(PROG / (n + ".vel"), fill(SOURCES[n]))
    write(PROBE_FILE, PROBE)
    write(PATHLESS_FILE, PATHLESS)
    # a directory holding every planted file, to run from
    write(PLANTED / "velaris.toml", TOML)
    write(PLANTED / "evil.vel", EVIL)
    write(PLANTED / "velaris.lock", PLANTED_LOCK)
    write(PLANTED / "velaris.capabilities", PLANTED_CAPABILITIES)
    plant_dotvelaris(PLANTED)
    write(PLANTED / "velaris.py",
          f"open(r'{PLANTED / 'IMPORTED'}', 'w').write('imported')\n")
    write(PLANTED / "std.vel", PLANTED_STD)
    write(PLANTED / "lib.vel", PLANTED_STD)
    write(PLANTED / ".hidden" / "std.vel", PLANTED_STD)
    write(PLANTED / "data" / "a.txt", "PLANTED")
    for n in NAMES:
        write(PLANTED / (n + ".vel"), EVIL)


# ---------------------------------------------------------------------------
# One observation: every program audited and run, under one cwd and one
# environment, through the command line (an audit of all five at once, and a
# run of each), the library in a child process, and optionally a pool.
# ---------------------------------------------------------------------------
def observe(cwd: Any, env: Any = None, prog_dir: Any = None, form: str = "abs", pool: bool = False) -> tuple[Any, ...]:
    prog_dir = Path(prog_dir or PROG)
    env = BASE_ENV if env is None else env

    def named(n: Any) -> Any:
        p = prog_dir / (n + ".vel")
        if form == "bare":
            return p.name
        if form == "rel":
            return os.path.relpath(str(p), str(cwd))
        return str(p)

    k = next(_seq)
    spec_file = WORK / "probe" / f"spec-{k}.json"
    out_file = WORK / "probe" / f"out-{k}.json"
    write(spec_file, json.dumps({
        "here": str(HERE), "out": str(out_file), "pool": pool,
        "programs": [[n, str(prog_dir / (n + ".vel")), BUDGETS[n]]
                     for n in NAMES]}))
    jobs = {"audit": (vel, ["audit"] + [named(n) for n in NAMES]
                      + ["--sarif"], cwd, env),
            "probe": (sh, [sys.executable, PROBE_FILE, spec_file], cwd, env)}
    for n in NAMES:
        jobs[n] = (vel, [named(n), "--allow", BUDGETS[n]], cwd, env)
    done = parallel(jobs)
    results: dict[str, dict[str, Any]] = {n: {} for n in NAMES}
    code, out, err = done["audit"]
    try:
        docs = json.loads(out)["runs"][0]["properties"]["audits"]
        cli = [caps(d) for d in docs]
    except (ValueError, KeyError, IndexError, TypeError):
        cli = [{"unreadable": f"exit {code}: {err[-240:]}"}] * len(NAMES)
    for n, doc in zip(NAMES, cli):
        results[n]["cli_audit"] = doc
        results[n]["cli_run"] = cli_outcome(done[n])
    pcode, _, perr = done["probe"]
    try:
        probe = json.loads(out_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        probe = {"programs": {}, "error": f"exit {pcode}: {perr[-300:]}"}
    for n in NAMES:
        results[n].update(probe["programs"].get(
            n, {"lib_audit": probe.get("error"),
                "lib_run": probe.get("error")}))
    return results, probe


def report(label: Any, results: Any, expect_run: Any = None) -> None:
    """Two lines: every audit is the baseline's, and every run ends as the
    baseline's (or as `expect_run` states for the programs it names)."""
    audit_bad, run_bad = [], []
    for n in NAMES:
        for s in ("cli_audit", "lib_audit", "pool_audit"):
            if s in results[n] and results[n][s] != BASE_CAPS[n]:
                audit_bad.append(
                    f"{n}.vel {s}: {_delta(results[n][s], BASE_CAPS[n])}")
        want = (expect_run or {}).get(n, BASE_RUN[n])
        for s in ("cli_run", "lib_run"):
            if results[n].get(s) != want:
                run_bad.append(f"{n}.vel {s}: {results[n].get(s)!r}, "
                               f"expected {want!r}")
    surfaces = "command line, library" + (
        ", pool" if any("pool_audit" in results[n] for n in NAMES) else "")
    ok(f"{label}: every audit is the baseline's ({surfaces})",
       not audit_bad, " | ".join(audit_bad))
    said = "as stated" if expect_run else "as at baseline"
    ok(f"{label}: every run ends {said} (command line, library)",
       not run_bad, " | ".join(run_bad))


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------
def baseline() -> None:
    section("Baseline: five programs, audited and run in this process")
    for n in NAMES:
        p = PROG / (n + ".vel")
        src = p.read_text(encoding="utf-8")
        BASE_CAPS[n] = caps(velaris.audit(src, path=str(p), timeout=None,
                                          max_memory_mb=None).as_dict())
        r = velaris.run(src, path=str(p), allow=set(BUDGETS[n].split(",")))
        BASE_RUN[n] = lib_outcome(r)
        if n == "print":
            BASE_PARAMS.update(
                cast(dict[str, Any], r.receipt)["predicate"]["run_parameters"])
    c = BASE_CAPS
    sane = {
        "read": c["read"]["fs_paths"]["read"] == sorted(
            [fwd(DATA) + "/a.txt", fwd(OUTSIDE) + "/b.txt"])
        and c["read"]["effects"] == ["fs", "io"],
        "net": c["net"]["net_hosts"] == {
            "hosts": sorted([f"127.0.0.1:{PORT}", "refused.example.invalid"]),
            "any": False},
        "ffi": c["ffi"]["ffi_modules"] == ["json", "os"]
        and c["ffi"]["ffi_any"] is False,
        "print": (c["print"]["secrets"] or {}).get("sources") == ["env"]
        and (c["print"]["secrets"] or {}).get("declassifies") is True,
        "promise": c["promise"]["effects"] == ["io"],
    }
    for n in NAMES:
        ends = str(EXPECT_RUN[n][:3]).replace(fwd(WORK), "<work>")
        label = (f"B0 {n}.vel under {BUDGETS[n].replace(fwd(WORK), '<work>')}"
                 f": audited ok, and ends {ends}")
        if n == "net" and BASE_RUN[n][1] == "E317":
            skip(label, "this machine's own proxy settings carry requests to "
                        "127.0.0.1; set NO_PROXY=127.0.0.1 to run it")
            continue
        ok(label, c[n]["ok"] and sane[n] and BASE_RUN[n] == EXPECT_RUN[n],
           f"audit {c[n]} run {BASE_RUN[n]}")


# ---------------------------------------------------------------------------
# A. The working directory
# ---------------------------------------------------------------------------
REL_SOURCE = ('fn main() uses io, fs {\n'
              '    check read_file("data/a.txt") {\n'
              '        ok t { print("rel: " + t) }\n'
              '        fail w { print("rel failed") }\n'
              '    }\n'
              '}\n')


def cwd_cases() -> None:
    section("A. The working directory")
    before = files_under(PLANTED)
    res, _ = observe(PROG, form="bare", pool=True)
    report("A1 cwd = the program's own directory, named bare (the command "
           "line's baseline; the library and a pool worker started there)",
           res)
    docs = parallel({n: (vel, ["audit", n + ".vel", "--json"], PROG)
                     for n in NAMES})
    bad = []
    for n in NAMES:
        try:
            if caps(json.loads(docs[n][1])) != BASE_CAPS[n]:
                bad.append(n)
        except ValueError:
            bad.append(f"{n}: {docs[n][2][-160:]}")
    ok("A1 ...and `velaris audit <file> --json` is the document "
       "`audit --sarif` carries, for each program", not bad, bad)

    res, _ = observe(WORK, form="rel")
    report("A2 cwd = its parent, named prog/<file>", res)
    res, _ = observe(UNRELATED)
    report("A3 cwd = an unrelated temporary directory, by absolute path", res)
    res, _ = observe(PLANTED, pool=True)
    report("A4 cwd = a directory of planted files (velaris.toml, "
           "velaris.lock, velaris.capabilities, .velaris/, velaris.py, "
           "std.vel, lib.vel, .hidden/, data/, a planted <name>.vel for each)",
           res)
    ok("A4 ...nothing imported the velaris.py planted there, and no planted "
       "file was changed",
       not (PLANTED / "IMPORTED").exists()
       and files_under(PLANTED) == before,
       sorted(set(files_under(PLANTED)) ^ set(before)))

    # Meant to matter: a relative path is resolved against the working
    # directory when the run opens it, as for any process - in the program's
    # literal and in a grant alike. What the audit reports is the literal as
    # written, so the audit does not move; the run reads what that name
    # names from where it starts, and an absolute grant still bounds it.
    write(PROG / "rel.vel", REL_SOURCE)
    write(PROG / "data" / "a.txt", "alpha-rel")
    grant = "io,fs:read:" + fwd(PROG / "data")
    rel = str(PROG / "rel.vel")
    done = parallel({
        "audit here": (vel, ["audit", "rel.vel", "--json"], PROG),
        "audit planted": (vel, ["audit", rel, "--json"], PLANTED),
        "run here": (vel, ["rel.vel", "--allow", grant], PROG),
        "run planted": (vel, [rel, "--allow", grant], PLANTED),
        "run planted, relative grant": (
            vel, [rel, "--allow", "io,fs:read:./data"], PLANTED)})
    try:
        here = caps(json.loads(done["audit here"][1]))
        there = caps(json.loads(done["audit planted"][1]))
    except ValueError:
        here, there = {"unreadable": done["audit here"][2][-160:]}, {}
    ok("A5 a relative literal (data/a.txt): the audit from the program's "
       "directory and from the planted one is the same, naming the literal",
       here == there and here.get("fs_paths", {}).get("read") ==
       ["data/a.txt"], _delta(here, there))
    runs = {k: cli_outcome(v) for k, v in done.items() if k.startswith("run")}
    ok("A5 ...run from its own directory under an absolute grant, it reads "
       "its own data",
       runs["run here"] == [0, None, None, "rel: alpha-rel\n"],
       runs["run here"])
    ok("A5 ...run from the planted directory under the same absolute grant, "
       "the name resolves there and is refused (E313): nothing planted is read",
       runs["run planted"][:2] == [1, "E313"]
       and "PLANTED" not in runs["run planted"][3], runs["run planted"])
    ok("A5 ...and an operator's relative grant (fs:read:./data) is resolved "
       "where the operator starts the run, so it reads that directory's file",
       runs["run planted, relative grant"] == [0, None, None,
                                               "rel: PLANTED\n"],
       runs["run planted, relative grant"])


# ---------------------------------------------------------------------------
# B. args()
# ---------------------------------------------------------------------------
WORDS: tuple[tuple[str, ...], ...]
WORDS = (("--allow", "all"), ("--allow=net",), ("--deny", "io"),
         ("--no-native",), ("--max-read", "99999"), ("--receipt", "x"),
         ("--no-cache",), ("--help",), ("--",))
ALL_WORDS = [w for words in WORDS for w in words]


def printed(words: Any) -> str:
    return "hello\nargs: [" + ", ".join(words) + "]\n"


def args_cases() -> None:
    section("B. args(): words after the program that look like Velaris flags")
    path = PROG / "print.vel"
    src = path.read_text(encoding="utf-8")
    for words in WORDS:
        r = velaris.run(src, path=str(path), allow={"io"}, args=list(words))
        pred = cast(dict[str, Any], r.receipt)["predicate"]
        got = lib_outcome(r)
        ok(f"B1 velaris.run(args=[{' '.join(words)}]): args() holds exactly "
           f"those words, and the run is still io, refused env",
           got == [1, "E310", "env", printed(words)]
           and pred["budget"] == "io"
           and pred["run_parameters"] == BASE_PARAMS,
           f"{got} budget={pred['budget']} {pred['run_parameters']}")
    bad = []
    for n in NAMES:
        if n == "print":
            continue
        p = PROG / (n + ".vel")
        r = velaris.run(p.read_text(encoding="utf-8"), path=str(p),
                        allow=set(BUDGETS[n].split(",")), args=ALL_WORDS)
        if lib_outcome(r) != BASE_RUN[n]:
            bad.append(f"{n}: {lib_outcome(r)}")
    ok("B1 ...and the other four programs, given all nine at once, end as at "
       "baseline", not bad, bad)

    bad = []
    with velaris.Pool(size=1, allow={"io"}, timeout=300) as pool:
        for words in WORDS:
            r = pool.run(src, path=str(path), args=list(words))
            pred = (r.receipt or {}).get("predicate") or {}
            if lib_outcome(r) != [1, "E310", "env", printed(words)] or \
                    pred.get("budget") != "io":
                bad.append(f"{words}: {lib_outcome(r)} {pred.get('budget')}")
    ok("B2 Pool.run(args=...), each of the nine: args() holds exactly those "
       "words, and the pool's budget is untouched", not bad, bad)

    r = velaris.run(src, path=str(path), allow={"io"}, args=ALL_WORDS,
                    timeout=300)
    pred = (r.receipt or {}).get("predicate") or {}
    ok("B3 velaris.run(args=all nine, timeout=300): the bounded run's child "
       "gets them as arguments, and nothing more",
       lib_outcome(r) == [1, "E310", "env", printed(ALL_WORDS)]
       and pred.get("budget") == "io"
       and (pred.get("run_parameters") or {}).get("max_read_bytes")
       == BASE_PARAMS["max_read_bytes"],
       f"{lib_outcome(r)} {pred.get('budget')}")

    # The command line. The operator's flags come first; `--` then marks
    # the end of them, and what follows is the program's (check_cli.py, 8.2:
    # "the flag after a file is the program's argument"). The operator's
    # --receipt records the budget and run parameters the run really had.
    zero = WORK / "args" / "none"
    zero.mkdir(parents=True)
    code, _, err = vel([path, "--allow", "io", "--receipt", zero / "r.json"],
                       zero)
    try:
        cli_params = json.loads((zero / "r.json").read_text(
            encoding="utf-8"))["predicate"]["run_parameters"]
    except (OSError, ValueError, KeyError):
        cli_params = {"unreadable": err[-160:]}
    jobs = {}
    for i, words in enumerate(WORDS):
        d = WORK / "args" / str(i)
        d.mkdir(parents=True)
        jobs[i] = (vel, [path, "--allow", "io", "--receipt", d / "r.json",
                         "--"] + list(words), d)
    done = parallel(jobs)
    missed = []
    for i, words in enumerate(WORDS):
        d = WORK / "args" / str(i)
        try:
            pred = json.loads((d / "r.json").read_text(
                encoding="utf-8"))["predicate"]
        except (OSError, ValueError, KeyError):
            pred = {}
        got = cli_outcome(done[i])
        changed = []
        if pred.get("budget") != "io":
            changed.append(f"budget {pred.get('budget')!r}")
        if pred.get("run_parameters") != cli_params:
            changed.append(f"run_parameters {pred.get('run_parameters')}")
        if got[:3] != [1, "E310", "env"] or not got[3].startswith("hello\n"):
            changed.append(f"the run ended {got}")
        if (d / "x").exists():
            changed.append("a file x was written")
        ok(f"B4 velaris print.vel --allow io --receipt R -- "
           f"{' '.join(words)}: the run's budget, parameters and end are the "
           f"operator's", not changed, "; ".join(changed))
        seen = re.search(r"^args: (.*)$", got[3], re.M)
        want = "[" + ", ".join(words) + "]"
        if seen is None or seen.group(1) != want:
            missed.append(f"-- {' '.join(words)} gave "
                          f"{seen.group(1) if seen else None}")
    ok("B4 ...and the words after -- reach args() as they were written",
       not missed, "; ".join(missed))

    # No budget from the operator at all: the words after -- must not be
    # where one comes from.
    bare = WORK / "args" / "bare"
    bare.mkdir(parents=True)
    done = parallel({
        "all": (vel, [path, "--", "--allow", "all"], bare),
        "receipt": (vel, [path, "--", "--receipt", "x"], bare)})
    got = cli_outcome(done["all"])
    ok("B5 velaris print.vel -- --allow all, the operator naming no budget: "
       "the run has the default io and is refused env (E310)",
       got[:3] == [1, "E310", "env"],
       f"the run ended {got}; stderr {done['all'][2][:140]!r}")
    ok("B5 velaris print.vel -- --receipt x: the run writes no file the "
       "operator did not name", not (bare / "x").exists(),
       f"{bare / 'x'} was written: {cli_outcome(done['receipt'])}")


# ---------------------------------------------------------------------------
# C. The environment
# ---------------------------------------------------------------------------
# Every variable velaris/*.py reads by name (grep os.environ). The standard
# library also reads some on Velaris's behalf: urllib's getproxies and
# proxy_bypass (HTTP_PROXY, HTTPS_PROXY, NO_PROXY - C9, C10), tempfile (TEMP,
# TMP, TMPDIR - C12 and G5) and os.path.expanduser (HOME, USERPROFILE - C13).
KNOWN_ENV = {
    "VELARIS_PROOF_TIMEOUT", "VELARIS_PROVER_SEED", "VELARIS_CHECK_CHILD",
    "VELARIS_CHECK_MEMORY_MB", "VELARIS_TOKEN", "VELARIS_DEBUG_INV",
    "VELARIS_CONFORMANCE_CORPUS", "VELARIS_PYPI_URL", "VELARIS_NPM_REGISTRY",
    "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "PYTHONPATH",
    "SOURCE_DATE_EPOCH", "GITHUB_TOKEN", "GITHUB_REPOSITORY",
    "GITHUB_API_URL"}


def env_names_read() -> Any:
    texts = [p.read_text(encoding="utf-8")
             for p in sorted((HERE / "velaris").glob("*.py"))]
    consts: dict[str, str] = {}
    for text in texts:
        consts.update(re.findall(r'^(\w+_ENV)\s*=\s*"(\w+)"', text, re.M))
    names = set()
    for text in texts:
        names.update(re.findall(
            r'os\.environ(?:\.get|\.pop)?[\(\[]\s*"(\w+)"', text))
        for const in re.findall(
                r'os\.environ(?:\.get|\.pop)?[\(\[]\s*(\w+_ENV)\b', text):
            names.add(consts.get(const, const))
    return names


def env_cases() -> None:
    section("C. The environment")
    found = env_names_read()
    ok("C0 the variables velaris/*.py reads by name are the ones this "
       "section varies", found == KNOWN_ENV,
       f"read and not varied here: {sorted(found - KNOWN_ENV)}; "
       f"no longer read: {sorted(KNOWN_ENV - found)}")

    cache = WORK / "cachedir"
    write(cache / "velaris" / "proofs" / ("0" * 64 + ".json"), json.dumps(
        {"schema": "velaris.proofcache/1", "proofs": {}}))
    variations = [
        ("C1 VELARIS_PROOF_TIMEOUT=0.001, too short for any proof",
         {"VELARIS_PROOF_TIMEOUT": "0.001"}, False),
        ("C2 VELARIS_PROOF_TIMEOUT=not-a-number",
         {"VELARIS_PROOF_TIMEOUT": "not-a-number"}, False),
        ("C3 VELARIS_PROVER_SEED=7", {"VELARIS_PROVER_SEED": "7"}, False),
        ("C4 VELARIS_CHECK_CHILD=1", {"VELARIS_CHECK_CHILD": "1"}, True),
        ("C5 VELARIS_CHECK_MEMORY_MB=1, without VELARIS_CHECK_CHILD",
         {"VELARIS_CHECK_MEMORY_MB": "1"}, False),
        ("C6 VELARIS_TOKEN set",
         {"VELARIS_TOKEN": "self-budget-token-" + "a" * 24}, False),
        ("C7 VELARIS_CACHE_DIR naming a directory of planted proof files",
         {"VELARIS_CACHE_DIR": str(cache)}, False),
        ("C11 every other variable velaris/*.py reads, set "
         "(VELARIS_CONFORMANCE_CORPUS, VELARIS_PYPI_URL, VELARIS_NPM_REGISTRY, "
         "VELARIS_DEBUG_INV, SOURCE_DATE_EPOCH, GITHUB_*)",
         {"VELARIS_CONFORMANCE_CORPUS": str(PLANTED),
          "VELARIS_PYPI_URL": "http://127.0.0.1:9/",
          "VELARIS_NPM_REGISTRY": "http://127.0.0.1:9/",
          "VELARIS_DEBUG_INV": "1", "SOURCE_DATE_EPOCH": "0",
          "GITHUB_TOKEN": "planted", "GITHUB_REPOSITORY": "planted/planted",
          "GITHUB_API_URL": "http://127.0.0.1:9/"}, False),
    ]
    probes = {}
    for label, extra, pool in variations:
        res, probe = observe(UNRELATED, env=dict(BASE_ENV, **extra),
                             pool=pool)
        report(label, res)
        probes[label[:3]] = probe

    # The check ceiling is the operator's: a child it starts carries
    # VELARIS_CHECK_CHILD=1 so as not to start another. Set in the
    # environment the command line is given, the ceiling is not applied at
    # all. That widens no effect; it is a question of what the operator's
    # environment may say. Seen here through --check-timeout 0, which the
    # ceiling refuses (exit 2) and nothing else reads.
    argv = ["audit", PROG / "read.vel", "--json", "--check-timeout", "0"]
    done = parallel({
        "plain": (vel, argv, UNRELATED),
        "child": (vel, argv, UNRELATED,
                  dict(BASE_ENV, VELARIS_CHECK_CHILD="1"))})
    try:
        child_caps = caps(json.loads(done["child"][1]))
    except ValueError:
        child_caps = {}
    ok("C4b VELARIS_CHECK_CHILD=1 in the environment turns off the command "
       "line's check ceiling (an operator-environment question: the audit "
       "is the same), while the library in that environment keeps its own",
       done["plain"][0] == 2 and done["child"][0] == 0
       and child_caps == BASE_CAPS["read"]
       and probes["C4 "].get("in_child") is False,
       f"exit {done['plain'][0]} without, {done['child'][0]} with; "
       f"library in_child={probes['C4 '].get('in_child')}")

    # A velaris.py on PYTHONPATH, and in the directory velaris starts in.
    # Velaris's launchers - velaris.py by path, the check ceiling's child and
    # a pool worker by the path of velaris/__main__.py - put the directory
    # holding the package first, so it is never imported. (`python -m
    # velaris` from such a directory would run it: that is Python's -m,
    # which puts the working directory first, and none of them use it.)
    drop = WORK / "pydrop"
    marker = drop / "IMPORTED"
    write(drop / "velaris.py",
          f"open(r'{marker}', 'w').write('imported')\n")
    res, _ = observe(drop, env=dict(BASE_ENV, PYTHONPATH=str(drop)),
                     pool=True)
    report("C8 PYTHONPATH naming a directory holding a planted velaris.py, "
           "started in that directory", res)
    ok("C8 ...and the planted velaris.py was never imported",
       not marker.exists())

    # Meant to matter (8.0): a net grant bounds the socket's peer, so an
    # ambient proxy outside the grants refuses the request (E317) before a
    # connection is made. It narrows what the run does; it never widens it.
    if BASE_RUN["net"][1] == "E317":
        skip("C9 HTTP_PROXY", "this machine's own proxy settings already "
                              "carry 127.0.0.1 (B0)")
    else:
        PROXY.seen.clear()
        proxy = f"http://127.0.0.1:{PROXY_PORT}"
        res, _ = observe(UNRELATED, env=dict(BASE_ENV, HTTP_PROXY=proxy,
                                             HTTPS_PROXY=proxy))
        report("C9 HTTP_PROXY and HTTPS_PROXY naming a proxy no grant covers "
               "(net.vel refused E317 before connecting, printing nothing)",
               res, expect_run={"net": [1, "E317",
                                        f"net:127.0.0.1:{PROXY_PORT}", ""]})
        ok("C9 ...and the proxy received nothing", PROXY.seen == [],
           PROXY.seen)
        res, _ = observe(UNRELATED, env=dict(BASE_ENV, HTTP_PROXY=proxy,
                                             HTTPS_PROXY=proxy,
                                             NO_PROXY="127.0.0.1"))
        report("C10 the same proxy with NO_PROXY=127.0.0.1", res)
        ok("C10 ...and the proxy received nothing", PROXY.seen == [],
           PROXY.seen)

    tmp = WORK / "tmpplant"
    write(tmp / "std.vel", PLANTED_STD)
    res, _ = observe(UNRELATED, env=dict(BASE_ENV, TEMP=str(tmp),
                                         TMP=str(tmp), TMPDIR=str(tmp)),
                     pool=True)
    report("C12 TEMP, TMP and TMPDIR naming a directory holding a planted "
           "std.vel, each program named by its path", res)

    # Meant to matter: the credential locations under the home directory
    # (8.0, E318) are found from HOME - USERPROFILE on Windows - which is
    # the operator's environment, not the program's; the ones known by name
    # (*.pem, *.key, .env) hold wherever home is.
    fake = WORK / "home"
    write(fake / ".aws" / "credentials", "[default]\nplanted = yes\n")
    write(DATA / "id.pem", "PEM")
    cred = write(WORK / "cred" / "cred.vel", fill(
        'fn main() uses io, fs {\n'
        '    check read_file("{HOME}/.aws/credentials") {\n'
        '        ok t { print("read it") }\n'
        '        fail w { print("failed") }\n'
        '    }\n'
        '    check read_file("{DATA}/id.pem") {\n'
        '        ok t { print("read pem") }\n'
        '        fail w { print("pem failed") }\n'
        '    }\n'
        '}\n').replace("{HOME}", fwd(fake)))
    grant = "io,fs:read:" + fwd(WORK)
    done = parallel({
        "plain": (vel, [cred, "--allow", grant], UNRELATED),
        "home": (vel, [cred, "--allow", grant], UNRELATED,
                 dict(BASE_ENV, HOME=str(fake), USERPROFILE=str(fake)))})
    plain, homed = cli_outcome(done["plain"]), cli_outcome(done["home"])
    ok("C13 a *.pem is a credential location (E318) whatever HOME and "
       "USERPROFILE say, and .aws/credentials is one under the home they "
       "name",
       plain == [1, "E318", "fs:" + fwd(DATA) + "/id.pem", "read it\n"]
       and homed == [1, "E318", "fs:" + fwd(fake) + "/.aws/credentials", ""],
       f"home unchanged: {plain}; home named: {homed}")


# ---------------------------------------------------------------------------
# D. velaris.toml
# ---------------------------------------------------------------------------
def toml_cases() -> None:
    section("D. velaris.toml")
    beside = WORK / "prog-toml"
    shutil.copytree(PROG, beside)
    write(beside / "velaris.toml", TOML)
    write(beside / "evil.vel", EVIL)
    res, _ = observe(beside, prog_dir=beside, form="bare")
    report("D1 a velaris.toml beside the program claiming another entry, "
           "every effect, a read ceiling and arguments; started there", res)

    cwd = WORK / "cwd-toml"
    write(cwd / "velaris.toml", TOML)
    write(cwd / "evil.vel", EVIL)
    res, _ = observe(cwd)
    report("D2 the same velaris.toml in the working directory only", res)

    # What reads it: `deps`, `verify` and `add`, as the manifest of the
    # directory they are run in - the one place it is meant to matter.
    code, out, _ = vel(["deps"], cwd)
    ok("D3 velaris deps run there reads it as that directory's manifest (the "
       "planted geo is listed, missing) - and nothing that audits or runs "
       "reads it",
       code == 0 and "geo" in out and "MISSING" in out, out[-200:])
    named = sorted(p.name for p in (HERE / "velaris").glob("*.py")
                   if "velaris.toml" in p.read_text(encoding="utf-8"))
    fresh = WORK / "new"
    fresh.mkdir()
    code, out, _ = vel(["new", "demo"], fresh)
    made = sorted(os.listdir(fresh / "demo")) if code == 0 else out
    ok("D4 velaris.toml is named only in velaris/project.py (deps, verify, "
       "add), and velaris new writes none",
       named == ["project.py"] and made == ["README.md", "main.vel"],
       f"{named} {made}")


# ---------------------------------------------------------------------------
# E. velaris.lock, and F. velaris add --force
# ---------------------------------------------------------------------------
GEO_V1 = ('fn where_am_i() -> Text uses net {\n'
          '    let place = "unreachable"\n'
          '    check fetch("http://127.0.0.1:{PORT}/geo") {\n'
          '        ok b { place = b }\n'
          '        fail w { place = "unreachable" }\n'
          '    }\n'
          '    return place\n'
          '}\n')
GEO_V2 = ('fn where_am_i() -> Text uses net, fs {\n'
          '    let place = "nowhere"\n'
          '    check read_file("{DATA}/a.txt") {\n'
          '        ok t { place = t }\n'
          '        fail w { place = "no file" }\n'
          '    }\n'
          '    check fetch("http://refused.example.invalid/geo") {\n'
          '        ok b { place = b }\n'
          '        fail w { place = "unreachable" }\n'
          '    }\n'
          '    return place\n'
          '}\n')
APP = ('import "lib/geo.vel" as geo\n'
       '\n'
       'fn main() uses io, net, fs {\n'
       '    print("geo: " + geo.where_am_i())\n'
       '}\n')
APP_NARROW = APP.replace("uses io, net, fs", "uses io, net")


def project_view(proj: Any, name: Any, budget: Any) -> dict[str, Any]:
    """The importing program as the command line audits and runs it, and
    as the library audits it in this process."""
    path = proj / name
    done = parallel({"audit": (vel, ["audit", name, "--json"], proj),
                     "run": (vel, [name, "--allow", budget], proj)})
    try:
        cli = caps(json.loads(done["audit"][1]))
    except ValueError:
        cli = {"unreadable": done["audit"][2][-200:]}
    lib = caps(velaris.audit(path.read_text(encoding="utf-8"), path=str(path),
                             timeout=None, max_memory_mb=None).as_dict())
    return {"cli": cli, "lib": lib, "run": cli_outcome(done["run"])}


def lock_and_add_cases() -> None:
    section("E. velaris.lock, and F. velaris add --force")
    proj = WORK / "lockproj"
    v1, v2 = fill(GEO_V1).encode("utf-8"), fill(GEO_V2).encode("utf-8")
    write(proj / "src" / "geo_v1.vel", v1.decode("utf-8"))
    write(proj / "src" / "geo_v2.vel", v2.decode("utf-8"))
    write(proj / "app.vel", APP)
    write(proj / "app_narrow.vel", APP_NARROW)
    budget = f"io,net:127.0.0.1:{PORT}"
    lib = proj / "lib" / "geo.vel"
    lock = proj / "velaris.lock"
    v1_host, v2_host = f"127.0.0.1:{PORT}", "refused.example.invalid"

    def narrow_caps() -> Any:
        p = proj / "app_narrow.vel"
        return caps(velaris.audit(p.read_text(encoding="utf-8"), path=str(p),
                                  timeout=None, max_memory_mb=None).as_dict())

    code, out, err = vel(["add", "src/geo_v1.vel", "as", "geo"], proj)
    first = project_view(proj, "app.vel", budget)
    vcode, vout, _ = vel(["deps", "--verify"], proj)
    ok("E0 velaris add vendors geo v1: the importer's audit names v1's host "
       "and no path, its run prints what it fetched, deps --verify passes",
       code == 0 and first["cli"] == first["lib"]
       and first["cli"].get("net_hosts", {}).get("hosts") == [v1_host]
       and first["cli"].get("fs_paths", {}).get("read") == []
       and first["run"] == [0, None, None, "geo: hi\n"] and vcode == 0,
       f"add exit {code} {err[-120:]}; {first}; verify {vcode}")

    # a lock that lies about the library: v2's digest, no capabilities
    original = lock.read_text(encoding="utf-8")
    doc = json.loads(original)
    entry = doc["libraries"][0]
    entry.update(sha256=sha(v2), added_by="99.0", effects=[],
                 capabilities={"effects": [], "net_hosts": [],
                               "fs_paths": [], "safe_command":
                               "velaris <file> --allow ''"})
    write(lock, json.dumps(doc, indent=2))
    lied = project_view(proj, "app.vel", budget)
    vcode, vout, _ = vel(["deps", "--verify"], proj)
    ok("E1 a velaris.lock claiming geo has v2's bytes and no capabilities: "
       "the importer's audit and run are those of the v1 on disk",
       lied == first, _delta(lied, first))
    ok("E1 ...and velaris deps --verify reports the mismatch (CHANGED, "
       "exit 1)", vcode == 1 and "CHANGED" in vout and "geo" in vout,
       vout[-240:])
    write(lock, original)

    # the library's bytes changed under a lock that still names v1
    lib.write_bytes(v2)
    moved = project_view(proj, "app.vel", budget)
    narrow = narrow_caps()
    vcode, vout, _ = vel(["deps", "--verify"], proj)
    ok("E2 lib/geo.vel made v2 under a lock naming v1: the importer's audit "
       "shows v2's path and host, and not v1's",
       moved["cli"] == moved["lib"]
       and moved["cli"].get("fs_paths", {}).get("read")
       == [fwd(DATA) + "/a.txt"]
       and moved["cli"].get("net_hosts", {}).get("hosts") == [v2_host],
       moved)
    ok("E2 ...its run under the same budget is refused fs (E310), an "
       "importer declaring only io, net no longer compiles (E300), and deps "
       "--verify reports it (CHANGED, exit 1)",
       moved["run"][:3] == [1, "E310", "fs"] and narrow["ok"] is False
       and "E300" in narrow["problems"] and vcode == 1
       and "CHANGED" in vout,
       f"run {moved['run']}; narrow {narrow['problems']}; verify {vcode}")
    lib.write_bytes(v1)

    code, out, err = vel(["add", "src/geo_v2.vel", "as", "geo"], proj)
    kept = project_view(proj, "app.vel", budget)
    ok("F1 velaris add of v2 without --force is refused, and geo stays v1: "
       "on disk, in the lock and in the importer's audit",
       code == 1 and sha(lib.read_bytes()) == sha(v1)
       and json.loads(lock.read_text(encoding="utf-8"))["libraries"][0][
           "sha256"] == sha(v1) and kept == first,
       f"exit {code}; {_delta(kept, first)}")

    code, out, err = vel(["add", "src/geo_v2.vel", "as", "geo", "--force"],
                         proj)
    forced = project_view(proj, "app.vel", budget)
    app_src = (proj / "app.vel").read_text(encoding="utf-8")
    pooled = caps(velaris.audit(app_src, path=str(proj / "app.vel"))
                  .as_dict())
    narrow = narrow_caps()
    vcode, vout, _ = vel(["deps", "--verify"], proj)
    locked = json.loads(lock.read_text(encoding="utf-8"))["libraries"][0]
    ok("F2 velaris add --force replaces geo with v2: the file and the lock "
       "are v2's, and deps --verify passes",
       code == 0 and lib.read_bytes() == v2 and locked["sha256"] == sha(v2)
       and vcode == 0, f"exit {code} {err[-120:]}; verify {vcode}")
    ok("F2 ...the importer's audit shows v2's needs through the command "
       "line, the library and a pool worker, and none of v1's",
       forced["cli"] == forced["lib"] == pooled
       and forced["cli"].get("net_hosts", {}).get("hosts") == [v2_host]
       and forced["cli"].get("fs_paths", {}).get("read")
       == [fwd(DATA) + "/a.txt"], f"{forced} pool {pooled}")
    ok("F2 ...and nothing keeps the old: the run is refused fs (E310) and "
       "the narrow importer is E300",
       forced["run"][:3] == [1, "E310", "fs"] and narrow["ok"] is False
       and "E300" in narrow["problems"],
       f"run {forced['run']}; narrow {narrow['problems']}")


# ---------------------------------------------------------------------------
# G. Hidden directories
# ---------------------------------------------------------------------------
HIDDEN_LIB = ('fn greet() -> Text {\n'
              '    return "hidden"\n'
              '}\n'
              '\n'
              'fn beacon() uses net {\n'
              '    check fetch("http://hidden.example.invalid/") {\n'
              '        ok b { }\n'
              '        fail w { }\n'
              '    }\n'
              '}\n')
REAL_LIB = 'fn greet() -> Text {\n    return "real"\n}\n'
IMPORTER = ('import "LIB"\n'
            '\n'
            'fn main() uses io {\n'
            '    print("greet: " + greet())\n'
            '}\n')
SCAN_PROGRAM = ('fn main() uses io, ffi {\n'
                '    check py_json("MOD", "f", "[1]") {\n'
                '        ok v { print(v) }\n'
                '        fail w { print(w) }\n'
                '    }\n'
                '}\n')
SCAN_FILES = {"top.vel": "json", "sub/s.vel": "math",
              ".hidden/h.vel": "string", ".velaris/v.vel": "textwrap",
              "cfg.velaris.d/w.vel": "keyword"}


def import_view(proj: Any, name: Any, cwd: Any, form: Any) -> tuple[Any, ...]:
    path = proj / name
    target = name if form == "bare" else str(path)
    done = parallel({"audit": (vel, ["audit", target, "--json"], cwd),
                     "run": (vel, [target, "--allow", "io"], cwd)})
    try:
        cli = caps(json.loads(done["audit"][1]))
    except ValueError:
        cli = {"unreadable": done["audit"][2][-200:]}
    lib = caps(velaris.audit(path.read_text(encoding="utf-8"), path=str(path),
                             timeout=None, max_memory_mb=None).as_dict())
    return cli, lib, cli_outcome(done["run"])


def hidden_cases() -> None:
    section("G. Hidden directories")
    proj = WORK / "hidproj"
    write(proj / "lib.vel", REAL_LIB)
    write(proj / ".hidden" / "lib.vel", HIDDEN_LIB)
    write(proj / "main.vel", IMPORTER.replace("LIB", "lib.vel"))
    write(proj / "explicit.vel", IMPORTER.replace("LIB", ".hidden/lib.vel"))
    for cwd, form, where in ((proj, "bare", "its own directory"),
                             (UNRELATED, "abs", "an unrelated one")):
        cli, lib, run = import_view(proj, "main.vel", cwd, form)
        ok(f"G1 import \"lib.vel\" beside .hidden/lib.vel, from {where}: the "
           f"import is lib.vel, and nothing of the hidden one is read",
           cli == lib and cli.get("ok") is True
           and cli.get("net_hosts") == {"hosts": [], "any": False}
           and run == [0, None, None, "greet: real\n"], f"{cli} {run}")

    gone = WORK / "hidproj-nolib"
    write(gone / ".hidden" / "lib.vel", HIDDEN_LIB)
    write(gone / "main.vel", IMPORTER.replace("LIB", "lib.vel"))
    cli, lib, run = import_view(gone, "main.vel", gone, "bare")
    ok("G2 with only .hidden/lib.vel there, import \"lib.vel\" is not found "
       "(E512): an import never looks inside a hidden directory",
       cli == lib and cli.get("ok") is False and cli.get("problems") ==
       ["E512"] and "hidden.example.invalid" not in json.dumps(cli)
       and run[:2] == [1, "E512"], f"{cli} {run}")

    cli, lib, run = import_view(proj, "explicit.vel", proj, "bare")
    ok("G3 import \".hidden/lib.vel\", written out, resolves as any relative "
       "import does, and the audit says what it holds",
       cli == lib and cli.get("ok") is True
       and cli.get("net_hosts", {}).get("hosts") == ["hidden.example.invalid"]
       and run == [0, None, None, "greet: hidden\n"], f"{cli} {run}")

    shadow = WORK / "prog-hiddenstd"
    shutil.copytree(PROG, shadow)
    write(shadow / ".hidden" / "std.vel", PLANTED_STD)
    res, _ = observe(shadow, prog_dir=shadow, form="bare")
    report("G4 a .hidden/std.vel beside promise.vel, which imports std.vel",
           res)

    # Found in this suite: a source given no path is compiled from a
    # temporary file, and its imports resolve beside that file - in the
    # system temp directory, which on a POSIX machine every local user can
    # write - before the shipped standard library. So a std.vel left there
    # changes what the audit of `velaris.audit(source)` says and what
    # `velaris.run(source)` computes. Nothing of the program or its budget
    # names that directory.
    src = fill(SOURCES["promise"])
    tmp = WORK / "tmpstd"
    write(tmp / "std.vel", PLANTED_STD)
    for label, env in (
            ("G5 velaris.audit(source) and velaris.run(source) with no path",
             BASE_ENV),
            ("G5 ...the same, the system temp directory (TEMP, TMP, TMPDIR) "
             "holding a planted std.vel",
             dict(BASE_ENV, TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp)))):
        k = next(_seq)
        spec = write(WORK / "probe" / f"pathless-{k}.json", json.dumps(
            {"here": str(HERE), "source": src,
             "out": str(WORK / "probe" / f"pathless-{k}.out.json")}))
        code, _, err = sh([sys.executable, PATHLESS_FILE, spec], UNRELATED,
                          env)
        try:
            got = json.loads((WORK / "probe" / f"pathless-{k}.out.json")
                             .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            got = {"error": f"exit {code}: {err[-300:]}"}
        audits = {s: got.get(s) for s in ("audit", "pool_audit")}
        runs = {s: got.get(s) for s in ("run", "bounded_run")}
        ok(f"{label}: the audit is the baseline's (in this process, and on a "
           f"worker)",
           all(a == BASE_CAPS["promise"] for a in audits.values()),
           f"temp dir {got.get('tempdir')}: " + " | ".join(
               f"{s}: {_delta(a, BASE_CAPS['promise'])}"
               for s, a in audits.items() if a != BASE_CAPS["promise"]))
        ok(f"{label}: the run ends as at baseline (in this process, and "
           f"bounded)",
           all(r == BASE_RUN["promise"] for r in runs.values()),
           f"{runs}, expected {BASE_RUN['promise']}")

    # The directory scans. What each does with a hidden directory is
    # recorded in the details; they must agree. The ratchet reads every
    # directory but .git (check_ratchet.py tests a widening in a hidden
    # one), and so must the rest.
    root = WORK / "scan"
    tree = root / "tree"
    for rel, module in SCAN_FILES.items():
        write(tree / rel, SCAN_PROGRAM.replace("MOD", module))
    every = set(SCAN_FILES)
    by_module = {module: rel for rel, module in SCAN_FILES.items()}

    def rel_of(p: Any) -> Any:
        p = p.replace("\\", "/")
        return p[len("tree/"):] if p.startswith("tree/") else p

    init = vel(["capabilities", "init", "tree"], root)
    done = parallel({
        "proofs .": (vel, ["proofs", "tree", "--json"], root),
        "audit --sarif .": (vel, ["audit", "tree", "--sarif"], root),
        "capabilities check": (vel, ["capabilities", "check", "tree",
                                     "--json"], root),
        "stats --ffi": (vel, ["stats", "--ffi", "tree", "--json"], root),
        "explain <dir>": (vel, ["explain", "tree"], root),
        "attest <dir>": (vel, ["attest", "tree", "--json"], root)})
    seen = {}
    try:
        seen["capabilities init"] = {rel_of(p["file"]) for p in json.loads(
            (tree / "velaris.capabilities").read_text(encoding="utf-8"))[
                "programs"]}
    except (OSError, ValueError, KeyError):
        seen["capabilities init"] = {f"<exit {init[0]}: {init[2][-80:]}>"}
    readers: dict[str, Callable[[str], set[str]]] = {
        "proofs .": lambda o: {rel_of(f["file"]) for f in
                               json.loads(o)["files"]},
        "audit --sarif .": lambda o: {
            by_module.get((a.get("ffi_modules") or ["?"])[0], "?")
            for a in json.loads(o)["runs"][0]["properties"]["audits"]},
        "capabilities check": lambda o: (
            set(seen["capabilities init"])
            if json.loads(o)["programs"] == len(seen["capabilities init"])
            else {f"<{json.loads(o)['programs']} program(s)>"}),
        "stats --ffi": lambda o: {rel_of(p["file"]) for p in
                                  json.loads(o)["programs"]},
        "explain <dir>": lambda o: {rel_of(ln[2:].strip())
                                    for ln in o.splitlines()
                                    if ln.strip().endswith(".vel")},
        "attest <dir>": lambda o: {rel_of(json.loads(ln)["subject"][0]["name"])
                                   for ln in o.splitlines() if ln.strip()},
    }
    for name, read in readers.items():
        code, out, err = done[name]
        try:
            seen[name] = read(out)
        except (ValueError, KeyError, IndexError, TypeError):
            seen[name] = {f"<exit {code}: {err[-80:]}>"}
    table = "; ".join(f"{k}: {sorted(v)}" for k, v in seen.items())
    ok("G6 every directory scan (proofs, audit --sarif, capabilities init and "
       "check, stats --ffi, explain, attest) reads sub/ and .hidden/",
       all({"top.vel", "sub/s.vel", ".hidden/h.vel"} <= v
           for v in seen.values()), table)
    left = sorted(k for k, v in seen.items() if ".velaris/v.vel" not in v)
    ok("G6 ...and treats .velaris/ as it treats every other hidden directory",
       not left, f"left out by {left}; {table}")
    left = sorted(k for k, v in seen.items()
                  if "cfg.velaris.d/w.vel" not in v)
    ok("G6 ...and reads cfg.velaris.d/, a directory whose name merely "
       "contains .velaris", not left, f"left out by {left}")
    extra = sorted(k for k, v in seen.items() if not v <= every)
    ok("G6 ...and reads nothing but the .vel files there (not "
       "velaris.capabilities, which init wrote)", not extra,
       f"{extra}; {table}")


# ---------------------------------------------------------------------------
# H. A planted velaris.capabilities and .velaris/ beside the program
# ---------------------------------------------------------------------------
def planted_cases() -> None:
    section("H. velaris.capabilities and .velaris/ beside the program")
    capdir = WORK / "prog-capabilities"
    shutil.copytree(PROG, capdir)
    write(capdir / "velaris.capabilities", PLANTED_CAPABILITIES)
    before = files_under(capdir)
    res, _ = observe(capdir, prog_dir=capdir, form="bare")
    report("H1 a velaris.capabilities beside the programs declaring every "
           "grant", res)
    ok("H1 ...and nothing rewrote it", files_under(capdir) == before)

    dotdir = WORK / "prog-dotvelaris"
    shutil.copytree(PROG, dotdir)
    plant_dotvelaris(dotdir)
    before = files_under(dotdir)
    res, _ = observe(dotdir, prog_dir=dotdir, form="bare", pool=True)
    report("H2 a .velaris/ beside the programs (proofs claimed, a budget of "
           "all, a std.vel, a read.vel)", res)
    res, _ = observe(UNRELATED, prog_dir=dotdir)
    report("H2 ...the same programs named by path from an unrelated "
           "directory", res)
    ok("H2 ...and nothing was written into it or beside it",
       files_under(dotdir) == before,
       sorted(set(files_under(dotdir)) ^ set(before)))


def main() -> Any:
    print(f"check_self_budget: Python {sys.version.split()[0]}, z3 "
          f"{'installed' if HAVE_Z3 else 'absent'}")
    fixtures()
    baseline()
    cwd_cases()
    args_cases()
    env_cases()
    toml_cases()
    lock_and_add_cases()
    hidden_cases()
    planted_cases()
    secs = time.perf_counter() - T0
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped in {secs:.0f}s")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
