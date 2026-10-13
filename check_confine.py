#!/usr/bin/env python3
"""The operating system holds the budget too (8.4), and says truthfully how
much of it.

  policy     os_policy() is the one derivation, budget -> OS policy: what
             each grant asks for, what a granted ffi module widens it to,
             ffi:os and ffi:subprocess widening it to nothing enforced, and a
             digest that is the same for the same budget
  the table  THREAT_MODEL.md prints confine.ENFORCES and confine.EXEMPT, row
             for row
  honesty    the fault-injection hook makes the runtime itself, from Python,
             attempt an effect outside the budget: a file read, a file
             written, a connection, a process started, a signal sent. Under
             confinement what this system's row of the table says is held is
             refused by the kernel and the run ends with E319 naming the
             layers; what it says is not held goes through; and with
             --no-confine every one goes through. Through every place
             docs/confinement.md and THREAT_MODEL.md say it is on by
             default: the command line, run(timeout=), a Pool, the HTTP
             door, the MCP server and sabline eval
  legitimate reads and writes inside a grant, a name resolved and a request
             made under a net grant, a temporary file under ffi:tempfile, a
             proof and native code made inside a confined pool worker
  reported   the receipt's level, reason, layers and policy digest; the
             audit's confinement; `sabline doctor`; `sabline receipts diff`
             naming a level that changed; eval refusing to run at none
  unreachable --no-confine after `--`, in a door's request, and in a
             program's own words changes nothing
  strict     --confine strict (9.0, decisions/0006 e): a granted module's
             native fopen, its own open and write through the C library and
             os.system's process are refused by the kernel, the hook is
             E319 with an ffi grant as without, and without strict 19d runs
             as it always has, its receipt naming the module
  required   --require-confinement (9.0, decisions/0007 32a): a level below
             the one asked for is E326 before the first statement, with the
             level in the receipt and the hook never run - on the command
             line, the library and a pool
  against it a symbolic link and a bind mount inside a granted path, the
             network and a process through a granted ffi module, a process
             asked to leave the Windows job, a mount, another thread
  container  on Windows, through sabline-rt: the ACEs a run's AppContainer
             is given are taken back when it ends, a run killed while
             holding them is swept by the next, `--contained` outside a
             container claims nothing, and each budget the container is
             left off for says so in its receipt
  no Landlock on Linux, through sabline-rt: the path a kernel without
             Landlock would take, asked for through the fault-injection
             hook - reads and writes go through, seccomp still refuses the
             network and a process, and `--require-confinement full`
             refuses the run. It is a simulation and says so
  the targets every escape of check_sandbox.py, and the file and ffi
             targets of check_adversarial.py, run on a Sabline whose budget
             checks are knocked out (tests/confine/faulty_runtime.py): which
             the kernel stops, and which the language alone does. --record
             writes tests/confine/kernel-<platform>.json

    python check_confine.py [--record]
    python check_confine.py --runtime rust

**`--runtime rust`** (9.0, M4) asks every one of those questions of
sabline-rt instead: each child is started with
`SABLINE_REFERENCE_RUNTIME=rust`, so the run inside each command is
sabline-rt's and the confinement is the one sabline-rt applied to its own
process (rt/.../confine.rs and the three platform modules beside it). Three
parts stay the Python package's and say so rather than being asked twice:
the policy, the filter and the table, which are this module's own
derivations and are compared with sabline-rt's by the agreement gate; the
escape targets, which are measured on a Sabline whose *Python* budget checks
are knocked out; and `sabline eval`, whose run sabline-rt does not take yet
(plan/9.0.md, M4). Everything else - the honesty test, what still works,
what is reported, what a program cannot reach, what is tried against the
confinement itself, `--confine strict` and `--require-confinement` - is
asked of both.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SABLINE = str(HERE / "sabline.py")
FAULTY = str(HERE / "tests" / "confine" / "faulty_runtime.py")
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from sabline import confine, through_rt  # noqa: E402
from sabline.budget import Budget  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_confine")
PLATFORM = confine._platform()
PASSED = FAILED = 0
# Which runtime every child runs its program in (9.0, M4): "python", or
# "rust" for sabline-rt, which confines its own process. It is read once,
# here, and `cli` puts it in every child's environment - so a case written
# for one runtime is asked of the other without being written twice.
RUNTIME = "rust" if "--runtime" in sys.argv and "rust" in sys.argv else "python"

# What each system's row of THREAT_MODEL.md's table says of the hook's
# attempts under the default budget, io: True is "the kernel refuses it".
#
# Windows differs by runtime from 9.0's M4, and that is the only cell that
# does: sabline-rt starts the run's own process inside an **AppContainer**
# (rt/.../confine_appcontainer.rs), which holds reads to the ACEs it was
# given and refuses the network without a capability, where a running
# python.exe cannot enter one at all. docs/os-enforces.md prints both
# columns and check_rt_enforces() holds sabline-rt's table to the
# package's, cell for cell.
HELD_BY_RUNTIME = {
    "python": {
        "linux": {"read": True, "write": True, "connect": True,
                  "spawn": True, "signal": True},
        "macos": {"read": True, "write": True, "connect": True,
                  "spawn": True, "signal": False},
        "windows": {"read": False, "write": True, "connect": False,
                    "spawn": True, "signal": False},
    },
    "rust": {
        "linux": {"read": True, "write": True, "connect": True,
                  "spawn": True, "signal": True},
        "macos": {"read": True, "write": True, "connect": True,
                  "spawn": True, "signal": False},
        "windows": {"read": True, "write": True, "connect": True,
                    "spawn": True, "signal": False},
    },
}
LEVEL_BY_RUNTIME = {
    "python": {"linux": "full", "macos": "partial", "windows": "partial"},
    "rust": {"linux": "full", "macos": "partial", "windows": "full"},
}
# Copies, because on Windows this suite asks the machine whether a run is
# held by an AppContainer before it holds anything to one (see main()).
HELD = {system: dict(row)
        for system, row in HELD_BY_RUNTIME[RUNTIME].items()}
# What a run measured here gets: the runtime that will run it.
LEVEL = dict(LEVEL_BY_RUNTIME[RUNTIME])
# What `sabline audit`, `sabline doctor` and `confine.predict()` answer,
# which is the Python package's own runtime whatever will run the program.
# It is the weaker of the two on Windows, so a prediction never promises
# more than the run gets (plan/9.0-m4-progress.md's question of
# 2026-10-13).
PREDICTED = LEVEL_BY_RUNTIME["python"]
# The level a door's own worker gets. A pool worker is a Python process,
# confined at its start, and the honesty hook fires there - before a
# program is sent anywhere - so what a door reports for it is this
# package's level whichever runtime would have run the program.
WORKER_LEVEL = LEVEL_BY_RUNTIME["python"]


def ok(label: str, condition: Any, detail: object = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ok       {label}")
    else:
        FAILED += 1
        print(f"  BROKEN   {label}\n           {str(detail)[:900]}")


def cli(*words: str, env: dict[str, str] | None = None, cwd: Any = None,
        faulty: bool = False, timeout: int = 300) -> tuple[int, str, str]:
    full = dict(os.environ)
    full.pop(confine.FAULT_ENV, None)
    full["SABLINE_REFERENCE_RUNTIME"] = RUNTIME
    full.update(env or {})
    done = subprocess.run(
        [sys.executable, FAULTY if faulty else SABLINE, *words],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=full, cwd=cwd, timeout=timeout)
    return done.returncode, done.stdout, done.stderr


def program(name: str, text: str, where: Path | None = None) -> str:
    path = (where or WORK) / name
    path.write_text(text, encoding="utf-8")
    return str(path)


HELLO = 'fn main() uses io {\n    print("ran to the end")\n}\n'


def outside_dir() -> Path:
    """A directory no budget here grants. Under the home directory on macOS,
    where reads are refused only there and under /Volumes."""
    if PLATFORM == "macos":
        made = Path(tempfile.mkdtemp(prefix=".sabline-check-confine-",
                                     dir=str(Path.home())))
        import atexit
        atexit.register(shutil.rmtree, made, ignore_errors=True)
        return made
    made = WORK / "outside"
    made.mkdir(exist_ok=True)
    return made


def listener() -> tuple[socket.socket, int]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)

    def accept() -> None:
        while True:
            try:
                conn, _ = srv.accept()
                conn.close()
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    return srv, srv.getsockname()[1]


# ---- the policy ------------------------------------------------------------------

def policy_cases() -> None:
    print("budget -> OS policy, the one derivation")
    print("-" * 62)

    def of(spec: str, **kw: Any) -> dict[str, Any]:
        return confine.os_policy(Budget.parse(spec), **kw)

    data = os.path.normcase(os.path.realpath(str(WORK / "data")))
    p = of("io")
    ok("io: no path, no host, no process, and enforced",
       p["fs_read"] == [] and p["fs_write"] == [] and p["net"] == "none"
       and p["spawn"] is False and p["enforced"] is True, p)
    p = of(f"io,fs:read:{WORK / 'data'}")
    ok("fs:read:DIR: reads beneath DIR, resolved, and no write",
       p["fs_read"] == [data] and p["fs_write"] == [], p)
    p = of(f"io,fs:write:{WORK / 'data'}")
    ok("fs:write:DIR: writes beneath DIR and no read",
       p["fs_write"] == [data] and p["fs_read"] == [], p)
    p = of("io,fs:read")
    ok("fs:read with no path: reads are not restricted, writes are",
       p["fs_read"] is None and p["fs_write"] == [], p)
    p = of("io,fs")
    ok("plain fs: neither direction is restricted",
       p["fs_read"] is None and p["fs_write"] is None, p)
    p = of("io,net:api.example.com:443,net:*.example.org")
    ok("net grants: the hosts, with their ports",
       p["net"] == {"hosts": [["*.example.org", None],
                              ["api.example.com", 443]]}, p["net"])
    ok("...and the resolver's files and the TLS roots are among what the "
       "interpreter reads", "dns" in p["system"] and "tls-roots"
       in p["system"] and "dns" not in of("io")["system"], p["system"])
    ok("plain net: any host", of("io,net")["net"] == "any")
    p = of("io,ffi:math,ffi:json")
    ok("ffi:math,json widen nothing",
       p["enforced"] and p["widened_by"] == [] and p["net"] == "none"
       and p["fs_read"] == [] and not p["spawn"], p)
    p = of("io,ffi:sqlite3")
    ok("ffi:sqlite3 widens to any path, and names itself",
       p["enforced"] and p["fs_read"] is None and p["fs_write"] is None
       and p["net"] == "none" and p["widened_by"] == [
           {"module": "sqlite3", "widens": ["fs"], "known": True}], p)
    p = of("io,ffi:socket")
    ok("ffi:socket widens to any host and nothing else",
       p["enforced"] and p["net"] == "any" and p["fs_read"] == []
       and not p["spawn"], p)
    for module in ("os", "subprocess"):
        p = of(f"io,ffi:{module}")
        ok(f"ffi:{module} widens to nothing enforced",
           p["enforced"] is False and p["spawn"] is True
           and p["net"] == "any" and p["fs_write"] is None
           and confine.predict(p)["level"] == "none"
           and f"ffi:{module}" in confine.predict(p)["reason"], p)
    p = of("io,ffi:a_module_nobody_listed")
    ok("a module that is not in the table widens to nothing enforced, and "
       "says it is not known",
       p["enforced"] is False and p["widened_by"][0]["known"] is False
       and "not in the table" in confine.predict(p)["reason"], p)
    p = of("io,ffi")
    ok("plain ffi widens to nothing enforced",
       p["enforced"] is False and "plain ffi"
       in confine.predict(p)["reason"], p)
    p = of("io", confine=False)
    ok("--no-confine: nothing is asked, the level is none, and the reason "
       "says why", p["enforced"] is False
       and confine.predict(p)["level"] == "none"
       and "--no-confine" in confine.predict(p)["reason"],
       confine.predict(p))
    ok("the same budget gives the same digest, a different one another, "
       "and --no-confine another still",
       confine.policy_sha256(of("io")) == confine.policy_sha256(of("io"))
       and len({confine.policy_sha256(of("io")),
                confine.policy_sha256(of("io,net")),
                confine.policy_sha256(of("io", confine=False))}) == 3)
    ok("every module of the table widens to nothing, fs, net or all",
       all(set(w) <= {"fs", "net", "all"}
           for w in confine.FFI_WIDENS.values()))
    would = confine.predict(of("io"))
    ok(f"this system gives a run under io the level the package's own row "
       f"says: {PREDICTED.get(PLATFORM)}",
       would["level"] == PREDICTED.get(PLATFORM), would)


def decide(prog: list[tuple[int, int, int, int]], nr: int, arch: int,
           args: list[int]) -> str:
    """What the seccomp filter answers one system call: the program run
    here, instruction by instruction, over the data the kernel would hand
    it. So the filter is held on every system, not only where it is
    installed."""
    import struct
    data = struct.pack("<iIQ6Q", nr, arch, 0, *(args + [0] * (6 - len(args))))
    pc = acc = 0
    while True:
        code, jt, jf, k = prog[pc]
        if code == 0x20:                       # load a word of the data
            acc = struct.unpack_from("<I", data, k)[0]
            pc += 1
        elif code == 0x15:                     # jump if equal
            pc += 1 + (jt if acc == k else jf)
        elif code == 0x35:                     # jump if greater or equal
            pc += 1 + (jt if acc >= k else jf)
        elif code == 0x45:                     # jump if any bit is set
            pc += 1 + (jt if acc & k else jf)
        else:                                  # return
            return {0x7FFF0000: "allow", 0x00050001: "EPERM",
                    0x00050026: "ENOSYS", 0x80000000: "kill"}.get(k, hex(k))


def filter_cases() -> None:
    print()
    print("the seccomp filter, decided here for x86_64 and aarch64")
    print("-" * 62)
    pid = 4242
    for arch in ("x86_64", "aarch64"):
        n, audit = confine._SYSCALLS[arch], confine._AUDIT_ARCH[arch]

        def prog(spec: str) -> list[tuple[int, int, int, int]]:
            return confine.seccomp_program(
                confine.os_policy(Budget.parse(spec)), arch, pid)

        io, net = prog("io"), prog("io,net:api.example.com:443")
        widened, shell = prog("io,ffi:socket"), prog("io,ffi:os")
        expected = [
            ("an ordinary call", io, 0 if arch == "x86_64" else 63, [0],
             "allow"),
            ("a socket with no net granted", io, n["socket"], [2, 1],
             "EPERM"),
            ("connect with no net granted", io, n["connect"], [3], "EPERM"),
            ("an IPv4 socket under a net grant", net, n["socket"], [2, 1],
             "allow"),
            ("an IPv6 socket under a net grant", net, n["socket"], [10, 1],
             "allow"),
            ("the resolver's netlink socket under a net grant", net,
             n["socket"], [16, 3], "allow"),
            ("a Unix socket under a net grant", net, n["socket"], [1, 1],
             "EPERM"),
            ("a socketpair under a net grant", net, n["socketpair"], [1, 1],
             "EPERM"),
            ("a Unix socket when ffi:socket widened the policy", widened,
             n["socket"], [1, 1], "allow"),
            ("a thread", io, n["clone"], [0x3D0F00], "allow"),
            ("a process by clone", io, n["clone"], [17], "EPERM"),
            ("clone3, whose flags a filter cannot read", io, n["clone3"], [0],
             "ENOSYS"),
            ("execve", io, n["execve"], [0], "EPERM"),
            ("execveat", io, n["execveat"], [0], "EPERM"),
            ("a signal to this process", io, n["kill"], [pid, 6], "allow"),
            ("abort(), which is tgkill of this process", io, n["tgkill"],
             [pid, 7, 6], "allow"),
            ("a signal to another process", io, n["kill"], [1, 9], "EPERM"),
            ("a signal to this process's group", io, n["kill"], [0, 9],
             "EPERM"),
            ("a signal to every process", io, n["kill"], [2 ** 64 - 1, 9],
             "EPERM"),
            ("sigqueue to another process", io, n["rt_sigqueueinfo"], [1, 9],
             "EPERM"),
            ("input pushed at the terminal (TIOCSTI)", io, n["ioctl"],
             [1, 0x5412], "EPERM"),
            ("...with bits the kernel ignores set above it", io, n["ioctl"],
             [1, 0x100005412], "EPERM"),
            ("TIOCLINUX", io, n["ioctl"], [1, 0x541C], "EPERM"),
            ("the ioctl isatty() makes", io, n["ioctl"], [1, 0x5401],
             "allow"),
            ("ptrace", io, n["ptrace"], [0], "EPERM"),
            ("mount", io, n["mount"], [0], "EPERM"),
            ("unshare", io, n["unshare"], [0], "EPERM"),
            ("bpf", io, n["bpf"], [0], "EPERM"),
            ("io_uring_setup", io, n["io_uring_setup"], [0], "EPERM"),
            ("a process, once ffi:os widened the policy to nothing", shell,
             n["execve"], [0], "allow"),
        ]
        wrong = [(label, got, want) for label, program, nr, args, want
                 in expected
                 if (got := decide(program, nr, audit, args)) != want]
        ok(f"{arch}: {len(expected)} system calls each get the answer the "
           f"table gives", not wrong, wrong)
        ok(f"{arch}: a call made under another machine's numbering ends the "
           f"process", decide(io, n["execve"], 0x40000003, [0]) == "kill")
    x32 = decide(confine.seccomp_program(confine.os_policy(
        Budget.parse("io")), "x86_64", pid), 0x40000000 + 59, 0xC000003E, [0])
    ok("x86_64: the x32 numbers, which name other calls, are answered 'no "
       "such call'", x32 == "ENOSYS", x32)
    ok("every call the deny-lists name has a number on both machines",
       all(name in confine._SYSCALLS[arch]
           for arch in ("x86_64", "aarch64")
           for name in confine.DENIED_ALWAYS + confine.DENIED_WITHOUT_NET
           + tuple(c for c in confine.DENIED_WITHOUT_SPAWN
                   if c not in ("fork", "vfork") or arch == "x86_64")))


def table_cases() -> None:
    print()
    print("docs/os-enforces.md prints the tables this module holds, and "
          "sabline-rt's own")
    print("-" * 62)
    page = HERE / "docs" / "os-enforces.md"
    text = page.read_text(encoding="utf-8")
    missing = [row[0] for row in confine.ENFORCES
               if "| " + " | ".join(row) + " |" not in text]
    ok("every row of confine.ENFORCES is a row of docs/os-enforces.md, "
       "word for word", not missing, missing)
    missing = [row[0] for row in confine.EXEMPT
               if "| " + " | ".join(row) + " |" not in text]
    ok("...and every exemption of confine.EXEMPT", not missing, missing)
    listed = sorted(m for m, w in confine.FFI_WIDENS.items() if w)
    missing = [m for m in listed if f"`{m}`" not in text]
    ok("...and every module that widens the policy is named there",
       not missing, missing)
    ok("confine.ENFORCES_HELD gives one of yes, partly, no for each of "
       "ENFORCES' rows and each of the three systems, and no other row",
       [r[0] for r in confine.ENFORCES] == list(confine.ENFORCES_HELD)
       and all(len(w) == len(confine.SYSTEMS)
               and set(w) <= set(confine.HELD_WORDS)
               for w in confine.ENFORCES_HELD.values()),
       confine.ENFORCES_HELD)
    rt_enforces_cases(text)


def rt_enforces_cases(page: str) -> None:
    """sabline-rt's own ENFORCES table (9.0, M4): the same rows in the same
    order, no cell weaker than the package's, every cell that differs
    carrying a reason, and docs/os-enforces.md printing them. The prose
    stays the package's - a second copy of it would be two places to keep
    one fact - and what is compared is how much of each row counts."""
    exe = through_rt.binary()
    if not exe:
        print("  skip     sabline-rt is not built here, so its ENFORCES "
              "table cannot be asked for")
        return
    done = subprocess.run([exe, "os-policy", "--enforces"],
                          capture_output=True, text=True, errors="replace",
                          timeout=120)
    if done.returncode != 0:
        ok("sabline-rt os-policy --enforces answers its table", False,
           done.stderr[-400:])
        return
    rt = json.loads(done.stdout)
    rows = {r["row"]: r for r in rt["rows"]}
    ok("sabline-rt's ENFORCES table has the package's rows, in the "
       "package's order, for the package's three systems",
       [r["row"] for r in rt["rows"]] == list(confine.ENFORCES_HELD)
       and rt["systems"] == list(confine.SYSTEMS)
       and all(len(r["held"]) == len(confine.SYSTEMS) for r in rt["rows"]),
       [r["row"] for r in rt["rows"]][:3])
    rank = confine.HELD_WORDS.index
    weaker, unexplained, differ = [], [], []
    for row, mine in confine.ENFORCES_HELD.items():
        theirs = rows.get(row, {}).get("held") or []
        for system, was, now in zip(confine.SYSTEMS, mine, theirs):
            if rank(now) < rank(was):
                weaker.append(f"{row} on {system}: {was} -> {now}")
            elif now != was:
                differ.append(f"{row} on {system}: {was} -> {now}")
        if any(a != b for a, b in zip(mine, theirs)) \
                and not rows.get(row, {}).get("why"):
            unexplained.append(row)
    ok("no cell of sabline-rt's table is weaker than the package's: the "
       "second runtime never holds less of a row than the first",
       not weaker, weaker)
    ok(f"...and each of the {len(differ)} cells that differ carries a "
       f"reason", not unexplained, unexplained)
    ok("...and every one of them is Windows', which is where sabline-rt "
       "starts the run's own process inside an AppContainer",
       all(c.endswith("windows: no -> yes") or " on windows:" in c
           for c in differ) and differ, differ)
    missing = [r["row"] for r in rt["rows"]
               if r["why"] and r["why"] not in page]
    ok("...and docs/os-enforces.md prints each of those reasons, word for "
       "word", not missing, missing)


# ---- the honesty test --------------------------------------------------------------

def attempts(outside: Path, port: int) -> dict[str, str]:
    (outside / "held.txt").write_text("outside every grant", encoding="utf-8")
    tried = {"read": f"read:{outside / 'held.txt'}",
             "write": f"write:{outside / 'written.txt'}",
             "connect": f"connect:127.0.0.1:{port}",
             "spawn": "spawn"}
    if PLATFORM != "windows":
        # Windows has no signal to send; os.kill's 0 there is CTRL_C_EVENT,
        # which would interrupt this suite and whatever started it
        tried["signal"] = f"signal:{os.getpid()}"
    return tried


def honesty_cases() -> None:
    print()
    print(f"the honesty test on {PLATFORM}: the runtime itself attempts an "
          f"effect outside the budget")
    print("-" * 62)
    held = HELD.get(PLATFORM, {})
    outside = outside_dir()
    srv, port = listener()
    hello = program("hello.vel", HELLO)
    try:
        for kind, fault in attempts(outside, port).items():
            written = outside / "written.txt"
            written.unlink(missing_ok=True)
            code, out, err = cli(hello, env={confine.FAULT_ENV: fault})
            if held.get(kind):
                layers = re.search(r"confinement: (full|partial), by (\S.*)",
                                   err)
                ok(f"{kind}: refused by the kernel under confinement, and "
                   f"the run ends with E319 naming the layers",
                   code != 0 and "error[E319]" in err and layers
                   and "ran to the end" not in out
                   and not written.exists(), err[-600:])
            else:
                ok(f"{kind}: not held on {PLATFORM}, as its row says - it "
                   f"goes through and the run goes on",
                   code == 0 and "succeeded" in err
                   and "ran to the end" in out, err[-600:])
            written.unlink(missing_ok=True)
            code, out, err = cli(hello, "--no-confine",
                                 env={confine.FAULT_ENV: fault})
            ok(f"{kind}: with --no-confine it goes through, the run goes "
               f"on, and stderr says confinement is off",
               code == 0 and "succeeded; confinement: none" in err
               and "--no-confine: the operating system is not asked" in err
               and "ran to the end" in out, err[-600:])
        written = outside / "written.txt"
        written.unlink(missing_ok=True)

        # the same hook, through the library: a run in a process of its own
        # (confined at its first statement) and a pool (confined at start)
        os.environ[confine.FAULT_ENV] = attempts(outside, port)["write"]
        try:
            r = sabline.run(HELLO, timeout=60)
            ok("run(timeout=): the write is refused by the kernel (E319)",
               not r.ok and r.problems and r.problems[0].code == "E319"
               and not written.exists(),
               [p.as_dict() for p in r.problems])
            with sabline.Pool(size=1, timeout=60) as pool:
                r = pool.run(HELLO)
            ok("a Pool: the write is refused by the kernel (E319)",
               not r.ok and r.problems and r.problems[0].code == "E319"
               and not written.exists(),
               [p.as_dict() for p in r.problems])
            r = sabline.run(HELLO, timeout=60, confine=False)
            ok("run(timeout=, confine=False): it goes through",
               r.ok and written.exists(), [p.as_dict() for p in r.problems])
            written.unlink(missing_ok=True)
            with sabline.Pool(size=1, timeout=60, confine=False) as pool:
                r = pool.run(HELLO)
            ok("Pool(confine=False): it goes through",
               r.ok and written.exists(), [p.as_dict() for p in r.problems])
            written.unlink(missing_ok=True)
        finally:
            os.environ.pop(confine.FAULT_ENV, None)
    finally:
        srv.close()


# ---- nothing legitimate breaks -------------------------------------------------------

def parameters_of(result: Any) -> dict[str, Any]:
    receipt = result.receipt
    assert isinstance(receipt, dict)
    found: dict[str, Any] = receipt["predicate"]["run_parameters"]
    return found


def http_server() -> tuple[Any, int]:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b"hello from the granted host"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: Any) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def legitimate_cases() -> None:
    print()
    print("nothing legitimate breaks under confinement")
    print("-" * 62)
    data, out_dir = WORK / "data", WORK / "out"
    data.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)
    (data / "a.txt").write_text("inside the grant", encoding="utf-8")
    d, o = data.as_posix(), out_dir.as_posix()
    prog = program("files.vel", f'''
fn main() uses io, fs {{
    check read_file("{d}/a.txt") {{
        ok body {{ print("read: " + body) }}
        fail why {{ print("could not read: " + why) }}
    }}
    write_file("{o}/made.txt", "written under the grant")
    if file_exists("{o}/made.txt") {{ print("it exists") }}
}}
''')
    code, out, err = cli(prog, "--allow", f"io,fs:read:{d},fs:write:{o}")
    ok("a read inside fs:read and a write inside fs:write both happen",
       code == 0 and "read: inside the grant" in out and "it exists" in out
       and (out_dir / "made.txt").read_text(encoding="utf-8")
       == "written under the grant", err[-500:] + out)

    back = (WORK / "readback")
    back.mkdir(exist_ok=True)
    (back / "kept.txt").unlink(missing_ok=True)
    k = (back / "kept.txt").as_posix()
    prog = program("readback.vel", f'''
fn main() uses io, fs {{
    write_file("{k}", "saved")
    check read_file("{k}") {{
        ok body {{ print("read back: " + body) }}
        fail why {{ print("could not read it back: " + why) }}
    }}
}}
''')
    code, out, err = cli(prog, "--allow", f"io,fs:read:{k},fs:write:{k}")
    ok("a program reads back a file it has just written, under grants that "
       "name a file not there when the run began (8.3.1 ran it; "
       "examples/ledger.vel is one)",
       code == 0 and "read back: saved" in out, err[-500:] + out)

    srv, port = http_server()
    try:
        prog = program("net.vel", f'''
fn main() uses io, net {{
    check fetch("http://localhost:{port}/") {{
        ok body {{ print("fetched: " + body) }}
        fail why {{ print("could not fetch: " + why) }}
    }}
}}
''')
        code, out, err = cli(prog, "--allow", f"io,net:localhost:{port}")
        ok("under a net grant a name is resolved and the request made",
           code == 0 and "fetched: hello from the granted host" in out,
           err[-500:] + out)
    finally:
        srv.shutdown()

    prog = program("temp.vel", '''
fn main() uses io, ffi {
    check py("tempfile", "mkdtemp", ["-sabline"]) {
        ok where { print("a temporary directory was made") }
        fail why { print("no temporary directory: " + why) }
    }
}
''')
    code, out, err = cli(prog, "--allow", "io,ffi:tempfile")
    ok("a temporary file under ffi:tempfile", code == 0
       and "a temporary directory was made" in out, err[-500:] + out)

    proved = '''
fn double(n: Int) -> Int
    requires n >= 0 and n < 1000
    ensures result == n + n
{
    return n * 2
}

fn main() uses io {
    print(double(21))
}
'''
    with sabline.Pool(size=1, timeout=120) as pool:
        first = pool.run(HELLO)             # the worker is confined by now
        checked = pool.check(proved)
        ran = pool.run(proved)
    ok("a pool worker confined at its start still proves (Z3, when it is "
       "installed) and runs native code",
       first.ok and checked.ok and ran.ok and ran.output.strip() == "42"
       and (not sabline.HAVE_Z3 or "double" in checked.proven),
       [checked.as_dict(), ran.as_dict()])

    receipt = WORK / "receipt.json"
    code, out, err = cli(program("hello.vel", HELLO), "--receipt",
                         str(receipt))
    ok("a confined run still writes its receipt, outside every grant",
       code == 0 and receipt.exists() and json.loads(receipt.read_text(
           encoding="utf-8"))["predicate"]["exit"]["outcome"] == "ok",
       err[-400:])


# ---- what is reported ------------------------------------------------------------------

def reported_cases() -> None:
    print()
    print("the receipt, the audit, doctor and receipts diff")
    print("-" * 62)
    hello = program("hello.vel", HELLO)
    confined, off = WORK / "confined.json", WORK / "off.json"
    again = WORK / "confined-again.json"
    cli(hello, "--receipt", str(again))
    cli(hello, "--receipt", str(confined))
    cli(hello, "--no-confine", "--receipt", str(off))
    a = json.loads(confined.read_text(encoding="utf-8"))["predicate"][
        "run_parameters"]
    b = json.loads(off.read_text(encoding="utf-8"))["predicate"][
        "run_parameters"]
    io = Budget.parse("io")
    ok("the receipt records the level, the reason, the layers and the OS "
       "policy digest",
       a.get("confinement") == LEVEL.get(PLATFORM)
       and a.get("confinement_reason") and a.get("confinement_layers")
       and a.get("os_policy_sha256") == confine.policy_sha256(
           confine.os_policy(io)), a)
    ok("...and under --no-confine: none, why, no layer, and the digest of "
       "the policy that asks nothing",
       b.get("confinement") == "none" and "--no-confine"
       in b.get("confinement_reason", "") and b.get("confinement_layers") == []
       and b.get("os_policy_sha256") == confine.policy_sha256(
           confine.os_policy(io, confine=False)), b)
    # 8.7: a run whose grants turn the OS layer off says so on stderr, once,
    # as it starts. One condition, the receipt's: the budget's OS policy is
    # not enforced. Plain ffi, a module the table widens to nothing enforced,
    # and one it does not name - even one that does not exist - meet it; a
    # module the table widens to less does not.
    line = "so the operating system layer is off for this run"
    rec = WORK / "grant.json"
    for spec, why in (
            ("io,ffi", "plain ffi grants any module"),
            ("io,ffi:os", "ffi:os is granted"),
            ("io,ffi:subprocess,ffi:json", "ffi:subprocess is granted"),
            ("io,ffi:a_module_nobody_listed,ffi:json",
             "ffi:a_module_nobody_listed is not in the confinement table"),
            ("io,ffi:os,ffi:a_module_nobody_listed", "ffi:os is granted and "
             "ffi:a_module_nobody_listed is not in the confinement table"),
            ("io,ffi:json", None), ("io,ffi:pathlib", None),
            ("io,ffi:socket", None), ("io", None)):
        _, out, err = cli(hello, "--allow", spec, "--receipt", str(rec))
        p = json.loads(rec.read_text(encoding="utf-8"))["predicate"][
            "run_parameters"]
        is_off = not confine.os_policy(Budget.parse(spec))["enforced"]
        ok(f"--allow {spec}: "
           + ("stderr says, once, that the OS layer is off, and why" if why
              else "stderr says nothing of the OS layer")
           + " - as the receipt's policy does",
           is_off == (why is not None)
           and err.count(line) == int(is_off)
           and (why is None or f"sabline: {why}, {line}" in err)
           and "ffi:json" not in err and "ran to the end" in out
           and (p.get("confinement") == "none"
                and "nothing enforced" in p.get("confinement_reason", ""))
           == is_off, [err, p])
    _, _, said = cli(hello, "--allow", "io,ffi:os", "--no-confine")
    ok("...and under --no-confine only its own line is said",
       line not in said and "--no-confine" in said, said)
    r = sabline.run(HELLO)
    params = parameters_of(r)
    ok("a run in the caller's own process says none, and that it is "
       "because the caller's process is not Sabline's to confine",
       params["confinement"] == "none" and "caller's own process"
       in params["confinement_reason"], params)
    r = sabline.run(HELLO, timeout=60)
    params = parameters_of(r)
    ok("run(timeout=) is confined as a command line in this package's own "
       "runtime is - the library calls here are not asked through "
       "sabline-rt, which required_cases does ask",
       params["confinement"] == PREDICTED.get(PLATFORM)
       and params["os_policy_sha256"] == a["os_policy_sha256"], params)
    r = sabline.run("fn main() uses io {\n    print(1 +)\n}\n", timeout=60)
    params = parameters_of(r)
    ok("a program that did not compile never reached its first statement, "
       "and its receipt says none and why",
       params["confinement"] == "none" and "first statement"
       in params["confinement_reason"], params)

    code, out, err = cli("receipts", "diff", str(off), "--against",
                         str(confined), "--json")
    report = json.loads(out) if out.strip().startswith("{") else {}
    kinds = [d for d in (report.get("against_receipts") or {}).get(
        "differences", []) if d.get("kind") == "confinement_changed"]
    ok("receipts diff names a confinement level that changed, and that it "
       "is weaker", code == 1 and len(kinds) == 1
       and kinds[0]["what"] == "none" and "weaker" in kinds[0]["detail"]
       and LEVEL.get(PLATFORM, "?") in kinds[0]["detail"], out[:600] + err)
    code, out, err = cli("receipts", "diff", str(again), "--against",
                         str(confined), "--json")
    ok("...and nothing when it did not", code == 0, out[:400] + err)

    doc = sabline.audit(HELLO).as_dict()
    systems = (doc.get("confinement") or {}).get("systems") or {}
    ok("the audit reports what a run under its safe_command gets on each "
       "system in the Python package's own runtime, with the reason: full "
       "on Linux, partial on macOS and on Windows - never more than a run "
       "through sabline-rt gets there",
       {k: v.get("level") for k, v in systems.items()} == PREDICTED
       and all(v.get("reason") for v in systems.values())
       and all(confine.LEVELS.index(PREDICTED[p])
               <= confine.LEVELS.index(LEVEL_BY_RUNTIME["rust"][p])
               for p in PREDICTED), systems)
    ok("...reading nothing of the machine: the same bytes wherever it is "
       "made", "platform" not in doc["confinement"]
       and not any(str(WORK) in json.dumps(v) for v in systems.values()),
       doc["confinement"])
    shell = ('fn main() uses io, ffi {\n'
             '    check py("subprocess", "getoutput", ["echo x"]) {\n'
             '        ok v { print(v) }\n        fail w { print(w) }\n'
             '    }\n}\n')
    doc = sabline.audit(shell).as_dict()
    assert doc["confinement"] is not None
    ok("...and that ffi:subprocess widens the policy to nothing enforced, "
       "on every system",
       all(v["level"] == "none" and "ffi:subprocess" in v["reason"]
           for v in doc["confinement"]["systems"].values())
       and doc["confinement"]["widened_by"] == [
           {"module": "subprocess", "widens": ["all"], "known": True}],
       doc["confinement"])
    code, out, err = cli("audit", program("shell.vel", shell))
    ok("...on the command line too",
       "CONFINEMENT ON THIS MACHINE: none" in out
       and "ffi:subprocess widens the OS policy to nothing enforced" in out,
       out[-700:])
    code, out, err = cli("doctor")
    ok("sabline doctor reports the level this package's own runtime "
       "gives, and the reason when it is not full",
       f"confinement: {PREDICTED.get(PLATFORM)}" in out
       and (PREDICTED.get(PLATFORM) == "full" or "why:" in out), out)

    from sabline.evaluation import EvalRefused, _EvalPool

    class NoneWorker:
        confinement: dict[str, Any] = {
            "level": "none", "layers": [], "policy_sha256": None,
            "reason": "this kernel has no Landlock"}
        disposed = False
        on_event = None

        def dispose(self) -> None:
            self.disposed = True

    pool = _EvalPool(allow="io", timeout=5, max_memory_mb=128,
                     import_root=str(WORK), stop_file=str(WORK / "stop"),
                     writable=[str(WORK)])
    worker = NoneWorker()
    try:
        pool._started(worker)               # type: ignore[arg-type]
        refused = ""
    except EvalRefused as e:
        refused = str(e)
    finally:
        pool.close()
    ok("sabline eval refuses to run on a worker whose confinement is none, "
       "before anything is sent to it",
       "this worker got none" in refused and worker.disposed, refused)


# ---- --no-confine is nothing a program can reach -----------------------------------

def unreachable_cases() -> None:
    print()
    print("--no-confine cannot be reached from a program")
    print("-" * 62)
    outside = outside_dir()
    written = outside / "written.txt"
    fault = {confine.FAULT_ENV: f"write:{written}"}
    words = program("words.vel", '''
fn main() uses io {
    for word in args() { print("word: " + word) }
}
''')
    written.unlink(missing_ok=True)
    code, out, err = cli(words, "--", "--no-confine", env=fault)
    ok("after `--` it is the program's word, and the run is confined",
       "error[E319]" in err and not written.exists(), err[-400:] + out)
    code, out, err = cli(words, "--", "--no-confine")
    ok("...which the program is given as one of its args()",
       code == 0 and "word: --no-confine" in out, out + err[-300:])
    code, out, err = cli("eval", words, "--no-confine", "--receipt",
                         str(WORK / "eval.json"))
    ok("sabline eval refuses the flag", code == 2 and "--no-confine" in err,
       err)

    token = "confine-" + os.urandom(12).hex()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    door = subprocess.Popen(
        [sys.executable, SABLINE, "serve", "--port", str(port)],
        env=dict(os.environ, SABLINE_TOKEN=token, **fault),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(WORK))
    import time
    import urllib.error
    import urllib.request

    def post(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/run", method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                       timeout=5).close()
                break
            except OSError:
                time.sleep(0.25)
        written.unlink(missing_ok=True)
        status, answer = post({"source": HELLO, "allow": ["io"],
                               "confine": False, "no_confine": True,
                               "no-confine": True, "receipt": True,
                               "args": ["--no-confine"]})
        codes = [p.get("code") for p in answer.get("problems") or []]
        level = (((answer.get("receipt") or {}).get("predicate") or {})
                 .get("run_parameters") or {}).get("confinement")
        ok("a request to the HTTP door that asks for no confinement gets a "
           "confined run all the same",
           status == 200 and codes == ["E319"] and not written.exists()
           and level == WORKER_LEVEL.get(PLATFORM), f"{status} {answer}")
    finally:
        door.terminate()
        door.wait(timeout=30)

    # The same door-level case for the MCP server (32e). Six places are
    # claimed confined and five were asserted here; `sabline mcp` is the
    # sixth: a real child with the hook in its environment, one
    # sabline_run that asks for no confinement every way the request
    # above asks, and E319 at this platform's own level coming back. The
    # operator's --no-confine is the second case on purpose - without it
    # a green first case could be green for a reason nobody wanted.
    def mcp_call(flags: list[str], arguments: dict[str, Any]) -> dict[str, Any]:
        """Start `sabline mcp`, make one tool call, stop it, and give back
        what the tool answered. Everything is written at once and read at
        EOF, so a server that stops answering ends this instead of
        holding it."""
        asks = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "sabline_run",
                            "arguments": arguments}},
                {"jsonrpc": "2.0", "id": 3, "method": "exit"}]
        child = subprocess.Popen(
            [sys.executable, SABLINE, "mcp", *flags],
            env=dict(os.environ, **fault), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            cwd=str(WORK))
        try:
            out, _ = child.communicate(
                "".join(json.dumps(a) + "\n" for a in asks),
                timeout=300)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=30)
            return {"error": "the MCP server did not answer"}
        for line in out.splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and msg.get("id") == 2:
                content = (msg.get("result") or {}).get("content") or [{}]
                text = content[0].get("text") or "{}"
                try:
                    answered = json.loads(text)
                except json.JSONDecodeError:
                    answered = None
                return (answered if isinstance(answered, dict)
                        else {"error": text})
        return {"error": f"no answer to the tool call in {out!r}"}

    def confinement_of(answer: dict[str, Any]) -> Any:
        return (((answer.get("receipt") or {}).get("predicate") or {})
                .get("run_parameters") or {}).get("confinement")

    tool_call = {"source": HELLO, "allow": ["io"], "confine": False,
                 "no_confine": True, "no-confine": True, "receipt": True,
                 "args": ["--no-confine"]}
    written.unlink(missing_ok=True)
    answer = mcp_call([], tool_call)
    codes = [p.get("code") for p in answer.get("problems") or []]
    ok("a tool call to the MCP server that asks for no confinement gets a "
       "confined run all the same",
       codes == ["E319"] and not written.exists()
       and confinement_of(answer) == WORKER_LEVEL.get(PLATFORM), answer)
    written.unlink(missing_ok=True)
    answer = mcp_call(["--no-confine"], tool_call)
    ok("...and the operator's own --no-confine is what turns it off, so "
       "the case above is one that can fail",
       not answer.get("problems") and written.exists()
       and confinement_of(answer) == "none", answer)
    written.unlink(missing_ok=True)

    # The doors' own two confinement flags (9.0, M4): the operator's, on
    # the command line, carried to every pool the door makes. A request
    # names a budget and never these, which the two cases above hold.
    widening = ["--max-allow", "io,ffi:nativefmt"]
    answer = mcp_call([*widening, "--confine", "strict"],
                      {"source": HELLO, "allow": ["io", "ffi:nativefmt"],
                       "receipt": True})
    digest = (((answer.get("receipt") or {}).get("predicate") or {})
              .get("run_parameters") or {}).get("os_policy_sha256")
    ok("sabline mcp --confine strict: every run on the server is derived "
       "under strict, so a granted module widens no policy - the receipt's "
       "digest is the strict one",
       digest == confine.policy_sha256(confine.os_policy(
           Budget.parse("io,ffi:nativefmt"), strict=True)), answer)
    answer = mcp_call(widening,
                      {"source": HELLO, "allow": ["io", "ffi:nativefmt"],
                       "receipt": True})
    ok("...and without it the default has not moved: the same run's "
       "digest is the policy no module widened under strict",
       (((answer.get("receipt") or {}).get("predicate") or {})
        .get("run_parameters") or {}).get("os_policy_sha256")
       == confine.policy_sha256(confine.os_policy(
           Budget.parse("io,ffi:nativefmt"))), answer)
    badly: list[str] = []
    for which, flags, says in (
            ("mcp", ["--confine", "lax"], "takes strict"),
            ("mcp", ["--no-confine", "--require-confinement", "full"],
             "say one"),
            ("mcp", ["--require-confinement", "most"], "full or partial"),
            ("serve", ["--confine", "lax"], "takes strict"),
            ("serve", ["--no-confine", "--confine", "strict"], "say one"),
            ("serve", ["--require-confinement", "most"],
             "full or partial")):
        tried = subprocess.run([sys.executable, SABLINE, which, *flags],
                               capture_output=True, text=True,
                               errors="replace", stdin=subprocess.DEVNULL,
                               timeout=300)
        said = tried.stdout + tried.stderr
        if tried.returncode == 0 or says not in said:
            badly.append(f"sabline {which} {' '.join(flags)}: "
                         f"{tried.returncode} {said[-200:]}")
    ok("a door's confinement flags are read the way every command line "
       "reads them: a mode that is not one, a level that is not one, and "
       "either beside --no-confine, are refused before the door starts",
       not badly, badly)
    refused: list[str] = []
    for flags, says in ((["--confine", "strict"], "--confine"),
                        (["--require-confinement", "partial"],
                         "--require-confinement")):
        tried = subprocess.run(
            [sys.executable, SABLINE, "eval", str(WORK / "hello.vel"),
             *flags], capture_output=True, text=True, errors="replace",
            stdin=subprocess.DEVNULL, timeout=300)
        if tried.returncode == 0 or f"refused: {says}" not in tried.stderr:
            refused.append(f"{flags}: {tried.returncode} "
                           f"{tried.stderr[-200:]}")
    ok("sabline eval refuses both by name, as it refuses --no-confine: "
       "confinement is part of its profile and has no switch",
       not refused, refused)


# ---- against the confinement itself ---------------------------------------------------

def against_cases() -> None:
    print()
    print("against the confinement itself")
    print("-" * 62)
    held = HELD.get(PLATFORM, {})
    outside = outside_dir()
    (outside / "held.txt").write_text("outside every grant", encoding="utf-8")
    granted = WORK / "granted"
    granted.mkdir(exist_ok=True)
    hello = program("hello.vel", HELLO)
    link = granted / "link.txt"
    try:
        link.unlink(missing_ok=True)
        link.symlink_to(outside / "held.txt")
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    if not linked:
        print("  skip     a symbolic link out of a granted path (this "
              "system will not make one here)")
    else:
        code, out, err = cli(hello, "--allow", f"io,fs:read:{granted}",
                             env={confine.FAULT_ENV: f"read:{link}"})
        if held.get("read"):
            ok("a symbolic link inside a granted path, to a file outside "
               "it: the kernel refuses the read", "error[E319]" in err,
               err[-400:])
        else:
            ok("a symbolic link inside a granted path: reads are not held "
               f"on {PLATFORM}, and the read goes through - the language's "
               f"realpath is what holds it", code == 0 and "succeeded" in err,
               err[-400:])

    srv, port = listener()
    try:
        connect = {confine.FAULT_ENV: f"connect:127.0.0.1:{port}"}
        code, out, err = cli(hello, "--allow", "io,ffi:json", env=connect)
        if held.get("connect"):
            ok("the network through a granted module that needs none "
               "(ffi:json): the kernel refuses the connection",
               "error[E319]" in err, err[-400:])
        else:
            ok(f"the network through ffi:json: not held on {PLATFORM}",
               code == 0 and "succeeded" in err, err[-400:])
        code, out, err = cli(hello, "--allow", "io,ffi:socket", env=connect)
        if PLATFORM == "windows" and RUNTIME == "rust":
            # the hook's connection is made inside the AppContainer, which
            # Windows isolates from the loopback address whatever
            # capability it holds (rt/spikes/appcontainer/README.md). A
            # budget that *names* a loopback host leaves the container off
            # for that reason; one that grants any host does not say it
            # needs the loopback address, so the container stays and this
            # is what it cannot reach from inside. A run's own fetch is
            # made by its host, which can - the case under "nothing
            # legitimate breaks" is that one.
            ok("ffi:socket widens the policy to any host, and the run is "
               "confined all the same: the connection from inside the "
               "AppContainer cannot reach the loopback address",
               "error[E319]" in err and f"confinement: {LEVEL[PLATFORM]}"
               in err, err[-400:])
        else:
            ok("ffi:socket widens the policy to any host, as the table "
               "says: the connection goes through and the run is still "
               "confined",
               code == 0 and "succeeded; confinement: "
               + ("partial" if PLATFORM != "linux" else "full") in err,
               err[-400:])
    finally:
        srv.close()
    spawn = {confine.FAULT_ENV: "spawn"}
    code, out, err = cli(hello, "--allow", "io,ffi:shutil", env=spawn)
    ok("a process through a granted module that needs none (ffi:shutil, "
       "which widens to any path): the kernel refuses it",
       "error[E319]" in err, err[-400:])
    code, out, err = cli(hello, "--allow", "io,ffi:subprocess", env=spawn)
    ok("ffi:subprocess widens to nothing enforced: the process starts, and "
       "the run says its confinement is none",
       code == 0 and "succeeded; confinement: none" in err, err[-400:])

    if PLATFORM == "windows":
        code, out, err = cli(hello, env={confine.FAULT_ENV:
                                         "spawn-breakaway"})
        ok("a process asked to leave the job object "
           "(CREATE_BREAKAWAY_FROM_JOB) is refused", "error[E319]" in err,
           err[-400:])
        r = sabline.run('fn main() uses io {\n    let big = grow("x")\n'
                        '    print(length(big))\n}\n'
                        'fn grow(s: Text) -> Text {\n    let t = s\n'
                        '    let i = 0\n    while i < 40 {\n'
                        '        t = t + t\n        i = i + 1\n    }\n'
                        '    return t\n}\n', timeout=120, max_memory_mb=200)
        ok("a program that exhausts the job's memory is stopped by it "
           "(E611), confined or not", r.out_of_memory
           and r.problems[0].code == "E611",
           [p.as_dict() for p in r.problems])
    if PLATFORM == "linux":
        code, out, err = cli(hello, env={
            confine.FAULT_ENV: "read:/proc/self/root/etc/hostname"})
        ok("/proc/self is readable, and /proc/self/root is still not a way "
           "to the rest of the file system", "error[E319]" in err, err[-400:])
        srv, port = listener()
        srv.close()
        code, out, err = cli(hello, "--allow", f"io,net:localhost:{port}",
                             env={confine.FAULT_ENV: "unix-socket"})
        ok("under a net grant a Unix socket - the way to a container "
           "runtime or the session bus - is still refused",
           "error[E319]" in err, err[-400:])
        code, out, err = cli(hello, "--allow", f"io,net:localhost:{port}",
                             "--no-confine",
                             env={confine.FAULT_ENV: "unix-socket"})
        ok("...and without confinement it is made", "succeeded" in err,
           err[-400:])
        unshare = shutil.which("unshare")
        can = unshare is not None and subprocess.run(
            [unshare, "-rm", "true"], capture_output=True).returncode == 0
        if not can:
            print("  skip     a bind mount (no unprivileged user namespace "
                  "here to make one in)")
        else:
            assert unshare is not None
            target = granted / "mounted"
            target.mkdir(exist_ok=True)
            script = (f'mount --bind "{outside}" "{target}" && '
                      f'"{sys.executable}" "{SABLINE}" "{hello}" --allow '
                      f'"io,fs:read:{granted}"')
            env = dict(os.environ)
            env[confine.FAULT_ENV] = f"read:{target / 'held.txt'}"
            done = subprocess.run([unshare, "-rm", "sh", "-c", script],
                                  capture_output=True, text=True, env=env)
            ok("a bind mount made INSIDE a granted path before the run is "
               "that path's content, to Landlock and to the language alike: "
               "the read goes through (THREAT_MODEL.md, what a granted path "
               "contains)", done.returncode == 0 and "succeeded"
               in done.stderr, done.stderr[-400:])
            env[confine.FAULT_ENV] = f"mount:{outside}:{target}"
            script = (f'"{sys.executable}" "{SABLINE}" "{hello}" --allow '
                      f'"io,fs:read:{granted}"')
            done = subprocess.run([unshare, "-rm", "sh", "-c", script],
                                  capture_output=True, text=True, env=env)
            ok("...and a confined run cannot make one: mount is refused "
               "even to a root of its own namespace",
               "error[E319]" in done.stderr, done.stderr[-400:])
            done = subprocess.run(
                [unshare, "-rm", "sh", "-c", script + " --no-confine"],
                capture_output=True, text=True, env=env)
            ok("...which without confinement it can",
               "succeeded" in done.stderr, done.stderr[-400:])

        probe = subprocess.run(
            [sys.executable, "-c",
             "import sys, threading\n"
             f"sys.path.insert(0, {str(HERE)!r})\n"
             "from sabline import confine\n"
             "from sabline.budget import Budget\n"
             "box = {}\n"
             "def work():\n"
             "    box['done'] = confine.apply(confine.os_policy("
             "Budget.parse('io')))\n"
             "t = threading.Thread(target=work); t.start(); t.join()\n"
             "print(box['done']['level'], '|', box['done']['reason'])\n"
             "try:\n"
             "    open('/etc/hostname').read(); print('MAIN READ IT')\n"
             "except OSError as e:\n"
             "    print('main refused')\n"],
            capture_output=True, text=True)
        ok("confinement applied from a thread that is not the main one, "
           "with no way to reach the main thread, says so: partial, and the "
           "unheld thread is named",
           "partial |" in probe.stdout and "not held by Landlock"
           in probe.stdout, probe.stdout + probe.stderr[-300:])


# ---- --confine strict (9.0, M4; decisions/0006 e) ---------------------------------

def strict_modules(outside: Path) -> tuple[Path, dict[str, str]]:
    """A directory of Python modules a budget grants, each of which does
    something below the language: 19d's vendored nativefmt, whose native
    code fopens a file of its own, and a module that opens and writes a
    file through the C library itself. (the directory, the env that puts it
    on the module path)."""
    where = WORK / "strict_modules"
    where.mkdir(exist_ok=True)
    corpus = HERE / "benchmark" / "corpus" / "19_below_the_language"
    native = (corpus / "d_native_writes" / "nativefmt.py").read_text(
        encoding="utf-8").replace("{path}", (outside / "native.txt")
                                  .as_posix())
    (where / "nativefmt.py").write_text(native, encoding="utf-8")
    (where / "scribble.py").write_text(
        "import ctypes, ctypes.util, os, sys\n"
        "def write(path):\n"
        "    libc = (ctypes.cdll.msvcrt if sys.platform == 'win32' else\n"
        "            ctypes.CDLL(ctypes.util.find_library('c')))\n"
        "    opener = libc._open if sys.platform == 'win32' else libc.open\n"
        "    fd = opener(path.encode(), os.O_WRONLY | os.O_CREAT, 0o600)\n"
        "    if fd >= 0:\n"
        "        libc.write(fd, b'written below the language', 26)\n"
        "        libc.close(fd)\n"
        "    return fd\n", encoding="utf-8")
    return where, {"PYTHONPATH": str(where)}


def strict_cases(runtime: str = "python") -> None:
    print()
    print(f"[{runtime}] --confine strict: a granted module widens nothing")
    print("-" * 62)
    outside = outside_dir()
    _where, env = strict_modules(outside)
    env = dict(env, **runtime_env(runtime))
    # the level the runtime this section is asking gives, which on Windows
    # is sabline-rt's AppContainer and the package's job object and token
    level = LEVEL_BY_RUNTIME[runtime].get(PLATFORM)
    rec = WORK / "strict.json"
    native = outside / "native.txt"
    measure = (HERE / "benchmark" / "corpus" / "19_below_the_language"
               / "d_native_writes.vel")

    def receipt() -> dict[str, Any]:
        # a run that never got as far as its receipt leaves the file empty
        text = rec.read_text(encoding="utf-8") if rec.exists() else ""
        found: dict[str, Any] = (json.loads(text)["predicate"]
                                 if text.strip() else {})
        return found

    def strict_digest(spec: str) -> str:
        return confine.policy_sha256(confine.os_policy(Budget.parse(spec),
                                                       strict=True))

    # 1. 19d: the native fopen outside every grant
    native.unlink(missing_ok=True)
    rec.unlink(missing_ok=True)
    code, out, err = cli(str(measure), "--allow", "io,ffi:nativefmt",
                         "--confine", "strict", "--receipt", str(rec),
                         env=env)
    p = receipt().get("run_parameters") or {}
    ok(f"19d under --confine strict: the module's own work is done, its "
       f"native fopen outside every grant fails, and the receipt says "
       f"{level} with the strict policy (no module widened it)",
       code == 0 and "length 6" in out and not native.exists()
       and p.get("confinement") == level
       and p.get("os_policy_sha256") == strict_digest("ffi:nativefmt,io")
       and "under --confine strict" in p.get("confinement_reason", ""),
       [code, out, err[-500:], p])
    # 2. a module that opens and writes a file through the C library
    target = outside / "scribbled.txt"
    target.unlink(missing_ok=True)
    scribble = program("scribble.vel", f'''
fn main() uses io, ffi {{
    check py_int("scribble", "write", ["{target.as_posix()}"]) {{
        ok fd {{ print(format("descriptor {{}}", fd)) }}
        fail why {{ print("no descriptor: " + why) }}
    }}
}}
''')
    code, out, err = cli(scribble, "--allow", "io,ffi:scribble", "--confine",
                         "strict", env=env)
    ok("a module that opens a file outside the grants through the C library "
       "and writes it: the open is refused by the kernel and nothing is "
       "written", code == 0 and "descriptor -1" in out
       and not target.exists(), [code, out, err[-500:]])
    # 3. ffi:os, and a process that would make a file
    made = outside / "made-by-a-shell.txt"
    made.unlink(missing_ok=True)
    command = (f'cmd /c type nul > "{made}"' if PLATFORM == "windows"
               else f'touch "{made.as_posix()}"')
    shell = program("shell_strict.vel", f'''
fn main() uses io, ffi {{
    check py_int("os", "system", [{json.dumps(command)}]) {{
        ok status {{ print(format("status {{}}", status)) }}
        fail why {{ print("no status: " + why) }}
    }}
}}
''')
    # os.system is posix.system, or nt.system, which the attribute check
    # follows (E311): all three granted, and under strict none widens
    code, out, err = cli(shell, "--allow", "io,ffi:os,ffi:nt,ffi:posix",
                         "--confine", "strict", env=env)
    ok("--confine strict --allow io,ffi:os: os.system's process is refused "
       "by the kernel and the file it would make does not exist",
       code == 0 and "status 0" not in out and "status" in out
       and not made.exists(), [code, out, err[-500:]])
    # 4. the honesty test, under strict with an ffi grant
    written = outside / "written.txt"
    written.unlink(missing_ok=True)
    code, out, err = cli(program("hello.vel", HELLO), "--allow", "io,ffi:os",
                         "--confine", "strict",
                         env=dict(env, **{confine.FAULT_ENV:
                                          f"write:{written}"}))
    ok("SABLINE_FAULT_INJECT=write under --confine strict with ffi:os "
       "granted: E319, exactly as without the grant",
       "error[E319]" in err and not written.exists(), err[-500:])
    # 5. without strict, the default has not moved
    native.unlink(missing_ok=True)
    rec.unlink(missing_ok=True)
    code, out, err = cli(str(measure), "--allow", "io,ffi:nativefmt",
                         "--receipt", str(rec), env=env)
    p = receipt().get("run_parameters") or {}
    ok("without --confine strict 19d runs as it always has - the native "
       "write happens - and the receipt says none, and why",
       code == 0 and "length 6" in out and native.exists()
       and p.get("confinement") == "none"
       and "ffi:nativefmt" in p.get("confinement_reason", ""),
       [code, out, err[-300:], p])
    native.unlink(missing_ok=True)
    code, out, err = cli(scribble, "--allow", "io,ffi:scribble", env=env)
    ok("...and so does the module that writes through the C library",
       code == 0 and "descriptor -1" not in out and target.exists(),
       [code, out, err[-300:]])
    target.unlink(missing_ok=True)
    made.unlink(missing_ok=True)
    code, out, err = cli(shell, "--allow", "io,ffi:os,ffi:nt,ffi:posix",
                         env=env)
    ok("...and os.system's process, which makes its file",
       code == 0 and "status 0" in out and made.exists(),
       [code, out, err[-300:]])
    made.unlink(missing_ok=True)
    code, _out, err = cli(program("hello.vel", HELLO), "--confine", "strict",
                          "--no-confine", env=env)
    ok("--confine strict beside --no-confine asks for two opposite things: "
       "exit 2, saying so", code == 2 and "say one" in err, err[-300:])


# ---- --require-confinement (9.0, M4; decisions/0007 32a) --------------------------

def required_cases(runtime: str = "python") -> None:
    print()
    print(f"[{runtime}] --require-confinement: refused, not warned, below the "
          f"level asked for")
    print("-" * 62)
    env = runtime_env(runtime)
    level = LEVEL_BY_RUNTIME[runtime].get(PLATFORM)
    hello = program("hello.vel", HELLO)
    rec = WORK / "required.json"
    outside = outside_dir()
    written = outside / "written.txt"
    for asked in ("full", "partial"):
        refused = confine.LEVELS.index(level or "none") < \
            confine.LEVELS.index(asked)
        rec.unlink(missing_ok=True)
        written.unlink(missing_ok=True)
        code, out, err = cli(hello, "--require-confinement", asked,
                             "--receipt", str(rec),
                             env=dict(env, **{confine.FAULT_ENV:
                                              f"write:{written}"}))
        p = json.loads(rec.read_text(encoding="utf-8"))["predicate"] \
            if rec.exists() else {}
        rp = p.get("run_parameters") or {}
        if refused:
            ok(f"--require-confinement {asked} on {PLATFORM}, which gives "
               f"io {level}: refused before the first statement, E326, the "
               f"receipt recording the level and the refusal - and the "
               f"fault-injection hook, which only a run allowed to start "
               f"tries, never ran",
               code == 1 and "error[E326]" in err and "ran to the end"
               not in out and rp.get("confinement") == level
               and (p.get("exit") or {}).get("code") == "E326"
               and [r["code"] for r in p.get("refusals", [])] == ["E326"]
               and "fault injection" not in err and not written.exists(),
               [code, out, err[-600:], rp, p.get("exit")])
        else:
            ok(f"--require-confinement {asked} on {PLATFORM}, which gives "
               f"io {level}: it runs, confined as ever",
               "ran to the end" not in out and "error[E319]" in err
               and rp.get("confinement") == level, [code, out, err[-600:]])
    code, out, err = cli(hello, "--allow", "io,ffi:os",
                         "--require-confinement", "partial", env=env)
    ok("--require-confinement partial with ffi:os granted, which widens the "
       "policy to nothing enforced: E326, naming none and why",
       code == 1 and "error[E326]" in err and "gave it none" in err
       and "ffi:os" in err and "ran to the end" not in out, err[-600:])
    code, out, err = cli(hello, "--allow", "io,ffi:os",
                         "--require-confinement", "partial", "--confine",
                         "strict", env=env)
    ok("...and under --confine strict as well it runs: the two compose",
       code == 0 and "ran to the end" in out, err[-600:])
    code, _out, err = cli(hello, "--require-confinement", "partial",
                          "--no-confine", env=env)
    ok("--require-confinement beside --no-confine: exit 2, saying so",
       code == 2 and "say one" in err, err[-300:])
    code, _out, err = cli(hello, "--require-confinement", "most", env=env)
    ok("--require-confinement takes full or partial and nothing else",
       code == 2 and "full or partial" in err, err[-300:])
    if runtime == "rust":
        # from 9.0's M4 sabline-rt confines its own runs: a level asked of
        # it is a level it gives, the run is its own, and nothing is kept in
        # the package for confinement's sake
        rec.unlink(missing_ok=True)
        code, out, err = cli(hello, "--require-confinement", "partial",
                             "--receipt", str(rec), env=env)
        p = (json.loads(rec.read_text(encoding="utf-8"))["predicate"]
             if rec.exists() else {})
        rp = p.get("run_parameters") or {}
        ok("SABLINE_REFERENCE_RUNTIME=rust: a run that asks for a level is "
           "sabline-rt's own, confined by it, and nothing is kept in the "
           "package for it",
           code == 0 and "ran to the end" in out
           and "this run is the Python package's" not in err
           and (p.get("producer") or {}).get("name") == "sabline-rt"
           and rp.get("confinement") == level
           and rp.get("confinement_layers"),
           [code, err[-400:], p.get("producer"), rp])
        # and the host of what it relays is confined too (M4, item 7): the
        # command's own process, which ends with the run. The hook runs in
        # sabline-rt, and a second one in the host would be a second answer;
        # what is held here is that the command's own process is held, which
        # the strict cases above measure through a granted module.
        code, out, err = cli(hello, "--confine", "strict", env=env)
        ok("a command's own process is the host of what the run relays, and "
           "is held to the same policy once sabline-rt has been started",
           code == 0 and "ran to the end" in out, [code, out, err[-400:]])

    # the library and a pool
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        r = sabline.run(HELLO, require_confinement="partial")
        if runtime == "rust":
            # the run is in sabline-rt's process and not this one, so a
            # level asked of an unbounded run is a level it can be given
            # (9.0, M4), where the package's own answer is E326
            ok("sabline.run with no limit through sabline-rt runs in another "
               "process, which can be confined: require_confinement="
               "'partial' is given, and the receipt says the level",
               r.ok and parameters_of(r)["confinement"] == level,
               [parameters_of(r), [q.as_dict() for q in r.problems]])
        else:
            ok("sabline.run with no limit runs in the caller's process, "
               "which nothing confines: require_confinement='partial' "
               "refuses it, E326, and the receipt says none",
               not r.ok and [q.code for q in r.problems] == ["E326"]
               and parameters_of(r)["confinement"] == "none",
               [q.as_dict() for q in r.problems])
        r = sabline.run(HELLO, timeout=60, require_confinement=level)
        ok(f"run(timeout=, require_confinement={level!r}): it runs",
           r.ok and parameters_of(r)["confinement"] == level,
           [p.as_dict() for p in r.problems])
        # with an import root, so that a Linux worker holds reads too
        with sabline.Pool(size=1, timeout=60, import_root=str(WORK),
                          require_confinement="full") as pool:
            r = pool.run(HELLO)
        if level == "full":
            ok("a Pool made with require_confinement='full': it runs",
               r.ok, [p.as_dict() for p in r.problems])
        else:
            ok(f"a Pool made with require_confinement='full' on {PLATFORM}: "
               f"each run refused, E326, its receipt saying {level}",
               not r.ok and [p.code for p in r.problems] == ["E326"]
               and parameters_of(r)["confinement"] == level,
               [p.as_dict() for p in r.problems])
        r = sabline.run(HELLO, timeout=60, allow="io,ffi:os",
                        confine="strict", require_confinement="partial")
        ok("run(confine='strict', require_confinement='partial') with ffi:os: "
           "it runs, at this platform's level", r.ok
           and parameters_of(r)["confinement"] == level,
           [p.as_dict() for p in r.problems])
        bad = []
        for kw in ({"confine": "lax"}, {"require_confinement": "most"},
                   {"confine": False, "require_confinement": "full"}):
            try:
                sabline.run(HELLO, **kw)
                bad.append(kw)
            except ValueError:
                pass
        ok("a mode or a level that is not one, and confine=False beside a "
           "level asked for, are ValueError", not bad, bad)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def runtime_env(runtime: str) -> dict[str, str]:
    """What a child is started with to choose its runtime (9.0)."""
    return {"SABLINE_REFERENCE_RUNTIME": runtime}


# ---- every escape target, with the language's refusals knocked out ---------------

def targets() -> list[dict[str, Any]]:
    import check_sandbox
    out = [dict(case, suite="check_sandbox") for case in check_sandbox.ESCAPES]
    import check_adversarial
    for label, source, allow in check_adversarial.FFI:
        out.append({"suite": "check_adversarial", "id": label.split()[0],
                    "name": label, "source": source + "\n", "allow": allow,
                    "deny": None, "args": [], "creates": None,
                    "requires": []})
    for label, path in (("FS1 dotdot", "../../outside.txt"),
                        ("FS2 abs sibling", "{OUTSIDE}")):
        out.append({"suite": "check_adversarial", "id": label.split()[0],
                    "name": label, "allow": "io,fs:read:{DATA}", "deny": None,
                    "source": check_adversarial._read_prog(f'"{path}"'),
                    "args": [], "creates": None, "requires": [],
                    "cwd": "{DATA}"})
    return out


# what a target prints once the effect itself has happened. Not the words it
# prints on catching a failure: with the language's refusal knocked out, the
# kernel's is an ordinary failure a program may catch, and the effect still
# did not happen
MARKERS = ("READ IT", "WROTE IT", "REACHED IT", "CALLED IT", "OPENED IT",
           "GOT THROUGH", "FOLLOWED IT", "LEAK:", "REACHED", "GOT HANDLE")


def target_cases(record: bool) -> None:
    import check_sandbox
    print()
    print("every escape target, on a Sabline whose budget checks are "
          "knocked out")
    print("-" * 62)
    root = Path(tempfile.mkdtemp(prefix="sabline-confine-targets-",
                                 dir=str(outside_dir())))
    srv_a, srv_b, port_a, port_b = check_sandbox.local_servers()
    values = check_sandbox.fixture(root, (port_a, port_b), symlink=True)
    rows = []
    try:
        for case in targets():
            if "symlink" in case["requires"] and not values["_symlink"]:
                continue
            prog = root / "_target.vel"
            prog.write_text(check_sandbox.fill(case["source"], values),
                            encoding="utf-8")
            flags = []
            if case["allow"] is not None:
                flags += ["--allow", check_sandbox.fill(case["allow"], values)]
            if case["deny"] is not None:
                flags += ["--deny", check_sandbox.fill(case["deny"], values)]
            creates = check_sandbox.fill(case["creates"], values)
            cwd = check_sandbox.fill(case.get("cwd"), values) or str(root)

            def got_through(*more: str) -> bool:
                if creates:
                    Path(creates).unlink(missing_ok=True)
                _code, out, _err = cli(str(prog), *flags, *more, cwd=cwd,
                                       faulty=True)
                through = any(m in out for m in MARKERS) or bool(
                    creates and Path(creates).exists())
                if creates:
                    Path(creates).unlink(missing_ok=True)
                return through

            unconfined = got_through("--no-confine")
            confined = got_through() if unconfined else False
            rows.append({"suite": case["suite"], "id": case["id"],
                         "name": case["name"],
                         "stopped_by": ("not applicable" if not unconfined
                                        else "language only" if confined
                                        else "kernel")})
    finally:
        for srv in (srv_a, srv_b):
            srv.shutdown()
        shutil.rmtree(root, ignore_errors=True)
    kernel = [r for r in rows if r["stopped_by"] == "kernel"]
    language = [r for r in rows if r["stopped_by"] == "language only"]
    other = [r for r in rows if r["stopped_by"] == "not applicable"]
    for r in rows:
        print(f"  {r['stopped_by']:<15}{r['id']:<28}{r['name']}")
    print(f"  {len(kernel)} now fail at the kernel as well as at the "
          f"language, {len(language)} at the language alone, {len(other)} "
          f"not applicable (refused before running, or not an effect)")
    ok("with its budget checks knocked out and no confinement, an escape "
       "gets through: the measurement measures something",
       len(kernel) + len(language) > 10, rows)
    floor = {"linux": 12, "macos": 8, "windows": 3}.get(PLATFORM, 0)
    ok(f"on {PLATFORM} the kernel stops at least {floor} of them",
       len(kernel) >= floor, [r["id"] for r in kernel])
    kept = HERE / "tests" / "confine" / f"kernel-{PLATFORM}.json"
    if record:
        kept.write_text(json.dumps(
            {"platform": PLATFORM, "sabline": sabline.VERSION,
             "kernel": len(kernel), "language_only": len(language),
             "not_applicable": len(other), "targets": rows}, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"  recorded in {kept.relative_to(HERE).as_posix()}")
    elif kept.exists():
        recorded = json.loads(kept.read_text(encoding="utf-8"))
        before = {(r["suite"], r["id"]): r["stopped_by"]
                  for r in recorded["targets"]}
        worse = [r["id"] for r in rows
                 if before.get((r["suite"], r["id"])) == "kernel"
                 and r["stopped_by"] == "language only"]
        ok("no target the recorded run had stopped at the kernel gets "
           "through it now", not worse, worse)


# ---- the Windows AppContainer (9.0, M4) --------------------------------------------

APPCONTAINER_SID = re.compile(r"S-1-15-2-[-0-9]+")


def container_aces(path: Path) -> list[str]:
    """Every AppContainer SID the rights of `path` name, as icacls prints
    them: what a run's parent grants and takes back."""
    try:
        done = subprocess.run(["icacls", str(path)], capture_output=True,
                              text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(set(APPCONTAINER_SID.findall(done.stdout)))


def appcontainer_cases() -> None:
    """sabline-rt starts the run's own process inside an AppContainer, and
    every claim that rests on it (9.0, M4). The honesty test above already
    measures what the container refuses; these are the container's own
    promises: that the ACEs it is given are taken back, that a run killed
    before it can is swept by the next one, that `--contained` is a claim
    the kernel answers, and that the budgets it is left off for say so."""
    print()
    print("the Windows AppContainer: its ACEs, its sweep and its claim")
    print("-" * 62)
    data = WORK / "container-data"
    data.mkdir(exist_ok=True)
    (data / "a.txt").write_text("inside the grant", encoding="utf-8")
    grant = f"io,fs:read:{data.as_posix()}"
    hello = program("hello.vel", HELLO)
    rec = WORK / "container.json"

    def parameters() -> dict[str, Any]:
        text = rec.read_text(encoding="utf-8") if rec.exists() else ""
        found: dict[str, Any] = (json.loads(text)["predicate"]
                                 ["run_parameters"] if text.strip() else {})
        return found

    # What the container was given, said two ways, because a run refused a
    # file its budget grants is a wrong answer and not a safe one: the
    # kernel lets the run read what it was given an ACE for, and the
    # language's own resolution of that path inside the container is the
    # one the host resolved the grant to. The second is the one that bit:
    # the host resolves the budget (`Budget.spec()`), the run resolves what
    # the program names, and a container that cannot resolve answers a path
    # the grant does not cover.
    inside = Budget.parse(grant).spec()
    code, out, err = cli(hello, "--allow", grant,
                         env={confine.FAULT_ENV: f"read:{data / 'a.txt'}"})
    ok("the hook's read of a file inside the grant goes through: the ACE "
       "the container was given is one the kernel honours",
       code == 0 and "succeeded" in err and "ran to the end" in out,
       [code, err[-400:], inside])
    reader = program("granted.vel", f'''
fn main() uses io, fs {{
    check read_file("{(data / "a.txt").as_posix()}") {{
        ok body {{ print("read: " + body) }}
        fail why {{ print("could not read: " + why) }}
    }}
}}
''')
    code, out, err = cli(reader, "--allow", grant)
    ok("...and a program reads it under the same grant: the run resolves "
       "the path inside the container as its host resolved the grant",
       code == 0 and "read: inside the grant" in out,
       [code, err[-500:], f"the host's grant: {inside}"])

    before = container_aces(data)
    rec.unlink(missing_ok=True)
    code, out, err = cli(hello, "--allow", grant, "--receipt", str(rec))
    p = parameters()
    ok("a run under a read grant is held by a container of its own: full, "
       "with the appcontainer layer named",
       code == 0 and "ran to the end" in out and p.get("confinement")
       == "full" and "appcontainer" in (p.get("confinement_layers") or []),
       [code, err[-400:], p])
    ok("...and every ACE it was given is taken back when it ends",
       container_aces(data) == before, container_aces(data))

    # two runs at once over one granted directory. Adding an ACE is read
    # the rights, add to them, write them back, so two runs doing it to one
    # file at the same time would lose one of the two ACEs and refuse that
    # run a file its budget grants. check_self_budget.py found it; this is
    # the case that keeps it found.
    reader = program("reader.vel", f'''
fn main() uses io, fs {{
    check read_file("{(data / "a.txt").as_posix()}") {{
        ok body {{ print("read: " + body) }}
        fail why {{ print("could not read: " + why) }}
    }}
}}
''')
    together: list[tuple[int, str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for answer in [f.result() for f in [
                pool.submit(cli, reader, "--allow", grant) for _ in range(6)]]:
            together.append(answer)
    ok("six runs at once over one granted directory each read it: an ACE "
       "is added under a lock, so no run loses another's",
       all(code == 0 and "read: inside the grant" in out
           for code, out, _err in together),
       [(c, o, e[-200:]) for c, o, e in together if c != 0
        or "read: inside the grant" not in o][:2])
    ok("...and every one of their ACEs is gone afterwards",
       container_aces(data) == before, container_aces(data))

    # a run killed before it can take them back, and the next run's sweep
    waiting = program("waiting.vel", 'fn main() uses io {\n'
                      '    let line = read_line()\n'
                      '    print(line)\n}\n')
    full = dict(os.environ)
    full.pop(confine.FAULT_ENV, None)
    full["SABLINE_REFERENCE_RUNTIME"] = RUNTIME
    killed = subprocess.Popen([sys.executable, SABLINE, waiting, "--allow",
                               grant], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=full)
    left: list[str] = []
    for _ in range(200):
        left = [s for s in container_aces(data) if s not in before]
        if left:
            break
        time.sleep(0.1)
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(killed.pid)],
                   capture_output=True, timeout=60)
    killed.wait(timeout=60)
    if killed.stdin:
        killed.stdin.close()
    ok("a run that is killed leaves the ACE it was holding behind - which "
       "is why something has to take it back", left, container_aces(data))
    cli(hello, "--allow", grant)
    ok("...and the next run sweeps it: no ACE of a profile that is gone is "
       "left on the granted directory",
       container_aces(data) == before, container_aces(data))

    # --contained is a claim, and the kernel answers it
    exe = through_rt.binary()
    if not exe:
        print("  skip     sabline-rt is not built here, so --contained "
              "cannot be asked")
    else:
        request = json.dumps({"path": hello, "allow": "io", "confine": True})
        # standard input is held open until the end frame: a parent that
        # goes away before it is a parent gone, which the run exits 3 for
        child = subprocess.Popen(
            [exe, "exec", "--install-dir", str(HERE),
             "--contained", "S-1-15-2-1-2-3-4-5-6-7-8"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, errors="replace")
        ending: list[dict[str, Any]] = []
        try:
            assert child.stdin and child.stdout
            child.stdin.write(request + "\n")
            child.stdin.flush()
            for line in child.stdout:
                if line.startswith("{") and '"end"' in line:
                    ending.append(json.loads(line)["end"])
                    break
        finally:
            if child.stdin:
                child.stdin.close()
            child.wait(timeout=120)
        got = (ending[0]["receipt"]["predicate"]["run_parameters"]
               if ending else {})
        ok("sabline-rt exec --contained outside a container claims nothing: "
           "the kernel is asked, the level is not full, and the reason says "
           "this token is not an AppContainer's",
           got.get("confinement") == "partial"
           and "not an AppContainer's" in got.get("confinement_reason", "")
           and "appcontainer" not in (got.get("confinement_layers") or []),
           got)

    # the budgets a container is left off for, each saying so
    for allow, says in (
            (f"io,net:localhost:1,fs:read:{data.as_posix()}", "loopback"),
            ("io,fs:read", "does not restrict reads"),
            ("io,fs:write", "does not restrict writes")):
        rec.unlink(missing_ok=True)
        code, out, err = cli(hello, "--allow", allow, "--receipt", str(rec))
        p = parameters()
        ok(f"--allow {allow}: no container, the receipt's reason saying "
           f"why ({says})",
           code == 0 and p.get("confinement") == "partial"
           and says in p.get("confinement_reason", "")
           and "appcontainer" not in (p.get("confinement_layers") or []),
           [code, err[-300:], p])


# ---- a kernel with no Landlock, simulated (9.0, M4) --------------------------------

NO_LANDLOCK = "SABLINE_FAULT_NO_LANDLOCK"


def no_landlock_cases() -> None:
    """The leg plan/9.0.md asks for and no runner has: a Linux kernel
    without Landlock. There is no honest way to take Landlock off a kernel
    that has it, and a self-hosted runner is not worth one machine
    (decided on 2026-10-13), so sabline-rt's fault-injection hook is asked
    to take the path a kernel with no Landlock would: the ruleset is not
    built, the layer reports it, seccomp-bpf is applied as ever, and the
    level is what such a machine gives. **It is a simulation**: what it
    measures is this runtime's own no-Landlock path, not a kernel's.

    The variable is behind the crate's `fault-inject` feature, which is off
    by default, so a released binary cannot be asked to stand a layer
    down - which is what `check_self_budget.py` exists to refuse."""
    print()
    print("a kernel with no Landlock, simulated by the fault-injection hook")
    print("-" * 62)
    hello = program("hello.vel", HELLO)
    rec = WORK / "no-landlock.json"
    outside = outside_dir()
    held = outside / "held.txt"
    held.write_text("outside every grant", encoding="utf-8")
    off = {NO_LANDLOCK: "1"}

    def parameters() -> dict[str, Any]:
        text = rec.read_text(encoding="utf-8") if rec.exists() else ""
        found: dict[str, Any] = (json.loads(text)["predicate"]
                                 ["run_parameters"] if text.strip() else {})
        return found

    rec.unlink(missing_ok=True)
    code, out, err = cli(hello, "--receipt", str(rec), env=off)
    p = parameters()
    layers = p.get("confinement_layers") or []
    if p.get("confinement") == "full":
        print("  skip     this sabline-rt was built without its "
              "fault-inject feature, so Landlock cannot be stood down")
        return
    ok("with Landlock stood down the run is partial, the reason says this "
       "kernel has no Landlock, and seccomp is the only layer left",
       code == 0 and "ran to the end" in out
       and p.get("confinement") == "partial"
       and "no Landlock" in p.get("confinement_reason", "")
       and any(name.startswith("seccomp") for name in layers)
       and not any(name.startswith("landlock") for name in layers),
       [code, err[-300:], p])
    code, out, err = cli(hello, env=dict(off, **{
        confine.FAULT_ENV: f"read:{held}"}))
    ok("...so a read outside every grant goes through, which Landlock is "
       "what holds", code == 0 and "succeeded" in err
       and "ran to the end" in out, err[-400:])
    written = outside / "written.txt"
    written.unlink(missing_ok=True)
    code, out, err = cli(hello, env=dict(off, **{
        confine.FAULT_ENV: f"write:{written}"}))
    ok("...and so does a write, for the same reason",
       code == 0 and "succeeded" in err and written.exists(), err[-400:])
    written.unlink(missing_ok=True)
    srv, port = listener()
    try:
        code, out, err = cli(hello, env=dict(off, **{
            confine.FAULT_ENV: f"connect:127.0.0.1:{port}"}))
        ok("...while seccomp still refuses the network with no net grant",
           "error[E319]" in err, err[-400:])
    finally:
        srv.close()
    code, out, err = cli(hello, env=dict(off, **{
        confine.FAULT_ENV: "spawn"}))
    ok("...and still refuses a process", "error[E319]" in err, err[-400:])
    code, out, err = cli(hello, "--require-confinement", "full", env=off)
    ok("--require-confinement full refuses such a run before its first "
       "statement, E326, naming the kernel's missing Landlock",
       code == 1 and "error[E326]" in err and "no Landlock" in err
       and "ran to the end" not in out, err[-500:])
    rec.unlink(missing_ok=True)
    code, out, err = cli(hello, "--receipt", str(rec))
    ok("...and the same run on this machine, which has Landlock, is full: "
       "the leg measures a difference", parameters().get("confinement")
       == "full", parameters())


def describe_macos() -> None:
    """On macOS, what the profile is built from, for whoever reads a failed
    leg: where Python is, as named and as resolved, and the profile itself."""
    print("macOS: what the sandbox profile is built from")
    print("-" * 62)
    for name in ("prefix", "base_prefix", "exec_prefix", "executable"):
        value = str(getattr(sys, name))
        print(f"  sys.{name}: {value} -> {os.path.realpath(value)}")
    print(f"  home: {Path.home()} -> {os.path.realpath(Path.home())}")
    print(f"  os.__file__: {os.__file__} -> {os.path.realpath(os.__file__)}")
    profile = confine.mac_profile(confine.os_policy(Budget.parse("io")), [],
                                  [], None)
    for line in profile.splitlines():
        print("  " + line[:1500])
    # is a file the profile allows again, under the home directory it
    # denies, readable? Python's own os.py, and its compiled copy
    hello = program("describe.vel", HELLO)
    import importlib.util
    for target in (os.__file__, importlib.util.cache_from_source(os.__file__)):
        _code, _out, err = cli(hello, env={confine.FAULT_ENV: f"read:{target}"})
        print(f"  a read of {target}: {err.strip().splitlines()[0][:300]}")
    print()


def windows_container() -> tuple[str, str]:
    """Whether a run through sabline-rt on **this** Windows is held by an
    AppContainer of its own, and what its receipt said (9.0, M4).

    It is not a given. `sabline-rt exec` asks the container, before it
    hands a run to one, whether a process inside it resolves a path as
    this one does; where it does not - some systems answer nothing to
    `GetFinalPathNameByHandle` inside a container - the container is left
    off, because a run that resolved a path differently from the host that
    resolved its grants would be refused a file its budget allows. So this
    suite asks the machine rather than assuming, and holds every case to
    the answer: the level, the layers and the reason are all read from the
    receipt, and the reason is printed either way."""
    data = WORK / "container-probe"
    data.mkdir(exist_ok=True)
    (data / "a.txt").write_text("inside the grant", encoding="utf-8")
    rec = WORK / "container-probe.json"
    rec.unlink(missing_ok=True)
    cli(program("probe.vel", HELLO), "--allow",
        f"io,fs:read:{data.as_posix()}", "--receipt", str(rec))
    text = rec.read_text(encoding="utf-8") if rec.exists() else ""
    p = ((json.loads(text)["predicate"]["run_parameters"])
         if text.strip() else {})
    layers = p.get("confinement_layers") or []
    return (str(p.get("confinement")) if "appcontainer" in layers else "",
            str(p.get("confinement_reason") or "no receipt"))


def main() -> int:
    record = "--record" in sys.argv[1:]
    if PLATFORM == "macos":
        describe_macos()
    print(f"the runtime every run goes through: {RUNTIME}")
    if PLATFORM == "windows" and RUNTIME == "rust":
        level, why = windows_container()
        if level:
            print(f"  listed  a run here is held by an AppContainer of its "
                  f"own, and is {level}")
        else:
            # the package's own row, which is what this machine gives
            HELD.update(HELD_BY_RUNTIME["python"])
            LEVEL.update(LEVEL_BY_RUNTIME["python"])
            print(f"  listed  a run here is NOT held by an AppContainer, so "
                  f"every case below is held to what this package's own "
                  f"runtime gives: {why}")
    if RUNTIME == "python":
        # this module's own derivations, which sabline-rt derives too and
        # the agreement gate compares field for field: asking them again
        # with the variable set would ask the same Python the same question
        policy_cases()
        filter_cases()
        table_cases()
    honesty_cases()
    legitimate_cases()
    reported_cases()
    unreachable_cases()
    against_cases()
    if PLATFORM == "windows" and RUNTIME == "rust":
        if LEVEL["windows"] == "full":
            appcontainer_cases()
        else:
            print()
            print("  skip     the Windows AppContainer's own promises (no "
                  "container is used on this machine)")
    if PLATFORM == "linux" and RUNTIME == "rust":
        no_landlock_cases()
    strict_cases(RUNTIME)
    required_cases(RUNTIME)
    if RUNTIME == "python":
        # with SABLINE_REFERENCE_RUNTIME=rust as well, so that one run of
        # this suite asks both runtimes the two options' questions
        strict_cases("rust")
        required_cases("rust")
        # the escape targets are measured on a Sabline whose Python budget
        # checks are knocked out (tests/confine/faulty_runtime.py), which is
        # this package's interpreter and nothing sabline-rt has
        target_cases(record)
    print("-" * 62)
    print(f"{PASSED} passed, {FAILED} broken ({RUNTIME})")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
