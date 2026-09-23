#!/usr/bin/env python3
"""The Python sandbox column's host: smolagents' LocalPythonExecutor.

    python sandbox_host.py PROGRAM [--grant G]... [--module NAME]...

WHY THIS SANDBOX. It is the one a developer gets by default when a model
writes Python in an agent: smolagents' CodeAgent runs model-written code in
LocalPythonExecutor unless it is pointed at a remote executor, and the
remote ones (E2B, Modal, Blaxel, a Docker host) either cost money or are not
a Python sandbox. It is free, runs anywhere Python runs, and was built for
exactly the programs this benchmark is made of. Its own docstring says it
"is not a security sandbox"; this column measures what it does anyway,
because it is what people run. RestrictedPython is the older, more general
choice; its guards are opt-in, so a fair configuration of it is a matter of
opinion, where smolagents has a default.

WHAT IT IS. An interpreter for Python's AST, in the host process: every
statement is evaluated by smolagents, an import is allowed only if its name
is authorised, `open`, `eval`, `exec` and other builtins exist only if
passed in as tools, dunder access is refused, and a while loop stops after
1,000,000 iterations. `timeout_seconds` is meant to stop a run; in 1.26.0 it
does not (its error is raised inside a `with ThreadPoolExecutor()`, whose
exit waits for the worker thread), so the timeout surfaces only when the
program ends by itself. The host therefore runs the program on a thread of
its own and stops it 5 s after interpretation begins - smolagents' import
is not counted - and says that it, not smolagents, did.

THE GRANT. The narrowest configuration that lets the task's legitimate work
run, using smolagents' own mechanisms only - an import allowlist and the
functions passed in - with no wrapper of this harness's own:

    always     json and dataclasses (pure: the programs use them for
               parsing and records), and smolagents' base modules (math
               among them)
    io         sys, so the program can read its input; print is smolagents'
    fs:read:D, fs:write:D
               the builtin open, passed in as a function. smolagents has no
               way to scope it to D, or to one direction
    net:H:P    urllib.request authorised. smolagents has no way to scope it
               to one host
    ffi:NAME   the host module NAME (subprocess in category 17), authorised
               by name; smolagents cannot narrow subprocess to one program
    --module   a module the project vendors beside the program (category
               12's dependency, 15's textcase, 19's library), authorised by
               name

Nothing is authorised because a program asks for it. An authorised module is
imported by real Python, outside the interpreter: its code runs with the
host process's full authority, and that is part of what this column shows.

OUTPUT. What the program printed, on stdout (smolagents captures print; it
is written out when the run ends, also when it fails). An error on stderr as
`sandbox-error: TYPE: MESSAGE`, exit 1; the timeout error exits 3. The
host leaves with os._exit, so a worker thread still running cannot hold the
process open.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any

from smolagents.local_python_executor import LocalPythonExecutor

TIMEOUT_S = 5


def config(grants: list[str], modules: list[str]) -> tuple[list[str],
                                                          dict[str, Any]]:
    imports = ["json", "dataclasses"] + list(modules)
    functions: dict[str, Any] = {}
    for g in grants:
        if g == "io":
            imports.append("sys")
        elif g.startswith(("fs:read:", "fs:write:")):
            functions["open"] = open
        elif g.startswith("net:"):
            imports.append("urllib.request")
        elif g.startswith("ffi:"):
            # the host module the task needs - subprocess (category 17), a
            # vendored library (19) - authorised by name; math is one of
            # smolagents' base modules already
            imports.append(g[len("ffi:"):])
        else:
            raise SystemExit(f"unknown grant {g}")
    return sorted(set(imports)), functions


def main(argv: list[str]) -> int:
    program, grants, modules = None, [], []
    it = iter(argv)
    for a in it:
        if a == "--grant":
            grants.append(next(it))
        elif a == "--module":
            modules.append(next(it))
        elif program is None:
            program = a
        else:
            raise SystemExit(f"unexpected argument {a}")
    if program is None:
        raise SystemExit("usage: sandbox_host.py PROGRAM [--grant G]... "
                         "[--module NAME]...")
    with open(program, encoding="utf-8") as f:
        code = f.read()
    # a vendored module sits beside the program, where an import finds it
    sys.path.insert(0, os.path.dirname(os.path.abspath(program)))
    # the program imports this process's sys: give it the argv that
    # `python PROGRAM` gives, not the host's own arguments (10e reads it)
    sys.argv = [program]
    imports, functions = config(grants, modules)
    executor = LocalPythonExecutor(additional_authorized_imports=imports,
                                   additional_functions=functions,
                                   timeout_seconds=TIMEOUT_S)
    executor.send_tools({})
    box: dict[str, BaseException] = {}

    def interpret() -> None:
        try:
            executor(code)
        except Exception as e:  # smolagents' InterpreterError, or its timeout
            box["error"] = e

    # smolagents' own timeout waits for the program to end before it
    # raises, so it cannot stop one that does not; the host's watchdog does,
    # TIMEOUT_S after interpretation begins (the import is not counted)
    worker = threading.Thread(target=interpret, daemon=True)
    worker.start()
    worker.join(TIMEOUT_S)
    status = 0
    error = ""
    if worker.is_alive():
        status = 3
        error = (f"sandbox-error: Timeout: stopped by the host after "
                 f"{TIMEOUT_S} s of interpretation; smolagents' own "
                 f"{TIMEOUT_S} s timeout had not fired")
    elif "error" in box:
        e = box["error"]
        name = type(e).__name__
        message = " ".join(str(e).split())
        status = 3 if name == "ExecutionTimeoutError" else 1
        error = f"sandbox-error: {name}: {message}"
    sys.stdout.write(str(executor.state.get("_print_outputs", "")))
    sys.stdout.flush()
    if error:
        sys.stderr.write(error + "\n")
        sys.stderr.flush()
    # a timed-out run leaves smolagents' worker thread running, and it
    # cannot be stopped; leave without waiting for it
    os._exit(status)


if __name__ == "__main__":
    main(sys.argv[1:])
