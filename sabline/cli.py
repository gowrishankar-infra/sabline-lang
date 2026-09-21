"""
Sabline — "The language where you can trust code you didn't write."

New in v2.36: examples/linkcheck.vel - a tool worth running, not a
    demonstration - and network failures that say what happened
    instead of quoting the implementation.

New in v2.2: out-of-the-box readiness.
    sabline doctor          check your setup, with exact fixes
    sabline new myproject   start a project with running code
    Standalone executables (no Python needed) are built for every
    release - download one file and go.

New in v2.1: a documentation site in docs/ (python build_docs.py).
    The library page is parsed from std.vel by this very compiler -
    contracts included - and the error index is scraped from this
    file, so the docs cannot go stale.

v2.0 - THE BUILTINS KEEP THE LANGUAGE'S PROMISE (breaking change):
    to_int, get-on-a-map, read_file, and fetch can now FAIL instead of
    killing the program - and therefore must be called through check
    or try, like any fallible function. The compiler walks you to
    every call that needs updating (error E520). get on a LIST is
    unchanged: list bounds are the prover's job. New: get_or(m, k,
    default) - a total map lookup that never fails.

New in v1.20: sort_by in the standard library (generic sorting by an
    Int key function), and the ledger app gains a 'report' command
    built on it - sorted listing, biggest, smallest, totals.

New in v1.19: a grown-up standard library. stdlib/std.vel now holds
    sixteen functions written in Sabline - including sort, which
    ensures is_sorted(result) using is_sorted, also from the library.
    Violating a library requires is a compile error at your call site.

New in v1.18: FLOAT PROOFS - real IEEE-754, not pretend-math.
    Promises about Float values are proven in Z3's floating-point
    theory, bit-for-bit the arithmetic your machine performs. The
    prover will happily refute x + 0.1 + 0.1 == x + 0.2, because in
    floating point it is false - and Sabline does not pretend.

New in v1.17: FAILURE-AWARE PROOFS. The prover now understands fail,
    check, and try - so promises on 'or fail' functions are proven for
    every path that actually returns. Failing early on bad input makes
    the remaining promise EASIER to prove, and the prover knows it.

New in v1.16: QUANTIFIED LIST PROOFS.
    all_of(xs, p) / any_of(xs, p) ask whether a predicate holds for
    every / some element - and promises using them are PROVEN where Z3
    can settle the quantifier, with runtime checks guarding the rest.
    ensures all_of(result, is_positive)   is now a provable sentence.

New in v1.15: NATIVE Float and Bool. The LLVM backend now compiles pure
    functions over Int, Float, and Bool (division and % stay interpreted
    in both types, so dividing by zero is always a clean error, never a
    silent infinity). Interpreted and native runs are verified to agree.

New in v1.14: RECORD PROOFS. Promises about record fields are now
    proven before running - ensures result.x == p.x + dx is mathematics,
    and a swapped-fields bug is a compile-time counterexample with the
    record values shown. Works for records whose fields are Int, Bool,
    or other such records; lists/Float fields stay runtime-checked.

New in v1.13: the first real app - examples/ledger.vel, an expense
    tracker written in Sabline (records, contracts, or-fail parsing,
    file persistence). Two supporting builtins: chars(text) splits Text
    into single characters (pure), and file_exists(path) checks before
    reading (fs).

New in v1.12: continuous integration + repo hygiene.
    Every push is tested by GitHub Actions on Linux and Windows,
    Python 3.10 and 3.12, WITH and WITHOUT the optional dependencies -
    plus formatter and playground checks. CHANGELOG.md tells the story.

New in v1.11: a LANGUAGE SERVER - errors as you type, in any LSP editor.
    sabline lsp
    Fast checks (effects + types) on every keystroke; the full pipeline
    including Z3 proofs on save. The VS Code extension in editor/vscode
    now launches it automatically (no extra dependencies).

New in v1.10: a formatter - one canonical style for every .vel file.
    sabline fmt program.vel            rewrite in place (if needed)
    sabline fmt program.vel --stdout   print instead of writing
    sabline fmt program.vel --check    exit 1 if not formatted (for CI)

New in v1.9: a REPL - try Sabline line by line.
    sabline repl
    Loose lines run immediately (checked while running); fn / record /
    import definitions get the FULL treatment - effects, types, and
    Z3 proofs - before they are accepted into the session.

New in v1.8: a real install.
    pip install .          (from a clone; add [full] for proofs + native)
    sabline program.vel    (the command, anywhere; it gets io - 5.0)
    import "std.vel" now finds the shipped standard library from any
    folder - imports check relative-to-your-file first, then stdlib.

New in v1.7: GENERICS - one function, every type.
    fn first(xs: List of T) -> T for any T
        requires length(xs) > 0
    { return get(xs, 0) }
    T is inferred at each call; conflicting uses are clear errors.
    Plus: examples/std.vel - the first standard library, written in
    Sabline itself.

New in v1.6: FUNCTIONS ARE VALUES - pass them to other functions.
    fn apply(xs: List of Int, f: fn(Int) -> Int) -> List of Int { ... }
    apply(nums, double)
    Only PURE functions (no effects, no fail) can be passed - so a
    passed-in function can never smuggle hidden behavior.

New in v1.5: failure is visible and UNIGNORABLE.
    fn parse(t: Text) -> Int or fail { ... fail "reason" ... }
    Callers must handle it:  check parse(t) { ok v {...} fail why {...} }
    or pass it upward inside another fallible function:  try parse(t)
    Calling a fallible function any other way is a compile error.

New in v1.4: MAPS - lookup tables, written {"alice": 30, "bob": 25}.
    Typed as: Map of Text to Int (keys are Text or Int).
    get(m, key) reads, has(m, key) checks, put(m, key, v) returns a new
    map, keys(m) lists the keys, length(m) counts entries.

New in v1.3: Float - decimal numbers like 3.14.
    Int and Float never mix silently: 1 + 2.5 is a compile error with a
    fix (use to_float(1), or round(2.5) for an Int). Float math is
    runtime-checked; proofs stay Int-only for now.

New in v1.2: a browser playground - open playground/index.html and run
    Sabline with zero install (rebuild it with: python build_playground.py).

New in v1.1: escape sequences in text - \n newline, \t tab, \" quote,
    \\ backslash - plus a VS Code syntax highlighter in editor/vscode.
New in v1.0: the testers' release.
    * Multiple problems are reported in one run (one per function),
      instead of stopping at the first.
    * to_text(x) turns any value into Text.
    * --version prints the version.

Usage:
  sabline program.vel                      run a program (after pip install);
                                           it gets io - print and read_line -
                                           and every other effect is refused
  sabline repl                             interactive session
  sabline run program.vel                  the same as sabline program.vel
  sabline demo [--keep]                    a refusal, a run inside a budget
                                           and their receipts, in a minute;
                                           it writes what it runs
  sabline run f.vel --tools MANIFEST       offer the program the manifest's
        [--tool-timeout S]                 tools, over stdin and stdout as
                                           JSON lines (docs/runner.md)
  sabline <command> --help                 how to use one command
  sabline <file> --allow io,fs:read:./data grant exactly this, nothing else
  sabline <file> --allow all               every effect; says so on stderr
  sabline <file> --allow all --deny net    every effect but these
  sabline <file> --receipt FILE            and write the run's receipt
                                           (sabline.receipt/1, in-toto)
  sabline <file> --no-confine              do not ask the operating system to
                                           hold the budget too (8.4; it is
                                           asked by default, and stderr says
                                           when it is not)
  sabline migrate --to 5.0 [path]          the budget each program needs, and
        [--write]                          the command to run it under 5.0
  sabline fmt program.vel                  format to the canonical style
  sabline check program.vel                compile only, do not run
  sabline check f.vel --strict             refuse any promise left to runtime
  sabline check f.vel --json               the problems as JSON
  sabline check f.vel --sarif              findings as SARIF 2.1.0 on stdout
  sabline check f.vel --check-timeout S    the ceiling on a check or audit
        [--check-memory-mb M]              (60 s, 2048 MB; E613, E614)
  sabline proofs [path] [--min 80]         how much is proven, not just checked
  sabline proofs . --detail                which functions, one by one
  sabline proofs . --sarif                 promises left to runtime, as SARIF
  sabline <any command> --proof-timeout S  how long one proof may take
                                           (default: 120 s with Float, 3 s
                                           without; a proof that runs out
                                           says it was abandoned)
  sabline clean                            does nothing: 8.2 keeps no proofs
                                           (it says so; removed in 9.0)
  sabline test program.vel                 run every test_ function
  sabline test f.vel --from-contracts      run each function on arguments Z3
        [--count 20] [--json]              finds its requires allow, ensures
        [--witness-seconds 5]              checked; one with effects is refused
  sabline trace program.vel                show every call as it happens
  sabline explain program.vel              walk through what it does
  sabline audit program.vel                what it can touch, before you run it
  sabline audit <files or folders> --sarif what they can touch, as SARIF
  sabline audit program.vel --html [-o F]  the audit as a page to read
  sabline card                             the language, for pasting into a model
  sabline mcp [--max-allow G]              the MCP server on stdin/stdout,
        [--max-timeout S]                  the same one python -m sabline_mcp
        [--max-memory-mb M]                starts; grants at most io, 30 s and
        [--log-file F] [--log minimal]     512 MB a run unless told otherwise
        [--root DIR]                       imports only from DIR (E515)
        [--check-timeout S]                and checks and audits under
        [--check-memory-mb M]              60 s and 2048 MB
  sabline mcp-install                      set up the tools in your assistant
  sabline mcp-manifest -o tools.json       the MCP server's tools, hashed
  sabline mcp-verify tools.json            a running server against a signed
                                           manifest (-- server command)
  sabline serve [--port 8787]              an HTTP door for any language,
        [--token-file F] [--max-allow G]   behind a bearer token; grants at
        [--max-timeout S]                  most io, 30 s and 512 MB a run
        [--max-memory-mb M]                unless the operator says more
        [--log-file F] [--log minimal]     one JSON line per call
        [--bind ADDR]                      127.0.0.1 unless named; says so
        [--root DIR]                       imports only from DIR (E515)
        [--rate-limit N]                   N requests a minute a token (600)
        [--no-confine]                     workers not confined by the OS
        [--check-timeout S]                checks and audits under 60 s
        [--check-memory-mb M]              and 2048 MB unless raised
  sabline capabilities init [path]         record the capability surface in
                                           sabline.capabilities (--force)
  sabline capabilities check [path]        fail if the surface widened past
        [--check-timeout S]                it (--json, --sarif), under the
        [--check-memory-mb M]              check ceiling: 60 s and 2048 MB
  sabline review --against REF [path]      what changed since a git ref:
                                           surface, proofs, risk (--json)
  sabline deps-diff <package> OLD NEW      what a dependency's newer version
        [--json | --sarif]                 gained; <package> is pypi:NAME,
                                           npm:NAME, git:URL or dir:PATH
  sabline deps-diff --against REF [path]   the same for every upgrade in the
        [--comment --pr N]                 lockfiles changed since REF
  sabline permissions-ratchet              fail if a workflow's permissions:
        --against REF [--json]             block gives a job more than REF
        [--root DIR]                       did (exit 1; 2 if one is unreadable)
  sabline conformance [--level 1|2|3]      run sabline-spec's conformance
        [--json] [--corpus DIR]            corpus against this Sabline
  sabline attest <path> [--output FILE]    the audit as an in-toto Statement,
        [--json]                           each file by its sha256 (unsigned)
  sabline eval program.vel --receipt FILE  a run as an evaluation sandbox runs
        [--receipt-url URL] [--allow G]    it: no net, ffi or env, time and
        [--timeout S] [--max-memory-mb M]  memory limits, confined by the OS or
        [--stop-file F] [--grace S]        not run, a stop honoured, and a
        [--seed N] [--freeze-time T]       receipt always (docs/eval.md)
        [--json] [--confinement-probe]
  sabline receipt show <receipt>           a receipt as a page to read: what
        [--text] [-o FILE]                 was read, written, fetched and
                                           refused (HTML; --text for here)
  sabline skill verify <dir>               the tools and the budget a skill's
        [--tools MANIFEST] [--json]        programs would need; runs nothing
  sabline receipts diff <receipt>          what a run did that its audit does
        [--audit PROGRAM|AUDIT|STATEMENT]  not name, or that earlier runs of
        [--against RECEIPT|DIR] [--json]   the same bytes did not (exit 1)
  sabline replay <receipt> [--root DIR]    the run again, from the receipt's
        [--max-allow G] [--stdin FILE]     bytes, seed, clock, budget and
        [--expect-output FILE]             limits; every difference named
        [--responses FILE] [--json]        (exit 1), different bytes refused
  sabline <file> --record-responses FILE   and record what its py, py_int,
                                           py_float and py_json calls gave
                                           back, for sabline replay
  sabline eject program.vel [-o DIR]       a directory that runs with nothing
        [--allow G] [--force]              from here, its budget fixed in it
  sabline stats --ffi [dir] [--json]       the ffi grants a directory of
                                           programs needs, counted
  sabline explain <folder>                 a map of every file
  sabline doctor                           check the installation
  sabline new <name>                       start a fresh project
  sabline build program.vel [-o name]      one file anyone can run
  sabline add <url or path> [as name]      vendor a library into lib/
  sabline add <url> --force                replace one with different bytes
  sabline deps                             what this project depends on
  sabline deps --verify                    do the libraries match sabline.lock?
  sabline verify                           the same check, older spelling
  sabline verify <statement> [--root DIR]  an attestation or a receipt: its
        [--identity ID] [--json]           type is Sabline's and each subject
        [--skip-signature]                 is these bytes, and its signature
  sabline lsp                              language server (for editors)
  sabline version                          print the version
  python sabline.py program.vel            run a program (it gets io)
  python sabline.py program.vel --json     errors as machine-readable JSON
  python sabline.py program.vel --time     show how long the run took
  python sabline.py program.vel --no-native  force the interpreter
  python sabline.py program.vel --max-memory-mb 512  stop it past that
  python sabline.py --version

New in v0.16: IMPORTS - programs can span multiple files.
    import "mathlib.vel"
    Paths are relative to the importing file; imports chain and cycles
    are safe; a name defined in two files is a clear error; and error
    messages name the file the problem actually lives in.

New in v0.15: RECORDS - group named fields into one value.
    record Point { x: Int  y: Int }
    let p = Point(x: 3, y: 4)      then      p.x
    Records are immutable: build a new one instead of changing fields.

New in v0.14: the usability pack.
    else if chains, the % remainder operator, and text tools:
    split, contains, upper, lower.

New in v0.13: LIST PROOFS via Z3's theory of arrays.
    Contracts and code over lists (length, get, push) are now provable,
    and every 'get' carries a bounds obligation - reading past the end
    of a list can be proven and rejected before the program runs (E705).

New in v0.12: interactive programs.
    ask("your name?")   reads a line from the keyboard (an io effect)
    to_int(text)        turns text into an Int (pure; clean error if not
                        a whole number)

New in v0.11: fetch(url) is REAL - an actual HTTP GET with a 10-second
    timeout, guarded by 'uses net'. A function without 'uses net' in its
    signature provably cannot touch the network. Failures are clean
    Sabline errors (E606), never tracebacks.

New in v0.10: LOOP INVARIANTS - the prover learned loops.
    while i <= n
        invariant total >= 0
    { ... }
    Sabline proves the invariant holds at loop entry, survives every step,
    and uses it to prove the function's promises. Unproven invariants are
    still checked at runtime on every iteration.

New in v0.9: NATIVE SPEED via LLVM. Pure Int math functions (no effects,
    no contracts, no lists/text) are compiled to real machine code and
    run at C-like speed; everything else stays safely interpreted.
    Flags:  --time       show how long the run took
            --no-native  force the interpreter for everything
    (needs: pip install llvmlite ; without it, everything still runs)

New in v0.8: MODULAR proofs - verification composes across functions.
    When A calls B, the prover uses B's promises to prove A's promises,
    and proves A can never violate B's 'requires' at the call site (E701).
New in v0.7: compile-time PROOFS via the Z3 theorem prover.
    For simple functions, broken promises are now proven false and the
    program is rejected BEFORE it runs - with an exact counterexample.
    Functions Z3 cannot handle (loops, lists, text math) safely fall
    back to runtime promise checks, exactly as in v0.5.
    (needs: pip install z3-solver ; without it, runtime checks still guard)
New in v0.6: negative numbers, and / or / not, and lists.
    let scores = [42, -7, 99]
    fn biggest(xs: List of Int) -> Int requires length(xs) > 0 { ... }
New in v0.5: contracts. Functions make promises; Sabline enforces them.
    fn discount(price: Int) -> Int
        requires price >= 0        <- promise about inputs (caller's duty)
        ensures result >= 0        <- promise about output (function's duty)
Contracts must be pure: a promise cannot print, fetch, or write files.
New in v0.4: while loops and changeable variables.
    while i <= n { total = total + i   i = i + 1 }
New in v0.3: full type checking before the program runs.
    add("hello", 5)   -> rejected at compile time, not a runtime crash
New in v0.2: effects split into io, net, fs, clock, rand.

Pipeline:  source text -> LEXER -> tokens -> PARSER -> AST
           -> EFFECT CHECKER (the special part) -> INTERPRETER

Design rules:
  * Plain English keywords: fn, let, return, if, else, uses
  * A function with no `uses` clause is PURE. Pure functions cannot
    print, touch files, or the network — the compiler proves it.
  * Errors are friendly for humans AND structured (JSON) for AI agents.

Usage:
  python3 sabline.py program.vel          # run a program (it gets io)
  python3 sabline.py program.vel --json   # errors come out as JSON too
"""
import json
import os
import re
import sys

from . import state as _state
from . import naming
from .version import REFERENCE_URL, VERSION, _INSTALL_DIR, _launch_command
from .errors import SablineError
from . import confine as _confine
from .tables import CHECK_MEMORY_MB_DEFAULT, CHECK_TIMEOUT_DEFAULT
from .recorder import _RunRecorder, _note_error, _note_stop, _utc_now_ms
from .loader import load_program
from .values import FailSignal, to_text
from .budget import (
    Budget,
    BudgetError,
    _ascii_digits,
    _flag_value,
    cli_budget,
    set_run_params,
)
from .effects import check_effects
from .checker import check_types
from .prover import check_proofs, set_proof_timeout
from .native import compile_native
from .runtime import _on_big_stack, build_runtime, interpret
from .editor import contract_coverage, inspect_source, lsp_serve
from .formatter import fmt_main
from .project import build_program, doctor, new_project, packages
from .session import repl
from .results import Problem, RunResult
from .library import (
    _audit_here,
    _cap_this_process,
    _ffi_modules_named,
    _ffi_native,
    _out_of_memory,
    _secrets_named,
    _spawn_capped,
)
from .pool import pool_worker
from .findings import (
    _EFFECT_WORDS,
    print_sarif_summary,
    sarif_audit,
    sarif_check,
    sarif_proofs,
)
from .mcp_manifest import mcp_manifest_main, mcp_verify_main
from .doors import serve_main
from .migrate import migrate_main
from .ratchet import capabilities_main, review_main
from .conform import conformance_main
from .attestation import attest_main
from .receipts import _receipt_subjects, _run_parameters, receipt_statement
from .statements import verify_main
from .evaluation import eval_main
from .receipt_diff import receipts_main
from .viewer import audit_html, receipt_main, write_page
from .demo import demo_main
from .skill import skill_main
from .replay import ResponseLog, replay_main
from .upgrades import deps_diff_main
from .stats import stats_main
from .eject import eject_main
from .witnesses import from_contracts_main
from .permissions import permissions_main
from typing import Any, cast


# Every proof is made in the process that reports on it or runs it, each
# time (8.2). From 2.29 to 8.1.1 proof results were kept on disk, and twice
# what was kept there was believed (advisory-proof-cache.md,
# advisory-proof-cache-2.md); 8.2 keeps nothing. `--no-cache` and `sabline
# clean` are accepted and do nothing but say so, until 9.0.
NO_CACHE_NOTICE = ("sabline: --no-cache is deprecated and does nothing: "
                   "from 8.2 every proof is made fresh and none is kept. "
                   "The flag is accepted until 9.0.")


def _check_ceiling(argv: list[Any]) -> int:
    """Run `sabline check`/`audit` in a child under a time and memory
    ceiling and pass its output through. The child carries SABLINE_CHECK_CHILD
    so it does the work directly rather than spawning again. Past the clock
    the child is killed (E613), past the memory cap it is stopped (E614),
    and this returns 2 with a clear message either way."""
    import subprocess
    limits = {"--check-timeout": CHECK_TIMEOUT_DEFAULT,
              "--check-memory-mb": CHECK_MEMORY_MB_DEFAULT}
    rest = list(argv)
    for flag, example, unit in (("--check-timeout", "120", "seconds"),
                                ("--check-memory-mb", "4096", "MB")):
        if flag not in rest:
            continue
        at = rest.index(flag)
        if at + 1 >= len(rest) or not _ascii_digits(rest[at + 1]) \
                or int(rest[at + 1]) < 1:
            print(f"{flag} needs a whole number of {unit}, as "
                  f"{flag} {example}", file=sys.stderr)
            return 2
        limits[flag] = int(rest[at + 1])
        del rest[at:at + 2]
    timeout, memory = limits["--check-timeout"], limits["--check-memory-mb"]
    what = " ".join(rest[:2]) if rest[0] == "capabilities" else rest[0]
    # the child caps itself from SABLINE_CHECK_MEMORY_MB on POSIX (main);
    # 8.0.0 passed it nothing, so there the cap was named and never set
    env = dict(os.environ, SABLINE_CHECK_CHILD="1",
               SABLINE_CHECK_MEMORY_MB=str(memory))
    cmd = _launch_command() + rest
    proc, job, _how = _spawn_capped(
        cmd, memory, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            print(f"error[E613] {what} did not finish within {timeout} "
                  f"second(s) and was stopped: the source may be crafted to "
                  f"stall the checker. Raise the ceiling with "
                  f"--check-timeout, or run it in a sandbox you control.\n"
                  f"  reference: {REFERENCE_URL}", file=sys.stderr)
            return 2
    finally:
        if job is not None:
            job.close()
    # The child's text with its line ends made "\n": writing it here adds
    # the platform's again (8.2; on Windows `check --json` came out "\r\r\n").
    shown = out.decode("utf-8", "replace").replace("\r\n", "\n")
    said = err.decode("utf-8", "replace").replace("\r\n", "\n")
    if proc.returncode != 0 and (_out_of_memory(said)
                                 or proc.returncode in (-9, 137)):
        sys.stdout.write(shown)
        print(f"error[E614] {what} used more than {memory} MB and was "
              f"stopped: the source may be crafted to bloat the checker. "
              f"Raise the cap with --check-memory-mb, or run it in a sandbox "
              f"you control.\n  reference: {REFERENCE_URL}", file=sys.stderr)
        return 2
    if "--html" in rest and getattr(sys.stdout, "buffer", None) is not None:
        # a page is the same bytes on every system (8.5): line feeds, as the
        # child wrote them, not the platform's line ends
        sys.stdout.flush()
        sys.stdout.buffer.write(shown.encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        sys.stdout.write(shown)
    sys.stderr.write(said)
    if proc.returncode not in (0, 1, 2):
        # The child ended without an answer of its own - a crash, not a
        # verdict. Until 8.2 that came through as a bare exit status.
        print(f"error[E000] {what} stopped without an answer (exit "
              f"status {proc.returncode}), so nothing was decided. Please "
              f"report it, with the program, at https://github.com/"
              f"gowrishankar-infra/sabline-lang/issues\n"
              f"  reference: {REFERENCE_URL}", file=sys.stderr)
        return 2
    return cast(int, proc.returncode)


HELP_FLAGS = ("--help", "-h")


def usage_lines() -> dict[Any, Any]:
    """{command: its lines in the usage list above} - the list `sabline`
    with no arguments prints, so a command's --help and that list cannot
    say different things (8.2)."""
    block = (__doc__ or "").split("\nUsage:\n", 1)[-1].split("\n\n", 1)[0]
    entries: dict[Any, Any] = {}
    current = None
    for line in block.splitlines():
        m = re.match(r"  sabline (\S+)", line)
        if m:
            word = m.group(1)
            current = (None if word.startswith(("<", "-")) or "." in word
                       else word)
            if current is not None:
                entries.setdefault(current, []).append(line.rstrip())
        elif not line.startswith("    "):     # `  python sabline.py ...`
            current = None
        elif current is not None:
            entries[current].append(line.rstrip())
    return entries


def print_usage(command: str | None = None) -> int:
    """`sabline --help`, or `sabline <command> --help`: the usage, and 0."""
    if command is None:
        block = (__doc__ or "").split("\nUsage:\n", 1)[-1].split("\n\n", 1)[0]
        print(f"Sabline {VERSION}\n\nusage:\n{block}")
    else:
        print("usage:\n" + "\n".join(usage_lines()[command]))
    return 0


def _vel_files_under(target: str) -> list[Any]:
    """Every .vel file under a folder, read as `capabilities check` reads
    one: every directory but git's own. Until 8.2 `proofs` and `audit
    --sarif` left out every path holding the text ".sabline" - the old
    proof cache's folder, and with it a folder such as cfg.sabline.d/ - so
    a program there was never counted."""
    found = []
    for dp, dirs, fns in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        found += [os.path.join(dp, f) for f in fns if f.endswith(".vel")]
    return sorted(found)


def velaris_main() -> int:
    """The `velaris` command, which is now `sabline`.

    The command name is part of what STABILITY.md covers, so dropping it
    would be a breaking change and a major version (rule 1). It is kept for
    one major, says once on stderr that the name has changed, and does
    exactly what `sabline` does - it IS main(), reached under another name,
    so there is no second command to keep in step. Removed no sooner than
    9.0. pyproject.toml's [project.scripts] and npm/package.json's "bin"
    both point here."""
    naming.say_renamed("velaris", "sabline", "the `velaris` command")
    return main()


@_on_big_stack
def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["--pool-worker"]:
        return pool_worker(argv[1:])       # one child behind sabline.Pool
    # a character the console cannot show is written as an escape, as stderr
    # always did. Until 8.2 printing one on a cp1252 console ended the run
    # with a UnicodeEncodeError traceback
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(errors="backslashreplace")
        except ValueError:
            pass
    # `--` ends Sabline's own flags on a run (8.2): a file, `run` or `trace`.
    # What follows it is the program's args() and nothing else. Until 8.2
    # every flag read below scanned the whole command line and the first
    # occurrence won, so `sabline a.vel -- --allow all` granted every effect
    # and `-- --receipt x` wrote a file. It is taken off here, before
    # anything reads a flag; mcp-verify and mcp-manifest keep theirs, which
    # comes before a server command.
    program_words: list[Any] = []
    if "--" in argv and (argv[0] in ("run", "trace", "eval", "replay")
                         or argv[0] not in usage_lines()):
        at = argv.index("--")
        program_words = argv[at + 1:]
        argv = argv[:at]
        sys.argv = [sys.argv[0]] + argv
    # --no-cache (2.29) kept a command from the proof cache. 8.2 keeps no
    # cache, so the flag is taken out here, before a command - or a check's
    # child - sees it, and says it does nothing (until 9.0). Everywhere it
    # was taken out before, that is: a run's args() never held it, and the
    # server command after mcp-verify's or mcp-manifest's `--` is left alone.
    head = argv[:argv.index("--")] if "--" in argv and argv[:1] in (
        ["mcp-verify"], ["mcp-manifest"]) else argv
    if "--no-cache" in head:
        argv = [a for a in head if a != "--no-cache"] + argv[len(head):]
        sys.argv = [sys.argv[0]] + argv
        print(NO_CACHE_NOTICE, file=sys.stderr)
    # --help and -h (8.2), at the top level or after a command. What follows
    # `run` or `trace` and a file is the program's own, so there only a flag
    # straight after the command asks for help; and a server command after
    # `--` is never read for one.
    if argv and argv[0] in HELP_FLAGS:
        return print_usage()
    if argv and argv[0] in usage_lines():
        head = argv[:argv.index("--")] if "--" in argv else argv
        asked = head[1:2] if argv[0] in ("run", "trace") else head[1:]
        if any(a in HELP_FLAGS for a in asked):
            return print_usage(argv[0])
    if os.environ.get("SABLINE_CHECK_CHILD") == "1":
        vars(_state)["_IN_CHILD"] = True      # already under the ceiling
        if os.environ.get("SABLINE_CHECK_MEMORY_MB"):
            # first, as a pool worker does: POSIX caps itself here; on
            # Windows the parent put this process in a job object already
            _cap_this_process(os.environ["SABLINE_CHECK_MEMORY_MB"])
    # check and audit run under a ceiling (8.0), and so does `capabilities
    # check` (8.2.1), which compiles every program under a directory - in
    # the Action's ratchet step, a pull request's among them. Not when we
    # are already the child doing so, or --no-check-ceiling was asked for
    if (argv[:1] in (["check"], ["audit"])
            or argv[:2] == ["capabilities", "check"]) \
            and os.environ.get("SABLINE_CHECK_CHILD") != "1" \
            and "--no-check-ceiling" not in argv:
        return _check_ceiling(argv)
    # --proof-timeout S is taken out of argv here, before any command
    # sees it, so every command accepts it and none mistakes its number
    # for a file name.
    while "--proof-timeout" in argv:
        at = argv.index("--proof-timeout")
        if at + 1 >= len(argv):
            print("--proof-timeout needs a number of seconds, as "
                  "--proof-timeout 300", file=sys.stderr)
            return 1
        try:
            set_proof_timeout(argv[at + 1])
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        del argv[at:at + 2]
        sys.argv = [sys.argv[0]] + argv
    for a in [a for a in argv if a.startswith("--proof-timeout=")]:
        try:
            set_proof_timeout(a.split("=", 1)[1])
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        argv.remove(a)
        sys.argv = [sys.argv[0]] + argv
    if "--max-memory-mb" in argv and argv[:1] not in (
            ["serve"], ["mcp"], ["mcp-verify"], ["mcp-manifest"], ["eval"]):
        # before anything else this process does: a cap asked for late
        # is a cap that missed whatever was allocated first. Not for the
        # door or the MCP server, whose --max-memory-mb is the most each
        # run may have (4.0), and not for a server command handed to
        # mcp-verify
        at = argv.index("--max-memory-mb") + 1
        if at < len(argv):
            _cap_this_process(argv[at])
    if "--max-read" in argv:
        # the read ceiling (MB); read_file/read_file_secret refuse a file
        # larger than this (E316). A resource ceiling, not a grant. (7.1.2)
        at = argv.index("--max-read") + 1
        if at >= len(argv) or not _ascii_digits(argv[at]) \
                or int(argv[at]) < 1:
            print("--max-read needs a whole number of megabytes, as "
                  "--max-read 256", file=sys.stderr)
            return 2
        vars(_state)["MAX_READ_BYTES"] = int(argv[at]) * 1024 * 1024
    # --seed / --freeze-time: the run's determinism parameters (8.0). Set
    # here so every path (run, --time) sees them; not grants (set_run_params).
    _seed = _flag_value(argv, "--seed")
    _frozen = _flag_value(argv, "--freeze-time")
    if _seed is not None or _frozen is not None:
        if _seed is not None and (not _ascii_digits(_seed.lstrip("-"))
                                  or _seed.startswith("-")):
            print("--seed needs a whole number, as --seed 42",
                  file=sys.stderr)
            return 2
        try:
            set_run_params(_seed, _frozen)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
    if argv[:1] == ["repl"]:
        return repl()
    if argv[:1] == ["version"]:
        print(f"Sabline {VERSION}")
        return 0
    if argv[:1] == ["fmt"]:
        return fmt_main(argv[1:])
    if argv[:1] == ["lsp"]:
        return lsp_serve()
    # `sabline verify` alone is the older spelling of `deps --verify`; given a
    # file, it is the check of an attestation or a receipt (8.3)
    if argv[:1] == ["verify"] and any(not a.startswith("-") for a in argv[1:]):
        return verify_main(argv[1:])
    if argv[:1] in (["add"], ["deps"], ["verify"]):
        return packages(argv)
    if argv[:1] == ["proofs"]:
        target = argv[1] if len(argv) > 1 and not argv[1].startswith("-") \
            else "."
        files = []
        if os.path.isdir(target):
            files = _vel_files_under(target)
        elif os.path.exists(target):
            files = [target]
        if not files:
            print(f"no .vel files under '{target}'", file=sys.stderr)
            return 1
        rows, totals = [], {"proven": 0, "runtime": 0, "plain": 0,
                            "errors": 0}
        reports = {}
        for path in files:
            rep_ = inspect_source(path)
            reports[path] = rep_
            own = [f for f in rep_["functions"]
                   if os.path.abspath(f["file"]) == os.path.abspath(path)]
            counts = {"proven": 0, "runtime": 0, "plain": 0}
            for f in own:
                if f["status"] == "proven":
                    counts["proven"] += 1
                elif f["status"] == "checked at runtime":
                    counts["runtime"] += 1
                else:
                    counts["plain"] += 1
            for k in counts:
                totals[k] += counts[k]
            totals["errors"] += len(rep_["errors"])
            rows.append({"file": path, **counts,
                         "errors": len(rep_["errors"])})
        promising = totals["proven"] + totals["runtime"]
        share = (100.0 * totals["proven"] / promising) if promising else 0.0
        if "--sarif" in argv:
            want = (float(argv[argv.index("--min") + 1])
                    if "--min" in argv else None)
            sarif = sarif_proofs(reports, totals, share, want)
            print(json.dumps(sarif, indent=2))
            print_sarif_summary(sarif)
        elif "--json" in argv:
            print(json.dumps({"files": rows, "totals": totals,
                              "proven_share": round(share, 1)}, indent=2))
        elif "--detail" in argv:
            print(f"{len(files)} file(s)")
            print("-" * 62)
            for path in files:
                rep_ = reports[path]      # already inspected once
                own = [f for f in rep_["functions"]
                       if os.path.abspath(f["file"])
                       == os.path.abspath(path)
                       and (f["requires"] or f["ensures"])]
                if not own:
                    continue
                print(path)
                for f in own:
                    mark = ("proven " if f["status"] == "proven"
                            else "timeout" if f.get("proof_timeout")
                            else "runtime")
                    print(f"    [{mark}] {f['name']}")
                    if f["status"] != "proven":
                        for r in f["requires"]:
                            print(f"                needs    {r}")
                        for ens in f["ensures"]:
                            print(f"                promises {ens}")
            print("-" * 62)
            print(f"{totals['proven']} of {promising} proven "
                  f"({share:.0f}%)")
        else:
            print(f"{len(files)} file(s)")
            print("-" * 62)
            for r in rows:
                if not (r["proven"] or r["runtime"] or r["errors"]):
                    continue
                mark = "!" if r["errors"] else " "
                print(f"{mark} {r['file']}")
                bits = []
                if r["proven"]:
                    bits.append(f"{r['proven']} proven")
                if r["runtime"]:
                    bits.append(f"{r['runtime']} checked while running")
                if r["errors"]:
                    bits.append(f"{r['errors']} problem(s)")
                print("    " + ", ".join(bits))
            print("-" * 62)
            print(f"{totals['proven']} of {promising} promise-carrying "
                  f"function(s) proven before running "
                  f"({share:.0f}%)")
            if totals["plain"]:
                print(f"{totals['plain']} function(s) make no promises")
            if totals["errors"]:
                print(f"{totals['errors']} problem(s) found")
        if "--min" in argv:
            want = float(argv[argv.index("--min") + 1])
            if share < want:
                print(f"\nproven share {share:.0f}% is below the "
                      f"required {want:.0f}%", file=sys.stderr)
                return 1
        return 1 if totals["errors"] else 0
    if argv[:1] == ["serve"]:
        return serve_main(argv[1:])
    if argv[:1] == ["capabilities"]:
        return capabilities_main(argv[1:])
    if argv[:1] == ["review"]:
        return review_main(argv[1:])
    if argv[:1] == ["deps-diff"]:
        return deps_diff_main(argv[1:])
    if argv[:1] == ["permissions-ratchet"]:
        return permissions_main(argv[1:])
    if argv[:1] == ["conformance"]:
        return conformance_main(argv[1:])
    if argv[:1] == ["attest"]:
        return attest_main(argv[1:])
    if argv[:1] == ["eval"]:
        return eval_main(argv[1:], program_words)
    if argv[:1] == ["receipts"]:
        if argv[1:2] == ["show"]:          # the same page, either spelling
            return receipt_main(argv[1:])
        return receipts_main(argv[1:])
    if argv[:1] == ["receipt"]:
        return receipt_main(argv[1:])
    if argv[:1] == ["demo"]:
        return demo_main(argv[1:])
    if argv[:1] == ["skill"]:
        return skill_main(argv[1:])
    if argv[:1] == ["replay"]:
        return replay_main(argv[1:], program_words)
    if argv[:1] == ["eject"]:
        return eject_main(argv[1:])
    if argv[:1] == ["stats"]:
        return stats_main(argv[1:])
    if argv[:1] == ["mcp-manifest"]:
        return mcp_manifest_main(argv[1:])
    if argv[:1] == ["mcp-verify"]:
        return mcp_verify_main(argv[1:])

    if argv[:1] == ["mcp"]:
        # The same stdio server `python -m sabline_mcp` starts, reached
        # through the console script - so `sabline mcp`, and through the
        # npm wrapper `npx sabline-lang mcp`, start an MCP server without
        # the client having to know where the module sits. A thin alias
        # and nothing else: the flags, the tools, the ceilings and the
        # log are sabline_mcp's, parsed by sabline_mcp, and there is no
        # second set of them here.
        here = _INSTALL_DIR
        for where in (here, os.path.join(here, "..")):
            script = os.path.join(where, "sabline_mcp.py")
            if os.path.exists(script):
                sys.path.insert(0, where)
                import sabline_mcp
                return sabline_mcp.main(argv[1:])
        try:
            import sabline_mcp
            return sabline_mcp.main(argv[1:])
        except ImportError:
            print("the MCP server is not alongside this compiler; get it "
                  "from https://github.com/gowrishankar-infra/sabline-lang",
                  file=sys.stderr)
            return 1

    if argv[:1] == ["mcp-install"]:
        here = _INSTALL_DIR
        for where in (here, os.path.join(here, "..")):
            script = os.path.join(where, "sabline_mcp_install.py")
            if os.path.exists(script):
                sys.path.insert(0, where)
                import sabline_mcp_install
                return sabline_mcp_install.main(argv[1:])
        try:
            import sabline_mcp_install
            return sabline_mcp_install.main(argv[1:])
        except ImportError:
            print("the installer is not alongside this compiler; get it "
                  "from https://github.com/gowrishankar-infra/sabline-lang",
                  file=sys.stderr)
            return 1

    if argv[:1] == ["card"]:
        here = _INSTALL_DIR
        for where in (os.path.join(here, "LLM.md"),
                      os.path.join(here, "..", "LLM.md")):
            if os.path.exists(where):
                sys.stdout.write(open(where, encoding="utf-8").read())
                return 0
        print("LLM.md is not installed alongside the compiler; read it at "
              "https://github.com/gowrishankar-infra/sabline-lang/blob/"
              "main/LLM.md", file=sys.stderr)
        return 1

    if argv[:1] == ["audit"]:
        if "--sarif" in argv:
            # one or more files or folders, as `proofs` takes them
            files = []
            for target in [a for a in argv[1:]
                           if not a.startswith("-")] or ["."]:
                if os.path.isdir(target):
                    files += _vel_files_under(target)
                elif os.path.exists(target):
                    files.append(target)
                else:
                    print(f"no such file: {target}", file=sys.stderr)
                    return 1
            strict = "--strict" in argv
            reasons: tuple[str, ...] | list[str] = ()
            rf = _flag_value(argv, "--allow-declassify-reasons")
            if rf is not None:
                try:
                    reasons = [ln.strip() for ln in
                               open(rf, encoding="utf-8").read().splitlines()
                               if ln.strip() and not ln.startswith("#")]
                except OSError as e:
                    print(f"cannot read --allow-declassify-reasons {rf}: {e}",
                          file=sys.stderr)
                    return 2
            sarif = sarif_audit(files, strict=strict, allow_reasons=reasons)
            print(json.dumps(sarif, indent=2))
            print_sarif_summary(sarif)
            results = sarif["runs"][0]["results"]
            bad: int = any(not a["ok"] for a in
                      sarif["runs"][0]["properties"]["audits"]) or \
                any(r["level"] == "error" for r in results)
            return 1 if bad else 0
        if len(argv) < 2:
            print("usage: sabline audit program.vel", file=sys.stderr)
            return 1
        target = argv[1]
        if not os.path.exists(target):
            print(f"no such file: {target}", file=sys.stderr)
            return 1
        report = inspect_source(target)
        own = [f for f in report["functions"]
               if os.path.abspath(f["file"]) == os.path.abspath(target)]
        outside = sorted({e for f in own for e in f["effects"]})
        promises = [f for f in own if f["requires"] or f["ensures"]]
        proven_fns = [f for f in promises if f["status"] == "proven"]
        runtime = [f for f in promises if f["status"] != "proven"]
        reaching = [f for f in own if f["effects"]]
        fallible = [f for f in own if f["can_fail"]]
        unshown = [f for f in own if f.get("loops_unshown")]
        inline_unshown = [lp for lp in report.get("inline_loops", [])
                          if lp["verdict"] == "unshown"
                          and os.path.abspath(lp["file"])
                          == os.path.abspath(target)]
        coverage = contract_coverage(own, report.get("records", []))

        if "--json" in argv:
            # sabline.audit/1, the same document the library, the MCP
            # server, the HTTP door, the npm package, the CrewAI tool and
            # the Action all emit - so a consumer meets one shape from
            # every door (spec Q3, resolved in 3.3). Before 3.3 this
            # printed an older, unversioned summary the schema rejected.
            result = _audit_here(open(target, encoding="utf-8").read(),
                           path=target)
            print(json.dumps(result.as_dict(), indent=2))
            return 0 if result.ok else 1
        if "--html" in argv:
            # the same document as a page (8.5): -o FILE, or standard output
            result = _audit_here(open(target, encoding="utf-8").read(),
                                 path=target)
            try:
                out_to = _flag_value(argv, "-o")
            except BudgetError as e:
                print(str(e), file=sys.stderr)
                return 2
            wrote = write_page(audit_html(result.as_dict(),
                                          target.replace(os.sep, "/")),
                               out_to, "sabline audit --html")
            return wrote or (0 if result.ok else 1)

        print(f"AUDIT  {target}")
        print("=" * 62)
        if report["errors"]:
            print(f"This does not compile ({len(report['errors'])} "
                  f"problem(s)). Do not run it.")
            for err in report["errors"][:5]:
                print(f"  line {err['line']}: [{err['code']}] {err['message']}")
            return 1

        print("WHAT IT CAN TOUCH")
        if not outside:
            print("  nothing. This program cannot reach the console, the")
            print("  disk, the network, the clock, randomness or Python,")
            print("  and it cannot let a secret out.")
        else:
            for eff in outside:
                print(f"  {eff:<10} {_EFFECT_WORDS.get(eff, eff)}")
            print()
            print("  reached by:")
            for f in reaching:
                print(f"    {f['name']} ({', '.join(sorted(f['effects']))})")
        print()

        print("WHAT IT PROMISES")
        if not promises:
            print("  nothing. No function here carries a contract.")
        else:
            for f in proven_fns:
                print(f"  [proven ] {f['name']}")
                for ens in f["ensures"]:
                    print(f"              always: {ens}")
            for f in runtime:
                print(f"  [runtime] {f['name']}")
                for ens in f["ensures"]:
                    print(f"              claims: {ens}")
            share = 100 * len(proven_fns) / len(promises)
            print()
            print(f"  {len(proven_fns)} of {len(promises)} proven before "
                  f"running ({share:.0f}%); the rest are checked while "
                  f"it runs.")
        print()

        if fallible:
            print("WHAT CAN FAIL")
            for f in fallible:
                print(f"  {f['name']}")
            print()

        if unshown or inline_unshown:
            print("WHAT MIGHT NOT END")
            for f in unshown:
                for lp in f["loops"]:
                    if lp["verdict"] == "unshown":
                        print(f"  {f['name']}, line {lp['line']}: "
                              f"{lp['why']}")
            for lp in inline_unshown:
                print(f"  an inline function, line {lp['line']}: "
                      f"{lp['why']}")
            print("  (a loop counts as ending only when a counter moves")
            print("  one step toward an unchanging limit; --strict makes")
            print("  this E612)")
            print()

        secrets = _secrets_named(target, None)
        if secrets and (secrets["sources"] or secrets["declassifies"]):
            print("WHAT IT KEEPS SECRET")
            if secrets["sources"]:
                print("  these hand it values the compiler will not let "
                      "it print,")
                print("  write, send or pass to Python:")
                for s in secrets["sources"]:
                    print(f"    {s}()")
            if not secrets["declassifies"]:
                print("  it never declassifies: no secret leaves this "
                      "program.")
            else:
                print("  it declassifies, which is how a secret becomes "
                      "an ordinary")
                print("  value anything may emit:")
                for d in secrets["declassifications"]:
                    print(f"    {d['function']}, line {d['line']}: "
                          f"{d['reason']}")
                print("  refuse the 'declassify' grant and none of these "
                      "happen.")
            print()

        if coverage:
            print("PROMISES NOTHING ABOUT THE DATA IT HANDLES")
            print("  these functions transform data and promise nothing:")
            for name in coverage:
                print(f"    {name}")
            print("  (a coverage note, not a defect)")
            print()

        print("HOW TO RUN IT SAFELY")
        grants = ",".join(outside)
        if grants:
            print(f"  sabline {target} --allow {grants}")
            print("  Anything it did not declare is refused while it runs.")
        else:
            print(f"  sabline {target} --allow ''")
            print("  It needs no permissions at all.")
        if "ffi" in outside:
            print()
            print("  NOTE: this program calls Python, which means it can")
            print("  do anything Python can. An effect budget does not")
            print("  contain that. Read the code before running it.")
            modules = sorted(_ffi_modules_named(target, None))
            if modules:
                native = _ffi_native(modules)
                say = [f"{m} ({native[m]})" for m in modules]
                print(f"  modules named: {', '.join(say)}")
                if any(v == "native" for v in native.values()):
                    print("  native code (a compiled extension) ships with "
                          "one of these;")
                    print("  there is no source to read.")
        if "net" in outside:
            # a net grant bounds the URL's host and, from 8.0, the socket's
            # peer; an ambient proxy that the run does not also grant is
            # refused (E317). Say whether one is set in this environment.
            proxies = sorted(v for k, v in
                             (("HTTP_PROXY", os.environ.get("HTTP_PROXY")
                               or os.environ.get("http_proxy")),
                              ("HTTPS_PROXY", os.environ.get("HTTPS_PROXY")
                               or os.environ.get("https_proxy"))) if v)
            if proxies:
                print()
                print(f"  NOTE: an ambient proxy is set ({', '.join(proxies)}).")
                print("  From 8.0 a request through it is refused (E317) "
                      "unless the")
                print("  proxy's host is itself in the net grants.")
        # what the operating system would hold of that run, here (8.4):
        # judged for the modules the program names, as the library's audit
        # judges it, not for the plain ffi the line above prints
        reached = sorted(_ffi_modules_named(target, None)) \
            if "ffi" in outside else []
        judged = ",".join(g for g in outside if g != "ffi" or not reached)
        if reached:
            judged = ",".join(filter(None, [judged] + [
                f"ffi:{m}" for m in reached]))
        try:
            policy = _confine.os_policy(Budget.parse(judged))
        except BudgetError:
            policy = None
        if policy is not None:
            would = _confine.predict(policy)
            print()
            print(f"CONFINEMENT ON THIS MACHINE: {would['level']}")
            for w in policy["widened_by"]:
                named = "plain ffi" if w["module"] == "*" \
                    else f"ffi:{w['module']}"
                to = ("nothing enforced" if "all" in w["widens"] else
                      " and ".join({"fs": "any path", "net": "any host"}[x]
                                   for x in w["widens"]))
                print(f"  {named} widens the OS policy to {to}"
                      + ("" if w.get("known", True) else
                         " (it is not in the table of modules)"))
            if would["level"] != _confine.FULL:
                print(f"  {would['reason']}")
        return 0

    if argv[:1] == ["clean"]:
        # it deleted the proof cache, 2.29 to 8.1.1; 8.2 keeps none, and the
        # command stays, doing nothing, until 9.0 (STABILITY.md rule 2)
        print("sabline clean: deprecated, and does nothing - Sabline keeps "
              "no proofs from 8.2, so there is nothing to clean. A "
              "'sabline' folder an earlier version left in your user cache "
              "directory can be deleted by hand. The command is removed in "
              "9.0.", file=sys.stderr)
        return 0
    if argv[:1] == ["build"]:
        return build_program(argv[1:])
    if argv[:1] == ["trace"]:
        if len(argv) < 2:
            print("usage: sabline trace program.vel", file=sys.stderr)
            return 1
        _state.TRACE["on"] = True
        # run it normally, the program's words after -- still its own
        sys.argv = [sys.argv[0]] + argv[1:] + (
            ["--"] + program_words if program_words else [])
        return main()
    if argv[:1] == ["test"]:
        if "--from-contracts" in argv:
            return from_contracts_main(argv[1:])
        if len(argv) < 2:
            print("usage: sabline test program.vel", file=sys.stderr)
            return 1
        target = argv[1]
        # a test function performs effects like any other, so it runs
        # under a budget: io unless --allow says more (5.0)
        try:
            cli_budget(argv).install()
        except BudgetError as e:
            print(str(e), file=sys.stderr)
            return 2
        try:
            funcs, records = load_program(target)
            errs: list[Any] = []
            check_effects(funcs, errs)
            check_types(funcs, records, errs)
            if not errs:
                check_proofs(funcs, records, errs)
            if errs:
                for err in errs:
                    print(err.human(target), file=sys.stderr)
                return 1
        except SablineError as e:
            print(e.human(target), file=sys.stderr)
            return 1
        tests = [f for f in funcs
                 if f.name.startswith("test_") and not f.params
                 and f.src_file == target]
        if not tests:
            print(f"no tests in {target} - name a function test_something "
                  f"and return true when it passes")
            return 1
        native = {} if "--no-native" in argv else compile_native(funcs)
        rt = build_runtime(funcs, native)
        passed = 0
        for t in tests:
            label = t.name[len("test_"):].replace("_", " ")
            try:
                got = rt["call"](t.name, [], t.line)
                if got is True:
                    print(f"  PASS  {label}")
                    passed += 1
                else:
                    print(f"  FAIL  {label}   (returned {to_text(got)})")
            except SablineError as e:
                print(f"  FAIL  {label}   [{e.code}] {e.message}")
            except FailSignal as e:
                print(f"  FAIL  {label}   failed: {e.reason}")
        print(f"\n{passed}/{len(tests)} passed")
        return 0 if passed == len(tests) else 1
    if argv[:1] == ["check"]:
        if len(argv) < 2:
            print("usage: sabline check program.vel", file=sys.stderr)
            return 1
        bad = 0
        strict = "--strict" in argv
        if "--sarif" in argv:
            # SARIF on stdout, for code scanning; the findings one line
            # each on stderr, so a CI log still says what was found
            sarif, code = sarif_check(
                [a for a in argv[1:] if not a.startswith("-")], strict)
            print(json.dumps(sarif, indent=2))
            print_sarif_summary(sarif)
            return code
        for target in [a for a in argv[1:] if not a.startswith("-")]:
            rep_ = inspect_source(target)
            if rep_["errors"]:
                bad += 1
                if "--json" in argv:
                    print(json.dumps(rep_["errors"], indent=2))
                else:
                    for err in rep_["errors"]:
                        print(f"{target}:{err['line']}: [{err['code']}] "
                              f"{err['message']}", file=sys.stderr)
            else:
                own = [f for f in rep_["functions"]
                       if os.path.abspath(f["file"])
                       == os.path.abspath(target)]
                proven = sum(1 for f in own if f["status"] == "proven")
                # --strict: "it compiled" should mean "every promise it
                # makes was proven", not "proven or hoped for". Without
                # the flag an unprovable promise degrades to a runtime
                # check, which keeps the language usable with no solver
                # installed - but that is a choice about the DEFAULT,
                # and someone who wants the stronger reading should be
                # able to ask for it.
                if strict:
                    if not rep_["proofs"]:
                        bad += 1
                        print(f"{target}: --strict needs the prover "
                              f"(pip install z3-solver)", file=sys.stderr)
                        continue
                    fell_back = [f for f in own
                                 if (f["requires"] or f["ensures"])
                                 and f["status"] != "proven"]
                    if fell_back:
                        bad += 1
                        print(f"{target}: {len(fell_back)} promise(s) "
                              f"could not be proven, and --strict does "
                              f"not accept runtime checks:",
                              file=sys.stderr)
                        for f in fell_back:
                            why = ("  (the proof ran out of time - it "
                                   "was abandoned, not settled)"
                                   if f.get("proof_timeout") else "")
                            print(f"  {f['name']}{why}", file=sys.stderr)
                            for ens in f["ensures"]:
                                print(f"      promises {ens}",
                                      file=sys.stderr)
                            for r in f["requires"]:
                                print(f"      needs    {r}",
                                      file=sys.stderr)
                        print("  either simplify them until they prove, "
                              "or drop --strict and accept the runtime "
                              "check", file=sys.stderr)
                        continue
                    # a loop whose end cannot be shown is E612 here and
                    # nowhere else: without --strict it is not an error
                    unshown = [(f["name"], lp) for f in own
                               for lp in f.get("loops", [])
                               if lp["verdict"] == "unshown"]
                    unshown += [("an inline function", lp)
                                for lp in rep_.get("inline_loops", [])
                                if lp["verdict"] == "unshown"
                                and os.path.abspath(lp["file"])
                                == os.path.abspath(target)]
                    if unshown:
                        bad += 1
                        if "--json" in argv:
                            print(json.dumps([{
                                "code": "E612",
                                "message": "this loop may never end - "
                                           "--strict needs a counter that "
                                           "moves toward the limit",
                                "file": target, "line": lp["line"],
                                "fixes": [lp["why"]]}
                                for _, lp in unshown], indent=2))
                        else:
                            for fname, lp in unshown:
                                print(f"{target}:{lp['line']}: [E612] "
                                      f"this loop may never end - --strict "
                                      f"needs a counter that moves toward "
                                      f"the limit ({fname}: {lp['why']})",
                                      file=sys.stderr)
                        continue
                if "--json" not in argv:
                    note = ("" if rep_["proofs"]
                            else "  (no z3: runtime checks)")
                    if strict:
                        note = "  (--strict: every promise proven)"
                    # "ok" here would read as "the prover looked and
                    # found nothing wrong", which is the one thing a
                    # clock running out is not
                    late = rep_.get("proof_timeouts") or []
                    if late:
                        note = (f"  ({len(late)} proof(s) abandoned: "
                                f"out of time, nothing settled)")
                    print(f"{target}: ok - {len(own)} function(s), "
                          f"{proven} with proven promises{note}")
        return 1 if bad else 0
    if argv[:1] == ["explain"]:
        if len(argv) < 2:
            print("usage: sabline explain program.vel", file=sys.stderr)
            return 1
        target = argv[1]
        if os.path.isdir(target):
            vels = sorted(
                os.path.join(dp, f)
                for dp, _, fns in os.walk(target) for f in fns
                if f.endswith(".vel"))
            if not vels:
                print(f"no .vel files under '{target}'", file=sys.stderr)
                return 1
            print(f"{len(vels)} file(s) under {target}")
            print("=" * 62)
            worst = 0
            for v in vels:
                r = inspect_source(v)
                own = [f for f in r["functions"]
                       if os.path.abspath(f["file"]) == os.path.abspath(v)]
                proven = sum(1 for f in own if f["status"] == "proven")
                effs = sorted({e for f in own for e in f["effects"]})
                mark = "!" if r["errors"] else " "
                print(f"{mark} {v}")
                print(f"    {len(own)} function(s), {proven} proven"
                      f"   performs: "
                      f"{', '.join(effs) if effs else 'nothing'}")
                for err in r["errors"]:
                    worst = 1
                    print(f"    line {err['line']}: [{err['code']}] "
                          f"{err['message'][:70]}")
            return worst
        rep_ = inspect_source(target)
        if "--json" in argv:
            print(json.dumps(rep_, indent=2))
            return 0 if not rep_["errors"] else 1
        print(f"{rep_['file']}  -  sabline {rep_['version']}")
        print("=" * 62)
        if not rep_["proofs"]:
            print("note: z3-solver is not installed, so promises are "
                  "checked while running\n")
        entry = os.path.abspath(rep_["file"])
        mine: list[Any] = []
        imported: dict[str, list[Any]] = {}
        for f in rep_["functions"]:
            if os.path.abspath(f["file"]) == entry:
                mine.append(f)
            else:
                imported.setdefault(f["file"], []).append(f)

        def show(f: Any) -> None:
            ps = ", ".join(f"{p['name']}: {p['type']}" for p in f["params"])
            print(f"\nfn {f['name']}({ps}) -> {f['returns']}")
            print(f"  line {f['line']}   [{f['status']}]")
            if f["effects"]:
                print(f"  may perform: {', '.join(f['effects'])}")
            else:
                print("  may perform: nothing (pure)")
            if f["can_fail"]:
                print("  can fail: callers must handle it")
            for r in f["requires"]:
                print(f"  needs:    {r}")
            for e in f["ensures"]:
                print(f"  promises: {e}")
            loops = f.get("loops") or []
            if loops:
                ends = sum(1 for lp in loops if lp["verdict"] == "terminates")
                print(f"  loops: {ends} terminate, "
                      f"{len(loops) - ends} not shown")
                for lp in loops:
                    if lp["verdict"] == "unshown":
                        print(f"    line {lp['line']}: {lp['why']}")

        for f in mine:
            show(f)
        if not mine:
            print("\n(no functions in this file)")
        show_all = "--all" in argv
        for path, fs in imported.items():
            print(f"\n{'-' * 62}")
            if show_all:
                print(f"imported from {path}")
                for f in fs:
                    show(f)
                continue
            proven = sum(1 for f in fs if f["status"] == "proven")
            effs = sorted({e for f in fs for e in f["effects"]})
            print(f"imported from {path}: {len(fs)} function(s), "
                  f"{proven} with proven promises")
            print(f"  performs: {', '.join(effs) if effs else 'nothing'}"
                  f"   (see them with --all)")
        if rep_["errors"]:
            print("\n" + "=" * 62)
            print(f"{len(rep_['errors'])} problem(s):")
            for err in rep_["errors"]:
                print(f"  line {err['line']}: [{err['code']}] {err['message']}")
            return 1
        print("\n" + "=" * 62)
        n_imp = sum(len(v) for v in imported.values())
        print(f"{len(mine)} function(s) in this file"
              + (f", {n_imp} imported" if n_imp else "")
              + ", no problems found.")
        return 0
    if argv[:1] == ["migrate"]:
        return migrate_main(argv[1:])
    if argv[:1] == ["doctor"]:
        return doctor()
    if argv[:1] == ["new"]:
        return new_project(argv[1] if len(argv) > 1 else "")
    if argv[:1] == ["run"]:
        sys.argv.pop(1)
    if "--version" in sys.argv:
        print(f"Sabline {VERSION}")
        return 0
    if len(sys.argv) < 2:
        # the docstring carries no version of its own, so this cannot go
        # stale: until 4.4 it opened "Sabline v2.36", which is what a
        # reader of `sabline` with no arguments was told they were running
        print((__doc__ or "").replace("Sabline —", f"Sabline {VERSION} —",
                                      1))
        return 1
    filename = sys.argv[1]
    as_json = "--json" in sys.argv
    # A budget is always installed, and without --allow it is io (5.0).
    # Before 5.0 this whole block was skipped when neither flag was
    # given, and the run kept the module-level budget - all seven
    # effects. --deny now narrows whatever --allow gave, which with no
    # --allow is io, so no flag combination gets back to everything
    # except by asking for it: --allow all.
    try:
        budget = cli_budget(sys.argv)
    except BudgetError as e:
        print(str(e), file=sys.stderr)
        return 2
    budget.install()
    # From 8.4 the operating system is asked to hold the same budget, at the
    # program's first statement (sabline/confine.py). --no-confine does not
    # ask, and says so; it is a flag of this command line, before any `--`,
    # and nothing a program can reach.
    if "--no-confine" in sys.argv:
        vars(_state)["CONFINE"] = False
        print("sabline: --no-confine: the operating system is not asked to "
              "hold this run; the budget is the only boundary",
              file=sys.stderr)
    vars(_state)["BEFORE_FIRST_STATEMENT"] = lambda: _confine.confine_this_run(
        budget, files=list(_state.PROGRAM_FILES))
    # args() is the program's arguments - never the flags this command
    # took for itself. Until 2.62 `--allow io` leaked in as two words.
    FLAGS = {"--json", "--no-native", "--time", "--check", "--no-confine"}
    VALUED = {"--allow", "--deny", "--timeout", "--max-memory-mb",
              "--max-read", "--seed", "--freeze-time", "--receipt",
              "--record-responses", "--tools", "--tool-timeout"}
    rest, skip = [], False
    for a in sys.argv[2:]:
        if skip:
            skip = False
        elif a in VALUED:
            skip = True
        elif a not in FLAGS:
            rest.append(a)
    _state.PROGRAM_ARGS[:] = rest + program_words
    if "--tools" in sys.argv:
        # the runner (8.5): the host process that started this run offers it
        # tools, over this process's standard input and output
        return _cli_run_with_tools(filename, as_json, budget)
    if "--record-responses" in sys.argv:
        # code mode (8.3): what each py, py_int, py_float and py_json call
        # gave back, in order, written when the run ends - for sabline replay
        try:
            record_to = cast(str, _flag_value(sys.argv, "--record-responses"))
        except BudgetError as e:
            print(str(e), file=sys.stderr)
            return 2
        log = ResponseLog()
        vars(_state)["RESPONSES"] = log
        # opened now: a confined run cannot open it once it has ended
        record_fh = _open_for_later(record_to)
        try:
            return _cli_run_receipt_or_not(filename, as_json, budget)
        finally:
            vars(_state)["RESPONSES"] = None
            try:
                _write_later(record_fh, record_to,
                             json.dumps(log.document(), indent=2,
                                        ensure_ascii=False) + "\n")
            except OSError as e:
                print(f"sabline: the responses could not be written to "
                      f"{record_to}: {e.strerror or e}", file=sys.stderr)
    return _cli_run_receipt_or_not(filename, as_json, budget)


def _cli_run_with_tools(filename: str, as_json: bool,
                        budget: "Budget") -> int:
    """`sabline run file.vel --tools MANIFEST` (8.5). The manifest is read
    and the door opened before the program is: a manifest that is not one
    is exit 2 and nothing runs. From there standard output carries the
    door's events and nothing else - `ready`, the program's `output`, each
    `call`, and `exit` last, whatever ended the run."""
    from .tools import (TOOL_TIMEOUT_DEFAULT, TOOLS_PROTOCOL, ManifestError,
                        open_session)
    try:
        manifest_path = cast(str, _flag_value(sys.argv, "--tools"))
        wait = _flag_value(sys.argv, "--tool-timeout")
    except BudgetError as e:
        print(str(e), file=sys.stderr)
        return 2
    timeout = float(TOOL_TIMEOUT_DEFAULT)
    if wait is not None:
        if not _ascii_digits(wait) or int(wait) < 1:
            print("--tool-timeout needs a whole number of seconds, as "
                  "--tool-timeout 30", file=sys.stderr)
            return 2
        timeout = float(wait)
    real_out = sys.stdout
    try:
        session = open_session(manifest_path, timeout)
    except (OSError, ManifestError) as e:
        print(f"sabline: the tool manifest {manifest_path} cannot be used: "
              f"{getattr(e, 'strerror', None) or e}", file=sys.stderr)
        return 2
    vars(_state)["TOOL_SESSION"] = session
    session.send({"event": "ready", "protocol": TOOLS_PROTOCOL,
                  "sabline": VERSION, "budget": budget.spec(),
                  "tools": sorted(session.manifest["tools"])})
    status = 1
    try:
        try:
            status = _cli_run_receipt_or_not(filename, as_json, budget)
        except SystemExit as e:
            status = e.code if isinstance(e.code, int) else \
                (0 if e.code is None else 1)
        return status
    finally:
        try:
            sys.stdout.flush()
        except (OSError, ValueError):
            pass
        session.send({"event": "exit", "status": status,
                      **session.ceiling_record()})
        sys.stdout = real_out
        vars(_state)["TOOL_SESSION"] = None


def _open_for_later(path: str) -> Any:
    """A file opened for writing without emptying it, or None when it cannot
    be: what is there stays until _write_later replaces it."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT
                     | getattr(os, "O_BINARY", 0), 0o666)
    except OSError:
        return None
    return os.fdopen(fd, "wb")


def _write_later(fh: Any, path: str, text: str) -> None:
    """Replace the file's content with `text`. OSError as open() gives it
    when the file could not be opened then and cannot be now."""
    if fh is None:
        fh = open(path, "wb")
    with fh:
        fh.seek(0)
        fh.truncate()
        fh.write(text.encode("utf-8"))


def _cli_run_receipt_or_not(filename: str, as_json: bool,
                            budget: "Budget") -> int:
    if "--receipt" in sys.argv:
        try:
            receipt_to = _flag_value(sys.argv, "--receipt")
        except BudgetError as e:
            print(str(e), file=sys.stderr)
            return 2
        return _cli_run_with_receipt(filename, as_json, budget,
                                     cast(str, receipt_to))
    return _cli_run(filename, as_json)


def _cli_run_with_receipt(filename: str, as_json: bool, budget: "Budget",
                          receipt_to: str) -> int:
    """`sabline file.vel --receipt FILE` (8.1): the run, then its
    sabline.receipt/1 Statement written to FILE - whether it ended well,
    was refused, failed or called exit_with. The receipt is written once
    the program has finished, so nothing the program wrote to that path
    survives it. A receipt that cannot be written is said on stderr, and a
    run that was otherwise clean exits 2."""
    import posixpath
    import time as _t
    try:
        with open(filename, "rb") as fh:
            entry_bytes = fh.read()
    except OSError:
        entry_bytes = b""
    recorder = _RunRecorder()
    loaded: list[Any] = []
    started_at, t0 = _utc_now_ms(), _t.monotonic()
    status, raised = 1, None
    # opened now, written when the run has ended: a confined run cannot
    # open a file outside its budget then (8.4)
    receipt_fh = _open_for_later(receipt_to)
    vars(_state)["RUN_RECORDER"] = recorder
    try:
        status = _cli_run(filename, as_json, loaded=loaded)
    except SystemExit as e:
        raised = e
        status = e.code if isinstance(e.code, int) else \
            (0 if e.code is None else 1)
    finally:
        recorder.close()
        vars(_state)["RUN_RECORDER"] = None
    name = posixpath.normpath(filename.replace(os.sep, "/"))
    if loaded:
        recorder.subjects = _receipt_subjects(filename, name, entry_bytes,
                                              loaded)
    stop = recorder.stop or {}
    result = RunResult(status == 0 and not stop, "", "",
                       [Problem(stop["code"], "", stop.get("line"), filename,
                                [])] if stop else [],
                       None, status, effects_used=dict(_state.EFFECT_USES))
    doc = receipt_statement(
        recorder, name=name, entry_bytes=entry_bytes, budget=budget.spec(),
        parameters=_run_parameters(
            _state.SEED, _state.FROZEN_TIME, None, None,
            confinement=_confine.current() or _confine.unconfined(
                _confine.os_policy(budget, confine=_state.CONFINE),
                "the run stopped before its first statement, where the "
                "confinement is applied")),
        result=result, started_at=started_at,
        wall_time_ms=(_t.monotonic() - t0) * 1000)
    try:
        _write_later(receipt_fh, receipt_to,
                     json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"sabline: the receipt could not be written to {receipt_to}: "
              f"{e.strerror or e}", file=sys.stderr)
        if raised is None and status == 0:
            status = 2
    if raised is not None:
        raise raised
    return status


def _cli_run(filename: str, as_json: bool, loaded: list[Any] | None = None) -> int:
    """`sabline file.vel`: compile, prove, and run, under the budget main()
    installed. `loaded` gets the files read, for a receipt."""
    running = False
    if loaded is None:
        loaded = []
    try:
        funcs, records = load_program(filename, loaded=loaded)
        _state.PROGRAM_FILES[:] = [filename] + [str(p) for p in loaded]
        errors: list[SablineError] = []
        check_effects(funcs, errors)  # superpower 1: no hidden effects
        check_types(funcs, records, errors)  # superpower 2: no type surprises
        proven: set[Any] = set()
        if not errors:                # proofs assume well-formed code
            check_proofs(funcs, records, errors, proven)
        if errors:
            seen_err, unique = set(), []
            for e in errors:            # two checkers can spot one problem
                key = (e.code, e.file or filename, e.line, e.message)
                if key not in seen_err:
                    seen_err.add(key)
                    unique.append(e)
            errors[:] = unique
            errors.sort(key=lambda e: (e.file or filename, e.line))
            if as_json:
                print(json.dumps(
                    [json.loads(e.machine(filename)) for e in errors],
                    indent=2), file=sys.stderr)
            else:
                print("\n\n".join(e.human(filename) for e in errors),
                      file=sys.stderr)
                if len(errors) > 1:
                    print(f"\nfound {len(errors)} problems", file=sys.stderr)
            _note_stop(errors[0].code, errors[0].line)
            return 1
        native = ({} if "--no-native" in sys.argv
                  else compile_native(funcs, proven))
        if _state.RUN_RECORDER is not None:
            _state.RUN_RECORDER.compiled = True
        import time as _t
        t0 = _t.perf_counter()
        running = True
        interpret(funcs, native)
        if "--time" in sys.argv:
            ms = (_t.perf_counter() - t0) * 1000
            mode = "interpreted" if not native else "native+interpreted"
            print(f"[--time] ran in {ms:.1f} ms ({mode})", file=sys.stderr)
        return 0
    except SablineError as e:
        _note_error(e)
        print(e.machine(filename) if as_json else e.human(filename), file=sys.stderr)
        return 1
    except RecursionError:
        # nested, or built, past Python's own recursion limit: a coded error,
        # not a traceback (8.2, check_hostile.py)
        from .errors import _too_deep_error
        err = _too_deep_error(running)
        _note_error(err)
        print(err.machine(filename) if as_json else err.human(filename), file=sys.stderr)
        return 1
