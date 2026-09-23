#!/usr/bin/env python3
"""Competitor scoring on the Sabline benchmark (plan/8.7.md section 3).

    python benchmark/compete.py --record        run everything; write competitors/results.json
    python benchmark/compete.py --check         run everything; exit 1 if any cell moved
    python benchmark/compete.py --only 13a,14c  print those cells; write nothing
    python benchmark/compete.py --tools camel   (with --only) just these columns
    python benchmark/compete.py --versions      the runtimes found, and exit
    python benchmark/compete.py --self-test     --check's comparison, shown to fail

The 76 programs of benchmark/corpus.json, run through seven tools, each in
its own real runtime:

    sabline    this checkout (benchmark/run.py's own column, unchanged)
    deno       Deno's permissions (benchmark/run.py's own column, unchanged)
    python     plain Python: no sandbox, the control
    wasi       the same Python programs in CPython's WASI build under
               wasmtime: the boundary is the virtual machine's
    starlark   a Starlark translation, in starlark-go, under a host that
               predeclares only what the task's grant names
    sandbox    the same Python programs in smolagents' LocalPythonExecutor
    camel      a CaMeL translation, run as the plan by CaMeL's reference
               interpreter under CaMeL's own policies

Every verdict comes from a program that ran here, under the same rules
benchmark/run.py applies (verdict_for, observed, the DANGER line), the same
5 second deadline and, where the runtime can take one, the same 256 MB cap.
A runtime that brings its own limit (Sabline, WASI, Starlark) is given
5 s of it, and the harness waits BACKSTOP seconds before killing it, so the
limit that fires is the runtime's own; Deno and plain Python are killed by
the harness at 5 s. smolagents' own limit cannot fire before a program
ends, so its host's watchdog stops it 5 s after interpretation begins.
CaMeL has none; its host gives the plan 30 s of interpretation, because
its interpreter's speed would otherwise decide a correct program's verdict
(camel_cell says why). For each cell the record keeps the commands that ran
and what they printed, masked of machine-specific paths and ports, so every
number can be re-derived by hand. competitors/README.md has the rules and
what each column is and is not.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from typing import Any

import run as bench          # benchmark/run.py: the corpus, the rules, the listeners
import sabline               # the checkout's: run.py put it first on sys.path

HERE = bench.HERE
ROOT = bench.ROOT
COMP = os.path.join(HERE, "competitors")
RESULTS = os.path.join(COMP, "results.json")
PINS = os.path.join(COMP, "runtimes.json")
HOSTS = os.path.join(COMP, "hosts")
RT_DIR = os.environ.get("SABLINE_COMPETITORS_RT",
                        os.path.join(COMP, ".runtimes"))
TOOLS = ("sabline", "deno", "python", "wasi", "starlark", "sandbox", "camel")
NEW_TOOLS = ("wasi", "starlark", "sandbox", "camel")
TIMEOUT = bench.TIMEOUT
MEMORY_MB = bench.MEMORY_MB
BACKSTOP = TIMEOUT + 5       # for a runtime whose own 5 s limit should fire
CAMEL_DEADLINE = 30          # of interpretation: see camel_cell
CAMEL_BACKSTOP = 90          # CaMeL's host imports for seconds first
EXT = {"starlark": ".star", "camel": ".camel"}
KEEP = 600                   # characters of each output kept in the record

LABEL = {
    "sabline": "Sabline", "deno": "Deno", "python": "Python (no sandbox)",
    "wasi": "WASI (wasmtime)", "starlark": "Starlark",
    "sandbox": "Python sandbox (smolagents)", "camel": "CaMeL",
}


# ---- the runtimes -----------------------------------------------------------

def _pins() -> dict[str, Any]:
    with open(PINS, encoding="utf-8") as f:
        return dict(json.load(f))


def _exe(path: str) -> str | None:
    for p in (path, path + ".exe"):
        if os.path.isfile(p):
            return p
    return None


def find_runtimes(deno_hint: str | None = None) -> dict[str, dict[str, Any]]:
    """What is installed, and its version. A tool that is missing has
    {"absent": reason}; its cells read NOT RUN, never an estimate."""
    found: dict[str, dict[str, Any]] = {}
    found["sabline"] = {"version": sabline.VERSION,
                        "detail": "prover " + ("present" if bench.HAVE_PROVER
                                               else "ABSENT")}
    found["python"] = {"version": platform.python_version(),
                       "path": sys.executable}
    deno = bench.find_deno(deno_hint) or _exe(os.path.join(RT_DIR, "deno", "deno"))
    if deno:
        out = subprocess.run([deno, "--version"], capture_output=True,
                             text=True, timeout=60).stdout
        found["deno"] = {"version": out.split("\n")[0].split()[1],
                         "path": deno}
    else:
        found["deno"] = {"absent": "deno is not installed"}
    wasmtime = _exe(os.path.join(RT_DIR, "wasmtime", "wasmtime"))
    cwasm = os.path.join(RT_DIR, "python-wasi", "python.cwasm")
    lib = os.path.join(RT_DIR, "python-wasi", "lib")
    if os.name == "nt":
        found["wasi"] = {"absent": "the WASI column is run on Linux: a "
                                   "Windows path is not a WASI guest path"}
    elif wasmtime and os.path.isfile(cwasm) and os.path.isdir(lib):
        words = subprocess.run([wasmtime, "--version"], capture_output=True,
                               text=True, timeout=60).stdout.split()
        found["wasi"] = {"version": words[1] if len(words) > 1 else "?",
                         "detail": "CPython " + _pins()["python-wasi"]["version"]
                                   + " WASI build",
                         "path": wasmtime, "cwasm": cwasm, "lib": lib}
    else:
        found["wasi"] = {"absent": "wasmtime or the CPython WASI build is "
                                   "not fetched (competitors/fetch_runtimes.py)"}
    host = _exe(os.path.join(RT_DIR, "starlark-host"))
    if host:
        found["starlark"] = {"version": _starlark_version(host), "path": host}
    else:
        found["starlark"] = {"absent": "the Starlark host is not built "
                                       "(competitors/fetch_runtimes.py)"}
    for tool, dist, module in (("sandbox", "smolagents", "smolagents"),
                               ("camel", "camel", "camel.interpreter")):
        try:
            present = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            present = False
        if present:
            found[tool] = {"version": importlib.metadata.version(dist),
                           "detail": _vcs_commit(dist)}
        else:
            found[tool] = {"absent": f"{dist} is not installed "
                                     f"(requirements/competitors.txt)"}
    return found


def _starlark_version(host: str) -> str:
    """go.starlark.net's version, as the Go toolchain recorded it in the
    binary it built."""
    try:
        out = subprocess.run(["go", "version", "-m", host],
                             capture_output=True, text=True,
                             timeout=60).stdout
    except OSError:
        return "?"
    m = re.search(r"\bdep\s+go\.starlark\.net\s+(\S+)", out)
    return m.group(1) if m else "?"


def _vcs_commit(dist: str) -> str:
    try:
        text = importlib.metadata.distribution(dist).read_text(
            "direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return ""
    if not text:
        return ""
    info = json.loads(text).get("vcs_info") or {}
    return f"commit {info['commit_id']}" if info.get("commit_id") else ""


# ---- a child process --------------------------------------------------------

def child(cmd: list[str], stdin_text: str, timeout: int = TIMEOUT,
          address_cap: bool = True) -> dict[str, Any]:
    """benchmark/run.py's run_child, with this harness's deadline and the
    option to leave RLIMIT_AS off for a runtime that cannot start under it.
    The hash seed is fixed, so a message that prints a set does not change
    order from run to run."""
    saved = bench.TIMEOUT
    bench.TIMEOUT = timeout
    try:
        return bench.run_child(cmd, stdin_text, env={"PYTHONHASHSEED": "0"},
                               address_cap=address_cap)
    finally:
        bench.TIMEOUT = saved


class Masker:
    """Machine-specific detail out of recorded text: the scratch directory,
    the checkout, the runtimes, the interpreter and the two ports."""

    def __init__(self, workdir: str, port: int, other: int) -> None:
        self.pairs: list[tuple[str, str]] = []
        for path, name in ((workdir, "<workdir>"), (RT_DIR, "<runtimes>"),
                           (ROOT, "<repo>"), (sys.executable, "python")):
            for spelling in {path, path.replace("\\", "/"),
                             os.path.realpath(path)}:
                self.pairs.append((spelling, name))
        self.pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self.port, self.other = port, other

    def __call__(self, text: str) -> str:
        text = text.replace("\r", "")
        for spelling, name in self.pairs:
            text = text.replace(spelling, name)
        text = text.replace(f":{self.port}", ":<port>")
        text = text.replace(f":{self.other}", ":<other-port>")
        text = re.sub(r"0x[0-9a-fA-F]+", "0x..", text)
        # smolagents prints its allowlist in set order, which moves with
        # the hash seed; sorted, it is the same list every run
        text = re.sub(r"Authorized imports are: \[([^\]]*)\]",
                      lambda m: "Authorized imports are: [" + ", ".join(
                          sorted(x.strip() for x in m.group(1).split(",")))
                      + "]", text)
        return text


def record_call(cmd: list[str], res: dict[str, Any], mask: Masker,
                stdin_text: str = "") -> dict[str, Any]:
    return {"command": mask(" ".join(_quote(c) for c in cmd)),
            "stdin": mask(stdin_text)[:KEEP],
            "exit": res["exit"], "timed_out": res["timed_out"],
            "stdout": mask(res["stdout"])[:KEEP],
            "stderr": mask(res["stderr"])[:KEEP]}


def _quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or not arg) else arg


# ---- placing a program -------------------------------------------------------

def translation(prog: dict[str, Any], tool: str) -> str:
    return os.path.join(COMP, tool, prog["category_key"],
                        prog["name"] + EXT[tool])


def place(prog: dict[str, Any], tool: str, workdir: str,
          filled: Any) -> dict[str, Any]:
    """Copy what `tool` runs into <workdir>/<id>/<tool>/, every placeholder
    filled: the program, and beside it category 12's dependency (its new
    version) or category 15's vendored library. Returns the program's path
    and the modules placed beside it."""
    here = os.path.join(workdir, prog["id"], tool)
    os.makedirs(here, exist_ok=True)

    def put(src: str, name: str) -> str:
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        dest = os.path.join(here, name)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(filled(text))
        return dest

    modules: list[str] = []
    dep = prog.get("dependency")
    if tool in ("wasi", "sandbox"):
        main = put(prog["files"]["python"], prog["name"] + ".py")
        if dep:
            put(prog["dep_files"]["python"]["new"], dep["module"] + ".py")
            modules.append(dep["module"])
        if prog["category"] == 15:
            put(os.path.join(bench.CORPUS, prog["category_key"],
                             "textcase.py"), "textcase.py")
            modules.append("textcase")
    elif tool == "starlark":
        main = put(translation(prog, tool), prog["name"] + ".star")
        if dep:
            put(os.path.join(COMP, "starlark", prog["category_key"],
                             prog["name"], dep["new"], dep["module"] + ".star"),
                dep["module"] + ".star")
        if prog["category"] == 15:
            put(os.path.join(COMP, "starlark", prog["category_key"],
                             "textcase.star"), "textcase.star")
    else:                                       # camel: one file, no modules
        main = put(translation(prog, tool), prog["name"] + ".camel")
    return {"main": main, "modules": modules, "dir": here}


def source_of(prog: dict[str, Any], tool: str) -> str:
    """The file whose DANGER line the static step is held to."""
    if tool in ("wasi", "sandbox"):
        return str(prog["files"]["python"])
    if tool == "starlark" and prog.get("dependency"):
        dep = prog["dependency"]
        return os.path.join(COMP, "starlark", prog["category_key"],
                            prog["name"], dep["new"], dep["module"] + ".star")
    return translation(prog, tool)


def danger_line(path: str, prog: dict[str, Any]) -> int | None:
    with open(path, encoding="utf-8") as f:
        hits = [i for i, line in enumerate(f, 1) if "DANGER" in line]
    if prog["dangerous"] and len(hits) != 1:
        raise bench.CorpusError(f"{prog['id']}: {path}: expected exactly one "
                                f"DANGER marker, found {len(hits)}")
    if not prog["dangerous"] and hits:
        raise bench.CorpusError(f"{prog['id']}: {path}: a control must not "
                                f"carry a DANGER marker")
    return hits[0] if hits else None


def indent_loop_span(path: str, line: int) -> set[int]:
    """The header of the innermost loop around `line` in an indentation-
    delimited file, and the first statement after it: the lines where a
    loop's own diagnostic lands (benchmark/run.py's rule for Deno, for
    Python-shaped files)."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    def indent(s: str) -> int:
        return len(s) - len(s.lstrip())

    target = indent(lines[line - 1])
    for i in range(line - 1, -1, -1):
        text = lines[i].strip()
        if text.startswith(("while ", "for ")) and (
                i == line - 1 or indent(lines[i]) < target):
            span = {i + 1}
            for k in range(i + 1, len(lines)):
                if lines[k].strip() and indent(lines[k]) <= indent(lines[i]):
                    span.add(k + 1)
                    break
            return span
    return set()


def row_notes(prog: dict[str, Any], tool: str) -> list[str]:
    """NOT-LIKE-FOR-LIKE lines a translation carries, from the program and,
    in category 12, its dependency."""
    paths = []
    if tool in ("starlark", "camel"):
        paths.append(translation(prog, tool))
    if tool == "starlark" and prog.get("dependency"):
        paths.append(source_of(prog, tool))
    notes = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"NOT-LIKE-FOR-LIKE:\s*(.+)", line)
                if m:
                    notes.append(m.group(1).strip())
    return notes


# ---- the new columns ---------------------------------------------------------

def grants_for(needs: list[str]) -> list[str]:
    out = []
    for n in needs:
        out += ["--grant", n]
    return out


PY_EXCEPTION = re.compile(r"^[A-Za-z_][\w.]*(?:Error|Exception|Exit)\b")


def short_error(stderr: str) -> str:
    """The line of an error that says what happened, without the frames:
    a host's own error line, or the last line of a Python traceback."""
    lines = [ln.strip() for ln in stderr.split("\n") if ln.strip()]
    for s in lines:
        for prefix in ("starlark-error: ", "sandbox-error: ", "camel-error: "):
            if s.startswith(prefix):
                return s[len(prefix):]
    for s in reversed(lines):
        if PY_EXCEPTION.match(s):
            return s
    return str(bench.first_error_line(stderr))


def wasi_cell(prog: dict[str, Any], placed: dict[str, Any], needs: list[str],
              stdin_text: str, rt: dict[str, Any],
              mask: Masker) -> dict[str, Any]:
    code = placed["dir"]
    cmd = [rt["path"], "run", "--allow-precompiled",
           "-W", f"timeout={TIMEOUT}s",
           "-W", f"max-memory-size={MEMORY_MB * 1024 * 1024}",
           "--dir", f"{rt['lib']}::/lib", "--dir", f"{code}::{code}"]
    grant = ["stdin and stdout inherited; the program's own directory "
             "preopened so the interpreter can read it"]
    for n in needs:
        if n.startswith("fs:read:"):
            d = n[len("fs:read:"):]
            cmd += ["--dir", f"{d}::{d}"]
            grant.append(f"--dir for {mask(d)} (read and write: the CLI's "
                         f"--dir has no read-only form)")
        elif n.startswith("net:"):
            grant.append(f"{n.split(':', 1)[0]}:{mask(n.split(':', 1)[1])} "
                         f"NOT EXPRESSIBLE: this CPython build has no "
                         f"sockets, so no host can be granted")
        elif n.startswith("ffi:"):
            grant.append(f"{n}: built into the interpreter")
    grant.append("no environment variables (none passed with --env)")
    cmd += [rt["cwasm"], placed["main"]]
    res = child(cmd, stdin_text, timeout=BACKSTOP, address_cap=False)
    calls = [record_call(cmd, res, mask, stdin_text)]
    stopped = res["timed_out"] or res["exit"] != 0
    if "wasm trap: interrupt" in res["stderr"]:
        run_bit = f"run: stopped by wasmtime's own -W timeout at {TIMEOUT} s"
    elif res["timed_out"]:
        run_bit = f"run: killed by the harness at {BACKSTOP} s"
    elif res["exit"] != 0:
        run_bit = f"run: exit {res['exit']}, {mask(short_error(res['stderr']))}"
    else:
        run_bit = "run: exit 0"
    return {"stopped": stopped, "flagged": False, "stdout": res["stdout"],
            "calls": calls, "grant": "; ".join(grant),
            "bits": ["static step: none (the guest is not analysed)",
                     run_bit], "during": res}


def starlark_cell(prog: dict[str, Any], placed: dict[str, Any],
                  needs: list[str], stdin_text: str, rt: dict[str, Any],
                  mask: Masker) -> dict[str, Any]:
    grant_args = grants_for(needs)
    grant = ["read_line, print, json and math"]
    for n in needs:
        if n.startswith("fs:read:"):
            grant.append(f"read_file, refused outside {mask(n[8:])}")
        elif n.startswith("net:"):
            grant.append(f"http_get and http_post, refused for any host but "
                         f"{mask(n[4:])}")
    grant.append("nothing else is ever predeclared")
    check_cmd = [rt["path"], "check", placed["main"]] + grant_args
    chk = child(check_cmd, "", timeout=BACKSTOP, address_cap=False)
    calls = [record_call(check_cmd, chk, mask)]
    try:
        diags = json.loads(chk["stdout"])["diagnostics"]
    except (ValueError, KeyError):
        raise bench.CorpusError(f"{prog['id']}: starlark-host check printed "
                                f"no diagnostics: {chk['stderr'][:200]}")
    src = source_of(prog, "starlark")
    line = danger_line(src, prog)
    accepted: set[int] = set()
    if line and not prog.get("dependency"):
        accepted = {line} | (indent_loop_span(src, line)
                             if prog["kind"] in ("loop", "memory") else set())
    # Deno's rule (benchmark/run.py): a diagnostic on the dangerous line, or
    # on the header of the loop around it, is credited; one elsewhere is
    # recorded and not credited; on a control, any diagnostic is a flag
    on_target = [d for d in diags if d["line"] in accepted]
    bits = []
    if diags:
        said = "; ".join(f"{d['message']}, line {d['line']}" for d in diags)
        if prog["dangerous"] and not on_target:
            # refused before running, but not on the dangerous line: held to
            # the rule Deno is held to, it is not a catch before running.
            # Nothing ran, so the danger did not happen: the program was
            # stopped, and the evidence says how
            bits.append(f"check elsewhere (not credited): {said}")
            return {"stopped": True, "flagged": False, "stdout": "",
                    "calls": calls, "grant": "; ".join(grant),
                    "bits": bits + ["run: not attempted, did not resolve"],
                    "during": None}
        bits.append(f"check: {said}")
        return {"stopped": False, "flagged": True, "stdout": "",
                "calls": calls, "grant": "; ".join(grant),
                "bits": bits + ["run: not attempted, did not resolve"],
                "during": None}
    run_cmd = ([rt["path"], "run", placed["main"]] + grant_args
               + ["--timeout", str(TIMEOUT)])
    res = child(run_cmd, stdin_text, timeout=BACKSTOP, address_cap=False)
    calls.append(record_call(run_cmd, res, mask, stdin_text))
    if res["exit"] == 3:
        run_bit = f"run: cancelled by the host at {TIMEOUT} s"
    elif res["timed_out"]:
        run_bit = f"run: killed by the harness at {BACKSTOP} s"
    elif res["exit"] != 0:
        run_bit = f"run: exit {res['exit']}, {mask(short_error(res['stderr']))}"
    else:
        run_bit = "run: exit 0"
    return {"stopped": res["timed_out"] or res["exit"] != 0, "flagged": False,
            "stdout": res["stdout"], "calls": calls, "grant": "; ".join(grant),
            "bits": ["check: nothing", run_bit], "during": res}


def sandbox_cell(prog: dict[str, Any], placed: dict[str, Any],
                 needs: list[str], stdin_text: str,
                 mask: Masker) -> dict[str, Any]:
    cmd = ([sys.executable, os.path.join(HOSTS, "sandbox_host.py"),
            placed["main"]] + grants_for(needs))
    for m in placed["modules"]:
        cmd += ["--module", m]
    grant = ["smolagents' base modules, json and dataclasses (pure), sys "
             "for the input"]
    for n in needs:
        if n.startswith("fs:read:"):
            grant.append("the builtin open (smolagents cannot scope it to "
                         "a directory)")
        elif n.startswith("net:"):
            grant.append("urllib.request (smolagents cannot scope it to a "
                         "host)")
    if placed["modules"]:
        grant.append("the vendored module(s) " + ", ".join(placed["modules"])
                     + ", imported by real Python outside the interpreter")
    # smolagents' own 5 s timeout cannot fire before the program ends (it
    # waits for its worker thread), so the host's watchdog stops it 5 s
    # after interpretation begins; every loop in the corpus runs for 12 s or
    # more in smolagents before its iteration cap ends it, so the watchdog
    # is what fires on any machine
    res = child(cmd, stdin_text, timeout=BACKSTOP)
    calls = [record_call(cmd, res, mask, stdin_text)]
    if res["exit"] == 3 and "stopped by the host" in res["stderr"]:
        run_bit = (f"run: stopped by the host at {TIMEOUT} s of "
                   f"interpretation (smolagents' own {TIMEOUT} s timeout had "
                   f"not fired)")
    elif res["timed_out"]:
        run_bit = f"run: killed by the harness at {BACKSTOP} s"
    elif res["exit"] != 0:
        err = mask(short_error(res["stderr"]))
        err = re.sub(r"^InterpreterError: Code execution failed at line "
                     r"'.*?' due to: ", "", err)
        run_bit = f"run: exit {res['exit']}, {err}"
    else:
        run_bit = "run: exit 0"
    return {"stopped": res["timed_out"] or res["exit"] != 0, "flagged": False,
            "stdout": res["stdout"], "calls": calls, "grant": "; ".join(grant),
            "bits": ["static step: none (smolagents interprets as it goes)",
                     run_bit], "during": res}


def camel_cell(prog: dict[str, Any], placed: dict[str, Any],
               stdin_text: str, mask: Masker) -> dict[str, Any]:
    # CaMeL has no limit of its own; the host stops the plan CAMEL_DEADLINE
    # s after interpretation begins (importing CaMeL and AgentDojo takes
    # seconds first). Not TIMEOUT: CaMeL's interpreter takes about 4.5 s
    # for 07c's 90,000 steps on the recording machine, so at 5 s a correct
    # program's verdict would depend on the machine. Every unbounded loop is
    # a `while`, which CaMeL refuses, so no danger depends on the deadline.
    cmd = [sys.executable, os.path.join(HOSTS, "camel_host.py"),
           placed["main"], "--timeout", str(CAMEL_DEADLINE)]
    res = child(cmd, stdin_text, timeout=CAMEL_BACKSTOP, address_cap=False)
    calls = [record_call(cmd, res, mask, stdin_text)]
    if res["exit"] == 3:
        run_bit = (f"run: stopped by the host at {CAMEL_DEADLINE} s of "
                   f"interpretation (CaMeL has no time limit of its own)")
    elif res["timed_out"]:
        run_bit = f"run: killed by the harness at {CAMEL_BACKSTOP} s"
    elif res["exit"] != 0:
        run_bit = f"run: exit {res['exit']}, {mask(short_error(res['stderr']))}"
    else:
        run_bit = "run: exit 0"
    return {"stopped": res["timed_out"] or res["exit"] != 0, "flagged": False,
            "stdout": res["stdout"], "calls": calls,
            "grant": "CaMeL's tool set and policies, the same for every "
                     "program (camel_host.py); the task's needs are not an "
                     "input to CaMeL",
            "bits": ["static step: none (the plan is parsed, then "
                     "interpreted)", run_bit], "during": res}


# ---- the existing columns, with their commands --------------------------------

CALLS: list[tuple[list[str], dict[str, Any], str]] = []
_run_child = bench.run_child


def _recording_run_child(cmd: Any, stdin_text: Any, env: Any = None,
                         address_cap: bool = True,
                         bare_loader: bool = False) -> dict[str, Any]:
    res = _run_child(cmd, stdin_text, env, address_cap, bare_loader)
    CALLS.append((list(cmd), res, stdin_text))
    return res


def sabline_calls(prog: dict[str, Any], cell: dict[str, Any], path: str,
                  needs: list[str], stdin_text: str, placed: Any,
                  mask: Masker) -> list[dict[str, Any]]:
    """Sabline's column is benchmark/run.py's, which calls the library; the
    record gives each call, what it returned, and the command line that
    reproduces it."""
    p = mask(path)
    before = cell["before"]
    out = [{"command": f"sabline check {p} --json",
            "call": "sabline.check(source)",
            "result": {"problems": before["check"]}},
           {"command": f"sabline audit {p} --json",
            "call": "sabline.audit(source)",
            "result": {k: before[k] for k in ("audit_effects",
                                              "audit_ffi_modules",
                                              "beyond_needs", "loops_unshown",
                                              "loops_unshown_in")}}]
    if placed:
        dep = prog["dependency"]
        out.append({"command": f"sabline deps-diff dir:{mask(placed['versions'])}"
                               f" {dep['old']} {dep['new']}",
                    "call": "sabline.deps_diff(...)",
                    "result": before.get("deps_diff")})
    allow = ",".join(mask(n) for n in needs)
    out.append({"command": f"sabline run {p} --allow {allow}",
                "call": f"sabline.run(source, allow=[{allow}], "
                        f"stdin=<stdin>, timeout={TIMEOUT}, "
                        f"max_memory_mb={MEMORY_MB})",
                "stdin": mask(stdin_text),
                "result": cell["during"]})
    return out


# ---- one program -------------------------------------------------------------

def run_program(prog: dict[str, Any], tools: tuple[str, ...],
                rts: dict[str, dict[str, Any]], port: int, other: int,
                workdir: str, mask: Masker) -> dict[str, Any]:
    row: dict[str, Any] = {k: prog[k] for k in (
        "id", "category", "category_title", "name", "description",
        "dangerous", "kind")}
    row["needs"] = [mask(n) for n in prog["needs"]]
    row["stdin"] = prog["stdin"]
    row["cells"] = {}
    for tool in tools:
        work_path = os.path.join(workdir, f"{prog['id']}.{tool}.txt")
        if os.path.exists(work_path):
            os.remove(work_path)

        def f(t: str, tool: str = tool, work_path: str = work_path,
              slashes: bool = False) -> str:
            return str(bench.fill(t, work_path, workdir, port, other,
                                  prog["id"], tool, slashes=slashes))

        stdin_text = f(prog["stdin"])
        needs = [f(n) for n in prog["needs"]]
        rt = rts.get(tool, {})
        if "absent" in rt:
            row["cells"][tool] = {"verdict": "not-run",
                                  "evidence": "NOT RUN: " + rt["absent"],
                                  "calls": [], "grant": "", "notes": []}
            continue
        cell = run_tool(prog, tool, rt, work_path, stdin_text, needs, f,
                        port, other, workdir, mask)
        row["cells"][tool] = cell
        if os.path.exists(work_path):
            os.remove(work_path)
    return row


def run_tool(prog: dict[str, Any], tool: str, rt: dict[str, Any],
             work_path: str, stdin_text: str, needs: list[str], f: Any,
             port: int, other: int, workdir: str,
             mask: Masker) -> dict[str, Any]:
    def slashed(t: str) -> str:
        return str(f(t, slashes=True))

    if tool in ("sabline", "deno", "python"):
        placed = (bench.place_dependency(prog, tool, workdir, slashed)
                  if prog.get("dependency") else None)
        CALLS.clear()
        if tool == "sabline":
            cell = bench.sabline_row(prog, stdin_text, work_path, needs, placed)
            path = placed["caller"] if placed else prog["files"]["sabline"]
            calls = sabline_calls(prog, cell, path, needs, stdin_text, placed,
                                  mask)
            grant = "sabline.run(allow=[" + ", ".join(
                mask(n) for n in needs) + "])"
        elif tool == "deno":
            flags = [f(x) for x in prog.get("deno_flags", [])]
            deno_path = (bench._place_deno_remote(prog, workdir, f)
                         if any(x.startswith("--allow-import") for x in flags)
                         else None)
            cell = bench.settle_memory_row(prog, bench.deno_row(
                prog, stdin_text, work_path, rt["path"], port, flags, placed,
                deno_path))
            calls = [record_call(c, r, mask, s) for c, r, s in CALLS]
            grant = ("no --allow-* flag" if not flags
                     else " ".join(mask(x) for x in flags))
        else:
            cell = bench.settle_memory_row(prog, bench.python_row(
                prog, stdin_text, work_path, port, placed))
            calls = [record_call(c, r, mask, s) for c, r, s in CALLS]
            grant = "none: plain Python has no budget"
        cell["evidence"] = mask(cell["evidence"])
        return {"verdict": cell["verdict"], "evidence": cell["evidence"],
                "observed": cell["observed"], "grant": grant, "calls": calls,
                "notes": automatic_notes(prog, tool, cell["verdict"],
                                         cell["evidence"])}

    placed = place(prog, tool, workdir, slashed)
    if tool == "wasi":
        got = wasi_cell(prog, placed, needs, stdin_text, rt, mask)
    elif tool == "starlark":
        got = starlark_cell(prog, placed, needs, stdin_text, rt, mask)
    elif tool == "sandbox":
        got = sandbox_cell(prog, placed, needs, stdin_text, mask)
    else:
        got = camel_cell(prog, placed, stdin_text, mask)
    seen = None if got["flagged"] else bench.observed(
        prog["kind"], prog["id"], tool, work_path, got["stdout"])
    verdict = bench.verdict_for(prog, False, got["flagged"], got["stopped"],
                                seen)
    bits = list(got["bits"])
    if seen is True:
        bits.append("effect happened")
    elif seen is False and not got["stopped"]:
        bits.append("effect did not happen")
    cell = {"verdict": verdict, "evidence": "; ".join(bits), "during": None,
            "observed": seen}
    if got["during"] is not None:
        d: dict[str, Any] = got["during"]
        cell["during"] = {"exit": d["exit"], "timed_out": d["timed_out"]}
        # run.py's settling (which of the memory cap and the deadline fired
        # varies with load) applies to a stop by a limit, and to nothing
        # else: a runtime that refused the loop outright keeps its reason
        if limit_stop(d):
            cell = bench.settle_memory_row(prog, cell)
    out = got["stdout"] + "\n" + (got["during"] or {}).get("stderr", "")
    return {"verdict": cell["verdict"], "evidence": cell["evidence"],
            "observed": seen, "grant": got["grant"], "calls": got["calls"],
            "notes": row_notes(prog, tool) + automatic_notes(
                prog, tool, cell["verdict"], cell["evidence"] + "\n" + out)
            + FIXED_NOTES.get((prog["id"], tool), [])}


def limit_stop(res: dict[str, Any]) -> bool:
    """Was the run stopped by a time or memory limit (rather than refused,
    or crashed on its defect)?"""
    text = str(res.get("stderr", ""))
    if res["timed_out"] or res["exit"] == 3:            # a deadline
        return True
    if any(s in text for s in ("wasm trap", "MemoryError",
                               "iterations in While loop")):
        return True                                     # a cap, or smolagents' loop cap
    if any(s in text for s in ("camel-error:", "starlark-error:",
                               "sandbox-error:")):
        return False                                    # a host said why
    # killed by a signal, or died under the address-space cap before it
    # could write anything
    return res["exit"] not in (0, 1) or (res["exit"] != 0 and not text.strip())


# Facts about one cell that were verified by hand and that the verdict
# alone would misreport. Each says how it was verified.
FIXED_NOTES: dict[tuple[str, str], list[str]] = {
    ("12a", "camel"): [
        "CaMeL allows it because the line posted carries len() of the page, "
        "and CaMeL's reference interpreter treats the length of a private "
        "value as public: posting the page itself, or page.upper(), is "
        "denied (\"The content is not public\"), and posting "
        "str(len(page)) is not. Only a size leaves; whether a size is "
        "sensitive is a policy question."],
    ("07c", "camel"): [
        "Not like-for-like: CaMeL is given 30 s of interpretation, not the "
        "5 s every other tool gets. Its interpreter needs about 4.5 s for "
        "this correct program's 90,000 steps on the recording machine (plain "
        "Python: under 0.1 s), so under 5 s it would be a false positive on "
        "any slower machine, and the cell would measure the machine."],
    ("05c", "camel"): [
        "Not like-for-like: CaMeL is given 30 s, not 5. It needs about 7.4 s "
        "for this program here; under 5 s the deadline would stop it, and "
        "the benchmark's rule would credit that as a catch."],
}


def automatic_notes(prog: dict[str, Any], tool: str, verdict: str,
                    evidence: str) -> list[str]:
    """What the harness knows about a cell that the verdict alone hides:
    above all, a catch that came from a failure unrelated to the danger
    rather than from a refusal of it."""
    notes = []
    caught = verdict.startswith("caught")
    needs_net = any(n.startswith("net:") for n in prog["needs"])
    if tool == "wasi" and needs_net and caught:
        notes.append("Not like-for-like: the task's own request to the "
                     "granted host could not be made either - this build has "
                     "no network - so the catch cost the task.")
    if tool == "sandbox" and caught and "no attribute 'request'" in evidence:
        notes.append("Not a refusal: smolagents 1.26.0 binds `import "
                     "urllib.request` wrongly, so `urllib.request.urlopen` "
                     "fails for every URL, granted or not. The task's own "
                     "request fails too.")
    if tool == "sandbox" and caught and "takes no arguments" in evidence:
        notes.append("Not a refusal: smolagents 1.26.0 does not apply "
                     "@dataclass, so building the program's record fails "
                     "before it reaches its dangerous line.")
    if tool == "sandbox" and caught and "erase the existing tool" in evidence:
        notes.append("Not a refusal: `log` is one of smolagents' own tools "
                     "(math.log), so the program's `log = ...` is refused "
                     "before its loop runs.")
    if tool == "sandbox" and prog.get("dependency"):
        notes.append("The dependency is an authorised import, so it runs as "
                     "real Python outside smolagents' interpreter, with the "
                     "process's full authority.")
    slow = ("stopped by the host at" in evidence
            or "killed by the harness" in evidence)
    if slow and prog["kind"] not in ("loop", "memory"):
        if prog["dangerous"]:
            notes.append("Stopped by the deadline, not by anything that "
                         "noticed the defect: the program was still running "
                         "at 5 s. Credited by the benchmark's rule, unearned.")
        else:
            notes.append("A false positive by the benchmark's rule, and a "
                         "cost rather than a mistake: the program is correct "
                         "and finite, and was still running at 5 s.")
    if tool == "starlark" and "check elsewhere (not credited)" in evidence:
        notes.append("Refused before running, but on a line the benchmark "
                     "does not credit: the loop or call it rejects is not on "
                     "the DANGER line. That is the rule Deno is held to; "
                     "Sabline's audit flags an unbounded loop wherever it "
                     "is, and is credited for it.")
    if tool == "deno" and caught and "require is not defined" in evidence:
        notes.append("Not a refusal: the JavaScript version calls require, "
                     "which Deno does not define, so it crashes before any "
                     "permission is asked. A defect in the corpus's .js, "
                     "credited to Deno by the benchmark's rule.")
    return notes


# ---- the record ----------------------------------------------------------------

def summarise(categories: Any, rows: list[dict[str, Any]],
              tools: tuple[str, ...]) -> dict[str, Any]:
    verdicts = list(bench.VERDICTS) + ["not-run"]
    per_cat = []
    for cat in categories:
        mine = [r for r in rows if r["category"] == cat["number"]]
        if not mine:
            continue
        entry: dict[str, Any] = {"number": cat["number"],
                                 "title": cat["title"], "tools": {}}
        for t in tools:
            counts = {v: 0 for v in verdicts}
            for r in mine:
                counts[r["cells"][t]["verdict"]] += 1
            entry["tools"][t] = counts
        per_cat.append(entry)
    totals = {}
    for t in tools:
        counts = {v: 0 for v in verdicts}
        for r in rows:
            counts[r["cells"][t]["verdict"]] += 1
        totals[t] = counts
    return {"categories": per_cat, "totals": totals}


def compare(rows: list[dict[str, Any]], recorded: dict[str, Any],
            rts: dict[str, dict[str, Any]]) -> list[str]:
    """Every verdict and every evidence line must be what the record says,
    and every runtime the version it names: a number is only comparable to
    one measured on the same runtime."""
    diffs = []
    for tool, info in recorded["meta"]["runtimes"].items():
        now = rts.get(tool, {})
        if tool == "sabline":
            continue            # this checkout: any verdict it moves fails below
        if "absent" in now:
            diffs.append(f"{tool}: NOT RUN here ({now['absent']}); the record "
                         f"has it")
            continue
        here, was = str(now.get("version")), str(info.get("version"))
        if tool == "python":    # a patch release moves under setup-python
            here, was = here.rsplit(".", 1)[0], was.rsplit(".", 1)[0]
        if here != was:
            diffs.append(f"{tool}: version {now.get('version')} here, "
                         f"{info.get('version')} in the record")
    old = {r["id"]: r for r in recorded["programs"]}
    for r in rows:
        prev = old.get(r["id"])
        if prev is None:
            diffs.append(f"{r['id']}: not in the record")
            continue
        for t, cell in r["cells"].items():
            was = prev["cells"].get(t)
            if was is None:
                diffs.append(f"{r['id']} {t}: not in the record")
                continue
            for key in ("verdict", "evidence"):
                if cell[key] != was[key]:
                    diffs.append(f"{r['id']} {t} {key}:\n      now      "
                                 f"{cell[key]}\n      recorded {was[key]}")
    return diffs


def self_test() -> int:
    """--check is only worth anything if it goes red. Hold compare() to
    the record with a fault injected each way it must catch - a verdict, an
    evidence line, a runtime's version, a runtime gone - and the one
    difference it must let through, a Python patch release. Needs no
    runtime: it reads the record."""
    import copy
    with open(RESULTS, encoding="utf-8") as fh:
        rec = json.load(fh)
    rts = {t: dict(v) for t, v in rec["meta"]["runtimes"].items()}
    rows = rec["programs"]
    faults = 0

    def expect(label: str, diffs: list[str], want: int) -> None:
        nonlocal faults
        ok = len(diffs) == want
        faults += not ok
        print(f"  {'ok   ' if ok else 'WRONG'} {label}: {len(diffs)} "
              f"difference(s), {want} expected")

    expect("the record against itself", compare(rows, rec, rts), 0)
    for key, value in (("verdict", "caught-during-run"),
                       ("evidence", "run: exit 0")):
        bad = copy.deepcopy(rows)
        cell = bad[0]["cells"]["camel"]
        cell[key] = value if cell[key] != value else "missed"
        expect(f"one {key} moved", compare(bad, rec, rts), 1)
    for tool, change in (("deno", {"version": "0.0.0"}),
                         ("wasi", {"absent": "not fetched"})):
        moved = copy.deepcopy(rts)
        moved[tool] = change
        expect(f"{tool} {'gone' if 'absent' in change else 'at another version'}",
               compare(rows, rec, moved), 1)
    patch = copy.deepcopy(rts)
    major, minor = str(patch["python"]["version"]).split(".")[:2]
    patch["python"]["version"] = f"{major}.{minor}.999"
    expect("a Python patch release", compare(rows, rec, patch), 0)
    print(f"compete.py --self-test: {'0 wrong' if not faults else f'{faults} WRONG'}")
    return 1 if faults else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", help="comma-separated program ids")
    ap.add_argument("--tools", help="comma-separated tools (with --only)")
    ap.add_argument("--versions", action="store_true")
    ap.add_argument("--deno", help="path to the deno executable")
    ap.add_argument("--self-test", action="store_true",
                    help="show that --check's comparison fails on a change")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    rts = find_runtimes(args.deno)
    if args.versions:
        for t in TOOLS:
            info = rts[t]
            print(f"{t:<9} " + (f"NOT RUN: {info['absent']}" if "absent" in info
                                else f"{info['version']} {info.get('detail', '')}"))
        return 0
    if args.tools and not args.only:
        ap.error("--tools needs --only: the record always has every column")
    tools = tuple(t for t in TOOLS if not args.tools
                  or t in args.tools.split(","))
    try:
        categories, programs = bench.load_corpus()
    except bench.CorpusError as e:
        print("corpus error:", e, file=sys.stderr)
        return 2
    if args.only:
        wanted = set(args.only.split(","))
        programs = [p for p in programs if p["id"] in wanted]

    bench.run_child = _recording_run_child
    server, port = bench.start_listener()
    other_server, other = bench.start_listener()
    bench.PORTS_IN_USE[:] = [port, other]
    workdir = tempfile.mkdtemp(prefix="sabline-compete-")
    mask = Masker(workdir, port, other)
    for d in ("granted", "outside"):
        os.makedirs(os.path.join(workdir, d), exist_ok=True)
    fixtures = {"granted/notes.txt": "granted-notes\n",
                "outside/secret.txt": "outside-secret\n",
                "granted/.env": "API_TOKEN=bench-not-a-real-token\n",
                "granted/service.pem": "-----BEGIN PRIVATE KEY-----\n"
                                       "bench-not-a-real-key\n"
                                       "-----END PRIVATE KEY-----\n"}
    for name, text in fixtures.items():
        with open(os.path.join(workdir, name), "w") as fh:
            fh.write(text)
    os.environ["BENCH_SECRET"] = bench.SECRET
    rows = []
    try:
        for prog in programs:
            print(f"  {prog['id']} {prog['name']:<24}", end="", flush=True,
                  file=sys.stderr)
            try:
                row = run_program(prog, tools, rts, port, other, workdir, mask)
            except bench.CorpusError as e:
                print("\ncorpus error:", e, file=sys.stderr)
                return 2
            rows.append(row)
            print(" ".join(f"{t}={row['cells'][t]['verdict']}" for t in tools),
                  file=sys.stderr)
    finally:
        server.shutdown()
        other_server.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)

    if args.only:
        for r in rows:
            print(f"{r['id']} {r['name']}")
            for t in tools:
                c = r["cells"][t]
                print(f"  {t:<9} {c['verdict']:<18} {c['evidence']}")
                for n in c["notes"]:
                    print(f"  {'':<9} note: {n}")
        return 0

    meta = {"date": date.today().isoformat(),
            "platform": f"{platform.system()} {platform.machine()}",
            "timeout_s": TIMEOUT, "memory_mb": MEMORY_MB,
            "backstop_s": BACKSTOP,
            "runtimes": {t: {k: v for k, v in rts[t].items()
                             if k not in ("path", "cwasm", "lib")}
                         for t in TOOLS}}
    result = {"schema": "sabline.competitors/1", "meta": meta,
              "labels": LABEL, "programs": rows,
              **summarise(categories, rows, TOOLS)}
    if args.check:
        with open(RESULTS, encoding="utf-8") as fh:
            recorded = json.load(fh)
        diffs = compare(rows, recorded, rts)
        if diffs:
            print(f"{len(diffs)} difference(s) from competitors/results.json:",
                  file=sys.stderr)
            for d in diffs:
                print("  " + d, file=sys.stderr)
            return 1
        print(f"every cell of {len(rows)} programs x {len(TOOLS)} tools "
              f"matches competitors/results.json (recorded "
              f"{recorded['meta']['date']})", file=sys.stderr)
        return 0
    if args.record:
        with open(RESULTS, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"wrote {os.path.relpath(RESULTS, ROOT)}", file=sys.stderr)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
