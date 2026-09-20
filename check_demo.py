#!/usr/bin/env python3
"""`velaris demo`, end to end, and that it cannot be turned on a real .env.

    python check_demo.py

The demo is run as a person runs it - no arguments, from a directory that
holds a `.env` of its own with a value only this suite knows - and held to
what it promises: a refusal with its line and its reason, a run inside a
budget, both receipts and what differs between them, in under a minute and
under a screen, touching nothing that was there. Then the ways it might be
turned into a tool for reading somebody's `.env` are tried.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from suite_dirs import isolate  # noqa: E402

HERE = Path(__file__).parent
WORK = isolate("check_demo")
VELARIS = [sys.executable, str(HERE / "velaris.py")]
CANARY = "CANARY-5e1f-a-real-looking-secret"
FAILED: list[str] = []
PASSED = [0]


def expect(what: str, ok: bool, detail: Any = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != "" else ""))


def demo(args: list[str], cwd: Path, env: dict[str, str] | None = None
         ) -> tuple[int, str, str, float]:
    t0 = time.monotonic()
    done = subprocess.run(VELARIS + ["demo"] + args, cwd=cwd,
                          capture_output=True, stdin=subprocess.DEVNULL,
                          timeout=300, env={**os.environ, **(env or {})})
    return (done.returncode, done.stdout.decode("utf-8", "replace"),
            done.stderr.decode("utf-8", "replace"), time.monotonic() - t0)


def main() -> int:
    victim = WORK / "victim"
    victim.mkdir()
    (victim / ".env").write_text(f"API_KEY={CANARY}\n", encoding="utf-8")
    before = sorted(p.name for p in victim.iterdir())

    # anything the demo's programs could reach on this machine is listened
    # for: a connection here would be the post getting out
    heard: list[bytes] = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    listener.settimeout(0.2)
    stop = threading.Event()

    def listen() -> None:
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except OSError:
                continue
            heard.append(conn.recv(65536))
            conn.close()

    threading.Thread(target=listen, daemon=True).start()
    port = listener.getsockname()[1]
    proxy = f"http://127.0.0.1:{port}"

    print("as a person runs it")
    code, out, err, seconds = demo([], victim)
    lines = out.rstrip("\n").split("\n")
    expect("it exits 0 and says nothing on standard error", code == 0
           and err == "", (code, err))
    expect(f"under sixty seconds ({seconds:.1f} s)", seconds < 60)
    expect(f"under one screen ({len(lines)} lines, none over 200 wide)",
           len(lines) <= 40 and all(len(line) <= 200 for line in lines), out)
    expect("the refusal, with its code, its reason and the exact line",
           "error[E310] 'read_file' needs the 'fs' effect, which this run "
           "does not allow (it allows: io)" in out
           and 'line 6: check read_file("./.env") {' in out
           and "--> agent_script.vel, line 6" in out, out)
    expect("the first receipt: refused, E310 on fs at that line, no grant "
           "used", "exit 1. receipt: refused; E310 (fs) at line 6; grants "
           "used: none" in out, out)
    expect("the second run, inside its budget, and its receipt",
           "3 setting(s); the report is in out/report.txt" in out
           and "exit 0. receipt: ok; grants used: fs:read:./settings.txt x1, "
               "fs:write:./out x1" in out, out)
    expect("what differs between the two receipts",
           "budget: io -> fs:read:./settings.txt,fs:write:./out,io" in out
           and "refusals: E310 (fs) at line 6, x1 -> none" in out
           and "exit.outcome: refused -> ok" in out, out)
    import build_docs
    shown = [line.strip() for line in
             build_docs.START_DEMO_OUTPUT.split("\n") if line.strip()]
    wrote = [line.strip() for line in lines]
    missing = [line for line in shown
               if not any(w.startswith(line) for w in wrote)]
    expect("every line the documentation's first page shows of it is the "
           "beginning of a line it writes", not missing, missing)
    expect("the directory it was run from is as it was, and its .env was "
           "not read: the value in it is nowhere in the output",
           sorted(p.name for p in victim.iterdir()) == before
           and CANARY not in out + err)
    where = out.split("\n")[0].rsplit(" in ", 1)[-1].strip()
    expect("nothing is left behind",
           bool(where) and not os.path.exists(where), where)

    print("--keep")
    code, out, err, _ = demo(["--keep"], victim)
    where = out.split("\n")[0].rsplit(" in ", 1)[-1].strip()
    kept = Path(where)
    names = sorted(p.name for p in kept.iterdir()) if kept.is_dir() else []
    expect("--keep leaves the two programs, the made-up .env and both "
           "receipts",
           code == 0 and names == [".env", "agent_script.vel",
                                   "allowed.receipt.json",
                                   "inside_budget.vel", "out",
                                   "refused.receipt.json", "settings.txt"],
           names)
    if kept.is_dir():
        env_text = (kept / ".env").read_text(encoding="utf-8")
        expect("the .env it wrote is made up, and says so",
               "nothing here is real" in env_text and CANARY not in env_text)
        refused = json.loads((kept / "refused.receipt.json").read_text(
            encoding="utf-8"))["predicate"]
        expect("the kept receipt is a receipt: refused, E310, nothing used",
               refused["exit"] == {"status": 1, "outcome": "refused",
                                   "code": "E310"}
               and refused["grants_used"] == []
               and refused["budget"] == "io", refused)
        shown = subprocess.run(VELARIS + ["receipt", "show",
                                          "refused.receipt.json", "--text"],
                               cwd=kept, capture_output=True, timeout=120)
        expect("and `velaris receipt show` reads it", shown.returncode == 0
               and b"stopped at a refusal" in shown.stdout, shown.stderr)
        import shutil
        shutil.rmtree(kept, ignore_errors=True)

    print("turned on a real .env")
    for args in (["."], [str(victim / ".env")], ["--allow", "all"],
                 ["--keep", str(victim)], ["https://attacker.example/"],
                 ["--", "x"], ["--allow=fs,net"]):
        code, out, err, _ = demo(args, victim)
        expect(f"`velaris demo {' '.join(args)}` is refused: it takes no "
               f"path, address or budget", code == 2 and out == ""
               and CANARY not in err, (code, out, err))
    hostile = {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy,
               "https_proxy": proxy, "ALL_PROXY": proxy,
               "TMPDIR": str(victim), "TEMP": str(victim), "TMP": str(victim),
               "VELARIS_ALLOW": "all", "PYTHONDONTWRITEBYTECODE": "1"}
    code, out, err, _ = demo([], victim, hostile)
    expect("with a proxy in the environment, and the temporary directory "
           "pointed at the victim's: still refused at the read, and the "
           "victim's .env is not the one the script meets",
           code == 0 and "error[E310]" in out and CANARY not in out + err
           and (victim / ".env").read_text(encoding="utf-8")
           == f"API_KEY={CANARY}\n", (code, out, err))
    expect("nothing was posted anywhere this machine could hear",
           not heard, heard)
    expect("what it made under the victim's directory is gone again",
           sorted(p.name for p in victim.iterdir()) == before,
           sorted(p.name for p in victim.iterdir()))
    stop.set()
    source = (HERE / "velaris" / "demo.py").read_text(encoding="utf-8")
    expect("the webhook's host is under .invalid, which nothing resolves",
           "https://webhook.invalid/" in source
           and source.count("https://") == 1, "")
    expect("the demo's runs are given no --allow but the one it writes, and "
           "read no argument, environment variable or working directory",
           "os.environ" not in source and "os.getcwd" not in source
           and "sys.argv" not in source and "input(" not in source)
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed: the demo shows a refusal and a run "
          f"inside a budget, and reads nobody's .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
