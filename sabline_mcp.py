#!/usr/bin/env python3
"""Sabline as an MCP server: write, audit, run - inside the assistant.

An assistant that writes code should be able to check it, see what it
can touch, and run it in a box, without leaving the conversation. This
speaks the Model Context Protocol over stdin/stdout, so any MCP client
can offer:

    sabline_card    the whole language, ~4,600 words, for writing it
    sabline_check   compile without running; problems as data
    sabline_audit   what a program touches, promises and can fail at
    sabline_run     run it under an effect budget you choose

Add to an MCP client's config:

    {"mcpServers": {"sabline": {"command": "python",
                                "args": ["-m", "sabline_mcp"]}}}

The operator's flags, after "sabline_mcp" in "args":

    --max-allow GRANTS   the most a sabline_run may ask for, in the
                         budget grammar (io,fs:read:./data,net:host@10,
                         ffi:math). Default: io only. A request for more
                         is refused, naming what the server grants.
    --max-timeout S      the most seconds one run may have. Default: 30.
    --max-memory-mb M    the most memory one run may have. Default: 512.
                         A run that names neither gets these; asking for
                         more is refused like an over-wide budget (4.0).
                         Before 4.0 a caller could ask for any timeout
                         and any memory cap and have it.
    --log-file PATH      the invocation log, one JSON line per tool call,
                         appended here instead of written to stderr
    --log minimal        fewer fields in each line; the log cannot be
                         turned off
    --root DIR           where a program's imports may come from: .vel
                         files at or under DIR, and the standard library.
                         Default: the directory the server was started in
                         (8.1). An import outside it is E515, and nothing
                         about the file is read.
    --check-timeout S    the most seconds sabline_check or sabline_audit
                         may take. Default: 60, as `sabline check` (8.1).
    --check-memory-mb M  the most memory either may use. Default: 2048.

What can connect: only the process that started the server, over its
stdin and stdout - an MCP client, which decides what the model may send.
It opens no port and reads no file but the program sent and its imports
under --root. sabline_check and sabline_audit compile, and never run, the
program they are given.

Nothing here trusts the program's own claims: sabline_run enforces the
budget while the program runs, and a refused effect stops it.
"""
import json
import sys

import os
from typing import Any

# the compiler may be: installed (pip), vendored beside this file in an
# .mcpb bundle, or sitting in the repo next door. Try each, in the order
# that keeps a user's own install winning.
_here = os.path.dirname(os.path.abspath(__file__))
for _where in (None, os.path.join(_here, "lib"), _here,
               os.path.dirname(_here)):
    if _where and _where not in sys.path:
        sys.path.insert(0, _where)
    try:
        import sabline
        break
    except ImportError:
        continue
else:                                     # pragma: no cover
    sys.stderr.write("sabline not found: pip install sabline-lang\n")
    raise SystemExit(1)

PROTOCOL = "2024-11-05"

# The ceiling on what sabline_run may grant, as the HTTP door's
# --max-allow is. Without the flag it is io: the least that is useful,
# and nothing a program can touch outside the console.
DEFAULT_CEILING = "io"
CEILING = None      # sabline.Budget, set by configure()
LOG = None          # sabline.InvocationLog, set by configure()
# the most one run may have, set by configure(); a request past either is
# refused like an over-wide budget (4.0)
MAX_TIMEOUT = sabline.DOOR_MAX_TIMEOUT
MAX_MEMORY_MB = sabline.DOOR_MAX_MEMORY_MB
# where imports may come from (8.1): the directory the server was started
# in unless --root names another; and the ceiling sabline_check and
# sabline_audit run under, the one `sabline check` has
ROOT = None
CHECK_TIMEOUT = sabline.CHECK_TIMEOUT_DEFAULT
CHECK_MEMORY_MB = sabline.CHECK_MEMORY_MB_DEFAULT
CHECKER = None      # sabline.Pool that checks and audits, set by checker()
# the name a program sent as text is compiled under: inside the root, so
# its relative imports resolve there
REQUEST_FILE = ".sabline-request.vel"

USAGE = ("usage: python -m sabline_mcp [--max-allow GRANTS] "
         "[--max-timeout SECONDS] [--max-memory-mb MB] "
         "[--log-file PATH] [--log full|minimal] [--root DIR] "
         "[--check-timeout SECONDS] [--check-memory-mb MB] [--no-confine]")

# One pool per distinct budget a caller asks for, made the first time
# that budget is seen and closed when the server stops. An assistant
# calls sabline_run over and over inside one conversation; without this
# each call paid a Python interpreter's startup. The budget still comes
# from the request, inside the ceiling, and a pool never mixes two.
POOLS = None

# Whether each worker asks the operating system to hold its budget too
# (8.4). The operator's --no-confine turns it off, and says so on stderr; a
# tool call cannot.
CONFINE = True


def pools() -> Any:
    global POOLS
    if POOLS is None:
        POOLS = sabline.PoolRegistry(confine=CONFINE)
    return POOLS


def root() -> str:
    global ROOT
    if ROOT is None:
        ROOT = os.path.realpath(os.getcwd())
    return ROOT


def request_path() -> str:
    return os.path.join(root(), REQUEST_FILE)


def checker() -> Any:
    """The worker sabline_check and sabline_audit run on: under the check
    ceiling, with imports held to the root. A crafted program comes back
    E613 or E614 instead of holding the server."""
    global CHECKER
    if CHECKER is None:
        CHECKER = sabline.Pool(size=1, timeout=CHECK_TIMEOUT,
                               max_memory_mb=CHECK_MEMORY_MB,
                               import_root=root(), confine=CONFINE)
    return CHECKER


def close_pools() -> None:
    global POOLS, CHECKER
    registry, POOLS = POOLS, None
    if registry is not None:
        registry.close()
    one, CHECKER = CHECKER, None
    if one is not None:
        one.close()


def ceiling() -> Any:
    global CEILING
    if CEILING is None:
        CEILING = sabline.Budget.parse(DEFAULT_CEILING)
    return CEILING


def ceiling_list() -> list[Any]:
    spec = ceiling().spec()
    return spec.split(",") if spec else []


def log() -> Any:
    global LOG
    if LOG is None:
        LOG = sabline.InvocationLog()
    return LOG


def configure(argv: list[Any]) -> str | None:
    """Read the operator's flags. None when they are fine, else what is
    wrong with them."""
    global CEILING, LOG, MAX_TIMEOUT, MAX_MEMORY_MB, ROOT
    global CHECK_TIMEOUT, CHECK_MEMORY_MB, CONFINE
    opts = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-confine":
            CONFINE = False
            print("sabline mcp: --no-confine: the operating system is not "
                  "asked to hold any run; the budget is the only boundary",
                  file=sys.stderr)
            i += 1
            continue
        if a in ("--max-allow", "--max-timeout", "--max-memory-mb",
                 "--log-file", "--log", "--root", "--check-timeout",
                 "--check-memory-mb"):
            if i + 1 >= len(argv):
                return f"{a} needs a value; {USAGE}"
            opts[a] = argv[i + 1]
            i += 2
            continue
        return f"unknown argument '{a}'; {USAGE}"
    try:
        asked = opts.get("--max-allow", DEFAULT_CEILING)
        if asked.strip() == sabline.ALLOW_ALL:
            sabline.warn_allow_all("sabline mcp")
        CEILING = sabline.Budget.parse(sabline.expand_allow(asked))
    except sabline.BudgetError as e:
        return f"--max-allow: {e}"
    try:
        MAX_TIMEOUT, MAX_MEMORY_MB = sabline.door_ceilings(
            opts.get("--max-timeout"), opts.get("--max-memory-mb"))
        CHECK_TIMEOUT, CHECK_MEMORY_MB = sabline.check_ceilings(
            opts.get("--check-timeout"), opts.get("--check-memory-mb"))
    except ValueError as e:
        return str(e)
    if "--root" in opts:
        if not os.path.isdir(opts["--root"]):
            return f"--root: {opts['--root']} is not a directory"
        ROOT = os.path.realpath(opts["--root"])
    try:
        LOG = sabline.InvocationLog(opts.get("--log-file"),
                                    opts.get("--log", "full"))
    except ValueError as e:
        return f"--log: {e}"
    except OSError as e:
        return f"cannot open the log file: {e.strerror or e}"
    return None


# The descriptions are fixed text: the release workflow hashes them into
# a signed manifest (sabline mcp-verify), so they say what the default
# ceiling is rather than the ceiling this server was started with.
TOOLS = [
    {
        "name": "sabline_card",
        "description": (
            "The Sabline language in about 4,600 words: syntax, the "
            "rules models get wrong, every builtin with its effects and "
            "whether it can fail, full standard-library signatures, and "
            "the error table. Read this before writing Sabline."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "sabline_check",
        "description": (
            "Compile a Sabline program without running it. Returns every "
            "problem with a code, line and suggested fixes, plus which "
            "promises were proven before running and which fall back to "
            "runtime checks. Use this to iterate until a program "
            "compiles."),
        "inputSchema": {
            "type": "object",
            "properties": {"source": {"type": "string",
                                      "description": "the program"}},
            "required": ["source"],
        },
    },
    {
        "name": "sabline_audit",
        "description": (
            "What a program can touch (io, env, fs, net, clock, rand, "
            "ffi, declassify), whether it holds a secret and whether it "
            "ever lets one out, "
            "what each function promises, how much of that is proven "
            "rather than checked while running, what can fail, and the "
            "command to run it safely. Use this before running code you "
            "did not write."),
        "inputSchema": {
            "type": "object",
            "properties": {"source": {"type": "string"}},
            "required": ["source"],
        },
    },
    {
        "name": "sabline_run",
        "description": (
            "Run a Sabline program under an effect budget. Anything "
            "outside the budget is refused while the program runs, "
            "whatever the source claims about itself, and a refusal "
            "cannot be caught by the program. Grant the least you can: "
            "['io'] lets it print and nothing else. This server grants "
            "at most what its operator set with --max-allow, and without "
            "that flag it grants io only: a request for more is refused, "
            "and the refusal names what the server grants. The operator "
            "also sets the most time and memory one run may have "
            "(--max-timeout, --max-memory-mb: 30 seconds and 512 MB "
            "unless changed); a run may ask for less, never more."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "allow": {
                    "type": "array", "items": {"type": "string"},
                    "description": ("effects to permit: io, env, fs, net, "
                                    "clock, rand, ffi, declassify. "
                                    "Default ['io']. "
                                    "Scoped grants: fs:read:./data, "
                                    "fs:write:./out, net:api.example.com"
                                    ":443, net:*.example.com, ffi:math,"
                                    "json, and @N for at most N "
                                    "operations (fs@50, net:host@100). "
                                    "Plain fs, net or ffi grants every "
                                    "path, host or module. Only what the "
                                    "server's ceiling covers is granted."),
                },
                "stdin": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "receipt": {
                    "type": "boolean",
                    "description": ("true to be given the run's receipt: "
                                    "an in-toto Statement "
                                    "(sabline.receipt/1) of what this run "
                                    "did - the budget, each refusal and "
                                    "declassification with its reason, the "
                                    "parameters, how it ended and how long "
                                    "it took - bound to the program's "
                                    "sha256 and holding none of its "
                                    "values."),
                },
                "timeout": {
                    "type": "number",
                    "description": ("seconds before the program is "
                                    "stopped. At most the server's "
                                    "--max-timeout (30 unless its "
                                    "operator changed it), which is also "
                                    "the default; more is refused."),
                },
                "max_memory_mb": {
                    "type": "integer",
                    "description": ("memory cap in MB. At most the "
                                    "server's --max-memory-mb (512 "
                                    "unless its operator changed it), "
                                    "which is also the default; more is "
                                    "refused. Enforced on Linux "
                                    "(RLIMIT_AS) and on Windows (a job "
                                    "object); best-effort on macOS. The "
                                    "timeout applies everywhere."),
                },
            },
            "required": ["source"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


def as_text(payload: Any, is_error: bool = False) -> dict[Any, Any]:
    body = payload if isinstance(payload, str) else json.dumps(payload,
                                                               indent=2)
    out: dict[str, Any] = {"content": [{"type": "text", "text": body}]}
    if is_error:
        out["isError"] = True
    return out


def call_tool(name: str, args: dict[Any, Any]) -> tuple[dict[Any, Any], dict[str, Any]]:
    """(the MCP result, what the invocation log records about it)."""
    rec: dict[str, Any] = {"outcome": "ok", "budget": None, "effects": None,
           "refusals": [], "source": None}
    if name == "sabline_card":
        return as_text(sabline.card()), rec
    if name not in TOOL_NAMES:
        rec["outcome"] = "unknown_tool"
        return as_text({"error": f"no tool called '{name}'"},
                       is_error=True), rec

    source = args.get("source", "")
    if not isinstance(source, str):
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": "source must be text"},
                       is_error=True), rec
    rec["source"] = source

    if name in ("sabline_check", "sabline_audit"):
        # compiled on a worker under the check ceiling, never run, with its
        # imports held to the root (8.1)
        if name == "sabline_check":
            got = checker().check(source, path=request_path())
        else:
            got = checker().audit(source, path=request_path())
        stopped = {p.code for p in got.problems} & {"E613", "E614"}
        rec["outcome"] = ("timeout" if "E613" in stopped else
                          "out_of_memory" if "E614" in stopped else
                          "ok" if got.ok else "problems")
        return as_text(got.as_dict()), rec

    # sabline_run: parse what was asked, hold it against the ceiling -
    # at every level, as the HTTP door does - and only then run it
    asked = args.get("allow") or ["io"]
    if not isinstance(asked, list) or \
            not all(isinstance(a, str) for a in asked):
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": "allow is a list of grants, "
                                              "as [\"io\"]"},
                       is_error=True), rec
    try:
        wanted = sabline.Budget.parse(",".join(asked))
    except sabline.BudgetError as e:
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": str(e)}, is_error=True), rec
    refused = ceiling().covers(wanted)
    if not refused:
        # the time and memory a run may have are the operator's too: less
        # may be asked for, more is refused like an over-wide budget (4.0)
        timeout, memory, why = sabline.run_limits(args, MAX_TIMEOUT,
                                                  MAX_MEMORY_MB)
        if why and why[0] == "bad_request":
            rec["outcome"] = "bad_request"
            return as_text({"ok": False, "error": why[1]},
                           is_error=True), rec
        refused = why[1] if why else None
    if refused:
        rec["outcome"] = "ceiling"
        rec["refusals"] = [{"by": "ceiling", "what": refused}]
        return as_text({"error": refused, "max_allow": ceiling_list(),
                        "max_timeout": MAX_TIMEOUT,
                        "max_memory_mb": MAX_MEMORY_MB},
                       is_error=True), rec
    rec["budget"] = wanted.spec()
    seed, frozen = args.get("seed"), args.get("freeze_time")
    if seed is not None and not isinstance(seed, int):
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": "seed is a whole number"},
                       is_error=True), rec
    want_receipt = args.get("receipt", False)
    if not isinstance(want_receipt, bool):
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": "receipt is true or false"},
                       is_error=True), rec
    try:
        result = pools().run(
            source, allow=set(asked),
            stdin=args.get("stdin", ""),
            args=args.get("args") or [],
            seed=seed, freeze_time=frozen,
            timeout=timeout, max_memory_mb=memory,
            path=request_path(), import_root=root(), _name="<source>")
    except ValueError as e:
        rec["outcome"] = "bad_request"
        return as_text({"ok": False, "error": str(e)}, is_error=True), rec
    if seed is not None or frozen is not None:
        rec["run_params"] = {"seed": seed, "freeze_time": frozen}
    rec["effects"] = result.effects_used
    rec["outcome"] = sabline.run_outcome(result)
    rec["refusals"] = sabline.run_refusals(result)
    payload = result.as_dict()
    if not want_receipt:
        payload.pop("receipt", None)      # on request only (8.1)
    payload["allowed"] = sorted(asked)
    if result.timed_out:
        payload["note"] = "the program ran too long and was stopped"
    elif result.out_of_memory:
        payload["note"] = "the program used too much memory and was stopped"
    elif result.refused_effect:
        payload["note"] = (
            f"the program tried to use '{result.refused_effect}', "
            f"which this run did not allow")
    return as_text(payload), rec


def handle_tool(name: str, args: dict[Any, Any]) -> dict[Any, Any]:
    return call_tool(name, args)[0]


def reply(msg_id: Any, result: Any = None, error: Any = None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def main(argv: list[Any] | None = None) -> int:
    problem = configure(sys.argv[1:] if argv is None else argv)
    if problem:
        sys.stderr.write(problem + "\n")
        return 2
    try:
        return serve()
    finally:
        close_pools()                     # no worker outlives the server
        if LOG is not None:
            LOG.close()


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        method, msg_id = msg.get("method"), msg.get("id")
        params = msg.get("params")
        params = params if isinstance(params, dict) else {}

        if method == "initialize":
            reply(msg_id, {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sabline",
                               "version": sabline.VERSION},
            })
        elif method == "tools/list":
            reply(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = params.get("name", "")
            name = name if isinstance(name, str) else ""
            arguments = params.get("arguments")
            arguments = arguments if isinstance(arguments, dict) else {}
            started = sabline.InvocationLog.started()
            rec: dict[str, Any] = {"outcome": "error", "budget": None,
                                   "effects": None,
                   "refusals": [], "source": None}
            try:
                result, rec = call_tool(name, arguments)
                reply(msg_id, result)
            except Exception as e:                # never kill the server
                reply(msg_id, as_text({"error": f"{type(e).__name__}: {e}"},
                                      is_error=True))
            finally:
                log().record(started, door="mcp",
                             tool=(name if name in TOOL_NAMES
                                   else "(no such tool)"),
                             outcome=rec["outcome"], budget=rec["budget"],
                             effects=rec["effects"],
                             refusals=rec["refusals"], source=rec["source"],
                             run_params=rec.get("run_params"))
        elif method in ("notifications/initialized", "initialized"):
            continue                              # no reply expected
        elif method == "shutdown":
            close_pools()
            reply(msg_id, None)
        elif method == "exit":
            close_pools()
            return 0
        elif msg_id is not None:
            reply(msg_id, error={"code": -32601,
                                 "message": f"no method '{method}'"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
