"""Velaris from inside another program: check, audit, run, card.
"""
import os
import re
import sys
from typing import TYPE_CHECKING, Any

from . import state as _state
from .version import VERSION, _INSTALL_DIR
from .errors import VelarisError
from .nodes import Call, Str
from .tables import (
    ALLOW_ALL,
    ALL_EFFECTS,
    CHECK_MEMORY_MB_DEFAULT,
    CHECK_TIMEOUT_DEFAULT,
    DEFAULT_ALLOW,
    SECRET_SOURCES,
    builtin_reached,
)
from .recorder import (
    _RunRecorder,
    _entry_name,
    _note_error,
    _note_stop,
    _utc_now_ms,
)
from .loader import load_program
from .values import FailSignal
from .budget import (
    Budget,
    BudgetError,
    _pct_encode,
    expand_allow,
    set_run_params,
    warn_allow_all,
)
from .effects import check_effects
from .checker import check_main, check_types
from .prover import check_proofs
from .native import compile_native
from .runtime import _on_big_stack, interpret
from .editor import contract_coverage, inspect_source
from .results import (
    AUDIT_SCHEMA,
    AuditResult,
    CheckResult,
    Problem,
    RunResult,
    _as_problem,
)

if TYPE_CHECKING:
    from .pool import Pool
    from .ratchet import COUNTED_EFFECTS, _as_count, _operation_bounds
    from .receipts import _receipt_subjects, _run_parameters, receipt_statement

# Used inside functions only, from modules after this one: velaris/__init__.py
# binds each here once every module is loaded.
__forward__ = {
    "COUNTED_EFFECTS": "ratchet",
    "Pool": "pool",
    "_as_count": "ratchet",
    "_operation_bounds": "ratchet",
    "_receipt_subjects": "receipts",
    "_run_parameters": "receipts",
    "receipt_statement": "receipts",
}

# ---------------------------------------------------------------------------
# 14. THE LIBRARY — Velaris from inside another program
#
#     An agent framework, an MCP server or an internal tool should not
#     have to shell out to use this. Everything the command line does is
#     available here, with the same guarantees: effects are enforced
#     while the program runs, whatever its source claims.
#
#         import velaris
#         print(velaris.check(src).ok)
#         print(velaris.audit(src).effects)
#         print(velaris.run(src, allow={"io"}).output)
# ---------------------------------------------------------------------------


def _source_to_file(source: str, path: str | None) -> tuple[Any, ...]:
    """Velaris resolves imports against a file, so give the text one, in a
    directory of its own. Until 8.2 the file sat in the system temp
    directory itself, where imports then resolved first: a std.vel that
    anyone could write to /tmp came ahead of the shipped standard library,
    in audit, check, run, the pool and bounded runs alike."""
    import tempfile
    if path is not None:
        return path, None
    home = tempfile.mkdtemp(prefix="velaris-source-")     # 0700 on POSIX
    tmp = tempfile.NamedTemporaryFile("w", suffix=".vel", delete=False,
                                      encoding="utf-8", dir=home)
    tmp.write(source)
    tmp.close()
    return tmp.name, tmp.name


def _drop_source_file(temp: str | None) -> None:
    """Remove what _source_to_file made: the file and its directory."""
    if temp:
        import shutil
        shutil.rmtree(os.path.dirname(temp), ignore_errors=True)


def _ffi_modules_named(path: str, source: str | None) -> set[Any]:
    """Top-level Python packages a program names in py* calls.

    Only literal module names can be read without running; a module
    built from text at runtime cannot, and the audit says so.
    """
    return _ffi_named(path, source)[0]


def _ffi_named(path: str, source: str | None) -> tuple[set[str], bool]:
    """(modules, any): the top-level packages named as literal text in the
    module argument of a py* call, and whether some such call names its
    module with a value built while running - the audit's `ffi_any`
    (4.0, velaris-spec Q4), without which a computed module name was
    invisible in velaris.audit/1."""
    try:
        funcs, _ = load_program(path, source)
    except Exception:
        return set(), False
    found: set[Any] = set()
    computed: list[Call] = []
    import dataclasses as _dc

    def visit(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call) and node.name in _FFI_CALLS \
                and node.args:
            if isinstance(node.args[0], Str):
                found.add(node.args[0].value.split(".")[0])
            else:
                computed.append(node)
        for f in _dc.fields(node):
            visit(getattr(node, f.name))

    for fn in funcs:
        visit(fn.body)
    return found, bool(computed)


# the builtins whose first argument names the Python module they reach
_FFI_CALLS = ("py", "py_int", "py_float", "py_json", "py_new")


def _fs_net_named(path: str, source: str | None) -> tuple[Any, ...]:
    """(paths, hosts) a program names in literals, for scoped grants.

    paths: {"read": [...], "write": [...], "read_any": bool,
    "write_any": bool} - the flags say a call used a path built at
    runtime, which no literal can cover. hosts: {"hosts": [...],
    "any": bool} the same way. Like _ffi_modules_named, this reads
    literals only.
    """
    paths: dict[str, Any] = {"read": set(), "write": set(), "read_any": False,
             "write_any": False}
    hosts: dict[str, Any] = {"hosts": set(), "any": False}
    try:
        funcs, _ = load_program(path, source)
    except Exception:
        return paths, hosts
    import dataclasses as _dc
    host_of = _host_entry

    def visit(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call):
            kind = {"read_file": "read", "read_file_secret": "read",
                    "file_exists": "read",
                    "write_file": "write"}.get(node.name)
            if kind and node.args:
                if isinstance(node.args[0], Str):
                    paths[kind].add(node.args[0].value)
                else:
                    paths[kind + "_any"] = True
            at = {"fetch": 0, "post": 0, "fetch_status": 0,
                  "request": 1}.get(node.name)
            if at is not None and len(node.args) > at:
                arg = node.args[at]
                h = host_of(arg.value) if isinstance(arg, Str) else None
                if h:
                    hosts["hosts"].add(h)
                else:
                    hosts["any"] = True
        for f in _dc.fields(node):
            visit(getattr(node, f.name))

    for fn in funcs:
        visit(fn.body)
    return paths, hosts


def _secrets_named(path: str, source: str | None) -> dict[Any, Any] | None:
    """velaris.audit/1's `secrets` (6.0): which builtins handed this
    program a Secret, whether it lets one out, and why.

    `sources` are the builtins the program as loaded reaches that return
    a Secret. `declassifies` says whether any call to declassify is in
    the text; `declassifications` names each, with the reason written in
    the call and the function it is in - which is why the reason has to
    be a literal (E561). A consumer that wants to know whether a program
    can ever let a secret out reads `declassifies` and nothing else.

    None when the program cannot be loaded: then nothing was determined.
    """
    try:
        funcs, _ = load_program(path, source)
    except Exception:
        return None
    import dataclasses as _dc
    table = {f.name: f for f in funcs}
    sources: set[Any] = set()
    out: list[Any] = []

    def visit(node: Any, where: str, line: int) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x, where, line)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call):
            reached = builtin_reached(node.name, table)
            if reached in SECRET_SOURCES:
                sources.add(reached)
            elif reached == "declassify" and len(node.args) == 2 \
                    and isinstance(node.args[1], Str):
                out.append({"reason": node.args[1].value,
                            "function": where, "line": node.line})
        for f in _dc.fields(node):
            visit(getattr(node, f.name), where, line)

    for fn in funcs:
        shown = ("an inline function value" if fn.name.startswith("fn#")
                 else fn.name)
        visit(fn.body, shown, fn.line)
    out.sort(key=lambda d: (d["function"], d["line"], d["reason"]))
    return {"sources": sorted(sources),
            "declassifies": bool(out),
            "declassifications": out}


_NATIVE_SUFFIXES = (".so", ".pyd", ".dylib")


def _ffi_native(modules: Any) -> dict[Any, Any]:
    """Per named Python module, whether it - or code it ships - is native
    (a compiled extension: .so / .pyd / .dylib), decided from the files on
    disk WITHOUT importing the module (8.0). A module is placed on the
    import path and its origin and, for a package, its on-disk tree are
    looked at; finding a compiled extension makes it `"native"`. Anything
    else is `"unknown"`, never `"false"`: a pure-Python module can import a
    native one, and that is not visible without running its code, so the
    audit does not claim a module is free of native code - only that it
    could not find any. The verdict reflects the packages installed on the
    machine that runs the audit.

    Importing is deliberately avoided: `importlib.util.find_spec` on a
    top-level name locates the module without executing it, so a module
    whose import would write a file, open a socket or otherwise act does
    none of that here."""
    import importlib.util
    out = {}
    for m in sorted(set(modules)):
        verdict = "unknown"
        try:
            spec = importlib.util.find_spec(m)   # top-level: no execution
        except Exception:
            spec = None
        if spec is not None:
            origin = spec.origin or ""
            if origin.endswith(_NATIVE_SUFFIXES) or origin == "built-in":
                verdict = "native"           # a C extension, or compiled in
            else:
                seen = 0
                for base in (spec.submodule_search_locations or []):
                    if verdict == "native":
                        break
                    try:
                        for _root, _dirs, files in os.walk(base):
                            seen += 1
                            if any(f.endswith(_NATIVE_SUFFIXES)
                                   for f in files):
                                verdict = "native"
                                break
                            if seen > 5000:      # a huge tree: stop looking
                                break
                    except OSError:
                        continue
        out[m] = verdict
    return out


def _host_entry(url: str) -> str | None:
    """A literal URL's `net_hosts` entry: the host, lower-cased, trailing
    dots removed, with `:port` when the URL writes one - or None when it
    has no host. `https://` is put in front of a URL with no scheme, as
    the runtime does."""
    import urllib.parse
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    try:
        parts = urllib.parse.urlsplit(url)
        h = (parts.hostname or "").lower().rstrip(".")
        if not h:
            return None
        # IPv6 in brackets, so host:port is not ambiguous, and any
        # structural character encoded: the entry is a grant the
        # safe_command can be built from and parsed back (spec v0.2, Q5
        # resolved)
        token = f"[{h}]" if ":" in h else _pct_encode(h)
        return f"{token}:{parts.port}" if parts.port else token
    except ValueError:
        return None


def _safe_grants(effects: Any, modules_named: Any, paths: Any, hosts: Any) -> list[Any]:
    """The narrowest budget the audit can write from what it read."""
    out = []
    for e in effects:
        if e == "ffi":
            out.append("ffi:" + ",".join(modules_named) if modules_named
                       else "ffi")
        elif e == "fs":
            for kind in ("read", "write"):
                if paths[kind + "_any"]:
                    out.append(f"fs:{kind}")
                else:
                    out.extend(f"fs:{kind}:{_pct_encode(p)}"
                               for p in sorted(paths[kind]))
            if not any(x.startswith("fs") for x in out):
                out.append("fs")           # declared, never used literally
        elif e == "net":
            if hosts["any"] or not hosts["hosts"]:
                out.append("net")
            else:
                out.extend(f"net:{h}" for h in sorted(hosts["hosts"]))
        else:
            out.append(e)
    return out


def _ceiling_args(timeout: Any, max_memory_mb: Any) -> None:
    """ValueError when a check's, an audit's or an attestation's ceiling
    is not one."""
    if timeout is not None and not (
            isinstance(timeout, (int, float))
            and not isinstance(timeout, bool)
            and 0 < timeout < float("inf")):
        raise ValueError("timeout is a number of seconds greater than 0, "
                         "or None for no ceiling")
    if max_memory_mb is not None and not (
            isinstance(max_memory_mb, int)
            and not isinstance(max_memory_mb, bool) and max_memory_mb >= 1):
        raise ValueError("max_memory_mb is a whole number of MB, 1 or more, "
                         "or None for no cap")


def check(source: str, *, path: str | None = None, prove: bool = True,
          timeout: Any = CHECK_TIMEOUT_DEFAULT,
          max_memory_mb: Any = CHECK_MEMORY_MB_DEFAULT,
          import_root: Any = None) -> CheckResult:
    """Compile without running. Every problem, plus what was proven.

    From 8.1 the check runs in a child process under a ceiling: `timeout`
    seconds and `max_memory_mb` MB, 60 and 2048 unless given - the ceiling
    `velaris check` has had since 8.0. Source crafted to stall the prover
    or bloat the checker comes back as a problem, E613 for the clock and
    E614 for memory, instead of holding the caller. Raise either for a
    large program; None for both checks in this process with no ceiling,
    as every check did before 8.1. The child costs an interpreter's
    startup; velaris.Pool(...).check() keeps one alive.

    `import_root`, when given, is the directory imports must stay inside
    (E515 otherwise): pass it when the source is someone else's.
    """
    _ceiling_args(timeout, max_memory_mb)
    if (timeout is not None or max_memory_mb is not None) and not _state._IN_CHILD:
        with Pool(size=1, timeout=timeout, max_memory_mb=max_memory_mb,
                  import_root=import_root) as pool:
            return pool.check(source, path=path, prove=prove)
    saved = _state.IMPORT_ROOT
    if import_root is not None:
        vars(_state)["IMPORT_ROOT"] = os.path.realpath(str(import_root))
    try:
        return _check_here(source, path=path, prove=prove)
    finally:
        vars(_state)["IMPORT_ROOT"] = saved


@_on_big_stack
def _check_here(source: str, *, path: str | None = None,
                prove: bool = True) -> CheckResult:
    """check() in this process, with no ceiling."""
    where, temp = _source_to_file(source, path)
    try:
        problems: list[Problem] = []
        proven: set[str] = set()
        runtime: list[str] = []
        try:
            funcs, records = load_program(where, source if path else None)
            errors: list[Any] = []
            check_main(funcs, errors, running=False)
            check_effects(funcs, errors)
            if not errors:
                check_types(funcs, records, errors)
            if not errors and prove:
                check_proofs(funcs, records, errors, proven)
            seen: set[Any] = set()
            problems = []
            for e in errors:             # two stages can find one problem
                key = (e.code, e.file, e.line, e.message)
                if key not in seen:
                    seen.add(key)
                    problems.append(_as_problem(e, where))
            for f in funcs:
                if (f.requires or f.ensures) and f.name not in proven:
                    runtime.append(f.name)
        except VelarisError as e:
            problems = [_as_problem(e, where)]
        except RecursionError:            # a coded error, not a traceback (8.2)
            from .errors import _too_deep_error
            problems = [_as_problem(_too_deep_error(False), where)]
        return CheckResult(not problems, problems, sorted(proven),
                           sorted(runtime))
    finally:
        _drop_source_file(temp)


def audit(source: str, *, path: str | None = None,
          timeout: Any = CHECK_TIMEOUT_DEFAULT,
          max_memory_mb: Any = CHECK_MEMORY_MB_DEFAULT,
          import_root: Any = None) -> AuditResult:
    """What this program can touch, promise and fail at.

    The same answer `velaris audit` prints, as data, with a schema name
    so a dashboard or an agent can rely on its shape.

    Under the same ceiling as check() from 8.1, with the same defaults and
    the same way out: an audit that does not finish in time or in memory
    comes back `ok: false` with E613 or E614 as its problem, and every
    other field saying nothing was determined. `import_root` as in check().
    """
    _ceiling_args(timeout, max_memory_mb)
    if (timeout is not None or max_memory_mb is not None) and not _state._IN_CHILD:
        with Pool(size=1, timeout=timeout, max_memory_mb=max_memory_mb,
                  import_root=import_root) as pool:
            return pool.audit(source, path=path)
    saved = _state.IMPORT_ROOT
    if import_root is not None:
        vars(_state)["IMPORT_ROOT"] = os.path.realpath(str(import_root))
    try:
        return _audit_here(source, path=path)
    finally:
        vars(_state)["IMPORT_ROOT"] = saved


def _unfinished_audit(problem: "Problem") -> AuditResult:
    """The velaris.audit/1 document of an audit that was stopped: ok false,
    the problem that stopped it, and nothing determined."""
    return AuditResult(
        schema=AUDIT_SCHEMA, velaris_version=VERSION, ok=False,
        problems=[problem], effects=[], functions=[], proven_share=None,
        safe_command="velaris <file> --allow ''",
        warnings=[problem.message], ffi_modules=[], loops_unshown=0,
        contract_coverage=[],
        fs_paths={"read": [], "write": [], "read_any": False,
                  "write_any": False},
        net_hosts={"hosts": [], "any": False}, ffi_any=False, counts=None,
        prover=False, secrets=None, ffi_native={})


@_on_big_stack
def _audit_here(source: str, *, path: str | None = None) -> AuditResult:
    """audit() in this process, with no ceiling."""
    where, temp = _source_to_file(source, path)
    try:
        report = inspect_source(where, source if path else None)
        own = [f for f in report["functions"]
               if os.path.abspath(f["file"]) == os.path.abspath(where)]
        # A uses clause naming anything but the seven does not compile
        # (E300, which names it). Until 4.1 the name still reached
        # effects, functions[].effects and safe_command of the document
        # that reported the E300, so `uses io, teleport` gave a
        # safe_command that does not parse - against velaris-spec 3.2
        # and 8.3, which say effects holds only the seven and
        # safe_command always parses. Found writing the conformance
        # corpus (velaris-spec tests/L1).
        for f in own:
            f["effects"] = [e for e in f["effects"] if e in ALL_EFFECTS]
        effects = sorted({e for f in own for e in f["effects"]})
        promising = [f for f in own if f["requires"] or f["ensures"]]
        proven = [f["name"] for f in promising if f["status"] == "proven"]
        share = round(100.0 * len(proven) / len(promising), 1) \
            if promising else None
        warnings = []
        own_inline = [lp for lp in report.get("inline_loops", [])
                      if os.path.abspath(lp["file"]) == os.path.abspath(where)]
        unshown = [f["name"] for f in own if f.get("loops_unshown")]
        unshown += [f"an inline function at line {lp['line']}"
                    for lp in own_inline if lp["verdict"] == "unshown"]
        if unshown:
            warnings.append(
                "termination is not shown for a loop in: "
                + ", ".join(unshown)
                + " (a counter must move one step toward an unchanging "
                  "limit; E612 under check --strict)")
        coverage = contract_coverage(own, report.get("records", []))
        if coverage:
            warnings.append(
                "these functions transform data and promise nothing: "
                + ", ".join(coverage))
        named, ffi_any = _ffi_named(where, source if path else None)
        modules_named = sorted(named)
        paths_named, hosts_named = _fs_net_named(where, source if path
                                                 else None)
        secrets = _secrets_named(where, source if path else None)
        # counts (4.2): the most fs and net operations one call to any of
        # the audited file's functions can perform, by velaris-spec 9.4's
        # fixed rules - 0 for an effect none of them declares, None where
        # the text fixes no bound. The whole field is None when the file
        # does not compile: then nothing was determined. prover (4.2):
        # whether a prover checked the promises; without one no status is
        # "proven", and a proven_share of 0 says nothing about what could
        # be proven.
        counts = None
        compiled = not report["errors"]
        if compiled:
            try:
                loaded_funcs, _ = load_program(where, source if path
                                               else None)
                bounds, _ = _operation_bounds(loaded_funcs)
                names = [f["name"] for f in own if f["name"] in bounds]
                counts = {e: _as_count(max([bounds[n][e] for n in names]
                                           or [0]))
                          for e in COUNTED_EFFECTS}
            except Exception:
                counts = None
        if "ffi" in effects:
            if modules_named:
                warnings.append(
                    "this program calls Python modules "
                    + ", ".join(modules_named)
                    + "; grant exactly those with ffi:"
                    + ",".join(modules_named)
                    + " rather than plain ffi")
                native = [m for m in modules_named
                          if _ffi_native([m]).get(m) == "native"]
                if native:
                    warnings.append(
                        "native code (a compiled extension) ships with: "
                        + ", ".join(native)
                        + " - there is no source to read, and a budget does "
                        "not contain what it does (ffi_native)")
                if ffi_any:
                    warnings.append(
                        "a call into Python names its module with a value "
                        "built while running; ffi_modules cannot list it, "
                        "and a budget of the modules listed refuses it "
                        "(E311)")
            else:
                warnings.append(
                    "this program calls Python through a module name the "
                    "audit cannot read statically; plain ffi grants "
                    "everything Python can do")
        return AuditResult(
            schema=AUDIT_SCHEMA, velaris_version=VERSION,
            ok=not report["errors"],
            # Problem objects, like check() and run() - they carry
            # .as_dict() for anyone who wants plain data. Returning
            # dicts here and objects there made callers handle both.
            problems=[Problem(e.get("code"), e.get("message"),
                              e.get("line"), e.get("file"),
                              e.get("fixes", []))
                      for e in report["errors"]],
            effects=effects,
            functions=[{"name": f["name"], "effects": sorted(f["effects"]),
                        "can_fail": f["can_fail"],
                        "requires": f["requires"], "ensures": f["ensures"],
                        "status": f["status"],
                        "loops_unshown": f.get("loops_unshown", 0)}
                       for f in own],
            loops_unshown=sum(f.get("loops_unshown", 0) for f in own)
            + len([lp for lp in own_inline if lp["verdict"] == "unshown"]),
            contract_coverage=coverage,
            proven_share=share,
            safe_command=("velaris <file> --allow " + (
                ",".join(_safe_grants(effects, modules_named,
                                      paths_named, hosts_named))
                or "''")),
            ffi_modules=modules_named,
            fs_paths={"read": sorted(paths_named["read"]),
                      "write": sorted(paths_named["write"]),
                      "read_any": paths_named["read_any"],
                      "write_any": paths_named["write_any"]},
            net_hosts={"hosts": sorted(hosts_named["hosts"]),
                       "any": hosts_named["any"]},
            ffi_any=ffi_any,
            counts=counts,
            secrets=secrets,
            ffi_native=_ffi_native(modules_named) if modules_named else {},
            prover=bool(compiled and report.get("proofs")),
            warnings=warnings)
    finally:
        _drop_source_file(temp)


def run(source: str, *, path: str | None = None,
        allow: set[str] | str | None = None, deny: set[str] | None = None,
        args: list[Any] | None = None, stdin: str = "",
        native: bool = True, timeout: float | None = None,
        max_memory_mb: int | None = None,
        seed: int | None = None, freeze_time: Any = None,
        import_root: Any = None) -> RunResult:
    """Run a program under an effect budget and capture what it did.

    allow={"io"} means it cannot read files, reach the network, call
    Python, ask the clock or use randomness - whatever its source says
    about itself. A refused effect stops the program and is reported in
    refused_effect; it cannot be caught by the program.

    allow=None is the same io: the console and nothing else. That is a
    change in 5.0, where it used to grant all seven effects. To ask for
    every effect, say so - allow="all", which writes one line to stderr,
    or allow=set(velaris.ALL_EFFECTS).

    timeout (seconds) and max_memory_mb bound the OTHER two things a
    program can do to the machine that runs it: spin forever, or eat
    memory. With either set, the program runs in a separate process
    that is killed on breach, and the result says which limit it hit.
    An agent framework calling this ten thousand times needs both.

    Memory limits use RLIMIT_AS on POSIX and a job object with
    JOB_OBJECT_LIMIT_PROCESS_MEMORY on Windows: enforced on Linux and,
    since 3.1, on Windows; best-effort on macOS, where the limit is set
    but not reliably honoured and the timeout is what stops a runaway.
    If the Windows job object cannot be made the cap is recorded and not
    enforced rather than the run failing. memory_cap_is_enforced() says
    which of those this machine is. The timeout is enforced everywhere.

    Calling this in a loop starts an interpreter every time. velaris.Pool
    keeps workers alive under one budget and is about a hundred times
    faster for a small program; EMBEDDING.md states what it does and
    does not carry between programs.

    The result's `receipt` (8.1) is the signed-to-be record of this run
    (receipt_statement). `import_root` as in check(): the directory
    imports must stay inside, for a source someone else wrote.
    """
    if timeout is not None or max_memory_mb is not None:
        return _run_bounded(source, path=path, allow=allow, deny=deny,
                            args=args, stdin=stdin, native=native,
                            timeout=timeout, max_memory_mb=max_memory_mb,
                            seed=seed, freeze_time=freeze_time,
                            import_root=import_root)
    budget = _budget_from(allow, deny)
    saved = _state.IMPORT_ROOT
    if import_root is not None:
        vars(_state)["IMPORT_ROOT"] = os.path.realpath(str(import_root))
    try:
        return _run_in_process(source, path=path, budget=budget,
                               args=args, stdin=stdin, native=native,
                               seed=seed, freeze_time=freeze_time)
    finally:
        vars(_state)["IMPORT_ROOT"] = saved


@_on_big_stack
def _run_in_process(source: Any, *, path: Any, budget: Any, args: Any, stdin: Any,
                    native: Any, seed: Any = None, freeze_time: Any = None,
                    emit: Any = None, name: Any = None) -> RunResult:
    """run() with the budget already parsed, in THIS process.

    The budget is installed, the program runs under it, and whatever
    budget was in place before is put back - so several audits and runs
    can share a process, and so a pool worker comes back to its own
    budget after every program it serves.

    The result carries the run's receipt (8.1). `emit`, when given, is
    handed each thing the receipt records as it happens: a pool worker
    streams them to its parent, which keeps them if the worker is killed
    before it can answer.
    """
    import time as _time
    recorder = _RunRecorder(emit)
    saved_recorder = _state.RUN_RECORDER
    started_at, t0 = _utc_now_ms(), _time.monotonic()
    vars(_state)["RUN_RECORDER"] = recorder
    try:
        result = _run_program(source, path=path, budget=budget, args=args,
                              stdin=stdin, native=native, seed=seed,
                              freeze_time=freeze_time, name=name)
    finally:
        vars(_state)["RUN_RECORDER"] = saved_recorder
    result.receipt = receipt_statement(
        recorder, name=_entry_name(path, name),
        entry_bytes=source.encode("utf-8", "surrogatepass"),
        budget=budget.spec(),
        parameters=_run_parameters(seed, freeze_time, None, None),
        result=result, started_at=started_at,
        wall_time_ms=(_time.monotonic() - t0) * 1000)
    return result


def _run_program(source: Any, *, path: Any, budget: Any, args: Any, stdin: Any, native: Any, seed: Any,
                 freeze_time: Any, name: Any) -> RunResult:
    """The run itself, for _run_in_process, which adds its receipt."""
    import io as _io
    import contextlib
    where, temp = _source_to_file(source, path)

    saved = Budget.snapshot()
    saved_args = list(_state.PROGRAM_ARGS)
    saved_handles, saved_next = dict(_state.PY_OBJECTS), _state.PY_NEXT[0]
    saved_params = (_state.SEED, _state.FROZEN_TIME, _state._RNG)
    out, err = _io.StringIO(), _io.StringIO()
    problems, refused, code = [], None, 0
    used: dict[Any, Any] = {}
    try:
        budget.install()
        set_run_params(seed, freeze_time)     # --seed / --freeze-time (8.0)
        _state.PROGRAM_ARGS[:] = list(args or [])
        read: list[Any] = []
        try:
            load_program(where, source if path else None, loaded=read)
        except Exception:                  # the check below says why
            pass
        if _state.RUN_RECORDER is not None:
            _state.RUN_RECORDER.set_subjects(_receipt_subjects(
                where, _entry_name(path, name),
                source.encode("utf-8", "surrogatepass"), read))
        result = _check_here(source, path=path)
        if not result.ok:
            return RunResult(False, "", "", result.problems, None, 1,
                             effects_used={})
        funcs, records = load_program(where, source if path else None)
        errors: list[Any] = []
        proven: set[Any] = set()
        check_proofs(funcs, records, errors, proven)
        compiled = compile_native(funcs, proven) if native else {}
        if _state.RUN_RECORDER is not None:
            _state.RUN_RECORDER.compiled = True
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            old_stdin = sys.stdin
            sys.stdin = _io.StringIO(stdin)
            try:
                interpret(funcs, compiled)
            finally:
                sys.stdin = old_stdin
    except SystemExit as e:
        # exit_with gives a number; a Python module the program was granted
        # can raise SystemExit with anything (8.2: text made this raise)
        code = e.code if isinstance(e.code, int) \
            else (0 if e.code is None else 1)
    except VelarisError as e:
        _note_error(e)
        problems = [_as_problem(e, where)]
        refused = _refused_from(e.code, e.message)
        code = 1
    except RecursionError:
        # a value built past Python's own recursion limit (8.2)
        from .errors import _too_deep_error
        deep = _too_deep_error(True)
        _note_error(deep)
        problems = [_as_problem(deep, where)]
        code = 1
    except FailSignal as e:
        _note_stop("E521", 0)
        problems = [Problem("E521", f"a failure escaped: {e.reason}", 0,
                            where, ["handle it with check"])]
        code = 1
    finally:
        used = dict(_state.EFFECT_USES)           # this run's, before the old
        Budget.restore(saved)              # budget's come back
        _state.PROGRAM_ARGS[:] = saved_args
        # handles a program opened and never closed are this program's,
        # not the next one's - the same reason the budget is put back
        _state.PY_OBJECTS.clear()
        _state.PY_OBJECTS.update(saved_handles)
        _state.PY_NEXT[0] = saved_next
        g = vars(_state)                          # put run params back too
        g["SEED"], g["FROZEN_TIME"], g["_RNG"] = saved_params
        _drop_source_file(temp)
    return RunResult(code == 0 and not problems, out.getvalue(),
                     err.getvalue(), problems, refused, code,
                     effects_used=used)


def _budget_from(allow: Any, deny: Any) -> "Budget":
    """The library's allow= / deny= as a Budget; a bad grant is a
    ValueError before anything runs.

    allow=None is `io` since 5.0 - the same default the command line
    has - where it used to be all seven effects. run(), a bounded run
    and Pool all come through here, so they all have it. The way to ask
    for everything is to say so: allow="all", or the seven names.
    """
    if allow is not None and not isinstance(allow, str):
        if {str(a).strip() for a in allow} == {ALLOW_ALL}:
            allow = ALLOW_ALL          # allow={"all"}, a set of one
    if isinstance(allow, str):
        asked = expand_allow(allow)
        if allow.strip() == ALLOW_ALL:
            warn_allow_all("velaris.run")
    elif allow is None:
        asked = DEFAULT_ALLOW
    else:
        asked = ",".join(sorted(allow))
    try:
        budget = Budget.parse(asked)
    except BudgetError as e:
        raise ValueError(str(e))
    unknown = set(deny or ()) - set(ALL_EFFECTS)
    if unknown:
        raise ValueError(f"not an effect: {', '.join(sorted(unknown))}; "
                         f"they are {', '.join(ALL_EFFECTS)}")
    budget.deny(deny or ())
    return budget


def _refused_from(code: str, message: str) -> Any:
    """What a refusal was about, for RunResult.refused_effect: the
    effect for E310, ffi:module for E311, fs:<path> for E313,
    net:<host> for E314, and the counted effect for E315."""
    if code == "E310":
        m = re.search(r"needs the '(\w+)' effect", message)
        return m.group(1) if m else None
    if code == "E311":
        m = re.search(r"module '([^']+)'", message)
        return "ffi:" + m.group(1) if m else "ffi"
    if code == "E313":
        m = re.search(r"reaches '([^']+)'", message)
        return "fs:" + m.group(1) if m else "fs"
    if code == "E314":
        m = re.search(r"host '([^']+)'", message)
        return "net:" + m.group(1) if m else "net"
    if code == "E315":
        m = re.search(r" (fs|net) operation", message)
        return (m.group(1) if m else "") + "@count"
    # 8.1: the three refusals 7.1.2 and 8.0 added were left out here, so a
    # run stopped by one reported refused_effect None and the doors logged
    # it as "failed" rather than "refused"
    if code == "E316":
        return "fs@size"
    if code == "E317":
        m = re.search(r"its host (\S+) is outside", message)
        return "net:" + m.group(1) if m else "net"
    if code == "E318":
        m = re.search(r"reaches '([^']+)'", message)
        return "fs:" + m.group(1) if m else "fs"
    return None


# ---------------------------------------------------------------------------
# Memory caps, per platform
#
#     POSIX: the child sets RLIMIT_AS on itself before it does anything
#     else, from --max-memory-mb on its own command line. It used to be
#     a preexec_fn in the parent, which is documented as unsafe when the
#     parent has threads - and the HTTP door, and now Pool, both do.
#
#     Windows: there is no RLIMIT_AS. The equivalent is a job object
#     with JOB_OBJECT_LIMIT_PROCESS_MEMORY, which the parent must build
#     before the child runs. So the child is created suspended, assigned
#     to the job, and only then resumed: no instruction of the child
#     runs outside the cap.
#
#     If any of it fails, the cap is recorded and not enforced - the
#     behaviour Velaris had on Windows before 3.1 - rather than the run
#     failing. The timeout is enforced on every platform either way.
# ---------------------------------------------------------------------------


def _cap_this_process(mb: Any) -> bool:
    """Cap this process's address space. True if the cap took hold."""
    try:
        import resource                    # POSIX only
    except ImportError:
        return False                       # Windows: the job object does it
    try:
        cap = int(mb) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        return True
    except Exception:
        return False


# How a process under one of these caps says it ran out. CPython raises
# MemoryError when it can; when an allocation fails where it cannot make
# even that, it reports "error return without exception set" instead - on
# Linux under a 120 MB cap, about half the time (8.1); the C library says
# "Cannot allocate memory". A job object, or the kernel, ends it with -9.
_OUT_OF_MEMORY_SIGNS = ("MemoryError", "Cannot allocate",
                        "error return without exception set")


def _out_of_memory(said: str) -> bool:
    """Does this text, from a capped process, say it ran out of memory?"""
    return any(sign in (said or "") for sign in _OUT_OF_MEMORY_SIGNS)


class _WindowsMemoryJob:
    """A Windows job object capping one child's committed memory.

    An allocation past the cap fails, which reaches a Python child as
    MemoryError. KILL_ON_JOB_CLOSE means closing this handle kills
    whatever is still inside it, so a parent that goes away - or a Pool
    that is closed - cannot leave a worker behind.

    Every call is checked and every failure raises, so the caller can
    fall back to recording the cap without enforcing it.
    """

    LIMIT_PROCESS_MEMORY = 0x00000100
    LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    EXTENDED_LIMIT_INFORMATION = 9
    CREATE_SUSPENDED = 0x00000004

    def __init__(self, max_memory_mb: int) -> None:
        import ctypes
        from ctypes import wintypes as w

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount",
                "WriteTransferCount", "OtherTransferCount")]

        class BASIC_LIMITS(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", w.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", w.DWORD),
                        ("SchedulingClass", w.DWORD)]

        class EXTENDED_LIMITS(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC_LIMITS),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        # the default restype is a 32-bit int, which truncates a handle
        k.CreateJobObjectW.restype = w.HANDLE
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        k.SetInformationJobObject.restype = w.BOOL
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int,
                                              ctypes.c_void_p, w.DWORD]
        k.AssignProcessToJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.CloseHandle.restype = w.BOOL
        k.CloseHandle.argtypes = [w.HANDLE]
        nt = ctypes.WinDLL("ntdll", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        nt.NtResumeProcess.argtypes = [w.HANDLE]

        self._ctypes, self._k, self._nt = ctypes, k, nt
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObject failed")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        info = EXTENDED_LIMITS()
        info.BasicLimitInformation.LimitFlags = (
            self.LIMIT_PROCESS_MEMORY | self.LIMIT_KILL_ON_JOB_CLOSE)
        info.ProcessMemoryLimit = int(max_memory_mb) * 1024 * 1024
        if not k.SetInformationJobObject(
                self.handle, self.EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
            self.close()
            raise OSError(err, "SetInformationJobObject failed")

    def adopt(self, proc: Any) -> None:
        """Put a suspended child in the job, then let it run."""
        if not self._k.AssignProcessToJobObject(self.handle,
                                                int(proc._handle)):
            raise OSError(self._ctypes.get_last_error(),  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
                          "AssignProcessToJobObject failed")
        self._nt.NtResumeProcess(int(proc._handle))

    def close(self) -> None:
        handle, self.handle = getattr(self, "handle", None), None
        if handle:
            try:
                self._k.CloseHandle(handle)
            except Exception:
                pass


def _spawn_capped(cmd: list[Any], max_memory_mb: Any, **popen_kw: Any) -> tuple[Any, ...]:
    """Start cmd under a memory cap. Returns (proc, job, how) - `job`
    must be closed once the child is finished with, and `how` is one of
    'RLIMIT_AS', 'job object' or 'not enforced'."""
    import subprocess
    if max_memory_mb is None:
        return subprocess.Popen(cmd, **popen_kw), None, "no cap asked for"
    if os.name != "nt":
        # the child caps itself: from --max-memory-mb in cmd, or from
        # VELARIS_CHECK_MEMORY_MB for the child of a command-line check
        return subprocess.Popen(cmd, **popen_kw), None, "RLIMIT_AS"
    try:
        job = _WindowsMemoryJob(max_memory_mb)
    except Exception:
        return subprocess.Popen(cmd, **popen_kw), None, "not enforced"
    suspended = dict(popen_kw)
    suspended["creationflags"] = (popen_kw.get("creationflags", 0)
                                  | _WindowsMemoryJob.CREATE_SUSPENDED)
    proc = subprocess.Popen(cmd, **suspended)
    try:
        job.adopt(proc)
    except Exception:
        job.close()                        # kills the suspended child
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        return subprocess.Popen(cmd, **popen_kw), None, "not enforced"
    return proc, job, "job object"


def memory_cap_is_enforced() -> bool:
    """Does max_memory_mb actually stop a program on this machine?

    True on Linux (RLIMIT_AS) and on Windows when a job object can be
    created. False on macOS, where RLIMIT_AS is set and not reliably
    honoured, and on a Windows where the job object could not be made.
    A suite that asserts the cap fires should ask this first.
    """
    if sys.platform == "linux":
        return True
    if os.name == "nt":
        try:
            job = _WindowsMemoryJob(256)
        except Exception:
            return False
        job.close()
        return True
    return False


def _run_bounded(source: Any, *, path: Any, allow: Any, deny: Any, args: Any, stdin: Any, native: Any,
                 timeout: Any, max_memory_mb: Any, seed: Any = None, freeze_time: Any = None,
                 import_root: Any = None) -> RunResult:
    """run() in a child process that can be killed: a pool of one worker,
    made for this run and closed after it.

    Until 8.1 this started the command line in a child and compiled the
    program first in THIS process, with no ceiling at all - so a program
    crafted to stall the prover held the caller of run(timeout=5) for as
    long as it liked before the timeout ever started. The worker compiles
    under the deadline, reports effects_used like any pool run, and
    streams what the receipt records, so a run killed by the clock still
    has one."""
    with Pool(size=1, allow=allow, deny=deny, timeout=timeout,
              max_memory_mb=max_memory_mb, native=native,
              import_root=import_root) as pool:
        return pool.run(source, stdin=stdin, args=args, path=path,
                        seed=seed, freeze_time=freeze_time)


def card() -> str:
    """The language, small enough to paste into a model."""
    here = _INSTALL_DIR
    for where in (os.path.join(here, "LLM.md"),
                  os.path.join(here, "..", "LLM.md")):
        if os.path.exists(where):
            return open(where, encoding="utf-8").read()
    return ""
