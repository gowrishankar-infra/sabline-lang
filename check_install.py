#!/usr/bin/env python3
"""An installed Velaris runs examples/discount.vel and refuses the network.

The nightly workflow (nightly.yml) builds every artefact a user can install
from this commit, installs each the way a user would, and hands it to this
script (item 17 of 8.2). Whatever the artefact, the same two things must
hold: examples/discount.vel runs and prints the amounts it always prints,
and a program that reaches for the network is refused under the default
budget and under --allow io, with E310, and never reaches it.

Every program is copied into an empty directory and run from there, so the
checkout this script sits in is never what answers.

    python check_install.py --name wheel --command velaris
    python check_install.py --name sdist --command "python -m velaris"
    python check_install.py --name binary --command dist/velaris-linux
    python check_install.py --name docker --docker velaris:nightly
    python check_install.py --name mcpb --mcp "python bundle/server/velaris_mcp.py" \\
        --pythonpath bundle/server/lib
    python check_install.py --name vscode --lsp "velaris lsp"

A path in a command is taken from where this script is started. The
language server runs nothing, so for it the check is that it diagnoses,
not that it refuses. --any-version accepts whatever version answers; the
Action installs from PyPI, so on an unreleased commit it answers with the
newest release.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DISCOUNT = HERE / "examples" / "discount.vel"
PAYABLE = ("payable  INR 112.90", "payable  INR 0.00")
NET = ('fn main() uses net, io {\n'
       '    check fetch("https://example.com/") {\n'
       '        ok body { print("reached the network") }\n'
       '        fail why { print(why) }\n'
       '    }\n'
       '}\n')
REACHED = "reached the network"
REFUSED = "'fetch' needs the 'net' effect"
BROKEN = 'fn main() uses io {\n    print(nowhere)\n}\n'
PASS = FAIL = 0


def ok(label: str, good: bool, detail: str = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        print(f"  ok      {label}")
    else:
        FAIL += 1
        print(f"  BROKEN  {label}")
        if detail:
            print("          " + detail.strip().replace("\n", "\n          ")[:1500])


def expected_version() -> str:
    text = (HERE / "velaris" / "version.py").read_text(encoding="utf-8")
    found = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    if not found:
        sys.exit("check_install: no VERSION in velaris/version.py")
    return found.group(1)


def split(command: str) -> list[str]:
    """The words of a command, each one naming an existing file made absolute:
    the command runs from an empty directory."""
    words = shlex.split(command, posix=os.name != "nt")
    return [os.path.abspath(w) if not w.startswith("-") and os.path.exists(w)
            else w for w in words]


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    return done.returncode, done.stdout + done.stderr


def as_command(cmd: list[str], work: Path, inside: str | None,
               version: str | None) -> None:
    """A command line: velaris, python -m velaris, a binary, npm's wrapper,
    or docker run with the work directory mounted at `inside`."""
    def path(name: str) -> str:
        return f"{inside}/{name}" if inside else name

    code, out = run(cmd + ["--version"], work)
    ok(f"--version answers{'' if version is None else ' ' + version}",
       code == 0 and (version is None or version in out), out)
    code, out = run(cmd + ["check", path("discount.vel")], work)
    ok("check discount.vel: it compiles and its promises hold", code == 0, out)
    code, out = run(cmd + [path("discount.vel")], work)
    ok("discount.vel runs and prints what it always prints",
       code == 0 and all(p in out for p in PAYABLE), out)
    for extra in ([], ["--allow", "io"]):
        code, out = run(cmd + [path("net.vel")] + extra, work)
        how = "under the default budget" if not extra else "under --allow io"
        ok(f"a program that fetches a URL is refused {how}, with E310, "
           f"and never reaches it",
           code == 1 and "E310" in out and REFUSED in out
           and REACHED not in out, f"exit {code}: {out}")


def as_mcp(cmd: list[str], work: Path, version: str | None) -> None:
    """The MCP server over stdio, as the .mcpb bundle starts it."""
    discount = DISCOUNT.read_text(encoding="utf-8")
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "velaris_run",
            "arguments": {"source": discount, "allow": ["io"]}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "velaris_run", "arguments": {"source": NET, "allow": ["io"]}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "velaris_run",
            "arguments": {"source": NET, "allow": ["io", "net"]}}},
        {"jsonrpc": "2.0", "method": "exit", "params": {}},
    ]
    done = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600,
                          input="\n".join(json.dumps(m) for m in msgs) + "\n")
    answers: dict[int, dict[str, Any]] = {}
    for line in done.stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("id") is not None:
            answers[d["id"]] = d
    info = answers.get(1, {}).get("result", {}).get("serverInfo", {})
    ok(f"the server announces itself{'' if version is None else ' as ' + version}",
       info.get("name") == "velaris"
       and (version is None or info.get("version") == version),
       f"{info} {done.stderr[-500:]}")

    def body(i: int) -> dict[str, Any]:
        try:
            found = json.loads(answers[i]["result"]["content"][0]["text"])
            return found if isinstance(found, dict) else {}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return {}
    ran = body(2)
    ok("velaris_run runs discount.vel and prints what it always prints",
       ran.get("ok") is True
       and all(p in ran.get("output", "") for p in PAYABLE), str(ran)[:600])
    refused = body(3)
    ok("velaris_run with allow [io] refuses a program that fetches a URL, "
       "and it never reaches it",
       refused.get("ok") is False and refused.get("refused_effect") == "net"
       and REACHED not in refused.get("output", ""), str(refused)[:600])
    ceiling = answers.get(4, {}).get("result", {})
    ok("...and asking for net is refused by the server's ceiling",
       ceiling.get("isError") is True
       and "does not grant net" in json.dumps(ceiling), str(ceiling)[:600])


def as_lsp(cmd: list[str], work: Path) -> None:
    """The language server the VS Code extension spawns."""
    proc = subprocess.Popen(cmd, cwd=work, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    got: queue.Queue[dict[str, Any] | None] = queue.Queue()
    errors: list[bytes] = []

    def read() -> None:
        assert proc.stdout is not None
        while True:
            length = 0
            while True:
                line = proc.stdout.readline()
                if not line:
                    got.put(None)
                    return
                line = line.strip()
                if not line:
                    break
                key, _, value = line.decode("ascii", "replace").partition(":")
                if key.strip().lower() == "content-length":
                    length = int(value.strip())
            got.put(json.loads(proc.stdout.read(length)))

    def drain() -> None:
        if proc.stderr is not None:
            errors.append(proc.stderr.read())

    threading.Thread(target=read, daemon=True).start()
    threading.Thread(target=drain, daemon=True).start()

    def send(message: dict[str, Any]) -> None:
        assert proc.stdin is not None
        data = json.dumps(message).encode("utf-8")
        proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        proc.stdin.flush()

    def wait(match: Callable[[dict[str, Any]], bool],
             seconds: float = 180) -> dict[str, Any] | None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                message = got.get(timeout=max(0.1, end - time.monotonic()))
            except queue.Empty:
                return None
            if message is None:
                return None
            if match(message):
                return message
        return None

    def diagnostics(uri: str) -> Callable[[dict[str, Any]], bool]:
        return lambda m: (m.get("method") == "textDocument/publishDiagnostics"
                          and m.get("params", {}).get("uri") == uri)

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"processId": None, "rootUri": work.as_uri(),
                         "capabilities": {}}})
        hello = wait(lambda m: m.get("id") == 1)
        ok("the language server answers initialize",
           bool(hello and "result" in hello), str(hello))
        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        for name, text, want_problems in (
                ("discount.vel", DISCOUNT.read_text(encoding="utf-8"), False),
                ("broken.vel", BROKEN, True)):
            uri = (work / name).as_uri()
            send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                  "params": {"textDocument": {"uri": uri, "languageId": "velaris",
                                              "version": 1, "text": text}}})
            said = wait(diagnostics(uri))
            found = (said or {}).get("params", {}).get("diagnostics")
            if want_problems:
                ok("...diagnoses a file that does not compile (E402)",
                   bool(found) and "E402" in json.dumps(found), str(said))
            else:
                ok("...and reports nothing for discount.vel", found == [],
                   str(said))
        send({"jsonrpc": "2.0", "id": 9, "method": "shutdown", "params": None})
        wait(lambda m: m.get("id") == 9, 30)
        send({"jsonrpc": "2.0", "method": "exit", "params": None})
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    if FAIL and errors:
        print("          stderr: " + errors[0].decode("utf-8", "replace")[-800:])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--name", required=True, help="what was installed, for the log")
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--command", help="the command that runs Velaris")
    how.add_argument("--docker", metavar="IMAGE",
                     help="an image whose entrypoint is velaris")
    how.add_argument("--mcp", help="the command that starts the MCP server")
    how.add_argument("--lsp", help="the command that starts the language server")
    ap.add_argument("--pythonpath", metavar="DIR",
                    help="PYTHONPATH for what is started, as a bundle sets it")
    ap.add_argument("--any-version", action="store_true",
                    help="accept whatever version answers")
    args = ap.parse_args(argv)
    version = None if args.any_version else expected_version()
    if args.pythonpath:
        os.environ["PYTHONPATH"] = os.path.abspath(args.pythonpath)
    print(f"installed from {args.name}")
    print("-" * 62)
    work = Path(tempfile.mkdtemp(prefix="velaris-install-"))
    try:
        shutil.copy2(DISCOUNT, work / "discount.vel")
        (work / "net.vel").write_text(NET, encoding="utf-8")
        if args.command:
            as_command(split(args.command), work, None, version)
        elif args.docker:
            mount = str(work).replace("\\", "/")
            as_command(["docker", "run", "--rm", "-v", f"{mount}:/work",
                        args.docker], work, "/work", version)
        elif args.mcp:
            as_mcp(split(args.mcp), work, version)
        else:
            as_lsp(split(args.lsp), work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("-" * 62)
    print(f"{args.name}: {PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
