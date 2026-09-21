#!/usr/bin/env python3
"""What Sabline offers the code and the people that use it, held to a golden.

tests/api/golden.json records, and this suite compares against, what this
tree offers:

  library  every public name `import sabline` gives: the signature of each
           function, class and public method, a result class's fields, the
           type of each constant, the value of each document identifier
           (a *_SCHEMA or *_PREDICATE_TYPE text), every error code and every
           removed one. STABILITY.md's covered names are marked "covered".
  cli      every command `sabline` has, and the flags its usage names
  http     the HTTP door (`sabline serve`): for a fixed set of requests, the
           status and the shape of each answer - every key, and the type of
           its value - and the shape of each line of its invocation log
  mcp      the MCP server: its tools as a client lists them, and the shape of
           each answer to a fixed set of calls and of its log lines
  lsp      the language server: its capabilities, and the shape of each
           answer to a fixed set of requests
  action   action.yml's inputs, their defaults and its outputs

Any difference fails and is named. A change that is meant is made with the
golden updated in the same commit (`python check_api.py --update`) and a
line beginning "api:" in the CHANGELOG saying what changed - in the entry
for VERSION when VERSION is not yet tagged, otherwise above the first
entry. release_checks.py's gate refuses a release whose golden differs
from the previous tag's without such a line.

The shapes are the same with and without the prover and on every system,
so every CI leg compares against the one golden. 8.2 recorded it from
sabline.py before that file became a package, which is how the package is
shown to offer what the file did.

    python check_api.py            compare
    python check_api.py --update   write the golden from this tree
"""
from __future__ import annotations

import dataclasses
import http.client
import inspect
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Any, Callable, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
import release_checks  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_api")
GOLDEN = HERE / "tests" / "api" / "golden.json"
SABLINE = [sys.executable, str(HERE / "sabline.py")]

# STABILITY.md's list of the library it covers
COVERED = ("check", "audit", "run", "Pool", "card", "attest",
           "CheckResult", "AuditResult", "RunResult", "Problem")

HELLO = 'fn main() uses io {\n    print("hello")\n}\n'
BROKEN = 'fn main() {\n    print("no effect declared")\n}\n'
READS = ('fn main() uses io, fs {\n'
         '    check read_file("x.txt") {\n'
         '        ok t { print(t) }\n'
         '        fail w { print(w) }\n    }\n}\n')
PROMISE = ('fn add1(n: Int) -> Int\n'
           '    ensures result == n + 1\n'
           '{\n'
           '    return n + 1\n'
           '}\n'
           '\n'
           'fn main() uses io {\n'
           '    print(add1(1))\n'
           '}\n')


def _key(k: object) -> str:
    """A key as the golden records it: a file URI - a rename's answer is
    keyed by one - by the file's name alone, since the directory is this
    run's."""
    k = str(k)
    return "file://.../" + k.rsplit("/", 1)[-1] if k.startswith("file://") \
        else k


def shape(value: Any) -> Any:
    """Every key and the type of every value; a list is the distinct shapes
    of its items, in order."""
    if isinstance(value, dict):
        return {_key(k): shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        kinds: list[Any] = []
        for item in value:
            s = shape(item)
            if s not in kinds:
                kinds.append(s)
        return kinds
    return type(value).__name__


# ---- the library ------------------------------------------------------------

def _signature(obj: Any) -> str | None:
    """The signature as text: each parameter's name, kind and default, and
    no annotation - of a parameter or of the return - so that typing the
    package (8.2) does not move the golden. A default that names something
    of ours is shown without the module it was defined in (`sabline.X` and,
    in the package, `sabline.nodes.X` are one default)."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    bare = sig.replace(
        parameters=[p.replace(annotation=inspect.Parameter.empty)
                    for p in sig.parameters.values()],
        return_annotation=inspect.Signature.empty)
    return re.sub(r"\bsabline(?:\.[a-z_]+)?\.(?=[A-Z_])", "", str(bare))


def _ours(obj: Any) -> bool:
    owner = str(getattr(obj, "__module__", "") or "")
    return owner == "sabline" or owner.startswith("sabline.")


def library_surface() -> dict[str, Any]:
    names: dict[Any, Any] = {}
    for name in sorted(dir(sabline)):
        if name.startswith("_"):
            continue
        obj = getattr(sabline, name)
        if inspect.ismodule(obj):
            continue
        if inspect.isclass(obj) or inspect.isfunction(obj):
            if not _ours(obj):
                continue                   # imported: dataclass, field, ...
        if inspect.isclass(obj):
            entry: dict[Any, Any] = {"kind": "class", "signature": _signature(obj),
                           "bases": [b.__name__ for b in obj.__bases__]}
            methods = {}
            for m, v in sorted(vars(obj).items()):
                if m.startswith("_") and m not in ("__init__", "__enter__",
                                                   "__exit__"):
                    continue
                if isinstance(v, (staticmethod, classmethod)):
                    v = v.__func__
                if inspect.isfunction(v):
                    methods[m] = _signature(v)
                elif isinstance(v, property):
                    methods[m] = "property"
            entry["methods"] = methods
            if dataclasses.is_dataclass(obj):
                entry["fields"] = [f.name for f in dataclasses.fields(obj)]
            slots = obj.__dict__.get("__slots__")
            if slots:
                entry["slots"] = [slots] if isinstance(slots, str) \
                    else list(slots)
        elif callable(obj):
            entry = {"kind": "function", "signature": _signature(obj)}
        else:
            entry = {"kind": "value", "type": type(obj).__name__}
            if isinstance(obj, str) and re.search(
                    r"(SCHEMA|PREDICATE_TYPE)$", name):
                entry["value"] = obj
        if name in COVERED:
            entry["covered"] = True
        names[name] = entry
    return {"names": names,
            "error_codes": sorted(sabline.ERROR_TABLE),
            "removed_codes": sorted(getattr(sabline, "REMOVED_ERRORS", {}))}


# ---- the command line -------------------------------------------------------

def cli_surface() -> dict[str, Any]:
    usage = sabline.usage_lines()
    block = (sabline.usage_lines.__globals__.get("__doc__") or "") \
        .split("\nUsage:\n", 1)[-1].split("\n\n", 1)[0]
    return {"commands": {c: sorted(set(re.findall(r"--[a-z][a-z-]*",
                                                  "\n".join(lines))))
                         for c, lines in sorted(usage.items())},
            "flags": sorted(set(re.findall(r"--[a-z][a-z-]*", block)))}


# ---- helpers for the doors --------------------------------------------------

def _log_shapes(path: Path) -> list[Any]:
    """The shape of each line of an invocation log, in order."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        out.append(shape(doc))
    return out


def _lines_of(stream: Any, into: queue.Queue[Any]) -> None:
    for line in iter(stream.readline, ""):
        into.put(line)
    into.put(None)


# ---- the HTTP door ----------------------------------------------------------

def http_surface() -> dict[str, Any]:
    token = "api-golden-" + secrets.token_hex(16)
    log_file = WORK / "door.log"
    env = dict(os.environ, SABLINE_TOKEN=token)
    door = subprocess.Popen(
        SABLINE + ["serve", "--port", "0", "--root", str(WORK),
                   "--log-file", str(log_file)],
        cwd=str(WORK), env=env, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True)
    said: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_lines_of, args=(door.stdout, said),
                     daemon=True).start()
    port = None
    deadline = time.monotonic() + 120
    while port is None and time.monotonic() < deadline:
        try:
            line = said.get(timeout=5)
        except queue.Empty:
            continue
        if line is None:
            break
        m = re.search(r"listening on http://127\.0\.0\.1:(\d+)", line)
        if m:
            port = int(m.group(1))
    if port is None:
        door.kill()
        raise RuntimeError("sabline serve did not say where it listens")

    auth = {"Authorization": f"Bearer {token}"}
    cases = [
        ("health, no token", "GET", "/health", None, {}),
        ("health", "GET", "/health", None, auth),
        ("index", "GET", "/", None, auth),
        ("card", "GET", "/card", None, auth),
        ("check", "POST", "/check", {"source": HELLO}, auth),
        ("check, does not compile", "POST", "/check", {"source": BROKEN},
         auth),
        ("audit", "POST", "/audit", {"source": HELLO}, auth),
        ("audit, does not compile", "POST", "/audit", {"source": BROKEN},
         auth),
        ("run", "POST", "/run", {"source": HELLO}, auth),
        ("run, every field", "POST", "/run",
         {"source": HELLO, "allow": ["io"], "args": ["a"], "stdin": "x\n",
          "seed": 7, "freeze_time": "2026-01-01T00:00:00Z", "timeout": 20,
          "max_memory_mb": 256, "receipt": True}, auth),
        ("run, refused", "POST", "/run", {"source": READS, "allow": ["io"],
                                         "receipt": True}, auth),
        ("run, past the ceiling", "POST", "/run",
         {"source": HELLO, "allow": ["net"]}, auth),
        ("run, a budget that does not parse", "POST", "/run",
         {"source": HELLO, "allow": ["banana"]}, auth),
        ("run, no source", "POST", "/run", {}, auth),
        ("run, no token", "POST", "/run", {"source": HELLO}, {}),
        ("no such endpoint", "GET", "/nope", None, auth),
    ]
    answers = {}
    try:
        for label, method, path, body, headers in cases:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
            data = None if body is None else json.dumps(body).encode()
            head = dict(headers)
            if data is not None:
                head["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=head)
            got = conn.getresponse()
            raw = got.read()
            conn.close()
            try:
                doc = json.loads(raw.decode("utf-8"))
            except ValueError:
                doc = "not JSON"
            answers[label] = {"status": got.status, "shape": shape(doc)}
    finally:
        door.terminate()
        try:
            door.wait(timeout=30)
        except subprocess.TimeoutExpired:
            door.kill()
    return {"answers": answers, "log": _log_shapes(log_file)}


# ---- the MCP server ---------------------------------------------------------

def mcp_surface() -> dict[str, Any]:
    log_file = WORK / "mcp.log"
    server = subprocess.Popen(
        [sys.executable, str(HERE / "sabline_mcp.py"), "--root", str(WORK),
         "--log-file", str(log_file)],
        cwd=str(WORK), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    said: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_lines_of, args=(server.stdout, said),
                     daemon=True).start()
    ids = iter(range(1, 10_000))

    def ask(method: Any, params: Any = None) -> Any:
        n = next(ids)
        cast("IO[str]", server.stdin).write(
            json.dumps({"jsonrpc": "2.0", "id": n, "method": method,
                        "params": params or {}}) + "\n")
        cast("IO[str]", server.stdin).flush()
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                line = said.get(timeout=5)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError(f"the MCP server stopped during {method}")
            doc = json.loads(line)
            if doc.get("id") == n:
                return doc
        raise RuntimeError(f"no answer to {method}")

    def call(name: Any, arguments: Any) -> dict[str, Any]:
        doc = ask("tools/call", {"name": name, "arguments": arguments})
        result = doc.get("result") or {}
        text = "".join(c.get("text", "") for c in result.get("content", []))
        try:
            body = shape(json.loads(text))
        except ValueError:
            body = "text"
        return {"is_error": bool(result.get("isError")), "shape": body}

    try:
        hello = ask("initialize", {"protocolVersion": "2024-11-05",
                                   "capabilities": {},
                                   "clientInfo": {"name": "check_api"}})
        tools = ask("tools/list")["result"]["tools"]
        calls = {
            "card": call("sabline_card", {}),
            "check": call("sabline_check", {"source": HELLO}),
            "check, does not compile": call("sabline_check",
                                            {"source": BROKEN}),
            "audit": call("sabline_audit", {"source": HELLO}),
            "run": call("sabline_run", {"source": HELLO}),
            "run, every field": call("sabline_run", {
                "source": HELLO, "allow": ["io"], "args": ["a"],
                "stdin": "x\n", "seed": 7,
                "freeze_time": "2026-01-01T00:00:00Z", "timeout": 20,
                "max_memory_mb": 256, "receipt": True}),
            "run, refused": call("sabline_run", {"source": READS,
                                                 "allow": ["io"]}),
            "run, past the ceiling": call("sabline_run", {
                "source": HELLO, "allow": ["net"]}),
            "run, a budget that does not parse": call("sabline_run", {
                "source": HELLO, "allow": ["banana"]}),
            "no such tool": call("sabline_nothing", {}),
        }
        unknown = ask("no/such/method")
    finally:
        try:
            cast("IO[str]", server.stdin).close()
        except OSError:
            pass
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()
    result = hello["result"]
    return {"protocol": result["protocolVersion"],
            "initialize": shape(result),
            "tools": tools, "calls": calls,
            "unknown_method": shape(unknown),
            "log": _log_shapes(log_file)}


# ---- the language server ----------------------------------------------------

def lsp_surface() -> dict[str, Any]:
    server = subprocess.Popen(SABLINE + ["lsp"], cwd=str(WORK),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
    got: queue.Queue[Any] = queue.Queue()

    def reader() -> None:
        out = cast("IO[bytes]", server.stdout)
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
    notes: list[Any] = []

    def send(payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        cast("IO[bytes]", server.stdin).write(
            f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        cast("IO[bytes]", server.stdin).flush()

    def ask(n: Any, method: Any, params: Any) -> Any:
        send({"jsonrpc": "2.0", "id": n, "method": method, "params": params})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                msg = got.get(timeout=5)
            except queue.Empty:
                continue
            if msg is None:
                raise RuntimeError(f"the language server stopped at {method}")
            if msg.get("id") == n:
                return msg
            notes.append(msg)
        raise RuntimeError(f"no answer to {method}")

    def uri_of(name: Any) -> Any:
        p = str(WORK / name).replace("\\", "/")
        return "file://" + ("" if p.startswith("/") else "/") + p

    good, bad = uri_of("p.vel"), uri_of("bad.vel")
    (WORK / "p.vel").write_text(PROMISE, encoding="utf-8")
    (WORK / "bad.vel").write_text(BROKEN, encoding="utf-8")
    at = {"textDocument": {"uri": good},
          "position": {"line": 7, "character": 11}}
    try:
        init = ask(1, "initialize", {"capabilities": {}})
        for uri, text in ((good, PROMISE), (bad, BROKEN)):
            send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                  "params": {"textDocument": {"uri": uri, "languageId":
                                              "sabline", "version": 1,
                                              "text": text}}})
        answers = {
            "hover": ask(2, "textDocument/hover", at),
            "definition": ask(3, "textDocument/definition", at),
            "codeLens": ask(4, "textDocument/codeLens",
                            {"textDocument": {"uri": good}}),
            "documentSymbol": ask(5, "textDocument/documentSymbol",
                                  {"textDocument": {"uri": good}}),
            "completion": ask(6, "textDocument/completion", at),
            "rename": ask(7, "textDocument/rename",
                          dict(at, newName="inc")),
            "shutdown": ask(8, "shutdown", {}),
        }
        send({"jsonrpc": "2.0", "method": "exit"})
    finally:
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()
    diagnostics = {}
    for msg in notes:
        if msg.get("method") == "textDocument/publishDiagnostics":
            which = "bad" if msg["params"]["uri"].endswith("bad.vel") \
                else "good"
            diagnostics[which] = shape(msg["params"])
    result = init["result"]
    return {"capabilities": result["capabilities"],
            "initialize": shape(result),
            "answers": {k: shape(v.get("result")) for k, v in answers.items()},
            "diagnostics": diagnostics}


# ---- the Action -------------------------------------------------------------

def action_surface() -> dict[str, Any]:
    import yaml
    doc = yaml.safe_load((HERE / "action.yml").read_text(encoding="utf-8"))
    return {"inputs": {name: {"required": spec.get("required"),
                              "default": spec.get("default")}
                       for name, spec in sorted(doc["inputs"].items())},
            "outputs": sorted(doc["outputs"]),
            "runs": doc["runs"]["using"]}


# ---- comparing --------------------------------------------------------------

def surface() -> dict[str, Any]:
    return {"library": library_surface(), "cli": cli_surface(),
            "http": http_surface(), "mcp": mcp_surface(),
            "lsp": lsp_surface(), "action": action_surface()}


def differences(want: Any, have: Any, where: str = "") -> list[Any]:
    """Every place two documents differ, one line each."""
    if isinstance(want, dict) and isinstance(have, dict):
        out = []
        for key in sorted(set(want) | set(have)):
            here = f"{where}.{key}" if where else str(key)
            if key not in have:
                out.append(f"{here}: gone (was {json.dumps(want[key])[:120]})")
            elif key not in want:
                out.append(f"{here}: new ({json.dumps(have[key])[:120]})")
            else:
                out += differences(want[key], have[key], here)
        return out
    if want != have:
        return [f"{where}: {json.dumps(want)[:160]} -> "
                f"{json.dumps(have)[:160]}"]
    return []


def _newest_tag() -> str | None:
    try:
        tags = release_checks.git(HERE, "tag", "--list", "v*").splitlines()
    except release_checks.Unanswered:
        return None
    tags = [t for t in tags if release_checks.parse_version(t)]
    # every tag left parses, so parse_version gives each one a version
    return max(tags, key=cast("Callable[[str], tuple[int, int, int]]",
                              release_checks.parse_version)) if tags else None


def api_line_for_change() -> tuple[bool, str]:
    """(whether a CHANGELOG line beginning "api:" covers a golden that
    differs from the newest tag's, what was found)."""
    tag = _newest_tag()
    if tag is None:
        return True, "no tag here to compare the golden with"
    try:
        before = release_checks.git(HERE, "show",
                                    f"{tag}:tests/api/golden.json")
    except release_checks.Unanswered:
        return True, f"{tag} has no golden to compare with"
    if json.loads(before) == json.loads(GOLDEN.read_text(encoding="utf-8")):
        return True, f"the golden is {tag}'s"
    version = sabline.VERSION
    text = (HERE / "CHANGELOG.md").read_text(encoding="utf-8")
    if cast("tuple[int, int, int]", release_checks.parse_version(version)) > \
            cast("tuple[int, int, int]", release_checks.parse_version(tag)):
        entry = release_checks.changelog_entry(HERE, version)
        body = entry[1] if entry else ""
        place = f"the CHANGELOG entry for {version}"
    else:
        first = re.search(r"^## \d", text, re.M)
        body = text[:first.start()] if first else text
        place = "the CHANGELOG, above its first entry"
    said = any(line.strip().lower().startswith("api:")
               for line in body.splitlines())
    return said, (f"the golden differs from {tag}'s, and {place} "
                  + ("has" if said else "has no") + " line beginning 'api:'")


def main() -> int:
    have = surface()
    if "--update" in sys.argv[1:]:
        old = json.loads(GOLDEN.read_text(encoding="utf-8")) \
            if GOLDEN.exists() else {}
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(have, indent=1, sort_keys=True,
                                     ensure_ascii=True) + "\n",
                          encoding="utf-8", newline="\n")
        changed = differences(old, have)
        print(f"wrote {GOLDEN.relative_to(HERE)}: {len(changed)} change(s)")
        for line in changed[:200]:
            print(f"  {line}")
        return 0
    if not GOLDEN.exists():
        print(f"no golden at {GOLDEN}; write one with --update")
        return 1
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    changed = differences(want, json.loads(json.dumps(have)))
    failed = 0
    for part in ("library", "cli", "http", "mcp", "lsp", "action"):
        mine = [c for c in changed if c.split(".", 1)[0].split(":")[0] == part]
        if mine:
            failed += 1
            print(f"  CHANGED  {part}: {len(mine)} difference(s)")
            for line in mine[:40]:
                print(f"           {line}")
        else:
            print(f"  ok       {part} is what the golden records")
    said, why = api_line_for_change()
    print(f"  {'ok' if said else 'MISSING'}       {why}")
    if not said:
        failed += 1
    if failed:
        print("\nIf the change is meant: python check_api.py --update, and a "
              "line beginning 'api:' in the CHANGELOG saying what changed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
