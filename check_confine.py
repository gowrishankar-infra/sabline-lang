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
             --no-confine every one goes through. Through the command line,
             run(timeout=), a Pool and the HTTP door
  legitimate reads and writes inside a grant, a name resolved and a request
             made under a net grant, a temporary file under ffi:tempfile, a
             proof and native code made inside a confined pool worker
  reported   the receipt's level, reason, layers and policy digest; the
             audit's confinement; `velaris doctor`; `velaris receipts diff`
             naming a level that changed; eval refusing to run at none
  unreachable --no-confine after `--`, in a door's request, and in a
             program's own words changes nothing
  against it a symbolic link and a bind mount inside a granted path, the
             network and a process through a granted ffi module, a process
             asked to leave the Windows job, a mount, another thread
  the targets every escape of check_sandbox.py, and the file and ffi
             targets of check_adversarial.py, run on a Velaris whose budget
             checks are knocked out (tests/confine/faulty_runtime.py): which
             the kernel stops, and which the language alone does. --record
             writes tests/confine/kernel-<platform>.json

    python check_confine.py [--record]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VELARIS = str(HERE / "velaris.py")
FAULTY = str(HERE / "tests" / "confine" / "faulty_runtime.py")
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from velaris import confine  # noqa: E402
from velaris.budget import Budget  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_confine")
PLATFORM = confine._platform()
PASSED = FAILED = 0

# What each system's row of THREAT_MODEL.md's table says of the hook's
# attempts under the default budget, io: True is "the kernel refuses it".
HELD = {
    "linux": {"read": True, "write": True, "connect": True, "spawn": True,
              "signal": True},
    "macos": {"read": True, "write": True, "connect": True, "spawn": True,
              "signal": False},
    "windows": {"read": False, "write": True, "connect": False,
                "spawn": True, "signal": False},
}
LEVEL = {"linux": "full", "macos": "partial", "windows": "partial"}


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
    full.update(env or {})
    done = subprocess.run(
        [sys.executable, FAULTY if faulty else VELARIS, *words],
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
        made = Path(tempfile.mkdtemp(prefix=".velaris-check-confine-",
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
    ok(f"this system gives a run under io the level its row says: "
       f"{LEVEL.get(PLATFORM)}", would["level"] == LEVEL.get(PLATFORM), would)


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
    print("THREAT_MODEL.md prints the table this module holds")
    print("-" * 62)
    text = (HERE / "THREAT_MODEL.md").read_text(encoding="utf-8")
    missing = [row[0] for row in confine.ENFORCES
               if "| " + " | ".join(row) + " |" not in text]
    ok("every row of confine.ENFORCES is a row of THREAT_MODEL.md, word for "
       "word", not missing, missing)
    missing = [row[0] for row in confine.EXEMPT
               if "| " + " | ".join(row) + " |" not in text]
    ok("...and every exemption of confine.EXEMPT", not missing, missing)
    listed = sorted(m for m, w in confine.FFI_WIDENS.items() if w)
    missing = [m for m in listed if f"`{m}`" not in text]
    ok("...and every module that widens the policy is named there",
       not missing, missing)


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
            r = velaris.run(HELLO, timeout=60)
            ok("run(timeout=): the write is refused by the kernel (E319)",
               not r.ok and r.problems and r.problems[0].code == "E319"
               and not written.exists(),
               [p.as_dict() for p in r.problems])
            with velaris.Pool(size=1, timeout=60) as pool:
                r = pool.run(HELLO)
            ok("a Pool: the write is refused by the kernel (E319)",
               not r.ok and r.problems and r.problems[0].code == "E319"
               and not written.exists(),
               [p.as_dict() for p in r.problems])
            r = velaris.run(HELLO, timeout=60, confine=False)
            ok("run(timeout=, confine=False): it goes through",
               r.ok and written.exists(), [p.as_dict() for p in r.problems])
            written.unlink(missing_ok=True)
            with velaris.Pool(size=1, timeout=60, confine=False) as pool:
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
    check py("tempfile", "mkdtemp", ["-velaris"]) {
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
    with velaris.Pool(size=1, timeout=120) as pool:
        first = pool.run(HELLO)             # the worker is confined by now
        checked = pool.check(proved)
        ran = pool.run(proved)
    ok("a pool worker confined at its start still proves (Z3, when it is "
       "installed) and runs native code",
       first.ok and checked.ok and ran.ok and ran.output.strip() == "42"
       and (not velaris.HAVE_Z3 or "double" in checked.proven),
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
    r = velaris.run(HELLO)
    params = parameters_of(r)
    ok("a run in the caller's own process says none, and that it is "
       "because the caller's process is not Velaris's to confine",
       params["confinement"] == "none" and "caller's own process"
       in params["confinement_reason"], params)
    r = velaris.run(HELLO, timeout=60)
    params = parameters_of(r)
    ok("run(timeout=) is confined as the command line is",
       params["confinement"] == LEVEL.get(PLATFORM)
       and params["os_policy_sha256"] == a["os_policy_sha256"], params)
    r = velaris.run("fn main() uses io {\n    print(1 +)\n}\n", timeout=60)
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

    doc = velaris.audit(HELLO).as_dict()
    systems = (doc.get("confinement") or {}).get("systems") or {}
    ok("the audit reports what a run under its safe_command gets on each "
       "system, with the reason: full on Linux, partial on macOS and on "
       "Windows",
       {k: v.get("level") for k, v in systems.items()} == LEVEL
       and all(v.get("reason") for v in systems.values()), systems)
    ok("...reading nothing of the machine: the same bytes wherever it is "
       "made", "platform" not in doc["confinement"]
       and not any(str(WORK) in json.dumps(v) for v in systems.values()),
       doc["confinement"])
    shell = ('fn main() uses io, ffi {\n'
             '    check py("subprocess", "getoutput", ["echo x"]) {\n'
             '        ok v { print(v) }\n        fail w { print(w) }\n'
             '    }\n}\n')
    doc = velaris.audit(shell).as_dict()
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
    ok("velaris doctor reports the level, and the reason when it is not "
       "full", f"confinement: {LEVEL.get(PLATFORM)}" in out
       and (LEVEL.get(PLATFORM) == "full" or "why:" in out), out)

    from velaris.evaluation import EvalRefused, _EvalPool

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
    ok("velaris eval refuses to run on a worker whose confinement is none, "
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
    ok("velaris eval refuses the flag", code == 2 and "--no-confine" in err,
       err)

    token = "confine-" + os.urandom(12).hex()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    door = subprocess.Popen(
        [sys.executable, VELARIS, "serve", "--port", str(port)],
        env=dict(os.environ, VELARIS_TOKEN=token, **fault),
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
           and level == LEVEL.get(PLATFORM), f"{status} {answer}")
    finally:
        door.terminate()
        door.wait(timeout=30)


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
        ok("ffi:socket widens the policy to any host, as the table says: "
           "the connection goes through and the run is still confined",
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
        r = velaris.run('fn main() uses io {\n    let big = grow("x")\n'
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
                      f'"{sys.executable}" "{VELARIS}" "{hello}" --allow '
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
            script = (f'"{sys.executable}" "{VELARIS}" "{hello}" --allow '
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
             "from velaris import confine\n"
             "from velaris.budget import Budget\n"
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
    print("every escape target, on a Velaris whose budget checks are "
          "knocked out")
    print("-" * 62)
    root = Path(tempfile.mkdtemp(prefix="velaris-confine-targets-",
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
            {"platform": PLATFORM, "velaris": velaris.VERSION,
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


def describe_macos() -> None:
    """On macOS, what the profile is built from, for whoever reads a failed
    leg: where Python is, as named and as resolved, and the profile itself."""
    print("macOS: what the sandbox profile is built from")
    print("-" * 62)
    for name in ("prefix", "base_prefix", "exec_prefix", "executable"):
        value = str(getattr(sys, name))
        print(f"  sys.{name}: {value}
    resolves to {os.path.realpath(value)}")
    print(f"  home: {Path.home()} -> {os.path.realpath(Path.home())}")
    print(f"  os.__file__: {os.__file__} -> {os.path.realpath(os.__file__)}")
    profile = confine.mac_profile(confine.os_policy(Budget.parse("io")), [],
                                  [], None)
    for line in profile.splitlines():
        print("  " + line[:1500])
    print()


def main() -> int:
    record = "--record" in sys.argv[1:]
    if PLATFORM == "macos":
        describe_macos()
    policy_cases()
    filter_cases()
    table_cases()
    honesty_cases()
    legitimate_cases()
    reported_cases()
    unreachable_cases()
    against_cases()
    target_cases(record)
    print("-" * 62)
    print(f"{PASSED} passed, {FAILED} broken")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
