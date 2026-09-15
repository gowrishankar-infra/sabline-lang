#!/usr/bin/env python3
"""The Velaris comparison benchmark.

    python benchmark/run.py            # all 67 programs -> RESULTS.md, results.json
    python benchmark/run.py --quick    # one program per category, table on stdout
    python benchmark/run.py --check    # also compare verdicts with results.json
    python benchmark/run.py --only 03a,10c

For every program in corpus.json and every tool (Velaris, Deno, plain
Python) this records one verdict:

    caught-before-run   flagged by a static step, before anything ran
    caught-during-run   refused, stopped or crashed while running, and the
                        dangerous effect did not happen
    missed              ran to the end, or the dangerous effect happened
    not-applicable      nothing to catch (control group) and nothing flagged
    false-positive      nothing to catch, but the tool flagged or stopped it
    tool-absent         the tool is not installed on this machine

The rules are in README.md. Nothing here is tuned per program: the same
budget, the same timeout, the same memory cap and the same observation
checks apply to every row.
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus")
TIMEOUT = 5            # seconds, for every tool
MEMORY_MB = 256        # for every tool, where the platform lets us
SENTINEL = "spawned-child-ran"   # printed by the child a program spawns
MODULE_MARK = "module-reached"   # printed when a module call came back
TOOLS = ("velaris", "deno", "python")
VERDICTS = ("caught-before-run", "caught-during-run", "missed",
            "not-applicable", "false-positive", "tool-absent")
SCOPED_KINDS = ("fs-scope", "net-scope", "env")
PORTS_IN_USE: list[Any] = []          # every listener port, masked in evidence
EXT = {"velaris": ".vel", "deno": ".js", "python": ".py"}

sys.path.insert(0, ROOT)
import velaris  # noqa: E402  (the checkout being benchmarked)
from suite_dirs import isolate  # noqa: E402

isolate("benchmark")                  # its own directory
HAVE_PROVER = velaris.HAVE_Z3


class CorpusError(Exception):
    """The corpus is inconsistent - a program that does not do what its
    entry says. Exit 2, never a verdict."""


# ---------------------------------------------------------------- corpus

def load_corpus() -> tuple[Any, ...]:
    with open(os.path.join(HERE, "corpus.json"), encoding="utf-8") as f:
        data = json.load(f)
    programs = []
    for cat in data["categories"]:
        for p in cat["programs"]:
            p = dict(p)
            p["category"] = cat["number"]
            p["category_key"] = cat["key"]
            p["category_title"] = cat["title"]
            p["files"] = {t: os.path.join(CORPUS, cat["key"], p["name"] + EXT[t])
                          for t in TOOLS}
            dep = p.get("dependency")
            if dep:
                # category 12: the caller above, and one directory per
                # version of the dependency it imports
                p["dep_files"] = {t: {side: os.path.join(
                    CORPUS, cat["key"], p["name"], dep[side],
                    dep["module"] + EXT[t]) for side in ("old", "new")}
                    for t in TOOLS}
            for t, path in p["files"].items():
                more = list(p["dep_files"][t].values()) if dep else []
                for need in [path] + more:
                    if not os.path.exists(need):
                        raise CorpusError(f"{p['id']}: missing {need}")
            p["danger_line"] = {t: marker_line(p, t) for t in TOOLS}
            programs.append(p)
    return data["categories"], programs


def marker_line(prog: Any, tool: Any) -> Any:
    """The 1-based line carrying the DANGER marker, or None. For a program
    with a dependency the marker is in the dependency's new version: the
    caller and the old version must carry none, since the danger is the
    upgrade."""
    where = prog["files"][tool]
    if prog.get("dependency"):
        for quiet in (where, prog["dep_files"][tool]["old"]):
            with open(quiet, encoding="utf-8") as f:
                if any("DANGER" in line for line in f):
                    raise CorpusError(f"{prog['id']} ({tool}): {quiet} must "
                                      f"not carry a DANGER marker; it goes "
                                      f"in the new version of the dependency")
        where = prog["dep_files"][tool]["new"]
    with open(where, encoding="utf-8") as f:
        hits = [i for i, line in enumerate(f, 1) if "DANGER" in line]
    if prog["dangerous"] and len(hits) != 1:
        raise CorpusError(f"{prog['id']} ({tool}): expected exactly one "
                          f"DANGER marker, found {len(hits)}")
    if not prog["dangerous"] and hits:
        raise CorpusError(f"{prog['id']} ({tool}): a control program "
                          f"must not carry a DANGER marker")
    return hits[0] if hits else None


def loop_span(path: Any, danger_line: Any) -> tuple[Any, ...] | None:
    """(header line, line after the loop) for the innermost loop that
    contains danger_line in a brace-delimited file, else None. Used only
    to decide whether a Deno diagnostic is about the dangerous loop."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    depth = 0
    header = None
    for i in range(danger_line - 1, -1, -1):
        depth += lines[i].count("}") - lines[i].count("{")
        if depth < 0:
            text = lines[i].strip()
            if text.startswith(("while", "for")):
                header = i + 1
                break
            depth = 0    # a block that is not a loop; keep climbing
    if header is None:
        return None
    depth = 0
    for j in range(header - 1, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0 and j >= header - 1 and "{" in "".join(lines[header - 1:j + 1]):
            for k in range(j + 1, len(lines)):
                if lines[k].strip():
                    return header, k + 1
            return header, None
    return header, None


# ---------------------------------------------------------- the listener

class Hits(BaseHTTPRequestHandler):
    paths: list[Any] = []
    by_port: list[Any] = []           # (the listener's port, path), category 12

    def do_GET(self) -> None:
        self._hit()

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        self._hit()

    def _hit(self) -> None:
        Hits.paths.append(self.path)
        Hits.by_port.append((cast("tuple[str, int]",
                                  self.server.server_address)[1], self.path))
        body = b"ok\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


def start_listener() -> tuple[Any, ...]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Hits)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# ------------------------------------------------------- child processes

def _posix_cap() -> Any:
    def pre() -> None:
        try:
            import resource
            cap = MEMORY_MB * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        except Exception:
            pass
    return pre


class _WindowsJob:
    """A job object capping the child's memory; also kills the child's
    own children when the job closes."""

    def __init__(self) -> None:
        import ctypes
        import ctypes.wintypes as w
        self.ctypes = ctypes
        k = ctypes.windll.kernel32  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount",
                "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", w.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", w.DWORD),
                        ("SchedulingClass", w.DWORD)]

        class EXT(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        PROCESS_MEMORY = 0x100
        KILL_ON_CLOSE = 0x2000
        self.job = k.CreateJobObjectW(None, None)
        info = EXT()
        info.BasicLimitInformation.LimitFlags = PROCESS_MEMORY | KILL_ON_CLOSE
        info.ProcessMemoryLimit = MEMORY_MB * 1024 * 1024
        if not k.SetInformationJobObject(self.job, 9, ctypes.byref(info),
                                         ctypes.sizeof(info)):
            raise OSError("SetInformationJobObject failed")
        self.k = k

    def assign(self, proc: Any) -> None:
        if not self.k.AssignProcessToJobObject(self.job, int(proc._handle)):
            raise OSError("AssignProcessToJobObject failed")
        self.ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux

    def close(self) -> None:
        self.k.CloseHandle(self.job)


def run_child(cmd: Any, stdin_text: Any, env: Any = None) -> dict[str, Any]:
    """Run cmd with the benchmark's timeout and memory cap. Returns a
    dict with exit, stdout, stderr, timed_out and which cap applied."""
    full_env = dict(os.environ)
    full_env.update({"NO_COLOR": "1", "PYTHONIOENCODING": "utf-8",
                     "PYTHONUTF8": "1", "BENCH_SECRET": SECRET})
    full_env.update(env or {})
    cap = "none"
    kwargs: dict[str, Any] = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE, env=full_env, cwd=HERE)
    job = None
    if os.name == "nt":
        try:
            job = _WindowsJob()
            kwargs["creationflags"] = 0x4        # CREATE_SUSPENDED
            cap = "job object"
        except Exception:
            job = None
    else:
        kwargs["preexec_fn"] = _posix_cap()
        cap = "RLIMIT_AS" + (" (may not apply on macOS)"
                             if sys.platform == "darwin" else "")
    proc = subprocess.Popen(cmd, **kwargs)
    if job is not None:
        try:
            job.assign(proc)
        except Exception:
            cap = "none"
            proc.kill()
            proc = subprocess.Popen(cmd, **{k: v for k, v in kwargs.items()
                                            if k != "creationflags"})
    timed_out = False
    try:
        out, err = proc.communicate(stdin_text.encode("utf-8"),
                                    timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        out, err = proc.communicate()
    finally:
        if job is not None:
            job.close()
    return {"exit": proc.returncode, "timed_out": timed_out,
            "stdout": out.decode("utf-8", "replace"),
            "stderr": err.decode("utf-8", "replace"), "cap": cap}


def find_deno(explicit: Any = None) -> Any:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    found = shutil.which("deno")
    if found:
        return found
    home = os.path.expanduser("~")
    candidates = [os.path.join(home, ".deno", "bin", "deno"),
                  os.path.join(home, ".deno", "bin", "deno.exe")]
    if os.environ.get("DENO_INSTALL"):
        candidates.append(os.path.join(os.environ["DENO_INSTALL"], "bin",
                                       "deno"))
    if os.environ.get("LOCALAPPDATA"):
        candidates += glob.glob(os.path.join(
            os.environ["LOCALAPPDATA"], "Microsoft", "WinGet", "Packages",
            "DenoLand.Deno_*", "deno.exe"))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# -------------------------------------------------------------- evidence

def tidy(text: Any, port: Any = None, paths: bool = True) -> Any:
    """Strip machine-specific detail so two runs produce the same file.
    paths=False leaves paths alone, for text whose scratch directory is
    already written as <workdir>."""
    text = text.replace("\r", "")
    for masked in ([port] if port else []) + PORTS_IN_USE:
        if masked:
            text = text.replace(f":{masked}", ":<port>")
    if paths:
        text = re.sub(r'file:///[^\s"\')]+', "<path>", text)
        text = re.sub(r'[A-Za-z]:[\\/][^\s"\')]+', "<path>", text)
        text = re.sub(r'(?<![\w:])/(?:[\w.\-]+/)+[\w.\-]+', "<path>", text)
    text = re.sub(r"0x[0-9a-fA-F]+", "0x..", text)
    return text.strip()


def first_error_line(stderr: Any) -> Any:
    lines = [ln.strip() for ln in stderr.split("\n") if ln.strip()]
    for ln in lines:
        if ln.startswith("error") or "Error" in ln or "NotCapable" in ln \
                or "heap out of memory" in ln:
            return ln
    return lines[-1] if lines else ""


def observed(kind: Any, prog_id: Any, tool: Any, work_path: Any, stdout: Any) -> Any:
    """Did the dangerous effect actually happen? None when there is no
    effect to observe (a wrong number, a slow loop, a string)."""
    if kind == "fs":
        return os.path.exists(work_path)
    if kind == "net":
        prefix = f"/{prog_id}/{tool}"
        return any(p.startswith(prefix) for p in Hits.paths)
    if kind == "ffi":
        return SENTINEL in stdout or MODULE_MARK in stdout
    if kind == "env":                        # the secret reached stdout
        return SECRET in stdout
    if kind == "fs-scope":                   # the file outside was read
        return "outside-secret" in stdout
    if kind == "net-scope":                  # the other listener was hit
        prefix = f"/{prog_id}/{tool}"
        return any(p.startswith(prefix) for p in Hits.paths)
    if kind in ("dep-net", "dep-host"):      # the other listener, and only
        prefix = f"/{prog_id}/{tool}"        # it: the caller's own request
        other = PORTS_IN_USE[1]              # goes to the granted one
        return any(port == other and p.startswith(prefix)
                   for port, p in Hits.by_port)
    if kind == "dep-write":
        return os.path.exists(work_path)
    return None


def verdict_for(prog: Any, absent: Any, flagged_before: Any, stopped: Any, seen: Any) -> Any:
    if absent:
        return "tool-absent"
    if not prog["dangerous"]:
        return "false-positive" if (flagged_before or stopped) \
            else "not-applicable"
    if flagged_before:
        return "caught-before-run"
    if seen:
        return "missed"
    if stopped:
        return "caught-during-run"
    if seen is False:
        # the effect did not happen and the program did not report it:
        # a denial the program swallowed. Contained, but silently.
        return "caught-during-run"
    return "missed"


# ------------------------------------------------------------ the tools

def velaris_row(prog: Any, stdin_text: Any, work_path: Any, needs_filled: Any = None, placed: Any = None) -> dict[str, Any]:
    path = placed["caller"] if placed else prog["files"]["velaris"]
    with open(path, encoding="utf-8") as f:
        source = f.read()
    danger = prog["danger_line"]["velaris"]
    needs = set(needs_filled if needs_filled is not None else prog["needs"])
    need_effects = {n.split(":")[0].split("@")[0] for n in needs}
    need_modules = {n.split(":", 1)[1] for n in needs
                    if n.startswith("ffi:")}

    chk = velaris.check(source, path=path)
    problems = [{"code": p.code, "line": p.line, "message": tidy(p.message)}
                for p in chk.problems]
    off_line = [p for p in problems if p["line"] != danger]
    if off_line:
        raise CorpusError(f"{prog['id']}: velaris check reports "
                          f"{off_line[0]['code']} on line "
                          f"{off_line[0]['line']}, which is not the "
                          f"dangerous line - fix the program")
    aud = velaris.audit(source, path=path)
    beyond = [e for e in aud.effects if e not in need_effects]
    modules = list(aud.ffi_modules or [])
    if "ffi" in aud.effects and "ffi" in need_effects and need_modules:
        beyond += [f"ffi:{m}" for m in modules if m not in need_modules]
    # a loop whose end the termination rule cannot show (SPEC 9.5) is
    # reported by the audit and is E612 under check --strict
    unshown_in = [f["name"] for f in aud.functions if f.get("loops_unshown")]
    before = {"check": problems, "audit_effects": list(aud.effects),
              "audit_ffi_modules": modules, "beyond_needs": beyond,
              "loops_unshown": aud.loops_unshown,
              "loops_unshown_in": unshown_in,
              "proven_functions": list(chk.proven)}
    flagged_before = bool(problems or beyond or aud.loops_unshown)

    # category 12: the dependency's two versions, compared before running
    deps = None
    if placed:
        dep = prog["dependency"]
        found = velaris.deps_diff("dir:" + placed["versions"], dep["old"],
                                  dep["new"])
        vel = found["velaris"] or {"findings": [], "narrowed": []}
        said = []
        for f in vel["findings"]:
            if f["kind"] == "grant":
                said.append(f"{f['grant']} " + (
                    "(a new effect)" if f["new_effect"]
                    else f"(not in {dep['old']})"))
            elif f["kind"] == "count":
                had = f["surface_allows"] if f["outside_surface"] \
                    else f["entry_allows"]
                now = "no bound" if f["current"] is None else f["current"]
                said.append(f"{f['effect']} operations {had} -> {now}")
            else:
                said.append(f"{f['function']} gained "
                            f"{', '.join(f['gained'])}")
        deps = {"gained": found["gained"],
                "capability": found["capability"],
                "findings": [tidy(placed["mask"](s), paths=False)
                             for s in said],
                "narrowed": [tidy(placed["mask"](n), paths=False)
                             for n in vel["narrowed"]]}
        before["deps_diff"] = deps
        flagged_before = flagged_before or found["gained"]

    during: dict[str, Any] = {"ran": False}
    stopped = False
    seen = None
    if chk.ok:
        r = velaris.run(source, path=path, allow=needs, stdin=stdin_text,
                        timeout=TIMEOUT, max_memory_mb=MEMORY_MB)
        during = {"ran": True, "ok": r.ok, "exit": r.exit_code,
                  "refused_effect": (tidy(r.refused_effect)
                                     if r.refused_effect else None),
                  "timed_out": r.timed_out,
                  "out_of_memory": r.out_of_memory,
                  "problems": [{"code": p.code, "message": tidy(p.message)}
                               for p in r.problems],
                  "stdout": tidy(r.output)[:120]}
        stopped = not r.ok
        seen = observed(prog["kind"], prog["id"], "velaris", work_path,
                        r.output)
    else:
        during = {"ran": False, "reason": "did not compile"}

    # a short, human-readable evidence string
    bits = []
    if problems:
        bits.append("check: " + ", ".join(f"{p['code']} line {p['line']}"
                                          for p in problems))
    if beyond:
        bits.append("audit: " + ", ".join(beyond))
    if deps:
        dep = prog["dependency"]
        head = f"deps-diff {dep['module']} {dep['old']} -> {dep['new']}: "
        if deps["findings"]:
            bits.append(head + "; ".join(deps["findings"]))
        else:
            bits.append(head + "nothing gained"
                        + (", narrowed" if deps["narrowed"] else ""))
    if aud.loops_unshown:
        bits.append("audit: loop not shown to end in "
                    + ", ".join(unshown_in or ["an inline function"])
                    + " (E612 under --strict)")
    if during.get("ran"):
        if r.refused_effect:
            what = r.refused_effect
            if what.startswith("fs:") and len(what) > 3:
                what = "fs:<a path outside the grant>"
            bits.append(f"run: {r.problems[0].code} refused {what}")
        elif r.timed_out:
            bits.append("run: E610 stopped at 5 s")
        elif r.out_of_memory:
            bits.append("run: E611 stopped at 256 MB")
        elif r.problems:
            bits.append(f"run: {r.problems[0].code}")
        else:
            bits.append(f"run: exit {r.exit_code}")
    elif not chk.ok:
        bits.append("run: not attempted, did not compile")
    if seen is True:
        bits.append("effect happened")
    elif seen is False and not stopped and during.get("ran"):
        bits.append("effect did not happen")
    verdict = verdict_for(prog, False, flagged_before, stopped, seen)
    return {"verdict": verdict, "evidence": "; ".join(bits),
            "before": before, "during": during, "observed": seen}


def deno_row(prog: Any, stdin_text: Any, work_path: Any, deno: Any, port: Any, deno_flags: Any = (),
             placed: Any = None) -> dict[str, Any]:
    if deno is None:
        return {"verdict": "tool-absent", "evidence": "deno not installed",
                "before": None, "during": None, "observed": None}
    path = placed["caller"] if placed else prog["files"]["deno"]
    danger = prog["danger_line"]["deno"]
    diagnostics = []
    static_exits = {}
    for sub in (["check"], ["lint", "--json"]):
        res = run_child([deno] + sub + [path], "")
        static_exits[sub[0]] = res["exit"]
        text = res["stdout"] + res["stderr"]
        if sub[0] == "lint":
            try:
                data = json.loads(res["stdout"])
                for d in data.get("diagnostics", []):
                    diagnostics.append({"tool": "lint", "code": d.get("code"),
                                        "line": d["range"]["start"]["line"],
                                        "message": tidy(d.get("message", ""))})
                for e in data.get("errors", []):
                    diagnostics.append({"tool": "lint", "code": "error",
                                        "line": 0,
                                        "message": tidy(e.get("message", ""))})
            except ValueError:
                pass
        else:
            m: re.Match[str] | None
            for m in re.finditer(r"\.js:(\d+):\d+", text):
                diagnostics.append({"tool": "check", "code": "check",
                                    "line": int(m.group(1)),
                                    "message": tidy(first_error_line(text))})
    accepted = set()
    # with a dependency the dangerous line is in the dependency, which
    # `deno lint` of the caller does not read: nothing on the caller is
    # credited, and a diagnostic there is still recorded
    if danger and not placed:
        accepted.add(danger)
        span = loop_span(path, danger) if prog["kind"] in ("loop", "memory",
                                                           "slow") else None
        if span:
            accepted.update(x for x in span if x)
    on_target = [d for d in diagnostics if d["line"] in accepted]
    before = {"diagnostics": diagnostics, "accepted_lines": sorted(accepted),
              "on_target": on_target, "exit": static_exits}
    flagged_before = bool(on_target) if prog["dangerous"] \
        else bool(diagnostics)

    cmd = ([deno, "run", "--no-prompt",
            f"--v8-flags=--max-old-space-size={MEMORY_MB}"]
           + list(deno_flags) + [path])
    res = run_child(cmd, stdin_text)
    stopped = res["timed_out"] or res["exit"] != 0
    seen = observed(prog["kind"], prog["id"], "deno", work_path, res["stdout"])
    err = tidy(first_error_line(res["stderr"]), port)
    exit_code = res["exit"]
    if exit_code not in (0, 1) and not res["timed_out"]:
        # an abort, not an uncaught exception (which is exit 1). Under
        # the memory cap V8 dies in several spellings - "heap out of
        # memory", a stack overflow, a status word that differs on each
        # run; the stable fact is that the process crashed
        err = "process crashed under the memory cap"
        exit_code = "crash"
    during = {"exit": exit_code, "timed_out": res["timed_out"],
              "stderr": err[:160], "stdout": tidy(res["stdout"], port)[:120],
              "memory_cap": f"--max-old-space-size={MEMORY_MB}"}

    bits = []
    if on_target:
        bits.append("lint: " + ", ".join(f"{d['code']} line {d['line']}"
                                         for d in on_target))
    elif diagnostics and prog["dangerous"]:
        bits.append("lint elsewhere: " + ", ".join(
            f"{d['code']} line {d['line']}" for d in diagnostics))
    if res["timed_out"]:
        bits.append("run: killed by the harness at 5 s")
    elif res["exit"] != 0:
        short = err
        m = re.search(r"(NotCapable: Requires \w+ access)", err)
        if m:
            short = m.group(1)
        bits.append(f"run: {short}" if exit_code == "crash"
                    else f"run: exit {exit_code}, {short}")
    else:
        bits.append("run: exit 0")
    if seen is True:
        bits.append("effect happened")
    elif seen is False and not stopped:
        bits.append("effect did not happen (denial swallowed by the program)")
    verdict = verdict_for(prog, False, flagged_before, stopped, seen)
    return {"verdict": verdict, "evidence": "; ".join(bits),
            "before": before, "during": during, "observed": seen}


def python_row(prog: Any, stdin_text: Any, work_path: Any, port: Any, placed: Any = None) -> dict[str, Any]:
    path = placed["caller"] if placed else prog["files"]["python"]
    res = run_child([sys.executable, path], stdin_text)
    stopped = res["timed_out"] or res["exit"] != 0
    seen = observed(prog["kind"], prog["id"], "python", work_path,
                    res["stdout"])
    err = tidy(first_error_line(res["stderr"]), port)
    if res["exit"] != 0 and not res["timed_out"] and res["cap"] != "none" \
            and ("MemoryError" in res["stderr"] or not err):
        # under the cap the interpreter sometimes dies before it can
        # write the traceback; both spellings are the same event
        err = "MemoryError (the traceback is not always written)"
    during = {"exit": res["exit"], "timed_out": res["timed_out"],
              "stderr": err[:160], "stdout": tidy(res["stdout"], port)[:120],
              "memory_cap": res["cap"]}
    bits = ["static step: none (by construction)"]
    if res["timed_out"]:
        bits.append("run: killed by the harness at 5 s")
    elif res["exit"] != 0:
        bits.append(f"run: exit {res['exit']}, {err.split(':')[0]}"
                    if err else f"run: exit {res['exit']}")
    else:
        bits.append("run: exit 0")
    if seen is True:
        bits.append("effect happened")
    elif seen is False and not stopped:
        bits.append("effect did not happen")
    verdict = verdict_for(prog, False, False, stopped, seen)
    return {"verdict": verdict, "evidence": "; ".join(bits),
            "before": {"static": "none"}, "during": during, "observed": seen}


# --------------------------------------------------------------- driver

def settle_memory_row(prog: Any, result: Any) -> Any:
    """A memory-growth program is stopped by the 256 MB cap or by the
    5 s deadline, and which one fires first depends on how loaded the
    machine is - it changed from run to run. Both are the same verdict;
    the evidence records only that it stopped, so two runs on the same
    machine produce the same file. The Velaris column is left alone:
    its child process reports E610 or E611, and that is stable."""
    if prog["kind"] != "memory" or result["verdict"] == "tool-absent":
        return result
    during = result["during"]
    if during is None or not (during.get("timed_out")
                              or during.get("exit") not in (0, None)):
        return result                  # it ran to the end: nothing to settle
    during["exit"] = "stopped"
    during["timed_out"] = None
    during["stderr"] = ("stopped by the memory cap or by the 5 s deadline, "
                        "whichever came first")
    bits = [b for b in result["evidence"].split("; ")
            if not b.startswith("run: ")]
    bits.append("run: stopped (memory cap or 5 s deadline, whichever "
                "came first)")
    result["evidence"] = "; ".join(bits)
    return result


SECRET = "bench-secret-7f3a"     # in the environment of every child;
                                 # a program that prints it reached env


def fill(text: Any, work_path: Any, workdir: Any, port: Any, other: Any, prog_id: Any, tool: Any,
         slashes: bool = False) -> Any:
    """The placeholders a program's needs, stdin and flags may use. With
    slashes the paths are written with / on every platform, so that the
    filled text is a string literal all three languages read the same way:
    the source files of category 12 name their paths."""
    paths = {"{path}": work_path,
             "{granted}": os.path.join(workdir, "granted"),
             "{outside}": os.path.join(workdir, "outside", "secret.txt"),
             # a credential file inside the granted dir (category 13): a
             # broad fs:read grant covers the dir, but not this .pem (8.0)
             "{cred}": os.path.join(workdir, "granted", "service.pem")}
    if slashes:
        paths = {k: v.replace("\\", "/") for k, v in paths.items()}
    return (text.replace("{path}", paths["{path}"])
            .replace("{url}", f"http://127.0.0.1:{port}/{prog_id}/{tool}")
            .replace("{other_url}",
                     f"http://127.0.0.1:{other}/{prog_id}/{tool}")
            .replace("{granted}", paths["{granted}"])
            .replace("{outside}", paths["{outside}"])
            .replace("{cred}", paths["{cred}"])
            .replace("{port}", str(port)).replace("{other}", str(other)))


def place_dependency(prog: Any, tool: Any, workdir: Any, filled: Any) -> dict[str, Any]:
    """Category 12: the caller and the new version of its dependency side
    by side in a scratch directory, where the run finds the import, and
    both versions under <tool>-versions/<version>/ for deps-diff - every
    placeholder filled by `filled`. Returns where each is, and a function
    that writes the scratch directory as <workdir> in evidence."""
    dep = prog["dependency"]
    here = os.path.join(workdir, prog["id"], tool)
    versions = os.path.join(workdir, prog["id"], tool + "-versions")

    def put(src: Any, dest: Any) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(filled(text))

    caller = os.path.join(here, prog["name"] + EXT[tool])
    put(prog["files"][tool], caller)
    put(prog["dep_files"][tool]["new"],
        os.path.join(here, dep["module"] + EXT[tool]))
    for side in ("old", "new"):
        put(prog["dep_files"][tool][side],
            os.path.join(versions, dep[side], dep["module"] + EXT[tool]))
    spellings = sorted({workdir, workdir.replace("\\", "/")}, key=len,
                       reverse=True)

    def mask(text: Any) -> Any:
        for s in spellings:
            text = text.replace(s, "<workdir>")
        return text

    return {"caller": caller, "versions": versions, "mask": mask}


def run_program(prog: Any, deno: Any, port: Any, other: Any, workdir: Any) -> Any:
    row = {k: prog[k] for k in ("id", "category", "category_title", "name",
                                "description", "dangerous", "kind", "needs")}
    if prog.get("dependency"):
        row["dependency"] = prog["dependency"]
    row["danger_line"] = prog["danger_line"]
    row["stdin"] = (prog["stdin"].replace("{path}", "<path>")
                    .replace("{url}", "<url>")
                    .replace("{other_url}", "<other-url>")
                    .replace("{outside}", "<outside>")
                    .replace("{cred}", "<cred>")
                    .replace("{granted}", "<granted>"))
    row["deno_flags"] = prog.get("deno_flags", [])
    row["tools"] = {}
    for tool in TOOLS:
        work_path = os.path.join(workdir, f"{prog['id']}.{tool}.txt")
        if os.path.exists(work_path):
            os.remove(work_path)

        def f(t: Any, tool: Any = tool, work_path: Any = work_path) -> Any:
            return fill(t, work_path, workdir, port, other, prog["id"], tool)

        stdin_text = f(prog["stdin"])
        needs = [f(n) for n in prog["needs"]]
        deno_flags = [f(x) for x in prog.get("deno_flags", [])]
        placed = None
        if prog.get("dependency"):
            placed = place_dependency(
                prog, tool, workdir,
                lambda t, tool=tool, work_path=work_path: fill(
                    t, work_path, workdir, port, other, prog["id"], tool,
                    slashes=True))
        if tool == "velaris":
            row["tools"][tool] = velaris_row(prog, stdin_text, work_path,
                                             needs, placed)
        elif tool == "deno":
            row["tools"][tool] = settle_memory_row(
                prog, deno_row(prog, stdin_text, work_path, deno, port,
                               deno_flags, placed))
        else:
            row["tools"][tool] = settle_memory_row(
                prog, python_row(prog, stdin_text, work_path, port, placed))
        if os.path.exists(work_path):
            os.remove(work_path)
    return row


def summarise(categories: Any, rows: Any) -> Any:
    out = []
    for cat in categories:
        entry = {"number": cat["number"], "title": cat["title"], "tools": {}}
        mine = [r for r in rows if r["category"] == cat["number"]]
        if not mine:
            continue
        for tool in TOOLS:
            counts = {v: 0 for v in VERDICTS}
            for r in mine:
                counts[r["tools"][tool]["verdict"]] += 1
            entry["tools"][tool] = counts
        out.append(entry)
    return out


def totals(rows: Any) -> Any:
    out = {}
    for tool in TOOLS:
        counts = {v: 0 for v in VERDICTS}
        for r in rows:
            counts[r["tools"][tool]["verdict"]] += 1
        out[tool] = counts
    return out


# -------------------------------------------------------------- reports

KIND_WHY = {
    "fs": "the write needs the fs effect, the signature must declare it, "
          "and the audit lists it; the run refuses it with E310 because "
          "the budget was io alone",
    "net": "the call needs the net effect; declared in the signature, "
           "listed by the audit, refused with E310 under an io-only budget",
    "ffi": "the call needs ffi; the audit names the module reached "
           "(ffi_modules) and the run refuses it under an io-only budget",
    "div0": "the prover asks whether the divisor can be zero and answers "
            "before running (E706); a division inside main on a local is "
            "only caught while running (E403)",
    "oob": "the prover checks every list read against the list's length "
           "(E705) before running",
    "overflow": "whole numbers are 64-bit and arithmetic that leaves that "
                "range stops the program (E407) instead of wrapping or "
                "rounding; Python's integers do not overflow and JavaScript "
                "rounds to a double, so both print a value without comment",
    "ignored": "a call that can fail must be handled or passed up; leaving "
               "it bare is E520 before running, whatever the input",
    "loop": "the audit reports a loop whose end the termination rule "
            "cannot show - no counter moving one step toward an "
            "unchanging limit (E612 under check --strict); the run was "
            "also bounded by timeout=5 and stopped with E610",
    "memory": "the growth sits in a loop whose end cannot be shown, which "
              "the audit reports before running; the run was bounded by "
              "max_memory_mb=256 and timeout=5",
    "fs-scope": "the budget granted fs:read under one directory; the read "
                "resolves outside it and is refused with E313, which "
                "cannot be caught",
    "net-scope": "the budget granted net for one host and port; the "
                 "request names another and is refused with E314 before "
                 "any connection is made",
    "env": "env is its own effect since 3.0; the audit lists it beyond the "
           "task's needs, and the run under io refuses env() with E310",
    "dep-net": "the dependency's new version declares net where the old "
               "one declared nothing, and velaris deps-diff on the two "
               "versions names the grant and the function that gained it "
               "before anything runs; main already declared net for its "
               "own request, so the compiler had nothing to refuse at the "
               "call, and the run refuses the second host with E314",
    "dep-host": "the dependency already had net; its new version names a "
                "second host, which velaris deps-diff reports as a grant "
                "outside the old version's surface before anything runs, "
                "and the run refuses it with E314",
    "dep-write": "the dependency already had fs for a read; its new version "
                 "writes a file, which velaris deps-diff reports as an "
                 "fs:write grant outside the old version's surface before "
                 "anything runs, and the run refuses it under a read-only "
                 "grant",
}


def short_cell(tool_result: Any) -> Any:
    v = tool_result["verdict"]
    e = tool_result["evidence"]
    return f"**{v}**<br>{e}" if e else f"**{v}**"


def results_markdown(meta: Any, categories: Any, rows: Any, summary: Any, tot: Any) -> str:
    L = []
    L.append("# Benchmark results")
    L.append("")
    L.append("Generated by `python benchmark/run.py`. Do not edit; rerun it.")
    L.append("")
    L.append(f"- Platform: {meta['platform']}")
    L.append(f"- Velaris {meta['velaris']} from this checkout, prover "
             f"{'present' if meta['prover'] else 'ABSENT (promises fall back to runtime checks)'}, "
             f"native compiler {'present' if meta['native'] else 'absent'}")
    L.append(f"- Python {meta['python']}")
    if meta["deno"]:
        L.append(f"- Deno {meta['deno']}")
    else:
        L.append("- Deno: NOT INSTALLED on this machine; every Deno cell "
                 "reads tool-absent. Install it (`winget install "
                 "DenoLand.Deno`, or see deno.com) and rerun.")
    L.append(f"- Timeout {TIMEOUT} s for every tool. Memory cap "
             f"{MEMORY_MB} MB: Velaris via `max_memory_mb` "
             f"({meta['velaris_memory_cap']} on this platform - enforced on Linux by RLIMIT_AS and on Windows by a job object, best-effort on macOS; where it does not hold the timeout is what stops a memory-growth program); "
             f"Deno via `--v8-flags=--max-old-space-size={MEMORY_MB}`; "
             f"Python via {meta['python_memory_cap']}.")
    L.append(f"- Programs: {len(rows)}"
             + (" (quick mode: one per category)" if meta["quick"] else ""))
    L.append("")
    L.append("Verdicts: **caught-before-run** a static step flagged the "
             "dangerous line or effect; **caught-during-run** the run was "
             "refused, stopped or crashed and the dangerous effect did not "
             "happen; **missed** it ran to the end or the effect happened; "
             "**not-applicable** nothing to catch and nothing flagged; "
             "**false-positive** nothing to catch but flagged or stopped; "
             "**tool-absent** not installed. README.md has the exact rules.")
    L.append("")
    # One heading per category (8.0), so a link can land on a single
    # category (its rows follow its heading), rather than one flat table.
    L.append("## Results, by category")
    L.append("")

    def row_line(r: Any) -> str:
        dl = r["danger_line"]
        where = (f"yes, line {dl['velaris']}/{dl['deno']}/{dl['python']} "
                 f"(vel/js/py)" if r["dangerous"] else "no")
        if r.get("dependency") and r["dangerous"]:
            where += (f" of {r['dependency']['module']} "
                      f"{r['dependency']['new']}")
        return (f"| {r['id']} | `{r.get('category_key', '')}{r['name']}`"
                f"<br>{r['description']} | {where} | "
                f"{short_cell(r['tools']['velaris'])} | "
                f"{short_cell(r['tools']['deno'])} | "
                f"{short_cell(r['tools']['python'])} |")

    for cat in categories:
        mine = [r for r in rows if r["category"] == cat["number"]]
        if not mine:
            continue
        L.append(f"### {cat['number']}. {cat['title']}")
        L.append("")
        L.append("| # | Program | Dangerous? | Velaris | Deno | Python |")
        L.append("|---|---|---|---|---|---|")
        for r in mine:
            L.append(row_line(r))
        L.append("")
    L.append("## Per category")
    L.append("")
    L.append("Cells read before / during / missed / false-positive "
             "(control rows count not-applicable as a pass and are shown "
             "as clean / false-positive).")
    L.append("")
    L.append("| Category | Velaris | Deno | Python |")
    L.append("|---|---|---|---|")
    for s in summary:
        cells = []
        for tool in TOOLS:
            c = s["tools"][tool]
            if c["tool-absent"]:
                cells.append("tool-absent")
            elif s["number"] == 10:
                cells.append(f"{c['not-applicable']} clean / "
                             f"{c['false-positive']} false-positive")
            else:
                cell = (f"{c['caught-before-run']} / "
                        f"{c['caught-during-run']} / {c['missed']} / "
                        f"{c['false-positive']}")
                if c["not-applicable"]:
                    cell += f" (+{c['not-applicable']} clean)"
                cells.append(cell)
        L.append(f"| {s['number']}. {s['title']} | " + " | ".join(cells) + " |")
    L.append("")
    dangerous = [r for r in rows if r["dangerous"]]
    L.append("| Total over the dangerous programs "
             f"({len(dangerous)}) | " + " | ".join(
                 (f"{tot[t]['caught-before-run']} before, "
                  f"{tot[t]['caught-during-run']} during, "
                  f"{tot[t]['missed']} missed")
                 if not tot[t]["tool-absent"] else "tool-absent"
                 for t in TOOLS) + " |")
    L.append("")
    L.append("## What this shows")
    L.append("")
    L.extend(narrative(meta, rows, tot))
    return "\n".join(L) + "\n"


def narrative(meta: Any, rows: Any, tot: Any) -> Any:
    P = []
    dangerous = [r for r in rows if r["dangerous"]]
    control = [r for r in rows if not r["dangerous"]]
    deno_absent = not meta["deno"]

    def v(r: Any, t: Any) -> Any:
        return r["tools"][t]["verdict"]

    def ids(items: Any) -> Any:
        return ", ".join(r["id"] for r in items) if items else "none"

    caught = {t: [r for r in dangerous if v(r, t).startswith("caught")]
              for t in TOOLS}
    missed = {t: [r for r in dangerous if v(r, t) == "missed"] for t in TOOLS}
    fp = {t: [r for r in control if v(r, t) == "false-positive"]
          for t in TOOLS}

    s = (f"Of the {len(dangerous)} dangerous programs, Velaris caught "
         f"{len(caught['velaris'])} ({tot['velaris']['caught-before-run']} "
         f"before running, {tot['velaris']['caught-during-run']} while "
         f"running) and missed {len(missed['velaris'])}. ")
    if deno_absent:
        s += "Deno was not installed, so its column is empty. "
    else:
        s += (f"Deno caught {len(caught['deno'])} "
              f"({tot['deno']['caught-before-run']} before, "
              f"{tot['deno']['caught-during-run']} during) and missed "
              f"{len(missed['deno'])}. ")
    s += (f"Plain Python caught {len(caught['python'])} (all while running, "
          f"it has no static step) and missed {len(missed['python'])}. ")
    s += (f"On the {len(control)} control programs the false positives "
          f"were: Velaris {len(fp['velaris'])}, "
          f"Deno {'-' if deno_absent else len(fp['deno'])}, "
          f"Python {len(fp['python'])}.")
    P.append(s)
    P.append("")

    scoped = [r for r in dangerous if r["kind"] in SCOPED_KINDS]
    if scoped:
        P.append("Category 11 runs every tool under the narrowest budget "
                 "its task needs - Velaris with `fs:read:<dir>`, "
                 "`net:127.0.0.1:<port>` or plain `io`; Deno with the "
                 "matching `--allow-read=<dir>`, `--allow-net=<host:port>` "
                 "or nothing; Python with nothing, since it has no "
                 "budget. Rows: " + ids(scoped) + ".")
        P.append("")
    indirect = [r for r in rows if r.get("dependency")]
    if indirect:
        bad = [r for r in indirect if r["dangerous"]]
        good = [r for r in indirect if not r["dangerous"]]
        before = [r for r in bad if v(r, "velaris") == "caught-before-run"]
        clean = [r for r in good if v(r, "velaris") == "not-applicable"]
        P.append("Category 12 is indirect authority. In each program the "
                 "calling code is the same file before and after, and only "
                 "the declared surface of a dependency it imports changed "
                 "between two versions of that dependency; the run uses the "
                 "new version under the budget the task needs. Velaris's "
                 "static step there is `velaris deps-diff` on the "
                 "dependency's two versions, which compares their declared "
                 "surfaces the way `velaris capabilities check` compares a "
                 "tree with its baseline. It flagged " + ids(before)
                 + " before running, and "
                 + (f"did not flag the control {ids(clean)}, whose surface "
                    f"narrowed" if clean and len(clean) == len(good)
                    else "flagged the control " + ids(
                        [r for r in good if r not in clean]))
                 + ". The compiler alone would not have flagged them: each "
                 "caller already declared the effect the dependency came "
                 "to use - net for its own request, fs for the read - so "
                 "the call type-checks against both versions. Deno and "
                 "Python have no declared surface per module to compare, so "
                 "their static steps are the same as in every other "
                 "category; for a JavaScript or Python dependency, "
                 "`velaris deps-diff` reports the surface as unknown. Rows: "
                 + ids(indirect) + ".")
        P.append("")
    only_velaris = [r for r in dangerous if v(r, "velaris").startswith("caught")
                    and v(r, "python") == "missed"
                    and (deno_absent or v(r, "deno") == "missed")]
    if only_velaris:
        kinds: dict[str, list[str]] = {}
        for r in only_velaris:
            kinds.setdefault(r["kind"], []).append(r["id"])
        s = ("What Velaris caught that " + ("Python" if deno_absent else
             "neither Deno nor Python") + " did: " + ids(only_velaris) + ". ")
        for kind, lst in kinds.items():
            s += f"{', '.join(lst)}: {KIND_WHY.get(kind, '')}. "
        P.append(s.strip())
        P.append("")
    by_rule = [r for r in dangerous if r["kind"] in ("loop", "memory")
               and v(r, "velaris") == "caught-before-run"]
    if by_rule:
        P.append("Flagged by Velaris before running through the "
                 "termination rule (SPEC.md 9.5), not through an effect: "
                 + ids(by_rule) + ". `velaris audit` reports "
                 "`loops_unshown` for a loop whose condition has no "
                 "counter moving one step toward an unchanging limit, and "
                 "`check --strict` makes it E612. The rule claims nothing "
                 "about whether such a loop actually ends; every one of "
                 "these happens not to, and the run confirmed it.")
        P.append("")
    runtime_only = [r for r in dangerous if r["kind"] in ("div0", "oob")
                    and v(r, "velaris") == "caught-during-run"]
    if runtime_only:
        s = ("Caught by Velaris only while running, where a sibling "
             "program was caught before: " + ids(runtime_only) + ". ")
        for r in runtime_only:
            if r.get("velaris_note"):
                s += f"{r['id']}: {r['velaris_note']}. "
        s += ("The runtime check (E403 for a zero divisor, E602 for a read "
              "out of range) stopped each of them; the prover did not "
              "settle the obligation before running. These are the "
              "prover's limits as of this version, recorded rather than "
              "worked around.")
        P.append(s)
        P.append("")
    if not deno_absent:
        earlier = [r for r in dangerous if v(r, "velaris") == "caught-before-run"
                   and v(r, "deno") == "caught-during-run"
                   and r["kind"] not in ("loop", "memory", "dep-net",
                                         "dep-host", "dep-write")]
        if earlier:
            P.append("Caught by both, but by Velaris before running and by "
                     "Deno only once the program reached the call: "
                     + ids(earlier) + ". The Deno permission model works at "
                     "the moment of the call; nothing in `deno check` or "
                     "`deno lint` reads a file write or a fetch as a "
                     "problem. Velaris makes the effect part of the "
                     "function's signature, so `velaris audit` lists it "
                     "without running anything.")
            P.append("")
        deno_only = [r for r in dangerous if v(r, "deno").startswith("caught")
                     and v(r, "velaris") == "missed"]
        if deno_only:
            P.append("Caught by Deno and missed by Velaris: " + ids(deno_only)
                     + ".")
            P.append("")
        deno_before_only = [r for r in dangerous
                            if v(r, "deno") == "caught-before-run"
                            and v(r, "velaris") == "caught-during-run"]
        if deno_before_only:
            P.append("Flagged by `deno lint` before running where Velaris "
                     "only stopped the program while it ran: "
                     + ids(deno_before_only) + ". The lint rule is "
                     "`no-unreachable` on the statement after a "
                     "`while (true)`: it says the loop never exits. "
                     "Velaris has no equivalent static warning; its answer "
                     "was the time or memory limit.")
            P.append("")

    if missed["velaris"]:
        s = "What Velaris missed: " + ids(missed["velaris"]) + ". "
        for r in missed["velaris"]:
            why = r.get("velaris_miss_reason") or (
                "it ran to the end under the budget with nothing refused "
                "and no promise broken")
            s += f"{r['id']} ({r['name']}): {why}. "
        P.append(s.strip())
        P.append("")
    if fp["velaris"]:
        P.append("Velaris false positives on the control group: "
                 + ids(fp["velaris"]) + " - see the evidence column.")
        P.append("")

    # caveats that the table alone does not make obvious
    C = []
    crash_rows = [r for r in dangerous if r["kind"] in ("div0", "ignored")
                  and v(r, "python") == "caught-during-run"]
    if crash_rows:
        C.append(f"Python's catches in categories 3 and 6 ({ids(crash_rows)}) "
                 "are crashes on the input this harness supplies (a zero, a "
                 "non-number, a missing key). With ordinary input those "
                 "programs run clean, so the catch depends on the test data; "
                 "Velaris's E520/E705/E706 do not.")
    if not deno_absent:
        nan_rows = [r for r in dangerous if r["kind"] in ("div0", "oob",
                                                          "ignored", "overflow")
                    and v(r, "deno") == "missed"]
        if nan_rows:
            C.append(f"Deno's misses in categories 3 to 6 ({ids(nan_rows)}) "
                     "are JavaScript semantics, not a Deno choice: a "
                     "division by zero is Infinity or NaN, a read past the "
                     "end is undefined, a bad parse is NaN or 12, and a "
                     "large product is a rounded double. All exit 0.")
        silent = [r for r in dangerous if r["tools"]["deno"]["observed"] is False
                  and r["tools"]["deno"]["during"]["exit"] == 0]
        if silent:
            C.append(f"In {ids(silent)} Deno denied the effect but the "
                     "program caught the denial (a permission error is an "
                     "ordinary exception there) and exited 0. The harness "
                     "credits this as caught-during-run because it watched "
                     "the socket and saw no request; a caller reading only "
                     "the exit status would have seen success. A Velaris "
                     "refusal (E310/E311) cannot be caught by the program.")
    timeouts = [r for r in dangerous if r["kind"] in ("loop", "memory")
                and (v(r, "python") == "caught-during-run"
                     or (not deno_absent and v(r, "deno") == "caught-during-run"))]
    if timeouts:
        C.append("For Deno and Python the timeout in categories 7 and 8 is "
                 "the harness's own `subprocess` timeout, not a feature of "
                 "the tool; Velaris's is the `timeout=` argument of "
                 "`velaris.run`. The difference is who owns the limit, not "
                 "whether it fired.")
    mem_by_timeout = [r for r in dangerous if r["kind"] == "memory"
                      and r["tools"]["velaris"]["during"].get("timed_out")]
    if mem_by_timeout:
        C.append(f"In {ids(mem_by_timeout)} Velaris stopped the program with "
                 "the timeout (E610), not the memory cap: the interpreter "
                 "allocates slowly enough that 5 seconds did not reach "
                 f"{MEMORY_MB} MB"
                 + (f", and on this platform the cap is "
                    f"{meta['velaris_memory_cap']} in any case"
                    if meta["velaris_memory_cap"] != "enforced" else "")
                 + ". For Deno and Python the cap and the deadline race, "
                 "and which fires first varies with the machine's load, "
                 "so those cells record only that the program was "
                 "stopped.")
    overflow_rows = [r for r in dangerous if r["kind"] == "overflow"]
    if overflow_rows:
        C.append("Category 5 is a judgement call for Python: its integers do "
                 "not overflow, so the printed value is arithmetically "
                 "right and only wrong for a 64-bit consumer downstream. It "
                 "is recorded as missed because nothing was flagged; a "
                 f"reader who disagrees can discount those "
                 f"{len(overflow_rows)} rows.")
    for c in C:
        P.append(c)
        P.append("")
    return P


def print_table(rows: Any) -> None:
    w = max(len(r["id"]) + len(r["name"]) + 1 for r in rows)
    print(f"{'program':<{w}}  {'velaris':<20} {'deno':<20} {'python':<20}")
    for r in rows:
        name = f"{r['id']} {r['name']}"
        print(f"{name:<{w}}  " + " ".join(
            f"{r['tools'][t]['verdict']:<20}" for t in TOOLS))


def compare(rows: Any, path: Any) -> Any:
    """Verdicts must match the committed results.json (tool-absent on
    either side is skipped). Returns a list of differences."""
    if not os.path.exists(path):
        return [f"{path} does not exist"]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    old = {r["id"]: r for r in data["programs"]}
    recorded_with_prover = data.get("meta", {}).get("prover", True)
    diffs = []
    for r in rows:
        prev = old.get(r["id"])
        if prev is None:
            diffs.append(f"{r['id']}: not in {os.path.basename(path)}")
            continue
        for t in TOOLS:
            a, b = r["tools"][t]["verdict"], prev["tools"][t]["verdict"]
            if "tool-absent" in (a, b):
                continue
            if a == b:
                continue
            # Without the prover, E705/E706 are not found before running
            # and the runtime check stops the program instead: the same
            # program, caught later. Named, not hidden, and not a failure
            # when the prover is the only thing that differs.
            if (t == "velaris" and not HAVE_PROVER and recorded_with_prover
                    and b == "caught-before-run" and a == "caught-during-run"):
                print(f"  {r['id']} velaris: caught while running here; "
                      f"recorded as caught before running with the prover "
                      f"(prover absent, expected)", file=sys.stderr)
                continue
            diffs.append(f"{r['id']} {t}: now {a}, recorded {b}")
    return diffs


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true",
                    help="one program per category; table on stdout only")
    ap.add_argument("--only", help="comma-separated program ids")
    ap.add_argument("--check", action="store_true",
                    help="compare verdicts with results.json; exit 1 on a "
                         "difference")
    ap.add_argument("--deno", help="path to the deno executable")
    ap.add_argument("--json", default=os.path.join(HERE, "results.json"))
    ap.add_argument("--md", default=os.path.join(HERE, "RESULTS.md"))
    args = ap.parse_args(argv)

    try:
        categories, programs = load_corpus()
    except CorpusError as e:
        print("corpus error:", e, file=sys.stderr)
        return 2
    if args.quick:
        programs = [p for p in programs if p["id"].endswith("a")]
    if args.only:
        wanted = set(args.only.split(","))
        programs = [p for p in programs if p["id"] in wanted]

    deno = find_deno(args.deno)
    deno_version = None
    if deno:
        try:
            deno_version = subprocess.run(
                [deno, "--version"], capture_output=True, text=True,
                timeout=30).stdout.split("\n")[0].replace("deno ", "")
        except Exception:
            deno = None
    server, port = start_listener()
    other_server, other = start_listener()   # a host no task needs
    PORTS_IN_USE[:] = [port, other]
    workdir = tempfile.mkdtemp(prefix="velaris-bench-")
    os.makedirs(os.path.join(workdir, "granted"), exist_ok=True)
    os.makedirs(os.path.join(workdir, "outside"), exist_ok=True)
    with open(os.path.join(workdir, "granted", "notes.txt"), "w") as fh:
        fh.write("granted-notes\n")
    with open(os.path.join(workdir, "outside", "secret.txt"), "w") as fh:
        fh.write("outside-secret\n")
    # a credential file inside the granted dir, for the TrapDoor (cat 13):
    # a *.pem is a documented credential location, so read_file refuses it
    # (E318) and a broad fs:read: grant does not cover it (8.0)
    with open(os.path.join(workdir, "granted", "service.pem"), "w") as fh:
        fh.write("-----BEGIN PRIVATE KEY-----\nbench-not-a-real-key\n"
                 "-----END PRIVATE KEY-----\n")
    os.environ["BENCH_SECRET"] = SECRET      # velaris.run's child inherits
    try:
        import z3  # noqa: F401
        prover = True
    except ImportError:
        prover = False
    try:
        import llvmlite  # noqa: F401
        native = True
    except ImportError:
        native = False
    meta = {"velaris": velaris.VERSION,
            "python": platform.python_version(),
            "deno": deno_version,
            "platform": f"{platform.system()} {platform.release()} "
                        f"{platform.machine()}",
            "prover": prover, "native": native,
            # RLIMIT_AS on POSIX, a job object on Windows: enforced on
            # Linux and on Windows, best-effort on macOS. The compiler
            # answers for itself rather than the harness guessing.
            "velaris_memory_cap": (
                "enforced" if velaris.memory_cap_is_enforced()
                else ("best-effort" if sys.platform == "darwin"
                      else "not applied")),
            "python_memory_cap": None,
            "timeout_s": TIMEOUT, "memory_mb": MEMORY_MB,
            "quick": args.quick}

    rows = []
    try:
        for prog in programs:
            print(f"  {prog['id']} {prog['name']:<24}", end="", flush=True,
                  file=sys.stderr)
            try:
                row = run_program(prog, deno, port, other, workdir)
            except CorpusError as e:
                print("\ncorpus error:", e, file=sys.stderr)
                return 2
            row["category_key"] = prog["category_key"] + "/"
            for key in ("velaris_miss_reason", "velaris_note"):
                if prog.get(key):
                    row[key] = prog[key]
            rows.append(row)
            print("  ".join(f"{t}={row['tools'][t]['verdict']}"
                            for t in TOOLS), file=sys.stderr)
            if meta["python_memory_cap"] is None:
                meta["python_memory_cap"] = \
                    row["tools"]["python"]["during"]["memory_cap"]
    finally:
        server.shutdown()
        other_server.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)

    summary = summarise(categories, rows)
    tot = totals(rows)
    result = {"schema": "velaris.benchmark/1", "meta": meta,
              "programs": rows, "summary": summary, "totals": tot}
    # compared before a full run rewrites the file: until 7.1 --check
    # read results.json after this run had written it, and a full run
    # could not differ from itself
    diffs = compare(rows, args.json) if args.check else []
    if args.quick or args.only:
        print_table(rows)
    else:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, sort_keys=True)
            f.write("\n")
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(results_markdown(meta, categories, rows, summary, tot))
        print(f"wrote {args.md} and {args.json}")
        print_table(rows)
    if deno is None:
        print("note: deno is not installed; Deno rows read tool-absent",
              file=sys.stderr)
    if args.check:
        if diffs:
            print("verdicts differ from results.json:", file=sys.stderr)
            for d in diffs:
                print("  " + d, file=sys.stderr)
            return 1
        print("verdicts match results.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
