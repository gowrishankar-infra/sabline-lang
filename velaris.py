#!/usr/bin/env python3
"""
Velaris — "The language where you can trust code you didn't write."

New in v2.36: examples/linkcheck.vel - a tool worth running, not a
    demonstration - and network failures that say what happened
    instead of quoting the implementation.

New in v2.2: out-of-the-box readiness.
    velaris doctor          check your setup, with exact fixes
    velaris new myproject   start a project with running code
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
    sixteen functions written in Velaris - including sort, which
    ensures is_sorted(result) using is_sorted, also from the library.
    Violating a library requires is a compile error at your call site.

New in v1.18: FLOAT PROOFS - real IEEE-754, not pretend-math.
    Promises about Float values are proven in Z3's floating-point
    theory, bit-for-bit the arithmetic your machine performs. The
    prover will happily refute x + 0.1 + 0.1 == x + 0.2, because in
    floating point it is false - and Velaris does not pretend.

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
    tracker written in Velaris (records, contracts, or-fail parsing,
    file persistence). Two supporting builtins: chars(text) splits Text
    into single characters (pure), and file_exists(path) checks before
    reading (fs).

New in v1.12: continuous integration + repo hygiene.
    Every push is tested by GitHub Actions on Linux and Windows,
    Python 3.10 and 3.12, WITH and WITHOUT the optional dependencies -
    plus formatter and playground checks. CHANGELOG.md tells the story.

New in v1.11: a LANGUAGE SERVER - errors as you type, in any LSP editor.
    velaris lsp
    Fast checks (effects + types) on every keystroke; the full pipeline
    including Z3 proofs on save. The VS Code extension in editor/vscode
    now launches it automatically (no extra dependencies).

New in v1.10: a formatter - one canonical style for every .vel file.
    velaris fmt program.vel            rewrite in place (if needed)
    velaris fmt program.vel --stdout   print instead of writing
    velaris fmt program.vel --check    exit 1 if not formatted (for CI)

New in v1.9: a REPL - try Velaris line by line.
    velaris repl
    Loose lines run immediately (checked while running); fn / record /
    import definitions get the FULL treatment - effects, types, and
    Z3 proofs - before they are accepted into the session.

New in v1.8: a real install.
    pip install .          (from a clone; add [full] for proofs + native)
    velaris program.vel    (the command, anywhere; it gets io - 5.0)
    import "std.vel" now finds the shipped standard library from any
    folder - imports check relative-to-your-file first, then stdlib.

New in v1.7: GENERICS - one function, every type.
    fn first(xs: List of T) -> T for any T
        requires length(xs) > 0
    { return get(xs, 0) }
    T is inferred at each call; conflicting uses are clear errors.
    Plus: examples/std.vel - the first standard library, written in
    Velaris itself.

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
    Velaris with zero install (rebuild it with: python build_playground.py).

New in v1.1: escape sequences in text - \n newline, \t tab, \" quote,
    \\ backslash - plus a VS Code syntax highlighter in editor/vscode.
New in v1.0: the testers' release.
    * Multiple problems are reported in one run (one per function),
      instead of stopping at the first.
    * to_text(x) turns any value into Text.
    * --version prints the version.

Usage:
  velaris program.vel                      run a program (after pip install);
                                           it gets io - print and read_line -
                                           and every other effect is refused
  velaris repl                             interactive session
  velaris <file> --allow io,fs:read:./data grant exactly this, nothing else
  velaris <file> --allow all               every effect; says so on stderr
  velaris <file> --allow all --deny net    every effect but these
  velaris migrate --to 5.0 [path]          the budget each program needs, and
        [--write]                          the command to run it under 5.0
  velaris fmt program.vel                  format to the canonical style
  velaris check program.vel                compile only, do not run
  velaris check f.vel --strict             refuse any promise left to runtime
  velaris check f.vel --sarif              findings as SARIF 2.1.0 on stdout
  velaris proofs [path] [--min 80]         how much is proven, not just checked
  velaris proofs . --detail                which functions, one by one
  velaris proofs . --sarif                 promises left to runtime, as SARIF
  velaris <any command> --proof-timeout S  how long one proof may take
                                           (default: 120 s with Float, 3 s
                                           without; a proof that runs out
                                           says it was abandoned)
  velaris clean                            forget remembered proofs
  velaris test program.vel                 run every test_ function
  velaris trace program.vel                show every call as it happens
  velaris explain program.vel              walk through what it does
  velaris audit program.vel                what it can touch, before you run it
  velaris audit <files or folders> --sarif what they can touch, as SARIF
  velaris card                             the language, for pasting into a model
  velaris mcp [--max-allow G]              the MCP server on stdin/stdout,
        [--max-timeout S]                  the same one python -m velaris_mcp
        [--max-memory-mb M]                starts; grants at most io, 30 s and
        [--log-file F] [--log minimal]     512 MB a run unless told otherwise
  velaris mcp-install                      set up the tools in your assistant
  velaris mcp-manifest -o tools.json       the MCP server's tools, hashed
  velaris mcp-verify tools.json            a running server against a signed
                                           manifest (-- server command)
  velaris serve [--port 8787]              an HTTP door for any language,
        [--token-file F] [--max-allow G]   behind a bearer token; grants at
        [--max-timeout S]                  most io, 30 s and 512 MB a run
        [--max-memory-mb M]                unless the operator says more
        [--log-file F] [--log minimal]     one JSON line per call
  velaris capabilities init [path]         record the capability surface in
                                           velaris.capabilities (--force)
  velaris capabilities check [path]        fail if the surface widened past
                                           it (--json, --sarif)
  velaris review --against REF [path]      what changed since a git ref:
                                           surface, proofs, risk (--json)
  velaris deps-diff <package> OLD NEW      what a dependency's newer version
        [--json | --sarif]                 gained; <package> is pypi:NAME,
                                           npm:NAME, git:URL or dir:PATH
  velaris deps-diff --against REF [path]   the same for every upgrade in the
        [--comment --pr N]                 lockfiles changed since REF
  velaris conformance [--level 1|2|3]      run velaris-spec's conformance
        [--json] [--corpus DIR]            corpus against this Velaris
  velaris attest <path> [--output FILE]    the audit as an in-toto Statement,
        [--json]                           each file by its sha256 (unsigned)
  velaris explain <folder>                 a map of every file
  velaris doctor                           check the installation
  velaris new <name>                       start a fresh project
  velaris build program.vel [-o name]      one file anyone can run
  velaris add <url or path> [as name]      vendor a library into lib/
  velaris add <url> --force                replace one with different bytes
  velaris deps                             what this project depends on
  velaris deps --verify                    do the libraries match velaris.lock?
  velaris verify                           the same check, older spelling
  velaris lsp                              language server (for editors)
  velaris version                          print the version
  python velaris.py program.vel            run a program (it gets io)
  python velaris.py program.vel --json     errors as machine-readable JSON
  python velaris.py program.vel --time     show how long the run took
  python velaris.py program.vel --no-native  force the interpreter
  python velaris.py program.vel --max-memory-mb 512  stop it past that
  python velaris.py --version

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
    Velaris errors (E606), never tracebacks.

New in v0.10: LOOP INVARIANTS - the prover learned loops.
    while i <= n
        invariant total >= 0
    { ... }
    Velaris proves the invariant holds at loop entry, survives every step,
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
New in v0.5: contracts. Functions make promises; Velaris enforces them.
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
  python3 velaris.py program.vel          # run a program (it gets io)
  python3 velaris.py program.vel --json   # errors come out as JSON too
"""

import json
import os

VERSION = "7.2.0"
import re
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. LEXER — turn raw text into a list of tokens
# ---------------------------------------------------------------------------

KEYWORDS = {"fn", "let", "return", "if", "else", "uses", "true", "false", "while", "requires", "ensures", "and", "or", "not", "invariant", "record", "import", "fail", "check", "try", "for"}

TOKEN_SPEC = [
    ("COMMENT", r"//[^\n]*"),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+"),
    ("ARROW",   r"->"),
    ("FLOAT",   r"\d+\.\d+"),
    ("NUMBER",  r"\d+"),
    ("STRING",  r'"(?:\\.|[^"\\\n])*"'),
    ("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",      r"==|!=|<=|>=|[+\-*/%<>=(){},:\[\].]"),
]

MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


@dataclass
class Token:
    kind: str          # NUMBER, STRING, IDENT, KEYWORD, OP, ARROW
    text: str
    line: int


def lex(source: str, keep_trivia: bool = False) -> list[Token]:
    tokens, line = [], 1
    pos = 0
    while pos < len(source):
        m = MASTER_RE.match(source, pos)
        if not m:
            raise VelarisError("E000", f"unexpected character {source[pos]!r}", line,
                              fixes=["remove or replace this character"])
        kind, text = m.lastgroup, m.group()
        pos = m.end()
        if kind == "NEWLINE":
            if keep_trivia:
                tokens.append(Token("NEWLINE", "", line))
            line += 1
        elif kind == "COMMENT":
            if keep_trivia:
                tokens.append(Token("COMMENT", text.rstrip(), line))
        elif kind == "SKIP":
            pass
        elif kind == "IDENT" and text in KEYWORDS:
            tokens.append(Token("KEYWORD", text, line))
        else:
            tokens.append(Token(kind, text, line))
    tokens.append(Token("EOF", "", line))
    return tokens


def fmt_fn_type(param_types: list, ret: str | None) -> str:
    s = "fn(" + ", ".join(param_types) + ")"
    if ret and ret != "Unit":
        s += f" -> {ret}"
    return s


def type_mentions(t: str, tv: str) -> bool:
    if t == tv:
        return True
    if t.startswith("Money of "):           # a currency variable
        return t[len("Money of "):] == tv
    if t.startswith("Secret of "):          # Secret of T, the way a
        return type_mentions(t[len("Secret of "):], tv)   # generic says
                                            # it holds a secret on purpose
    if t.startswith("List of "):
        return type_mentions(t[len("List of "):], tv)
    if t.startswith("Map of "):
        key, _, val = t[len("Map of "):].partition(" to ")
        return type_mentions(key, tv) or type_mentions(val, tv)
    sig = fn_sig_parts(t)
    if sig is not None:
        parts, ret = sig
        return any(type_mentions(p, tv) for p in parts) or \
            type_mentions(ret, tv)
    return False


def fn_sig_parts(t: str):
    """Split 'fn(A, B) -> R' into ([A, B], R). None if not a fn type."""
    if not t.startswith("fn("):
        return None
    depth, i, start, parts = 0, 3, 3, []
    while i < len(t):
        c = t[i]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(t[start:i].strip())
            start = i + 1
        i += 1
    last = t[start:i].strip()
    if last:
        parts.append(last)
    rest = t[i + 1:]
    ret = rest[4:].strip() if rest.startswith(" -> ") else "Unit"
    return parts, ret


ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def unescape(raw: str, line: int) -> str:
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == "\\":
            i += 1
            e = raw[i] if i < len(raw) else ""
            if e not in ESCAPES:
                raise VelarisError("E002",
                    f"unknown escape '\\{e}' in text", line,
                    fixes=['known escapes: \\n (newline), \\t (tab), '
                           '\\" (quote), \\\\ (backslash)'])
            out.append(ESCAPES[e])
        else:
            out.append(c)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# 2. AST — the tree shapes the parser produces
# ---------------------------------------------------------------------------

@dataclass
class Num:      value: int
@dataclass
class FloatNum: value: float
@dataclass
class Neg:      value: object; line: int
@dataclass
class Str:      value: str
@dataclass
class Bool:     value: bool
@dataclass
class Closure:
    """A function value that may carry values from around it.

    The function itself was lifted to the top level; this node is what
    the surrounding code evaluates to, and it is where the captured
    values are read - once, at the moment the value is made.
    """
    name: str
    free: list
    line: int


@dataclass
class Var:      name: str; line: int
@dataclass
class BinOp:    op: str; left: object; right: object; line: int
@dataclass
class Call:     name: str; args: list; line: int
@dataclass
class Let:
    name: str; value: object; line: int
    ann: str | None = None             # optional 'let x: Type = ...' 
@dataclass
class Return:   value: object; line: int
@dataclass
class If:       cond: object; then: list; other: list; line: int
@dataclass
class While:
    cond: object; body: list; line: int
    invariants: list = field(default_factory=list)   # [(expr, line)]
@dataclass
class Assign:   name: str; value: object; line: int
@dataclass
class Not:      value: object; line: int
@dataclass
class RecordLit: name: str; fields: list; line: int      # [(fname, expr)]
@dataclass
class FieldGet: obj: object; field: str; line: int
@dataclass
class RecordDef:
    name: str; fields: list; line: int                   # [(fname, type)]
    src_file: str = ""
@dataclass
class ListLit:  items: list; line: int
@dataclass
class MapLit:   entries: list; line: int         # [(key_expr, val_expr)]
@dataclass
class Block:    stmts: list; line: int      # a 'for' unrolled into while
@dataclass
class ExprStmt: expr: object; line: int
@dataclass
class FailStmt: value: object; line: int
@dataclass
class TryExpr:  value: object; line: int         # value is a Call
@dataclass
class Check:
    subject: object; line: int                   # subject is a Call
    ok_name: str | None = None; ok_body: list = field(default_factory=list)
    fail_name: str = ""; fail_body: list = field(default_factory=list)

@dataclass
class Function:
    name: str
    params: list[tuple[str, str]]      # (name, type)
    return_type: str | None
    effects: set[str]                  # declared with `uses`
    requires: list                     # [(expr, line)] promises about inputs
    ensures: list                      # [(expr, line)] promises about output
    body: list
    line: int
    src_file: str = ""
    can_fail: bool = False
    type_vars: list = field(default_factory=list)
    is_lambda: bool = False
    captures: list = field(default_factory=list)   # [(name, type)]


# ---------------------------------------------------------------------------
# Friendly + machine-readable errors
# ---------------------------------------------------------------------------

class VelarisError(Exception):
    def __init__(self, code: str, message: str, line: int,
                 fixes: list[str] | None = None, file: str | None = None):
        self.code, self.message, self.line = code, message, line
        self.fixes = fixes or []
        self.file = file
        super().__init__(message)

    def human(self, filename: str) -> str:
        out = [f"error[{self.code}] {self.message}",
               f"  --> {self.file or filename}, line {self.line}"]
        if self.fixes:
            out.append("  how to fix (pick one):")
            for i, f in enumerate(self.fixes, 1):
                out.append(f"    {i}. {f}")
        return "\n".join(out)

    def machine(self, filename: str) -> str:
        return json.dumps({
            "code": self.code, "message": self.message,
            "file": self.file or filename, "line": self.line,
            "fixes": self.fixes,
        }, indent=2)


# The error table: every code the compiler, the runtime and the library
# can report, with one line saying what it means. It is the only list.
# The published errors page is built from it, `check --sarif` makes one
# rule of each entry, and check_library.py reads this file's syntax tree
# and fails if a code is raised anywhere that is not here, or is here
# and raised nowhere. A code with two meanings says both.
ERROR_TABLE = {
    "E000": "a character the lexer cannot read, or a run that stopped "
            "without a Velaris error to report",
    "E001": "the program's file cannot be found",
    "E002": "an unknown escape sequence in a text literal",
    "E100": "the parser expected something else here",
    "E101": "a token that cannot start an expression here",
    "E102": "an expression that nests, or chains operators, too deeply",
    "E200": "an unknown function, or an import with no such function",
    "E300": "an effect used but not declared in 'uses', or a name in "
            "'uses' that is not an effect",
    "E310": "an effect outside the run's budget (while running); or a "
            "promise that calls a function with effects or uses 'try'",
    "E311": "a Python module outside the run's ffi: grants was reached",
    "E313": "a path outside the run's fs grants",
    "E314": "a host or port outside the run's net grants",
    "E315": "the run's fs or net operation count was reached",
    "E316": "a file larger than the read ceiling (raise it with --max-read)",
    "E400": "there is no 'main' function",
    "E401": "the wrong number of arguments, or parameters on 'main'",
    "E402": "an unknown variable, or a function value that uses a name "
            "from the code around it",
    "E403": "division or remainder by zero while running",
    "E405": "random(n) with n less than 1",
    "E406": "the placeholders in a format text and the values given do "
            "not match",
    "E407": "a whole number grew past 64 bits",
    "E408": "an exit code outside 0 to 255",
    "E500": "an unknown type",
    "E501": "types do not match",
    "E502": "a value is needed from a function that returns nothing",
    "E503": "a return does not match the declared return type",
    "E504": "an 'if' or 'while' condition that is not a Bool",
    "E505": "a requires, ensures or invariant that is not a Bool",
    "E506": "an empty list or map with no type to say what it holds",
    "E507": "a record defined twice, a field given twice in a record, or "
            "one name used for a record and a function",
    "E508": "an unknown record",
    "E509": "a record value with a missing, unknown or repeated field, "
            "or a map with a repeated key",
    "E510": "a field that the value does not have",
    "E511": "a record changed in place",
    "E512": "an imported file cannot be found",
    "E513": "a function or record defined in two files",
    "E514": "a variable named like an import",
    "E520": "a failure that is ignored: a call that can fail, not "
            "handled with check or passed up with try",
    "E521": "'try' in a function that cannot fail, or a failure that "
            "escaped the program while running",
    "E522": "'try' or 'check' on a call that cannot fail",
    "E523": "'fail' in a function that does not declare 'or fail', or a "
            "'main' that can fail",
    "E524": "'main' declared 'or fail'",
    "E525": "a check's ok arm names the result of a call that returns "
            "nothing, or leaves a returned value unnamed",
    "E530": "a function passed as a value that has effects or can fail",
    "E560": "a Secret given to something that emits it: a builtin with "
            "an effect, a generic function with an effect, or a 'fail' "
            "reason",
    "E561": "declassify without a reason written as text in the call, or "
            "given something that is not a Secret",
    "E562": "a Secret of a Secret",
    "E563": "an 'if' or 'while' branching on a value derived from a "
            "Secret",
    "E540": "a type variable that appears only in the return type",
    "E541": "a type variable named like a real type",
    "E542": "a function value of the wrong shape",
    "E543": "a generic function passed as a value",
    "E550": "amounts in two different currencies added, compared, or one "
            "given where the other is needed",
    "E551": "a currency that is not in velaris.CURRENCIES, or one not "
            "written as text in the call",
    "E552": "a rounding mode other than \"half_up\", \"half_even\" or "
            "\"down\", or one not written as text in the call",
    "E553": "an amount divided with '/' or '%', which would round "
            "without saying how",
    "E600": "a 'requires' broke while running",
    "E601": "an 'ensures' broke while running",
    "E602": "a position outside a list or text while running",
    "E607": "a text grew too large to build, or there was no input to "
            "read",
    "E608": "a file could not be written",
    "E609": "recursion too deep, or split by empty text",
    "E610": "the run's time limit was reached and the program stopped",
    "E611": "the run's memory cap was reached and the program stopped",
    "E612": "a loop whose end cannot be shown (check --strict only)",
    "E700": "a promise that is provably false, with the input that "
            "breaks it",
    "E701": "a call that can break the called function's 'requires', "
            "with the input that does",
    "E703": "a loop invariant the prover cannot show holds",
    "E704": "a loop invariant broke while running",
    "E705": "a list read the prover shows can go past the end",
    "E706": "a divisor the prover shows can be zero",
    "E999": "the self-test in 'velaris doctor' failed",
}

# Codes that were given once and are not given now, as (code, what it
# meant, the version that removed it). STABILITY.md rule 3: a code is
# never reused for a different meaning, and a removed one stays listed
# here and on the errors page. None has been removed since the rule was
# written (4.0); E610's reuse in 2.59 is in STABILITY.md's record.
REMOVED_ERRORS = ()


# ---------------------------------------------------------------------------
# 3. PARSER — recursive descent, one function per grammar rule
# ---------------------------------------------------------------------------

# An expression's tree is walked recursively by every later stage (effect
# checker, type checker, prover, formatter). A pathological source - a chain
# of thousands of operators, or thousands of nested brackets - would build a
# tree deep enough to overflow one of those walks with a Python traceback
# rather than a clean error (fixed in 7.1.2). These caps are far above any
# real expression; past them the parser stops with E102. The compile
# pipeline also raises Python's recursion limit (load_program) so a tree up
# to these depths walks without trouble.
EXPR_CHAIN_LIMIT = 1000       # operators in one left-associative run
EXPR_NEST_LIMIT = 1000        # bracket / unary nesting depth


class Parser:
    lambda_n = 0

    def __init__(self, tokens: list[Token]):
        self.lifted: list = []
        self.toks = tokens
        self.i = 0
        self._nest = 0            # current expression nesting depth (E102)

    def _too_deep(self, line: int):
        return VelarisError("E102",
            "this expression nests, or chains operators, too deeply",
            line,
            fixes=["split it into smaller pieces with intermediate 'let' "
                   "bindings",
                   "a single expression this large is almost always a bug"])

    def peek(self) -> Token: return self.toks[self.i]
    def next(self) -> Token:
        t = self.toks[self.i]; self.i += 1; return t

    def expect(self, kind: str, text: str | None = None) -> Token:
        t = self.peek()
        if t.kind != kind or (text is not None and t.text != text):
            want = text or kind.lower()
            raise VelarisError("E100", f"expected '{want}' but found '{t.text or 'end of file'}'",
                              t.line, fixes=[f"insert '{want}' here"])
        return self.next()

    def parse_program(self):
        funcs, records, imports = self.lifted, [], []
        while self.peek().kind != "EOF":
            t = self.peek()
            if t.kind == "KEYWORD" and t.text == "import":
                self.next()
                s = self.expect("STRING")
                alias = None
                if self.peek().kind == "IDENT" and self.peek().text == "as":
                    self.next()
                    alias = self.expect("IDENT").text
                imports.append(
                    (unescape(s.text[1:-1], s.line), t.line, alias))
            elif t.kind == "KEYWORD" and t.text == "record":
                records.append(self.parse_record())
            else:
                funcs.append(self.parse_function())
        return funcs, records, imports

    def parse_record(self) -> RecordDef:
        start = self.expect("KEYWORD", "record")
        name = self.expect("IDENT").text
        self.expect("OP", "{")
        fields = []
        while self.peek().text != "}":
            fname = self.expect("IDENT").text
            self.expect("OP", ":")
            fields.append((fname, self.parse_type()))
        self.expect("OP", "}")
        return RecordDef(name, fields, start.line)

    def parse_function(self) -> Function:
        start = self.expect("KEYWORD", "fn")
        name = self.expect("IDENT").text
        self.expect("OP", "(")
        params = []
        while self.peek().text != ")":
            pname = self.expect("IDENT").text
            self.expect("OP", ":")
            ptype = self.parse_type()
            params.append((pname, ptype))
            if self.peek().text == ",":
                self.next()
        self.expect("OP", ")")
        ret = None
        if self.peek().kind == "ARROW":
            self.next()
            ret = self.parse_type()
        effects: set[str] = set()
        type_vars: list[str] = []
        can_fail = False
        while True:                    # uses / for any / or fail, any order
            t2 = self.peek()
            if t2.kind == "KEYWORD" and t2.text == "uses":
                self.next()
                effects.add(self.expect("IDENT").text)
                while self.peek().text == ",":
                    self.next()
                    effects.add(self.expect("IDENT").text)
            elif t2.kind == "KEYWORD" and t2.text == "for":
                self.next()
                anykw = self.expect("IDENT")
                if anykw.text != "any":
                    raise VelarisError("E100", "expected 'any' after 'for'",
                        anykw.line, fixes=["write: for any T"])
                type_vars.append(self.expect("IDENT").text)
                while self.peek().text == ",":
                    self.next()
                    type_vars.append(self.expect("IDENT").text)
            elif (t2.kind == "KEYWORD" and t2.text == "or"
                    and self.toks[self.i + 1].text == "fail"):
                self.next(); self.next()
                can_fail = True
            else:
                break
        requires_, ensures_ = [], []
        while (self.peek().kind == "KEYWORD"
               and self.peek().text in ("requires", "ensures")):
            kw = self.next()
            clause = (self.parse_expr(), kw.line)
            (requires_ if kw.text == "requires" else ensures_).append(clause)
        body = self.parse_block()
        f = Function(name, params, ret, effects, requires_, ensures_,
                     body, start.line)
        f.can_fail = can_fail
        f.type_vars = type_vars
        return f

    def parse_lambda(self, start: Token):
        """fn(x: Int) -> Bool { return x > 0 } as a value.

        Lifted to a real top-level function with a generated name, so
        every later stage (types, effects, proofs, native codegen) sees
        an ordinary function. Lambdas are pure and cannot capture
        variables from around them - pass what you need as a parameter.
        """
        self.expect("OP", "(")
        params = []
        while self.peek().text != ")":
            pname = self.expect("IDENT").text
            self.expect("OP", ":")
            params.append((pname, self.parse_type()))
            if self.peek().text == ",":
                self.next()
        self.expect("OP", ")")
        if self.peek().text != "->":
            raise VelarisError("E100",
                "a function value needs a result type", start.line,
                fixes=["write: fn(x: Int) -> Bool { return x > 0 }"])
        self.next()
        ret = self.parse_type()
        requires_, ensures_ = [], []      # a function value can promise too
        while (self.peek().kind == "KEYWORD"
               and self.peek().text in ("requires", "ensures")):
            kw = self.next()
            clause = (self.parse_expr(), kw.line)
            (requires_ if kw.text == "requires" else ensures_).append(clause)
        body = self.parse_block()
        Parser.lambda_n += 1
        name = f"fn#{Parser.lambda_n}"
        f = Function(name, params, ret, set(), requires_, ensures_,
                     body, start.line)
        f.can_fail = False
        f.type_vars = []
        f.is_lambda = True
        # names the body reads that it did not bind itself: candidates
        # for capture. Which are really locals is known only once the
        # surrounding function is type checked, so decide there.
        bound = {p for p, _ in params}
        free = []

        def look(node):
            if isinstance(node, Let) or isinstance(node, Assign):
                bound.add(node.name)
            if isinstance(node, Var) and node.name not in bound \
                    and node.name not in free:
                free.append(node.name)
            if isinstance(node, Check):
                bound.add(node.ok_name)
                bound.add(node.fail_name)

        import dataclasses as _dc

        def visit(n):
            if isinstance(n, (list, tuple)):
                for x in n:
                    visit(x)
                return
            if not _dc.is_dataclass(n):
                return
            look(n)
            for fl in _dc.fields(n):
                visit(getattr(n, fl.name))

        visit(body)
        f.free_names = free
        self.lifted.append(f)
        return Closure(name, free, start.line)

    @staticmethod
    def flatten(stmts: list) -> list:
        out = []
        for s in stmts:
            if isinstance(s, Block):
                out.extend(Parser.flatten(s.stmts))
            else:
                out.append(s)
        return out

    def parse_block(self) -> list:
        self.expect("OP", "{")
        stmts = []
        while self.peek().text != "}":
            stmts.append(self.parse_statement())
        self.expect("OP", "}")
        return Parser.flatten(stmts)

    def parse_statement(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "let":
            self.next()
            name = self.expect("IDENT").text
            ann = None
            if self.peek().text == ":":
                self.next()
                ann = self.parse_type()
            self.expect("OP", "=")
            return Let(name, self.parse_expr(), t.line, ann)
        if t.kind == "KEYWORD" and t.text == "return":
            self.next()
            if self.peek().text == "}":          # bare 'return' with no value
                return Return(None, t.line)
            return Return(self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "fail":
            self.next()
            return FailStmt(self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "check":
            self.next()
            subject = self.parse_expr()
            if isinstance(subject, TryExpr) or not isinstance(subject, Call):
                raise VelarisError("E100",
                    "'check' needs a call to a function that can fail",
                    t.line, fixes=["write: check f(args) { ok v { ... } "
                                   "fail reason { ... } }"])
            self.expect("OP", "{")
            okkw = self.expect("IDENT")
            if okkw.text != "ok":
                raise VelarisError("E100", "expected 'ok' arm first in check",
                    okkw.line, fixes=["write: ok value { ... }"])
            ok_name = None
            if self.peek().kind == "IDENT":
                ok_name = self.next().text
            ok_body = self.parse_block()
            self.expect("KEYWORD", "fail")
            fail_name = self.expect("IDENT").text
            fail_body = self.parse_block()
            self.expect("OP", "}")
            return Check(subject, t.line, ok_name, ok_body,
                         fail_name, fail_body)
        if t.kind == "KEYWORD" and t.text == "for":
            self.next()
            name = self.expect("IDENT").text
            inw = self.expect("IDENT")
            if inw.text != "in":
                raise VelarisError("E100", "expected 'in' after the name",
                    inw.line, fixes=["write: for i in 0 to n { ... }",
                                     "or:    for item in xs { ... }"])
            start = self.parse_expr()
            if (self.peek().kind == "IDENT" and self.peek().text == "to"):
                self.next()                       # for i in a to b
                stop = self.parse_expr()
                invs = []
                while (self.peek().kind == "KEYWORD"
                       and self.peek().text == "invariant"):
                    kw = self.next()
                    invs.append((self.parse_expr(), kw.line))
                body = self.parse_block()
                step = Assign(name, BinOp("+", Var(name, t.line),
                                          Num(1), t.line), t.line)
                return Block([
                    Let(name, start, t.line, None),
                    While(BinOp("<", Var(name, t.line), stop, t.line),
                          list(body) + [step], t.line, invs),
                ], t.line)
            Parser.lambda_n += 1                  # for item in xs
            idx = f"for#{Parser.lambda_n}"
            invs = []
            while (self.peek().kind == "KEYWORD"
                   and self.peek().text == "invariant"):
                kw = self.next()
                invs.append((self.parse_expr(), kw.line))
            body = self.parse_block()
            step = Assign(idx, BinOp("+", Var(idx, t.line), Num(1),
                                     t.line), t.line)
            inner = [Let(name, Call("get", [start, Var(idx, t.line)],
                                    t.line), t.line, None)]
            return Block([
                Let(idx, Num(0), t.line, None),
                While(BinOp("<", Var(idx, t.line),
                            Call("length", [start], t.line), t.line),
                      inner + list(body) + [step], t.line, invs),
            ], t.line)
        if t.kind == "KEYWORD" and t.text == "while":
            self.next()
            cond = self.parse_expr()
            invs = []
            while (self.peek().kind == "KEYWORD"
                   and self.peek().text == "invariant"):
                kw = self.next()
                invs.append((self.parse_expr(), kw.line))
            body = self.parse_block()
            return While(cond, body, t.line, invs)
        if t.kind == "IDENT" and self.toks[self.i + 1].text == ".":
            j = self.i + 1                       # looks like p.x(.y)* = ...
            while (self.toks[j].text == "."
                   and self.toks[j + 1].kind == "IDENT"):
                j += 2
            if self.toks[j].text == "=":
                raise VelarisError("E511",
                    "records cannot be changed in place", t.line,
                    fixes=["build a new one: let p2 = "
                           "Point(x: new_value, y: p.y)"])
        if t.kind == "IDENT" and self.toks[self.i + 1].text == "=":
            self.next()
            self.expect("OP", "=")
            return Assign(t.text, self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "if":
            self.next()
            cond = self.parse_expr()
            then = self.parse_block()
            other = []
            if self.peek().text == "else":
                self.next()
                if (self.peek().kind == "KEYWORD"
                        and self.peek().text == "if"):
                    other = [self.parse_statement()]   # else if chain
                else:
                    other = self.parse_block()
            return If(cond, then, other, t.line)
        return ExprStmt(self.parse_expr(), t.line)

    def parse_type(self) -> str:
        if self.peek().kind == "KEYWORD" and self.peek().text == "fn":
            self.next()
            self.expect("OP", "(")
            parts = []
            while self.peek().text != ")":
                parts.append(self.parse_type())
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", ")")
            ret = None
            if self.peek().kind == "ARROW":
                self.next()
                ret = self.parse_type()
            return fmt_fn_type(parts, ret)
        t = self.expect("IDENT")
        if t.text == "Map":
            of = self.expect("IDENT")
            if of.text != "of":
                raise VelarisError("E100", "expected 'of' after 'Map'",
                    of.line, fixes=["write map types like: Map of Text to Int"])
            key = self.expect("IDENT").text
            to = self.expect("IDENT")
            if to.text != "to":
                raise VelarisError("E100", "expected 'to' after the key type",
                    to.line, fixes=["write map types like: Map of Text to Int"])
            return f"Map of {key} to " + self.parse_type()
        if t.text == "List":
            of = self.expect("IDENT")
            if of.text != "of":
                raise VelarisError("E100", "expected 'of' after 'List'", of.line,
                                  fixes=["write list types like: List of Int"])
            return "List of " + self.parse_type()   # nesting allowed
        # an amount: Money of INR, or Money of C in a function generic in
        # its currency (4.3). 'Money' alone stays a name, so a program's
        # own record called Money means what it did - including one
        # followed by a field called 'of'.
        if (t.text == "Money" and self.peek().text == "of"
                and self.toks[self.i + 1].kind == "IDENT"
                and self.toks[self.i + 2].text != ":"):
            self.next()
            return "Money of " + self.next().text
        # a value that must not escape: Secret of Text, Secret of Int,
        # Secret of List of Text (5.1/6.0, SPEC.md 3.1). Like Money,
        # `Secret` alone stays a name, so a program's own record called
        # Secret means what it did.
        if (t.text == "Secret" and self.peek().text == "of"
                and self.toks[self.i + 1].kind == "IDENT"
                and self.toks[self.i + 2].text != ":"):
            self.next()
            inner = self.parse_type()
            if inner.startswith("Secret of "):
                raise VelarisError("E562",
                    "a Secret of a Secret is the same secret; write "
                    f"{inner}", t.line,
                    fixes=[f"write {inner}"])
            return "Secret of " + inner
        return t.text

    # expressions: or -> and -> not -> comparison -> add/sub -> mul/div -> atoms
    def parse_expr(self):
        left = self.parse_and()
        n = 0
        while self.peek().kind == "KEYWORD" and self.peek().text == "or":
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp("or", left, self.parse_and(), op.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        n = 0
        while self.peek().kind == "KEYWORD" and self.peek().text == "and":
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp("and", left, self.parse_not(), op.line)
        return left

    def parse_not(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "not":
            self.next()
            self._nest += 1
            if self._nest > EXPR_NEST_LIMIT:
                raise self._too_deep(t.line)
            try:
                return Not(self.parse_not(), t.line)
            finally:
                self._nest -= 1
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        n = 0
        while self.peek().text in ("==", "!=", "<", ">", "<=", ">="):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_add(), op.line)
        return left

    def parse_add(self):
        left = self.parse_mul()
        n = 0
        while self.peek().text in ("+", "-"):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_mul(), op.line)
        return left

    def parse_mul(self):
        left = self.parse_postfix()
        n = 0
        while self.peek().text in ("*", "/", "%"):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_postfix(), op.line)
        return left

    def parse_postfix(self):
        e = self.parse_atom()
        while self.peek().text == ".":
            dot = self.next()
            fname = self.expect("IDENT").text
            e = FieldGet(e, fname, dot.line)
        return e

    def parse_atom(self):
        self._nest += 1
        if self._nest > EXPR_NEST_LIMIT:
            raise self._too_deep(self.peek().line)
        try:
            return self._parse_atom()
        finally:
            self._nest -= 1

    def _parse_atom(self):
        t = self.next()
        if t.kind == "KEYWORD" and t.text == "fn":
            return self.parse_lambda(t)
        if t.kind == "KEYWORD" and t.text == "try":
            inner = self.parse_postfix()
            if not isinstance(inner, Call):
                raise VelarisError("E100",
                    "'try' needs a call to a function that can fail",
                    t.line, fixes=["write: try f(args)"])
            return TryExpr(inner, t.line)
        if t.text == "-":                      # negative numbers: -7, -x
            return Neg(self.parse_postfix(), t.line)
        if t.text == "{":                      # map literal: {"a": 1}
            entries = []
            while self.peek().text != "}":
                k = self.parse_expr()
                self.expect("OP", ":")
                entries.append((k, self.parse_expr()))
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", "}")
            return MapLit(entries, t.line)
        if t.text == "[":                      # list literal: [1, 2, 3]
            items = []
            while self.peek().text != "]":
                items.append(self.parse_expr())
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", "]")
            return ListLit(items, t.line)
        if t.kind == "NUMBER":
            return Num(int(t.text))
        if t.kind == "FLOAT":
            return FloatNum(float(t.text))
        if t.kind == "STRING":
            return Str(unescape(t.text[1:-1], t.line))
        if t.kind == "KEYWORD" and t.text in ("true", "false"):
            return Bool(t.text == "true")
        if t.text == "(":
            e = self.parse_expr()
            self.expect("OP", ")")
            return e
        if t.kind == "IDENT":
            if (self.peek().text == "." and
                    self.toks[self.i + 1].kind == "IDENT" and
                    self.toks[self.i + 2].text == "("):
                self.next()                        # '.'
                fname = self.next().text           # function in namespace
                self.next()                        # '('
                qargs = []
                while self.peek().text != ")":
                    qargs.append(self.parse_expr())
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return Call(f"{t.text}.{fname}", qargs, t.line)
            if (self.peek().text == "("
                    and self.toks[self.i + 1].kind == "IDENT"
                    and self.toks[self.i + 2].text == ":"):
                self.next()                        # record literal
                fields = []
                while self.peek().text != ")":
                    fname = self.expect("IDENT").text
                    self.expect("OP", ":")
                    fields.append((fname, self.parse_expr()))
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return RecordLit(t.text, fields, t.line)
            if self.peek().text == "(":            # function call
                self.next()
                args = []
                while self.peek().text != ")":
                    args.append(self.parse_expr())
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return Call(t.text, args, t.line)
            return Var(t.text, t.line)
        raise VelarisError("E101", f"unexpected '{t.text}'", t.line,
                          fixes=["expected a number, string, variable, or function call"])


def nice_name(name: str) -> str:
    """Lifted lambdas get generated names; show something readable."""
    if name.startswith("fn#"):
        return "this function value"
    return f"'{name}'"


def expr_str(e) -> str:
    """Turn an AST expression back into readable source text (for errors)."""
    if isinstance(e, Num):  return str(e.value)
    if isinstance(e, FloatNum): return str(e.value)
    if isinstance(e, Neg):  return f"-{expr_str(e.value)}"
    if isinstance(e, TryExpr): return f"try {expr_str(e.value)}"
    if isinstance(e, Str):  return f'"{e.value}"'
    if isinstance(e, Bool): return "true" if e.value else "false"
    if isinstance(e, Var):  return e.name
    if isinstance(e, Call): return f"{e.name}({', '.join(expr_str(a) for a in e.args)})"
    if isinstance(e, BinOp):
        # keep the meaning: parenthesise operands that bind less tightly,
        # so (result + 1) * count never prints as result + 1 * count
        prec = {"or": 1, "and": 2,
                "==": 3, "!=": 3, "<": 3, ">": 3, "<=": 3, ">=": 3,
                "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}
        here = prec.get(e.op, 6)

        def side(sub, is_right: bool) -> str:
            text = expr_str(sub)
            if isinstance(sub, BinOp):
                there = prec.get(sub.op, 6)
                if there < here or (there == here and is_right):
                    return f"({text})"
            return text
        return f"{side(e.left, False)} {e.op} {side(e.right, True)}"
    if isinstance(e, Not):   return f"not {expr_str(e.value)}"
    if isinstance(e, ListLit): return "[" + ", ".join(expr_str(i) for i in e.items) + "]"
    if isinstance(e, MapLit):
        return "{" + ", ".join(f"{expr_str(k)}: {expr_str(v)}"
                               for k, v in e.entries) + "}"
    if isinstance(e, FieldGet): return f"{expr_str(e.obj)}.{e.field}"
    if isinstance(e, RecordLit):
        return e.name + "(" + ", ".join(f"{f}: {expr_str(v)}" for f, v in e.fields) + ")"
    return "?"


def expr_vars(e) -> set[str]:
    if isinstance(e, Var):   return {e.name}
    if isinstance(e, Not):   return expr_vars(e.value)
    if isinstance(e, Neg):   return expr_vars(e.value)
    if isinstance(e, TryExpr): return expr_vars(e.value)
    if isinstance(e, ListLit):
        out = set()
        for i in e.items:
            out |= expr_vars(i)
        return out
    if isinstance(e, BinOp): return expr_vars(e.left) | expr_vars(e.right)
    if isinstance(e, MapLit):
        out = set()
        for k, v in e.entries:
            out |= expr_vars(k) | expr_vars(v)
        return out
    if isinstance(e, FieldGet): return expr_vars(e.obj)
    if isinstance(e, RecordLit):
        out = set()
        for _, v in e.fields:
            out |= expr_vars(v)
        return out
    if isinstance(e, Call):
        out = set()
        for a in e.args:
            out |= expr_vars(a)
        return out
    return set()


# ---------------------------------------------------------------------------
# 3b. LOADER — resolve imports into one program, remembering which file
#     every function and record came from.
# ---------------------------------------------------------------------------

def qualify(fs: list, alias: str) -> None:
    """Rename a library's functions to alias.name, in place.

    References the library makes to its own functions are renamed too,
    so a namespaced import behaves exactly like the flat one from the
    inside - only the importer sees the prefix.
    """
    import dataclasses
    local = {f.name for f in fs}
    new_name = {n: f"{alias}.{n}" for n in local}

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
            return
        if isinstance(node, tuple):
            for x in node:
                walk(x)
            return
        if not dataclasses.is_dataclass(node):
            return
        if isinstance(node, (Call, Var)) and node.name in new_name:
            node.name = new_name[node.name]
        for fld in dataclasses.fields(node):
            if fld.name == "name":
                continue
            walk(getattr(node, fld.name))

    for f in fs:
        walk(f.body)
        walk([e for e, _ in f.requires])
        walk([e for e, _ in f.ensures])
    for f in fs:
        f.name = new_name[f.name]


def unknown_function(name: str, line: int, known) -> VelarisError:
    """One clear message for an unknown name, namespace-aware."""
    if "." in name:
        ns, _, fname = name.partition(".")
        spaces = sorted({n.split(".")[0] for n in known if "." in n})
        if ns in spaces:
            near = sorted(n.split(".", 1)[1] for n in known
                          if n.startswith(ns + "."))
            return VelarisError("E200",
                f"'{ns}' has no function called '{fname}'", line,
                fixes=[f"available in '{ns}': {', '.join(near[:8])}"
                       + (" ..." if len(near) > 8 else ""),
                       "check the spelling of the name"])
        return VelarisError("E200", f"no import is named '{ns}'", line,
            fixes=[f'name an import: import "lib.vel" as {ns}',
                   (f"names in scope: {', '.join(spaces)}" if spaces
                    else "an import only gets a name if you write 'as'")])
    return VelarisError("E200", f"unknown function '{name}'", line,
                        fixes=[f"define 'fn {name}(...)' somewhere",
                               "check the spelling of the name"])


def load_program(entry: str, entry_source: str | None = None,
                 loaded: list | None = None):
    """(functions, records) of the entry file and everything it imports.
    `loaded`, when given, gets the path of each file read, in the order
    they were read - the entry first."""
    # Every later stage walks the AST recursively; the parser caps how deep
    # an expression can nest (EXPR_NEST_LIMIT / EXPR_CHAIN_LIMIT), and this
    # lifts Python's own limit so a tree up to that depth walks without a
    # traceback (the interpreter raises it too, for deep calls). 7.1.2.
    if sys.getrecursionlimit() < 20000:
        try:
            sys.setrecursionlimit(20000)
        except Exception:
            pass
    funcs, records = [], []
    fn_src, rec_src = {}, {}
    visited = set()

    def load(path: str, importer: str | None, iline: int = 1,
             alias: str | None = None):
        ap = os.path.abspath(path)
        if ap in visited:
            return                       # already loaded (diamond or cycle)
        visited.add(ap)
        source = None
        if importer is None and entry_source is not None:
            source = entry_source
        try:
            if source is None:
                source = open(path, encoding="utf-8").read()
        except OSError:
            if importer is not None:
                shipped = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "stdlib", os.path.basename(path))
                if os.path.exists(shipped):
                    visited.discard(ap)
                    return load(shipped, importer, iline, alias)
            if importer is None:
                raise VelarisError("E001", f"cannot find file '{path}'", 1,
                    fixes=["check the file name spelling",
                           "make sure you are in the folder that contains it"])
            raise VelarisError("E512",
                f"cannot find imported file '{path}'", iline,
                fixes=["check the path in the import line",
                       "paths are relative to the importing file"],
                file=importer)
        if loaded is not None:
            loaded.append(path)
        try:
            tokens = lex(source)
            fs, rs, imports = Parser(tokens).parse_program()
        except VelarisError as e:
            e.file = e.file or path
            raise
        base = os.path.dirname(path)
        for ipath, iline, ialias in imports:   # ialias: don't shadow alias
            load(os.path.join(base, ipath) if base else ipath, path, iline,
                 ialias)
        if alias:
            qualify(fs, alias)
        for f in fs:
            f.src_file = path
            if f.name in fn_src:
                raise VelarisError("E513",
                    f"function '{f.name}' is defined in both "
                    f"'{fn_src[f.name]}' and '{path}'", f.line,
                    fixes=["rename one of them"], file=path)
            fn_src[f.name] = path
            funcs.append(f)
        for r in rs:
            r.src_file = path
            if r.name in rec_src:
                raise VelarisError("E513",
                    f"record '{r.name}' is defined in both "
                    f"'{rec_src[r.name]}' and '{path}'", r.line,
                    fixes=["rename one of them"], file=path)
            rec_src[r.name] = path
            records.append(r)

    load(entry, None)
    _bind_new_builtins(funcs)
    return funcs, records


def _bind_new_builtins(funcs: list) -> None:
    """A builtin added from 4.3 on gives way to a program's own function
    of the same name (SPEC.md 10.1). Inside a library imported with a
    name, though, a call can only mean the builtin: the library's own
    functions carry its prefix, and it was not written against the
    program that imports it. When the program's plain names hide such a
    builtin, the library's calls to it are bound to it here, as '@name'.
    Programs with no such clash are left exactly as parsed."""
    hidden = NEW_BUILTINS & {f.name for f in funcs if "." not in f.name}
    if not hidden:
        return
    import dataclasses as _dc

    def walk(node):
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call) and node.name in hidden:
            node.name = "@" + node.name
        for fl in _dc.fields(node):
            walk(getattr(node, fl.name))

    for f in funcs:
        if "." in f.name:
            walk(f.body)
            walk(f.requires)
            walk(f.ensures)


def blame(fn_or_rec, err: VelarisError) -> VelarisError:
    """Attach the true source file to an error, innermost wins."""
    err.file = err.file or fn_or_rec.src_file or None
    return err


# ---------------------------------------------------------------------------
# 4. EFFECT CHECKER — the heart of Velaris
#    Rule: a function may only cause effects it declares with `uses`.
# ---------------------------------------------------------------------------

FALLIBLE_BUILTINS = {"to_int", "read_file", "read_file_secret",
                     "fetch", "post",
                     "pop", "slice", "set_at",
                     "add_or_fail", "sub_or_fail", "mul_or_fail",
                     "div_or_fail", "mod_or_fail",
                     "fetch_status", "request", "py", "py_int", "py_float",
                     "py_json", "json_get", "json_int", "json_float",
                     "json_len", "py_new", "py_do", "py_field",
                     "divide_or_fail", "parse_money"}   # + get on maps

PROGRAM_ARGS: list = []    # filled by the CLI: velaris prog.vel a b c

# read_file / read_file_secret refuse a file larger than this, so a single
# read cannot exhaust memory (a whole file is read at once). The default is
# generous for source, config and data files; a program that legitimately
# reads more raises it with `--allow ... ` no - with `--max-read <MB>` on the
# command line. It is a resource ceiling like a memory cap, not a grant, so
# breaching it is E316 and cannot be caught. 64 MiB unless raised (7.1.2).
MAX_READ_BYTES = 64 * 1024 * 1024

# The eight. `declassify` joined the seven in 6.0: it is not a way to
# reach the outside world, it is the one way a Secret becomes an
# ordinary value (SPEC.md 3.1), and it is an effect for the same reason
# the other seven are - so that a signature says a function does it, the
# rule is transitive across the call graph, and an operator can refuse
# to grant it.
ALL_EFFECTS = ("io", "env", "fs", "net", "clock", "rand", "ffi",
               "declassify")

# The default budget, since 5.0: the console and nothing else. A run
# given no budget used to get all seven effects, which made the one
# thing a capability language must get right - what an operator gets
# when they say nothing - the widest answer instead of the narrowest.
# io rather than nothing so that a refused program can still say why it
# stopped; CHANGELOG 5.0 says why that trade was made.
DEFAULT_ALLOW = "io"
ALLOW_ALL = "all"                       # the CLI shorthand for every effect
EFFECT_BUDGET: set = {DEFAULT_ALLOW}    # io, unless you say otherwise
FFI_MODULES: set | None = None          # None = any module; a set = only
                                        # these top-level packages


FS_GRANTS: list | None = None          # None = any path; else [(kind, prefix)]
NET_GRANTS: list | None = None         # None = any host; else [(host, port)]
OP_LIMITS: dict = {"fs": None, "net": None}   # None = unlimited
OP_COUNTS: dict = {"fs": 0, "net": 0}
EFFECT_USES: dict = {}     # effect -> how many builtin calls the budget let
                           # through this run; what the doors log (3.4)


def expand_allow(spec: str) -> str:
    """`all`, written on its own, as every effect; anything else
    unchanged. From 6.0 that is eight, `declassify` among them: `all`
    means all, and an operator who writes it has waived every gate,
    which is why it writes a line to stderr.

    `all` is an operator's shorthand on a command line (`--allow all`,
    `--max-allow all`), not part of the budget grammar of SPEC.md 7.1 -
    so a caller sending a budget over the HTTP door or the MCP server
    cannot write it, and `Budget.parse` never sees it. It exists because
    5.0 made `io` the default: there has to be a way to ask for what a
    run used to get, and it has to be written down when it is used.
    """
    return ",".join(ALL_EFFECTS) if spec.strip() == ALLOW_ALL else spec


def warn_allow_all(where: str = "velaris") -> None:
    """One line to stderr when an operator asks for every effect.

    Not a refusal and not advice: a record, where whoever is watching
    the terminal or the log can see it.
    """
    print(f"{where}: --allow all grants every effect "
          f"({', '.join(ALL_EFFECTS)}); nothing this run does will be "
          f"refused by the budget", file=sys.stderr)


class BudgetError(ValueError):
    """A budget that does not parse. Raised before anything runs."""


# A path or host component can hold characters the grant grammar uses as
# structure: `,` splits items, `@` marks a count, `[` `]` bracket an IPv6
# address. Those five characters (with `%` itself) are percent-encoded
# inside a path or host component and decoded when the budget is parsed,
# so `safe_command` round-trips: a path with a comma, a host with an `@`,
# an IPv6 literal all survive being written to text and read back. This
# is the escaping rule of velaris-spec v0.2 (§5.1, §5.2). Only these five
# sequences are decoded; every other `%` is literal.
_PCT_ENCODE = (("%", "%25"), (",", "%2C"), ("@", "%40"),
               ("[", "%5B"), ("]", "%5D"))
_PCT_DECODE = {"%2C": ",", "%40": "@", "%5B": "[", "%5D": "]", "%25": "%"}


def _pct_encode(s: str) -> str:
    """Encode the five structural characters in a path or host component.
    `%` first, so an already-`%`-bearing string is not double-decoded."""
    for ch, enc in _PCT_ENCODE:
        s = s.replace(ch, enc)
    return s


def _pct_decode(s: str) -> str:
    """Decode exactly the five sequences, in one left-to-right pass so a
    literal `%2C` (written `%252C`) decodes to `%2C`, not to a comma."""
    out, i, n = [], 0, len(s)
    while i < n:
        chunk = s[i:i + 3].upper()
        if s[i] == "%" and chunk in _PCT_DECODE:
            out.append(_PCT_DECODE[chunk])
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _net_grant_text(host: str, port) -> str:
    """One `net:` grant as canonical text: an IPv6 host in brackets, any
    other host with its structural characters percent-encoded, then an
    optional `:port`."""
    h = f"[{host}]" if ":" in host else _pct_encode(host)
    return f"net:{h}" + (f":{port}" if port else "")


def _ascii_digits(s: str) -> bool:
    """True for a non-empty run of ASCII 0-9 only - not other Unicode
    digits, which str.isdigit would accept."""
    return bool(s) and s.isascii() and s.isdigit()


class Budget:
    """What a run may touch, as written on the command line.

        io                      the console: print, read_line, args
        env                     environment variables (since 3.0)
        fs                      any file, read and write
        fs:read  fs:write       one direction, any path
        fs:read:./data          one direction, under that path only
        fs:write:./out@50       ...and at most 50 file operations
        net                     any host
        net:api.example.com     that host, any port
        net:api.example.com:443 that host and port
        net:*.example.com       one label in place of the star
        net:...@100             at most 100 network operations
        ffi                     any Python module
        ffi:math,json           those top-level modules only

    Grants are additive: two fs items grant both. A count is the
    smallest count given for that effect and applies to the whole run.
    A budget with no count is a budget on what, not on how much. Paths
    are resolved with realpath when the budget is parsed and again at
    every call, so `..` and symlinks cannot reach past a prefix; paths
    holding a comma cannot be written in this grammar.
    """

    def __init__(self):
        self.effects: set = set()
        self.modules: set | None = None
        self.fs: list | None = None        # [(kind, prefix or None)]
        self.net: list | None = None       # [(host pattern, port or None)]
        self.limits: dict = {"fs": None, "net": None}
        self._fs_any = False               # a plain 'fs' was written
        self._net_any = False              # a plain 'net' was written
        self._ffi_any = False              # a plain 'ffi' was written

    # ---- parsing -------------------------------------------------------
    @classmethod
    def parse(cls, spec: str) -> "Budget":
        b = cls()
        items = [s.strip() for s in spec.split(",")]
        i = 0
        while i < len(items):
            item = items[i]
            i += 1
            if not item or item in ("''", '""'):
                # an empty budget. A shell strips the quotes; a child
                # process started with a list of arguments does not, and
                # until 3.1 `run(src, allow=set(), timeout=1)` reached the
                # child as the literal two characters '' and came back
                # E000 instead of refusing io.
                continue
            if item.startswith("ffi:"):
                b.effects.add("ffi")
                # ffi is additive like fs and net (SPEC.md §7.1, resolved
                # in spec v0.2 / Q2): a plain `ffi` anywhere grants every
                # module, and the wider grant wins, so `ffi,ffi:math` and
                # `ffi:math,ffi` both grant every module. Named modules
                # narrow only while no plain `ffi` has been written.
                raw = [item[4:].strip()]
                while i < len(items) and items[i] and ":" not in items[i] \
                        and "@" not in items[i] \
                        and items[i] not in ALL_EFFECTS:
                    raw.append(items[i])
                    i += 1
                mods = []
                for r in raw:
                    if "@" in r:      # ffi takes no count (spec Q6)
                        raise BudgetError(
                            f"'{r}': ffi takes no count; a module is a "
                            f"name, as ffi:math")
                    m = r.split(".")[0]
                    if not m:         # ffi: with no module (spec Q6)
                        raise BudgetError(
                            f"'{item}': ffi: needs a module name, as "
                            f"ffi:math")
                    mods.append(m)
                if not b._ffi_any:
                    b.modules = set() if b.modules is None else b.modules
                    b.modules.update(mods)
            elif item == "fs" or item.startswith("fs:") or \
                    item.startswith("fs@"):
                b._add_fs(item)
            elif item == "net" or item.startswith("net:") or \
                    item.startswith("net@"):
                b._add_net(item)
            elif item == "ffi":
                b.effects.add("ffi")
                b._ffi_any = True
                b.modules = None           # every module; the wider grant
            elif item in ALL_EFFECTS:
                b.effects.add(item)
            elif item == ALLOW_ALL:
                # `all` is the command line's shorthand and is expanded
                # before a budget is parsed (expand_allow), so reaching
                # here means it was written among other grants, or sent
                # by a caller over a door, where it is not a grant
                raise BudgetError(
                    f"'{ALLOW_ALL}' is not an effect. On a command line "
                    f"write it on its own - --allow {ALLOW_ALL} - which "
                    f"grants {', '.join(ALL_EFFECTS)}; in a budget "
                    f"alongside other grants, name the effects you want")
            else:
                raise BudgetError(
                    f"'{item}' is not an effect. They are: "
                    f"{', '.join(ALL_EFFECTS)} (or ffi:module, fs:read:path, "
                    f"net:host:port, with @count)")
        return b

    @staticmethod
    def _split_count(item: str) -> tuple:
        """'fs:read:./x@50' -> ('fs:read:./x', 50); no count -> None.

        A count is ASCII digits only. Python's str.isdigit also accepts
        other Unicode digits, so before 3.3 `fs@٣` was read as 3 and
        `fs@²` stopped the parser with an uncaught ValueError instead of
        a budget error (spec Q6). Only 0-9 count now."""
        at = item.rfind("@")
        if at > 0 and _ascii_digits(item[at + 1:]):
            body = item[:at]
            if "@" in body:      # a second @ is a stray, not a count
                raise BudgetError(
                    f"'{item}': a grant takes at most one @count; write "
                    f"an @ inside a path as %40")
            return body, int(item[at + 1:])
        if at > 0:
            raise BudgetError(f"'{item}': what follows @ must be a whole "
                              f"number of operations, written 0-9")
        return item, None

    def _limit(self, kind: str, n) -> None:
        if n is None:
            return
        cur = self.limits[kind]
        self.limits[kind] = n if cur is None else min(cur, n)

    def _add_fs(self, item: str) -> None:
        body, n = self._split_count(item)
        self.effects.add("fs")
        self._limit("fs", n)
        if body == "fs":
            self.fs = None                     # any path, either direction
            self._fs_any = True
            return
        rest = body[3:]                        # after 'fs:'
        kind, sep, path = rest.partition(":")
        if kind not in ("read", "write"):
            raise BudgetError(f"'{item}': after fs: write read or write, "
                              f"then optionally :path")
        prefix = None
        if sep:
            if not path:
                raise BudgetError(f"'{item}': the path after fs:{kind}: "
                                  f"is empty")
            # a `,` or `@` in the path arrives percent-encoded (spec v0.2
            # §5.1); decode before resolving, so the path names the file
            # it means
            prefix = os.path.normcase(os.path.realpath(_pct_decode(path)))
        if getattr(self, "_fs_any", False):
            return                             # plain fs already covers it
        if self.fs is None:
            self.fs = []
        self.fs.append((kind, prefix))

    def _add_net(self, item: str) -> None:
        body, n = self._split_count(item)
        self.effects.add("net")
        self._limit("net", n)
        if body == "net":
            self._net_any = True
            self.net = None
            return
        rest = body[4:]                        # after 'net:'
        host, port = parse_host_port(rest)
        if host.startswith("*."):
            tail = host[2:]
            if not tail or "*" in tail or "." not in tail:
                raise BudgetError(f"'{item}': the wildcard must be "
                                  f"'*.' followed by at least two labels")
            if all(lbl.isdigit() for lbl in tail.split(".")):
                raise BudgetError(f"'{item}': no wildcard over an IP "
                                  f"literal")
        elif "*" in host:
            raise BudgetError(f"'{item}': only one leading '*.' label "
                              f"is allowed")
        if getattr(self, "_net_any", False):
            return
        if self.net is None:
            self.net = []
        self.net.append((host, port))

    # ---- the other direction: back to text, and to the runtime --------
    def spec(self) -> str:
        """The budget as the command line would write it, absolute paths
        included, so a child process parses to the same budget."""
        out = []
        for e in sorted(self.effects):
            if e == "ffi":
                out.append("ffi" if self.modules is None else
                           ",".join("ffi:" + m for m in sorted(self.modules)))
            elif e == "fs":
                tail = f"@{self.limits['fs']}" if self.limits["fs"] is not None else ""
                if self.fs is None:
                    out.append("fs" + tail)
                else:
                    for kind, prefix in self.fs:
                        p = f":{_pct_encode(prefix)}" if prefix else ""
                        out.append(f"fs:{kind}" + p + tail)
            elif e == "net":
                tail = f"@{self.limits['net']}" if self.limits["net"] is not None else ""
                if self.net is None:
                    out.append("net" + tail)
                else:
                    for host, port in self.net:
                        out.append(_net_grant_text(host, port) + tail)
            else:
                out.append(e)
        return ",".join(out)

    def deny(self, names) -> None:
        for name in names:
            self.effects.discard(name)
            if name == "fs":
                self.fs = None
                self.limits["fs"] = None
            elif name == "net":
                self.net = None
                self.limits["net"] = None
            elif name == "ffi":
                self.modules = None

    def install(self) -> None:
        EFFECT_BUDGET.clear()
        EFFECT_BUDGET.update(self.effects)
        g = globals()
        g["FFI_MODULES"] = self.modules
        g["FS_GRANTS"] = None if self.fs is None else list(self.fs)
        g["NET_GRANTS"] = None if self.net is None else list(self.net)
        g["OP_LIMITS"] = dict(self.limits)
        g["OP_COUNTS"] = {"fs": 0, "net": 0}
        g["EFFECT_USES"] = {}

    @classmethod
    def current(cls) -> "Budget":
        """The budget this run is under, read back from what install()
        wrote. Nothing new is stored for it, so a pool worker has one
        less piece of state to put back between programs."""
        b = cls()
        b.effects = set(EFFECT_BUDGET)
        b.modules = FFI_MODULES
        b.fs = None if FS_GRANTS is None else list(FS_GRANTS)
        b.net = None if NET_GRANTS is None else list(NET_GRANTS)
        b.limits = dict(OP_LIMITS)
        return b

    @staticmethod
    def snapshot() -> dict:
        return {"effects": set(EFFECT_BUDGET), "modules": FFI_MODULES,
                "fs": FS_GRANTS, "net": NET_GRANTS,
                "limits": dict(OP_LIMITS), "counts": dict(OP_COUNTS),
                "uses": dict(EFFECT_USES)}

    @staticmethod
    def restore(saved: dict) -> None:
        EFFECT_BUDGET.clear()
        EFFECT_BUDGET.update(saved["effects"])
        g = globals()
        g["FFI_MODULES"] = saved["modules"]
        g["FS_GRANTS"] = saved["fs"]
        g["NET_GRANTS"] = saved["net"]
        g["OP_LIMITS"] = saved["limits"]
        g["OP_COUNTS"] = saved["counts"]
        g["EFFECT_USES"] = saved.get("uses", {})

    # ---- one budget inside another (the HTTP door's ceiling) ----------
    def covers(self, asked: "Budget") -> str | None:
        """None when everything `asked` wants sits inside this budget;
        else one sentence naming the first thing that does not."""
        for e in sorted(asked.effects):
            if e not in self.effects:
                return f"this server does not grant {e}"
        if "ffi" in asked.effects and self.modules is not None:
            if asked.modules is None:
                return "this server grants ffi for named modules only"
            extra = asked.modules - self.modules
            if extra:
                return f"this server does not grant ffi:{sorted(extra)[0]}"
        if "fs" in asked.effects:
            if self.limits["fs"] is not None and (
                    asked.limits["fs"] is None
                    or asked.limits["fs"] > self.limits["fs"]):
                return (f"this server allows at most {self.limits['fs']} "
                        f"file operations")
            if self.fs is not None:
                if asked.fs is None:
                    return "this server grants fs under named paths only"
                for kind, prefix in asked.fs:
                    if not any(_fs_grant_covers(sk, sp, kind, prefix)
                               for sk, sp in self.fs):
                        return (f"this server does not grant fs:{kind}"
                                + (f":{prefix}" if prefix else ""))
        if "net" in asked.effects:
            if self.limits["net"] is not None and (
                    asked.limits["net"] is None
                    or asked.limits["net"] > self.limits["net"]):
                return (f"this server allows at most {self.limits['net']} "
                        f"network operations")
            if self.net is not None:
                if asked.net is None:
                    return "this server grants net for named hosts only"
                for host, port in asked.net:
                    if not any(_net_grant_covers(sh, sp, host, port)
                               for sh, sp in self.net):
                        return (f"this server does not grant net:{host}"
                                + (f":{port}" if port else ""))
        return None


def parse_host_port(text: str) -> tuple:
    """'api.example.com:443' -> ('api.example.com', 443); '[::1]:80' ->
    ('::1', 80); a bare host -> (host, None). Lower-cased, no trailing
    dot."""
    text = text.strip()
    if not text:
        raise BudgetError("net: needs a host")
    port = None
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            raise BudgetError(f"'{text}': unclosed [ in an IPv6 literal")
        host = _pct_decode(text[1:end])
        if not host:
            raise BudgetError(f"'{text}': the brackets hold no address")
        rest = text[end + 1:]
        if rest:
            if not rest.startswith(":") or not _ascii_digits(rest[1:]):
                raise BudgetError(f"'{text}': expected :port after ]")
            port = int(rest[1:])
    else:
        # structure is read on the encoded text - `@` and `/` are still
        # errors as raw characters, since a host that means to hold them
        # writes them percent-encoded (spec v0.2 §5.2)
        host, sep, tail = text.rpartition(":")
        if sep and _ascii_digits(tail):
            port = int(tail)
        else:
            host = text
        if "/" in host or "@" in host or not host:
            raise BudgetError(f"'{text}': a host is a name or address, "
                              f"with an optional :port")
        if ":" in host:
            # a residual colon is an unbracketed IPv6 address; it must be
            # written net:[...] so host:port is not ambiguous (spec v0.2
            # §5.2, Q5). This is what made net:::1 mean the host ':' at
            # port 1 before 3.3.
            raise BudgetError(f"'{text}': an IPv6 address must be written "
                              f"in brackets, as net:[{host}] or "
                              f"net:[{host}]:port")
        host = _pct_decode(host)
    if port is not None and not 0 < port < 65536:
        raise BudgetError(f"'{text}': port out of range")
    return host.lower().rstrip("."), port


def _fs_grant_covers(kind: str, prefix, want_kind: str, want_prefix) -> bool:
    """Does a server's grant (kind, prefix) cover a caller's grant
    (want_kind, want_prefix)? Same direction, and the caller's prefix
    (None = any path) must sit under the server's (None = any path)."""
    if kind != want_kind:
        return False
    if prefix is None:
        return True
    if want_prefix is None:
        return False
    return (want_prefix == prefix
            or want_prefix.startswith(prefix.rstrip(os.sep) + os.sep))


def _host_matches(pattern: str, host: str) -> bool:
    if pattern.startswith("*."):
        tail = pattern[2:]
        return host.endswith("." + tail) and \
            "." not in host[:-len(tail) - 1] and len(host) > len(tail) + 1
    return pattern == host


def _net_grant_covers(host: str, port, want_host: str, want_port) -> bool:
    """Does the grant permit want_host:want_port? Both sides may be
    patterns when one budget is checked against another; a wildcard
    covers the same wildcard and any single-label host under it."""
    if port is not None and want_port != port:
        return False
    if host.startswith("*.") and want_host.startswith("*."):
        return host == want_host
    if want_host.startswith("*."):
        return False
    return _host_matches(host, want_host)


def parse_budget(spec: str) -> tuple:
    """(effects, modules) - the 2.60 shape, kept for callers that only
    want those two; the scoped grants live on Budget.parse(spec)."""
    b = Budget.parse(spec)
    return b.effects, b.modules


def _flag_value(argv: list, flag: str) -> str | None:
    """The word after `flag`, or None when the flag is absent; a flag
    written last, with nothing after it, is a budget error rather than
    an IndexError."""
    if flag not in argv:
        return None
    i = argv.index(flag)
    if i + 1 >= len(argv):
        raise BudgetError(f"{flag} needs a value after it")
    return argv[i + 1]


def cli_budget(argv: list) -> "Budget":
    """The budget a command line asks for: --allow, then --deny.

    Since 5.0, no --allow means `io` - the console and nothing else -
    where it used to mean all seven effects. --deny narrows whatever
    --allow gave, so `--deny net` no longer grants fs and ffi by the
    back door; `--allow all` is the one way to ask for everything, and
    says so on stderr when it is used.
    """
    asked = _flag_value(argv, "--allow")
    if asked is None:
        asked = DEFAULT_ALLOW
    elif asked.strip() == ALLOW_ALL:
        warn_allow_all()
    budget = Budget.parse(expand_allow(asked))
    denied = _flag_value(argv, "--deny")
    if denied is not None:
        names = [n.strip() for n in denied.split(",") if n.strip()]
        for name in names:
            if name not in ALL_EFFECTS:
                raise BudgetError(f"'{name}' is not an effect. They are: "
                                  f"{', '.join(ALL_EFFECTS)}")
        budget.deny(names)
    return budget


def allow_path(kind: str, path: str, what: str, line: int) -> str:
    """Refuse a file operation outside the paths this run granted.

    kind is 'read', 'write' or 'any' (file_exists). The path is resolved
    with realpath before the comparison, and so is every grant, so `..`
    and symlinks cannot reach past a prefix. Returns the resolved path
    the operation should use.
    """
    real = os.path.normcase(os.path.realpath(str(path)))
    if FS_GRANTS is None:
        return real
    wants = ("read", "write") if kind == "any" else (kind,)
    for gkind, prefix in FS_GRANTS:
        if gkind in wants and (prefix is None or real == prefix
                               or real.startswith(prefix.rstrip(os.sep)
                                                  + os.sep)):
            return real
    need = kind if kind != "any" else "read"
    raise VelarisError("E313",
        f"'{what}' reaches '{path}' (resolved: {real}), which this run's "
        f"fs grants do not cover", line,
        fixes=[f"allow it: --allow fs:{need}:{os.path.dirname(real) or real}",
               "or use a program that stays inside the granted paths"])


class _RedirectRefused(Exception):
    def __init__(self, target: str, why: str):
        self.target, self.why = target, why
        super().__init__(why)


def host_refusal(url: str) -> str | None:
    """Why this URL's host is outside the run's net grants, or None."""
    import urllib.parse
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return f"'{parts.scheme or '?'}' is not http or https"
    try:
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as e:
        return f"the address does not parse: {e}"
    if not host:
        return "the address has no host"
    if NET_GRANTS is None:
        return None
    for ghost, gport in NET_GRANTS:
        if _host_matches(ghost, host) and (gport is None or gport == port):
            return None
    return (f"host {host}:{port} is not in this run's net grants "
            f"(allow it: --allow net:{host}:{port})")


def allow_host(url: str, what: str, line: int) -> None:
    """Refuse a request to a host this run did not grant (E314)."""
    why = host_refusal(url)
    if why is None:
        return
    import urllib.parse
    host = (urllib.parse.urlsplit(url).hostname or "?")
    raise VelarisError("E314",
        f"'{what}' reaches host '{host}', which this run does not allow: "
        f"{why}", line,
        fixes=["or use a program that stays with the granted hosts"])


def count_op(kind: str, what: str, line: int) -> None:
    """Spend one of the run's fs or net operations (E315 past the count)."""
    limit = OP_LIMITS.get(kind)
    OP_COUNTS[kind] = OP_COUNTS.get(kind, 0) + 1
    if limit is not None and OP_COUNTS[kind] > limit:
        raise VelarisError("E315",
            f"'{what}' is the {OP_COUNTS[kind]}{_ordinal(OP_COUNTS[kind])} "
            f"{kind} operation, and this run allows {limit}", line,
            fixes=[f"allow more: --allow {kind}@{OP_COUNTS[kind]}",
                   "or use a program that does less"])


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else \
        {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def guarded_opener():
    """An opener whose redirects are held to the same net grants, and
    which refuses to leave http(s). A refused redirect is a failure the
    program can catch: it asked for one host and was sent to another."""
    import urllib.request

    class Guarded(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            why = host_refusal(newurl)
            if why is not None:
                raise _RedirectRefused(newurl, why)
            return super().redirect_request(req, fp, code, msg, headers,
                                            newurl)
    return urllib.request.build_opener(Guarded)


def allow_module(module: str, what: str, line: int) -> None:
    """Refuse a Python module this run did not grant."""
    if FFI_MODULES is None:
        return
    top = module.split(".")[0]
    if top in FFI_MODULES:
        return
    raise VelarisError("E311",
        f"'{what}' reaches into Python module '{module}', which this run "
        f"does not allow", line,
        fixes=[f"allow it: --allow ffi:{top}"
               + ("," + ",".join(sorted(FFI_MODULES)) if FFI_MODULES
                  else ""),
               "or use a program that does not need it"])


# A call into Python names a module (checked by allow_module) and then a
# dotted path of attributes reached from it. Until 3.3 only the module
# name was checked, so `py("json", "codecs.encode", ...)` ran codecs code
# under `ffi:json` - the module json imports codecs into its namespace,
# and the attribute chain walked straight into it. From 3.3 every step of
# the chain is checked: an ffi:M grant is bounded to the module actually
# reached, not merely the one named. See SPEC.md §12 and THREAT_MODEL.md.

# Inert values are data, not code from any module, and are not checked:
# returning math.pi or a JSON field reaches no module's behaviour.
_FFI_INERT = (int, float, bool, str, bytes, bytearray, type(None),
              list, tuple, dict, set, frozenset)
_FFI_UNKNOWN = object()   # owning module cannot be determined -> refuse


def _ffi_owner(obj):
    """The top-level Python package that owns `obj` as code, `None` when
    `obj` is inert data, or `_FFI_UNKNOWN` when it cannot be told.

    Determining this soundly matters: the check refuses more rather than
    less, so anything whose owner cannot be placed - a bare code object,
    a frame, a reflective handle - is _FFI_UNKNOWN and is refused, not
    allowed. A builtin method carries `__module__` `None` but is bound to
    a class or module through `__self__`/`__objclass__`, which is where
    its code lives; that is consulted before the object's own type, so
    `datetime.date.today` is placed in `datetime`, not in `builtins`.
    """
    import types
    if isinstance(obj, types.ModuleType):
        name = getattr(obj, "__name__", None)
        return name.split(".")[0] if name else _FFI_UNKNOWN
    if isinstance(obj, _FFI_INERT):
        return None
    m = getattr(obj, "__module__", None)
    if isinstance(m, str) and m:
        return m.split(".")[0]
    # a builtin or bound method: the class or module it belongs to holds
    # the code, even when the method object itself reports no __module__
    for attr in ("__self__", "__objclass__"):
        holder = getattr(obj, attr, None)
        if holder is None:
            continue
        if isinstance(holder, types.ModuleType):
            n = getattr(holder, "__name__", None)
            if n:
                return n.split(".")[0]
        hm = getattr(holder, "__module__", None)
        if not (isinstance(hm, str) and hm):
            hm = getattr(type(holder), "__module__", None)
        if isinstance(hm, str) and hm:
            return hm.split(".")[0]
    # a foreign instance names its home in its type; a builtins-typed
    # object with no __module__ of its own (a code object, a frame, a
    # range) is not inert data we recognise, so it cannot be placed
    tm = getattr(type(obj), "__module__", None)
    if isinstance(tm, str) and tm and tm != "builtins":
        return tm.split(".")[0]
    return _FFI_UNKNOWN


def ffi_reach(obj, what: str, line: int, described: str) -> None:
    """Refuse (E311) when `obj` - a step in the attribute chain a call
    names, an attribute read through a handle, or a non-JSON result kept
    as a handle - is code owned by a module outside this run's ffi
    grants, naming the module actually reached. Inert data is allowed;
    an owner that cannot be determined is refused."""
    if FFI_MODULES is None:
        return
    owner = _ffi_owner(obj)
    if owner is None:
        return
    granted = ",".join(sorted(FFI_MODULES))
    if owner is _FFI_UNKNOWN:
        raise VelarisError("E311",
            f"'{what}' reaches {described}, whose owning Python module "
            f"cannot be determined; this run allows ffi:{granted} and "
            f"refuses what it cannot place", line,
            fixes=["name the module the object comes from directly",
                   "or use a program that does not reach it this way"])
    if owner not in FFI_MODULES:
        raise VelarisError("E311",
            f"'{what}' reaches into Python module '{owner}' (via "
            f"{described}), which this run does not allow", line,
            fixes=[f"allow it: --allow ffi:{owner}"
                   + ("," + granted if FFI_MODULES else ""),
                   "or use a program that does not need it"])


def _ffi_resolve(module: str, func, name: str, line: int):
    """Import the module a call names (allow_module checks the name) and
    walk the attribute chain to the target it calls, checking the owning
    module of every step (ffi_reach). One place for all three py* import
    sites, so the chain is checked the same way for each."""
    import importlib
    mod, rest = None, ""
    parts = str(module).split(".")
    for cut in range(len(parts), 0, -1):      # datetime.date works:
        try:                                  # import what imports,
            allow_module(".".join(parts[:cut]), name, line)
            mod = importlib.import_module(".".join(parts[:cut]))
            rest = ".".join(parts[cut:])      # reach the rest by name
            break
        except ImportError:
            continue
    if mod is None:
        raise FailSignal(f"cannot import '{module}'")
    target = mod
    for part in ([p for p in rest.split(".") if p]
                 + [p for p in str(func).split(".") if p]):
        nxt = getattr(target, part, None)
        if nxt is None:
            raise FailSignal(f"'{module}' has no '{func}'")
        ffi_reach(nxt, name, line, f"attribute '{part}'")
        target = nxt
    return target


def spend(effect: str, what: str, line: int) -> None:
    """Refuse an effect the person running this did not allow.

    The compiler checks that a function declares what it does. This is
    the other half: the runtime refuses anything outside the budget
    given on the command line, whatever the source says about itself -
    so you can run a program you have not read.
    """
    if effect in EFFECT_BUDGET:
        EFFECT_USES[effect] = EFFECT_USES.get(effect, 0) + 1
        return
    # Since 5.0 a run with no --allow gets io, so this is the first
    # thing many people meet after upgrading. It has to name the effect,
    # say what the run does allow, and give the flag that grants it -
    # the whole flag, with what was already granted kept.
    have = Budget.current().spec()
    wider = f"{have},{effect}" if have else effect
    raise VelarisError("E310",
        f"'{what}' needs the '{effect}' effect, which this run does not "
        f"allow (it allows: {have or 'nothing'})", line,
        fixes=[f"allow it: velaris <file> --allow {wider}",
               f"a run with no --allow gets {DEFAULT_ALLOW} (5.0); "
               f"--allow all grants every effect",
               "or use a program that does not need it"])

INT_MIN, INT_MAX = -(2 ** 63), 2 ** 63 - 1

TRACE = {"on": False, "depth": 0, "calls": 0, "limit": 4000}


REDACTED = "<secret>"      # what a trace and a broken promise print in
                           # place of a value the type system calls secret


def trace_enter(name: str, params, args, secret=()) -> None:
    if not TRACE["on"] or TRACE["calls"] >= TRACE["limit"]:
        return
    TRACE["calls"] += 1
    shown = ", ".join(
        f"{p}=" + (REDACTED if p in secret else to_text(a))
        for (p, _), a in zip(params, args))
    print("  " * TRACE["depth"] + f"-> {name}({shown})", file=sys.stderr)
    TRACE["depth"] += 1


def trace_leave(name: str, value, failed: str | None = None,
                secret: bool = False) -> None:
    if not TRACE["on"] or TRACE["calls"] > TRACE["limit"]:
        return
    TRACE["depth"] = max(0, TRACE["depth"] - 1)
    if failed is not None:
        print("  " * TRACE["depth"] + f"<- {name} FAILED: {failed}",
              file=sys.stderr)
    elif value is None:
        print("  " * TRACE["depth"] + f"<- {name}", file=sys.stderr)
    else:
        print("  " * TRACE["depth"] + f"<- {name} = "
              + (REDACTED if secret else to_text(value)), file=sys.stderr)


def checked_int(value: int, op: str, line: int) -> int:
    """Whole numbers are 64-bit. Outgrowing that is an error, because
    the alternative is native code wrapping while the interpreter keeps
    counting - two engines, two answers, and no way to know which."""
    if isinstance(value, int) and not INT_MIN <= value <= INT_MAX:
        raise VelarisError("E407",
            f"this '{op}' made a number too big to hold "
            f"(whole numbers go from {INT_MIN} to {INT_MAX})", line,
            fixes=["keep the numbers smaller",
                   "or work in smaller units, like cents instead of "
                   "rupees"])
    if value.__class__ is MoneyValue and \
            not INT_MIN <= value.units <= INT_MAX:
        raise VelarisError("E407",
            f"this '{op}' made an amount too big to hold (an amount is "
            f"{INT_MIN} to {INT_MAX} minor units)", line,
            fixes=["an amount is held exactly, in 64 bits of minor "
                   "units; one this large is almost certainly a bug"])
    return value

def _z3_installed() -> bool:
    """Is the prover available, without paying ~350ms to import it?

    importlib.util.find_spec only locates the package; z3 itself is
    imported when a proof actually starts. Programs with no contracts
    - and every run of a cached-proof program - never pay for it.
    """
    try:
        import importlib.util
        return importlib.util.find_spec("z3") is not None
    except Exception:
        return False


HAVE_Z3 = _z3_installed()

BUILTINS = {
    # name          effects needed      argument types        returns
    "log":        {"effects": {"io"},     "types": ["Any"],         "ret": "Unit"},
    "print":      {"effects": {"io"},    "types": ["Any"],         "ret": "Unit"},
    "read_file":  {"effects": {"fs"},    "types": ["Text"],        "ret": "Text"},
    "write_file": {"effects": {"fs"},    "types": ["Text", "Any"], "ret": "Unit"},
    "fetch":      {"effects": {"net"},   "types": ["Text"],        "ret": "Text"},
    "now":        {"effects": {"clock"}, "types": [],              "ret": "Int"},
    "random":     {"effects": {"rand"},  "types": ["Int"],         "ret": "Int"},
    "ask":        {"effects": {"io"},     "types": ["Text"],        "ret": "Text"},
    # pure helpers (no effects) - usable everywhere, including promises
    "to_int":     {"effects": set(),      "types": ["Text"],        "ret": "Int"},
    "to_text":    {"effects": set(),      "types": ["Any"],         "ret": "Text"},
    "to_float":   {"effects": set(),      "types": ["Int"],         "ret": "Float"},
    "round":      {"effects": set(),      "types": ["Float"],       "ret": "Int"},
    "contains":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Bool"},
    "split":      {"effects": set(),      "types": ["Text", "Text"], "ret": "List of Text"},
    "upper":      {"effects": set(),      "types": ["Text"],        "ret": "Text"},
    "chars":      {"effects": set(),      "types": ["Text"],        "ret": "List of Text"},
    "file_exists": {"effects": {"fs"},    "types": ["Text"],        "ret": "Bool"},
    "put":        {"effects": set(),      "types": ["Any", "Any", "Any"], "ret": "Any"},
    "get_or":     {"effects": set(),      "types": ["Any", "Any", "Any"], "ret": "Any"},
    "code_at":    {"effects": set(),      "types": ["Text", "Int"], "ret": "Int"},
    "py":         {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Text"},
    "py_int":     {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Int"},
    "py_float":   {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Float"},
    "py_json":    {"effects": {"ffi"},    "types": ["Text", "Text", "Text"], "ret": "Text"},
    "py_new":     {"effects": {"ffi"},    "types": ["Text", "Text", "Text"], "ret": "Handle"},
    "py_do":      {"effects": {"ffi"},    "types": ["Handle", "Text", "Text"], "ret": "Text"},
    "py_field":   {"effects": {"ffi"},    "types": ["Handle", "Text"], "ret": "Text"},
    "py_close":   {"effects": {"ffi"},    "types": ["Handle"],       "ret": "Unit"},
    "json_get":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Text"},
    "json_int":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Int"},
    "json_float": {"effects": set(),      "types": ["Text", "Text"], "ret": "Float"},
    "json_len":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Int"},
    "json_has":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Bool"},
    "json_of":    {"effects": set(),      "types": ["Any"],          "ret": "Text"},
    "args":       {"effects": {"io"},     "types": [],              "ret": "List of Text"},
    "env":        {"effects": {"env"},    "types": ["Text", "Text"],
                   "ret": "Secret of Text"},
    "exit_with":  {"effects": {"io"},     "types": ["Int"],         "ret": "Unit"},
    "read_line":  {"effects": {"io"},     "types": [],              "ret": "Text"},
    "post":       {"effects": {"net"},    "types": ["Text", "Text"], "ret": "Text"},
    "fetch_status": {"effects": {"net"},  "types": ["Text"],        "ret": "Int"},
    "request":    {"effects": {"net"},    "types": ["Text", "Text", "Text", "Text"], "ret": "Text"},
    "format":     {"effects": set(),      "types": ["Any"],         "ret": "Text"},
    "has":        {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "keys":       {"effects": set(),      "types": ["Any"],         "ret": "Any"},
    "all_of":     {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "any_of":     {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "lower":      {"effects": set(),      "types": ["Text"],        "ret": "Text"},
    "length":     {"effects": set(),      "types": ["Any"],         "ret": "Int"},
    "push":       {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
    "pop":        {"effects": set(),      "types": ["Any"],         "ret": "Any"},
    "slice":      {"effects": set(),      "types": ["Any", "Int", "Int"], "ret": "Any"},
    "set_at":     {"effects": set(),      "types": ["Any", "Int", "Any"], "ret": "Any"},
    "add_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "div_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "mod_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "sub_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "mul_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "get":        {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
    # Money (4.3), all pure. Their types are checked by their own rules
    # in check_types, because an amount's currency is part of its type;
    # these rows are what the docs and the editor show.
    "money":      {"effects": set(), "types": ["Int", "Text"],
                   "ret": "Money of that currency"},
    "units_of":   {"effects": set(), "types": ["Money of C, or List of Money of C"],
                   "ret": "Int"},
    "with_units": {"effects": set(), "types": ["Money of C", "Int"],
                   "ret": "Money of C"},
    "percent_of": {"effects": set(),
                   "types": ["Money of C", "Int", "Int", "Text"],
                   "ret": "Money of C"},
    "divide_or_fail": {"effects": set(),
                       "types": ["Money of C", "Int", "Text"],
                       "ret": "Money of C"},
    "text_of":    {"effects": set(), "types": ["Money of C"], "ret": "Text"},
    "parse_money": {"effects": set(), "types": ["Text", "Text"],
                    "ret": "Money of that currency"},
    # Secret (6.0). read_file_secret reads a file the way read_file
    # does and calls what it read a secret; declassify is the only way
    # out of Secret, and its types are checked by their own rule in
    # check_types because the result is the argument's inner type.
    "read_file_secret": {"effects": {"fs"}, "types": ["Text"],
                         "ret": "Secret of Text"},
    "declassify": {"effects": {"declassify"},
                   "types": ["Secret of T", "Text"], "ret": "T"},
}

KNOWN_TYPES = {"Int", "Text", "Bool", "Float", "Handle"}

# ---- Money (4.3) ------------------------------------------------------------
# An amount is a whole number of minor units - paise, cents - and a
# currency. It is an Int underneath, so it is exact and it proves the way
# an Int proves; its currency is part of its type, so an amount in INR
# never meets one in USD; and no Float is part of anything it does
# (SPEC.md 4.3, and 4.4 for the currency table).

# ISO 4217 code -> digits after the point. Not every currency: the ones
# a program here has needed. Adding one is a line here, with the minor
# unit ISO 4217 gives it, and a case in check_money.py. A program cannot
# add its own, because two programs that disagreed about how many digits
# a currency has would print the same amount two ways.
CURRENCIES = {
    "AED": 2, "AUD": 2, "BHD": 3, "BRL": 2, "CAD": 2, "CHF": 2,
    "CNY": 2, "EUR": 2, "GBP": 2, "HKD": 2, "INR": 2, "JOD": 3,
    "JPY": 0, "KRW": 0, "KWD": 3, "MXN": 2, "OMR": 3, "SAR": 2,
    "SGD": 2, "USD": 2, "ZAR": 2,
}

# how a division that does not come out even is rounded; always named in
# the call, never assumed. half_up takes a half away from zero, half_even
# to the even neighbour, down toward zero.
ROUNDING = ("half_up", "half_even", "down")

MONEY_BUILTINS = frozenset({"money", "units_of", "with_units", "percent_of",
                            "divide_or_fail", "text_of", "parse_money"})

# Builtins added from 4.3 on give way to a function of the same name that
# a program defines (SPEC.md 10.1). A program written before a builtin
# existed can have used its name, and a minor version must not change
# what that program means. The older builtins keep the precedence they
# always had.
SECRET_BUILTINS = frozenset({"read_file_secret", "declassify"})

# Builtins that hand back a Secret. The audit's secrets.sources lists
# the ones a program reaches (velaris-spec 8.6).
SECRET_SOURCES = ("env", "read_file_secret")

NEW_BUILTINS = MONEY_BUILTINS | SECRET_BUILTINS


def builtin_reached(name: str, table) -> str | None:
    """The builtin a call to `name` reaches in this program, or None when
    it reaches a function of the program's own. `table` is the program's
    functions by name. A call written '@name' was bound to the builtin
    when the program was loaded (_bind_new_builtins)."""
    if name[:1] == "@":
        return name[1:]
    if name in NEW_BUILTINS and table and name in table:
        return None
    return name if name in BUILTINS else None


def shown_name(name: str) -> str:
    """A call's name as the program wrote it."""
    return name[1:] if name[:1] == "@" else name


def is_money(t: str) -> bool:
    return t.startswith("Money of ")


def currency_clash(a: str, b: str) -> bool:
    """Two types that differ only in the currency of an amount: Money of
    INR and Money of USD, or lists, maps or secrets of them."""
    if a.startswith(SECRET_PREFIX) and b.startswith(SECRET_PREFIX):
        return currency_clash(secret_inner(a), secret_inner(b))
    if is_money(a) and is_money(b):
        return a != b
    if a.startswith("List of ") and b.startswith("List of "):
        return currency_clash(a[8:], b[8:])
    if a.startswith("Map of ") and b.startswith("Map of "):
        ak, _, av = a[7:].partition(" to ")
        bk, _, bv = b[7:].partition(" to ")
        return ak == bk and currency_clash(av, bv)
    return False


def clash_error(want: str, got: str, line: int, what: str = "") -> VelarisError:
    return VelarisError("E550",
        (what or "this") + f" is {got}, where {want} is needed - amounts "
        f"in two currencies do not mix", line,
        fixes=["convert on purpose: a rate and a rounding mode are a "
               "program's decision, so there is no conversion builtin",
               "or keep both sides in one currency"])


def _outside_money(t: str, tv: str) -> bool:
    """Does type t mention type variable tv anywhere other than as the
    currency of an amount?"""
    if t == tv:
        return True
    if is_money(t):
        return False
    if t.startswith(SECRET_PREFIX):
        return _outside_money(secret_inner(t), tv)
    if t.startswith("List of "):
        return _outside_money(t[8:], tv)
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return _outside_money(k, tv) or _outside_money(v, tv)
    sig = fn_sig_parts(t)
    if sig is not None:
        parts, ret = sig
        return any(_outside_money(p, tv) for p in parts) or \
            _outside_money(ret, tv)
    return False


def currency_generic(fn) -> bool:
    """True when every type variable of fn stands only for the currency
    of an amount. Such a function means the same to the prover whatever
    the currency, since an amount is its minor units there."""
    types = [t for _, t in fn.params] + [fn.return_type or "Unit"]
    return bool(fn.type_vars) and not any(
        _outside_money(t, tv) for tv in fn.type_vars for t in types)


def erase_wrappers(t: str) -> str:
    """The prover's view of a type: an amount is its minor units, an
    Int, and a secret is whatever it wraps. The type checker has already
    kept every currency apart and kept every secret away from a sink, so
    neither distinction means anything to the solver - a Secret of Int
    proves exactly as an Int does."""
    if t.startswith("Secret of "):
        return erase_wrappers(t[len("Secret of "):])
    if is_money(t):
        return "Int"
    if t.startswith("List of "):
        return "List of " + erase_wrappers(t[8:])
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return f"Map of {k} to {erase_wrappers(v)}"
    return t


# ---- Secret (6.0) -----------------------------------------------------------
# A value the type system tracks so that it cannot reach anything that
# emits it. `Secret of T` wraps any T; it is made by env() and
# read_file_secret(), it survives every pure operation over it, and
# declassify() - which needs the `declassify` effect and a written
# reason - is the only way out. SPEC.md 3.1 states the rules; this is
# the type-level half of them.

SECRET_PREFIX = "Secret of "


def is_secret(t: str) -> bool:
    return t.startswith(SECRET_PREFIX)


def secret_inner(t: str) -> str:
    return t[len(SECRET_PREFIX):]


def wrap_secret(t: str) -> str:
    """A result derived from a secret is a secret. No exceptions - a
    Bool least of all. A comparison is not a one-bit channel: with
    `length` and a loop, `secret == c` reads the value out character by
    character, and a program that could print that Bool could print the
    whole key. So a Bool derived from a Secret is a `Secret of Bool`,
    which nothing prints and nothing branches on (E560, E563), and
    `declassify` is what a program writes when it means to act on one.
    SPEC.md 3.1 states the choice. `Unit` is not a value.

    `Secret of Secret of T` is the same secret, so a type that already
    carries one is left alone."""
    if t in ("Unit", "") or carries_secret(t):
        return t
    return SECRET_PREFIX + t


def strip_secret(t: str) -> str:
    """The type underneath, with every Secret wrapper removed and
    everything else - an amount's currency above all - left alone."""
    if t.startswith(SECRET_PREFIX):
        return strip_secret(secret_inner(t))
    if t.startswith("List of "):
        return "List of " + strip_secret(t[8:])
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return f"Map of {k} to {strip_secret(v)}"
    return t


def carries_secret(t: str, records=None) -> bool:
    """Does a value of this type hold a secret anywhere inside it?

    A list of secrets, a map whose values are secrets and a record with
    a secret field all answer yes, so a structure cannot be used to
    smuggle one past the sink check. `records` maps a record name to
    whether it carries one; without it a record name answers no, which
    is only right where records cannot appear."""
    if t.startswith(SECRET_PREFIX):
        return True
    if t.startswith("List of "):
        return carries_secret(t[8:], records)
    if t.startswith("Map of "):
        return carries_secret(t[7:].partition(" to ")[2], records)
    sig = fn_sig_parts(t)
    if sig is not None:
        # A function value is a name, not the values it would return:
        # printing one prints nothing a caller did not already have,
        # and it cannot be called without its result being checked
        # where it is used. Its parameter and result types are not
        # walked for that reason.
        return False
    return bool(records) and bool(records.get(t))


def records_carrying(records) -> dict:
    """Which record types hold a secret, directly or through another
    record, a list or a map. A fixpoint, so a record that holds a list
    of records that hold a secret is one too."""
    carry = {r.name: False for r in records}
    changed = True
    while changed:
        changed = False
        for r in records:
            if carry[r.name]:
                continue
            if any(carries_secret(ft, carry) for _, ft in r.fields):
                carry[r.name] = True
                changed = True
    return carry


@dataclass(frozen=True, order=True, slots=True)
class MoneyValue:
    """An amount while running: minor units and a currency. Ordering and
    equality compare units within one currency, which is the only kind
    of comparison the type checker lets through."""
    units: int
    currency: str

    def _same(self, other) -> None:
        if other.currency != self.currency:   # kept out before running;
            raise VelarisError("E550",        # this is the second lock
                f"an amount in {self.currency} met one in "
                f"{other.currency}", 0)

    def __add__(self, other):
        if other.__class__ is not MoneyValue:
            return NotImplemented
        self._same(other)
        return MoneyValue(self.units + other.units, self.currency)

    def __sub__(self, other):
        if other.__class__ is not MoneyValue:
            return NotImplemented
        self._same(other)
        return MoneyValue(self.units - other.units, self.currency)

    def __mul__(self, other):
        if other.__class__ is not int:
            return NotImplemented
        return MoneyValue(self.units * other, self.currency)

    __rmul__ = __mul__

    def __neg__(self):
        return MoneyValue(-self.units, self.currency)

    def __str__(self) -> str:
        return money_text(self)


def money_text(m: "MoneyValue") -> str:
    """INR 12.50, JPY 1250, KWD 1.250, INR -0.05: the code, then the
    amount with exactly as many digits after the point as the currency
    has minor units."""
    digits = CURRENCIES.get(m.currency, 0)
    sign = "-" if m.units < 0 else ""
    whole = abs(m.units)
    if digits == 0:
        return f"{m.currency} {sign}{whole}"
    major, minor = divmod(whole, 10 ** digits)
    return f"{m.currency} {sign}{major}.{minor:0{digits}d}"


_MONEY_TEXT = re.compile(r"(?:([A-Z]{3}) *)?(-)?([0-9]+)(?:\.([0-9]+))?")


def parse_money_text(text: str, currency: str) -> "MoneyValue":
    """The amount a text names, in `currency`, or a FailSignal saying
    why it names none. Takes what money_text writes, and the same
    without the code or with fewer digits after the point: 12.50, 12.5,
    12, -3.05, INR 12.50. Refuses more digits than the currency has
    (that would round), separators, signs other than a leading minus,
    and an amount too big for 64 bits."""
    t = str(text).strip(" \t\r\n")
    m = _MONEY_TEXT.fullmatch(t)
    if not m:
        raise FailSignal(f"'{text}' is not an amount like 12.50")
    code, minus, whole, frac = m.groups()
    if code is not None and code != currency:
        raise FailSignal(f"'{text}' is in {code}, not {currency}")
    digits = CURRENCIES[currency]
    if frac is not None and digits == 0:
        raise FailSignal(f"'{text}' has digits after the point, and "
                         f"{currency} has no minor unit")
    if frac is not None and len(frac) > digits:
        raise FailSignal(f"'{text}' has {len(frac)} digits after the "
                         f"point, and {currency} has {digits}")
    whole = whole.lstrip("0") or "0"
    if len(whole) > 19:                        # before int(): 10**4300
        raise FailSignal(f"'{text}' is too big to hold")   # digits of
    units = int(whole) * 10 ** digits + int((frac or "").ljust(digits, "0")
                                            or "0")      # input is not
    if minus:                                             # a number
        units = -units
    if not INT_MIN <= units <= INT_MAX:
        raise FailSignal(f"'{text}' is too big to hold")
    return MoneyValue(units, currency)


def round_ratio(p: int, q: int, mode: str) -> int:
    """p / q, exactly, rounded to a whole number by `mode`. q != 0.
    The prover's formulas for percent_of are this, in Z3's integers."""
    if q < 0:
        p, q = -p, -q
    f, r = divmod(p, q)              # floor, and 0 <= r < q
    if r == 0:
        return f
    if mode == "down":               # toward zero
        return f if p >= 0 else f + 1
    if 2 * r > q:
        return f + 1
    if 2 * r < q:
        return f
    if mode == "half_up":            # a half goes away from zero
        return f + 1 if p >= 0 else f
    return f if f % 2 == 0 else f + 1    # half_even

def local_names_of(fn: Function) -> set[str]:
    out = {p for p, _ in fn.params}

    def gather(stmts):
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                gather(s.then); gather(s.other)
            elif isinstance(s, While):
                gather(s.body)
            elif isinstance(s, Check):
                if s.ok_name:
                    out.add(s.ok_name)
                out.add(s.fail_name)
                gather(s.ok_body); gather(s.fail_body)
    gather(fn.body)
    return out


def check_effects(funcs: list[Function], errors: list) -> None:
    table = {f.name: f for f in funcs}

    def effects_of_callee(name: str, line: int) -> set[str]:
        builtin = builtin_reached(name, table)
        if builtin is not None:
            return BUILTINS[builtin]["effects"]
        if name in table:
            return table[name].effects
        raise unknown_function(name, line, table)

    locals_cache: dict[str, set] = {}

    def walk(node, fn: Function):
        if isinstance(node, Call):
            if fn.name not in locals_cache:
                locals_cache[fn.name] = local_names_of(fn)
            if node.name in locals_cache[fn.name]:
                for a in node.args:          # a passed-in function is pure
                    walk(a, fn)
                return
            needed = effects_of_callee(node.name, node.line)
            missing = needed - fn.effects
            if missing == {"env"} and node.name == "env":
                # since 3.0 the environment is its own effect, so an
                # io-only budget cannot read secrets; the message says
                # exactly what changed
                raise VelarisError(
                    "E300", "env() now needs 'uses env'", node.line,
                    fixes=[f"add 'uses env' to the signature of "
                           f"'{fn.name}' (and to every function that "
                           f"calls it)",
                           "run it with --allow io,env, or drop the "
                           "env() call"])
            if missing:
                eff = ", ".join(sorted(missing))
                declared = ("declares no effects (it is pure)" if not fn.effects
                            else f"only declares 'uses {', '.join(sorted(fn.effects))}'")
                raise VelarisError(
                    "E300",
                    f"function '{fn.name}' calls '{node.name}' which needs "
                    f"effect '{eff}', but '{fn.name}' {declared}",
                    node.line,
                    fixes=[f"add 'uses {eff}' to the signature of '{fn.name}'",
                           f"remove the call to '{node.name}'"],
                )
            for a in node.args:
                walk(a, fn)
        elif isinstance(node, BinOp):
            walk(node.left, fn); walk(node.right, fn)
        elif isinstance(node, (Let, Return, ExprStmt, FailStmt)):
            inner = node.expr if isinstance(node, ExprStmt) else node.value
            if inner is not None:
                walk(inner, fn)
        elif isinstance(node, TryExpr):
            walk(node.value, fn)
        elif isinstance(node, Check):
            walk(node.subject, fn)
            for s in node.ok_body + node.fail_body:
                walk(s, fn)
        elif isinstance(node, If):
            walk(node.cond, fn)
            for s in node.then + node.other:
                walk(s, fn)
        elif isinstance(node, While):
            walk(node.cond, fn)
            for inv_expr, _ in node.invariants:
                walk_pure(inv_expr, fn, "invariant")
            for s in node.body:
                walk(s, fn)
        elif isinstance(node, Assign):
            walk(node.value, fn)
        elif isinstance(node, (Not, Neg)):
            walk(node.value, fn)
        elif isinstance(node, ListLit):
            for it in node.items:
                walk(it, fn)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                walk(k, fn); walk(v, fn)
        elif isinstance(node, FieldGet):
            walk(node.obj, fn)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                walk(v, fn)

    def walk_pure(node, fn: Function, where: str):
        if isinstance(node, Call):
            if fn.name not in locals_cache:
                locals_cache[fn.name] = local_names_of(fn)
            if node.name in locals_cache[fn.name]:
                for a in node.args:
                    walk_pure(a, fn, where)
                return
            eff = effects_of_callee(node.name, node.line)
            if eff:
                raise VelarisError("E310",
                    f"the '{where}' promise of '{fn.name}' calls "
                    f"'{node.name}' which has effects "
                    f"({', '.join(sorted(eff))}); promises must be pure",
                    node.line,
                    fixes=["only use pure functions and math inside promises"])
            for a in node.args:
                walk_pure(a, fn, where)
        elif isinstance(node, BinOp):
            walk_pure(node.left, fn, where)
            walk_pure(node.right, fn, where)
        elif isinstance(node, (Not, Neg)):
            walk_pure(node.value, fn, where)
        elif isinstance(node, TryExpr):
            raise VelarisError("E310",
                f"the '{where}' promise of '{fn.name}' uses 'try'; "
                f"promises must be simple and pure", node.line,
                fixes=["only use plain values and pure functions in promises"])
        elif isinstance(node, ListLit):
            for it in node.items:
                walk_pure(it, fn, where)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                walk_pure(k, fn, where); walk_pure(v, fn, where)
        elif isinstance(node, FieldGet):
            walk_pure(node.obj, fn, where)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                walk_pure(v, fn, where)

    for fn in funcs:
        try:
            # a uses clause names effects, and only the seven exist. Until
            # 3.3 any identifier was accepted: `uses io, teleport`
            # compiled, reached velaris.audit/1's effects, and made its
            # safe_command a budget that does not parse (spec Q1). An
            # unknown name is now a compile error naming the seven.
            unknown = [e for e in sorted(fn.effects) if e not in ALL_EFFECTS]
            if unknown:
                raise VelarisError("E300",
                    f"function '{fn.name}' declares '{unknown[0]}', which "
                    f"is not an effect; the effects are "
                    f"{', '.join(ALL_EFFECTS)}", fn.line,
                    fixes=[f"remove '{unknown[0]}' from the uses clause",
                           f"or use one of: {', '.join(ALL_EFFECTS)}"])
            for stmt in fn.body:
                walk(stmt, fn)
            for expr, _ in fn.requires:
                walk_pure(expr, fn, "requires")
            for expr, _ in fn.ensures:
                walk_pure(expr, fn, "ensures")
        except VelarisError as e:
            errors.append(blame(fn, e))


# ---------------------------------------------------------------------------
# 4b. TYPE CHECKER — catch wrong-type bugs before the program ever runs
#     Types: Int, Text, Bool.  "Unit" means "returns nothing".
# ---------------------------------------------------------------------------

def check_main(funcs: list, errors: list, *, running: bool = True) -> None:
    """main must exist (when running), take nothing, declare no failure.

    `velaris check library.vel` checks a library as a library - a
    missing main is only an error for the file being run."""
    mains = [f for f in funcs if f.name == "main"]
    if not mains:
        if running:
            errors.append(VelarisError("E400",
                "there is no 'main' - a program needs somewhere to start",
                1, fixes=["add one: fn main() uses io { ... }"]))
        return
    m = mains[0]
    if m.params:
        errors.append(VelarisError("E401",
            f"'main' takes no parameters, but this one asks for "
            f"{len(m.params)}", m.line,
            fixes=["read the command line with args() instead"]))
    if getattr(m, "can_fail", False):
        errors.append(VelarisError("E523",
            "'main' cannot fail - there is nobody above it to catch",
            m.line,
            fixes=["handle failures inside main with check",
                   "or exit_with(1) when something goes wrong"]))


def check_types(funcs: list[Function], records: list, errors: list) -> None:
    table = {f.name: f for f in funcs}
    rec = {}
    for r in records:
      try:
        if r.name in rec:
            raise VelarisError("E507", f"record '{r.name}' is defined twice",
                               r.line, fixes=["rename one of them"])
        if r.name in table:
            raise VelarisError("E507",
                f"'{r.name}' is used for both a record and a function",
                r.line, fixes=["rename one of them"])
        seen = set()
        for fname, _ in r.fields:
            if fname in seen:
                raise VelarisError("E507",
                    f"record '{r.name}' has field '{fname}' twice", r.line,
                    fixes=["remove the duplicate field"])
            seen.add(fname)
        rec[r.name] = dict(r.fields)
      except VelarisError as e:
        errors.append(blame(r, e))

    # ---- Secret (6.0) ----------------------------------------------------
    # Which records hold a secret, so that a structure cannot smuggle one
    # past the sink check, and `carries` in terms of it.
    rec_carries = records_carrying(records)

    def carries(t: str) -> bool:
        return carries_secret(t, rec_carries)

    def sink_builtin(name: str) -> str | None:
        """The name of the emitting builtin this call reaches, or None.
        A builtin that declares an effect is one: it hands what it is
        given to the console, a file, a host, Python or the operating
        system. declassify is the exception - taking a Secret is what it
        is for - and it says so in a signature and in the audit."""
        b = builtin_reached(name, table)
        if b is None or b == "declassify":
            return None
        return b if BUILTINS[b]["effects"] else None

    def secret_enters(name: str, seen=None):
        """Where the secret a function hands back first enters the
        program, as 'env(), line 4' - following one call at a time
        through the program's own functions. None when it cannot be
        told, which is no worse than the name of the function itself."""
        import dataclasses as _dc
        seen = set() if seen is None else seen
        f = table.get(name)
        if f is None or name in seen:
            return None
        seen.add(name)
        found = [None]

        def walk(n):
            if found[0] is not None:
                return
            if isinstance(n, (list, tuple)):
                for x in n:
                    walk(x)
                return
            if not _dc.is_dataclass(n):
                return
            if isinstance(n, Call):
                b = builtin_reached(n.name, table)
                if b in SECRET_SOURCES:
                    found[0] = f"{b}(), line {n.line}"
                    return
                deeper = table.get(n.name)
                if deeper is not None and carries(deeper.return_type or ""):
                    got = secret_enters(n.name, seen)
                    if got:
                        found[0] = got
                        return
            for fl in _dc.fields(n):
                walk(getattr(n, fl.name))

        walk(f.body)
        return found[0]

    def tattling_builtin(name: str) -> str | None:
        """The fallible builtin this call reaches, or None.

        A failure's reason is Text the program may print, and the
        runtime writes it out of the values it was given - `to_int` and
        `parse_money` quote the text they could not read, and
        `divide_or_fail` the amount it could not divide. Nothing at run
        time knows which of those values the type system called secret,
        so the compiler keeps secrets away from all of them. `get` on a
        map is not one: its reason names the key, and a key is Text or
        Int, never a Secret."""
        b = builtin_reached(name, table)
        return b if b in FALLIBLE_BUILTINS else None

    def leak(what: str, where: str, t: str, origin: str,
             line: int) -> VelarisError:
        return VelarisError("E560",
            f"{what} is {t}, and {where} - a Secret cannot be printed, "
            f"written, sent or passed to Python. It came from {origin}",
            line,
            fixes=["build what you emit out of values that are not "
                   "secret",
                   'or let it out on purpose: declassify(x, "why this '
                   'is safe to emit") needs "uses declassify", is named '
                   'in the audit with that reason, and an operator can '
                   'refuse to grant it'])

    def no_secret_branch(kind: str, t: str, node, origin: str) -> None:
        """A program does not branch on a secret (6.1, SPEC.md 3.1).

        A comparison over a secret gives a `Secret of Bool`, and this is
        why: with `length` and a loop, `key == c` is not one bit, it is
        a character-by-character oracle that reads the whole key out and
        can then print it. So the branch is where the line is drawn, and
        `declassify` is what a program writes when it means to cross
        it - in the signature, in the audit, and in the operator's
        budget."""
        if not carries(t):
            return
        raise VelarisError("E563",
            f"'{kind}' would branch on {t}, which came from {origin} - "
            f"a program does not choose what to do by looking at a "
            f"secret. A comparison over one gives a Secret of Bool "
            f"exactly so that this is refused: in a loop it would read "
            f"the secret out a character at a time", node.line,
            fixes=['say so and branch on the answer: '
                   'declassify(key == "", "whether a key is set is not '
                   'the key") needs "uses declassify", is named in the '
                   'audit with that reason, and an operator can refuse '
                   'to grant it',
                   "or decide without looking: build what you do out of "
                   "values that are not secret"])

    def callee_sig(name: str, line: int = 1) -> tuple[list[str], str]:
        builtin = builtin_reached(name, table)
        if builtin is not None:
            return BUILTINS[builtin]["types"], BUILTINS[builtin]["ret"]
        if name not in table:
            raise unknown_function(name, line, table)
        f = table[name]
        return [t for _, t in f.params], (f.return_type or "Unit")

    def valid_type(t: str, tvars: frozenset = frozenset()) -> bool:
        if t in KNOWN_TYPES or t in rec or t in tvars:
            return True
        if is_money(t):                 # a currency, or a currency variable
            cur = t[len("Money of "):]
            return cur in CURRENCIES or cur in tvars
        if is_secret(t):
            inner = secret_inner(t)
            return not is_secret(inner) and valid_type(inner, tvars)
        if t.startswith("List of "):
            return valid_type(t[len("List of "):], tvars)
        if t.startswith("Map of "):
            rest = t[len("Map of "):]
            key, sep, val = rest.partition(" to ")
            return sep != "" and key in ("Text", "Int") and \
                valid_type(val, tvars)
        sig = fn_sig_parts(t)
        if sig is not None:
            parts, ret = sig
            return all(valid_type(p, tvars) for p in parts) and (
                ret == "Unit" or valid_type(ret, tvars))
        return False

    TYPE_HINT = ("use Int, Text, Bool, Money of INR, a record name, or "
                 "List of <one of those>")

    def currency_named(t: str, tvars: frozenset = frozenset()):
        """The currency code in type t that is not in the table, if any."""
        if is_money(t):
            cur = t[len("Money of "):]
            return None if cur in CURRENCIES or cur in tvars else cur
        if is_secret(t):
            return currency_named(secret_inner(t), tvars)
        if t.startswith("List of "):
            return currency_named(t[8:], tvars)
        if t.startswith("Map of "):
            return currency_named(t[7:].partition(" to ")[2], tvars)
        sig = fn_sig_parts(t)
        if sig is not None:
            for p in sig[0] + [sig[1]]:
                got = currency_named(p, tvars)
                if got:
                    return got
        return None

    def unknown_currency(code: str, line: int) -> VelarisError:
        return VelarisError("E551",
            f"'{code}' is not a currency Velaris knows", line,
            fixes=["the currencies are: " + ", ".join(sorted(CURRENCIES)),
                   "a currency is added to velaris.CURRENCIES with the "
                   "minor-unit count ISO 4217 gives it, not by a program"])

    def bad_type(t: str, tvars, message: str, line: int) -> VelarisError:
        code = currency_named(t, tvars)
        if code:
            return unknown_currency(code, line)
        return VelarisError("E500", message, line, fixes=[TYPE_HINT])

    for r in records:
        for fname, ftype in r.fields:
            if not valid_type(ftype):
                errors.append(blame(r, bad_type(ftype, frozenset(),
                    f"unknown type '{ftype}' for field '{fname}' of "
                    f"record '{r.name}'", r.line)))

    # first: every declared type must be a real type
    for f in funcs:
        tvs = frozenset(f.type_vars)
        for tv in f.type_vars:
            if tv in KNOWN_TYPES or tv in rec:
                errors.append(blame(f, VelarisError("E541",
                    f"type variable '{tv}' shadows a real type", f.line,
                    fixes=["pick a fresh name like T, U, or Item"])))
            elif not any(type_mentions(pt, tv) for _, pt in f.params):
                errors.append(blame(f, VelarisError("E540",
                    f"type variable '{tv}' must appear in at least one "
                    f"parameter (a {tv} only in the return type cannot be "
                    f"inferred)", f.line,
                    fixes=[f"use {tv} in a parameter type"])))
        for pname, ptype in f.params:
            if not valid_type(ptype, tvs):
                raise bad_type(ptype, tvs, f"unknown type '{ptype}' for "
                               f"parameter '{pname}' of '{f.name}'", f.line)
        if f.return_type is not None and not valid_type(f.return_type, tvs):
            raise bad_type(f.return_type, tvs, f"unknown return type "
                           f"'{f.return_type}' for '{f.name}'", f.line)

    def builtin_call_fallible(node, infer) -> bool:
        if builtin_reached(node.name, table) in FALLIBLE_BUILTINS:
            return True
        if node.name == "get" and node.args:
            try:
                return infer(node.args[0]).startswith("Map of ")
            except VelarisError:
                return False
        return False

    NAMESPACES = {n.split(".")[0] for n in table if "." in n}

    def no_shadow(name: str, line: int) -> None:
        if name in NAMESPACES:
            raise VelarisError("E514",
                f"'{name}' is the name of an import, so it cannot also be "
                f"a variable", line,
                fixes=[f"rename the variable",
                       f"or give the import another name: as {name}_lib"])

    lambda_of = {f.name: f for f in funcs if getattr(f, "is_lambda", False)}

    def check_fn(fn: Function) -> None:
        for _pname, _ in fn.params:
            no_shadow(_pname, fn.line)
        env = dict(fn.params)                       # variable -> type
        for cname, ctype in getattr(fn, "captures", []):
            env.setdefault(cname, ctype)            # values carried in
        declared_ret = fn.return_type or "Unit"

        # where each secret-carrying name got its secret, so that E560
        # can name the place rather than only the value. Best effort and
        # never load-bearing: the refusal does not depend on it.
        origins = {p: f"the parameter '{p}' of {nice_name(fn.name)}"
                   for p, t in fn.params if carries(t)}
        origins.update({c: f"'{c}', carried into this function value"
                        for c, t in getattr(fn, "captures", [])
                        if carries(t)})

        def origin_of(node) -> str:
            """Where the secret in this expression came from."""
            if isinstance(node, Var):
                return origins.get(node.name) or f"'{node.name}'"
            if isinstance(node, Call):
                b = builtin_reached(node.name, table)
                if b in SECRET_SOURCES:
                    return f"{b}(), line {node.line}"
                called = table.get(node.name)
                if called is not None and carries(called.return_type or ""):
                    said = (f"{nice_name(node.name)}, which returns "
                            f"{called.return_type} (line {node.line})")
                    # a secret handed in is where this one came from;
                    # otherwise look for where the callee got its own
                    for a in node.args:
                        try:
                            if carries(infer(a, allow_fail=True)):
                                return f"{origin_of(a)}, through {said}"
                        except VelarisError:
                            continue
                    deeper = secret_enters(node.name)
                    return f"{deeper}, through {said}" if deeper else said
            if isinstance(node, FieldGet):
                base = origin_of(node.obj)
                return f"the field '{node.field}' of {base}"
            if isinstance(node, TryExpr):
                return origin_of(node.value)
            kids = []
            if isinstance(node, Call):
                kids = list(node.args)
            elif isinstance(node, BinOp):
                kids = [node.left, node.right]
            elif isinstance(node, (Not, Neg)):
                kids = [node.value]
            elif isinstance(node, ListLit):
                kids = list(node.items)
            elif isinstance(node, MapLit):
                kids = [v for _, v in node.entries]
            elif isinstance(node, RecordLit):
                kids = [v for _, v in node.fields]
            for k in kids:
                try:
                    if carries(infer(k, allow_fail=True)):
                        return origin_of(k)
                except VelarisError:
                    continue
            return "a secret value"

        def refuse_secret_args(node, said: str, where: str) -> None:
            """No argument of an emitting call may carry a secret."""
            for i, a in enumerate(node.args, 1):
                try:
                    t = infer(a, allow_fail=True)
                except VelarisError:
                    continue
                if carries(t):
                    raise leak(f"argument {i} of '{said}'", where, t,
                               origin_of(a), node.line)

        def infer(node, allow_fail: bool = False) -> str:
            if isinstance(node, TryExpr):
                if not fn.can_fail:
                    raise VelarisError("E521",
                        f"'try' passes failure up, but '{fn.name}' cannot "
                        f"fail", node.line,
                        fixes=[f"add 'or fail' to the signature of "
                               f"'{fn.name}'",
                               "or handle it here with a check block"])
                callee = table.get(node.value.name)
                user_ok = callee is not None and callee.can_fail
                if not user_ok and not builtin_call_fallible(node.value,
                                                             infer):
                    raise VelarisError("E522",
                        f"'{shown_name(node.value.name)}' cannot fail - "
                        f"call it directly without 'try'", node.line,
                        fixes=["remove the 'try'"])
                return infer(node.value, allow_fail=True)
            if isinstance(node, Num):  return "Int"
            if isinstance(node, FloatNum): return "Float"
            if isinstance(node, Neg):
                t = infer(node.value)
                bare = strip_secret(t)
                if bare not in ("Int", "Float") and not is_money(bare):
                    raise VelarisError("E501",
                        f"'-' needs a number, but this is {t}", node.line,
                        fixes=["negate an Int or Float value"])
                return t
            if isinstance(node, Str):  return "Text"
            if isinstance(node, Bool): return "Bool"
            if isinstance(node, Closure):
                lam = lambda_of.get(node.name)
                if lam is None:
                    raise VelarisError("E402",
                        f"unknown function value '{node.name}'", node.line)
                # a name is captured when the surrounding code has it as
                # a local; anything else is a global function or builtin
                caught = []
                for n in node.free:
                    if n in env:
                        caught.append((n, env[n]))
                lam.captures = caught
                check_fn(lam)              # check it where its names mean
                                           # something
                return fmt_fn_type([t for _, t in lam.params],
                                   lam.return_type)
            if isinstance(node, Var):
                if node.name in env:
                    return env[node.name]
                f2 = table.get(node.name)
                if f2 is not None:
                    if f2.type_vars:
                        raise VelarisError("E543",
                            f"'{f2.name}' is generic - generic functions "
                            f"cannot be passed as values yet", node.line,
                            fixes=["call it directly instead"])
                    if f2.effects:
                        raise VelarisError("E530",
                            f"'{f2.name}' uses effects "
                            f"({', '.join(sorted(f2.effects))}) - only pure "
                            f"functions can be passed as values", node.line,
                            fixes=["pass a function with no 'uses' clause"])
                    if f2.can_fail:
                        raise VelarisError("E530",
                            f"'{f2.name}' can fail - only functions that "
                            f"cannot fail can be passed as values", node.line,
                            fixes=["pass a function without 'or fail'"])
                    return fmt_fn_type([t for _, t in f2.params],
                                       f2.return_type)
                if getattr(fn, "is_lambda", False):
                    raise VelarisError("E402",
                        f"a function value cannot use '{node.name}' from "
                        f"the code around it", node.line,
                        fixes=[f"add it as a parameter: "
                               f"fn(x: T, {node.name}: T) -> ...",
                               "or write a named function that takes it"])
                if node.name in ("break", "continue"):
                    raise VelarisError("E402",
                        f"there is no '{node.name}' in this language",
                        node.line,
                        fixes=["use a condition in the loop test instead",
                               "or keep a flag: "
                               "while going and i < n { ... }"])
                raise VelarisError("E402",
                                  f"unknown variable '{node.name}'",
                                  node.line,
                                  fixes=[f"declare it first: let {node.name} = ..."])
            if isinstance(node, Not):
                t = infer(node.value)
                if strip_secret(t) != "Bool":
                    raise VelarisError("E501",
                        f"'not' needs a yes/no value (Bool), but this is {t}",
                        node.line, fixes=["use it on a comparison like not (x > 0)"])
                return t
            if isinstance(node, RecordLit):
                if node.name not in rec:
                    raise VelarisError("E508",
                        f"unknown record '{node.name}'", node.line,
                        fixes=[f"declare it first: record {node.name} {{ ... }}"])
                want = rec[node.name]
                given = {}
                for fname, v in node.fields:
                    if fname not in want:
                        raise VelarisError("E509",
                            f"record '{node.name}' has no field '{fname}'",
                            node.line,
                            fixes=[f"its fields are: {', '.join(want)}"])
                    if fname in given:
                        raise VelarisError("E509",
                            f"field '{fname}' is given twice", node.line,
                            fixes=["give each field exactly once"])
                    given[fname] = infer(v)
                    if currency_clash(want[fname], given[fname]):
                        raise clash_error(want[fname], given[fname],
                                          node.line, f"field '{fname}'")
                    if given[fname] != want[fname]:
                        raise VelarisError("E501",
                            f"field '{fname}' of '{node.name}' holds "
                            f"{want[fname]}, but this is {given[fname]}",
                            node.line,
                            fixes=[f"give {'an' if want[fname] == 'Int' else 'a'} "
                                   f"{want[fname]} value"])
                missing = [f for f in want if f not in given]
                if missing:
                    raise VelarisError("E509",
                        f"record '{node.name}' is missing field(s): "
                        f"{', '.join(missing)}", node.line,
                        fixes=["give every field a value"])
                return node.name
            if isinstance(node, FieldGet):
                t = infer(node.obj)
                if t not in rec:
                    raise VelarisError("E510",
                        f"{t} has no fields", node.line,
                        fixes=["only records have fields, accessed like p.x"])
                if node.field not in rec[t]:
                    raise VelarisError("E510",
                        f"record '{t}' has no field '{node.field}'",
                        node.line,
                        fixes=[f"its fields are: {', '.join(rec[t])}"])
                return rec[t][node.field]
            if isinstance(node, MapLit):
                if not node.entries:
                    raise VelarisError("E506",
                        "cannot tell what an empty map holds", node.line,
                        fixes=['put at least one entry in it, e.g. {"a": 0}'])
                kt = infer(node.entries[0][0])
                vt = infer(node.entries[0][1])
                if kt not in ("Text", "Int"):
                    raise VelarisError("E501",
                        f"map keys must be Text or Int, but this is {kt}",
                        node.line, fixes=["use Text or Int keys"])
                seen_const = set()
                for k, v in node.entries:
                    if infer(k) != kt:
                        raise VelarisError("E501",
                            f"a map cannot mix {kt} and {infer(k)} keys",
                            node.line, fixes=["keep every key the same type"])
                    if currency_clash(vt, infer(v)):
                        raise clash_error(vt, infer(v), node.line,
                                          "a value in this map")
                    if infer(v) != vt:
                        raise VelarisError("E501",
                            f"a map cannot mix {vt} and {infer(v)} values",
                            node.line, fixes=["keep every value the same type"])
                    if isinstance(k, (Str, Num)):
                        if k.value in seen_const:
                            raise VelarisError("E509",
                                f"map key {expr_str(k)} is given twice",
                                node.line, fixes=["give each key once"])
                        seen_const.add(k.value)
                return f"Map of {kt} to {vt}"
            if isinstance(node, ListLit):
                if not node.items:
                    raise VelarisError("E506",
                        "cannot tell what an empty list holds", node.line,
                        fixes=["put at least one item in it, e.g. [0]"])
                t0 = infer(node.items[0])
                for it in node.items[1:]:
                    t = infer(it)
                    if currency_clash(t0, t):
                        raise clash_error(t0, t, node.line,
                                          "an item in this list")
                    if t != t0:
                        raise VelarisError("E501",
                            f"a list cannot mix {t0} and {t}", node.line,
                            fixes=["keep every item in a list the same type"])
                return "List of " + t0
            # ---- the sink check (6.0), in one place ------------------
            # Every route by which a builtin can put a value in front of
            # somebody is here, so a builtin added later cannot acquire
            # one quietly. `node.name in env` is a function value being
            # called, not a builtin.
            if isinstance(node, Call) and node.name not in env:
                emits = sink_builtin(node.name)
                if emits is not None:
                    refuse_secret_args(
                        node, shown_name(node.name),
                        f"'{emits}' performs "
                        f"{', '.join(sorted(BUILTINS[emits]['effects']))}")
                tells = tattling_builtin(node.name)
                if tells is not None:
                    refuse_secret_args(
                        node, shown_name(node.name),
                        f"'{tells}' can fail with a reason the runtime "
                        f"builds out of the values it was given, which "
                        f"the program can then print")
            if isinstance(node, Call) and node.name in (
                    "all_of", "any_of"):
                if len(node.args) != 2:
                    raise VelarisError("E401",
                        f"'{node.name}' expects 2 argument(s) but got "
                        f"{len(node.args)}", node.line,
                        fixes=["pass a list and a predicate function"])
                t0 = infer(node.args[0])
                if not t0.startswith("List of "):
                    raise VelarisError("E501",
                        f"'{node.name}' needs a list first, but this is "
                        f"{t0}", node.line, fixes=["pass a list"])
                elem = t0[len("List of "):]
                want_p = fmt_fn_type([elem], "Bool")
                parg = node.args[1]
                pf = (table.get(parg.name) if isinstance(parg, Var)
                      and parg.name not in env else None)
                if pf is not None and currency_generic(pf) \
                        and is_money(elem):
                    # a predicate generic only in its currency, like
                    # money.vel's not_negative, takes the list's (4.3)
                    ptypes = [t for _, t in pf.params]
                    if (len(ptypes) != 1 or not is_money(ptypes[0])
                            or (pf.return_type or "Unit") != "Bool"):
                        raise VelarisError("E501",
                            f"'{node.name}' needs a {want_p} predicate, "
                            f"but '{pf.name}' is not one", node.line,
                            fixes=[f"pass a function taking {elem} and "
                                   f"returning Bool"])
                    if pf.effects or pf.can_fail:
                        raise VelarisError("E530",
                            f"'{pf.name}' has effects or can fail - only "
                            f"pure functions can be passed as values",
                            node.line,
                            fixes=["pass a function with no 'uses' clause "
                                   "and no 'or fail'"])
                    cur = ptypes[0][len("Money of "):]
                    if cur not in pf.type_vars and ptypes[0] != elem:
                        raise clash_error(ptypes[0], elem, node.line,
                                          "each item")
                    return "Bool"
                t1 = infer(node.args[1])
                if t1 != want_p:
                    raise VelarisError("E501",
                        f"'{node.name}' needs a {want_p} predicate, "
                        f"but this is {t1}", node.line,
                        fixes=[f"pass a function taking {elem} and "
                               f"returning Bool"])
                return wrap_secret("Bool") if carries(t0) else "Bool"
            if isinstance(node, Call) and node.name in (
                    "length", "push", "get", "put", "has", "keys",
                    "get_or", "pop", "slice", "set_at"):
                n_want = {"length": 1, "keys": 1, "push": 2, "get": 2,
                          "has": 2, "put": 3, "get_or": 3, "pop": 1,
                          "slice": 3, "set_at": 3}[node.name]
                if len(node.args) != n_want:
                    raise VelarisError("E401",
                        f"'{node.name}' expects {n_want} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {n_want} argument(s)"])
                t0 = infer(node.args[0])
                # a container that is itself secret is read as what it
                # holds, and everything taken out of it comes back secret
                sec0 = is_secret(t0)
                if sec0:
                    t0 = secret_inner(t0)

                def keep0(t: str) -> str:
                    return (SECRET_PREFIX + t
                            if sec0 and not carries(t) else t)

                def keep_any(t: str) -> str:
                    """For a result that is about the container rather
                    than about what it holds: how many items there are,
                    which keys exist, whether one does.

                    This is secret when the *container* is - the length
                    of a `Secret of Text` is a secret - and not when
                    only its elements are. How many secrets a list holds
                    was decided by the pushes the program made, and a
                    program cannot have made those depend on a secret:
                    that would need a branch on one, which is E563. So
                    `length(List of Secret of Text)` is an ordinary Int,
                    and a program can walk a list of secrets."""
                    return (SECRET_PREFIX + t
                            if sec0 and not carries(t) else t)

                is_map = t0.startswith("Map of ")
                if is_map:
                    key_t, _, val_t = t0[len("Map of "):].partition(" to ")
                if node.name in ("pop", "slice", "set_at"):
                    if not allow_fail:
                        raise VelarisError("E520",
                            f"'{node.name}' can fail - that cannot be "
                            f"ignored", node.line,
                            fixes=[f"handle it: check {node.name}(...) "
                                   f"{{ ok v {{ ... }} fail why "
                                   f"{{ ... }} }}",
                                   f"or pass it up (inside a fallible "
                                   f"function): try {node.name}(...)"])
                    if not t0.startswith("List of "):
                        raise VelarisError("E501",
                            f"'{node.name}' works on a list, not {t0}",
                            node.line,
                            fixes=[f"pass a list to '{node.name}'"])
                    if node.name == "set_at":
                        want = t0[len("List of "):]
                        got = infer(node.args[2])
                        if currency_clash(want, got):
                            raise clash_error(want, got, node.line)
                        if got != want and want != "Any":
                            raise VelarisError("E501",
                                f"this list holds {want}, so 'set_at' "
                                f"cannot put {got} in it", node.line,
                                fixes=[f"pass a {want}"])
                    for arg in node.args[1:3 if node.name == "slice" else 2]:
                        if node.name != "pop" and infer(arg) != "Int":
                            raise VelarisError("E501",
                                f"'{node.name}' takes whole-number "
                                f"positions", node.line,
                                fixes=["pass an Int"])
                    return keep0(t0)
                if node.name == "length":
                    if t0 == "Text" or t0.startswith("List of ") or is_map:
                        return keep_any("Int")
                    raise VelarisError("E501",
                        f"'length' works on Text, a list, or a map, "
                        f"but this is {t0}",
                        node.line, fixes=["pass a Text value, list, or map"])
                if node.name == "keys":
                    if not is_map:
                        raise VelarisError("E501",
                            f"'keys' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map"])
                    return keep_any("List of " + key_t)
                if node.name in ("has", "put"):
                    if not is_map:
                        raise VelarisError("E501",
                            f"'{node.name}' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map as the first argument"])
                    if infer(node.args[1]) != key_t:
                        raise VelarisError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} {key_t} key"])
                    if node.name == "has":
                        return keep_any("Bool")
                    if currency_clash(val_t, infer(node.args[2])):
                        raise clash_error(val_t, infer(node.args[2]),
                                          node.line)
                    if infer(node.args[2]) != val_t:
                        raise VelarisError("E501",
                            f"this map holds {val_t} values, cannot put "
                            f"{infer(node.args[2])}", node.line,
                            fixes=[f"put {'an' if val_t == 'Int' else 'a'} {val_t} value"])
                    return keep0(t0)
                if node.name == "get_or":
                    if not is_map:
                        raise VelarisError("E501",
                            f"'get_or' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map first"])
                    if infer(node.args[1]) != key_t:
                        raise VelarisError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} "
                                   f"{key_t} key"])
                    if currency_clash(val_t, infer(node.args[2])):
                        raise clash_error(val_t, infer(node.args[2]),
                                          node.line, "the default")
                    if infer(node.args[2]) != val_t:
                        raise VelarisError("E501",
                            f"this map holds {val_t} values, but the "
                            f"default is {infer(node.args[2])}", node.line,
                            fixes=[f"use {'an' if val_t == 'Int' else 'a'} "
                                   f"{val_t} default"])
                    return keep0(val_t)
                if node.name == "get" and is_map:
                    if not allow_fail:
                        raise VelarisError("E520",
                            "'get' on a map can fail - the key may be "
                            "missing, and that cannot be ignored",
                            node.line,
                            fixes=["handle it: check get(m, key) "
                                   "{ ok v { ... } fail why { ... } }",
                                   "or use get_or(m, key, default) "
                                   "which never fails",
                                   "or pass it up with: try get(m, key)"])
                    if infer(node.args[1]) != key_t:
                        raise VelarisError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} {key_t} key"])
                    return keep0(val_t)
                if not t0.startswith("List of "):
                    raise VelarisError("E501",
                        f"'{node.name}' needs a list first, but this is {t0}"
                        + (" - use put for maps" if node.name == "push" else ""),
                        node.line, fixes=["pass a list as the first argument"])
                elem = t0[len("List of "):]
                t1 = infer(node.args[1])
                if node.name == "push":
                    if currency_clash(elem, t1):
                        raise clash_error(elem, t1, node.line,
                                          "what is pushed")
                    if t1 != elem:
                        raise VelarisError("E501",
                            f"this list holds {elem}, cannot push a {t1} into it",
                            node.line, fixes=[f"push {'an' if elem == 'Int' else 'a'} {elem} value"])
                    return keep0(t0)
                if t1 != "Int":                      # get
                    raise VelarisError("E501",
                        f"'get' needs an Int position, but this is {t1}",
                        node.line, fixes=["positions are numbers, e.g. get(xs, 0)"])
                return keep0(elem)
            if isinstance(node, Call) and node.name in env \
                    and env[node.name].startswith("fn("):
                parts, ret = fn_sig_parts(env[node.name])
                if len(node.args) != len(parts):
                    raise VelarisError("E401",
                        f"'{node.name}' expects {len(parts)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(parts)} argument(s)"])
                for i, (a, want) in enumerate(zip(node.args, parts), 1):
                    got = infer(a)
                    if currency_clash(want, got):
                        raise clash_error(want, got, node.line,
                                          f"argument {i}")
                    if got != want:
                        raise VelarisError("E501",
                            f"'{node.name}' needs {want} for argument {i}, "
                            f"but this is {got}", node.line,
                            fixes=[f"pass a {want} value"])
                return ret
            if isinstance(node, Call) and not allow_fail and \
                    builtin_reached(node.name, table) in FALLIBLE_BUILTINS:
                said = shown_name(node.name)
                raise VelarisError("E520",
                    f"'{said}' can fail - that cannot be ignored",
                    node.line,
                    fixes=[f"handle it: check {said}(...) "
                           f"{{ ok v {{ ... }} fail reason {{ ... }} }}",
                           f"or pass it up (inside a fallible function): "
                           f"try {said}(...)"])
            if isinstance(node, Call) and \
                    builtin_reached(node.name, table) == "declassify":
                said = shown_name(node.name)
                if len(node.args) != 2:
                    raise VelarisError("E401",
                        f"'{said}' expects 2 argument(s) but got "
                        f"{len(node.args)}", node.line,
                        fixes=['pass the secret and a reason: '
                               'declassify(key, "the vendor needs it")'])
                t0 = infer(node.args[0])
                if not is_secret(t0):
                    raise VelarisError("E561",
                        f"'{said}' takes a Secret, but this is {t0}"
                        + (" - the secret is inside it, so take that out "
                           "first" if carries(t0) else ""), node.line,
                        fixes=["declassify the Secret itself, not what "
                               "holds it"])
                # the reason is written in the call, so that the audit can
                # report it without running the program (velaris-spec 8.6)
                if not isinstance(node.args[1], Str):
                    raise VelarisError("E561",
                        f"the reason given to '{said}' must be written as "
                        f"text in the call", node.line,
                        fixes=['write it here: declassify(x, "the vendor '
                               'authenticates with this key")',
                               "a reason built while running cannot be "
                               "read by the audit, so it would say that a "
                               "secret leaves and not why"])
                if not node.args[1].value.strip():
                    raise VelarisError("E561",
                        f"the reason given to '{said}' is empty", node.line,
                        fixes=["say why this value is safe to let out; it "
                               "is what an operator reads in the audit"])
                return secret_inner(t0)
            if isinstance(node, Call) and \
                    builtin_reached(node.name, table) in MONEY_BUILTINS:
                return money_call(builtin_reached(node.name, table), node)
            if isinstance(node, Call) and (cg := table.get(node.name)) \
                    is not None and cg.type_vars:
                if cg.can_fail and not allow_fail:
                    raise VelarisError("E520",
                        f"'{node.name}' can fail - that cannot be ignored",
                        node.line,
                        fixes=[f"handle it with a check block",
                               f"or pass it up with try {node.name}(...)"])
                ptypes = [t for _, t in cg.params]
                if len(node.args) != len(ptypes):
                    raise VelarisError("E401",
                        f"'{node.name}' expects {len(ptypes)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(ptypes)} argument(s)"])
                tvset = set(cg.type_vars)
                bind: dict = {}

                def unify(want: str, got: str) -> bool:
                    if want in tvset:
                        if want in bind:
                            return bind[want] == got
                        bind[want] = got
                        return True
                    if want == got:
                        return True
                    if is_money(want) and is_money(got):
                        return unify(want[9:], got[9:])   # the currency
                    if is_secret(want) and is_secret(got):
                        return unify(secret_inner(want), secret_inner(got))
                    if want.startswith("List of ") and \
                            got.startswith("List of "):
                        return unify(want[8:], got[8:])
                    if want.startswith("Map of ") and \
                            got.startswith("Map of "):
                        wk, _, wv = want[7:].partition(" to ")
                        gk, _, gv = got[7:].partition(" to ")
                        return unify(wk, gk) and unify(wv, gv)
                    wf, gf = fn_sig_parts(want), fn_sig_parts(got)
                    if wf is not None and gf is not None:
                        (wp, wr), (gp, gr) = wf, gf
                        return len(wp) == len(gp) and all(
                            unify(a, b) for a, b in zip(wp, gp)) and \
                            unify(wr, gr)
                    return False

                def subst(t: str) -> str:
                    if t in bind:
                        return bind[t]
                    if is_secret(t):
                        return SECRET_PREFIX + subst(secret_inner(t))
                    if is_money(t):
                        return "Money of " + subst(t[9:])
                    if t.startswith("List of "):
                        return "List of " + subst(t[8:])
                    if t.startswith("Map of "):
                        k, _, v = t[7:].partition(" to ")
                        return f"Map of {subst(k)} to {subst(v)}"
                    sig = fn_sig_parts(t)
                    if sig is not None:
                        parts, ret = sig
                        return fmt_fn_type([subst(p) for p in parts],
                                           subst(ret))
                    return t

                for i, (a, want) in enumerate(zip(node.args, ptypes), 1):
                    got = infer(a)
                    if not unify(want, got):
                        if currency_clash(subst(want), got):
                            raise clash_error(subst(want), got, node.line,
                                              f"argument {i}")
                        so_far = ", ".join(f"{k} = {v}"
                                           for k, v in bind.items())
                        raise VelarisError("E542",
                            f"'{node.name}' argument {i} should look like "
                            f"{want}, but this is {got}"
                            + (f" (so far: {so_far})" if so_far else ""),
                            node.line,
                            fixes=["make the arguments agree on what "
                                   f"{', '.join(cg.type_vars)} is"])

                # A generic body is checked once, with its type
                # variables standing for nothing in particular. Inside
                # it a value of type T can be compared (`got == item`
                # gives a plain Bool there), handed to `to_text`, or
                # printed - none of which the checker can see as
                # touching a secret, because there is no secret in
                # sight. Bind T to one at a call site and those become
                # an oracle that hands the caller an ordinary Bool, Int
                # or Text: `contains_item([guess], key)` is exactly
                # that. So **no type variable is ever bound to a type
                # that carries a secret** (E560).
                #
                # It is a blunt rule and it is the sound one. The way
                # to write a generic function over secrets is to say so
                # in its signature - `fn pass(s: Secret of T) ->
                # Secret of T for any T` binds T to Text, which carries
                # nothing - and then the body is checked knowing what
                # it holds.
                for tv, bound in bind.items():
                    if carries(bound):
                        at = next((j for j, (_, w) in
                                   enumerate(zip(node.args, ptypes), 1)
                                   if type_mentions(w, tv)), 1)
                        raise leak(
                            f"argument {at} of '{node.name}'",
                            f"'{node.name}' is generic, and its body was "
                            f"checked without knowing that {tv} could be "
                            f"a secret - so it may compare one, or hand "
                            f"one to to_text, and give the answer back as "
                            f"an ordinary value", bound,
                            origin_of(node.args[at - 1]), node.line)
                return subst(cg.return_type or "Unit")
            if isinstance(node, Call):
                cfn = table.get(node.name)
                if cfn is not None and cfn.can_fail and not allow_fail:
                    raise VelarisError("E520",
                        f"'{node.name}' can fail - that cannot be ignored",
                        node.line,
                        fixes=[f"handle it: check {node.name}(...) "
                               f"{{ ok v {{ ... }} fail reason {{ ... }} }}",
                               f"or pass it up (inside a fallible "
                               f"function): try {node.name}(...)"])
                ptypes, ret = callee_sig(node.name, node.line)
                if node.name == "format":          # text, then one value
                    if not node.args:              # per {} placeholder
                        raise VelarisError("E401",
                            "'format' needs the text first", node.line,
                            fixes=['write: format("hi {}", name)'])
                    t_fmt = infer(node.args[0])
                    if strip_secret(t_fmt) != "Text":
                        raise VelarisError("E501",
                            "'format' needs Text as its first argument",
                            node.line, fixes=['write: format("hi {}", name)'])
                    secret_in = carries(t_fmt)
                    for a in node.args[1:]:
                        secret_in = carries(infer(a)) or secret_in
                    if isinstance(node.args[0], Str):   # literal: check now
                        holes = node.args[0].value.count("{}")
                        given = len(node.args) - 1
                        if holes != given:
                            raise VelarisError("E406",
                                f"this text has {holes} placeholder(s) "
                                f"but got {given} value(s)", node.line,
                                fixes=[f"pass exactly {holes} value(s)",
                                       "each {} takes one value"])
                    return wrap_secret("Text") if secret_in else "Text"
                if len(node.args) != len(ptypes):
                    raise VelarisError("E401",
                        f"'{node.name}' expects {len(ptypes)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(ptypes)} argument(s)"])
                secret_in = False
                for i, (arg, want) in enumerate(zip(node.args, ptypes), 1):
                    got = infer(arg)
                    if got == "Unit":
                        raise VelarisError("E502",
                            f"argument {i} of '{node.name}' is a call to a "
                            f"function that returns nothing", node.line,
                            fixes=["call a function that returns a value here"])
                    if currency_clash(want, got):
                        raise clash_error(want, got, node.line,
                                          f"argument {i} of '{node.name}'")
                    # a pure builtin over a secret keeps the secret: what
                    # it hands back was computed from one. The comparison
                    # is on the type underneath, so to_int(key) is the
                    # to_int of a Text and gives a Secret of Int.
                    if carries(got) and builtin_reached(node.name, table) \
                            is not None:
                        if want == "Any":
                            secret_in = True
                        elif strip_secret(got) == want:
                            secret_in = True
                            got = strip_secret(got)
                    if want != "Any" and got != want:
                        if (node.name in table and node.name in BUILTINS
                                and builtin_reached(node.name, table)):
                            raise VelarisError("E501",
                                f"'{node.name}' here is the builtin, which "
                                f"needs {want} for argument {i}; the "
                                f"function '{node.name}' of this program "
                                f"is hidden by it", node.line,
                                fixes=[f"rename your '{node.name}'",
                                       "or import its file with a name: "
                                       'import "money.vel" as money'])
                        raise VelarisError("E501",
                            f"'{node.name}' needs {want} for argument {i}, "
                            f"but this is {got}", node.line,
                            fixes=[f"pass {'an' if want == 'Int' else 'a'} {want} value instead",
                                   f"or change the parameter type to {got}"])
                return wrap_secret(ret) if secret_in else ret
            if isinstance(node, BinOp):
                l, r = infer(node.left), infer(node.right)
                # An operator over a secret works on what is underneath
                # and hands back a secret - except a comparison, which
                # hands back an ordinary Bool. SPEC.md 3.1 states that
                # choice and what it costs: `if key == ""` has to be
                # writable, and refusing the Bool while allowing the
                # branch would stop nothing. A comparison may also put a
                # secret beside a plain value of the same type, which is
                # the only place the two mix.
                secret_in = carries(l) or carries(r)
                if secret_in:
                    l, r = strip_secret(l), strip_secret(r)

                def kept(t: str) -> str:
                    """A result computed from a secret is a secret - a
                    Bool from a comparison included (SPEC.md 3.1)."""
                    return (SECRET_PREFIX + t
                            if secret_in and not carries_secret(t) else t)

                if "Unit" in (l, r):
                    raise VelarisError("E502",
                        "this expression uses a function that returns nothing",
                        node.line, fixes=["only use functions that return a value in math/text"])
                op = node.op
                if op in ("and", "or"):
                    if l == "Bool" and r == "Bool":
                        # a Bool a program declared secret stays secret
                        # here: only a comparison makes a plain one
                        return kept("Bool")
                    raise VelarisError("E501",
                        f"'{op}' needs yes/no values (Bool) on both sides, "
                        f"but this is {l} {op} {r}", node.line,
                        fixes=["use comparisons on both sides, like x > 0 and x < 10"])
                NUM_FIX = ["make both sides the same number type",
                           "convert with to_float(x), or round(x) for an Int"]
                if (is_money(l) or is_money(r)) and not (
                        op == "+" and "Text" in (l, r)):
                    got = money_op(op, l, r, node.line)
                    return got if got == "Bool" else kept(got)
                if op == "+":
                    if l == "Text" or r == "Text":
                        return kept("Text")            # text joining, e.g. "n: " + 5
                    if l == r and l in ("Int", "Float"):
                        return kept(l)
                    raise VelarisError("E501", f"cannot add {l} and {r}",
                                       node.line, fixes=NUM_FIX)
                if op == "%":
                    if l == "Int" and r == "Int":
                        return kept("Int")
                    raise VelarisError("E501",
                        f"'%' needs Int on both sides, but this is {l} % {r}",
                        node.line, fixes=["make both sides Int"])
                if op in ("-", "*", "/"):
                    if l == r and l in ("Int", "Float"):
                        return kept(l)
                    raise VelarisError("E501",
                        f"'{op}' needs matching number types, but this is "
                        f"{l} {op} {r}", node.line, fixes=NUM_FIX)
                if op in ("<", ">", "<=", ">="):
                    if l == r and l in ("Int", "Float", "Text"):
                        return kept("Bool")   # Text compares alphabetically
                    raise VelarisError("E501",
                        f"'{op}' compares two Ints, two Floats, or two "
                        f"Texts, but this is {l} {op} {r}", node.line,
                        fixes=NUM_FIX)
                if l != r:                             # == and !=
                    raise VelarisError("E501",
                        f"cannot compare {l} with {r}", node.line,
                        fixes=["compare values of the same type"])
                return kept("Bool")

        def check_stmt(node) -> None:
            if isinstance(node, Let):
                no_shadow(node.name, node.line)
                if node.ann is not None:
                    if not valid_type(node.ann, frozenset(fn.type_vars)):
                        raise bad_type(node.ann, frozenset(fn.type_vars),
                                       f"unknown type '{node.ann}'",
                                       node.line)
                    empty_list = (isinstance(node.value, ListLit)
                                  and not node.value.items)
                    empty_map = (isinstance(node.value, MapLit)
                                 and not node.value.entries)
                    if empty_list or empty_map:
                        want_kind = "List of " if empty_list else "Map of "
                        if not node.ann.startswith(want_kind):
                            raise VelarisError("E501",
                                f"'{node.name}' is declared {node.ann}, "
                                f"but this is an empty "
                                f"{'list' if empty_list else 'map'}",
                                node.line,
                                fixes=["match the declared type and the "
                                       "value"])
                        env[node.name] = node.ann
                        return
                    t = infer(node.value)
                    if currency_clash(node.ann, t):
                        raise clash_error(node.ann, t, node.line,
                                          f"'{node.name}'")
                    if t != node.ann:
                        raise VelarisError("E501",
                            f"'{node.name}' is declared {node.ann}, "
                            f"but this is {t}", node.line,
                            fixes=[f"give {'an' if node.ann == 'Int' else 'a'} "
                                   f"{node.ann} value",
                                   "or fix the declared type"])
                    env[node.name] = t
                    if carries(t):
                        origins[node.name] = origin_of(node.value)
                    return
                t = infer(node.value)
                if t == "Unit":
                    raise VelarisError("E502",
                        f"'{node.name}' would hold nothing: that function "
                        f"returns no value", node.line,
                        fixes=["assign a function that returns a value"])
                env[node.name] = t
                if carries(t):
                    origins[node.name] = origin_of(node.value)
            elif isinstance(node, Return):
                if node.value is None:
                    if declared_ret != "Unit":
                        raise VelarisError("E503",
                            f"'{fn.name}' promises to return {declared_ret} "
                            f"but this return gives nothing", node.line,
                            fixes=[f"return a {declared_ret} value"])
                    return
                t = infer(node.value)
                if declared_ret == "Unit":
                    raise VelarisError("E503",
                        f"'{fn.name}' does not declare a return type "
                        f"but returns a {t}", node.line,
                        fixes=[f"add '-> {t}' to the signature of '{fn.name}'",
                               "or remove the returned value"])
                if currency_clash(declared_ret, t):
                    raise clash_error(declared_ret, t, node.line,
                                      "what this returns")
                if t != declared_ret:
                    raise VelarisError("E503",
                        f"'{fn.name}' promises to return {declared_ret} "
                        f"but this returns {t}", node.line,
                        fixes=[f"return a {declared_ret} value",
                               f"or change the signature to '-> {t}'"])
            elif isinstance(node, ExprStmt):
                infer(node.expr)
            elif isinstance(node, FailStmt):
                if not fn.can_fail:
                    raise VelarisError("E523",
                        f"'fail' is used, but '{fn.name}' does not declare "
                        f"it can fail", node.line,
                        fixes=[f"add 'or fail' to the signature of "
                               f"'{fn.name}'"])
                t = infer(node.value)
                if carries(t):
                    raise leak("the reason given to 'fail'",
                               "a failure's reason is shown to whoever "
                               "runs the program", t, origin_of(node.value),
                               node.line)
                if t != "Text":
                    raise VelarisError("E501",
                        f"'fail' needs a Text reason, but this is {t}",
                        node.line, fixes=['write a message: fail "why"'])
            elif isinstance(node, Check):
                callee = table.get(node.subject.name)
                user_ok = callee is not None and callee.can_fail
                if not user_ok and not builtin_call_fallible(node.subject,
                                                             infer):
                    raise VelarisError("E522",
                        f"'{shown_name(node.subject.name)}' cannot fail - "
                        f"call it directly, no check needed", node.line,
                        fixes=["remove the check block"])
                rt = infer(node.subject, allow_fail=True)
                if rt == "Unit" and node.ok_name is not None:
                    raise VelarisError("E525",
                        f"'{node.subject.name}' returns nothing - "
                        f"write 'ok {{ ... }}' with no name", node.line,
                        fixes=["remove the name after ok"])
                if rt != "Unit" and node.ok_name is None:
                    raise VelarisError("E525",
                        f"name the result: 'ok value {{ ... }}'", node.line,
                        fixes=["add a name after ok to hold the result"])
                if node.ok_name is not None:
                    env[node.ok_name] = rt
                    if carries(rt):
                        origins[node.ok_name] = origin_of(node.subject)
                for s in node.ok_body:
                    check_stmt(s)
                env[node.fail_name] = "Text"
                for s in node.fail_body:
                    check_stmt(s)
            elif isinstance(node, If):
                c = infer(node.cond)
                no_secret_branch("if", c, node, origin_of(node.cond))
                if c != "Bool":
                    raise VelarisError("E504",
                        f"'if' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like x > 0"])
                for s in node.then + node.other:
                    check_stmt(s)
            elif isinstance(node, While):
                c = infer(node.cond)
                no_secret_branch("while", c, node, origin_of(node.cond))
                if c != "Bool":
                    raise VelarisError("E504",
                        f"'while' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like i < 10"])
                for inv_expr, iline in node.invariants:
                    if strip_secret(infer(inv_expr)) != "Bool":
                        raise VelarisError("E505",
                            "'invariant' must be a yes/no promise (Bool)",
                            iline, fixes=["use a comparison like total >= 0"])
                for s in node.body:
                    check_stmt(s)
            elif isinstance(node, Assign):
                if node.name not in env:
                    raise VelarisError("E402",
                        f"unknown variable '{node.name}'", node.line,
                        fixes=[f"declare it first: let {node.name} = ..."])
                t = infer(node.value)
                have = env[node.name]
                if currency_clash(have, t):
                    raise clash_error(have, t, node.line,
                                      f"what is put in '{node.name}'")
                if t != have:
                    raise VelarisError("E501",
                        f"'{node.name}' holds {have}, cannot put a {t} in it",
                        node.line,
                        fixes=[f"assign {'an' if have == 'Int' else 'a'} {have} value",
                               f"or make a new variable: let {node.name}2 = ..."])
                if carries(t):
                    origins[node.name] = origin_of(node.value)

        # ---- Money (4.3): the rules an amount's type carries ----------
        UNITS_FIX = ['money(1250, "INR") is an amount of 1250 minor units',
                     "units_of(m) is an amount's minor units, as an Int"]

        def money_op(op: str, l: str, r: str, line: int) -> str:
            lm, rm = is_money(l), is_money(r)
            if op in ("/", "%"):
                if lm and not rm:
                    raise VelarisError("E553",
                        f"'{op}' on an amount would round without saying "
                        f"how", line,
                        fixes=['divide_or_fail(amount, n, "half_even") '
                               "names the rounding",
                               "money.split(amount, n) makes n parts that "
                               "add up to the amount exactly",
                               'percent_of(amount, numerator, denominator, '
                               '"half_up") for a share'])
                raise VelarisError("E501",
                    f"'{op}' cannot divide by an amount: this is "
                    f"{l} {op} {r}", line, fixes=UNITS_FIX)
            if "Float" in (l, r):
                raise VelarisError("E501",
                    f"an amount never meets a Float: this is {l} {op} {r}",
                    line, fixes=["a Float cannot hold 0.10 exactly; keep "
                                 "the amount in minor units",
                                 'percent_of(amount, 25, 1000, "half_up") '
                                 "takes 2.5 per cent without one"])
            if op == "*":
                if lm and rm:
                    raise VelarisError("E501",
                        f"an amount times an amount has no meaning: this "
                        f"is {l} * {r}", line,
                        fixes=["multiply an amount by an Int: price * 3",
                               'percent_of(amount, numerator, denominator, '
                               '"half_up") for a share of one'])
                other = r if lm else l
                if other != "Int":
                    raise VelarisError("E501",
                        f"an amount multiplies by an Int, not {other}",
                        line, fixes=["multiply an amount by an Int: price "
                                     "* 3"])
                return l if lm else r
            if lm and rm:
                if l != r:
                    raise clash_error(l, r, line,
                        "the right side" if op in ("+", "-")
                        else "one side")
                return l if op in ("+", "-") else "Bool"
            if op in ("+", "-"):
                raise VelarisError("E501",
                    f"an amount adds only to an amount: this is "
                    f"{l} {op} {r}", line, fixes=UNITS_FIX)
            raise VelarisError("E501",
                f"an amount compares only with an amount: this is "
                f"{l} {op} {r}", line,
                fixes=['compare with an amount: m >= money(0, "INR")',
                       "or compare units_of(m) with an Int"])

        def written_currency(arg, line: int) -> str:
            if not isinstance(arg, Str):
                raise VelarisError("E551",
                    "the currency must be written in the call, as text",
                    line, fixes=['write it there: money(1250, "INR")'])
            if arg.value not in CURRENCIES:
                raise unknown_currency(arg.value, line)
            return arg.value

        def written_rounding(arg, line: int) -> None:
            if not (isinstance(arg, Str) and arg.value in ROUNDING):
                raise VelarisError("E552",
                    "the rounding mode must be written in the call: "
                    '"half_up", "half_even" or "down"', line,
                    fixes=['"half_up" takes a half away from zero, '
                           '"half_even" to the even neighbour, "down" '
                           "toward zero",
                           "there is no default: a division that does "
                           "not come out even says how it rounds"])

        def money_call(b: str, node) -> str:
            want_n = {"money": 2, "units_of": 1, "with_units": 2,
                      "percent_of": 4, "divide_or_fail": 3, "text_of": 1,
                      "parse_money": 2}[b]
            if len(node.args) != want_n:
                raise VelarisError("E401",
                    f"'{b}' expects {want_n} argument(s) but got "
                    f"{len(node.args)}", node.line,
                    fixes=[f"pass exactly {want_n} argument(s)"])
            types = [infer(a) for a in node.args]

            def need(i: int, want: str) -> None:
                if types[i] != want:
                    raise VelarisError("E501",
                        f"'{b}' needs {want} for argument {i + 1}, but "
                        f"this is {types[i]}", node.line,
                        fixes=[f"pass {'an' if want == 'Int' else 'a'} "
                               f"{want}"])

            def amount(i: int) -> str:
                if not is_money(types[i]):
                    raise VelarisError("E501",
                        f"'{b}' needs an amount for argument {i + 1}, but "
                        f"this is {types[i]}", node.line, fixes=UNITS_FIX)
                return types[i]

            if b in ("money", "parse_money"):
                need(0, "Int" if b == "money" else "Text")
                return "Money of " + written_currency(node.args[1],
                                                      node.line)
            if b == "units_of":
                t = types[0]
                if is_money(t) or (t.startswith("List of ")
                                   and is_money(t[8:])):
                    return "Int"
                raise VelarisError("E501",
                    f"'units_of' takes an amount or a list of amounts, "
                    f"but this is {t}", node.line, fixes=UNITS_FIX)
            if b == "text_of":
                amount(0)
                return "Text"
            if b == "with_units":
                need(1, "Int")
                return amount(0)
            if b == "percent_of":
                need(1, "Int")
                need(2, "Int")
                written_rounding(node.args[3], node.line)
                return amount(0)
            need(1, "Int")                                  # divide_or_fail
            written_rounding(node.args[2], node.line)
            return amount(0)

        # Contracts are checked first, while env holds exactly the
        # parameters. A promise may be about a secret - `requires
        # length(key) > 0` is exactly the kind of thing to promise -
        # so a `Secret of Bool` is a promise, where it is not a branch
        # (E563). It is not one for a reason: a broken promise stops
        # the run, cannot be caught and cannot accumulate, so it tells
        # a reader at most one bit per run rather than reading a secret
        # out in a loop, and the message it prints redacts the values
        # whose type is secret. SPEC.md 3.1 says so, and THREAT_MODEL.md
        # lists the bit-per-run that remains.
        for expr, cline in fn.requires:
            if strip_secret(infer(expr)) != "Bool":
                raise VelarisError("E505",
                    f"'requires' must be a yes/no promise (Bool)", cline,
                    fixes=["use a comparison like price >= 0"])
        if fn.ensures:
            if declared_ret != "Unit":
                env["result"] = declared_ret
            for expr, cline in fn.ensures:
                if strip_secret(infer(expr)) != "Bool":
                    raise VelarisError("E505",
                        f"'ensures' must be a yes/no promise (Bool)", cline,
                        fixes=["use a comparison like result >= 0"])
            env.pop("result", None)

        for stmt in fn.body:
            check_stmt(stmt)

    m = table.get("main")
    if m is not None and m.can_fail:
        errors.append(blame(m, VelarisError("E524",
            "'main' cannot be 'or fail' - there is no one above it to "
            "handle the failure", m.line,
            fixes=["handle failures inside main with check blocks"])))
    # what the tracer and a broken promise must not print (6.0): the
    # names whose type holds a secret, and whether the result does.
    # Nothing refuses a program because of this - it is redaction, and
    # the refusals above are what keeps a secret in.
    for fn in funcs:
        fn.secret_params = {p for p, t in fn.params
                            if carries_secret(t, rec_carries)}
        fn.secret_params |= {c for c, t in getattr(fn, "captures", [])
                             if carries_secret(t, rec_carries)}
        fn.secret_result = carries_secret(fn.return_type or "", rec_carries)

    for fn in funcs:
        if getattr(fn, "is_lambda", False) and getattr(fn, "free_names", []):
            continue      # checked at its creation site, where the names
                          # it carries actually mean something
        try:
            check_fn(fn)
        except VelarisError as e:
            errors.append(blame(fn, e))


# ---------------------------------------------------------------------------
# 4c. PROOF CHECKER (v0.8: modular) — proofs now COMPOSE across functions.
#     * When A calls B, the prover uses B's contract as a summary of B:
#       it assumes B's 'ensures' about the result, and PROVES that A always
#       satisfies B's 'requires' at the call site (error E701 if not).
#     * Sound because Velaris has no global state: a call cannot silently
#       change the caller's variables.
#     * Anything unprovable (loops, lists, text math) falls back silently
#       to runtime promise checks.
# ---------------------------------------------------------------------------

# The proof cache lives in a PER-USER directory, never in the program's own
# directory. Until 7.1.1 it was `./.velaris/proofs.json`, read from wherever
# the compiler ran - so a ./.velaris/proofs.json shipped alongside an
# untrusted program (a project directory, a tarball) was believed, and a
# forged `"proven": true` entry made a false `ensures` report proven and, for
# a native-compiled pure function, go unenforced at runtime. That was a hole
# from 2.29 (when the cache was added) to 7.1.1; see advisory-proof-cache.md
# and THREAT_MODEL.md. From 7.1.2 the program directory is never trusted for
# it: a stray ./.velaris/ is ignored (velaris audit says so), and the cache
# is keyed by the source's ABSOLUTE path + content hash + VERSION, so it can
# never be transplanted onto a different file, and a tampered entry whose
# header does not match is rejected.
CACHE_DIR = ".velaris"                 # the stale project-local name, only
CACHE_FILE = os.path.join(CACHE_DIR, "proofs.json")   # detected, never read


def _user_cache_dir() -> str | None:
    """The per-user proof-cache root, or None when one cannot be placed.

    %LOCALAPPDATA%\\velaris\\proofs on Windows; $XDG_CACHE_HOME/velaris/proofs
    or ~/.cache/velaris/proofs elsewhere. Never the program's directory."""
    try:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        else:
            base = os.environ.get("XDG_CACHE_HOME") or \
                os.path.join(os.path.expanduser("~"), ".cache")
        if not base or base == "~":
            return None
        return os.path.join(base, "velaris", "proofs")
    except Exception:
        return None


def _proof_cache_ref(source_path, source_text):
    """(cache_file, abspath, content_sha256) for this source, or None when
    there is no usable per-user cache: no source path, an unreadable file,
    or no per-user directory. The cache is bound to the absolute path, the
    exact bytes, and this VERSION, so a changed file - or one at a different
    path - never reuses another's proofs."""
    if not source_path:
        return None
    import hashlib
    try:
        ap = os.path.normcase(os.path.abspath(source_path))
        text = source_text
        if text is None:
            with open(source_path, encoding="utf-8") as fh:
                text = fh.read()
    except OSError:
        return None
    d = _user_cache_dir()
    if not d:
        return None
    ch = hashlib.sha256(text.encode("utf-8")).hexdigest()
    tag = hashlib.sha256(
        (ap + "\0" + VERSION + "\0" + ch).encode("utf-8")).hexdigest()
    return (os.path.join(d, tag + ".json"), ap, ch)

# ---- how long one proof may take --------------------------------------
# A query about Float is decided by bit-blasting - 64-bit values expanded
# into circuits of individual bits - and it is slow: refuting
# examples/fp_proof_bad.vel takes about fifteen seconds on an idle
# machine and several times that on a busy one. Every other query
# finishes in milliseconds. So a function that mentions Float gets two
# minutes and every other function three seconds.
#
# Either can be replaced for one run, when a proof needs longer or a CI
# leg needs to give up sooner:
#
#     velaris check f.vel --proof-timeout 300
#     VELARIS_PROOF_TIMEOUT=300 velaris check f.vel
#
# A proof that spends its budget without an answer is ABANDONED, and
# every report says so in those words. It is never counted as a proof
# that looked and found nothing wrong; docs/floats.md says why that
# distinction is the whole point.
FLOAT_PROOF_SECONDS = 120.0
PROOF_SECONDS = 3.0
PROOF_TIMEOUT_ENV = "VELARIS_PROOF_TIMEOUT"
_proof_timeout: float | None = None      # set by --proof-timeout


def set_proof_timeout(seconds) -> None:
    """Give every proof in this process `seconds` instead of the two
    defaults. None restores them. ValueError names what was wrong."""
    global _proof_timeout
    if seconds is None:
        _proof_timeout = None
        return
    _proof_timeout = _proof_seconds(seconds, "--proof-timeout")


def _proof_seconds(value, where: str) -> float:
    try:
        s = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{where} needs a number of seconds greater "
                         f"than 0, as {where} 300")
    if not (s > 0) or s == float("inf"):
        raise ValueError(f"{where} needs a number of seconds greater "
                         f"than 0, as {where} 300")
    return s


def proof_timeout_env() -> float | None:
    """VELARIS_PROOF_TIMEOUT, or None when it is unset or unusable."""
    env = os.environ.get(PROOF_TIMEOUT_ENV)
    if not env:
        return None
    try:
        return _proof_seconds(env, PROOF_TIMEOUT_ENV)
    except ValueError:
        return None          # said once by check_proofs, not per query


def proof_timeout_seconds(float_heavy: bool) -> float:
    """What one query gets, in seconds: the flag, then the environment,
    then the default for its kind."""
    if _proof_timeout is not None:
        return _proof_timeout
    from_env = proof_timeout_env()
    if from_env is not None:
        return from_env
    return FLOAT_PROOF_SECONDS if float_heavy else PROOF_SECONDS


def proof_key(fn: Function, table: dict, records: list) -> str:
    """What this function's proof actually depends on.

    Its own text, and the *contracts* of everything it calls - because
    a modular proof assumes those. Change a callee's promise and this
    function must be proven again, or the cache would be telling you
    something that is no longer true.
    """
    import hashlib

    def contract_of(f: Function) -> str:
        return "|".join([
            f.name, str(f.params), str(f.return_type),
            ",".join(sorted(f.effects)), str(f.can_fail),
            ";".join(expr_str(e) for e, _ in f.requires),
            ";".join(expr_str(e) for e, _ in f.ensures)])

    called: set = set()

    def walk(node):
        import dataclasses as _dc
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call):
            called.add(node.name)
        for f in _dc.fields(node):
            walk(getattr(node, f.name))
    walk(fn.body)
    walk([e for e, _ in fn.requires])
    walk([e for e, _ in fn.ensures])

    parts = [VERSION, contract_of(fn), stmt_key(fn.body)]
    for name in sorted(called):
        callee = table.get(name)
        if callee is not None:
            parts.append(contract_of(callee))
    for r in records:
        parts.append(f"{r.name}:{r.fields}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def stmt_key(stmts) -> str:
    """A stable text for a function body."""
    import dataclasses as _dc

    def show(node) -> str:
        if isinstance(node, (list, tuple)):
            return "[" + ",".join(show(x) for x in node) + "]"
        if not _dc.is_dataclass(node):
            return repr(node)
        inner = ",".join(f"{f.name}={show(getattr(node, f.name))}"
                         for f in _dc.fields(node) if f.name != "line")
        return f"{type(node).__name__}({inner})"
    return show(stmts)


def _cache_load(ref) -> dict:
    """The proofs remembered for this exact source, or {} when there is no
    cache, it does not parse, or its header does not match the path, bytes
    and version it claims - so a hand-edited or transplanted file is
    rejected rather than trusted."""
    if ref is None:
        return {}
    cache_file, ap, ch = ref
    try:
        with open(cache_file, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return {}
    if (not isinstance(doc, dict) or doc.get("version") != VERSION
            or doc.get("path") != ap or doc.get("content_sha256") != ch):
        return {}                       # tampered or stale: prove again
    proofs = doc.get("proofs")
    return proofs if isinstance(proofs, dict) else {}


def _cache_save(ref, data: dict) -> None:
    if ref is None:
        return
    cache_file, ap, ch = ref
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"schema": "velaris.proofcache/1", "path": ap,
                       "version": VERSION, "content_sha256": ch,
                       "proofs": data}, f)
    except OSError:
        pass                            # a cache that cannot be written
                                        # is a slowdown, never an error


# ---------------------------------------------------------------------------
# Termination: which loops provably end
# ---------------------------------------------------------------------------

def _names_bound_in(stmts) -> set:
    """Every name assigned or (re)bound anywhere inside these statements,
    nested blocks included."""
    out: set = set()

    def walk(node):
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, (Assign, Let)):
            out.add(node.name)
            walk(node.value)
        elif isinstance(node, If):
            walk(node.then)
            walk(node.other)
        elif isinstance(node, While):
            walk(node.body)
        elif isinstance(node, Check):
            if node.ok_name:
                out.add(node.ok_name)
            out.add(node.fail_name)
            walk(node.ok_body)
            walk(node.fail_body)
        elif isinstance(node, Block):
            walk(node.stmts)
    walk(stmts)
    return out


def _limit_is_invariant(expr, bound: set, table: dict | None) -> bool:
    """A loop limit counts as unchanging when it mentions no name the body
    binds and calls only functions that read their arguments and touch
    nothing. Anything the analysis does not recognise makes it False."""
    if isinstance(expr, (Num, FloatNum, Str, Bool)):
        return True
    if isinstance(expr, Var):
        return expr.name not in bound
    if isinstance(expr, Neg):
        return _limit_is_invariant(expr.value, bound, table)
    if isinstance(expr, BinOp):
        return (expr.op in ("+", "-", "*", "/", "%")
                and _limit_is_invariant(expr.left, bound, table)
                and _limit_is_invariant(expr.right, bound, table))
    if isinstance(expr, FieldGet):
        return _limit_is_invariant(expr.obj, bound, table)
    if isinstance(expr, Call):
        # a builtin counts when the BUILTINS table says it has no
        # effects and it cannot fail (`length`, `split`, `keys`, ...);
        # a user function when it declares no effects and cannot fail
        reached = builtin_reached(expr.name, table)
        builtin = BUILTINS.get(reached) if reached else None
        if builtin is not None:
            pure = (not builtin["effects"]
                    and reached not in FALLIBLE_BUILTINS)
        else:
            fn = (table or {}).get(expr.name)
            pure = fn is not None and not fn.effects and not fn.can_fail
        return pure and all(_limit_is_invariant(a, bound, table)
                            for a in expr.args)
    return False


BAD = object()


def _steps_along_paths(stmts, v: str, op: str) -> set | object:
    """The number of one-step moves of v on every path that runs to the
    end of stmts, as a set ({1} is what a terminating loop needs), or
    BAD when v is touched in any other way. A path that leaves through
    `return` or `fail` leaves the loop too, so it drops out of the set.
    """
    want = "+" if op in ("<", "<=") else "-"
    counts = {0}
    for st in stmts:
        if isinstance(st, Assign) and st.name == v:
            val = st.value
            if not (isinstance(val, BinOp) and val.op == want
                    and isinstance(val.left, Var) and val.left.name == v
                    and isinstance(val.right, Num) and val.right.value == 1):
                return BAD
            counts = {c + 1 for c in counts}
        elif isinstance(st, Let) and st.name == v:
            return BAD
        elif isinstance(st, (Return, FailStmt)):
            return set()                      # every path here has left
        elif isinstance(st, If):
            a = _steps_along_paths(st.then, v, op)
            b = _steps_along_paths(st.other, v, op)
            if a is BAD or b is BAD:
                return BAD
            counts = {c + x for c in counts for x in (a | b)}
        elif isinstance(st, Check):
            if v in (st.ok_name, st.fail_name):
                return BAD
            a = _steps_along_paths(st.ok_body, v, op)
            b = _steps_along_paths(st.fail_body, v, op)
            if a is BAD or b is BAD:
                return BAD
            counts = {c + x for c in counts for x in (a | b)}
        elif isinstance(st, While):
            if v in _names_bound_in(st.body):
                return BAD                    # moved a number of times
        elif isinstance(st, Block):
            inner = _steps_along_paths(st.stmts, v, op)
            if inner is BAD:
                return BAD
            counts = {c + x for c in counts for x in inner}
        if any(c > 1 for c in counts):
            return BAD
    return counts


def _conjuncts(cond) -> list:
    if isinstance(cond, BinOp) and cond.op == "and":
        return _conjuncts(cond.left) + _conjuncts(cond.right)
    return [cond]


FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}


def loop_termination(fn, table: dict | None = None) -> list:
    """For every loop in fn: {"line", "verdict", "why"}.

    verdict is "terminates" for exactly one shape, and "unshown" for
    everything else. The shape: the condition is, or has as an `and`
    conjunct, `v < E`, `v <= E`, `v > E` or `v >= E` (v on either
    side), where E mentions nothing the body binds and calls only pure
    functions, and every path through the body moves v by exactly one
    step toward E - `v = v + 1` for < and <=, `v = v - 1` for > and >= -
    with v assigned nowhere else in the body. A path that returns or
    fails leaves the loop and needs no step. Extra `and` conjuncts can
    only end the loop sooner; an `or` cannot, so it does not qualify.

    A `for` is a while loop by the time this runs (see the parser), and
    goes through the same rule: it qualifies unless the body assigns
    the counter or grows what the loop ranges over. This is purely
    syntactic and needs no solver, so it is the same with and without
    the prover installed.
    """
    out = []

    def judge(loop: While) -> tuple:
        bound = _names_bound_in(loop.body)
        for c in _conjuncts(loop.cond):
            if not isinstance(c, BinOp) or c.op not in FLIP:
                continue
            for side, other, op in ((c.left, c.right, c.op),
                                    (c.right, c.left, FLIP[c.op])):
                if not isinstance(side, Var):
                    continue
                v = side.name
                if v not in bound:
                    continue                  # never moves: not a counter
                if not _limit_is_invariant(other, bound, table):
                    return ("unshown", f"the limit '{expr_str(other)}' "
                                       f"changes inside the loop")
                steps = _steps_along_paths(loop.body, v, op)
                if steps is BAD:
                    return ("unshown", f"'{v}' is not moved by exactly "
                                       f"one step toward the limit on "
                                       f"every path")
                if steps and steps != {1}:
                    return ("unshown", f"some path through the body "
                                       f"leaves '{v}' where it was")
                return ("terminates", f"'{v}' moves one step toward "
                                      f"'{expr_str(other)}' every turn")
        return ("unshown", "no counter walking toward a limit in the "
                           "loop's condition")

    def walk(node):
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, While):
            verdict, why = judge(node)
            out.append({"line": node.line, "verdict": verdict, "why": why})
            walk(node.body)
        elif isinstance(node, If):
            walk(node.then)
            walk(node.other)
        elif isinstance(node, Check):
            walk(node.ok_body)
            walk(node.fail_body)
        elif isinstance(node, Block):
            walk(node.stmts)
    walk(fn.body)
    return out


def check_proofs(funcs: list[Function], records: list,
                 errors: list, proven_out: set | None = None,
                 use_cache: bool = False,
                 timeouts_out: list | None = None,
                 source_path: str | None = None,
                 source_text: str | None = None) -> None:
    # The proof cache is per-user and bound to (source_path, its bytes,
    # VERSION); see _proof_cache_ref. With use_cache and no source_path there
    # is simply no cache - the program's own directory is never read (7.1.2).
    # Nothing to prove means nothing to import. Loading z3 costs about
    # 350ms, and most programs - every hello world, every script whose
    # functions carry no promises - were paying it for no work at all.
    # Division, list reads and calls into contracted functions still
    # create obligations, so this asks about those too.
    def needs_proving(fn) -> bool:
        if fn.requires or fn.ensures:
            return True
        found = [False]

        def look(node):
            if isinstance(node, BinOp) and node.op in ("/", "%"):
                found[0] = True
            if isinstance(node, While) and node.invariants:
                found[0] = True
            if isinstance(node, Call):
                if node.name in ("get", "pop", "slice", "set_at"):
                    found[0] = True
                if builtin_reached(node.name, table_all) == "percent_of":
                    found[0] = True           # a divisor, like '/'
                callee = table_all.get(node.name)
                if callee is not None and (callee.requires or callee.ensures):
                    found[0] = True

        import dataclasses as _dc

        def visit(node):
            if isinstance(node, (list, tuple)):
                for x in node:
                    visit(x)
                return
            if not _dc.is_dataclass(node):
                return
            look(node)
            for f in _dc.fields(node):
                visit(getattr(node, f.name))

        visit(fn.body)
        return found[0]

    table_all = {f.name: f for f in funcs}
    if not any(needs_proving(f) for f in funcs):
        if proven_out is not None:
            proven_out.clear()
        return

    try:
        import z3
    except ImportError:
        print("note: z3-solver is not installed, so promises are checked "
              "while running instead of proven beforehand "
              "(install with: pip install z3-solver)", file=sys.stderr)
        return

    if (_proof_timeout is None and os.environ.get(PROOF_TIMEOUT_ENV)
            and proof_timeout_env() is None):
        print(f"note: {PROOF_TIMEOUT_ENV}="
              f"{os.environ[PROOF_TIMEOUT_ENV]!r} is not a number of "
              f"seconds greater than 0, so the default proof budgets "
              f"apply ({FLOAT_PROOF_SECONDS:.0f}s with Float, "
              f"{PROOF_SECONDS:.0f}s without)", file=sys.stderr)

    table = {f.name: f for f in funcs}
    # an amount is its minor units here: the type checker has already
    # kept every currency apart, so what is left is Int arithmetic
    rec_fields = {r.name: [(f, erase_wrappers(t)) for f, t in r.fields]
                  for r in records}

    def provable_rec(name: str, seen=frozenset()) -> bool:
        if name in seen:
            return False
        fs = rec_fields.get(name)
        if fs is None:
            return False
        return all(ft in ("Int", "Bool", "Float", "Text",
                          "List of Int")
                   or provable_rec(ft, seen | {name})
                   for _, ft in fs)

    class Unprovable(Exception):
        pass

    FELL_OFF = object()
    FAILED = object()
    saw_fp = [False]                   # FP queries earn a bigger budget

    def solver_budget() -> int:
        return int(proof_timeout_seconds(saw_fp[0]) * 1000)

    # 'unknown' has two meanings and they are nothing alike. Z3 says it
    # when the question is outside what it decides - and it says it when
    # the clock ran out, which is not an answer at all. Telling them
    # apart is the difference between "this cannot be proven, so it is
    # checked while running" and "nobody looked".
    ran_out = [False]                  # this function's clock ran out
    timed_out: dict = {}               # function name -> what it got

    def verdict_of(solver):
        """solver.check(), remembering an answer that was a clock."""
        v = solver.check()
        if v == z3.unknown:
            try:
                why = solver.reason_unknown()
            except z3.Z3Exception:
                why = ""
            if "timeout" in why or "canceled" in why:
                ran_out[0] = True
                fn_ = current_fn[0]
                timed_out.setdefault(
                    fn_.name if fn_ is not None else "?",
                    {"name": fn_.name if fn_ is not None else "?",
                     "line": fn_.line if fn_ is not None else 0,
                     "file": (fn_.src_file if fn_ is not None else None),
                     "seconds": proof_timeout_seconds(saw_fp[0]),
                     "float": bool(saw_fp[0])})
        return v
    counter = [0]

    class RecVal:
        """A symbolic record: one Z3 value per field."""
        def __init__(self, rname: str, fields: dict):
            self.rname, self.fields = rname, fields

    class ListVal:
        """A symbolic list: a Z3 array of Ints plus a length. `total`,
        when the list was built here, is what its items add up to - or a
        function giving it, so a list nobody asks units_of about never
        pays for the sum."""
        def __init__(self, arr, length, total=None):
            self.arr, self.length, self.total = arr, length, total

    class GridVal:
        """A symbolic list of lists: rows, row lengths, and how many."""
        def __init__(self, rows, lens, length):
            self.rows, self.lens, self.length = rows, lens, length

    class MapVal:
        """A symbolic map: values, plus which keys are actually there."""
        def __init__(self, vals, present, key_t, val_t):
            self.vals, self.present = vals, present
            self.key_t, self.val_t = key_t, val_t

    MAP_SORTS = {"Int": lambda: z3.IntSort(), "Bool": lambda: z3.BoolSort(),
                 "Text": lambda: z3.StringSort()}
    CODE_AT = z3.Function("code_at", z3.StringSort(), z3.IntSort(),
                          z3.IntSort())
    SPLIT = z3.Function("split", z3.StringSort(), z3.StringSort(),
                        z3.ArraySort(z3.IntSort(), z3.StringSort()))
    SPLIT_N = z3.Function("split_count", z3.StringSort(),
                          z3.StringSort(), z3.IntSort())
    _st, _ss = z3.String("__split_t"), z3.String("__split_s")
    SPLIT_AXIOMS = [z3.ForAll([_st, _ss], SPLIT_N(_st, _ss) >= 1)]
    UPPER = z3.Function("upper", z3.StringSort(), z3.StringSort())
    LOWER = z3.Function("lower", z3.StringSort(), z3.StringSort())
    _t = z3.String("__case_t")
    CASE_AXIOMS = [                     # changing case keeps the length
        z3.ForAll([_t], z3.Length(UPPER(_t)) == z3.Length(_t)),
        z3.ForAll([_t], z3.Length(LOWER(_t)) == z3.Length(_t)),
    ]
    # units_of(xs) for a list the prover did not build - a parameter, a
    # loop's list, a call's result - is TOTAL(its array, its length),
    # a value Z3 is told nothing about except the three facts below,
    # stated about that list alone: nothing adds up to 0, and items that
    # are all >= 0 (all <= 0) add up to something >= 0 (<= 0). Each is a
    # theorem about a real sum. Stating them for every list at once, as
    # one axiom, made Z3 answer 'unknown' to questions it used to settle,
    # which would have cost refutations elsewhere in the same program.
    # A sum is still not defined by them, so a counterexample that
    # mentions TOTAL may be one no real list has: has_fresh says so.
    TOTAL = z3.Function("__total", z3.ArraySort(z3.IntSort(), z3.IntSort()),
                        z3.IntSort(), z3.IntSort())
    total_facts: list = []
    _total_seen: set = set()

    def list_total(lv):
        """What the items of a symbolic list add up to."""
        t = lv.total
        if t is None:
            if lv.arr.sort().range() != z3.IntSort():
                raise Unprovable()
            term = TOTAL(lv.arr, lv.length)
            key = str(term)
            if key not in _total_seen:
                _total_seen.add(key)
                k = z3.Int(f"__total_k{len(_total_seen)}")

                def every(cmp, k=k, lv=lv):
                    return z3.ForAll([k], z3.Implies(
                        z3.And(k >= 0, k < lv.length),
                        cmp(z3.Select(lv.arr, k))))

                total_facts.extend([
                    z3.Implies(lv.length <= 0, term == 0),
                    z3.Implies(every(lambda v: v >= 0), term >= 0),
                    z3.Implies(every(lambda v: v <= 0), term <= 0),
                ])
            return term
        if callable(t):
            t = lv.total = t()
        return t

    def new_solver():
        """A solver that knows what is known about the sums seen so far."""
        s = z3.Solver()
        s.set("timeout", solver_budget())
        if total_facts:
            s.add(*total_facts)
        return s

    def mentions_total(e) -> bool:
        if not z3.is_expr(e):
            return False
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() == "__total":
            return True
        return any(mentions_total(c) for c in e.children())

    # The Money builtins the prover models, exactly as the interpreter
    # runs them. text_of, parse_money and divide_or_fail are not modelled:
    # a function that uses one keeps its promises as runtime checks.
    MONEY_Z3 = ("money", "units_of", "with_units", "percent_of")
    # a parameter or local named like one of them is called as itself
    money_shadowed = NEW_BUILTINS & set().union(
        *(local_names_of(f) for f in funcs))

    def money_z3(b: str, node, env, ctx):
        if b == "money":                  # the currency is in the type
            return to_z3(node.args[0], env, ctx)
        if b == "units_of":
            v = to_z3(node.args[0], env, ctx)
            if isinstance(v, ListVal):
                return list_total(v)
            if z3.is_int(v):
                return v
            raise Unprovable()
        if b == "with_units":
            to_z3(node.args[0], env, ctx)
            return to_z3(node.args[1], env, ctx)
        # percent_of: amount * numerator / denominator, rounded as named,
        # in the formulas round_ratio computes while running. Like '/',
        # it is translated only for a denominator shown positive.
        mode = node.args[3].value if isinstance(node.args[3], Str) else None
        if mode not in ROUNDING:
            raise Unprovable()
        a = to_z3(node.args[0], env, ctx)
        num = to_z3(node.args[1], env, ctx)
        den = to_z3(node.args[2], env, ctx)
        if not all(z3.is_int(x) for x in (a, num, den)):
            raise Unprovable()
        constant = z3.is_int_value(den) and den.as_long() > 0
        if ctx is not None:
            prove_nonzero(den, ctx, node.line, "/")
        if not constant and (ctx is None or not provably_positive(den, ctx)):
            raise Unprovable()
        return rounded(a * num, den, mode)

    def rounded(p, den, mode: str):
        """p / den rounded as `mode` says, for den > 0: round_ratio, in
        Z3's integers. Z3's div and mod agree with Velaris's for a
        positive divisor, which is the only case translated."""
        q, r = p / den, p % den
        if mode == "down":                           # toward zero
            return z3.If(z3.Or(p >= 0, r == 0), q, q + 1)
        if mode == "half_up":                        # a half: away from 0
            return z3.If(2 * r > den, q + 1, z3.If(2 * r < den, q,
                         z3.If(p >= 0, q + 1, q)))
        return z3.If(2 * r > den, q + 1, z3.If(2 * r < den, q,  # half_even
                     z3.If(q % 2 == 0, q, q + 1)))

    def money_fallible(mb: str, node, env, ctx):
        """parse_money and divide_or_fail on the path where they did not
        fail. An amount parsed out of text is simply unknown; a division
        that did not fail is the exact rounding, when the divisor is
        shown positive (the other side of zero stays unknown)."""
        for a in node.args:
            try:
                to_z3(a, env, ctx)       # what is inside still gets checked
            except Unprovable:
                pass
        if mb == "divide_or_fail":
            mode = node.args[2].value if isinstance(node.args[2], Str) \
                else None
            try:
                a = to_z3(node.args[0], env, ctx)
                by = to_z3(node.args[1], env, ctx)
            except Unprovable:
                a = by = None
            if mode in ROUNDING and a is not None and z3.is_int(a) \
                    and z3.is_int(by) and provably_positive(by, ctx):
                return rounded(a, by, mode)
        counter[0] += 1
        return z3.Int(f"__{mb}_result_{counter[0]}")

    def map_parts(t: str):
        """('Map of Text to Int') -> ('Text', 'Int') if both are modelable."""
        if not t.startswith("Map of "):
            return None
        key, sep, val = t[len("Map of "):].partition(" to ")
        if not sep or key not in MAP_SORTS or val not in MAP_SORTS:
            return None
        return key, val

    def mk_map(name: str, t: str):
        parts = map_parts(t)
        if parts is None:
            return None
        key_t, val_t = parts
        ks, vs = MAP_SORTS[key_t](), MAP_SORTS[val_t]()
        return MapVal(z3.Array(name, ks, vs),
                      z3.Array(name + "__has", ks, z3.BoolSort()),
                      key_t, val_t)

    def mk(name: str, t: str):
        if t == "Int":
            return z3.Int(name)
        if t == "Float":
            saw_fp[0] = True
            return z3.FP(name, z3.Float64())
        if t == "Text":
            return z3.String(name)
        return z3.Bool(name)

    def mk_rec(prefix: str, rname: str) -> "RecVal":
        out = {}
        for f, ft in rec_fields[rname]:
            if ft in ("Int", "Bool", "Float", "Text"):
                out[f] = mk(f"{prefix}.{f}", ft)
            elif ft == "List of Int":
                arr = z3.Array(f"{prefix}.{f}", z3.IntSort(), z3.IntSort())
                out[f] = ListVal(arr, z3.Int(f"{prefix}.{f}__n"))
            else:
                out[f] = mk_rec(f"{prefix}.{f}", ft)
        return RecVal(rname, out)

    def rec_eq(l: "RecVal", r: "RecVal"):
        parts = []
        for f, ft in rec_fields[l.rname]:
            a, b = l.fields[f], r.fields[f]
            if isinstance(a, RecVal):
                parts.append(rec_eq(a, b))
            else:
                parts.append(a == b)
        return z3.And(*parts) if parts else z3.BoolVal(True)

    def fresh(t: str, base: str):
        counter[0] += 1
        return mk(f"__{base}_result_{counter[0]}", t)

    class Ctx:
        """Per-path proof state: path conditions + facts assumed so far.
        param_assum holds only facts about the caller's own parameters
        (never about summarized call results), so violations proven from
        it alone are guaranteed real - never false alarms."""
        def __init__(self, conds, assum, param_assum, caller):
            self.conds, self.assum = conds, assum
            self.param_assum, self.caller = param_assum, caller

        def fork(self, extra):
            return Ctx(self.conds + [extra], list(self.assum),
                       list(self.param_assum), self.caller)

    def has_fresh(e) -> bool:
        """Does this Z3 expression mention a summarized/havoc value?"""
        if isinstance(e, RecVal):
            return any(has_fresh(v) for v in e.fields.values())
        if isinstance(e, ListVal):
            return has_fresh(e.arr) or has_fresh(e.length)
        if isinstance(e, OpaqueList):
            return has_fresh(e.length)
        if isinstance(e, RecListVal):
            return has_fresh(e.length) or any(
                has_fresh(a) for a in e.arrays.values())
        if isinstance(e, RecElem):
            return has_fresh(e.idx) or has_fresh(e.src.length)
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() == "__total":
            return True              # a sum Z3 was never told the value of
        if isinstance(e, MapVal):
            return has_fresh(e.vals) or has_fresh(e.present)
        if isinstance(e, GridVal):
            return (has_fresh(e.rows) or has_fresh(e.lens)
                    or has_fresh(e.length))
        if z3.is_const(e) and e.decl().name().startswith("__"):
            return True
        return any(has_fresh(c) for c in e.children())

    def show_val(name, v, model):
        if isinstance(v, RecVal):
            def field_text(f, x):
                if isinstance(x, RecVal):
                    return show_val(f, x, model).split(" = ", 1)[-1]
                if isinstance(x, ListVal):
                    n = model.eval(x.length, model_completion=True)
                    return f"{f}: a list of {n}"
                if isinstance(x, MapVal):
                    return f"{f}: a map"
                return f"{f}: {model.eval(x, model_completion=True)}"
            inner = ", ".join(field_text(f, x) for f, x in v.fields.items())
            return f"{name} = {v.rname}({inner})"
        if isinstance(v, ListVal):
            return f"length({name}) = {model.eval(v.length, model_completion=True)}"
        if isinstance(v, MapVal):
            return f"{name} = a map"        # keys are symbolic here
        if isinstance(v, GridVal):
            return (f"length({name}) = "
                    f"{model.eval(v.length, model_completion=True)}")
        return f"{name} = {model.eval(v, model_completion=True)}"

    def bind_params(fnB: Function, args_z3: list) -> dict:
        return {pname: a for (pname, _), a in zip(fnB.params, args_z3)}

    def check_requires_at(fnB, args_z3, ctx, line):
        """Prove the caller always satisfies fnB's requires here (E701)."""
        def names_in(e, out=None):
            if out is None:
                out = set()
            if isinstance(e, Var):
                out.add(e.name)
            import dataclasses as _dc
            if _dc.is_dataclass(e):
                for f in _dc.fields(e):
                    v = getattr(e, f.name)
                    if isinstance(v, (list, tuple)):
                        for x in v:
                            names_in(x, out)
                    else:
                        names_in(v, out)
            return out

        def conjuncts(e):
            """a and b and c -> [a, b, c], so one untranslatable part
            does not throw away the checkable ones. A single length()
            over a record list used to mask a divisor > 0 sitting right
            next to it."""
            if isinstance(e, BinOp) and e.op == "and":
                return conjuncts(e.left) + conjuncts(e.right)
            return [e]

        parts = [p for r_expr, _ in fnB.requires
                 for p in conjuncts(r_expr)]
        bound = bind_params(fnB, [a for a in args_z3])
        for r_expr in parts:
            names = names_in(r_expr)
            involved = [a for (pname, _), a in zip(fnB.params, args_z3)
                        if pname in names]
            if any(a is None for a in involved):
                continue        # this conjunct mentions an unknown
            try:
                need = to_z3(r_expr, bound, None)
            except Unprovable:
                continue
            if any(a is not None and has_fresh(a) for a in involved) or \
                    any(has_fresh(c) for c in ctx.conds) or has_fresh(need):
                continue        # could be a false alarm; runtime will guard
            solver = new_solver()
            solver.add(*ctx.param_assum)
            solver.add(*ctx.conds)
            solver.add(z3.Not(need))
            if verdict_of(solver) == z3.sat:
                m = solver.model()
                vals = ", ".join(
                    show_val(pname, a, m)
                    for (pname, _), a in zip(fnB.params, args_z3))
                raise VelarisError("E701",
                    f"this call can break a promise: '{fnB.name}' requires "
                    f"{expr_str(r_expr)}, but '{ctx.caller}' can call it "
                    f"with {vals} - proven without running the program",
                    line,
                    fixes=["make sure the value meets the promise before "
                           "calling",
                           "or strengthen the caller's own 'requires' to "
                           "rule this out"])

    def predicate_formula(pfn: Function, val):
        """Translate a predicate's body into 'returns true' as a Z3
        formula over val. Only simple pure predicates qualify: one Int
        parameter, Bool result, no loops, no calls, no failure. An
        amount is an Int parameter here, whatever its currency."""
        if (pfn.effects or pfn.can_fail
                or (pfn.type_vars and not currency_generic(pfn))
                or len(pfn.params) != 1
                or erase_wrappers(pfn.params[0][1]) != "Int"
                or pfn.return_type != "Bool"):
            raise Unprovable()

        def paths(stmts, penv, conds):
            out = []
            for i, s in enumerate(stmts):
                if isinstance(s, (Let, Assign)):
                    penv = dict(penv)
                    penv[s.name] = to_z3(s.value, penv, None)
                elif isinstance(s, Return):
                    out.append((conds, to_z3(s.value, penv, None)))
                    return out
                elif isinstance(s, If):
                    c = to_z3(s.cond, penv, None)
                    rest = stmts[i + 1:]
                    out += paths(s.then + rest, dict(penv), conds + [c])
                    out += paths(s.other + rest, dict(penv),
                                 conds + [z3.Not(c)])
                    return out
                else:
                    raise Unprovable()  # loops etc.: too clever to inline
            raise Unprovable()          # fell off without returning
        branches = paths(pfn.body, {pfn.params[0][0]: val}, [])
        return z3.Or(*[z3.And(*(cs + [r])) if cs else r
                       for cs, r in branches])

    def summarize_call(node: Call, env, ctx, allow_fail: bool = False):
        """Model a call to a pure user function by its contract."""
        if node.name not in money_shadowed and builtin_reached(
                node.name, table) in ("parse_money", "divide_or_fail"):
            if not allow_fail or ctx is None:
                raise Unprovable()
            return money_fallible(builtin_reached(node.name, table), node,
                                  env, ctx)
        fnB = table.get(node.name)

        def summarizable(t):
            t = erase_wrappers(t)
            return t in ("Int", "Bool", "Float", "Text") or (
                map_parts(t) is not None) or (
                t in rec_fields and provable_rec(t))

        # a list of amounts comes back as a fresh list whose length and
        # sum the callee's promises describe (4.3) - how money.split's
        # promises reach its caller. Other lists still do not: summarizing
        # them would move verdicts of programs written before it.
        ret_t = (fnB.return_type or "") if fnB is not None else ""
        amounts_back = ret_t.startswith("List of Money of ")
        if (fnB is None or fnB.effects
                or (fnB.type_vars and not currency_generic(fnB))
                or (fnB.can_fail and not allow_fail)
                or not (summarizable(ret_t) or amounts_back)
                or any(not summarizable(pt) for _, pt in fnB.params)):
            raise Unprovable()
        args_z3 = [to_z3(a, env, ctx) for a in node.args]
        check_requires_at(fnB, args_z3, ctx, node.line)
        if amounts_back:
            counter[0] += 1
            base = f"__{fnB.name}_result_{counter[0]}"
            rv = ListVal(z3.Array(base, z3.IntSort(), z3.IntSort()),
                         z3.Int(base + "__n"))
            ctx.assum.append(rv.length >= 0)
        elif fnB.return_type in rec_fields:
            counter[0] += 1
            rv = mk_rec(f"__{fnB.name}_result_{counter[0]}",
                        fnB.return_type)
        else:
            rv = fresh(erase_wrappers(fnB.return_type), fnB.name)
        for ens_expr, _ in fnB.ensures:
            e2 = bind_params(fnB, args_z3)
            e2["result"] = rv
            try:
                ctx.assum.append(to_z3(ens_expr, e2, None))
            except Unprovable:
                pass
        return rv

    def to_z3(node, env, ctx):
        if isinstance(node, Num):  return z3.IntVal(node.value)
        if isinstance(node, FloatNum):
            saw_fp[0] = True
            return z3.FPVal(node.value, z3.Float64())
        if isinstance(node, Str):
            return z3.StringVal(node.value)
        if isinstance(node, Bool): return z3.BoolVal(node.value)
        if isinstance(node, Var):
            if node.name not in env:
                raise Unprovable()
            return env[node.name]
        if isinstance(node, Not):
            return z3.Not(to_z3(node.value, env, ctx))
        if isinstance(node, Neg):
            v = to_z3(node.value, env, ctx)
            if isinstance(v, ListVal):
                raise Unprovable()
            return -v
        if isinstance(node, RecordLit):
            if not provable_rec(node.name):
                raise Unprovable()
            vals = {}
            for f, v in node.fields:
                vals[f] = to_z3(v, env, ctx)
            return RecVal(node.name, vals)
        if isinstance(node, FieldGet):
            obj = to_z3(node.obj, env, ctx)
            if isinstance(obj, RecElem):
                arr = obj.src.arrays.get(node.field)
                if arr is None:
                    raise Unprovable()   # a field the model skipped
                return z3.Select(arr, obj.idx)
            if not isinstance(obj, RecVal):
                raise Unprovable()
            got = obj.fields.get(node.field)
            if got is None:
                raise Unprovable()
            return got
        if isinstance(node, ListLit):
            vals = [to_z3(it, env, ctx) for it in node.items]
            if vals and all(z3.is_string(v) for v in vals):
                arr = z3.K(z3.IntSort(), z3.StringVal(""))
            else:
                arr = z3.K(z3.IntSort(), z3.IntVal(0))
            for idx, v in enumerate(vals):
                if not (z3.is_int(v) or z3.is_string(v)):
                    raise Unprovable()      # lists of lists, records, ...
                if v.sort() != arr.sort().range():
                    raise Unprovable()      # a list cannot mix sorts
                arr = z3.Store(arr, z3.IntVal(idx), v)
            return ListVal(arr, z3.IntVal(len(node.items)),
                           total=lambda vals=vals: sum(vals[1:], vals[0])
                           if vals else z3.IntVal(0))
        if isinstance(node, Call) and node.name in ("all_of", "any_of"):
            a0 = to_z3(node.args[0], env, ctx)
            if not isinstance(a0, ListVal):
                raise Unprovable()
            parg = node.args[1]
            if not isinstance(parg, Var):
                raise Unprovable()
            pfn = table.get(parg.name)
            if pfn is None:
                raise Unprovable()      # predicate came through a variable
            counter[0] += 1
            k = z3.Int(f"__q{counter[0]}")
            body = predicate_formula(pfn, z3.Select(a0.arr, k))
            inside = z3.And(k >= 0, k < a0.length)
            if node.name == "all_of":
                return z3.ForAll([k], z3.Implies(inside, body))
            return z3.Exists([k], z3.And(inside, body))
        if isinstance(node, Call) and node.name == "split":
            t = to_z3(node.args[0], env, ctx)
            sep = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_string(sep)):
                raise Unprovable()
            return ListVal(SPLIT(t, sep), SPLIT_N(t, sep))
        if isinstance(node, Call) and node.name in ("upper", "lower"):
            t = to_z3(node.args[0], env, ctx)
            if not z3.is_string(t):
                raise Unprovable()
            return (UPPER if node.name == "upper" else LOWER)(t)
        if isinstance(node, Call) and node.name == "split":
            t = to_z3(node.args[0], env, ctx)
            sep = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_string(sep)):
                raise Unprovable()
            # the pieces are unknown, but there is always at least one
            return ListVal(SPLIT(t, sep), SPLIT_N(t, sep))
        if isinstance(node, Call) and node.name == "contains":
            hay = to_z3(node.args[0], env, ctx)
            needle = to_z3(node.args[1], env, ctx)
            if z3.is_string(hay) and z3.is_string(needle):
                return z3.Contains(hay, needle)
            raise Unprovable()
        if isinstance(node, Call) and node.name == "code_at":
            t = to_z3(node.args[0], env, ctx)
            i = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_int(i)):
                raise Unprovable()
            # the exact character is unknown to the prover, but it IS a
            # value - enough to reason about the code around it
            return CODE_AT(t, i)
        if isinstance(node, Call) and node.name in ("put", "get_or", "has"):
            base = to_z3(node.args[0], env, ctx)
            if isinstance(base, MapVal):
                k = to_z3(node.args[1], env, ctx)
                if node.name == "has":
                    return z3.Select(base.present, k)
                if node.name == "get_or":
                    d = to_z3(node.args[2], env, ctx)
                    return z3.If(z3.Select(base.present, k),
                                 z3.Select(base.vals, k), d)
                v = to_z3(node.args[2], env, ctx)        # put
                return MapVal(z3.Store(base.vals, k, v),
                              z3.Store(base.present, k, z3.BoolVal(True)),
                              base.key_t, base.val_t)
            if node.name != "put":
                raise Unprovable()
        if isinstance(node, MapLit):
            raise Unprovable()          # literal maps: runtime for now
        if isinstance(node, Call) and node.name in ("length", "get",
                                                    "push"):
            g0 = to_z3(node.args[0], env, ctx) if node.args else None
            if isinstance(g0, GridVal):
                if node.name == "length":
                    return g0.length
                if node.name == "get":
                    idx = to_z3(node.args[1], env, ctx)
                    if ctx is not None:
                        prove_bounds(idx, g0.length, ctx, node.line)
                    return ListVal(z3.Select(g0.rows, idx),
                                   z3.Select(g0.lens, idx))
                row = to_z3(node.args[1], env, ctx)      # push
                if not isinstance(row, ListVal):
                    raise Unprovable()
                return GridVal(
                    z3.Store(g0.rows, g0.length, row.arr),
                    z3.Store(g0.lens, g0.length, row.length),
                    g0.length + 1)
        if isinstance(node, Call) and node.name in ("length", "get", "push"):
            a0 = to_z3(node.args[0], env, ctx)
            if isinstance(a0, OpaqueList):
                if node.name == "length":
                    return a0.length
                raise Unprovable()      # contents are invisible
            if isinstance(a0, RecListVal):
                if node.name == "length":
                    return a0.length
                if node.name == "get":
                    a1 = to_z3(node.args[1], env, ctx)
                    if not hasattr(a1, "sort") or not z3.is_int(a1):
                        raise Unprovable()
                    if ctx is not None:
                        prove_bounds(a1, a0.length, ctx, node.line)
                    return RecElem(a0, a1)
                if node.name == "push":
                    a1 = to_z3(node.args[1], env, ctx)
                    if not isinstance(a1, RecVal) \
                            or a1.rname != a0.rname:
                        raise Unprovable()
                    new_arrays = {}
                    for fname, arr in a0.arrays.items():
                        fv = a1.fields.get(fname)
                        if fv is None or not hasattr(fv, "sort") \
                                or not z3.is_int(fv):
                            raise Unprovable()
                        new_arrays[fname] = z3.Store(arr, a0.length, fv)
                    return RecListVal(a0.rname, new_arrays,
                                      a0.length + 1)
            if not isinstance(a0, ListVal):
                if z3.is_string(a0):
                    return z3.Length(a0)        # characters in the text
                raise Unprovable()
            if node.name == "length":
                return a0.length
            a1 = to_z3(node.args[1], env, ctx)
            # lists are modelled as arrays of Ints; anything else (Text,
            # records, nested lists) stays runtime-checked rather than
            # being forced into a sort it does not fit
            if node.name == "push":
                # a record, a nested list or a map has no Z3 sort at all;
                # ask before assuming, or the translator crashes
                if not hasattr(a1, "sort") or \
                        a1.sort() != a0.arr.sort().range():
                    raise Unprovable()
                return ListVal(z3.Store(a0.arr, a0.length, a1),
                               a0.length + 1,
                               total=lambda a0=a0, a1=a1: list_total(a0) + a1)
            if not hasattr(a1, "sort") or not z3.is_int(a1):
                raise Unprovable()          # an index is always an Int
            # get: prove the read stays inside the list (E705)
            if ctx is not None:
                prove_bounds(a1, a0.length, ctx, node.line)
            return z3.Select(a0.arr, a1)
        if isinstance(node, Call) and node.name not in money_shadowed and \
                builtin_reached(node.name, table) in MONEY_Z3:
            return money_z3(builtin_reached(node.name, table), node, env,
                            ctx)
        if isinstance(node, Call):
            if ctx is None:            # inside a contract: no call summaries
                raise Unprovable()
            return summarize_call(node, env, ctx)
        if isinstance(node, BinOp):
            op = node.op
            if op == "and":
                return z3.And(to_z3(node.left, env, ctx),
                              to_z3(node.right, env, ctx))
            if op == "or":
                return z3.Or(to_z3(node.left, env, ctx),
                             to_z3(node.right, env, ctx))
            l = to_z3(node.left, env, ctx)
            r = to_z3(node.right, env, ctx)
            if isinstance(l, RecVal) or isinstance(r, RecVal):
                if not (isinstance(l, RecVal) and isinstance(r, RecVal)):
                    raise Unprovable()
                if op == "==":
                    return rec_eq(l, r)
                if op == "!=":
                    return z3.Not(rec_eq(l, r))
                raise Unprovable()
            if isinstance(l, ListVal) or isinstance(r, ListVal):
                if not (isinstance(l, ListVal) and isinstance(r, ListVal)):
                    raise Unprovable()
                if op == "==":
                    return z3.And(l.arr == r.arr, l.length == r.length)
                if op == "!=":
                    return z3.Not(z3.And(l.arr == r.arr,
                                         l.length == r.length))
                raise Unprovable()
            if op == "+":  return l + r
            if op == "-":  return l - r
            if op == "*":  return l * r
            if op == "==":
                if z3.is_fp(l) or z3.is_fp(r):
                    return z3.fpEQ(l, r)     # IEEE: NaN != NaN, +0 == -0
                return l == r
            if op == "!=":
                if z3.is_fp(l) or z3.is_fp(r):
                    return z3.Not(z3.fpEQ(l, r))
                return l != r
            if op == "<":  return l < r
            if op == ">":  return l > r
            if op == "<=": return l <= r
            if op == ">=": return l >= r
            if op in ("/", "%") and not (z3.is_fp(l) or z3.is_fp(r)):
                if ctx is not None:        # divide by zero, proven early
                    prove_nonzero(r, ctx, node.line, op)
                # Velaris divides the way Python does: the result floors
                # toward minus infinity. That matches Z3's integer
                # division only when the divisor is POSITIVE, so that is
                # the only case translated - a negative divisor falls
                # back to a runtime check rather than a formula that
                # would quietly disagree with the interpreter.
                if ctx is None or not provably_positive(r, ctx):
                    raise Unprovable()
                return (l / r) if op == "/" else (l % r)
        raise Unprovable()             # Str, ListLit, floats, anything else

    def provably_positive(divisor, ctx) -> bool:
        """True only if the divisor cannot be zero or negative here.

        Until 4.3 a divisor, or a path, that mentioned a loop's values
        was never shown positive, so no division by a loop counter was
        translated. The facts on such a path are the loop's condition and
        invariants, which hold on every real turn (an inferred one is
        proven inductive, a written one is proven or the function is
        not), and the question is only whether the divisor can be <= 0
        under them - a no there is a no in every run. A callee's promise
        is not among them: it sits in assum, which this does not read."""
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(divisor <= 0)
        return verdict_of(solver) == z3.unsat

    def prove_nonzero(divisor, ctx, line, op: str):
        """Prove the divisor is never zero; only report real violations."""
        if has_fresh(divisor):
            return          # the divisor itself is unknown here; the
                            # runtime check still guards it
        # conditions mentioning havoc'd values stay in the solver rather
        # than cancelling the proof: dropping them would invent
        # counterexamples, and keeping them costs nothing. Without this a
        # loop anywhere before the division hid the check entirely -
        # which is the shape of nearly every average.
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(divisor == 0)
        if verdict_of(solver) == z3.sat:
            m = solver.model()
            names = sorted({d.name() for d in m.decls()
                            if not d.name().startswith("__")})
            shown = ", ".join(
                f"{n} = {m.eval(z3.Int(n), model_completion=True)}"
                for n in names[:3])
            word = "divide by" if op == "/" else "take the remainder of"
            raise VelarisError("E706",
                f"this can {word} zero"
                + (f": {shown}" if shown else "")
                + " - proven without running the program", line,
                fixes=["guard it: if d != 0 { ... }",
                       "or add a 'requires' that rules out zero"])

    pinned_counter = [False]   # True while checking a real final turn

    def prove_bounds(idx, length, ctx, line):
        """Prove 0 <= idx < length; report only provably-real violations."""
        if not pinned_counter[0] and (
                has_fresh(idx) or has_fresh(length)
                or any(has_fresh(c) for c in ctx.conds)):
            return                       # runtime bounds check still guards
        if has_fresh(length) and not pinned_counter[0]:
            return
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(z3.Not(z3.And(idx >= 0, idx < length)))
        if verdict_of(solver) == z3.sat:
            m = solver.model()
            raise VelarisError("E705",
                f"this 'get' can reach position "
                f"{m.eval(idx, model_completion=True)}, but the list has "
                f"{m.eval(length, model_completion=True)} item(s) - proven "
                f"without running the program", line,
                fixes=["positions go from 0 to length - 1",
                       "guard the read: if i < length(xs) { ... }"])

    def scan_calls(node, env, ctx):
        """Inside expressions we cannot fully model (like text joining),
        still find user-function calls and prove their requires hold,
        and prove every 'get' stays inside its list."""
        if isinstance(node, Call):
            for a in node.args:
                scan_calls(a, env, ctx)
            if node.name == "get" and len(node.args) == 2:
                try:
                    a0 = to_z3(node.args[0], env, ctx)
                    a1 = to_z3(node.args[1], env, ctx)
                    if isinstance(a0, ListVal):
                        prove_bounds(a1, a0.length, ctx, node.line)
                except Unprovable:
                    pass
            fnB = table.get(node.name)
            if (fnB is not None and fnB.requires
                    and len(fnB.params) == len(node.args)):
                # translate what translates; an argument the prover
                # cannot see becomes an unknown rather than cancelling
                # the whole check - so 'divisor > 0' is still enforced
                # when it sits beside a record list
                args_z3 = []
                for a, (_, pt) in zip(node.args, fnB.params):
                    try:
                        v = to_z3(a, env, ctx)
                    except Unprovable:
                        if pt.startswith("List of "):
                            counter[0] += 1
                            ln = z3.Int(f"__arg_len_{counter[0]}")
                            v = OpaqueList(ln)
                        else:
                            v = None
                    args_z3.append(v)
                check_requires_at(fnB, args_z3, ctx, node.line)
        elif isinstance(node, BinOp):
            scan_calls(node.left, env, ctx)
            scan_calls(node.right, env, ctx)
        elif isinstance(node, (Not, Neg, TryExpr)):
            scan_calls(node.value, env, ctx)
        elif isinstance(node, ListLit):
            for it in node.items:
                scan_calls(it, env, ctx)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                scan_calls(k, env, ctx); scan_calls(v, env, ctx)
        elif isinstance(node, FieldGet):
            scan_calls(node.obj, env, ctx)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                scan_calls(v, env, ctx)

    def assigned_names(stmts, out):
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                assigned_names(s.then, out)
                assigned_names(s.other, out)
            elif isinstance(s, While):
                assigned_names(s.body, out)
        return out

    def prove_invariant(inv_expr, iline, env, ctx, where):
        """Prove one invariant under the given state; honest wording only."""
        try:
            goal = to_z3(inv_expr, env, None)
        except Unprovable:
            return                       # can't model it; runtime will check
        solver = new_solver()
        solver.add(*ctx.assum)
        solver.add(*ctx.conds)
        solver.add(z3.Not(goal))
        verdict = verdict_of(solver)
        if verdict == z3.sat and mentions_total(goal):
            raise Unprovable()       # a sum Z3 was not given: the state it
                                     # found may be one no list is in
        if verdict == z3.sat:
            m = solver.model()
            names = sorted(n for n in expr_vars(inv_expr) if n in env)
            vals = ", ".join(
                f"{n} = {m.eval(env[n], model_completion=True)}"
                for n in names)
            raise VelarisError("E703",
                f"cannot prove the loop keeps 'invariant "
                f"{expr_str(inv_expr)}' {where} in '{ctx.caller}' - "
                f"the promises allow: {vals}", iline,
                fixes=["fix the loop so the invariant always holds",
                       "or strengthen the invariant(s) to rule this "
                       "state out",
                       "or remove the invariant (it will then be checked "
                       "at runtime instead)"])
        if verdict != z3.unsat:
            raise Unprovable()

    def bound_of(s, env, ctx, changed):
        """(counter, its last value in the loop, its starting value).

        Only for the simple shape: one Int compared against something the
        loop does not change, stepping by one.
        """
        if not isinstance(s.cond, BinOp) or s.cond.op not in ("<", "<="):
            return None
        left, right = s.cond.left, s.cond.right
        if not isinstance(left, Var) or left.name not in changed:
            return None
        start = env.get(left.name)
        if start is None or not z3.is_int(start) or has_fresh(start):
            return None
        try:
            limit = to_z3(right, env, None)
        except (Unprovable, KeyError):
            return None
        if not z3.is_int(limit) or has_fresh(limit):
            return None
        steps = [st for st in s.body
                 if isinstance(st, Assign) and st.name == left.name]
        if len(steps) != 1:
            return None                  # not a plain one-step counter
        step = steps[0].value
        if not (isinstance(step, BinOp) and step.op == "+"
                and isinstance(step.left, Var)
                and step.left.name == left.name
                and isinstance(step.right, Num) and step.right.value == 1):
            return None
        last = limit - 1 if s.cond.op == "<" else limit
        return (left.name, last, start)

    current_fn = [None]      # the function being proven, for its ensures

    def quantified_candidates(env, changed):
        """all_of(x, P) in the current ensures becomes a candidate
        invariant over every changed list: everything in it so far
        satisfies P. Entry is vacuous (empty list); preservation asks
        the solver whether each pushed element satisfies P on its path;
        afterward the promise follows directly. This is what lets
        'ensures all_of(result, is_positive)' prove through a loop."""
        fn = current_fn[0]
        if fn is None or not fn.ensures:
            return []
        preds = []
        def harvest(e):
            if isinstance(e, Call) and e.name in ("all_of", "any_of") \
                    and len(e.args) == 2 and isinstance(e.args[1], Var):
                pfn = table.get(e.args[1].name)
                if pfn is not None:
                    preds.append(pfn)
            import dataclasses as _dc
            if _dc.is_dataclass(e):
                for f in _dc.fields(e):
                    v = getattr(e, f.name)
                    if isinstance(v, (list, tuple)):
                        for x in v:
                            if _dc.is_dataclass(x):
                                harvest(x)
                    elif _dc.is_dataclass(v):
                        harvest(v)
        for e_expr, _ in fn.ensures:
            harvest(e_expr)
        if not preds:
            return []
        cands = []
        for n in sorted(changed):
            v = env.get(n)
            if not isinstance(v, ListVal):
                continue
            for pfn in preds:
                def c(e, n=n, pfn=pfn):
                    lv = e[n]
                    if not isinstance(lv, ListVal):
                        raise KeyError(n)
                    counter[0] += 1
                    k = z3.Int(f"__qq{counter[0]}")
                    return z3.ForAll([k], z3.Implies(
                        z3.And(k >= 0, k < lv.length),
                        predicate_formula(pfn, z3.Select(lv.arr, k))))
                cands.append((f"everything in '{n}' satisfies "
                              f"'{pfn.name}'", c))
        return cands

    def infer_invariants(env, changed, s, ctx):
        """Guess the boring invariants so people stop writing them.

        Candidates are simple bounds on the counters a loop moves: each
        changed Int either never goes below or never goes above the
        value it had on entry, and lists keep their length. Everything
        is assumed together, one loop step is explored, and whatever a
        step can break is dropped - repeating until the set is stable.
        (This is the Houdini algorithm, kept deliberately small.)
        """
        snap = {}
        for n in sorted(changed):
            v = env.get(n)
            if v is not None and z3.is_int(v) and not has_fresh(v):
                snap[n] = v
        if not snap:
            return []
        cands = []
        for n, start in snap.items():
            cands.append((f"{n} never goes below its starting value",
                          lambda e, n=n, s0=start: e[n] >= s0))
            cands.append((f"{n} never goes above its starting value",
                          lambda e, n=n, s0=start: e[n] <= s0))

        # A counter walking toward a limit stops AT the limit, not past
        # it. Without this the state after a loop only says i >= limit,
        # so 'the loop ran exactly limit times' can never follow - which
        # is what almost every list-building loop needs.
        bound = None
        if isinstance(s.cond, BinOp) and s.cond.op in ("<", "<=", ">", ">="):
            for side, other, op in ((s.cond.left, s.cond.right, s.cond.op),
                                    (s.cond.right, s.cond.left,
                                     {"<": ">", "<=": ">=", ">": "<",
                                      ">=": "<="}[s.cond.op])):
                if isinstance(side, Var) and side.name in snap:
                    try:
                        limit = to_z3(other, env, None)
                    except (Unprovable, KeyError):
                        continue
                    if not z3.is_int(limit) or has_fresh(limit):
                        continue
                    counter = side.name
                    step = 1 if op in ("<", "<=") else -1
                    # 'while i < E' exits with i at most E; 'while i <= E'
                    # exits with i at most E + 1. Off by one here and the
                    # bound is too weak to pin the counter at exit.
                    edge = (limit if op == "<" else limit + 1) if step > 0 \
                        else (limit if op == ">" else limit - 1)
                    bound = (counter, edge, step)
                    label = (f"{counter} never passes the limit the loop "
                             f"tests against")
                    if step > 0:
                        cands.append((label,
                                      lambda e, n=counter, b=edge: e[n] <= b))
                    else:
                        cands.append((label,
                                      lambda e, n=counter, b=edge: e[n] >= b))
                    break

        try:
            cands.extend(quantified_candidates(env, changed))
        except Unprovable:
            pass

        # A list built one item per turn has exactly as many items as the
        # counter has turns. This is the bridge the prover was missing
        # between a loop and the length of what it produced.
        if bound is not None:
            counter, _, _ = bound
            for n in sorted(changed):
                v = env.get(n)
                if not isinstance(v, ListVal) or has_fresh(v.length):
                    continue
                start_len = v.length
                start_counter = snap.get(counter)
                if start_counter is None:
                    continue
                cands.append((
                    f"'{n}' grows one item for each turn of '{counter}'",
                    lambda e, n=n, c=counter, l0=start_len,
                    c0=start_counter: e[n].length == l0 + (e[c] - c0)))
                cands.append((
                    f"'{n}' never outgrows the turns of '{counter}'",
                    lambda e, n=n, c=counter, l0=start_len,
                    c0=start_counter: e[n].length <= l0 + (e[c] - c0)))
                cands.append((f"'{n}' never shrinks",
                              lambda e, n=n, l0=start_len:
                              e[n].length >= l0))

        for _round in range(3):
            env_h, hfacts = havoc_like(env, changed)
            try:
                facts = list(hfacts) + [c(env_h) for _, c in cands]
                cond_h = to_z3(s.cond, env_h, ctx)
            except (Unprovable, KeyError):
                return []
            ctx_body = Ctx(ctx.conds + facts + [cond_h],
                           list(ctx.assum) + facts + [cond_h],
                           list(ctx.param_assum), ctx.caller)
            try:
                paths = explore(list(s.body), dict(env_h), ctx_body)
            except (Unprovable, VelarisError):
                return []
            if os.environ.get("VELARIS_DEBUG_INV"):
                print("  candidates this round:",
                      [lab for lab, _ in cands], file=sys.stderr)
            keep = []
            for label, c in cands:
                ok = True
                for pctx, ret, penv in paths:
                    if ret is not FELL_OFF:
                        continue
                    try:
                        goal = c(penv)
                    except KeyError:
                        ok = False
                        break
                    solver = new_solver()
                    solver.add(*pctx.assum)
                    solver.add(*pctx.conds)
                    solver.add(z3.Not(goal))
                    if verdict_of(solver) != z3.unsat:
                        ok = False
                        break
                if ok:
                    keep.append((label, c))
            if len(keep) == len(cands):
                return cands
            cands = keep
            if not cands:
                return []
        return cands

    def havoc_like(env, names):
        """Fresh unknowns for every variable the loop can change.
        Returns (new_env, facts) - facts like 'list lengths stay >= 0'."""
        out = dict(env)
        facts = []
        for n in names:
            old = env.get(n)
            if isinstance(old, RecVal):
                counter[0] += 1
                out[n] = mk_rec(f"__{n}_{counter[0]}", old.rname)
            elif isinstance(old, ListVal):
                counter[0] += 1
                arr = z3.Array(f"__{n}_arr_{counter[0]}",
                               z3.IntSort(), z3.IntSort())
                ln = z3.Int(f"__{n}_len_{counter[0]}")
                out[n] = ListVal(arr, ln)
                facts.append(ln >= 0)
            elif old is not None and z3.is_bool(old):
                out[n] = fresh("Bool", n)
            elif old is not None and isinstance(old, GridVal):
                counter[0] += 1
                base = f"__{n}_grid_{counter[0]}"
                inner = z3.ArraySort(z3.IntSort(), z3.IntSort())
                gl = z3.Int(base + "__n")
                out[n] = GridVal(z3.Array(base, z3.IntSort(), inner),
                                 z3.Array(base + "__lens", z3.IntSort(),
                                          z3.IntSort()), gl)
                facts.append(gl >= 0)
            elif old is not None and isinstance(old, RecListVal):
                counter[0] += 1
                arrays = {f: z3.Array(f"__{n}_{f}_{counter[0]}",
                                      z3.IntSort(), z3.IntSort())
                          for f in old.arrays}
                ln = z3.Int(f"__{n}_rlen_{counter[0]}")
                out[n] = RecListVal(old.rname, arrays, ln)
                facts.append(ln >= 0)
            elif old is not None and isinstance(old, OpaqueList):
                counter[0] += 1
                ln = z3.Int(f"__{n}_olen_{counter[0]}")
                out[n] = OpaqueList(ln)
                facts.append(ln >= 0)
            elif old is not None and isinstance(old, MapVal):
                counter[0] += 1
                out[n] = mk_map(f"__{n}_havoc_{counter[0]}",
                                f"Map of {old.key_t} to {old.val_t}")
            elif old is not None and z3.is_string(old):
                out[n] = fresh("Text", n)
            elif old is not None and z3.is_fp(old):
                out[n] = fresh("Float", n)
            else:
                out[n] = fresh("Int", n)
        return out, facts

    def explore(stmts, env, ctx):
        i = 0
        while i < len(stmts):
            s = stmts[i]
            if isinstance(s, FailStmt):
                return [(ctx, FAILED, dict(env))]  # this path never returns
            if isinstance(s, Check):
                rest = stmts[i + 1:]
                rv = summarize_call(s.subject, env, ctx, allow_fail=True)
                env_ok = dict(env)
                if s.ok_name is not None:
                    env_ok[s.ok_name] = rv
                ok_paths = explore(list(s.ok_body) + rest, env_ok, ctx)
                env_fail = dict(env)
                env_fail.pop(s.fail_name, None)   # a Text reason: unmodeled
                fail_paths = explore(list(s.fail_body) + rest, env_fail,
                                     ctx)
                return ok_paths + fail_paths
            if (isinstance(s, (Let, Assign)) and
                    isinstance(s.value, TryExpr)):
                rest = stmts[i + 1:]
                rv = summarize_call(s.value.value, env, ctx,
                                    allow_fail=True)
                env2 = dict(env)
                env2[s.name] = rv
                return (explore(rest, env2, ctx)
                        + [(ctx, FAILED, dict(env))])
            if isinstance(s, Return) and isinstance(s.value, TryExpr):
                rv = summarize_call(s.value.value, env, ctx,
                                    allow_fail=True)
                return [(ctx, rv, dict(env)), (ctx, FAILED, dict(env))]
            if (isinstance(s, ExprStmt)
                    and isinstance(s.expr, TryExpr)):
                rest = stmts[i + 1:]
                summarize_call(s.expr.value, env, ctx, allow_fail=True)
                return (explore(rest, dict(env), ctx)
                        + [(ctx, FAILED, dict(env))])
            if isinstance(s, (Let, Assign)):
                env[s.name] = to_z3(s.value, env, ctx)
            elif isinstance(s, Return):
                r = FELL_OFF if s.value is None else to_z3(s.value, env, ctx)
                return [(ctx, r, dict(env))]
            elif isinstance(s, If):
                c = to_z3(s.cond, env, ctx)
                rest = stmts[i + 1:]
                yes = explore(list(s.then) + rest, dict(env), ctx.fork(c))
                no = explore(list(s.other) + rest, dict(env),
                             ctx.fork(z3.Not(c)))
                return yes + no
            elif isinstance(s, While):
                changed = assigned_names(s.body, set())
                inferred = infer_invariants(env, changed, s, ctx)
                if not s.invariants and not inferred:
                    raise Unprovable()   # no bridge across this loop
                # 1. ENTRY: every written invariant must hold before the
                #    first spin (inferred ones hold by construction)
                for inv_expr, iline in s.invariants:
                    prove_invariant(inv_expr, iline, env, ctx,
                                    "when the loop starts")
                # 2. PRESERVATION: from ANY state the invariants allow,
                #    one loop step must land back inside the invariants
                env_h, hfacts = havoc_like(env, changed)
                facts = list(hfacts)
                for _, c in inferred:
                    try:
                        facts.append(c(env_h))
                    except KeyError:
                        pass
                for inv_expr, _ in s.invariants:
                    try:
                        facts.append(to_z3(inv_expr, env_h, None))
                    except Unprovable:
                        pass
                cond_h = to_z3(s.cond, env_h, ctx)
                ctx_body = Ctx(ctx.conds + facts + [cond_h],
                               list(ctx.assum) + facts + [cond_h],
                               list(ctx.param_assum), ctx.caller)
                exits = []
                for pctx, ret, penv in explore(list(s.body), dict(env_h),
                                               ctx_body):
                    if ret is FELL_OFF:
                        for inv_expr, iline in s.invariants:
                            prove_invariant(inv_expr, iline, penv, pctx,
                                            "after one loop step")
                    else:
                        exits.append((pctx, ret, penv))  # return inside loop
                # 2b. THE LAST TURN. A counter that starts inside the
                #     loop's limit and steps by exactly one takes every
                #     value up to the largest the condition allows - so
                #     that turn really happens, and a read on it is a
                #     real read. Pinning the counter there turns "might
                #     be out of range somewhere" into a fact.
                if bound_of(s, env, ctx, changed) is not None:
                    counter, last, start = bound_of(s, env, ctx, changed)
                    reach = new_solver()
                    reach.add(*ctx.param_assum)
                    reach.add(*ctx.conds)
                    reach.add(z3.Not(start <= last))
                    if verdict_of(reach) == z3.unsat:      # the turn happens
                        env_last, lfacts = havoc_like(env, changed)
                        env_last[counter] = last
                        ctx_last = Ctx(
                            ctx.conds + lfacts,
                            list(ctx.assum) + lfacts,
                            list(ctx.param_assum), ctx.caller)
                        pinned_counter[0] = True
                        try:
                            explore(list(s.body), dict(env_last), ctx_last)
                        except Unprovable:
                            pass
                        finally:
                            pinned_counter[0] = False

                # 3. AFTERWARD: all we know is invariants hold, cond is false
                env_a, hfacts_a = havoc_like(env, changed)
                facts_a = list(hfacts_a)
                for _, c in inferred:
                    try:
                        facts_a.append(c(env_a))
                    except KeyError:
                        pass
                for inv_expr, _ in s.invariants:
                    try:
                        facts_a.append(to_z3(inv_expr, env_a, None))
                    except Unprovable:
                        pass
                cond_a = to_z3(s.cond, env_a, ctx)
                ctx_after = Ctx(ctx.conds + facts_a + [z3.Not(cond_a)],
                                list(ctx.assum) + facts_a + [z3.Not(cond_a)],
                                list(ctx.param_assum), ctx.caller)
                return exits + explore(stmts[i + 1:], env_a, ctx_after)
            elif isinstance(s, ExprStmt):
                try:
                    to_z3(s.expr, env, ctx)
                except Unprovable:
                    scan_calls(s.expr, env, ctx)   # still verify call sites
            else:
                raise Unprovable()
            i += 1
        return [(ctx, FELL_OFF, dict(env))]

    cache_ref = _proof_cache_ref(source_path, source_text) if use_cache \
        else None
    cache = _cache_load(cache_ref)
    settled: dict = {}          # what this run confirmed
    for fn in funcs:
        key = proof_key(fn, table, records) if use_cache else None
        if key is not None and key in cache:
            remembered = cache[key]
            settled[key] = remembered
            if remembered.get("proven") and proven_out is not None:
                proven_out.add(fn.name)
            for e in remembered.get("errors", []):
                errors.append(VelarisError(
                    e["code"], e["message"], e["line"],
                    fixes=e.get("fixes", []), file=e.get("file")))
            continue
        before_errors = len(errors)
        current_fn[0] = fn
        saw_fp[0] = False              # FP budget only when FP appears
        ran_out[0] = False             # and a fresh clock with it
        total_facts.clear()            # the sums of the last function's
        _total_seen.clear()            # lists say nothing about this one's
        env = {}
        list_facts = []
        for pname, ptype in fn.params:
            ptype = erase_wrappers(ptype)   # an amount is its minor units;
                                            # a secret is what it wraps
            if ptype in ("Int", "Bool", "Float", "Text"):
                env[pname] = mk(pname, ptype)
            elif ptype == "List of Int":
                arr = z3.Array(pname, z3.IntSort(), z3.IntSort())
                ln = z3.Int(pname + "__n")
                env[pname] = ListVal(arr, ln)
                list_facts.append(ln >= 0)
            elif ptype == "List of Text":
                arr = z3.Array(pname, z3.IntSort(), z3.StringSort())
                ln = z3.Int(pname + "__n")
                env[pname] = ListVal(arr, ln)
                list_facts.append(ln >= 0)
            elif ptype == "List of List of Int":
                inner = z3.ArraySort(z3.IntSort(), z3.IntSort())
                rows = z3.Array(pname, z3.IntSort(), inner)
                lens = z3.Array(pname + "__lens", z3.IntSort(),
                                z3.IntSort())
                ln = z3.Int(pname + "__n")
                env[pname] = GridVal(rows, lens, ln)
                list_facts.append(ln >= 0)
                k0 = z3.Int(pname + "__k")
                list_facts.append(z3.ForAll(
                    [k0], z3.Select(lens, k0) >= 0))
            elif ptype in rec_fields and provable_rec(ptype):
                env[pname] = mk_rec(pname, ptype)
            elif (ptype.startswith("List of ")
                  and ptype[len("List of "):] in rec_fields
                  and provable_rec(ptype[len("List of "):])):
                rname = ptype[len("List of "):]
                arrays = {}
                for fname, ftype in rec_fields[rname]:
                    if ftype == "Int":
                        arrays[fname] = z3.Array(
                            f"{pname}__{fname}", z3.IntSort(),
                            z3.IntSort())
                ln = z3.Int(pname + "__n")
                env[pname] = RecListVal(rname, arrays, ln)
                list_facts.append(ln >= 0)
            elif ptype.startswith("List of "):
                # the contents cannot be modelled, but the LENGTH can -
                # and length is what contracts about lists usually say.
                # Without this, one length(items) in a conjunction threw
                # the whole requires away, checkable parts included.
                ln = z3.Int(pname + "__n")
                env[pname] = OpaqueList(ln)
                list_facts.append(ln >= 0)
            elif ptype.startswith("Map of "):
                mv = mk_map(pname, ptype)
                if mv is not None:
                    env[pname] = mv
        import dataclasses as _dc

        def mentions_case(node) -> bool:
            if isinstance(node, (list, tuple)):
                return any(mentions_case(x) for x in node)
            if not _dc.is_dataclass(node):
                return False
            if isinstance(node, Call) and node.name in ("upper", "lower"):
                return True
            return any(mentions_case(getattr(node, f.name))
                       for f in _dc.fields(node))

        def mentions(node, names) -> bool:
            if isinstance(node, (list, tuple)):
                return any(mentions(x, names) for x in node)
            if not _dc.is_dataclass(node):
                return False
            if isinstance(node, Call) and node.name in names:
                return True
            return any(mentions(getattr(node, f.name), names)
                       for f in _dc.fields(node))

        parts = [fn.body, [e for e, _ in fn.ensures],
                 [e for e, _ in fn.requires]]
        if any(mentions(p, ("upper", "lower")) for p in parts):
            list_facts.extend(CASE_AXIOMS)   # only where they matter
        if any(mentions(p, ("split",)) for p in parts):
            list_facts.extend(SPLIT_AXIOMS)
        ctx = Ctx([], list(list_facts), list(list_facts), fn.name)
        try:
            for r_expr, _ in fn.requires:
                # If a premise cannot be translated, the whole proof is
                # off: proving with dropped premises would manufacture
                # false counterexamples. Runtime checks still guard.
                fact = to_z3(r_expr, dict(env), None)
                ctx.assum.append(fact)
                ctx.param_assum.append(fact)
            paths = explore(list(fn.body), dict(env), ctx)
            if not fn.ensures:
                continue
            for pctx, ret, _ in paths:
                if ret is FAILED:
                    continue           # ensures speaks only of returns
                if ret is FELL_OFF:
                    raise Unprovable()
                for ens_expr, cline in fn.ensures:
                    e2 = dict(env)
                    e2["result"] = ret
                    goal = to_z3(ens_expr, e2, None)
                    solver = new_solver()
                    solver.add(*pctx.assum)
                    solver.add(*pctx.conds)
                    solver.add(z3.Not(goal))
                    verdict = verdict_of(solver)
                    if verdict == z3.sat:
                        if has_fresh(ret) or has_fresh(goal) or any(
                                has_fresh(c) for c in pctx.conds):
                            # counterexample depends on a summarized call:
                            # might be impossible in reality - never claim
                            # "proven"; fall back to runtime checks instead
                            raise Unprovable()
                        m = solver.model()
                        vals = ", ".join(
                            show_val(p, v, m)
                            for p, v in sorted(env.items()))
                        if isinstance(ret, RecVal):
                            rv = show_val("r", ret, m).split(" = ", 1)[-1]
                        elif isinstance(ret, ListVal):
                            rv = "a list"
                        elif isinstance(ret, MapVal):
                            rv = "a map"
                        elif isinstance(ret, GridVal):
                            rv = "a list of lists"
                        else:
                            rv = m.eval(ret, model_completion=True)
                        raise VelarisError("E700",
                            f"promise cannot be kept: {nice_name(fn.name)} ensures "
                            f"{expr_str(ens_expr)} - proven without running "
                            f"the program: {vals} gives result = {rv}",
                            cline,
                            fixes=["fix the code so the promise holds for "
                                   "every allowed input",
                                   "or add a 'requires' that rules out "
                                   "such inputs"])
                    if verdict != z3.unsat:
                        raise Unprovable()
            if proven_out is not None and (fn.ensures or fn.requires):
                proven_out.add(fn.name)   # every obligation discharged
            if key is not None:
                settled[key] = {
                    "proven": bool(fn.ensures or fn.requires),
                    "errors": [{"code": e.code, "message": e.message,
                                "line": e.line, "fixes": e.fixes,
                                "file": e.file}
                               for e in errors[before_errors:]]}
        except Unprovable:
            # a proof the clock ended is not remembered: nothing was
            # settled, so the next run should spend its budget again
            if key is not None and not ran_out[0]:
                settled[key] = {"proven": False, "errors": [
                    {"code": e.code, "message": e.message, "line": e.line,
                     "fixes": e.fixes, "file": e.file}
                    for e in errors[before_errors:]]}
            continue                    # runtime promise checks still guard
        except z3.Z3Exception:
            continue                    # solver hiccup: runtime still guards
        except VelarisError as e:
            errors.append(blame(fn, e))
            if key is not None:         # a refutation is worth remembering
                settled[key] = {"proven": False, "errors": [
                    {"code": x.code, "message": x.message, "line": x.line,
                     "fixes": x.fixes, "file": x.file}
                    for x in errors[before_errors:]]}
            continue

    if cache_ref is not None:
        _cache_save(cache_ref, settled)

    # A proof that ran out of time says so, here and in every report
    # built from this run. Silence would read exactly like the prover
    # looking and finding nothing wrong, which is the one thing it must
    # never be mistaken for.
    left = [t for name, t in sorted(timed_out.items())
            if proven_out is None or name not in proven_out]
    if timeouts_out is not None:
        timeouts_out.extend(left)
    for t in left:
        spent = (f"{t['seconds']:.0f}" if t["seconds"] >= 1
                 else f"{t['seconds']:g}")
        print(f"note: the proof of {nice_name(t['name'])} ran out of time "
              f"after {spent}s and was abandoned - nothing was proven and "
              f"nothing was refuted, so its promises are checked while "
              f"running instead. This is not 'the prover found nothing "
              f"wrong'. Give it longer with --proof-timeout "
              f"{max(2, int(t['seconds'] * 2))} (or "
              f"{PROOF_TIMEOUT_ENV}={max(2, int(t['seconds'] * 2))}).",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# 4d. NATIVE COMPILER (v0.9) — compile pure Int functions to machine code
#     via LLVM. Eligible: params and return are Int; body uses only math,
#     comparisons, and/or/not, if, while, let/assign, and calls to other
#     eligible functions. No effects; contracts are allowed once PROVEN
#     (an unproven promise still needs its runtime check); no '/';
#     lists and text may be READ (bounds-guarded), not built.
# ---------------------------------------------------------------------------

_NATIVE_KEEPALIVE = []          # prevents the JIT engine being garbage-collected


def native_eligible(funcs: list[Function],
                    proven: set = frozenset()) -> set[str]:
    table = {f.name: f for f in funcs}

    def locally_ok(fn: Function):
        if fn.effects or fn.can_fail or fn.type_vars:
            return None
        if (fn.requires or fn.ensures) and fn.name not in proven:
            return None       # unproven promises still need runtime checks
        if fn.return_type not in ("Int", "Float", "Bool"):
            return None      # text results stay interpreted: returning a
                             # struct by value is platform-specific ABI
        if any(pt not in ("Int", "Float", "Bool", "List of Int", "Text")
               for _, pt in fn.params):
            return None
        list_params = {p for p, t in fn.params if t == "List of Int"}
        text_params = {p for p, t in fn.params if t == "Text"}
        calls, ok = set(), [True]
        local_text = set(text_params)

        def text_valued(e) -> bool:
            if isinstance(e, Str):
                return True
            if isinstance(e, Var):
                return e.name in local_text
            if isinstance(e, Call):
                callee = table.get(e.name)
                return callee is not None and callee.return_type == "Text"
            if isinstance(e, BinOp) and e.op == "+":
                return text_valued(e.left)
            return False

        def note_text(stmts):           # locals that hold text
            for s in stmts:
                if isinstance(s, (Let, Assign)) and text_valued(s.value):
                    local_text.add(s.name)
                elif isinstance(s, If):
                    note_text(s.then); note_text(s.other)
                elif isinstance(s, While):
                    note_text(s.body)
        note_text(fn.body)
        note_text(fn.body)              # twice: assignments after use

        def we(e):
            if isinstance(e, Str):
                return                  # text literals are compiled in
            if isinstance(e, (Num, FloatNum, Bool, Var)):
                return
            if (isinstance(e, Call) and e.name in ("length", "get")
                    and e.args and isinstance(e.args[0], Var)
                    and e.args[0].name in list_params):
                for a in e.args[1:]:
                    we(a)
                return
            if (isinstance(e, Call) and e.name in ("length", "code_at")
                    and e.args and text_valued(e.args[0])):
                we(e.args[0])
                for a in e.args[1:]:
                    we(a)
                return
            if isinstance(e, (Not, Neg)):
                we(e.value)
            elif isinstance(e, BinOp):
                if e.op in ("/", "%"):
                    ok[0] = False       # backend semantics differ on negatives
                else:
                    we(e.left); we(e.right)
            elif isinstance(e, Call):
                if builtin_reached(e.name, table) is not None \
                        or e.name not in table:
                    ok[0] = False
                else:
                    calls.add(e.name)
                    for a in e.args:
                        we(a)
            else:
                ok[0] = False          # Str, ListLit

        def ws(s):
            if isinstance(s, (Let, Assign)):
                we(s.value)
            elif isinstance(s, Return):
                if s.value is None:
                    ok[0] = False
                else:
                    we(s.value)
            elif isinstance(s, If):
                we(s.cond)
                for x in s.then + s.other:
                    ws(x)
            elif isinstance(s, While):
                if s.invariants:
                    ok[0] = False      # invariant checks must not be skipped
                we(s.cond)
                for x in s.body:
                    ws(x)
            elif isinstance(s, ExprStmt):
                we(s.expr)
            else:
                ok[0] = False

        for s in fn.body:
            ws(s)
        return calls if ok[0] else None

    cand = {}
    for f in funcs:
        c = locally_ok(f)
        if c is not None:
            cand[f.name] = c
    changed = True
    while changed:                      # drop anyone calling a non-candidate
        changed = False
        for name in list(cand):
            if not cand[name] <= set(cand):
                del cand[name]
                changed = True
    # A directly or mutually recursive function is NOT compiled to native
    # (7.1.2): the interpreter's E609 depth guard (call_function) has no
    # equivalent in native code, so a recursion that never bottoms out would
    # loop unbounded in native code instead of stopping. Interpreting it
    # keeps E609. Find every function that can reach itself through the
    # call graph and drop it, then drop anyone left calling a dropped one.
    reach = {n: set(cand[n] & set(cand)) for n in cand}
    grew = True
    while grew:
        grew = False
        for n in reach:
            add = set().union(*(reach[m] for m in reach[n])) if reach[n] \
                else set()
            if not add <= reach[n]:
                reach[n] |= add
                grew = True
    for n in [n for n in cand if n in reach[n]]:
        del cand[n]
    changed = True
    while changed:
        changed = False
        for name in list(cand):
            if not cand[name] <= set(cand):
                del cand[name]
                changed = True
    return set(cand)


def compile_native(funcs: list[Function],
                   proven: set = frozenset()) -> dict:
    """Native code is an optimisation, never a requirement: if anything
    about this machine's backend disagrees with us, the program runs
    interpreted and behaves exactly the same, just slower."""
    try:
        return _compile_native(funcs, proven)
    except Exception:
        return {}


def _compile_native(funcs: list[Function],
                    proven: set = frozenset()) -> dict:
    eligible = native_eligible(funcs, proven)
    if not eligible:
        return {}
    try:
        from llvmlite import ir, binding
    except ImportError:
        print("note: llvmlite is not installed - running fully interpreted "
              "(for native speed: pip install llvmlite)", file=sys.stderr)
        return {}

    i64 = ir.IntType(64)
    f64 = ir.DoubleType()
    i64p = ir.PointerType(i64)
    i32 = ir.IntType(32)
    i32p = ir.PointerType(i32)
    TEXT = ir.LiteralStructType([i32p, i64])
    LTY = {"Int": i64, "Bool": i64, "Float": f64, "Text": TEXT}


    def llvm_params(fn):
        out = []
        for _, pt in fn.params:
            if pt == "List of Int":
                out += [i64p, i64]        # data pointer, then length
            elif pt == "Text":
                out += [i32p, i64]        # code points, then length
            else:
                out.append(LTY[pt])
        return out
    module = ir.Module(name="velaris")
    oob = ir.GlobalVariable(module, i64, name="velaris_oob")
    oob.initializer = i64(0)
    oob_idx = ir.GlobalVariable(module, i64, name="velaris_oob_idx")
    oob_idx.initializer = i64(0)
    oob_len = ir.GlobalVariable(module, i64, name="velaris_oob_len")
    oob_len.initializer = i64(0)
    arena = ir.GlobalVariable(module, i32p, name="velaris_arena")
    arena.initializer = ir.Constant(i32p, None)
    arena_cap = ir.GlobalVariable(module, i64, name="velaris_arena_cap")
    arena_cap.initializer = i64(0)
    arena_used = ir.GlobalVariable(module, i64, name="velaris_arena_used")
    arena_used.initializer = i64(0)
    arena_full = ir.GlobalVariable(module, i64, name="velaris_arena_full")
    arena_full.initializer = i64(0)
    overflowed = ir.GlobalVariable(module, i64, name="velaris_overflow")
    overflowed.initializer = i64(0)
    ovf_fns = {}
    for op_name in ("sadd", "ssub", "smul"):
        fty = ir.FunctionType(
            ir.LiteralStructType([i64, ir.IntType(1)]), [i64, i64])
        ovf_fns[op_name] = ir.Function(
            module, fty, name=f"llvm.{op_name}.with.overflow.i64")
    lit_count = [0]
    table = {f.name: f for f in funcs}
    llvm_fns = {}
    for name in eligible:
        fn = table[name]
        fty = ir.FunctionType(LTY[fn.return_type], llvm_params(fn))
        llvm_fns[name] = ir.Function(module, fty, name=name)

    def var_types(fn: Function) -> dict:
        """Sequentially infer each local's Velaris type for typed allocas."""
        tenv = dict(fn.params)

        def te(e) -> str:
            if isinstance(e, Num):
                return "Int"
            if isinstance(e, Str):
                return "Text"
            if isinstance(e, FloatNum):
                return "Float"
            if isinstance(e, Bool):
                return "Bool"
            if isinstance(e, Var):
                return tenv[e.name]
            if isinstance(e, Not):
                return "Bool"
            if isinstance(e, Neg):
                return te(e.value)
            if isinstance(e, Call):
                if e.name in ("length", "get", "code_at"):
                    return "Int"        # builtin reads used natively
                return table[e.name].return_type
            if isinstance(e, BinOp):
                if e.op in ("and", "or", "==", "!=", "<", ">", "<=", ">="):
                    return "Bool"
                return te(e.left)      # '+' on Text gives Text
            return "Int"

        def ts(stmts):
            for s in stmts:
                if isinstance(s, (Let, Assign)):
                    tenv.setdefault(s.name, te(s.value))
                elif isinstance(s, If):
                    ts(s.then); ts(s.other)
                elif isinstance(s, While):
                    ts(s.body)
        ts(fn.body)
        return tenv

    def collect_names(stmts, out):
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                collect_names(s.then, out); collect_names(s.other, out)
            elif isinstance(s, While):
                collect_names(s.body, out)

    CMP = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}

    for name in eligible:
        fn = table[name]
        lf = llvm_fns[name]
        entry = lf.append_basic_block("entry")
        b = ir.IRBuilder(entry)
        slots = {}
        tenv = var_types(fn)
        names = {p for p, _ in fn.params}
        collect_names(fn.body, names)
        lists = {}                     # name -> (data pointer, length)
        texts = {}                     # name -> (code points, length)
        list_names = {p for p, t in fn.params if t == "List of Int"}
        for n in sorted(names - list_names):
            slots[n] = b.alloca(LTY[tenv.get(n, "Int")], name=n)
        ai = 0
        for pname, ptype in fn.params:
            if ptype == "Text":
                data, ln = lf.args[ai], lf.args[ai + 1]
                data.name, ln.name = pname + "_data", pname + "_len"
                tv = b.insert_value(
                    b.insert_value(ir.Constant(TEXT, ir.Undefined), data, 0),
                    ln, 1)
                slots[pname] = b.alloca(TEXT, name=pname)
                b.store(tv, slots[pname])
                ai += 2
            elif ptype == "List of Int":
                data, ln = lf.args[ai], lf.args[ai + 1]
                data.name, ln.name = pname + "_data", pname + "_len"
                lists[pname] = (data, ln)
                ai += 2
            else:
                lf.args[ai].name = pname
                b.store(lf.args[ai], slots[pname])
                ai += 1

        def txt_ptr(v):
            return b.extract_value(v, 0)

        def txt_len(v):
            return b.extract_value(v, 1)

        def make_text(ptr, ln):
            t = b.insert_value(ir.Constant(TEXT, ir.Undefined), ptr, 0)
            return b.insert_value(t, ln, 1)

        def arena_alloc(n):
            """Bump-allocate n code points; flag (don't crash) if full."""
            used = b.load(arena_used)
            cap = b.load(arena_cap)
            room = b.icmp_signed("<=", b.add(used, n), cap)
            ok_bb = lf.append_basic_block("arena_ok")
            full_bb = lf.append_basic_block("arena_full")
            cont_bb = lf.append_basic_block("arena_done")
            b.cbranch(room, ok_bb, full_bb)
            b.position_at_end(ok_bb)
            base = b.load(arena)
            slot = b.gep(base, [used])
            b.store(b.add(used, n), arena_used)
            b.branch(cont_bb)
            b.position_at_end(full_bb)
            b.store(i64(1), arena_full)      # caller grows and retries
            fallback = b.load(arena)
            b.branch(cont_bb)
            b.position_at_end(cont_bb)
            phi = b.phi(i32p)
            phi.add_incoming(slot, ok_bb)
            phi.add_incoming(fallback, full_bb)
            room_phi = b.phi(ir.IntType(1))
            room_phi.add_incoming(ir.Constant(ir.IntType(1), 1), ok_bb)
            room_phi.add_incoming(ir.Constant(ir.IntType(1), 0), full_bb)
            return phi, room_phi

        def copy_into(dst, src_ptr, n, tag):
            """Copy n code points, one at a time (small texts, no libc)."""
            i_slot = b.alloca(i64, name=tag + "_i")
            b.store(i64(0), i_slot)
            head = lf.append_basic_block(tag + "_head")
            body = lf.append_basic_block(tag + "_body")
            done = lf.append_basic_block(tag + "_done")
            b.branch(head)
            b.position_at_end(head)
            iv = b.load(i_slot)
            b.cbranch(b.icmp_signed("<", iv, n), body, done)
            b.position_at_end(body)
            iv2 = b.load(i_slot)
            b.store(b.load(b.gep(src_ptr, [iv2])), b.gep(dst, [iv2]))
            b.store(b.add(iv2, i64(1)), i_slot)
            b.branch(head)
            b.position_at_end(done)

        def ee(e):                    # emit expression (i64 or double)
            if isinstance(e, Num):
                return i64(e.value)
            if isinstance(e, Str):
                pts = [ord(c) for c in e.value]
                lit_count[0] += 1
                arr_ty = ir.ArrayType(i32, max(len(pts), 1))
                g = ir.GlobalVariable(module, arr_ty,
                                      name=f"text_lit_{lit_count[0]}")
                g.global_constant = True
                g.initializer = ir.Constant(
                    arr_ty, [ir.Constant(i32, p) for p in pts] or
                    [ir.Constant(i32, 0)])
                ptr = b.gep(g, [i64(0), i64(0)])
                return make_text(ptr, i64(len(pts)))
            if isinstance(e, FloatNum):
                return ir.Constant(f64, e.value)
            if isinstance(e, Bool):
                return i64(1 if e.value else 0)
            if isinstance(e, Var):
                return b.load(slots[e.name])
            if isinstance(e, Not):
                return b.xor(ee(e.value), i64(1))
            if isinstance(e, Neg):
                v = ee(e.value)
                if v.type == f64:
                    return b.fsub(ir.Constant(f64, 0.0), v)
                return b.sub(i64(0), v)
            if (isinstance(e, Call) and e.name in ("length", "code_at")
                    and e.args and not (isinstance(e.args[0], Var)
                                        and e.args[0].name in lists)):
                tv = ee(e.args[0])
                if tv.type != TEXT:
                    raise NotImplementedError("length on a non-text value")
                data, ln = txt_ptr(tv), txt_len(tv)
                if e.name == "length":
                    return ln
                idx = ee(e.args[1])
                inside = b.and_(b.icmp_signed(">=", idx, i64(0)),
                                b.icmp_signed("<", idx, ln))
                ok_bb = lf.append_basic_block("char_ok")
                bad_bb = lf.append_basic_block("char_out")
                cont_bb = lf.append_basic_block("char_done")
                b.cbranch(inside, ok_bb, bad_bb)
                b.position_at_end(ok_bb)
                ch = b.zext(b.load(b.gep(data, [idx])), i64)
                b.branch(cont_bb)
                b.position_at_end(bad_bb)
                b.store(i64(1), oob)
                b.store(idx, oob_idx)
                b.store(ln, oob_len)
                b.branch(cont_bb)
                b.position_at_end(cont_bb)
                phi = b.phi(i64)
                phi.add_incoming(ch, ok_bb)
                phi.add_incoming(i64(0), bad_bb)
                return phi
            if (isinstance(e, Call) and e.name in ("length", "get")
                    and e.args and isinstance(e.args[0], Var)
                    and e.args[0].name in lists):
                data, ln = lists[e.args[0].name]
                if e.name == "length":
                    return ln
                idx = ee(e.args[1])
                inside = b.and_(b.icmp_signed(">=", idx, i64(0)),
                                b.icmp_signed("<", idx, ln))
                ok_bb = lf.append_basic_block("read_ok")
                bad_bb = lf.append_basic_block("read_out")
                cont_bb = lf.append_basic_block("read_done")
                b.cbranch(inside, ok_bb, bad_bb)
                b.position_at_end(ok_bb)          # in range: real read
                val = b.load(b.gep(data, [idx]))
                b.branch(cont_bb)
                b.position_at_end(bad_bb)         # out of range: no read,
                b.store(i64(1), oob)              # just record it
                b.store(idx, oob_idx)
                b.store(ln, oob_len)
                b.branch(cont_bb)
                b.position_at_end(cont_bb)
                phi = b.phi(i64)
                phi.add_incoming(val, ok_bb)
                phi.add_incoming(i64(0), bad_bb)
                return phi
            if isinstance(e, Call):
                args_ll = []
                callee = table.get(e.name)
                want = [t for _, t in callee.params] if callee else []
                for pos, a in enumerate(e.args):
                    if pos < len(want) and want[pos] == "Text":
                        tv = ee(a)
                        args_ll += [txt_ptr(tv), txt_len(tv)]
                        continue
                    if isinstance(a, Var) and a.name in lists:
                        args_ll += list(lists[a.name])
                    else:
                        args_ll.append(ee(a))
                return b.call(llvm_fns[e.name], args_ll)
            if isinstance(e, BinOp) and e.op == "+":
                lv = ee(e.left)
                if lv.type == TEXT:
                    rv = ee(e.right)
                    if rv.type != TEXT:
                        raise NotImplementedError
                    ln_l, ln_r = txt_len(lv), txt_len(rv)
                    total = b.add(ln_l, ln_r)
                    dst, had_room = arena_alloc(total)
                    # no room means NO copying: the caller grows the
                    # buffer and runs the whole call again
                    do_bb = lf.append_basic_block("cat_do")
                    skip_bb = lf.append_basic_block("cat_skip")
                    end_bb = lf.append_basic_block("cat_end")
                    b.cbranch(had_room, do_bb, skip_bb)
                    b.position_at_end(do_bb)
                    copy_into(dst, txt_ptr(lv), ln_l, "cpl")
                    copy_into(b.gep(dst, [ln_l]), txt_ptr(rv), ln_r, "cpr")
                    did_bb = b.block          # loops moved us elsewhere
                    b.branch(end_bb)
                    b.position_at_end(skip_bb)
                    skipped_bb = b.block
                    b.branch(end_bb)
                    b.position_at_end(end_bb)
                    ln_phi = b.phi(i64)
                    ln_phi.add_incoming(total, did_bb)
                    ln_phi.add_incoming(i64(0), skipped_bb)
                    return make_text(dst, ln_phi)
            if isinstance(e, BinOp):
                if e.op == "and":
                    return b.and_(ee(e.left), ee(e.right))
                if e.op == "or":
                    return b.or_(ee(e.left), ee(e.right))
                l, r = ee(e.left), ee(e.right)
                flt = l.type == f64

                def checked(kind, value):
                    """Same answer as interpreted: too big is an error."""
                    pair = b.call(ovf_fns[kind], [l, r])
                    bit = b.extract_value(pair, 1)
                    was = b.load(overflowed)
                    b.store(b.select(bit, i64(1), was), overflowed)
                    return b.extract_value(pair, 0)

                if e.op == "+":
                    return b.fadd(l, r) if flt else checked("sadd", None)
                if e.op == "-":
                    return b.fsub(l, r) if flt else checked("ssub", None)
                if e.op == "*":
                    return b.fmul(l, r) if flt else checked("smul", None)
                if flt:
                    return b.zext(b.fcmp_ordered(CMP[e.op], l, r), i64)
                return b.zext(b.icmp_signed(CMP[e.op], l, r), i64)
            raise AssertionError("unreachable")

        def truthy(e):
            return b.icmp_signed("!=", ee(e), i64(0))

        def es(stmts):                              # emit statements
            for s in stmts:
                if b.block.is_terminated:
                    return
                if isinstance(s, (Let, Assign)):
                    b.store(ee(s.value), slots[s.name])
                elif isinstance(s, Return):
                    b.ret(ee(s.value))
                elif isinstance(s, ExprStmt):
                    ee(s.expr)
                elif isinstance(s, If):
                    bb_then = lf.append_basic_block("then")
                    bb_else = lf.append_basic_block("else")
                    bb_cont = lf.append_basic_block("cont")
                    b.cbranch(truthy(s.cond), bb_then, bb_else)
                    b.position_at_end(bb_then)
                    es(s.then)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_else)
                    es(s.other)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_cont)
                elif isinstance(s, While):
                    bb_cond = lf.append_basic_block("wcond")
                    bb_body = lf.append_basic_block("wbody")
                    bb_end = lf.append_basic_block("wend")
                    b.branch(bb_cond)
                    b.position_at_end(bb_cond)
                    b.cbranch(truthy(s.cond), bb_body, bb_end)
                    b.position_at_end(bb_body)
                    es(s.body)
                    if not b.block.is_terminated:
                        b.branch(bb_cond)
                    b.position_at_end(bb_end)

        es(fn.body)
        if not b.block.is_terminated:
            b.ret(ir.Constant(f64, 0.0)
                  if fn.return_type == "Float" else i64(0))

    for init in ("initialize", "initialize_native_target",
                 "initialize_native_asmprinter"):
        try:                   # each may be required or deprecated,
            getattr(binding, init)()       # depending on llvmlite version
        except (RuntimeError, AttributeError):
            pass
    target = binding.Target.from_default_triple()
    tm = target.create_target_machine(opt=3)
    backing = binding.parse_assembly(str(module))
    backing.verify()
    try:                                    # optimize IR if this API exists
        pto = binding.create_pipeline_tuning_options()
        pto.speed_level = 3
        pb = binding.create_pass_builder(tm, pto)
        pb.getModulePassManager().run(backing, pb)
    except Exception:
        try:
            pmb = binding.PassManagerBuilder()
            pmb.opt_level = 3
            pm = binding.ModulePassManager()
            pmb.populate(pm)
            pm.run(backing)
        except Exception:
            pass                            # unoptimized native is still fast
    engine = binding.create_mcjit_compiler(backing, tm)
    engine.finalize_object()
    _NATIVE_KEEPALIVE.append(engine)

    import ctypes
    CT = {"Int": ctypes.c_int64, "Bool": ctypes.c_int64,
          "Float": ctypes.c_double}
    I64P = ctypes.POINTER(ctypes.c_int64)
    I32P = ctypes.POINTER(ctypes.c_uint32)
    oob_addr = engine.get_global_value_address("velaris_oob")
    idx_addr = engine.get_global_value_address("velaris_oob_idx")
    len_addr = engine.get_global_value_address("velaris_oob_len")
    flag = ctypes.cast(oob_addr, I64P)
    ovf_cell = ctypes.cast(
        engine.get_global_value_address("velaris_overflow"), I64P)
    flag_i = ctypes.cast(idx_addr, I64P)
    flag_n = ctypes.cast(len_addr, I64P)

    class CText(ctypes.Structure):
        _fields_ = [("data", ctypes.POINTER(ctypes.c_uint32)),
                    ("length", ctypes.c_int64)]

    arena_state = {"buf": (ctypes.c_uint32 * (1 << 16))(), "cap": 1 << 16}
    arena_ptr_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena"),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)))
    arena_cap_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_cap"), I64P)
    arena_used_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_used"), I64P)
    arena_full_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_full"), I64P)

    def install_arena():
        arena_ptr_cell[0] = ctypes.cast(
            arena_state["buf"], ctypes.POINTER(ctypes.c_uint32))
        arena_cap_cell[0] = arena_state["cap"]
    install_arena()

    def grow_arena():
        arena_state["cap"] *= 4
        arena_state["buf"] = (ctypes.c_uint32 * arena_state["cap"])()
        install_arena()

    def wrap(fn, raw):
        types = [pt for _, pt in fn.params]
        wants_bool = fn.return_type == "Bool"
        wants_text = fn.return_type == "Text"

        def call(*vals):
            cargs = []
            keep = []                    # keep buffers alive for the call
            for t, v in zip(types, vals):
                if t == "Text":
                    buf = (ctypes.c_uint32 * len(v))(*[ord(c) for c in v])
                    keep.append(buf)
                    cargs += [ctypes.cast(buf, I32P), len(v)]
                elif t == "List of Int":
                    buf = (ctypes.c_int64 * len(v))(*v)
                    keep.append(buf)
                    cargs += [ctypes.cast(buf, I64P), len(v)]
                else:
                    cargs.append(v)
            for _attempt in range(6):
                flag[0] = 0
                ovf_cell[0] = 0
                arena_used_cell[0] = 0
                arena_full_cell[0] = 0
                r = raw(*cargs)
                if ovf_cell[0]:
                    ovf_cell[0] = 0
                    raise VelarisError("E407",
                        "this arithmetic made a number too big to hold "
                        f"(whole numbers go from {INT_MIN} to "
                        f"{INT_MAX})", fn.line,
                        fixes=["keep the numbers smaller",
                               "or work in smaller units, like cents "
                               "instead of rupees"])
                if not arena_full_cell[0]:
                    break
                grow_arena()          # too small: bigger buffer, run again
            else:
                raise VelarisError("E607",
                    "this text grew too large to build", fn.line,
                    fixes=["build shorter pieces of text"])
            if flag[0]:                  # the read was refused, not made
                i, n = flag_i[0], flag_n[0]
                flag[0] = 0
                what = ("text" if any(t == "Text" for t in types)
                        else "list")
                unit = "character" if what == "text" else "item"
                raise VelarisError("E602",
                    f"position {i} is outside the {what} "
                    f"(it has {n} {unit}(s))", fn.line,
                    fixes=["positions go from 0 to length - 1",
                           "check with length(...) before using get"])
            if wants_text:
                return "".join(chr(r.data[i]) for i in range(r.length))
            return bool(r) if wants_bool else r
        return call

    out = {}
    for name in eligible:
        fn = table[name]
        ctypes_args = []
        for _, pt in fn.params:
            if pt == "Text":
                ctypes_args += [I32P, ctypes.c_int64]
            elif pt == "List of Int":
                ctypes_args += [I64P, ctypes.c_int64]
            else:
                ctypes_args.append(CT[pt])
        proto = ctypes.CFUNCTYPE(CT[fn.return_type], *ctypes_args)
        raw = proto(engine.get_function_address(name))
        out[name] = wrap(fn, raw)
    return out


# ---------------------------------------------------------------------------
# 5. INTERPRETER — actually run the program (main() is the entry point)
# ---------------------------------------------------------------------------

class ReturnSignal(Exception):
    def __init__(self, value): self.value = value


class RecElem:
    """rows[i] before a field is chosen: .amount selects from the
    field's array at that index."""
    def __init__(self, src, idx):
        self.src = src
        self.idx = idx


class RecListVal:
    """A list of records, as one array per provable field.

    get(rows, i).amount becomes Select(amount_arr, i) - so bounds are
    checked (the off-by-one over a record list refused before running,
    like the Int-list case) and field arithmetic can prove.
    """
    def __init__(self, rname, arrays, length):
        self.rname = rname          # the record type's name
        self.arrays = arrays        # field name -> z3 Int array
        self.length = length


class OpaqueList:
    """A list whose contents the prover cannot see - only its length.

    Enough for the contracts people actually write about lists of
    records: length(items) > 0, length(result) == length(items), and
    for a divisor to be provably nonzero.
    """
    def __init__(self, length):
        self.length = length


class FailSignal(Exception):
    def __init__(self, reason): self.reason = reason


class HandleValue:
    """A ticket for something living on the Python side of the bridge."""
    __slots__ = ("id", "what")

    def __init__(self, id_: int, what: str):
        self.id, self.what = id_, what

    def __repr__(self):
        return f"<{self.what} #{self.id}>"


PY_OBJECTS: dict = {}
PY_NEXT = [1]


class RecordValue:
    def __init__(self, rname: str, fields: dict):
        self.rname, self.fields = rname, fields

    def __eq__(self, other):
        return (isinstance(other, RecordValue)
                and self.rname == other.rname
                and self.fields == other.fields)


def to_text(v) -> str:
    if v.__class__ is MoneyValue:
        return money_text(v)
    if isinstance(v, Function):
        return f"fn {v.name}"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{to_text(k)}: {to_text(x)}"
                               for k, x in v.items()) + "}"
    if isinstance(v, RecordValue):
        inner = ", ".join(f"{k}: {to_text(x)}" for k, x in v.fields.items())
        return f"{v.rname}({inner})"
    if isinstance(v, HandleValue):
        return f"<{v.what} #{v.id}>"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x) for x in v) + "]"
    return str(v)


# effects per builtin, sorted once instead of on every call
BUILTIN_EFFECTS = {n: tuple(sorted(d.get("effects", ())))
                   for n, d in BUILTINS.items() if d.get("effects")}


def run_money(name: str, args: list, line: int):
    """The Money builtins while running (SPEC.md 4.4). The type checker
    has already seen to the currencies and the written arguments; what
    is left is exact integer arithmetic, and its range."""
    if name == "money":
        cur = str(args[1])
        if cur not in CURRENCIES:              # kept out before running
            raise VelarisError("E551",
                f"'{cur}' is not a currency Velaris knows", line)
        return MoneyValue(int(args[0]), cur)
    if name == "units_of":
        x = args[0]
        if x.__class__ is MoneyValue:
            return x.units
        total = 0
        for m in x:                            # as a loop adding them
            total = checked_int(total + m.units, "units_of", line)
        return total
    if name == "with_units":
        return MoneyValue(int(args[1]), args[0].currency)
    if name == "text_of":
        return money_text(args[0])
    if name == "parse_money":
        return parse_money_text(args[0], str(args[1]))
    mode = str(args[-1])
    if mode not in ROUNDING:                   # kept out before running
        raise VelarisError("E552",
            f"'{mode}' is not a rounding mode", line)
    m = args[0]
    if name == "percent_of":
        num, den = int(args[1]), int(args[2])
        if den == 0:
            raise VelarisError("E403", "percent_of with a denominator of "
                               "zero", line,
                               fixes=["check the denominator first"])
        # the product is exact, however large: only the answer must fit
        return checked_int(MoneyValue(round_ratio(m.units * num, den, mode),
                                      m.currency), "percent_of", line)
    by = int(args[1])                          # divide_or_fail
    if by == 0:
        raise FailSignal("cannot divide an amount by zero")
    units = round_ratio(m.units, by, mode)
    if not INT_MIN <= units <= INT_MAX:
        raise FailSignal(f"dividing {money_text(m)} by {by} makes an "
                         f"amount too big to hold")
    return MoneyValue(units, m.currency)


def run_builtin(name: str, args: list, line: int):
    # The hot three, before anything else: these are most of the builtin
    # calls in any program and used to sit behind thirty string
    # comparisons and two module imports. None of them has effects, so
    # the budget check does not apply.
    if name == "length":
        a0 = args[0]
        return len(a0) if not isinstance(a0, str) else len(a0)
    if name == "get" and isinstance(args[0], list):
        xs, at = args[0], args[1]
        if not isinstance(at, int) or at < 0 or at >= len(xs):
            raise VelarisError("E602",
                f"this list has {len(xs)} item(s), so there is no "
                f"position {at}", line,
                fixes=["check the length before reading",
                       "or add a 'requires' about the length"])
        return xs[at]
    if name == "push" and isinstance(args[0], list):
        return args[0] + [args[1]]
    if name in MONEY_BUILTINS:
        return run_money(name, args, line)

    import time as _time
    import random as _rand
    for effect in BUILTIN_EFFECTS.get(name, ()):   # precomputed; this
        spend(effect, name, line)                  # ran sorted() on
                                                   # every single call
    if name == "print":
        print(to_text(args[0]))
        return None
    if name == "ask":
        try:
            return input(str(args[0]) + " ")
        except (EOFError, KeyboardInterrupt):
            raise VelarisError("E607", "no input available to read", line,
                               fixes=["run this program in a terminal where "
                                      "you can type an answer"])
    if name == "to_int":
        t = str(args[0]).strip()
        body = t[1:] if t.startswith("-") else t
        if not body.isdigit():
            raise FailSignal(f"'{args[0]}' is not a whole number")
        return int(t)
    if name == "to_text":
        return to_text(args[0])
    if name == "to_float":
        return float(args[0])
    if name == "round":
        return int(round(args[0]))
    if name == "contains":
        return str(args[1]) in str(args[0])
    if name == "split":
        if args[1] == "":
            raise VelarisError("E609", "cannot split by empty text", line,
                               fixes=['use a separator like " " or ","'])
        return str(args[0]).split(str(args[1]))
    if name == "upper":
        return str(args[0]).upper()
    if name == "chars":
        return list(str(args[0]))
    if name == "file_exists":
        real = allow_path("any", str(args[0]), name, line)
        count_op("fs", name, line)
        return os.path.exists(real)
    if name == "lower":
        return str(args[0]).lower()
    if name == "length":
        return len(args[0])
    if name == "pop":
        xs = args[0]
        if not xs:
            raise FailSignal("there is nothing left to take off the end")
        return list(xs[:-1])
    if name == "slice":
        xs, start, stop = args[0], int(args[1]), int(args[2])
        if start < 0 or stop > len(xs) or start > stop:
            raise FailSignal(
                f"a slice from {start} to {stop} does not fit a list of "
                f"{len(xs)}")
        return list(xs[start:stop])
    if name == "set_at":
        xs, at = args[0], int(args[1])
        if at < 0 or at >= len(xs):
            raise FailSignal(
                f"there is no position {at} in a list of {len(xs)}")
        out = list(xs)
        out[at] = args[2]
        return out
    if name in ("div_or_fail", "mod_or_fail"):
        a, b = int(args[0]), int(args[1])
        if b == 0:
            word = "divide" if name == "div_or_fail" else "take a remainder"
            raise FailSignal(f"cannot {word} by zero")
        return a // b if name == "div_or_fail" else a % b
    if name in ("add_or_fail", "sub_or_fail", "mul_or_fail"):
        a, b = int(args[0]), int(args[1])
        answer = (a + b if name == "add_or_fail" else
                  a - b if name == "sub_or_fail" else a * b)
        if not (-(2 ** 63) <= answer <= 2 ** 63 - 1):
            word = {"add_or_fail": "adding", "sub_or_fail": "subtracting",
                    "mul_or_fail": "multiplying"}[name]
            raise FailSignal(
                f"{word} {a} and {b} makes a number too big to hold")
        return answer
    if name == "push":
        return args[0] + [args[1]]
    if name == "put":
        m, k, v = args
        out = dict(m); out[k] = v
        return out
    if name == "has":
        return args[1] in args[0]
    if name == "keys":
        return list(args[0].keys())
    if name in ("py_new", "py_do", "py_field", "py_close"):
        import json as _json

        def resolve(module: str, func: str):
            return _ffi_resolve(module, func, name, line)

        def split_args(raw):
            """A JSON list of arguments; a trailing object is keywords."""
            try:
                vals = _json.loads(str(raw))
            except Exception as e:
                raise FailSignal(f"the arguments are not valid JSON: {e}")
            if not isinstance(vals, list):
                raise FailSignal("the arguments must be a JSON list")
            kwargs = {}
            if (vals and isinstance(vals[-1], dict)
                    and set(vals[-1]) != {"handle"}):
                kwargs = {str(k): v for k, v in vals[-1].items()}
                vals = vals[:-1]
            return [unwrap(v) for v in vals], {k: unwrap(v)
                                               for k, v in kwargs.items()}

        def unwrap(v):
            """A handle written as {"handle": 3} becomes the object."""
            if isinstance(v, dict) and set(v) == {"handle"}:
                obj = PY_OBJECTS.get(int(v["handle"]))
                if obj is None:
                    raise FailSignal("that handle is closed or unknown")
                return obj
            return v

        def keep(obj) -> "HandleValue":
            PY_NEXT[0] += 1
            PY_OBJECTS[PY_NEXT[0]] = obj
            return HandleValue(PY_NEXT[0], type(obj).__name__)

        def answer(out):
            if isinstance(out, (bytes, bytearray)):
                out = out.decode("utf-8", errors="replace")
            try:
                return _json.dumps(out, ensure_ascii=False)
            except TypeError:                  # not JSON: keep it alive
                return _json.dumps({"handle": keep(out).id})

        if name == "py_close":
            h = args[0]
            if isinstance(h, HandleValue):
                obj = PY_OBJECTS.pop(h.id, None)
                for closer in ("close", "shutdown", "__exit__"):
                    fn_ = getattr(obj, closer, None)
                    if fn_ is not None:
                        try:
                            fn_() if closer != "__exit__" else fn_(
                                None, None, None)
                        except Exception:
                            pass
                        break
            return None

        if name == "py_new":
            target = resolve(args[0], args[1])
            pos, kw = split_args(args[2])
            try:
                built = target(*pos, **kw)
            except Exception as e:
                raise FailSignal(f"{args[0]}.{args[1]} failed: {e}")
            ffi_reach(built, name, line, "the object it built")
            return keep(built)

        h = args[0]
        if not isinstance(h, HandleValue):
            raise FailSignal("this is not a handle")
        obj = PY_OBJECTS.get(h.id)
        if obj is None:
            raise FailSignal("that handle is closed")
        # a method or field reached through a handle is checked the same
        # way as one reached through a module: a handle to a granted
        # module's object must not be a door into an ungranted one
        if name == "py_field":
            got = getattr(obj, str(args[1]), None)
            if got is None:
                raise FailSignal(f"no '{args[1]}' on {h.what}")
            ffi_reach(got, name, line, f"field '{args[1]}' of {h.what}")
            return answer(got)
        method = getattr(obj, str(args[1]), None)
        if method is None:
            raise FailSignal(f"{h.what} has no '{args[1]}'")
        ffi_reach(method, name, line, f"method '{args[1]}' of {h.what}")
        pos, kw = split_args(args[2])
        try:
            produced = method(*pos, **kw)
        except Exception as e:
            raise FailSignal(f"{h.what}.{args[1]} failed: {e}")
        ffi_reach(produced, name, line,
                  f"the object '{args[1]}' returned")
        return answer(produced)
    if name.startswith("json_") or name == "py_json":
        import json as _json

        def walk(doc_text, path_text, what):
            try:
                cur = _json.loads(str(doc_text))
            except Exception as e:
                raise FailSignal(f"this is not valid JSON: {e}")
            if str(path_text) == "":
                return cur
            for step in str(path_text).replace("[", ".").replace(
                    "]", "").split("."):
                if step == "":
                    continue
                if isinstance(cur, list):
                    try:
                        idx = int(step)
                    except ValueError:
                        raise FailSignal(
                            f"'{step}' is not a position in a list "
                            f"(while looking for '{path_text}')")
                    if not -len(cur) <= idx < len(cur):
                        raise FailSignal(
                            f"position {idx} is outside this list of "
                            f"{len(cur)} (while looking for "
                            f"'{path_text}')")
                    cur = cur[idx]
                elif isinstance(cur, dict):
                    if step not in cur:
                        raise FailSignal(
                            f"there is no '{step}' here (while looking "
                            f"for '{path_text}')")
                    cur = cur[step]
                else:
                    raise FailSignal(
                        f"cannot look inside {type(cur).__name__} "
                        f"(while looking for '{path_text}')")
            return cur

        if name == "json_of":
            def plain(v):
                if isinstance(v, dict):
                    return {str(k): plain(x) for k, x in v.items()}
                if isinstance(v, list):
                    return [plain(x) for x in v]
                if isinstance(v, RecordValue):
                    return {f: plain(x) for f, x in v.fields.items()}
                if v.__class__ is MoneyValue:     # exact: never a JSON
                    return {"currency": v.currency,   # number with a point
                            "units": v.units}
                return v
            return _json.dumps(plain(args[0]), ensure_ascii=False)

        if name == "json_has":
            try:
                walk(args[0], args[1], "has")
                return True
            except FailSignal:
                return False

        if name == "json_len":
            got = walk(args[0], args[1], "len")
            if isinstance(got, (list, dict, str)):
                return len(got)
            raise FailSignal("this value has no length")

        if name in ("json_get", "json_int", "json_float"):
            got = walk(args[0], args[1], name)
            if name == "json_get":
                if isinstance(got, bool):
                    return "true" if got else "false"
                if isinstance(got, (dict, list)):
                    return _json.dumps(got, ensure_ascii=False)
                return "" if got is None else str(got)
            try:
                return int(got) if name == "json_int" else float(got)
            except (TypeError, ValueError):
                raise FailSignal(
                    f"'{args[1]}' is not a "
                    f"{'whole number' if name == 'json_int' else 'decimal'}")

        # py_json: arguments and answer both travel as JSON, so numbers,
        # lists and nested data survive the trip intact
        module, func, args_json = args[0], args[1], args[2]
        try:
            call_args = _json.loads(str(args_json))
        except Exception as e:
            raise FailSignal(f"the arguments are not valid JSON: {e}")
        if not isinstance(call_args, list):
            raise FailSignal("the arguments must be a JSON list, "
                             'like [1, "two", [3]]')
        def unwrap_handle(v):
            if isinstance(v, dict) and set(v) == {"handle"}:
                obj = PY_OBJECTS.get(int(v["handle"]))
                if obj is None:
                    raise FailSignal("that handle is closed or unknown")
                return obj
            return v

        kwargs = {}
        if (call_args and isinstance(call_args[-1], dict)
                and set(call_args[-1]) != {"handle"}):
            kwargs = {str(k): unwrap_handle(v)
                      for k, v in call_args[-1].items()}
            call_args = call_args[:-1]
        call_args = [unwrap_handle(v) for v in call_args]
        target = _ffi_resolve(module, func, name, line)
        try:
            out = target(*call_args, **kwargs)
        except Exception as e:
            raise FailSignal(f"{module}.{func} failed: {e}")
        if isinstance(out, (bytes, bytearray)):
            out = out.decode("utf-8", errors="replace")
        try:
            return _json.dumps(out, ensure_ascii=False)
        except TypeError:                     # not JSON: keep it alive
            ffi_reach(out, name, line, "the object it returned")
            PY_NEXT[0] += 1
            PY_OBJECTS[PY_NEXT[0]] = out
            return _json.dumps({"handle": PY_NEXT[0]})
    if name in ("py", "py_int", "py_float"):
        module, func, call_args = args[0], args[1], args[2]
        target = _ffi_resolve(module, func, name, line)
        def as_number_if_it_is(text):
            """'16' -> 16 and '2.5' -> 2.5, so numeric functions work.

            The arguments arrive as Text (that is the declared type),
            but math.sqrt("16") is a TypeError in Python. A string that
            reads as a number is passed as one; anything else stays
            text. Functions genuinely wanting the text "16" still get
            it via the all-strings retry below.
            """
            s = str(text)
            try:
                return int(s)
            except ValueError:
                pass
            try:
                return float(s)
            except ValueError:
                return s

        attempts = ([as_number_if_it_is(a) for a in call_args],
                    [str(a) for a in call_args],
                    [str(a).encode("utf-8") for a in call_args])
        out, last_err = None, None
        for formed in attempts:
            try:
                out = target(*formed)
                last_err = None
                break
            except TypeError as e:
                last_err = e
                continue                 # the next shape may fit
            except Exception as e:
                raise FailSignal(f"{module}.{func} failed: {e}")
        if last_err is not None:
            raise FailSignal(f"{module}.{func} failed: {last_err}")
        if isinstance(out, (bytes, bytearray)):
            out = out.decode("utf-8", errors="replace")
        try:
            if name == "py_int":
                return int(out)
            if name == "py_float":
                return float(out)
            return str(out)
        except (TypeError, ValueError):
            raise FailSignal(
                f"{module}.{func} gave back something that is not a "
                f"{'whole number' if name == 'py_int' else 'decimal' if name == 'py_float' else 'text'}")
    if name == "code_at":
        t, i = args
        if i < 0 or i >= len(t):
            raise VelarisError("E602",
                f"position {i} is outside the text (it has {len(t)} "
                f"character(s))", line,
                fixes=["positions go from 0 to length - 1",
                       "check with length(...) before using code_at"])
        return ord(t[i])
    if name == "get_or":
        m, k, d = args
        return m.get(k, d)
    if name == "get" and isinstance(args[0], dict):
        m, k = args
        if k not in m:
            key_txt = f"'{k}'" if isinstance(k, str) else to_text(k)
            raise FailSignal(f"map has no key {key_txt}")
        return m[k]
    if name == "get":
        xs, i = args
        if i < 0 or i >= len(xs):
            raise VelarisError("E602",
                f"position {i} is outside the list (it has {len(xs)} item(s))",
                line, fixes=["positions go from 0 to length - 1",
                             "check with length(...) before using get"])
        return xs[i]
    if name in ("read_file", "read_file_secret"):
        real = allow_path("read", str(args[0]), name, line)
        count_op("fs", name, line)
        try:
            size = os.path.getsize(real)
        except OSError:
            size = None
        if size is not None and size > MAX_READ_BYTES:
            raise VelarisError("E316",
                f"'{args[0]}' is {size} bytes, over the read ceiling of "
                f"{MAX_READ_BYTES} bytes - a file is read whole, into "
                f"memory, so a large one is capped", line,
                fixes=[f"raise the ceiling: --max-read "
                       f"{max(1, size // (1024 * 1024) + 1)} (megabytes)",
                       "or read less, or read it in another program"])
        try:
            return open(real, encoding="utf-8").read()
        except OSError:
            raise FailSignal(f"cannot read file '{args[0]}'")
    if name == "declassify":
        # the effect was spent before this ran; a Secret is a compile-time
        # distinction, so at this point the value is simply itself
        return args[0]
    if name == "write_file":
        real = allow_path("write", str(args[0]), name, line)
        count_op("fs", name, line)
        try:
            with open(real, "w", encoding="utf-8") as fh:
                fh.write(to_text(args[1]))
            return None
        except OSError as e:
            raise VelarisError("E608",
                f"could not write '{args[0]}': {e.strerror or e}", line,
                fixes=["check the folder exists and is writable",
                       "or write somewhere else"])

    if name == "request":
        import json as _json
        import urllib.request
        import urllib.error
        method, url, body, headers_json = (str(a) for a in args)
        method = method.upper() or "GET"
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        try:
            headers = _json.loads(headers_json) if headers_json.strip() \
                else {}
        except Exception as e:
            raise FailSignal(f"the headers are not valid JSON: {e}")
        if not isinstance(headers, dict):
            raise FailSignal('the headers must be a JSON object, like '
                             '{"Accept": "application/json"}')
        headers = {str(k): str(v) for k, v in headers.items()}
        headers.setdefault("User-Agent", f"velaris/{VERSION}")
        data = body.encode("utf-8") if body else None
        allow_host(url, name, line)
        count_op("net", name, line)
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            with guarded_opener().open(req, timeout=20) as resp:
                answer = {
                    "status": int(resp.status),
                    "body": resp.read(1 << 20).decode("utf-8",
                                                      errors="replace"),
                    "headers": {k: v for k, v in resp.headers.items()}}
        except urllib.error.HTTPError as e:      # a real answer
            answer = {
                "status": int(e.code),
                "body": e.read(1 << 20).decode("utf-8", errors="replace"),
                "headers": {k: v for k, v in (e.headers or {}).items()}}
        except _RedirectRefused as e:     # sent somewhere it may not go
            raise FailSignal(f"'{url}' redirected to '{e.target}', which "
                             f"this run does not allow: {e.why}")
        except Exception as e:            # say what happened, not how
            reason = "the address did not resolve"
            text = str(e).lower()
            if "timed out" in text or "timeout" in text:
                reason = "it did not answer in time"
            elif "refused" in text:
                reason = "the connection was refused"
            elif "certificate" in text or "ssl" in text:
                reason = "the certificate was not accepted"
            elif "unreachable" in text or "network" in text:
                reason = "the network is unreachable"
            raise FailSignal(f"cannot reach '{url}': {reason}")
        return _json.dumps(answer, ensure_ascii=False)
    if name in ("fetch", "post", "fetch_status"):
        import urllib.request
        import urllib.error
        url = str(args[0])
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        headers = {"User-Agent": f"velaris/{VERSION}"}
        data = None
        if name == "post":
            body = str(args[1])
            data = body.encode("utf-8")
            headers["Content-Type"] = (
                "application/json" if body.lstrip()[:1] in "{["
                else "text/plain; charset=utf-8")
        allow_host(url, name, line)
        count_op("net", name, line)
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with guarded_opener().open(req, timeout=10) as resp:
                if name == "fetch_status":
                    return int(resp.status)
                return resp.read(1 << 20).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:      # a real answer, not silence
            if name == "fetch_status":
                return int(e.code)
            raise FailSignal(f"'{url}' answered with status {e.code}")
        except _RedirectRefused as e:     # sent somewhere it may not go
            raise FailSignal(f"'{url}' redirected to '{e.target}', which "
                             f"this run does not allow: {e.why}")
        except Exception:
            raise FailSignal(f"cannot reach '{url}'")
    if name == "args":
        return list(PROGRAM_ARGS)
    if name == "log":
        print(to_text(args[0]), file=sys.stderr)
        return None
    if name == "env":
        return os.environ.get(str(args[0]), str(args[1]))
    if name == "exit_with":
        code = int(args[0])
        if not 0 <= code <= 255:
            raise VelarisError("E408",
                f"an exit code must be between 0 and 255, not {code}",
                line, fixes=["0 means success; anything else means "
                             "something went wrong"])
        raise SystemExit(code)
    if name == "read_line":
        got = sys.stdin.readline()
        return got.rstrip("\n")
    if name == "format":
        template = str(args[0])
        pieces = template.split("{}")
        holes = len(pieces) - 1
        given = len(args) - 1
        if holes != given:
            raise VelarisError("E406",
                f"format has {holes} placeholder(s) but got {given} "
                f"value(s)", line,
                fixes=[f"pass exactly {holes} value(s) after the text",
                       "each {} in the text takes one value"])
        out = pieces[0]
        for piece, val in zip(pieces[1:], args[1:]):
            out += to_text(val) + piece
        return out
    if name == "now":
        return int(_time.time())
    if name == "random":
        n = args[0]
        if n <= 0:
            raise VelarisError("E405", "random(n) needs n greater than 0", line,
                              fixes=["pass a positive number, e.g. random(6)"])
        return _rand.randrange(n)


def build_runtime(funcs: list[Function], native: dict | None = None):
    native = native or {}
    table = {f.name: f for f in funcs}

    # builtins from 4.3 on give way to the program's own function of the
    # same name; '@name' is a library's call bound to the builtin
    hidden = NEW_BUILTINS & set(table)

    def call(name: str, args: list, line: int):
        if name in ("all_of", "any_of"):
            xs, p = args
            hits = (call_function(p, [v], line) for v in xs)
            return all(hits) if name == "all_of" else any(hits)
        if name in BUILTINS and name not in hidden:
            return run_builtin(name, args, line)
        if name[0] == "@":
            return run_builtin(name[1:], args, line)
        if name in native:                 # machine code, C-like speed
            if TRACE["on"]:                # still visible when tracing
                fnn = table.get(name)
                trace_enter(name + " (native)",
                            fnn.params if fnn else [], args,
                            getattr(fnn, "secret_params", frozenset()))
                out = native[name](*args)
                trace_leave(name + " (native)", out,
                            secret=getattr(fnn, "secret_result", False))
                return out
            return native[name](*args)
        fn = table.get(name)
        if fn is None:
            raise unknown_function(name, line, table)
        return call_function(fn, args, line)

    depth = [0]
    DEPTH_LIMIT = 2000        # deep enough for real recursion, shallow
                              # enough to report before Python's own
                              # stack gives out with a traceback
    # each Velaris frame costs several Python frames, so lift Python's
    # ceiling high enough that OUR limit is the one that fires
    if sys.getrecursionlimit() < DEPTH_LIMIT * 12:
        try:
            sys.setrecursionlimit(DEPTH_LIMIT * 12)
        except Exception:
            pass

    def call_function(fn, args: list, line: int):
        caught = None
        if isinstance(fn, Bound):
            caught, fn = fn.caught, fn.fn
        name = fn.name
        if depth[0] >= DEPTH_LIMIT:
            raise VelarisError("E609",
                f"'{name}' called itself {DEPTH_LIMIT} deep - this looks "
                f"like recursion that never stops", line,
                fixes=["make sure the recursive case moves toward the "
                       "base case",
                       "or rewrite it as a loop"])
        if len(args) != len(fn.params):
            raise VelarisError("E401",
                f"'{name}' expects {len(fn.params)} argument(s) but got {len(args)}",
                line, fixes=[f"pass exactly {len(fn.params)} argument(s)"])
        env = {p[0]: a for p, a in zip(fn.params, args)}
        if caught:
            for cn, cv in caught.items():
                env.setdefault(cn, cv)     # values carried in, read once
                                           # when the value was made
        # the snapshot exists so promises can see entry values; a
        # function with no promises was copying its whole scope on
        # every single call for nothing
        entry = dict(env) if (fn.requires or fn.ensures) else env

        # a promise may talk about a secret - `requires length(key) > 0`
        # is exactly the kind of thing to promise - so the message a
        # broken one prints redacts the values whose type is secret (6.0)
        hush = getattr(fn, "secret_params", frozenset())
        hush_result = getattr(fn, "secret_result", False)

        def vals(expr, extra=None):
            scope = dict(entry)
            if extra is not None:
                scope["result"] = extra[0]
            names = sorted(n for n in expr_vars(expr) if n in scope)
            return ", ".join(
                f"{n} = " + (REDACTED if (n in hush or
                                          (n == "result" and hush_result))
                             else f"{scope[n]}")
                for n in names)

        for expr, cline in fn.requires:
            if not eval_(expr, dict(entry)):
                raise VelarisError("E600",
                    f"broken promise: {nice_name(name)} requires "
                    f"{expr_str(expr)}  ({vals(expr)})", cline,
                    fixes=["check the value before calling this function",
                           "or loosen the promise if it is too strict"])

        retval = None
        trace_enter(name, fn.params, args, hush)
        depth[0] += 1
        try:
            for stmt in fn.body:
                run(stmt, env)
        except ReturnSignal as r:
            retval = r.value
        except FailSignal as f:
            trace_leave(name, None, failed=str(f.reason))
            raise
        except VelarisError as e:
            trace_leave(name, None, failed=f"[{e.code}] {e.message}")
            raise blame(fn, e)
        finally:
            depth[0] -= 1
        trace_leave(name, retval, secret=hush_result)

        for expr, cline in fn.ensures:
            check_env = dict(entry)
            check_env["result"] = retval
            if not eval_(expr, check_env):
                raise VelarisError("E601",
                    f"broken promise: {nice_name(name)} ensures "
                    f"{expr_str(expr)}  ({vals(expr, (retval,))})", cline,
                    fixes=["the code does not keep this promise - fix the code",
                           "or fix the promise if it is wrong"])
        return retval

    def run(node, env):
        cls = node.__class__
        if cls is Assign:               # the body of every loop
            env[node.name] = eval_(node.value, env)
            return
        if cls is Let:
            env[node.name] = eval_(node.value, env)
            return
        if cls is Let:
            env[node.name] = eval_(node.value, env)
        elif cls is Return:
            raise ReturnSignal(None if node.value is None else eval_(node.value, env))
        elif cls is ExprStmt:
            eval_(node.expr, env)
        elif cls is FailStmt:
            raise FailSignal(eval_(node.value, env))
        elif cls is Check:
            try:
                val = eval_(node.subject, env)
            except FailSignal as f:
                env[node.fail_name] = f.reason
                for s in node.fail_body:
                    run(s, env)
            else:
                if node.ok_name is not None:
                    env[node.ok_name] = val
                for s in node.ok_body:
                    run(s, env)
        elif cls is If:
            branch = node.then if eval_(node.cond, env) else node.other
            for s in branch:
                run(s, env)
        elif cls is While:
            def check_invariants():
                for inv_expr, iline in node.invariants:
                    if not eval_(inv_expr, env):
                        names = sorted(n for n in expr_vars(inv_expr)
                                       if n in env)
                        vals = ", ".join(f"{n} = {to_text(env[n])}"
                                         for n in names)
                        raise VelarisError("E704",
                            f"loop broke its promise: invariant "
                            f"{expr_str(inv_expr)}  ({vals})", iline,
                            fixes=["fix the loop body so the promise holds "
                                   "on every step",
                                   "or fix the invariant if it is wrong"])
            check_invariants()
            while eval_(node.cond, env):
                for s in node.body:
                    run(s, env)
                check_invariants()
        elif cls is Assign:
            env[node.name] = eval_(node.value, env)

    _hot = (Num, FloatNum, Str, Bool)

    class Bound:
        """A function value carrying the values it was made with."""
        __slots__ = ("fn", "caught")

        def __init__(self, fn, caught):
            self.fn = fn
            self.caught = caught

    def eval_(node, env):
        cls = node.__class__
        if cls is Closure:
            fn = table[node.name]
            caught = {n: env[n] for n in node.free if n in env}
            return Bound(fn, caught) if caught else fn
        if cls is Var:                  # the commonest node by far
            name = node.name
            if name in env:
                return env[name]
            if name in table:
                return table[name]
            raise VelarisError("E402", f"unknown variable '{name}'",
                               node.line,
                               fixes=[f"declare it first: let {name} = ..."])
        if cls in _hot:                 # literals: the value is the node
            return node.value
        if cls is Num:  return node.value
        if cls is FloatNum: return node.value
        if cls is Neg:
            v = -eval_(node.value, env)
            if v.__class__ is MoneyValue:        # -(the smallest amount)
                return checked_int(v, "-", node.line)   # does not fit
            return v
        if cls is TryExpr:
            return eval_(node.value, env)   # a failure keeps rising
        if cls is Str:  return node.value
        if cls is Bool: return node.value
        if cls is Var:
            if node.name in env:
                return env[node.name]
            if node.name in table:
                return table[node.name]        # a function, as a value
            raise VelarisError("E402", f"unknown variable '{node.name}'", node.line,
                              fixes=[f"declare it first: let {node.name} = ..."])
        if cls is Call:
            if node.name in env and isinstance(env[node.name],
                                               (Function, Bound)):
                return call_function(env[node.name],
                                     [eval_(a, env) for a in node.args],
                                     node.line)
            return call(node.name, [eval_(a, env) for a in node.args], node.line)
        if cls is Not:
            return not eval_(node.value, env)
        if cls is RecordLit:
            return RecordValue(node.name,
                               {f: eval_(v, env) for f, v in node.fields})
        if cls is FieldGet:
            return eval_(node.obj, env).fields[node.field]
        if cls is ListLit:
            return [eval_(i, env) for i in node.items]
        if cls is MapLit:
            return {eval_(k, env): eval_(v, env) for k, v in node.entries}
        if cls is BinOp:
            if node.op == "and":
                return eval_(node.left, env) and eval_(node.right, env)
            if node.op == "or":
                return eval_(node.left, env) or eval_(node.right, env)
            l, r = eval_(node.left, env), eval_(node.right, env)
            if node.op == "+":
                if isinstance(l, str) or isinstance(r, str):
                    return to_text(l) + to_text(r)
                return checked_int(l + r, "+", node.line)
            if node.op == "-":
                return checked_int(l - r, "-", node.line)
            if node.op == "*":
                return checked_int(l * r, "*", node.line)
            if node.op == "/":
                if r == 0:
                    raise VelarisError("E403", "division by zero", node.line,
                                      fixes=["check the divisor before dividing"])
                if isinstance(l, float):
                    return l / r
                return l // r
            if node.op == "%":
                if r == 0:
                    raise VelarisError("E403", "remainder by zero", node.line,
                                      fixes=["check the divisor before using %"])
                return l % r
            if node.op == "==":
                return l == r
            if node.op == "!=":
                return l != r
            if node.op == "<":
                return l < r
            if node.op == ">":
                return l > r
            if node.op == "<=":
                return l <= r
            return l >= r

    return {"table": table, "call": call, "run": run, "eval": eval_}


def _needs_big_stack() -> bool:
    """CPython before 3.11 uses much more C stack per Python frame, so with
    the raised recursion limit build_runtime sets, a deeply recursive Velaris
    program can overflow the C stack (a segfault on Windows) before the
    interpreter's DEPTH_LIMIT guard fires E609. 3.11+ handles the same depth
    in place. Running on a worker thread perturbs a memory cap's accounting,
    so we only take that path where the guard would otherwise not be
    reached. 7.1.2."""
    return sys.version_info < (3, 11)


def _run_on_big_stack(fn):
    """On CPython < 3.11, run fn on a thread with a larger C stack and
    re-raise whatever it raised (a VelarisError, a FailSignal, or the
    SystemExit exit_with throws), so a runaway recursion reaches E609 rather
    than overflowing the C stack. Elsewhere - and if the platform will not
    size a thread stack - run in place, which leaves the memory-cap path
    untouched. 7.1.2."""
    if not _needs_big_stack():
        return fn()
    import threading
    box: dict = {}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as e:          # VelarisError/FailSignal/SystemExit
            box["error"] = e

    # Windows CPython rejects very large thread stacks (256 MiB raises on
    # 3.10), so try descending sizes and take the first the platform accepts;
    # 64 MiB holds the ~24000 Python frames DEPTH_LIMIT allows, verified on
    # 3.10.
    prev = None
    for size in (64 * 1024 * 1024, 32 * 1024 * 1024):
        try:
            prev = threading.stack_size(size)
            break
        except (ValueError, RuntimeError, OverflowError):
            continue
    else:
        return fn()                         # cannot size a stack: run here
    started = False
    try:
        t = threading.Thread(target=worker)
        try:
            t.start()
            started = True
        except RuntimeError:
            # "can't start new thread": a big stack can exceed the address
            # space a memory cap (RLIMIT_AS) leaves, especially with llvmlite
            # loaded. Run in place - the big stack is a best-effort guard,
            # never a requirement.
            started = False
        if started:
            t.join()
    finally:
        try:
            threading.stack_size(prev or 0)
        except (ValueError, RuntimeError, OverflowError):
            pass
    if not started:
        return fn()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def interpret(funcs: list[Function], native: dict | None = None) -> None:
    rt = build_runtime(funcs, native)
    if "main" not in rt["table"]:
        raise VelarisError("E400", "no 'main' function found", 1,
                          fixes=["add: fn main() uses io { ... }"])
    _run_on_big_stack(
        lambda: rt["call"]("main", [], rt["table"]["main"].line))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def lsp_analyze(path: str, text: str, deep: bool) -> list:
    """Run the checkers on an editor buffer; return VelarisErrors."""
    errors: list = []
    try:
        funcs, records = load_program(path, entry_source=text)
    except VelarisError as e:
        return [e]
    check_effects(funcs, errors)
    check_types(funcs, records, errors)
    if deep and not errors:
        check_proofs(funcs, records, errors)
    return errors


def contract_coverage(functions: list, records: list) -> list:
    """Names of the functions that take or return a List, a Map or a
    record and carry no requires or ensures: they transform data and
    promise nothing about it. A coverage note, not a defect - the audit
    lists them so a reader knows where no promise was even attempted.
    """
    def is_data(t: str) -> bool:
        return (t.startswith("List of") or t.startswith("Map of")
                or t in records)
    out = []
    for f in functions:
        if f["requires"] or f["ensures"]:
            continue
        types = [p["type"] for p in f["params"]] + [f["returns"] or ""]
        if any(is_data(t) for t in types):
            out.append(f["name"])
    return out


def inspect_source(path: str, source: str | None = None, require_main: bool = False) -> dict:
    """Everything a reader wants to know about a program, as data.

    Used by 'velaris explain' and the browser inspector: for each
    function, what it may do (effects), what it promises, whether the
    promises are proven or left to runtime, and every error in place.
    """
    running = require_main
    report: dict = {"file": path, "functions": [], "errors": [],
                    "proofs": bool(HAVE_Z3), "version": VERSION}
    try:
        funcs, records = load_program(path, source)
    except VelarisError as e:
        report["errors"].append(json.loads(e.machine(path)))
        return report
    errors: list = []
    try:
        check_main(funcs, errors, running=running)
        check_effects(funcs, errors)
        if not errors:
            check_types(funcs, records, errors)
    except VelarisError as e:          # a raise instead of an append is
        errors.append(e)               # still one problem, not a crash
    proved: set = set()
    abandoned: list = []
    if not errors:
        try:
            check_proofs(funcs, records, errors, proved,
                         use_cache="--no-cache" not in sys.argv,
                         timeouts_out=abandoned,
                         source_path=path, source_text=source)
        except VelarisError as e:
            errors.append(e)
    report["proof_timeouts"] = abandoned
    out_of_time = {t["name"] for t in abandoned}
    seen_e = set()
    for e in errors:                # one problem, one message, everywhere
        key = (e.code, e.file or path, e.line, e.message)
        if key in seen_e:
            continue
        seen_e.add(key)
        report["errors"].append(json.loads(e.machine(path)))
    bad_lines = {e.line for e in errors}
    # which loops provably end - syntactic, so it is the same answer
    # with and without the prover
    table_all = {f.name: f for f in funcs}
    loops_by = {f.name: loop_termination(f, table_all) for f in funcs}
    report["records"] = [r.name for r in records]
    report["inline_loops"] = []          # loops inside lifted lambdas
    for f in funcs:
        if f.name.startswith("fn#"):
            for lp in loops_by[f.name]:
                report["inline_loops"].append(
                    dict(lp, function=f.name, file=f.src_file or path))
            continue                     # lifted lambda: shown in place
        report["functions"].append({
            "loops": loops_by[f.name],
            "loops_unshown": sum(1 for lp in loops_by[f.name]
                                 if lp["verdict"] == "unshown"),
            "name": f.name,
            "line": f.line,
            "params": [{"name": n, "type": t} for n, t in f.params],
            "returns": f.return_type or "nothing",
            "effects": sorted(f.effects) or [],
            "can_fail": bool(f.can_fail),
            "generic": list(f.type_vars),
            "requires": [expr_str(e) for e, _ in f.requires],
            "ensures": [expr_str(e) for e, _ in f.ensures],
            "status": ("error" if f.line in bad_lines else
                       "proven" if f.name in proved and HAVE_Z3 else
                       "checked at runtime" if (f.requires or f.ensures)
                       else "no promises"),
            # the promise is checked while running either way; this says
            # the prover ran out of time rather than settling anything
            "proof_timeout": f.name in out_of_time,
            "file": f.src_file or path,
        })
    return report


def editor_answer(method: str, params: dict, text: str, uri: str):
    """Hover, go-to-definition, proof lenses and an outline."""
    import urllib.parse
    path = urllib.parse.unquote(uri.replace("file://", ""))
    if os.name == "nt" and path.startswith("/"):
        path = path[1:]
    try:
        funcs, records = load_program(path, text)
    except VelarisError:
        return None if "codeLens" not in method else []

    proven: set = set()
    if "codeLens" in method:
        errors: list = []
        check_effects(funcs, errors)
        check_types(funcs, records, errors)
        if not errors:
            try:
                check_proofs(funcs, records, errors, proven, use_cache=True,
                             source_path=path, source_text=text)
            except Exception:
                pass

    mine = [f for f in funcs
            if not f.src_file or os.path.abspath(f.src_file)
            == os.path.abspath(path)]

    def signature(f) -> str:
        ps = ", ".join(f"{n}: {t}" for n, t in f.params)
        out = f"fn {f.name}({ps})"
        if f.return_type and f.return_type != "Unit":
            out += f" -> {f.return_type}"
        if f.type_vars:
            out += " for any " + ", ".join(f.type_vars)
        if f.can_fail:
            out += " or fail"
        if f.effects:
            out += " uses " + ", ".join(sorted(f.effects))
        return out

    if method == "textDocument/codeLens":
        lenses = []
        for f in mine:
            if f.name.startswith("fn#"):
                continue
            if f.requires or f.ensures:
                title = ("promises proven before running"
                         if f.name in proven
                         else "promises checked while running")
            elif f.effects:
                title = "may perform: " + ", ".join(sorted(f.effects))
            else:
                title = "pure"
            if f.can_fail:
                title += " - can fail"
            lenses.append({
                "range": {"start": {"line": max(f.line - 1, 0),
                                    "character": 0},
                          "end": {"line": max(f.line - 1, 0),
                                  "character": 1}},
                "command": {"title": title, "command": ""}})
        return lenses

    if method == "textDocument/rename":
        line_no = params["position"]["line"]
        col = params["position"]["character"]
        new_name = params.get("newName", "")
        lines = text.splitlines()
        if line_no >= len(lines) or not new_name:
            return None
        row = lines[line_no]
        start, end = col, col
        while start > 0 and (row[start - 1].isalnum()
                             or row[start - 1] == "_"):
            start -= 1
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        old_name = row[start:end]
        if not old_name:
            return None
        here = {f.name for f in funcs
                if not f.src_file
                or os.path.abspath(f.src_file) == os.path.abspath(path)}
        if old_name not in here:
            return None            # only names this file owns
        import re as _re
        pattern = _re.compile(r"\b" + _re.escape(old_name) + r"\b")
        edits = []
        for i, row_text in enumerate(lines):
            code = row_text.split("//")[0]        # leave comments alone
            for m in pattern.finditer(code):
                edits.append({
                    "range": {"start": {"line": i, "character": m.start()},
                              "end": {"line": i, "character": m.end()}},
                    "newText": new_name})
        if not edits:
            return None
        return {"changes": {uri: edits}}

    if method == "textDocument/completion":
        items = []
        for f in funcs:
            if f.name.startswith("fn#"):
                continue
            items.append({"label": f.name, "kind": 3,
                          "detail": signature(f),
                          "documentation": " ".join(
                              [f"requires {expr_str(e)}"
                               for e, _ in f.requires]
                              + [f"ensures {expr_str(e)}"
                                 for e, _ in f.ensures]) or None})
        for name, info in BUILTINS.items():
            eff = ", ".join(sorted(info["effects"])) or "pure"
            fail = " (can fail)" if name in FALLIBLE_BUILTINS else ""
            items.append({"label": name, "kind": 3,
                          "detail": f"builtin -> {info['ret']}{fail}",
                          "documentation": f"effects: {eff}"})
        for word in ("fn", "let", "return", "if", "else", "while", "for",
                     "uses", "requires", "ensures", "invariant", "record",
                     "import", "fail", "check", "try", "or fail",
                     "for any T"):
            items.append({"label": word, "kind": 14})
        return {"isIncomplete": False, "items": items}

    if method == "textDocument/documentSymbol":
        return [{"name": f.name, "kind": 12,
                 "range": {"start": {"line": max(f.line - 1, 0),
                                     "character": 0},
                           "end": {"line": max(f.line - 1, 0),
                                   "character": 80}},
                 "selectionRange": {
                     "start": {"line": max(f.line - 1, 0), "character": 0},
                     "end": {"line": max(f.line - 1, 0), "character": 80}},
                 "detail": signature(f)}
                for f in mine if not f.name.startswith("fn#")]

    # hover and definition both need the word under the cursor
    line_no = params["position"]["line"]
    col = params["position"]["character"]
    lines = text.splitlines()
    if line_no >= len(lines):
        return None
    row = lines[line_no]
    start = col
    while start > 0 and (row[start - 1].isalnum()
                         or row[start - 1] in "_."):
        start -= 1
    end = col
    while end < len(row) and (row[end].isalnum() or row[end] in "_."):
        end += 1
    word = row[start:end]
    if not word:
        return None

    table = {f.name: f for f in funcs}
    found = table.get(word)

    if method == "textDocument/definition":
        if found is None or found.name.startswith("fn#"):
            return None
        target = found.src_file or path
        return {"uri": "file://" + os.path.abspath(target).replace(
                    "\\", "/"),
                "range": {"start": {"line": max(found.line - 1, 0),
                                    "character": 0},
                          "end": {"line": max(found.line - 1, 0),
                                  "character": 1}}}

    if found is not None:
        parts = [signature(found)]
        for e, _ in found.requires:
            parts.append(f"    requires {expr_str(e)}")
        for e, _ in found.ensures:
            parts.append(f"    ensures {expr_str(e)}")
        body = ["```velaris", "\n".join(parts), "```"]
        if found.src_file and os.path.abspath(found.src_file) != \
                os.path.abspath(path):
            body.append(f"from `{os.path.basename(found.src_file)}`")
        return {"contents": {"kind": "markdown",
                             "value": "\n".join(body)}}

    if word in BUILTINS:
        info = BUILTINS[word]
        eff = ", ".join(sorted(info["effects"])) or "pure"
        fail = " (can fail)" if word in FALLIBLE_BUILTINS else ""
        return {"contents": {"kind": "markdown", "value":
                f"**{word}**{fail}\n\n"
                f"takes: {', '.join(info['types']) or 'nothing'}  \n"
                f"gives: {info['ret']}  \n"
                f"effects: {eff}"}}
    return None


def lsp_serve() -> int:
    import urllib.parse

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    docs: dict[str, str] = {}          # uri -> latest text
    published: set = set()             # uris we have diagnostics on

    def read_message():
        length = None
        while True:
            line = stdin.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            key, _, val = line.partition(b":")
            if key.lower() == b"content-length":
                length = int(val)
        if length is None:
            return None
        return json.loads(stdin.read(length))

    def send(payload: dict):
        body = json.dumps(payload).encode("utf-8")
        stdout.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
        stdout.write(body)
        stdout.flush()

    def uri_to_path(uri: str) -> str:
        p = urllib.parse.unquote(uri[len("file://"):])
        if len(p) > 2 and p[0] == "/" and p[2] == ":":
            p = p[1:]                   # windows: /C:/... -> C:/...
        return p

    def path_to_uri(p: str) -> str:
        p = os.path.abspath(p).replace("\\", "/")
        if not p.startswith("/"):
            p = "/" + p
        return "file://" + urllib.parse.quote(p)

    def diag_of(e: VelarisError) -> dict:
        msg = f"[{e.code}] {e.message}"
        if e.fixes:
            msg += "".join(f"\nfix: {f}" for f in e.fixes)
        line = max(e.line - 1, 0)
        return {"range": {"start": {"line": line, "character": 0},
                          "end": {"line": line, "character": 500}},
                "severity": 1, "source": "velaris", "message": msg}

    def publish(uri: str, deep: bool):
        path = uri_to_path(uri)
        errors = lsp_analyze(path, docs.get(uri, ""), deep)
        by_file: dict[str, list] = {uri: []}
        for e in errors:
            target = uri if e.file in (None, path) else path_to_uri(e.file)
            by_file.setdefault(target, []).append(diag_of(e))
        for target, ds in by_file.items():
            send({"jsonrpc": "2.0",
                  "method": "textDocument/publishDiagnostics",
                  "params": {"uri": target, "diagnostics": ds}})
            published.add(target)
        for old in list(published):
            if old not in by_file:
                send({"jsonrpc": "2.0",
                      "method": "textDocument/publishDiagnostics",
                      "params": {"uri": old, "diagnostics": []}})
                published.discard(old)

    while True:
        msg = read_message()
        if msg is None:
            return 0
        method = msg.get("method", "")
        params = msg.get("params", {})
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True, "change": 1,
                        "save": {"includeText": True}},
                    "hoverProvider": True,
                    "renameProvider": {"prepareProvider": False},
                    "completionProvider": {
                        "triggerCharacters": [".", " "]},
                    "definitionProvider": True,
                    "codeLensProvider": {"resolveProvider": False},
                    "documentSymbolProvider": True},
                "serverInfo": {"name": "velaris", "version": VERSION}}})
        elif method in ("textDocument/hover", "textDocument/definition",
                        "textDocument/codeLens", "textDocument/completion",
                        "textDocument/rename",
                        "textDocument/documentSymbol"):
            uri = params["textDocument"]["uri"]
            text = docs.get(uri, "")
            result = editor_answer(method, params, text, uri)
            send({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        elif method == "shutdown":
            send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
        elif method == "exit":
            return 0
        elif method == "textDocument/didOpen":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["textDocument"]["text"]
            publish(uri, deep=True)
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["contentChanges"][0]["text"]
            publish(uri, deep=False)
        elif method == "textDocument/didSave":
            uri = params["textDocument"]["uri"]
            if "text" in params:
                docs[uri] = params["text"]
            publish(uri, deep=True)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            docs.pop(uri, None)
            send({"jsonrpc": "2.0",
                  "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": []}})
        elif "id" in msg:               # any other request: empty result
            send({"jsonrpc": "2.0", "id": msg["id"], "result": None})


UNARY_BEFORE = {"(", "[", "{", ",", ":", "=", "==", "!=", "<", ">",
                "<=", ">=", "+", "-", "*", "/", "%"}
UNARY_KEYWORDS = {"return", "fail", "and", "or", "not", "requires",
                  "ensures", "invariant", "while", "if"}


def format_source(source: str) -> str:
    toks = lex(source, keep_trivia=True)
    lines, cur = [], []
    for t in toks:
        if t.kind == "NEWLINE":
            lines.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        lines.append(cur)

    def render(line_toks) -> str:
        out = ""
        prev = None
        unary = False
        for t in line_toks:
            if t.kind == "COMMENT":
                body = t.text[2:].strip()
                comment = "// " + body if body else "//"
                out = (out.rstrip() + "  " + comment) if out.strip() \
                    else comment
                prev = t
                continue
            if prev is None or unary:
                space = False
            elif t.text in (")", "]", ",", ".", ":"):
                space = False
            elif prev.text in ("(", "[", "."):
                space = False
            elif t.text == "(" and prev.kind == "IDENT":
                space = False
            elif (t.text == "(" and prev.kind == "KEYWORD"
                    and prev.text == "fn"):
                space = False              # lambda value: fn(x: Int)
            else:
                space = True          # includes symmetric { x } spacing
            unary = (t.text == "-" and (
                prev is None or prev.text in UNARY_BEFORE
                or prev.kind == "ARROW"
                or (prev.kind == "KEYWORD" and prev.text in UNARY_KEYWORDS)))
            out += (" " if space else "") + t.text
            prev = t
        return out

    depth = 0
    out_lines: list[str] = []
    blank = False
    for line_toks in lines:
        if not line_toks:
            if out_lines and not blank:
                out_lines.append("")
            blank = True
            continue
        blank = False
        lead = 0
        while lead < len(line_toks) and line_toks[lead].text == "}":
            lead += 1
        d = max(depth - lead, 0)
        # a contract sits between the signature and the body, where no
        # brace has opened yet - indent it under the signature it belongs
        # to rather than flattening it to the margin
        if line_toks[0].text in ("requires", "ensures", "invariant"):
            d += 1
        text = render(line_toks)
        out_lines.append("    " * d + text if text else "")
        for t in line_toks:
            if t.text == "{":
                depth += 1
            elif t.text == "}":
                depth = max(depth - 1, 0)
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    return "\n".join(out_lines) + "\n"


def fmt_main(argv: list[str]) -> int:
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print("usage: velaris fmt <file.vel> [--stdout | --check]",
              file=sys.stderr)
        return 1
    status = 0
    for path in files:
        try:
            source = open(path, encoding="utf-8").read()
            formatted = format_source(source)
        except (OSError, VelarisError) as e:
            msg = e.human(path) if isinstance(e, VelarisError) else str(e)
            print(msg, file=sys.stderr)
            status = 1
            continue
        if "--stdout" in argv:
            print(formatted, end="")
        elif "--check" in argv:
            if formatted != source:
                print(f"{path}: needs formatting")
                status = 1
            else:
                print(f"{path}: ok")
        elif formatted != source:
            open(path, "w", encoding="utf-8").write(formatted)
            print(f"formatted {path}")
        else:
            print(f"{path}: already formatted")
    return status


STARTER = """// Welcome to Velaris - the language where you can trust code you
// didn't write. Run me with:   velaris main.vel

import "std.vel"

fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    if price < 10 {
        return 0
    }
    return price - 10
}

fn main() uses io {
    print("hello from Velaris!")
    print("discount(50) = " + discount(50))
    print("sorted: " + sort([5, 3, 8, 1]))
    check to_int(ask("type a number:")) {
        ok n {
            print("double that is " + (n * 2))
        }
        fail why {
            print("that was not a number - " + why)
        }
    }
}
"""


MANIFEST = "velaris.toml"
LOCKFILE = "velaris.lock"
LOCK_SCHEMA = "velaris.lock/1"


def _manifest_read() -> list:
    """Every dependency, as (name, source, sha256)."""
    if not os.path.exists(MANIFEST):
        return []
    import re as _re
    text = open(MANIFEST, encoding="utf-8").read()
    return [(m.group(1), m.group(2), m.group(3)) for m in _re.finditer(
        r'^(\w[\w.-]*)\s*=\s*\{\s*source\s*=\s*"([^"]*)"\s*,\s*'
        r'sha256\s*=\s*"([0-9a-f]{64})"\s*\}\s*$', text, _re.M)]


def _manifest_write(deps: list) -> None:
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("# Velaris dependencies. Every library is vendored into\n"
                "# lib/ and recorded here with the exact bytes it had, so\n"
                "# 'velaris deps --verify' can tell you if anything "
                "changed.\n\n")
        f.write("[dependencies]\n")
        for name, source, digest in sorted(deps):
            f.write(f'{name} = {{ source = "{source}", '
                    f'sha256 = "{digest}" }}\n')


# ---- velaris.lock ---------------------------------------------------------
#      The manifest says what this project depends on. The lock says
#      exactly which bytes were vendored, where they came from, and
#      which Velaris put them there - so a checkout on another machine
#      can be shown to hold the same libraries, not merely libraries
#      with the same names.

def _lock_read() -> dict:
    """{name: entry}, empty when there is no lock or it cannot be read."""
    if not os.path.exists(LOCKFILE):
        return {}
    try:
        with open(LOCKFILE, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for entry in (doc.get("libraries") or []):
        if isinstance(entry, dict) and entry.get("name"):
            out[entry["name"]] = entry
    return out


def _lock_write(entries: dict) -> None:
    doc = {"lockfile": LOCK_SCHEMA,
           "libraries": [entries[name] for name in sorted(entries)]}
    with open(LOCKFILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")


def _lock_path(entry: dict) -> str:
    """Where a lock entry says its library lives, as this OS spells it."""
    where = entry.get("file") or ("lib/" + entry["name"] + ".vel")
    return os.path.join(*where.split("/"))


def _digest_of(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_libraries() -> int:
    """Are the vendored libraries exactly the ones that were locked?

    Against velaris.lock when there is one - which also knows which
    Velaris added each library - and against velaris.toml when there is
    not, so a project made before 3.1 still verifies. Returns the exit
    code: 0 when everything matches.
    """
    lock = _lock_read()
    deps = _manifest_read()
    if not lock and not deps:
        print("nothing to verify - add a library with: "
              "velaris add <url or path>")
        return 0

    if lock:
        rows = [(e["name"], e.get("source", "?"), e.get("sha256", ""),
                 _lock_path(e), e.get("added_by", "?")) for e in
                (lock[n] for n in sorted(lock))]
        against = f"{LOCKFILE} ({len(rows)} librar(ies))"
    else:
        rows = [(n, src, digest, os.path.join("lib", n + ".vel"), "?")
                for n, src, digest in sorted(deps)]
        against = (f"{MANIFEST} - there is no {LOCKFILE} yet; "
                   f"velaris add writes one")
    print(f"checking against {against}")

    bad = 0
    for name, source, digest, path, added_by in rows:
        if not os.path.exists(path):
            print(f"  MISSING  {name} - {path} is not there "
                  f"(re-add it: velaris add {source})")
            bad += 1
            continue
        now = _digest_of(path)
        if now != digest:
            print(f"  CHANGED  {name} - {path} is not the file that was "
                  f"locked")
            print(f"           locked {digest[:16]}...  now "
                  f"{now[:16]}...")
            bad += 1
        else:
            note = f"  (added by Velaris {added_by})" if added_by != "?" \
                else ""
            print(f"  ok       {name}{note}")

    if lock:
        # a manifest entry with no lock entry is a half-recorded library
        locked = set(lock)
        for name, source, _digest in sorted(deps):
            if name not in locked:
                print(f"  UNLOCKED {name} is in {MANIFEST} and not in "
                      f"{LOCKFILE} (re-add it: velaris add {source})")
                bad += 1

    named = {os.path.normcase(os.path.abspath(row[3])) for row in rows}
    if os.path.isdir("lib"):
        for found in sorted(os.listdir("lib")):
            if not found.endswith(".vel"):
                continue
            here = os.path.join("lib", found)
            if os.path.normcase(os.path.abspath(here)) not in named:
                print(f"  note     {here} is vendored and nothing records "
                      f"where it came from")

    if bad:
        print(f"\n{bad} problem(s). A library that changed under you is "
              f"worth looking at before trusting it.")
        return 1
    print(f"\nall {len(rows)} librar(ies) are exactly as locked")
    return 0


def packages(argv: list) -> int:
    import hashlib
    cmd = argv[0]
    deps = _manifest_read()
    lock = _lock_read()

    if cmd == "verify" or (cmd == "deps" and "--verify" in argv):
        return verify_libraries()

    if cmd == "deps":
        if not deps:
            print("no dependencies yet - add one with: "
                  "velaris add <url or path>")
            return 0
        print(f"{len(deps)} dependenc(ies), vendored in lib/")
        for name, source, digest in deps:
            here = os.path.join("lib", name + ".vel")
            mark = "ok " if os.path.exists(here) else "MISSING"
            added = lock.get(name, {}).get("added_by")
            print(f"  [{mark}] {name}\n      from {source}"
                  f"\n      {digest[:16]}..."
                  + (f"   added by Velaris {added}" if added else ""))
        if not lock:
            print(f"\nthere is no {LOCKFILE} yet - velaris add writes "
                  f"one, and 'velaris deps --verify' reads it")
        else:
            print(f"\n{LOCKFILE} records all of it; check it with: "
                  f"velaris deps --verify")
        return 0

    if len(argv) < 2:                     # add
        print("usage: velaris add <url or path> [as <name>] [--force]",
              file=sys.stderr)
        return 1
    force = "--force" in argv
    words = [a for a in argv[1:] if not a.startswith("--")]
    source = words[0] if words else ""
    name = None
    if len(words) >= 3 and words[1] == "as":
        name = words[2]
    if name is None:
        name = os.path.basename(source)
        if name.endswith(".vel"):
            name = name[:-4]
    if not name or "/" in name or "\\" in name:
        print(f"'{name}' is not a usable library name", file=sys.stderr)
        return 1

    if source.startswith("http://") or source.startswith("https://"):
        import urllib.request
        try:
            with urllib.request.urlopen(source, timeout=20) as resp:
                data = resp.read(4 << 20)
        except Exception as e:
            print(f"could not fetch {source}: {e}", file=sys.stderr)
            return 1
    else:
        if not os.path.exists(source):
            print(f"no such file: {source}", file=sys.stderr)
            return 1
        data = open(source, "rb").read()

    # the exact bytes, byte for byte, are what gets vendored and what
    # gets locked: the digest a lock records is then the digest of what
    # the source published, on every platform. Before 3.1 the file was
    # decoded and rewritten, so the same library added on Windows and on
    # Linux locked two different hashes.
    digest = hashlib.sha256(data).hexdigest()
    path = os.path.join("lib", name + ".vel")

    if os.path.exists(path):
        here = _digest_of(path)
        if here != digest and not force:
            print(f"'{name}' is already vendored at {path}, and what you "
                  f"are adding is a different file.", file=sys.stderr)
            print(f"  vendored  {here}", file=sys.stderr)
            print(f"  incoming  {digest}", file=sys.stderr)
            print(f"  add --force to replace it, after you have looked "
                  f"at what changed", file=sys.stderr)
            return 1
        locked = lock.get(name, {}).get("sha256")
        if locked and locked != here:
            print(f"note: {path} did not match {LOCKFILE} before this "
                  f"({locked[:16]}... locked, {here[:16]}... on disk)")

    os.makedirs("lib", exist_ok=True)
    kept = open(path, "rb").read() if os.path.exists(path) else None
    with open(path, "wb") as f:
        f.write(data)

    rep_ = inspect_source(path)           # a library must compile
    if rep_["errors"]:
        if kept is None:
            os.remove(path)
        else:
            with open(path, "wb") as f:   # put back what was there
                f.write(kept)
        print(f"'{name}' does not compile, so it was not added:",
              file=sys.stderr)
        for e in rep_["errors"][:3]:
            print(f"  line {e['line']}: [{e['code']}] {e['message']}",
                  file=sys.stderr)
        return 1

    deps = [d for d in deps if d[0] != name] + [(name, source, digest)]
    _manifest_write(deps)
    lock[name] = {"name": name, "source": source, "sha256": digest,
                  "file": "lib/" + name + ".vel", "added_by": VERSION}
    _lock_write(lock)
    own = [f for f in rep_["functions"]
           if os.path.abspath(f["file"]) == os.path.abspath(path)]
    proven = sum(1 for f in own if f["status"] == "proven")
    effs = sorted({e for f in own for e in f["effects"]})
    print(f"added {name} -> lib/{name}.vel")
    print(f"  {len(own)} function(s), {proven} with proven promises")
    print(f"  performs: {', '.join(effs) if effs else 'nothing'}")
    print(f"  sha256 {digest[:16]}..., locked in {LOCKFILE}")
    print(f'  use it with: import "lib/{name}.vel" as {name}')
    return 0


def gather_sources(entry: str) -> dict:
    """The entry file and everything it imports, by relative path."""
    seen: dict = {}
    root = os.path.dirname(os.path.abspath(entry)) or "."

    def walk(path: str) -> None:
        ap = os.path.abspath(path)
        rel = os.path.relpath(ap, root).replace("\\", "/")
        if rel in seen:
            return
        if not os.path.exists(ap):
            return                       # the stdlib is bundled separately
        text = open(ap, encoding="utf-8").read()
        seen[rel] = text
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("import "):
                continue
            piece = line[len("import "):].strip()
            if piece.startswith('"'):
                target = piece[1:piece.index('"', 1)]
                walk(os.path.join(os.path.dirname(ap), target))
    walk(entry)
    return seen


def build_program(argv: list) -> int:
    """Turn a Velaris program into one file anyone can run."""
    if not argv or argv[0].startswith("-"):
        print("usage: velaris build program.vel [-o name]",
              file=sys.stderr)
        return 1
    entry = argv[0]
    if not os.path.exists(entry):
        print(f"no such file: {entry}", file=sys.stderr)
        return 1
    out_name = os.path.splitext(os.path.basename(entry))[0]
    if "-o" in argv:
        out_name = argv[argv.index("-o") + 1]

    report = inspect_source(entry)       # never ship what does not compile
    if report["errors"]:
        print(f"{entry} does not compile, so it was not built:",
              file=sys.stderr)
        for e in report["errors"][:5]:
            print(f"  line {e['line']}: [{e['code']}] {e['message']}",
                  file=sys.stderr)
        return 1

    try:
        import PyInstaller                       # noqa: F401
    except ImportError:
        print("building needs PyInstaller:\n  pip install pyinstaller",
              file=sys.stderr)
        return 1

    import json as _json
    import shutil
    import subprocess
    import tempfile

    sources = gather_sources(entry)
    entry_rel = os.path.relpath(os.path.abspath(entry),
                                os.path.dirname(os.path.abspath(entry)))
    entry_rel = entry_rel.replace("\\", "/")
    work = tempfile.mkdtemp(prefix="velaris-build-")
    launcher = os.path.join(work, f"{out_name}.py")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("# Generated by velaris build - a Velaris program,\n"
                "# carrying its own compiler.\n"
                "import os, sys, tempfile\n"
                f"SOURCES = {_json.dumps(sources)}\n"
                f"ENTRY = {_json.dumps(entry_rel)}\n"
                "import velaris\n"
                "def main():\n"
                "    here = tempfile.mkdtemp(prefix='velaris-run-')\n"
                "    for rel, text in SOURCES.items():\n"
                "        p = os.path.join(here, rel)\n"
                "        os.makedirs(os.path.dirname(p), exist_ok=True)\n"
                "        open(p, 'w', encoding='utf-8').write(text)\n"
                "    sys.argv = [sys.argv[0], os.path.join(here, ENTRY)]"
                " + sys.argv[1:]\n"
                "    return velaris.main()\n"
                "sys.exit(main())\n")

    here = os.path.dirname(os.path.abspath(__file__))
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile",
           "--name", out_name, "--distpath", os.path.abspath("."),
           "--workpath", os.path.join(work, "build"),
           "--specpath", work, "--noconfirm",
           "--paths", here,
           "--add-data", f"{os.path.join(here, 'stdlib')}{sep}stdlib"]
    for extra in ("z3", "llvmlite"):
        try:
            __import__(extra)
            cmd += ["--collect-all", extra]
        except ImportError:
            pass
    cmd.append(launcher)
    if "--for-everyone" in argv:
        wf = os.path.join(".github", "workflows",
                          f"build-{out_name}.yml")
        os.makedirs(os.path.dirname(wf), exist_ok=True)
        with open(wf, "w", encoding="utf-8") as f:
            f.write(f"""# Built by velaris build --for-everyone.
# One machine cannot build for other machines, so three build for you.
name: build {out_name}

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            asset: {out_name}-windows.exe
          - os: ubuntu-latest
            asset: {out_name}-linux
          - os: macos-latest
            asset: {out_name}-macos
    runs-on: ${{{{ matrix.os }}}}
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "velaris-lang[full]" pyinstaller
      - run: velaris build {entry} -o {out_name}
      - shell: bash
        run: |
          for f in {out_name} {out_name}.exe; do
            [ -f "$f" ] && mv "$f" "${{{{ matrix.asset }}}}"
          done
      - uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: ${{{{ matrix.asset }}}}
""")
        print(f"wrote {wf}")
        print("commit it, then push a tag: three machines will build "
              f"{out_name} for Windows, Linux and macOS")
        return 0

    print(f"building {out_name} from {entry} "
          f"({len(sources)} file(s), this takes a minute)...")
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stdout[-2000:], file=sys.stderr)
        print(done.stderr[-2000:], file=sys.stderr)
        print("the build failed - the output above is from PyInstaller",
              file=sys.stderr)
        return 1
    shutil.rmtree(work, ignore_errors=True)
    made = out_name + (".exe" if os.name == "nt" else "")
    size = os.path.getsize(made) / (1024 * 1024) if os.path.exists(made) else 0
    print(f"built ./{made}  ({size:.0f} MB)")
    print("that file is the whole program - no Python, no Velaris, "
          "nothing to install")
    return 0


def doctor() -> int:
    OK, OPT, BAD = "[ ok ]", "[ -- ]", "[FAIL]"
    lines, healthy = [], True
    pv = sys.version_info
    if (pv.major, pv.minor) >= (3, 10):
        lines.append(f"{OK} python {pv.major}.{pv.minor}.{pv.micro}")
    else:
        healthy = False
        lines.append(f"{BAD} python {pv.major}.{pv.minor} - Velaris "
                     f"needs 3.10+ (install from python.org)")
    here = os.path.abspath(__file__)
    lines.append(f"{OK} velaris {VERSION}  ({here})")
    try:
        import z3  # noqa: F401
        lines.append(f"{OK} z3-solver - promises are PROVEN before "
                     f"running")
    except ImportError:
        lines.append(f"{OPT} z3-solver absent - promises checked at "
                     f"runtime instead   fix: pip install z3-solver")
    try:
        import llvmlite  # noqa: F401
        lines.append(f"{OK} llvmlite - pure numeric functions run as "
                     f"machine code")
    except ImportError:
        lines.append(f"{OPT} llvmlite absent - everything runs "
                     f"interpreted   fix: pip install llvmlite")
    std = os.path.join(os.path.dirname(here), "stdlib", "std.vel")
    if os.path.exists(std):
        try:
            fs, _ = load_program(std)
            lines.append(f"{OK} standard library - {len(fs)} functions "
                         f"ready to import")
        except VelarisError:
            healthy = False
            lines.append(f"{BAD} standard library present but broken - "
                         f"reinstall: pip install --force-reinstall "
                         f"velaris-lang")
    else:
        healthy = False
        lines.append(f"{BAD} standard library missing - reinstall: "
                     f"pip install --force-reinstall velaris-lang")
    try:
        toks = lex('fn main() uses io { print(2 + 2) }')
        fs2, rs2, _ = Parser(toks).parse_program()
        errs: list = []
        check_effects(fs2, errs)
        check_types(fs2, rs2, errs)
        if errs:
            raise VelarisError("E999", "self-test failed", 1)
        lines.append(f"{OK} compiler self-test - lex, parse, effects, "
                     f"types all answering")
    except Exception:
        healthy = False
        lines.append(f"{BAD} compiler self-test failed - please report "
                     f"this at github.com/gowrishankar-infra/"
                     f"velaris-lang/issues")
    print(f"velaris doctor - {VERSION}")
    print("-" * 60)
    for ln in lines:
        print(ln)
    print("-" * 60)
    if healthy:
        print("all essential checks passed. "
              "[ -- ] items are optional extras.")
        return 0
    print("something needs fixing - see [FAIL] lines above.")
    return 1


def new_project(name: str) -> int:
    if not name or name.startswith("-"):
        print("usage: velaris new <project-name>", file=sys.stderr)
        return 1
    if os.path.exists(name):
        print(f"'{name}' already exists - pick a fresh name",
              file=sys.stderr)
        return 1
    os.makedirs(name)
    with open(os.path.join(name, "main.vel"), "w",
              encoding="utf-8") as f:
        f.write(STARTER)
    with open(os.path.join(name, "README.md"), "w",
              encoding="utf-8") as f:
        f.write(f"# {name}\n\nA Velaris project.\n\n"
                f"```\ncd {name}\nvelaris main.vel\n```\n\n"
                f"Docs: https://github.com/gowrishankar-infra/"
                f"velaris-lang\n")
    print(f"created {name}/")
    print(f"  {name}/main.vel    - a working program with a proven "
          f"contract")
    print(f"  {name}/README.md")
    print(f"next:  cd {name}  then  velaris main.vel")
    return 0


def repl() -> int:
    print(f"Velaris {VERSION} - interactive session.")
    print("Definitions (fn / record / import) are fully checked before "
          "joining;\nloose lines are checked while running. "
          "Type exit to leave.")
    sess_funcs: list[Function] = []
    sess_recs: list = []
    env: dict = {}
    rt = build_runtime(sess_funcs)

    while True:
        try:
            line = input("velaris> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.strip() in ("exit", "quit", ":q"):
            return 0
        if not line.strip():
            continue
        depth = line.count("{") - line.count("}")
        while depth > 0:
            try:
                more = input("   ...  ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            line += "\n" + more
            depth += more.count("{") - more.count("}")
        try:
            toks = lex(line)
        except VelarisError as e:
            print(e.human("<repl>"))
            continue
        kind = toks[0].text if toks and toks[0].kind == "KEYWORD" else ""
        try:
            if kind in ("fn", "record", "import"):
                fs, rs, imps = Parser(toks).parse_program()
                for ipath, _ in imps:
                    if not os.path.exists(ipath):
                        shipped = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "stdlib", os.path.basename(ipath))
                        if os.path.exists(shipped):
                            ipath = shipped
                    ifuncs, irecs = load_program(ipath)
                    fs += ifuncs
                    rs += irecs
                cand_f = {f.name: f for f in sess_funcs}
                cand_r = {r.name: r for r in sess_recs}
                for f in fs:
                    if f.name in cand_f:
                        print(f"(replacing fn {f.name})")
                    cand_f[f.name] = f
                for r in rs:
                    if r.name in cand_r:
                        print(f"(replacing record {r.name})")
                    cand_r[r.name] = r
                new_f, new_r = list(cand_f.values()), list(cand_r.values())
                errs: list = []
                check_effects(new_f, errs)
                check_types(new_f, new_r, errs)
                if not errs:
                    check_proofs(new_f, new_r, errs)
                if errs:
                    for e in errs:
                        print(e.human("<repl>"))
                    print("(not accepted)")
                    continue
                sess_funcs[:] = new_f
                sess_recs[:] = new_r
                rt = build_runtime(list(sess_funcs))
                names = [f.name for f in fs] + [r.name for r in rs]
                print("defined: " + ", ".join(names))
            else:
                p = Parser(toks)
                stmts = []
                while p.peek().kind != "EOF":
                    stmts.append(p.parse_statement())
                for s in stmts:
                    if isinstance(s, ExprStmt):
                        v = rt["eval"](s.expr, env)
                        if v is not None:
                            print(to_text(v))
                    else:
                        rt["run"](s, env)
        except FailSignal as f:
            print("failed: " + to_text(f.reason))
        except ReturnSignal:
            print("('return' only works inside a function)")
        except VelarisError as e:
            print(e.human("<repl>"))
        except RecursionError:
            print("(too much recursion)")


def _token_problem(token: str, where: str) -> str | None:
    """Why this token will not do, without ever repeating it."""
    if len(token) < 16:
        return (f"the token in {where} is shorter than 16 characters; make "
                f"one with: python -c \"import secrets; "
                f"print(secrets.token_urlsafe(32))\"")
    if not all(0x21 <= ord(c) <= 0x7E for c in token):
        return (f"the token in {where} must be printable ASCII with no "
                f"spaces")
    return None


def _read_token_file(path: str) -> tuple:
    """(token, None) or (None, why not). The file holds the token and
    nothing else; surrounding whitespace and a UTF-8 byte-order mark
    are ignored."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        return None, f"cannot read the token file {path}: {e.strerror or e}"
    raw = raw.removeprefix(b"\xef\xbb\xbf").strip()
    try:
        token = raw.decode("ascii")
    except UnicodeDecodeError:
        return None, (f"the token in {path} must be printable ASCII with "
                      f"no spaces")
    why = _token_problem(token, path)
    return (None, why) if why else (token, None)


# What a door - the HTTP door or the MCP server - lets one run take when
# its operator names nothing else: the defaults the doors have had since
# 2.59, and from 4.0 a ceiling as well. Before 4.0 a caller could send
# any timeout and any memory cap and have it, so the operator's limits
# were only the values used when a caller sent none.
DOOR_MAX_TIMEOUT = 30
DOOR_MAX_MEMORY_MB = 512


def door_ceilings(timeout_flag, memory_flag) -> tuple:
    """(most seconds, most MB) one run may have, from a door's
    --max-timeout and --max-memory-mb (None when not given). A value
    that is not a limit is a ValueError holding the sentence to show."""
    most_time = DOOR_MAX_TIMEOUT
    if timeout_flag is not None:
        try:
            most_time = float(timeout_flag)
        except ValueError:
            most_time = float("nan")
        if not (most_time > 0 and most_time != float("inf")):
            raise ValueError("--max-timeout needs a number of seconds "
                             "greater than 0, as --max-timeout 30")
        if most_time == int(most_time):
            most_time = int(most_time)
    most_memory = DOOR_MAX_MEMORY_MB
    if memory_flag is not None:
        if not (_ascii_digits(str(memory_flag)) and int(memory_flag) >= 1):
            raise ValueError("--max-memory-mb needs a whole number of MB, "
                             "1 or more, as --max-memory-mb 512")
        most_memory = int(memory_flag)
    return most_time, most_memory


def run_limits(asked: dict, most_time, most_memory) -> tuple:
    """What a door gives one run: (timeout, max_memory_mb, None), or
    (None, None, (outcome, sentence)) when the request cannot have it -
    'bad_request' for a value that is not a limit, 'ceiling' for one
    past what the operator set. A limit the request leaves out is the
    operator's; a caller may ask for less, never for more."""
    def number(v) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    timeout = asked.get("timeout")
    if timeout is None:
        timeout = most_time
    elif not (number(timeout) and 0 < timeout < float("inf")):
        return None, None, ("bad_request", "timeout is a number of "
                            "seconds greater than 0")
    elif timeout > most_time:
        return None, None, ("ceiling", f"this server allows at most "
                            f"{most_time:g} second(s) per run; the request "
                            f"asked for {timeout:g}")
    memory = asked.get("max_memory_mb")
    if memory is None:
        memory = most_memory
    elif not (number(memory) and memory == int(memory) and memory >= 1):
        return None, None, ("bad_request", "max_memory_mb is a whole number "
                            "of MB, 1 or more")
    elif memory > most_memory:
        return None, None, ("ceiling", f"this server allows at most "
                            f"{most_memory} MB per run; the request asked "
                            f"for {int(memory)}")
    return timeout, int(memory), None


def serve_main(argv: list) -> int:
    """`velaris serve`: an HTTP door, so a program in any language can
    check, audit and run Velaris under a budget - not only Python and
    not only MCP clients.

    Every endpoint but GET /health needs `Authorization: Bearer
    <token>`, compared in constant time; a missing or wrong token is a
    401 that says nothing about which. The token comes from
    --token-file, else VELARIS_TOKEN (which is then removed from the
    environment the workers inherit), else it is made here and printed
    once. It is never taken as an argument: every process on the machine
    can read another's command line. --no-auth drops the token, for
    local development only, is refused on any host but 127.0.0.1 or
    localhost, and warns on every start. Every call is one line in the
    invocation log (InvocationLog).

    The operator sets the limits (4.0): --max-allow is the most a
    request's budget may grant, io when the flag is absent;
    --max-timeout and --max-memory-mb are the most one run may have, 30
    seconds and 512 MB when absent. A request for more at any of the
    three is refused with 403, naming the ceilings.
    """
    import hashlib
    import http.server
    import secrets
    import urllib.parse

    valued = {"--port", "--host", "--max-allow", "--token-file",
              "--log-file", "--log", "--max-timeout", "--max-memory-mb"}
    opts: dict = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--token" or a.startswith("--token="):
            print("velaris serve does not take a token as an argument: "
                  "every process on this machine can read another's "
                  "command line. Put it in a file and pass --token-file "
                  "<path>, or set VELARIS_TOKEN.", file=sys.stderr)
            return 2
        if a == "--no-auth":
            opts[a] = True
            i += 1
            continue
        if a in valued:
            if i + 1 >= len(argv):
                print(f"{a} needs a value", file=sys.stderr)
                return 2
            opts[a] = argv[i + 1]
            i += 2
            continue
        # an option's name is repeated back; anything else is not, in
        # case it is a token typed where it should not be
        shown = f" '{a}'" if re.fullmatch(r"--[a-z][a-z-]{0,30}", a) else ""
        print(f"velaris serve: unknown argument{shown}. It takes --port, "
              f"--host, --max-allow, --max-timeout, --max-memory-mb, "
              f"--token-file, --no-auth, --log-file and --log.",
              file=sys.stderr)
        return 2

    # Read VELARIS_TOKEN and take it out of the environment whichever
    # source wins, so no pool worker - and so no program - inherits it.
    # The token is settled first, so every message after this point can
    # be kept from repeating it, even one about a flag it was typed into.
    env_token = os.environ.pop("VELARIS_TOKEN", None)
    no_auth = "--no-auth" in opts
    token_file = opts.get("--token-file")
    token: str | None = None
    told = None
    if no_auth:
        if token_file:
            print("--no-auth and --token-file ask for opposite things; "
                  "give one", file=sys.stderr)
            return 2
    elif token_file:
        token, why = _read_token_file(token_file)
        if why:
            print(why, file=sys.stderr)
            return 2
        told = f"read from {token_file}"
    elif env_token is not None:
        token = env_token.strip()
        why = _token_problem(token, "VELARIS_TOKEN")
        if why:
            print(why, file=sys.stderr)
            return 2
        told = "read from VELARIS_TOKEN, and removed from the environment"
    else:
        token = secrets.token_urlsafe(32)
        told = "made for this run, shown once: " + token
    want = hashlib.sha256(token.encode("ascii")).digest() if token else None

    def refuse(message: str) -> int:
        print(message.replace(token, "[redacted]") if token else message,
              file=sys.stderr)
        return 2

    host = opts.get("--host", "127.0.0.1")
    if no_auth and host not in ("127.0.0.1", "localhost"):
        return refuse(f"--no-auth is refused with --host {host}: without "
                      f"a token, anyone who can reach the port can run "
                      f"programs. It is allowed on 127.0.0.1 or localhost "
                      f"only.")
    try:
        port = int(opts.get("--port", "8787"))
        if not 0 <= port <= 65535:
            raise ValueError
    except ValueError:
        return refuse("--port needs a whole number from 0 to 65535")
    # the ceiling: a caller may ask for anything inside it, at any level -
    # effect, module, path prefix, host, count - and nothing outside;
    # Budget.covers is the one place that rule lives. Without the flag it
    # is io, as the MCP server's is (4.0); before 4.0 a door started
    # without --max-allow granted every effect, ffi included, to anyone
    # holding the token.
    try:
        _asked_ceiling = opts.get("--max-allow", DEFAULT_ALLOW)
        if _asked_ceiling.strip() == ALLOW_ALL:
            warn_allow_all("velaris serve")
        ceiling = Budget.parse(expand_allow(_asked_ceiling))
    except BudgetError as e:
        return refuse(f"--max-allow: {e}")
    max_allow = ceiling.effects
    ceiling_list = ceiling.spec().split(",") if ceiling.spec() else []
    try:
        most_time, most_memory = door_ceilings(opts.get("--max-timeout"),
                                               opts.get("--max-memory-mb"))
    except ValueError as e:
        return refuse(str(e))

    def over_ceiling(what: str) -> dict:
        return {"error": what, "max_allow": ceiling_list,
                "max_timeout": most_time, "max_memory_mb": most_memory}

    try:
        log = InvocationLog(opts.get("--log-file"), opts.get("--log", "full"),
                            redact=[token] if token else [])
    except ValueError as e:
        return refuse(f"--log: {e}")
    except OSError as e:
        return refuse(f"cannot open the log file {opts.get('--log-file')}: "
                      f"{e.strerror or e}")

    import velaris as _self              # the library half, reused whole

    # One pool per distinct budget a caller asks for, made the first
    # time that budget is seen and closed when the door stops. The
    # ceiling is checked before a pool is asked for, so a pool never
    # exists for a budget this server would refuse.
    pools = _self.PoolRegistry()
    endpoints = {("GET", "/health"), ("GET", "/"), ("GET", "/card"),
                 ("POST", "/check"), ("POST", "/audit"), ("POST", "/run")}

    class Door(http.server.BaseHTTPRequestHandler):
        def version_string(self):        # no Python version in the header
            return "velaris"

        def log_message(self, *a):       # the invocation log is the log
            pass

        def answer(self, code, payload, headers=()):
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def authorized(self) -> bool:
            if want is None:
                return True
            given = self.headers.get_all("Authorization") or []
            if len(given) != 1:
                return False
            scheme, _, value = given[0].strip().partition(" ")
            if scheme.lower() != "bearer":
                return False
            got = hashlib.sha256(
                value.strip().encode("latin-1", "replace")).digest()
            return secrets.compare_digest(got, want)

        def not_local(self):
            """With --no-auth, what stands in for the token against a web
            page open in a browser on this machine: the request must be
            addressed to 127.0.0.1 or localhost (which a DNS-rebinding
            page cannot fake), carry no Origin but this server's, and a
            POST must say it is JSON (which a page cannot send across
            origins without a preflight, and this server approves none)."""
            bound = str(self.server.server_address[1])
            ok_names = ("127.0.0.1", "localhost")
            name, _, at = (self.headers.get("Host") or "").strip() \
                .lower().partition(":")
            if name not in ok_names or at not in ("", bound):
                return 403, ("this server answers requests addressed to "
                             "127.0.0.1 or localhost only")
            origin = (self.headers.get("Origin") or "").strip().lower()
            if origin and origin not in (f"http://{n}:{bound}"
                                         for n in ok_names):
                return 403, "this server does not answer web pages"
            kind = (self.headers.get("Content-Type") or "").split(";")[0]
            if self.command == "POST" and \
                    kind.strip().lower() != "application/json":
                return 415, "send Content-Type: application/json"
            return None

        def drain(self) -> None:
            # read what the caller sent before refusing it, so the socket
            # closes cleanly instead of resetting under the answer
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return
            if 0 < n <= 2_000_000:
                self.rfile.read(n)

        def do_GET(self):
            self.call()

        def do_POST(self):
            self.call()

        do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_GET

        def call(self) -> None:
            started = InvocationLog.started()
            method = self.command
            where = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            rec = {"outcome": "error", "budget": None, "effects": None,
                   "refusals": [], "source": None}
            try:
                code, payload, headers = self.route(method, where, rec)
                try:
                    self.answer(code, payload, headers)
                except OSError:
                    rec["outcome"] = "caller_gone"
            finally:
                # the endpoint by name - never the path as sent, which
                # could carry anything, a token in a query string included
                log.record(started, door="http",
                           endpoint=(f"{method} {where}"
                                     if (method, where) in endpoints
                                     else f"{method} (no such endpoint)"),
                           client=self.client_address[0],
                           outcome=rec["outcome"], budget=rec["budget"],
                           effects=rec["effects"], refusals=rec["refusals"],
                           source=rec["source"])

        def status(self) -> dict:
            doc = {"velaris": VERSION, "prover": bool(HAVE_Z3),
                   "auth": "bearer" if want is not None else "none"}
            if self.authorized():
                doc["max_allow"] = sorted(max_allow)
                doc["max_timeout"] = most_time
                doc["max_memory_mb"] = most_memory
                doc["endpoints"] = ["POST /check", "POST /audit",
                                    "POST /run", "GET /card"]
            return doc

        def route(self, method, where, rec) -> tuple:
            if (method, where) == ("GET", "/health"):
                rec["outcome"] = "ok"
                return 200, self.status(), ()
            if no_auth:
                why = self.not_local()
                if why:
                    self.drain()
                    rec["outcome"] = "not_local"
                    return why[0], {"error": why[1]}, ()
            if not self.authorized():
                self.drain()
                rec["outcome"] = "unauthorized"
                return 401, {"error": "unauthorized"}, (
                    ("WWW-Authenticate", 'Bearer realm="velaris"'),)
            if (method, where) not in endpoints:
                self.drain()
                rec["outcome"] = "not_found"
                return 404, {"error": "no such endpoint"}, ()
            if method == "GET":
                rec["outcome"] = "ok"
                if where == "/card":
                    return 200, {"card": _self.card()}, ()
                return 200, self.status(), ()
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length < 0:
                    raise ValueError
            except ValueError:
                rec["outcome"] = "bad_request"
                return 400, {"error": "Content-Length is not a length"}, ()
            if length > 2_000_000:
                rec["outcome"] = "too_large"
                return 413, {"error": "that is too large"}, ()
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError) as e:
                rec["outcome"] = "bad_request"
                return 400, {"error": f"bad JSON: {e}"}, ()
            source = body.get("source", "") if isinstance(body, dict) \
                else None
            if not isinstance(source, str) or not source.strip():
                rec["outcome"] = "bad_request"
                return 400, {"error": "send {\"source\": ...}"}, ()
            rec["source"] = source
            try:
                if where == "/check":
                    got = _self.check(source)
                    rec["outcome"] = "ok" if got.ok else "problems"
                    return 200, got.as_dict(), ()
                if where == "/audit":
                    got = _self.audit(source)
                    rec["outcome"] = "ok" if got.ok else "problems"
                    return 200, got.as_dict(), ()
                asked = body.get("allow") or ["io"]
                if not isinstance(asked, list) or \
                        not all(isinstance(a, str) for a in asked):
                    rec["outcome"] = "bad_request"
                    return 400, {"error": "allow is a list of grants, "
                                          "as [\"io\"]"}, ()
                try:
                    wanted = _self.Budget.parse(",".join(asked))
                except _self.BudgetError as e:
                    rec["outcome"] = "bad_request"
                    return 400, {"error": str(e)}, ()
                refused = ceiling.covers(wanted)
                if refused:
                    rec["outcome"] = "ceiling"
                    rec["refusals"] = [{"by": "ceiling", "what": refused}]
                    return 403, over_ceiling(refused), ()
                # the time and memory a run may have are the operator's
                # too: a caller may ask for less, and asking for more is
                # refused the way an over-wide budget is (4.0)
                timeout, memory, why = run_limits(body, most_time,
                                                  most_memory)
                if why:
                    rec["outcome"] = why[0]
                    if why[0] == "ceiling":
                        rec["refusals"] = [{"by": "ceiling",
                                            "what": why[1]}]
                        return 403, over_ceiling(why[1]), ()
                    return 400, {"error": why[1]}, ()
                rec["budget"] = wanted.spec()
                out = pools.run(
                    source, allow=set(asked),
                    stdin=body.get("stdin", ""),
                    args=body.get("args") or [],
                    timeout=timeout, max_memory_mb=memory)
                rec["effects"] = out.effects_used
                rec["outcome"] = run_outcome(out)
                rec["refusals"] = run_refusals(out)
                payload = out.as_dict()
                payload["allowed"] = sorted(asked)
                return 200, payload, ()
            except Exception as e:
                rec["outcome"] = "error"
                return 500, {"error": f"{type(e).__name__}: {e}"}, ()

    try:
        httpd = http.server.ThreadingHTTPServer((host, port), Door)
    except OSError as e:
        log.close()
        return refuse(f"cannot listen on {host}:{port}: {e.strerror or e}")
    port = httpd.server_address[1]

    print(f"velaris {VERSION} listening on http://{host}:{port}")
    print("  POST /check /audit /run   GET /card /health")
    print(f"  grants at most: {ceiling.spec() or 'nothing'}"
          + ("   (the default; --max-allow to change it)"
             if "--max-allow" not in opts else ""))
    print(f"  each run at most: {most_time:g} second(s), {most_memory} MB"
          + ("" if "--max-timeout" in opts and "--max-memory-mb" in opts
             else "   (--max-timeout, --max-memory-mb)"))
    if token is not None:
        print("  every endpoint but GET /health needs "
              "'Authorization: Bearer <token>'")
        print(f"  token: {told}")
    where_log = opts.get("--log-file") or "stderr"
    print(f"  log: one JSON line per call ({log.detail}) to {where_log}")
    sys.stdout.flush()
    if no_auth:
        bar = "  " + "!" * 66
        print("\n".join([
            bar,
            "  WARNING: --no-auth. No token is asked for. Any process on",
            "  this machine, run by any user, can send this server a",
            f"  program and it runs, with up to: {ceiling.spec() or 'nothing'}",
            "  This is for local development only. A request must be",
            "  addressed to 127.0.0.1 or localhost, carry no other",
            "  Origin, and POST as Content-Type: application/json, so a",
            "  web page in a browser here cannot use it; nothing stops a",
            "  local program.",
            bar]), file=sys.stderr)
    if host not in ("127.0.0.1", "localhost"):
        print("  WARNING: not bound to localhost. This endpoint RUNS "
              "programs, and it speaks plain HTTP: the token crosses the "
              "network readable by anyone on the path unless a TLS proxy "
              "sits in front. Do not expose it to a network you do not "
              "control.", file=sys.stderr)
    if token_file and os.name != "nt":
        try:
            if os.stat(token_file).st_mode & 0o077:
                print(f"  WARNING: {token_file} can be read by other users "
                      f"on this machine; chmod 600 it", file=sys.stderr)
        except OSError:
            pass
    if "ffi" in max_allow:
        print("  note: ffi is grantable here, which means a caller "
              "can do anything Python can. --max-allow io,fs is "
              "safer for a shared machine.")
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
        pools.close()                     # no worker outlives the door
        log.close()
    return 0


MIGRATE_TO = ("5.0", "5", "5.0.0")

# A line in a shell script or a CI file that runs a Velaris program:
# the command, the .vel path, and whatever follows it. `velaris`,
# `velaris run`, `python velaris.py` and `npx velaris-lang` all count.
_RUNNER = r"(?:(?:python[0-9.]*\s+)?[\w./\\-]*velaris(?:\.py|-lang)?)"
MIGRATE_LINE = re.compile(
    r"^(?P<head>\s*(?:-\s+)?(?:run:\s*)?)"
    r"(?P<cmd>" + _RUNNER + r"(?:\s+run)?)"
    r"(?P<mid>\s+)"
    r"(?P<file>[\w./\\-]+\.vel)"
    r"(?P<tail>.*)$")

# what stops a line being rewritten: another command after this one, a
# substitution, or output sent somewhere. The flag would still parse,
# but where it belongs on such a line is a guess, and this command does
# not guess.
MIGRATE_UNSURE = ("|", "&", ";", "`", "$(", ">>", "<")


def migrate_needs(path: str) -> dict:
    """What one program needs to keep running under 5.0.

    The narrowest budget its own audit can write - the same grants
    `safe_command` carries - or why it could not be worked out.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as e:
        return {"path": path, "ok": False, "why": str(e), "allow": None}
    try:
        report = audit(source, path=path)
    except Exception as e:                 # a file that does not parse
        return {"path": path, "ok": False, "why": str(e), "allow": None}
    if not report.ok:
        first = report.problems[0] if report.problems else None
        return {"path": path, "ok": False, "allow": None,
                "why": (f"does not compile: [{first.code}] {first.message}"
                        if first else "does not compile")}
    grants = _safe_grants(report.effects, report.ffi_modules,
                          {"read": sorted(report.fs_paths["read"]),
                           "write": sorted(report.fs_paths["write"]),
                           "read_any": report.fs_paths["read_any"],
                           "write_any": report.fs_paths["write_any"]},
                          {"hosts": sorted(report.net_hosts["hosts"]),
                           "any": report.net_hosts["any"]})
    return {"path": path, "ok": True, "allow": ",".join(grants),
            "effects": list(report.effects),
            # io alone, or no effect at all, is what 5.0 grants already
            "enough": set(report.effects) <= {DEFAULT_ALLOW},
            "warnings": list(report.warnings), "why": None}


def _migrate_rewrite(text: str, needs: dict, root: str) -> tuple:
    """One shell script or CI file with `--allow` added to every line
    that runs a program this migration worked out a budget for.

    Returns (new text, [what changed], [what was left alone and why]).
    A line is rewritten only when all of it is understood: one command,
    a .vel path that resolves to a program in `needs`, no budget flag
    already on it, and nothing that would make the end of the command
    the wrong place for a flag.
    """
    changed, skipped, out = [], [], []
    for n, line in enumerate(text.split("\n"), 1):
        m = MIGRATE_LINE.match(line)
        if not m:
            out.append(line)
            continue
        out.append(line)
        if "--allow" in line or "--deny" in line:
            continue                        # already says what it needs
        target = m.group("file").replace("\\", "/")
        found = None
        for cand in (os.path.normpath(os.path.join(root, target)),
                     os.path.normpath(target)):
            found = needs.get(os.path.normcase(os.path.abspath(cand)))
            if found is not None:
                break
        if found is None:
            skipped.append((n, line.strip(),
                            f"no program of this checkout at {target}"))
            continue
        if not found["ok"]:
            skipped.append((n, line.strip(), f"{target}: {found['why']}"))
            continue
        if found["enough"]:
            continue                        # io, which 5.0 grants anyway
        if any(c in line for c in MIGRATE_UNSURE):
            skipped.append((n, line.strip(),
                            "more than one command on the line, or its "
                            "input or output moved: add --allow "
                            + found["allow"] + " by hand"))
            continue
        # after the file name, before the program's own arguments, which
        # is where the command line reads flags and where a reader of
        # the script looks for them
        out[-1] = (m.group("head") + m.group("cmd") + m.group("mid")
                   + m.group("file") + f" --allow {found['allow']}"
                   + m.group("tail"))
        changed.append((n, target, found["allow"]))
    return "\n".join(out), changed, skipped


MIGRATE_WRITABLE = (".sh", ".bash", ".yml", ".yaml")


def migrate_main(argv: list) -> int:
    """velaris migrate --to 5.0 [path] [--write] [--json]

    What every program under `path` needs to keep running under 5.0,
    where a run with no --allow gets `io` instead of all seven effects
    (STABILITY.md, "Breaks we have made"). It reads; it writes nothing
    unless --write is given, and then only shell scripts and CI files
    it can parse with no guessing, and it says what it left alone.
    """
    if "--to" not in argv:
        print("usage: velaris migrate --to 5.0 [path] [--write] [--json]",
              file=sys.stderr)
        return 2
    at = argv.index("--to")
    want = argv[at + 1] if at + 1 < len(argv) else ""
    if want not in MIGRATE_TO:
        print(f"velaris migrate knows how to migrate to 5.0, not "
              f"{want or '(nothing)'}", file=sys.stderr)
        return 2
    flags = {"--write", "--json"}
    rest = [a for i, a in enumerate(argv)
            if i not in (at, at + 1) and a not in flags]
    write, as_json = "--write" in argv, "--json" in argv
    unknown = [a for a in rest if a.startswith("-")]
    if unknown:
        print(f"velaris migrate: unknown argument '{unknown[0]}'",
              file=sys.stderr)
        return 2
    target = rest[0] if rest else "."

    if os.path.isdir(target):
        root = target
        programs = [os.path.join(target, f.replace("/", os.sep))
                    for f in _capability_files(target)]
    elif os.path.exists(target):
        root = os.path.dirname(target) or "."
        programs = [target]
    else:
        print(f"no such file or folder: {target}", file=sys.stderr)
        return 1

    rows = [migrate_needs(p) for p in sorted(programs)]
    by_path = {os.path.normcase(os.path.abspath(r["path"])): r
               for r in rows}

    wrote, untouched = [], []
    if write:
        for dp, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for f in sorted(files):
                if not f.endswith(MIGRATE_WRITABLE):
                    continue
                full = os.path.join(dp, f)
                try:
                    with open(full, "r", encoding="utf-8") as fh:
                        before = fh.read()
                except (OSError, UnicodeDecodeError) as e:
                    untouched.append((full, 0, str(e)))
                    continue
                after, changed, skipped = _migrate_rewrite(
                    before, by_path, root)
                untouched += [(full, n, why) for n, _, why in skipped]
                if changed and after != before:
                    with open(full, "w", encoding="utf-8",
                              newline="") as fh:
                        fh.write(after)
                    wrote.append((full, changed))

    def command_for(r: dict) -> str:
        shown = r["path"].replace(os.sep, "/")
        return (f"velaris {shown}" if r["enough"]
                else f"velaris {shown} --allow {r['allow']}")

    if as_json:
        print(json.dumps({
            "schema": "velaris.migrate/1", "velaris_version": VERSION,
            "to": "5.0", "root": root.replace(os.sep, "/"),
            "programs": [
                {"path": r["path"].replace(os.sep, "/"), "ok": r["ok"],
                 "allow": r["allow"], "why": r["why"],
                 "command": command_for(r) if r["ok"] else None}
                for r in rows],
            "written": [{"file": f.replace(os.sep, "/"),
                         "lines": [{"line": n, "program": p, "allow": a}
                                   for n, p, a in ch]}
                        for f, ch in wrote],
            "not_written": [{"file": f.replace(os.sep, "/"), "line": n,
                             "why": why} for f, n, why in untouched],
        }, indent=2))
        return 0

    print(f"velaris migrate --to 5.0   ({len(rows)} program(s) under "
          f"{root.replace(os.sep, '/')})")
    print("a run with no --allow gets io from 5.0; before, it got all "
          "seven effects.")
    print("=" * 68)
    needs_more = [r for r in rows if r["ok"] and not r["enough"]]
    fine = [r for r in rows if r["ok"] and r["enough"]]
    broken = [r for r in rows if not r["ok"]]
    for r in needs_more:
        print(f"\n{r['path'].replace(os.sep, '/')}")
        print(f"    uses:  {', '.join(r['effects'])}")
        print(f"    run:   {command_for(r)}")
        for w in r["warnings"]:
            print(f"    note:  {w}")
    if fine:
        print(f"\n{len(fine)} program(s) need nothing: they use io or no "
              f"effect at all, which 5.0 grants.")
    if broken:
        print(f"\n{len(broken)} file(s) the budget could not be worked "
              f"out for:")
        for r in broken:
            print(f"    {r['path'].replace(os.sep, '/')}: {r['why']}")
    if write:
        print()
        if wrote:
            for f, changed in wrote:
                print(f"wrote {f.replace(os.sep, '/')}")
                for n, p, a in changed:
                    print(f"    line {n}: {p} --allow {a}")
        else:
            print("wrote nothing: no line in a shell script or CI file "
                  "needed a budget added.")
        if untouched:
            print(f"\nleft alone ({len(untouched)}), for you to read:")
            for f, n, why in untouched:
                where = f.replace(os.sep, "/")
                print(f"    {where}{':' + str(n) if n else ''}: {why}")
    else:
        print("\nnothing was changed. --write updates the shell scripts "
              "and CI files it can parse, and says what it did not.")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["--pool-worker"]:
        return pool_worker(argv[1:])       # one child behind velaris.Pool
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
            ["serve"], ["mcp"], ["mcp-verify"], ["mcp-manifest"]):
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
        globals()["MAX_READ_BYTES"] = int(argv[at]) * 1024 * 1024
    if argv[:1] == ["repl"]:
        return repl()
    if argv[:1] == ["version"]:
        print(f"Velaris {VERSION}")
        return 0
    if argv[:1] == ["fmt"]:
        return fmt_main(argv[1:])
    if argv[:1] == ["lsp"]:
        return lsp_serve()
    if argv[:1] in (["add"], ["deps"], ["verify"]):
        return packages(argv)
    if argv[:1] == ["proofs"]:
        target = argv[1] if len(argv) > 1 and not argv[1].startswith("-") \
            else "."
        files = []
        if os.path.isdir(target):
            files = sorted(
                os.path.join(dp, f)
                for dp, _, fns in os.walk(target) for f in fns
                if f.endswith(".vel") and ".velaris" not in dp)
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
                        for e in f["ensures"]:
                            print(f"                promises {e}")
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
    if argv[:1] == ["conformance"]:
        return conformance_main(argv[1:])
    if argv[:1] == ["attest"]:
        return attest_main(argv[1:])
    if argv[:1] == ["mcp-manifest"]:
        return mcp_manifest_main(argv[1:])
    if argv[:1] == ["mcp-verify"]:
        return mcp_verify_main(argv[1:])

    if argv[:1] == ["mcp"]:
        # The same stdio server `python -m velaris_mcp` starts, reached
        # through the console script - so `velaris mcp`, and through the
        # npm wrapper `npx velaris-lang mcp`, start an MCP server without
        # the client having to know where the module sits. A thin alias
        # and nothing else: the flags, the tools, the ceilings and the
        # log are velaris_mcp's, parsed by velaris_mcp, and there is no
        # second set of them here.
        here = os.path.dirname(os.path.abspath(__file__))
        for where in (here, os.path.join(here, "..")):
            script = os.path.join(where, "velaris_mcp.py")
            if os.path.exists(script):
                sys.path.insert(0, where)
                import velaris_mcp
                return velaris_mcp.main(argv[1:])
        try:
            import velaris_mcp
            return velaris_mcp.main(argv[1:])
        except ImportError:
            print("the MCP server is not alongside this compiler; get it "
                  "from https://github.com/gowrishankar-infra/velaris-lang",
                  file=sys.stderr)
            return 1

    if argv[:1] == ["mcp-install"]:
        here = os.path.dirname(os.path.abspath(__file__))
        for where in (here, os.path.join(here, "..")):
            script = os.path.join(where, "velaris_mcp_install.py")
            if os.path.exists(script):
                sys.path.insert(0, where)
                import velaris_mcp_install
                return velaris_mcp_install.main(argv[1:])
        try:
            import velaris_mcp_install
            return velaris_mcp_install.main(argv[1:])
        except ImportError:
            print("the installer is not alongside this compiler; get it "
                  "from https://github.com/gowrishankar-infra/velaris-lang",
                  file=sys.stderr)
            return 1

    if argv[:1] == ["card"]:
        here = os.path.dirname(os.path.abspath(__file__))
        for where in (os.path.join(here, "LLM.md"),
                      os.path.join(here, "..", "LLM.md")):
            if os.path.exists(where):
                sys.stdout.write(open(where, encoding="utf-8").read())
                return 0
        print("LLM.md is not installed alongside the compiler; read it at "
              "https://github.com/gowrishankar-infra/velaris-lang/blob/"
              "main/LLM.md", file=sys.stderr)
        return 1

    if argv[:1] == ["audit"]:
        if "--sarif" in argv:
            # one or more files or folders, as `proofs` takes them
            files = []
            for target in [a for a in argv[1:]
                           if not a.startswith("-")] or ["."]:
                if os.path.isdir(target):
                    files += sorted(
                        os.path.join(dp, f)
                        for dp, _, fns in os.walk(target) for f in fns
                        if f.endswith(".vel") and ".velaris" not in dp)
                elif os.path.exists(target):
                    files.append(target)
                else:
                    print(f"no such file: {target}", file=sys.stderr)
                    return 1
            sarif = sarif_audit(files)
            print(json.dumps(sarif, indent=2))
            print_sarif_summary(sarif)
            return 1 if any(not a["ok"] for a in
                            sarif["runs"][0]["properties"]["audits"]) else 0
        if len(argv) < 2:
            print("usage: velaris audit program.vel", file=sys.stderr)
            return 1
        target = argv[1]
        if not os.path.exists(target):
            print(f"no such file: {target}", file=sys.stderr)
            return 1
        report = inspect_source(target)
        own = [f for f in report["functions"]
               if os.path.abspath(f["file"]) == os.path.abspath(target)]
        outside = sorted({e for f in own for e in f["effects"]})
        promising = [f for f in own if f["requires"] or f["ensures"]]
        proven = [f for f in promising if f["status"] == "proven"]
        runtime = [f for f in promising if f["status"] != "proven"]
        reaching = [f for f in own if f["effects"]]
        fallible = [f for f in own if f["can_fail"]]
        unshown = [f for f in own if f.get("loops_unshown")]
        inline_unshown = [lp for lp in report.get("inline_loops", [])
                          if lp["verdict"] == "unshown"
                          and os.path.abspath(lp["file"])
                          == os.path.abspath(target)]
        coverage = contract_coverage(own, report.get("records", []))

        if "--json" in argv:
            # velaris.audit/1, the same document the library, the MCP
            # server, the HTTP door, the npm package, the CrewAI tool and
            # the Action all emit - so a consumer meets one shape from
            # every door (spec Q3, resolved in 3.3). Before 3.3 this
            # printed an older, unversioned summary the schema rejected.
            result = audit(open(target, encoding="utf-8").read(),
                           path=target)
            print(json.dumps(result.as_dict(), indent=2))
            return 0 if result.ok else 1

        print(f"AUDIT  {target}")
        print("=" * 62)
        if report["errors"]:
            print(f"This does not compile ({len(report['errors'])} "
                  f"problem(s)). Do not run it.")
            for e in report["errors"][:5]:
                print(f"  line {e['line']}: [{e['code']}] {e['message']}")
            return 1

        # a project-local proof cache is never trusted (7.1.2): say so where
        # one is present, so a reader knows the proofs below were re-checked
        _tdir = os.path.dirname(os.path.abspath(target)) or "."
        if os.path.isdir(os.path.join(_tdir, CACHE_DIR)) or \
                os.path.isdir(CACHE_DIR):
            print(f"ignored: ./{CACHE_DIR}/  (a project-local proof cache is "
                  f"never trusted; proofs here were re-checked)")
            print()

        print("WHAT IT CAN TOUCH")
        if not outside:
            print("  nothing. This program cannot reach the console, the")
            print("  disk, the network, the clock, randomness or Python,")
            print("  and it cannot let a secret out.")
        else:
            for e in outside:
                print(f"  {e:<10} {_EFFECT_WORDS.get(e, e)}")
            print()
            print("  reached by:")
            for f in reaching:
                print(f"    {f['name']} ({', '.join(sorted(f['effects']))})")
        print()

        print("WHAT IT PROMISES")
        if not promising:
            print("  nothing. No function here carries a contract.")
        else:
            for f in proven:
                print(f"  [proven ] {f['name']}")
                for e in f["ensures"]:
                    print(f"              always: {e}")
            for f in runtime:
                print(f"  [runtime] {f['name']}")
                for e in f["ensures"]:
                    print(f"              claims: {e}")
            share = 100 * len(proven) / len(promising)
            print()
            print(f"  {len(proven)} of {len(promising)} proven before "
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
        budget = ",".join(outside)
        if budget:
            print(f"  velaris {target} --allow {budget}")
            print("  Anything it did not declare is refused while it runs.")
        else:
            print(f"  velaris {target} --allow ''")
            print("  It needs no permissions at all.")
        if "ffi" in outside:
            print()
            print("  NOTE: this program calls Python, which means it can")
            print("  do anything Python can. An effect budget does not")
            print("  contain that. Read the code before running it.")
        return 0

    if argv[:1] == ["clean"]:
        import shutil
        did = False
        d = _user_cache_dir()
        root = os.path.dirname(d) if d else None      # <cache>/velaris
        if root and os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)
            print(f"removed the proof cache at {root} - the next run "
                  f"proves everything again")
            did = True
        if os.path.isdir(CACHE_DIR):
            print(f"note: {CACHE_DIR}/ in this directory is ignored (since "
                  f"7.1.2 a project-local proof cache is never trusted); "
                  f"you may delete it")
            did = True
        if not did:
            print("nothing to clean")
        return 0
    if argv[:1] == ["build"]:
        return build_program(argv[1:])
    if argv[:1] == ["trace"]:
        if len(argv) < 2:
            print("usage: velaris trace program.vel", file=sys.stderr)
            return 1
        TRACE["on"] = True
        sys.argv = [sys.argv[0]] + argv[1:]      # run it normally
        return main()
    if argv[:1] == ["test"]:
        if len(argv) < 2:
            print("usage: velaris test program.vel", file=sys.stderr)
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
            errs: list = []
            check_effects(funcs, errs)
            check_types(funcs, records, errs)
            if not errs:
                check_proofs(funcs, records, errs)
            if errs:
                for e in errs:
                    print(e.human(target), file=sys.stderr)
                return 1
        except VelarisError as e:
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
            except VelarisError as e:
                print(f"  FAIL  {label}   [{e.code}] {e.message}")
            except FailSignal as e:
                print(f"  FAIL  {label}   failed: {e.reason}")
        print(f"\n{passed}/{len(tests)} passed")
        return 0 if passed == len(tests) else 1
    if argv[:1] == ["check"]:
        if len(argv) < 2:
            print("usage: velaris check program.vel", file=sys.stderr)
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
                    for e in rep_["errors"]:
                        print(f"{target}:{e['line']}: [{e['code']}] "
                              f"{e['message']}", file=sys.stderr)
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
                            for e in f["ensures"]:
                                print(f"      promises {e}",
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
            print("usage: velaris explain program.vel", file=sys.stderr)
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
                for e in r["errors"]:
                    worst = 1
                    print(f"    line {e['line']}: [{e['code']}] "
                          f"{e['message'][:70]}")
            return worst
        rep_ = inspect_source(target)
        if "--json" in argv:
            print(json.dumps(rep_, indent=2))
            return 0 if not rep_["errors"] else 1
        print(f"{rep_['file']}  -  velaris {rep_['version']}")
        print("=" * 62)
        if not rep_["proofs"]:
            print("note: z3-solver is not installed, so promises are "
                  "checked while running\n")
        entry = os.path.abspath(rep_["file"])
        mine, imported = [], {}
        for f in rep_["functions"]:
            if os.path.abspath(f["file"]) == entry:
                mine.append(f)
            else:
                imported.setdefault(f["file"], []).append(f)

        def show(f):
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
            for e in rep_["errors"]:
                print(f"  line {e['line']}: [{e['code']}] {e['message']}")
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
        print(f"Velaris {VERSION}")
        return 0
    if len(sys.argv) < 2:
        # the docstring carries no version of its own, so this cannot go
        # stale: until 4.4 it opened "Velaris v2.36", which is what a
        # reader of `velaris` with no arguments was told they were running
        print((__doc__ or "").replace("Velaris —", f"Velaris {VERSION} —",
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
    # args() is the program's arguments - never the flags this command
    # took for itself. Until 2.62 `--allow io` leaked in as two words.
    FLAGS = {"--json", "--no-native", "--time", "--check", "--no-cache"}
    VALUED = {"--allow", "--deny", "--timeout", "--max-memory-mb",
              "--max-read"}
    rest, skip = [], False
    for a in sys.argv[2:]:
        if skip:
            skip = False
        elif a in VALUED:
            skip = True
        elif a not in FLAGS:
            rest.append(a)
    PROGRAM_ARGS[:] = rest
    try:
        funcs, records = load_program(filename)
        errors: list[VelarisError] = []
        check_effects(funcs, errors)  # superpower 1: no hidden effects
        check_types(funcs, records, errors)  # superpower 2: no type surprises
        proven: set = set()
        if not errors:                # proofs assume well-formed code
            check_proofs(funcs, records, errors, proven,
                         use_cache="--no-cache" not in sys.argv,
                         source_path=filename)
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
            return 1
        native = ({} if "--no-native" in sys.argv
                  else compile_native(funcs, proven))
        import time as _t
        t0 = _t.perf_counter()
        interpret(funcs, native)
        if "--time" in sys.argv:
            ms = (_t.perf_counter() - t0) * 1000
            mode = "interpreted" if not native else "native+interpreted"
            print(f"[--time] ran in {ms:.1f} ms ({mode})", file=sys.stderr)
        return 0
    except VelarisError as e:
        print(e.machine(filename) if as_json else e.human(filename), file=sys.stderr)
        return 1




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

AUDIT_SCHEMA = "velaris.audit/1"     # the shape of audit().as_dict()


class Problem:
    """One thing wrong, in a form a tool can act on."""

    __slots__ = ("code", "message", "line", "file", "fixes")

    def __init__(self, code, message, line, file, fixes):
        self.code, self.message = code, message
        self.line, self.file, self.fixes = line, file, list(fixes or [])

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message,
                "line": self.line, "file": self.file, "fixes": self.fixes}

    def __repr__(self):
        return f"[{self.code}] line {self.line}: {self.message}"


class CheckResult:
    __slots__ = ("ok", "problems", "proven", "runtime_checked")

    def __init__(self, ok, problems, proven, runtime_checked):
        self.ok = ok
        self.problems = problems
        self.proven = proven                  # names proven before running
        self.runtime_checked = runtime_checked

    def as_dict(self) -> dict:
        return {"ok": self.ok,
                "problems": [p.as_dict() for p in self.problems],
                "proven": list(self.proven),
                "runtime_checked": list(self.runtime_checked)}


class AuditResult:
    """What a program can touch, promise and fail at - before running."""

    __slots__ = ("schema", "velaris_version", "ok", "problems", "effects",
                 "functions", "proven_share", "safe_command", "warnings",
                 "ffi_modules", "loops_unshown", "contract_coverage",
                 "fs_paths", "net_hosts", "ffi_any", "counts", "prover",
                 "secrets")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self) -> dict:
        out = {k: getattr(self, k) for k in self.__slots__}
        out["problems"] = [p.as_dict() if hasattr(p, "as_dict") else p
                           for p in (out.get("problems") or [])]
        return out


class RunResult:
    """What a run did. `effects_used` (3.4) maps each effect to how many
    builtin calls the budget let through - what the program actually
    performed, as the runtime saw it. It is {} when nothing ran and None
    when the run happened in a child process that could not report it
    (run() with a timeout or memory cap outside a pool, or a pool worker
    that was killed). What a granted ffi module does inside Python is
    not seen: it counts as ffi calls, nothing more."""

    __slots__ = ("ok", "output", "logs", "problems", "refused_effect",
                 "exit_code", "timed_out", "out_of_memory", "effects_used")

    def __init__(self, ok, output, logs, problems, refused_effect,
                 exit_code, timed_out=False, out_of_memory=False,
                 effects_used=None):
        self.ok, self.output, self.logs = ok, output, logs
        self.problems, self.refused_effect = problems, refused_effect
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.out_of_memory = out_of_memory
        self.effects_used = effects_used

    def as_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "logs": self.logs,
                "problems": [p.as_dict() for p in self.problems],
                "refused_effect": self.refused_effect,
                "exit_code": self.exit_code,
                "timed_out": self.timed_out,
                "out_of_memory": self.out_of_memory,
                "effects_used": self.effects_used}


def _as_problem(e, where) -> Problem:
    return Problem(getattr(e, "code", "E000"), getattr(e, "message", str(e)),
                   getattr(e, "line", 0), getattr(e, "file", None) or where,
                   getattr(e, "fixes", []))


def _source_to_file(source: str, path: str | None):
    """Velaris resolves imports against a file, so give the text one."""
    import tempfile
    if path is not None:
        return path, None
    tmp = tempfile.NamedTemporaryFile("w", suffix=".vel", delete=False,
                                      encoding="utf-8")
    tmp.write(source)
    tmp.close()
    return tmp.name, tmp.name


def _ffi_modules_named(path: str, source: str | None) -> set:
    """Top-level Python packages a program names in py* calls.

    Only literal module names can be read without running; a module
    built from text at runtime cannot, and the audit says so.
    """
    return _ffi_named(path, source)[0]


def _ffi_named(path: str, source: str | None) -> tuple:
    """(modules, any): the top-level packages named as literal text in the
    module argument of a py* call, and whether some such call names its
    module with a value built while running - the audit's `ffi_any`
    (4.0, velaris-spec Q4), without which a computed module name was
    invisible in velaris.audit/1."""
    try:
        funcs, _ = load_program(path, source)
    except Exception:
        return set(), False
    found: set = set()
    computed = []
    import dataclasses as _dc

    def visit(node):
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


def _fs_net_named(path: str, source: str | None) -> tuple:
    """(paths, hosts) a program names in literals, for scoped grants.

    paths: {"read": [...], "write": [...], "read_any": bool,
    "write_any": bool} - the flags say a call used a path built at
    runtime, which no literal can cover. hosts: {"hosts": [...],
    "any": bool} the same way. Like _ffi_modules_named, this reads
    literals only.
    """
    paths = {"read": set(), "write": set(), "read_any": False,
             "write_any": False}
    hosts = {"hosts": set(), "any": False}
    try:
        funcs, _ = load_program(path, source)
    except Exception:
        return paths, hosts
    import dataclasses as _dc
    host_of = _host_entry

    def visit(node):
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


def _secrets_named(path: str, source: str | None) -> dict | None:
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
    sources: set = set()
    out: list = []

    def visit(node, where: str, line: int):
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


def _safe_grants(effects, modules_named, paths, hosts) -> list:
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


def check(source: str, *, path: str | None = None,
          prove: bool = True) -> CheckResult:
    """Compile without running. Every problem, plus what was proven."""
    where, temp = _source_to_file(source, path)
    try:
        problems, proven, runtime = [], set(), []
        try:
            funcs, records = load_program(where, source if path else None)
            errors: list = []
            check_main(funcs, errors, running=False)
            check_effects(funcs, errors)
            if not errors:
                check_types(funcs, records, errors)
            if not errors and prove:
                check_proofs(funcs, records, errors, proven, use_cache=False)
            problems = [_as_problem(e, where) for e in errors]
            for f in funcs:
                if (f.requires or f.ensures) and f.name not in proven:
                    runtime.append(f.name)
        except VelarisError as e:
            problems = [_as_problem(e, where)]
        return CheckResult(not problems, problems, sorted(proven),
                           sorted(runtime))
    finally:
        if temp:
            os.unlink(temp)


def audit(source: str, *, path: str | None = None) -> AuditResult:
    """What this program can touch, promise and fail at.

    The same answer `velaris audit` prints, as data, with a schema name
    so a dashboard or an agent can rely on its shape.
    """
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
            prover=bool(compiled and report.get("proofs")),
            warnings=warnings)
    finally:
        if temp:
            os.unlink(temp)


def run(source: str, *, path: str | None = None,
        allow: set | None = None, deny: set | None = None,
        args: list | None = None, stdin: str = "",
        native: bool = True, timeout: float | None = None,
        max_memory_mb: int | None = None) -> RunResult:
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
    """
    if timeout is not None or max_memory_mb is not None:
        return _run_bounded(source, path=path, allow=allow, deny=deny,
                            args=args, stdin=stdin, native=native,
                            timeout=timeout, max_memory_mb=max_memory_mb)
    return _run_in_process(source, path=path,
                           budget=_budget_from(allow, deny),
                           args=args, stdin=stdin, native=native)


def _run_in_process(source, *, path, budget, args, stdin,
                    native) -> RunResult:
    """run() with the budget already parsed, in THIS process.

    The budget is installed, the program runs under it, and whatever
    budget was in place before is put back - so several audits and runs
    can share a process, and so a pool worker comes back to its own
    budget after every program it serves.
    """
    import io as _io
    import contextlib
    where, temp = _source_to_file(source, path)

    saved = Budget.snapshot()
    saved_args = list(PROGRAM_ARGS)
    saved_handles, saved_next = dict(PY_OBJECTS), PY_NEXT[0]
    out, err = _io.StringIO(), _io.StringIO()
    problems, refused, code = [], None, 0
    used: dict = {}
    try:
        budget.install()
        PROGRAM_ARGS[:] = list(args or [])
        result = check(source, path=path)
        if not result.ok:
            return RunResult(False, "", "", result.problems, None, 1,
                             effects_used={})
        funcs, records = load_program(where, source if path else None)
        errors: list = []
        proven: set = set()
        check_proofs(funcs, records, errors, proven, use_cache=False)
        compiled = compile_native(funcs, proven) if native else {}
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            old_stdin = sys.stdin
            sys.stdin = _io.StringIO(stdin)
            try:
                interpret(funcs, compiled)
            finally:
                sys.stdin = old_stdin
    except SystemExit as e:
        code = int(e.code or 0)
    except VelarisError as e:
        problems = [_as_problem(e, where)]
        refused = _refused_from(e.code, e.message)
        code = 1
    except FailSignal as e:
        problems = [Problem("E521", f"a failure escaped: {e.reason}", 0,
                            where, ["handle it with check"])]
        code = 1
    finally:
        used = dict(EFFECT_USES)           # this run's, before the old
        Budget.restore(saved)              # budget's come back
        PROGRAM_ARGS[:] = saved_args
        # handles a program opened and never closed are this program's,
        # not the next one's - the same reason the budget is put back
        PY_OBJECTS.clear()
        PY_OBJECTS.update(saved_handles)
        PY_NEXT[0] = saved_next
        if temp:
            os.unlink(temp)
    return RunResult(code == 0 and not problems, out.getvalue(),
                     err.getvalue(), problems, refused, code,
                     effects_used=used)


def _budget_from(allow, deny) -> "Budget":
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


def _refused_from(code: str, message: str):
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


def _cap_this_process(mb) -> bool:
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

    def __init__(self, max_memory_mb: int):
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

        k = ctypes.WinDLL("kernel32", use_last_error=True)
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
        nt = ctypes.WinDLL("ntdll", use_last_error=True)
        nt.NtResumeProcess.argtypes = [w.HANDLE]

        self._ctypes, self._k, self._nt = ctypes, k, nt
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
        info = EXTENDED_LIMITS()
        info.BasicLimitInformation.LimitFlags = (
            self.LIMIT_PROCESS_MEMORY | self.LIMIT_KILL_ON_JOB_CLOSE)
        info.ProcessMemoryLimit = int(max_memory_mb) * 1024 * 1024
        if not k.SetInformationJobObject(
                self.handle, self.EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            self.close()
            raise OSError(err, "SetInformationJobObject failed")

    def adopt(self, proc) -> None:
        """Put a suspended child in the job, then let it run."""
        if not self._k.AssignProcessToJobObject(self.handle,
                                                int(proc._handle)):
            raise OSError(self._ctypes.get_last_error(),
                          "AssignProcessToJobObject failed")
        self._nt.NtResumeProcess(int(proc._handle))

    def close(self) -> None:
        handle, self.handle = getattr(self, "handle", None), None
        if handle:
            try:
                self._k.CloseHandle(handle)
            except Exception:
                pass


def _spawn_capped(cmd: list, max_memory_mb, **popen_kw):
    """Start cmd under a memory cap. Returns (proc, job, how) - `job`
    must be closed once the child is finished with, and `how` is one of
    'RLIMIT_AS', 'job object' or 'not enforced'."""
    import subprocess
    if max_memory_mb is None:
        return subprocess.Popen(cmd, **popen_kw), None, "no cap asked for"
    if os.name != "nt":
        # the child caps itself from --max-memory-mb, already in cmd
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


def _run_bounded(source, *, path, allow, deny, args, stdin, native,
                 timeout, max_memory_mb) -> RunResult:
    """run() in a child process that can be killed."""
    import subprocess
    where, temp = _source_to_file(source, path)
    try:
        budget = _budget_from(allow, deny)
    except ValueError:
        if temp:
            os.unlink(temp)
        raise

    # compile first, in this process: a program that does not compile
    # never needs a child, and the problems come back the normal way
    result = check(source, path=path)
    if not result.ok:
        if temp:
            os.unlink(temp)
        return RunResult(False, "", "", result.problems, None, 1,
                         effects_used={})

    # the same budget, spelled out with absolute paths, so the child
    # parses to exactly what this process would have enforced
    cmd = [sys.executable, os.path.abspath(__file__), where,
           "--allow", budget.spec() or "''"]
    if not native:
        cmd.append("--no-native")
    if max_memory_mb is not None:
        # the child caps itself on POSIX; on Windows the job object
        # below does it, and this only records what was asked for
        cmd += ["--max-memory-mb", str(int(max_memory_mb))]
    cmd += list(args or [])

    timed_out = False
    out, err, code = "", "", 0
    proc, job, _how = _spawn_capped(
        cmd, max_memory_mb, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    try:
        try:
            raw_out, raw_err = proc.communicate(
                stdin.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            raw_out, raw_err = proc.communicate()
        out = raw_out.decode("utf-8", "replace")
        err = raw_err.decode("utf-8", "replace")
        code = 124 if timed_out else proc.returncode
    finally:
        if job is not None:
            job.close()
        if temp:
            os.unlink(temp)

    problems, refused = [], None
    out_of_memory = False
    if timed_out:
        problems.append(Problem(
            "E610", f"the program ran longer than {timeout} second(s) "
                    f"and was stopped", 0, where,
            ["give it more time, or fix the loop that never ends"]))
    elif code != 0:
        text = err.strip()
        m = re.search(r"error\[(E\d{3})\] (.+)", text)
        if m:
            problems.append(Problem(m.group(1), m.group(2).strip(), 0,
                                    where, []))
            refused = _refused_from(m.group(1), m.group(2))
        elif "MemoryError" in text or code in (-9, 137) or \
                "Cannot allocate" in text:
            out_of_memory = True
            problems.append(Problem(
                "E611", f"the program used more than {max_memory_mb} MB "
                        f"and was stopped", 0, where,
                ["give it more memory, or find what is growing"]))
        else:
            problems.append(Problem("E000", text.splitlines()[0][:200]
                                    if text else f"exit code {code}",
                                    0, where, []))
    ok = code == 0 and not problems
    return RunResult(ok, out, err if not problems else "", problems,
                     refused, code, timed_out, out_of_memory)


# ---------------------------------------------------------------------------
# 15. THE POOL — bounded runs without a new interpreter every time
#
#     A run with a timeout or a memory cap starts a Python interpreter,
#     which costs about a tenth of a second before a line of Velaris is
#     read. An agent platform calling run() thousands of times an hour
#     pays that every time. A Pool keeps workers alive and hands each
#     program to an idle one.
#
#     Speed is why it exists; isolation is why it can be used. Every
#     rule in Pool's docstring is asserted in check_pool.py, because a
#     fast sandbox that leaks state between programs is worse than a
#     slow one.
# ---------------------------------------------------------------------------

import atexit
import queue as _queue
import threading
import weakref

# Every module-level container a running program can reach. The rest of
# the module-level containers in this file - KEYWORDS, BUILTINS,
# FALLIBLE_BUILTINS, TOKEN_SPEC and so on - are constants nothing writes
# to. check_pool.py walks this file and fails if a new mutable one
# appears that is named in neither list.
MUTABLE_GLOBALS = ("PROGRAM_ARGS", "EFFECT_BUDGET", "FFI_MODULES",
                   "FS_GRANTS", "NET_GRANTS", "OP_LIMITS", "OP_COUNTS",
                   "EFFECT_USES", "PY_OBJECTS", "PY_NEXT", "TRACE",
                   "_NATIVE_KEEPALIVE")


def program_state_baseline() -> dict:
    """What this process looked like before it ran anyone's program."""
    return {"cwd": os.getcwd(), "env": dict(os.environ),
            "recursion": sys.getrecursionlimit()}


def reset_program_state(budget: "Budget | None" = None,
                        baseline: dict | None = None) -> None:
    """Put every piece of module-level mutable state back to how a
    fresh process would find it.

    A pool worker runs one program after another in one process, so
    anything a program leaves behind here is state the next program
    could see. Exhaustively, as of 3.1, that is:

        PROGRAM_ARGS        what args() answers
        EFFECT_BUDGET       the effects granted
        FFI_MODULES         the Python modules granted
        FS_GRANTS           the directions and paths granted
        NET_GRANTS          the hosts and ports granted
        OP_LIMITS           the @N caps
        OP_COUNTS           how many fs and net operations have run
        EFFECT_USES         which effects the program has used (3.4)
        PY_OBJECTS          handles from py_new, closed by the program
                            or not
        PY_NEXT             the number the next handle would get
        TRACE               the tracer's switch, depth and call count
        _NATIVE_KEEPALIVE   the JIT engines, and the text arena each
                            engine owns

    There is no proof cache in memory to clear. check_proofs keeps its
    cache on disk, in a per-user directory (7.1.2; never the program's own
    directory), and only when it is asked to (use_cache=True); the library
    and the pool never ask, so nothing about one program's proofs survives
    in this process to reach the next.

    With a baseline, three things that are the process's rather than
    this module's are put back too, because a program granted ffi can
    change all three: the working directory, the environment, and
    Python's recursion limit (which the interpreter raises so that its
    own depth limit is the one that fires).

    Passing no budget grants nothing, which is the right answer for a
    reset outside a pool: the budget must be chosen deliberately, never
    inherited from whatever ran last.
    """
    PROGRAM_ARGS[:] = []
    PY_OBJECTS.clear()
    PY_NEXT[0] = 1
    _NATIVE_KEEPALIVE.clear()
    TRACE.update({"on": False, "depth": 0, "calls": 0, "limit": 4000})
    (budget if budget is not None else Budget()).install()
    if baseline is None:
        return
    try:
        if os.getcwd() != baseline["cwd"]:
            os.chdir(baseline["cwd"])
    except OSError:
        pass
    if dict(os.environ) != baseline["env"]:
        os.environ.clear()
        os.environ.update(baseline["env"])
    if sys.getrecursionlimit() != baseline["recursion"]:
        try:
            sys.setrecursionlimit(baseline["recursion"])
        except (ValueError, RecursionError):
            pass


# ---- the wire between a pool and its workers ------------------------------
#      Four bytes of length, then one JSON object. Length-prefixed and
#      not line-delimited, because a program's output is inside the
#      object and can hold anything at all.

def _msg_write(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    stream.write(len(body).to_bytes(4, "little"))
    stream.write(body)
    stream.flush()


def _read_exactly(stream, n: int):
    parts = []
    while n > 0:
        try:
            chunk = stream.read(n)
        except (OSError, ValueError):
            return None
        if not chunk:
            return None                    # the other end went away
        parts.append(chunk)
        n -= len(chunk)
    return b"".join(parts)


def _msg_read(stream):
    """The next message, or None when the pipe closed or went wrong."""
    head = _read_exactly(stream, 4)
    if head is None:
        return None
    body = _read_exactly(stream, int.from_bytes(head, "little"))
    if body is None:
        return None
    try:
        answer = json.loads(body.decode("utf-8"))
    except ValueError:
        return None
    return answer if isinstance(answer, dict) else None


def pool_worker(argv: list) -> int:
    """One long-lived child behind velaris.Pool.

    It parses its budget once, from its own command line, installs it,
    and then serves one program at a time: read a request, run it,
    answer with exactly the dict run() returns. A request carries a
    program, its stdin and its arguments - never a budget. There is
    nowhere for a program to ask for more than the pool was made with.
    """
    spec = argv[argv.index("--allow") + 1] if "--allow" in argv else ""
    native = "--no-native" not in argv
    if "--max-memory-mb" in argv:
        # POSIX caps itself here; on Windows the parent put this process
        # in a job object before it was allowed to run at all
        _cap_this_process(argv[argv.index("--max-memory-mb") + 1])
    try:
        budget = Budget.parse(spec)
    except BudgetError as e:
        sys.stderr.write(f"velaris worker: {e}\n")
        return 2

    # The protocol gets private copies of fd 0 and fd 1, and the
    # program's own fd 0 and fd 1 are pointed at the null device.
    # Nothing a program writes - print, a hand-redirected stderr, or a
    # write straight at the file descriptor through ffi - can reach the
    # pipe the parent is parsing.
    requests = os.fdopen(os.dup(0), "rb")
    replies = os.fdopen(os.dup(1), "wb")
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.close(null)

    baseline = program_state_baseline()
    reset_program_state(budget, baseline)
    _msg_write(replies, {"ready": VERSION, "pid": os.getpid(),
                         "allow": budget.spec()})
    while True:
        request = _msg_read(requests)
        if request is None or request.get("stop"):
            return 0                       # the parent closed the pipe
        reset_program_state(budget, baseline)
        try:
            answer = _run_in_process(
                request.get("source") or "", path=request.get("path"),
                budget=budget, args=request.get("args") or [],
                stdin=request.get("stdin") or "",
                native=native).as_dict()
        except MemoryError:
            answer = {"out_of_memory": True}
        except Exception as e:             # a defect in the compiler, not
            answer = {"crashed": f"{type(e).__name__}: {e}"}   # in the run
        reset_program_state(budget, baseline)
        try:
            _msg_write(replies, answer)
        except OSError:
            return 0                       # the parent stopped listening


class _Worker:
    """One child process, and the pipe its pool talks to it over."""

    def __init__(self, cmd: list, max_memory_mb):
        import subprocess
        self.killed_by_timeout = False
        self.dead = False
        self._kill_lock = threading.Lock()
        self._noise: list = []
        self.proc, self.job, self.cap = _spawn_capped(
            cmd, max_memory_mb, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.pid = self.proc.pid
        self._drain = threading.Thread(target=self._read_stderr, daemon=True)
        self._drain.start()
        hello = _msg_read(self.proc.stdout)
        if hello is None or not hello.get("ready"):
            self.dispose()
            raise RuntimeError("a pool worker did not start: "
                               + (self.stderr() or "it said nothing"))
        self.allow = hello.get("allow") or ""

    def _read_stderr(self) -> None:
        try:
            for line in self.proc.stderr:
                self._noise.append(line.decode("utf-8", "replace"))
                del self._noise[:-40]      # the last 40 lines are plenty
        except Exception:
            pass

    def stderr(self) -> str:
        return "".join(self._noise).strip()

    def ask(self, request: dict, timeout):
        """Send one program and wait. None means the worker did not
        answer: killed by the deadline, or dead for another reason."""
        self.killed_by_timeout = False
        alarm = None
        if timeout is not None:
            alarm = threading.Timer(timeout, self._deadline)
            alarm.daemon = True
            alarm.start()
        try:
            try:
                _msg_write(self.proc.stdin, request)
            except (OSError, ValueError):
                return None
            return _msg_read(self.proc.stdout)
        finally:
            if alarm is not None:
                alarm.cancel()

    def _deadline(self) -> None:
        # the PARENT owns the deadline: a worker that has not answered
        # is killed, not asked to stop. A program that ignores its own
        # limits cannot ignore this one.
        self.killed_by_timeout = True
        self.kill()

    def kill(self) -> None:
        """Stop the child and reap it. Safe from any thread, and safe
        while another thread is still reading the child's answer - the
        pipes are closed by dispose(), once nobody is reading."""
        with self._kill_lock:
            if self.dead:
                return
            self.dead = True
        if self.job is not None:
            self.job.close()               # kills whatever is in the job
        try:
            self.proc.kill()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass

    def dispose(self) -> None:
        self.kill()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except Exception:
                pass
        try:
            self._drain.join(timeout=2)
        except Exception:
            pass


def _kill_workers(live: set, lock) -> None:
    """Every worker in `live`, stopped and forgotten. Used by close(),
    by the finalizer of a pool nobody closed, and at exit."""
    try:
        with lock:
            workers = list(live)
            live.clear()
    except Exception:                      # interpreter shutdown
        workers = list(live)
        live.clear()
    for worker in workers:
        try:
            worker.dispose()
        except Exception:
            pass


_POOLS: "weakref.WeakSet" = weakref.WeakSet()


@atexit.register
def _close_pools_at_exit() -> None:
    for pool in list(_POOLS):
        try:
            pool.close()
        except Exception:
            pass


class Pool:
    """Long-lived workers for bounded runs, all under ONE budget.

        pool = velaris.Pool(size=4, allow={"io"}, timeout=30,
                            max_memory_mb=512)
        result = pool.run(source)          # the RunResult run() returns
        pool.close()                       # also a context manager

    A bounded run costs an interpreter's startup - about a tenth of a
    second - before a line of Velaris is read. A pool pays that once
    per worker instead of once per program.

    The isolation rules, which matter more than the speed:

    * THE BUDGET IS THE POOL'S, NOT THE PROGRAM'S. It is parsed once,
      here, and installed by each worker at startup; `run` on a pool
      takes no allow argument. allow=None is `io` from 5.0, as it is
      everywhere else, where it used to be all seven effects. A caller who needs a different budget
      makes a different pool. Nothing a program does can widen it: the
      budget is re-asserted from this object before every program,
      which also puts the per-run operation counts (@N) back to zero,
      so one program cannot spend another's allowance.

    * A WORKER IS USED ONCE UNLESS THE RUN WAS CLEAN. Anything other
      than ok - a refused effect, a failure that escaped, a program
      that did not compile, the timeout, the memory cap - retires the
      worker: it is killed and a fresh one takes its place. Only a run
      that finished cleanly hands its worker back. That costs a
      restart on every rejected program, and it is the rule that makes
      the rest of this list checkable.

    * A REUSED WORKER STARTS EMPTY. Before every program the child
      resets every piece of module-level mutable state there is: the
      arguments, the Python handles, the native compiler's engines and
      the text arena they own, the tracer, the budget and its counts -
      and the working directory, the environment and the recursion
      limit, which a program granted ffi can change.
      `reset_program_state` lists all of it.

    * THE PARENT OWNS THE DEADLINE. A worker that has not answered
      within `timeout` is killed by this process; the call returns
      E610 and a replacement is started. The memory cap is set in the
      child at startup, the same way a bounded `run` sets it.

    * CLOSING KILLS EVERY WORKER, including one still running a
      program. A pool collected without close() is closed by its
      finalizer; a pool that outlives the interpreter is closed at
      exit; and a worker whose pipe closes ends by itself, so a parent
      that dies without doing either still leaves nothing behind.

    `run` is safe to call from several threads: each call takes an idle
    worker and blocks while none is free.

    What a pool does NOT change: the effect budget is the same guard it
    is everywhere else in Velaris, and the same things sit outside it -
    a granted ffi module can do whatever that module can do, in a
    worker as anywhere. THREAT_MODEL.md is the long form.
    """

    _CLOSED = object()

    def __init__(self, size: int = 4, *, allow: set | None = None,
                 deny: set | None = None, timeout: float | None = None,
                 max_memory_mb: int | None = None, native: bool = True):
        if int(size) < 1:
            raise ValueError("a pool needs at least one worker")
        self.size = int(size)
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.native = native
        self._budget = _budget_from(allow, deny)   # a bad grant fails here,
        self.allow = self._budget.spec()           # before any worker starts
        self._free: "_queue.Queue" = _queue.Queue()
        for _ in range(self.size):
            self._free.put(None)           # a worker starts on first demand
        self._live: set = set()
        self._lock = threading.Lock()
        self._closed = False
        self.started = 0                   # how many workers ever started
        _POOLS.add(self)
        self._finalizer = weakref.finalize(self, _kill_workers,
                                           self._live, self._lock)

    # ---- using it ----------------------------------------------------
    def run(self, source: str, *, stdin: str = "", args: list | None = None,
            path: str | None = None) -> RunResult:
        """Run one program on this pool, under the pool's budget.

        The same RunResult `velaris.run` returns, including timed_out
        and out_of_memory.
        """
        if self._closed:
            raise RuntimeError("this pool is closed")
        slot = self._free.get()
        if slot is self._CLOSED:
            self._free.put(slot)           # leave it for the next waiter
            raise RuntimeError("this pool is closed")
        worker, keep = slot, False
        try:
            if self._closed:
                raise RuntimeError("this pool is closed")
            if worker is not None and worker.proc.poll() is not None:
                self._forget(worker)       # it died while it was idle
                worker = None
            if worker is None:
                worker = self._start()
            result = self._ask(worker, source, stdin, args, path)
            keep = result.ok
            return result
        finally:
            if worker is not None and not keep:
                try:
                    self._forget(worker)   # used once
                finally:
                    worker = None          # the slot comes back either
            self._free.put(worker)         # way, or the pool shrinks

    def close(self) -> None:
        """Kill every worker, including one still running a program."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._free.put(self._CLOSED)       # wake anyone waiting
        _kill_workers(self._live, self._lock)
        self._finalizer.detach()

    def __enter__(self) -> "Pool":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        return self._closed

    def worker_pids(self) -> list:
        """The process ids of the workers alive right now."""
        with self._lock:
            return sorted(w.pid for w in self._live)

    # ---- the machinery -----------------------------------------------
    def _start(self) -> "_Worker":
        cmd = [sys.executable, os.path.abspath(__file__), "--pool-worker",
               "--allow", self._budget.spec()]
        if not self.native:
            cmd.append("--no-native")
        if self.max_memory_mb is not None:
            cmd += ["--max-memory-mb", str(int(self.max_memory_mb))]
        worker = _Worker(cmd, self.max_memory_mb)
        with self._lock:
            # close() may have run between the check in run() and here.
            # A worker added after close() drained the set would outlive
            # the pool, which is the one thing close() promises it will
            # not leave behind.
            too_late = self._closed
            if not too_late:
                self._live.add(worker)
                self.started += 1
        if too_late:
            worker.dispose()
            raise RuntimeError("this pool is closed")
        return worker

    def _forget(self, worker) -> None:
        with self._lock:
            self._live.discard(worker)
        worker.dispose()

    def _ask(self, worker, source, stdin, args, path) -> RunResult:
        answer = worker.ask({"source": source, "stdin": stdin or "",
                             "args": list(args or []), "path": path},
                            self.timeout)
        if answer is not None and "ok" in answer:
            return RunResult(
                bool(answer.get("ok")), answer.get("output") or "",
                answer.get("logs") or "",
                [Problem(p.get("code"), p.get("message"), p.get("line"),
                         p.get("file"), p.get("fixes") or [])
                 for p in answer.get("problems") or []],
                answer.get("refused_effect"), answer.get("exit_code") or 0,
                bool(answer.get("timed_out")),
                bool(answer.get("out_of_memory")),
                answer.get("effects_used"))
        return self._no_answer(worker, answer, path)

    def _no_answer(self, worker, answer, path) -> RunResult:
        """The worker handed back no run. Say which limit or which
        fault it was, in the shape run() would have used."""
        where = path or "<source>"
        if worker.killed_by_timeout:
            return RunResult(False, "", "", [Problem(
                "E610", f"the program ran longer than {self.timeout} "
                        f"second(s) and was stopped", 0, where,
                ["give it more time, or fix the loop that never ends"])],
                None, 124, True, False)
        noise = worker.stderr()
        starved = bool((answer or {}).get("out_of_memory")) or \
            "MemoryError" in noise or "Cannot allocate" in noise
        if starved and self.max_memory_mb is not None:
            return RunResult(False, "", "", [Problem(
                "E611", f"the program used more than {self.max_memory_mb} "
                        f"MB and was stopped", 0, where,
                ["give it more memory, or find what is growing"])],
                None, 1, False, True)
        detail = (answer or {}).get("crashed") or (
            noise.splitlines()[-1][:200] if noise
            else "the worker stopped without answering")
        return RunResult(False, "", "", [Problem("E000", detail, 0, where,
                                                 [])], None, 1)


class PoolRegistry:
    """One pool per distinct budget, made the first time it is asked for.

    A server takes a budget per request, so it cannot make its pools up
    front. This makes one the first time a budget is seen and keeps it
    for the next request that names the same budget - the same grants,
    timeout and memory cap. Budgets that differ never share a pool,
    because a pool's budget is the thing that makes its workers safe to
    reuse.

    At most `keep` pools are held; the least recently used beyond that
    is closed, so a caller who varies the budget on every request
    cannot make a server hold processes without end.

        pools = velaris.PoolRegistry()
        result = pools.run(source, allow={"io"}, timeout=30,
                           max_memory_mb=512)
        pools.close()
    """

    def __init__(self, size: int = 4, keep: int = 8):
        self.size, self.keep = int(size), max(1, int(keep))
        self._pools: dict = {}             # key -> Pool, least used first
        self._lock = threading.Lock()

    def pool(self, *, allow=None, deny=None, timeout=None,
             max_memory_mb=None, native: bool = True) -> "Pool":
        # spec() rather than the caller's words: two spellings of one
        # budget are one budget, and a bad grant fails here as it would
        # in run(), before any worker starts
        key = (_budget_from(allow, deny).spec(), timeout, max_memory_mb,
               bool(native))
        stale = []
        with self._lock:
            found = self._pools.pop(key, None)
            if found is None or found.closed:
                found = Pool(self.size, allow=allow, deny=deny,
                             timeout=timeout, max_memory_mb=max_memory_mb,
                             native=native)
            self._pools[key] = found       # most recently used, last
            while len(self._pools) > self.keep:
                stale.append(self._pools.pop(next(iter(self._pools))))
        for old in stale:
            old.close()
        return found

    def run(self, source: str, *, allow=None, deny=None, timeout=None,
            max_memory_mb=None, native: bool = True, stdin: str = "",
            args: list | None = None, path: str | None = None) -> RunResult:
        return self.pool(allow=allow, deny=deny, timeout=timeout,
                         max_memory_mb=max_memory_mb, native=native).run(
            source, stdin=stdin, args=args, path=path)

    def close(self) -> None:
        with self._lock:
            pools, self._pools = list(self._pools.values()), {}
        for pool in pools:
            pool.close()

    def __enter__(self) -> "PoolRegistry":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


# ---------------------------------------------------------------------------
# 16. FINDINGS AS SARIF, AND WHAT THE DOORS RECORD
#
#     `check --sarif`, `proofs --sarif` and `audit --sarif` write SARIF
#     2.1.0, which GitHub code scanning, SonarQube and Azure DevOps read
#     without a plugin. The rules are the error table plus the findings
#     that are not errors, and nothing is written that SARIF cannot hold
#     as Velaris means it.
#
#     The HTTP door and the MCP server each write one JSON line per call
#     (InvocationLog), and the MCP server's tools can be held against a
#     manifest the release workflow signs (mcp-manifest, mcp-verify).
#     The verifier lives here and not in velaris_mcp.py, so a changed
#     server file cannot also change the code that checks it.
# ---------------------------------------------------------------------------

SARIF_SCHEMA_URI = ("https://docs.oasis-open.org/sarif/sarif/v2.1.0/"
                    "errata01/os/schemas/sarif-schema-2.1.0.json")
REPOSITORY = "https://github.com/gowrishankar-infra/velaris-lang"
ERRORS_PAGE = "https://gowrishankar-infra.github.io/velaris-lang/errors.html"

_EFFECT_WORDS = {"io": "the console", "env": "environment variables",
                 "fs": "files", "net": "the network", "clock": "the time",
                 "rand": "randomness",
                 "ffi": "Python, and so anything Python can do",
                 "declassify": "turning a Secret into an ordinary value, "
                               "which anything may then emit"}

# The findings that are not errors, as (rule id, level, meaning). The
# E-codes come from ERROR_TABLE and are all errors: each one stops a
# program from compiling or from running. An unproven promise is a
# warning; a function that promises nothing about its data, a loop not
# shown to end and a capability are notes.
SARIF_FINDINGS = (
    ("unproven-promise", "warning",
     "a requires or ensures that is checked while the program runs, not "
     "proven before it runs"),
    ("contract-coverage", "note",
     "a function that takes or returns data and promises nothing about "
     "it"),
    ("loop-not-shown-to-end", "note",
     "a loop the termination rule cannot show to end; check --strict "
     "refuses it as E612"),
) + tuple((f"uses-{e}", "note",
           f"a function that may perform {e}: {_EFFECT_WORDS[e]}")
          for e in ALL_EFFECTS) + (
    ("capability-widened", "error",
     "code that needs a grant velaris.capabilities does not give: an "
     "effect, a Python module, a path outside the recorded ones, a host, "
     "a scoped grant made unscoped, or more fs or net operations in a run "
     "than recorded (capabilities check)"),
    ("capability-effect-gained", "error",
     "a function velaris.capabilities records now declares an effect it "
     "did not declare there (capabilities check)"),
    ("capability-narrowed", "note",
     "velaris.capabilities gives more than the code needs now; "
     "capabilities init --force records the narrower surface"),
    ("dependency-capability-widened", "error",
     "an upgraded Velaris dependency needs a grant its previous version "
     "did not: an effect, a Python module, a path, a host, or more fs or "
     "net operations in a run (deps-diff)"),
    ("dependency-effect-gained", "error",
     "a function of an upgraded Velaris dependency declares an effect it "
     "did not declare in the previous version (deps-diff)"),
    ("dependency-install-script", "error",
     "an upgraded dependency runs an install-time script its previous "
     "version did not, or a different one; what the script does is not "
     "derived (deps-diff)"),
    ("dependency-surface-unknown", "note",
     "an upgraded dependency holds code other than Velaris, or could not "
     "be read, so what it can do was not derived; unknown is not safe "
     "(deps-diff)"),
    ("dependency-added", "note",
     "a dependency the upgraded version declares that the previous one "
     "did not; its own surface was not examined (deps-diff)"),
    ("dependency-narrowed", "note",
     "an upgraded Velaris dependency needs less than its previous version "
     "did (deps-diff)"),
)


def sarif_rules() -> list:
    """Every rule a Velaris SARIF log can cite: one per entry of the
    error table, then the findings that are not errors. The help URI of
    each is its row on the published errors page."""
    rules = [{"id": code, "shortDescription": {"text": text},
              "helpUri": f"{ERRORS_PAGE}#{code}",
              "defaultConfiguration": {"level": "error"}}
             for code, text in sorted(ERROR_TABLE.items())]
    rules += [{"id": rid, "shortDescription": {"text": text},
               "helpUri": f"{ERRORS_PAGE}#{rid}",
               "defaultConfiguration": {"level": level}}
              for rid, level, text in SARIF_FINDINGS]
    return rules


class _SarifRun:
    """One SARIF run being filled in: results, and the rules they cite.

    What is deliberately not written: a Velaris fix is a sentence, and
    a SARIF `fix` must carry the exact bytes to change (artifactChanges
    is required), so the suggestions go in each result's property bag as
    `fixes` rather than as SARIF fixes with an edit made up to fill the
    slot. Findings with no place in a file (a proven share, the audit's
    safe_command) go in the run's property bag, not in results."""

    def __init__(self, command: str):
        self.command = command
        self.rules = sarif_rules()
        self.index = {r["id"]: i for i, r in enumerate(self.rules)}
        self.results: list = []
        self.notes: list = []
        self.properties: dict = {"prover": bool(HAVE_Z3)}
        self.root = os.getcwd()
        self.base_ids: dict = {}      # more originalUriBaseIds (deps-diff)

    def add(self, rule: str, message, path, line, level=None,
            fixes=None) -> None:
        if rule not in self.index:          # cannot happen while the
            self.index[rule] = len(self.rules)   # table is complete;
            self.rules.append({                  # check_library says so
                "id": rule, "shortDescription": {
                    "text": f"{rule}, which is not in the error table"},
                "defaultConfiguration": {"level": "error"}})
        rule_level = self.rules[self.index[rule]]["defaultConfiguration"]
        result = {"ruleId": rule, "ruleIndex": self.index[rule],
                  "level": level or rule_level["level"],
                  "message": {"text": str(message)},
                  "locations": [self._location(path, line)]}
        if fixes:
            result["properties"] = {"fixes": [str(f) for f in fixes]}
        self.results.append(result)

    def note(self, text: str) -> None:
        """Something that kept the tool from doing what was asked."""
        self.notes.append({"level": "error", "message": {"text": text}})

    def _location(self, path, line) -> dict:
        # a dict is an artifactLocation already: a file inside a package
        # deps-diff read, which is not a file of the checked tree
        where: dict = {"artifactLocation": dict(path) if isinstance(path, dict)
                       else self._artifact(str(path))}
        if isinstance(line, int) and not isinstance(line, bool) \
                and line >= 1:
            where["region"] = {"startLine": line}
        return {"physicalLocation": where}

    def _artifact(self, path: str) -> dict:
        import pathlib
        import urllib.parse
        full = os.path.abspath(path)
        try:
            rel = os.path.relpath(full, self.root)
        except ValueError:                  # another drive, on Windows
            rel = None
        if rel is not None and rel.split(os.sep)[0] != "..":
            return {"uri": urllib.parse.quote(rel.replace(os.sep, "/")),
                    "uriBaseId": "%SRCROOT%"}
        return {"uri": pathlib.Path(full).as_uri()}

    def log(self) -> dict:
        import pathlib
        invocation: dict = {"executionSuccessful": not self.notes}
        if self.notes:
            invocation["toolConfigurationNotifications"] = self.notes
        root = pathlib.Path(self.root).as_uri().rstrip("/") + "/"
        results = sorted(self.results, key=lambda r: (
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            r["locations"][0]["physicalLocation"].get("region", {})
            .get("startLine", 0), r["ruleId"], r["message"]["text"]))
        return {"$schema": SARIF_SCHEMA_URI, "version": "2.1.0",
                "runs": [{
                    "tool": {"driver": {
                        "name": "Velaris", "version": VERSION,
                        "semanticVersion": VERSION,
                        "informationUri": REPOSITORY,
                        "rules": self.rules}},
                    "automationDetails": {"id": f"velaris/{self.command}/"},
                    "originalUriBaseIds": {"%SRCROOT%": {"uri": root},
                                           **self.base_ids},
                    "invocations": [invocation],
                    "results": results,
                    "properties": self.properties}]}


def _own_functions(report: dict, path: str) -> list:
    here = os.path.abspath(path)
    return [f for f in report["functions"]
            if os.path.abspath(f["file"]) == here]


def _sarif_errors(run: "_SarifRun", report: dict, path: str) -> None:
    for e in report["errors"]:
        run.add(e.get("code") or "E000", e.get("message") or "",
                e.get("file") or path, e.get("line"), fixes=e.get("fixes"))


def _sarif_unproven(run: "_SarifRun", own: list, prover: bool,
                    level=None) -> list:
    """A result for every promise-carrying function not proven; returns
    those functions."""
    unproven = [f for f in own if (f["requires"] or f["ensures"])
                and f["status"] != "proven"]
    for f in unproven:
        said = "; ".join([f"requires {r}" for r in f["requires"]]
                         + [f"ensures {e}" for e in f["ensures"]])
        why = ("" if prover else
               " (the prover, z3-solver, is not installed)")
        if f.get("proof_timeout"):      # abandoned, not settled
            why = (" (the proof ran out of time and was abandoned - "
                   "nothing was proven and nothing was refuted)")
        run.add("unproven-promise",
                f"'{f['name']}': {said} - not proven before running; "
                f"checked while the program runs{why}",
                f["file"], f["line"], level=level)
    return unproven


def _sarif_coverage(run: "_SarifRun", own: list, report: dict) -> None:
    by_name = {f["name"]: f for f in own}
    for name in contract_coverage(own, report.get("records", [])):
        f = by_name[name]
        run.add("contract-coverage",
                f"'{name}' takes or returns data and promises nothing "
                f"about it", f["file"], f["line"])


def _unshown_loops(own: list, report: dict, path: str) -> list:
    """(function name, loop, file) for every loop not shown to end."""
    here = os.path.abspath(path)
    found = [(f["name"], lp, f["file"]) for f in own
             for lp in f.get("loops", []) if lp["verdict"] == "unshown"]
    found += [("an inline function", lp, lp["file"])
              for lp in report.get("inline_loops", [])
              if lp["verdict"] == "unshown"
              and os.path.abspath(lp["file"]) == here]
    return found


def sarif_check(targets: list, strict: bool = False) -> tuple:
    """`velaris check --sarif`: (the SARIF log, the exit code the plain
    check would give). Errors are errors; a promise left to runtime is a
    warning, and an error under --strict, as is a loop not shown to end
    (E612); a function promising nothing about its data is a note."""
    run = _SarifRun("check")
    bad = 0
    for target in targets:
        report = inspect_source(target)
        if report["errors"]:
            bad += 1
            _sarif_errors(run, report, target)
            continue
        own = _own_functions(report, target)
        if strict and not report["proofs"]:
            bad += 1
            run.note(f"{target}: --strict needs the prover "
                     f"(pip install z3-solver)")
            continue
        unproven = _sarif_unproven(run, own, report["proofs"],
                                   "error" if strict else None)
        loops = _unshown_loops(own, report, target) if strict else []
        for _name, lp, file in loops:
            run.add("E612", "this loop may never end - --strict needs a "
                            "counter that moves toward the limit",
                    file, lp["line"], fixes=[lp["why"]])
        if strict and (unproven or loops):
            bad += 1
        _sarif_coverage(run, own, report)
    return run.log(), (1 if bad else 0)


def sarif_proofs(reports: dict, totals: dict, share: float,
                 minimum) -> dict:
    """`velaris proofs --sarif`: what did not compile, and every promise
    left to runtime; the totals and the proven share in the run's
    property bag."""
    run = _SarifRun("proofs")
    for path, report in reports.items():
        if report["errors"]:
            _sarif_errors(run, report, path)
            continue
        _sarif_unproven(run, _own_functions(report, path),
                        report["proofs"])
    run.properties.update({"totals": totals, "proven_share": round(share, 1)})
    if minimum is not None:
        run.properties["min_proven"] = minimum
        run.properties["below_min"] = share < minimum
    return run.log()


def sarif_audit(files: list) -> dict:
    """`velaris audit --sarif`: the audit of each file as findings - what
    each function may perform, promises left to runtime, loops not shown
    to end, functions promising nothing about their data - and the
    velaris.audit/1 document of each file, unchanged, in the run's
    property bag for what has no line (safe_command, proven_share)."""
    run = _SarifRun("audit")
    audits = []
    for path in files:
        report = inspect_source(path)
        with open(path, encoding="utf-8") as fh:
            audits.append(audit(fh.read(), path=path).as_dict())
        if report["errors"]:
            _sarif_errors(run, report, path)
            continue
        own = _own_functions(report, path)
        for f in own:
            for e in f["effects"]:
                if e in _EFFECT_WORDS:
                    run.add(f"uses-{e}", f"'{f['name']}' may perform {e} "
                                         f"({_EFFECT_WORDS[e]})",
                            f["file"], f["line"])
        _sarif_unproven(run, own, report["proofs"])
        for name, lp, file in _unshown_loops(own, report, path):
            who = name if name.startswith("an ") else f"'{name}'"
            run.add("loop-not-shown-to-end",
                    f"a loop in {who} is not shown to end: {lp['why']}",
                    file, lp["line"])
        _sarif_coverage(run, own, report)
    run.properties["audits"] = audits
    return run.log()


def print_sarif_summary(log: dict) -> None:
    """The findings in a SARIF log, one line each on stderr, so a CI log
    still says what was found while stdout carries the SARIF."""
    import urllib.parse
    for r in log["runs"][0]["results"]:
        where = r["locations"][0]["physicalLocation"]
        uri = urllib.parse.unquote(where["artifactLocation"]["uri"])
        line = where.get("region", {}).get("startLine")
        at = f"{uri}:{line}" if line else uri
        print(f"{at}: {r['level']} [{r['ruleId']}] {r['message']['text']}",
              file=sys.stderr)
    for n in log["runs"][0]["invocations"][0].get(
            "toolConfigurationNotifications", []):
        print(n["message"]["text"], file=sys.stderr)


def run_outcome(result: "RunResult") -> str:
    """One word for how a run ended, as the doors log it."""
    if result.timed_out:
        return "timeout"
    if result.out_of_memory:
        return "out_of_memory"
    if result.refused_effect:
        return "refused"
    return "ok" if result.ok else "failed"


def run_refusals(result: "RunResult") -> list:
    """The budget's refusal of a run, as the doors log it, or []."""
    if not result.refused_effect:
        return []
    code = next((p.code for p in result.problems
                 if p.code in ("E310", "E311", "E313", "E314", "E315")),
                None)
    return [{"by": "budget", "code": code, "what": result.refused_effect}]


INVOCATION_SCHEMA = "velaris.invocation/1"


class InvocationLog:
    """One JSON line per call through a door - the HTTP door or the MCP
    server - on stderr, or appended to a file.

    A full line holds when the call arrived (UTC), the door, the tool or
    endpoint, the outcome, how long it took, the budget the program ran
    under, the effects it performed (RunResult.effects_used), what was
    refused and by what, the caller's address (HTTP), and the sha256 of
    the source. Never the source itself, the program's output, its
    stdin or arguments, a request header, or the door's token - and any
    secret handed to `redact` is replaced by [redacted] should it ever
    be part of a line. `detail="minimal"` keeps when, the door, what was
    called, the outcome and the duration. Nothing turns the log off.
    """

    DETAILS = ("full", "minimal")

    def __init__(self, path: str | None = None, detail: str = "full",
                 redact=()):
        import threading as _threading
        if detail not in self.DETAILS:
            raise ValueError("the invocation log is 'full' or 'minimal'; "
                             "it cannot be turned off")
        self.detail = detail
        self.path = path
        self._redact = [s for s in redact if s]
        self._lock = _threading.Lock()
        # opened now, so a path that cannot be written stops the door
        # before it answers anyone
        self._file = open(path, "a", encoding="utf-8") if path else None

    @staticmethod
    def started() -> tuple:
        import datetime
        import time as _t
        return datetime.datetime.now(datetime.timezone.utc), _t.monotonic()

    def record(self, started: tuple, *, door: str, outcome: str,
               tool: str | None = None, endpoint: str | None = None,
               client: str | None = None, budget=None, effects=None,
               refusals=(), source=None) -> dict:
        import hashlib
        import time as _t
        when, t0 = started
        line: dict = {"schema": INVOCATION_SCHEMA,
                      "ts": when.isoformat(timespec="milliseconds")
                      .replace("+00:00", "Z"),
                      "door": door}
        if tool is not None:
            line["tool"] = tool
        if endpoint is not None:
            line["endpoint"] = endpoint
        line["outcome"] = outcome
        line["duration_ms"] = round((_t.monotonic() - t0) * 1000, 1)
        if self.detail == "full":
            if client is not None:
                line["client"] = client
            line["budget"] = budget
            line["effects"] = effects
            line["refusals"] = list(refusals)
            line["source_sha256"] = (
                hashlib.sha256(source.encode("utf-8", "surrogatepass"))
                .hexdigest() if isinstance(source, str) else None)
        text = json.dumps(line)
        for secret in self._redact:
            for form in (secret, json.dumps(secret)[1:-1]):
                text = text.replace(form, "[redacted]")
        with self._lock:
            try:
                out = self._file or sys.stderr
                out.write(text + "\n")
                out.flush()
            except (OSError, ValueError):
                # the file failed; the line goes to stderr rather than
                # nowhere, since a door that cannot log still logs
                sys.stderr.write(text + "\n")
                sys.stderr.flush()
        return line

    def close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass


# ---- the MCP server's tools, hashed and signed ------------------------------

MCP_TOOLS_SCHEMA = "velaris.mcp-tools/1"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
RELEASE_IDENTITY = REPOSITORY + "/.github/workflows/release.yml@refs/tags/v{version}"
# From 7.2.0 no pushed tag starts a release: release.yml runs on main once
# the tests pass there (a workflow_run), tags the commit itself and signs in
# that same run - so a release is signed as main, not as its tag.
# RELEASING.md and SECURITY.md.
RELEASE_IDENTITY_MAIN = REPOSITORY + "/.github/workflows/release.yml@refs/heads/main"
RELEASED_FROM_MAIN = (7, 2, 0)


def release_identity(version) -> str:
    """The sigstore identity the release workflow signed `version` with:
    its tag up to 7.1.2, main from 7.2.0."""
    try:
        parts = [int(p) for p in str(version).split(".")]
    except ValueError:
        return RELEASE_IDENTITY.format(version=version)
    if len(parts) in (2, 3) and tuple(parts + [0])[:3] >= RELEASED_FROM_MAIN:
        return RELEASE_IDENTITY_MAIN
    return RELEASE_IDENTITY.format(version=version)


def _canonical_json(value) -> bytes:
    """Keys sorted, no whitespace between tokens, text as UTF-8 rather
    than escaped: the RFC 8785 form of the objects, arrays, strings,
    integers, booleans and nulls a tool's input schema holds."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode(
                          "utf-8", "surrogatepass")


def mcp_tool_hashes(tool: dict) -> dict:
    """A tool's name, the sha256 of its description (the UTF-8 bytes of
    the text exactly as the server sends it) and of its input schema
    (_canonical_json)."""
    import hashlib
    description = tool.get("description")
    if not isinstance(description, str):
        description = ""
    try:
        schema = hashlib.sha256(_canonical_json(
            tool.get("inputSchema"))).hexdigest()
    except (TypeError, ValueError):         # NaN, or something not JSON
        schema = "cannot be hashed"
    return {"name": tool.get("name"),
            "description_sha256": hashlib.sha256(description.encode(
                "utf-8", "surrogatepass")).hexdigest(),
            "input_schema_sha256": schema}


def mcp_tool_manifest(server_info: dict, tools: list) -> dict:
    """velaris.mcp-tools/1: every tool a server offers, hashed."""
    return {"schema": MCP_TOOLS_SCHEMA,
            "server": {"name": server_info.get("name"),
                       "version": server_info.get("version")},
            "hash": "sha256",
            "tools": sorted((mcp_tool_hashes(t) for t in tools),
                            key=lambda t: str(t["name"]))}


def mcp_list_tools(command: list, timeout: float = 120) -> tuple:
    """Start an MCP server over stdio, as a client would, and ask it for
    its tools: (serverInfo, tools). RuntimeError says what went wrong."""
    import queue as _q
    import subprocess
    import threading as _threading
    import time as _t
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except OSError as e:
        raise RuntimeError(f"cannot start the server: {e.strerror or e}")
    lines: "_q.Queue" = _q.Queue()
    noise: list = []

    def pump():
        for raw in proc.stdout:
            lines.put(raw)
        lines.put(None)

    def drain():
        for raw in proc.stderr:
            noise.append(raw.decode("utf-8", "replace").strip())
            del noise[:-20]

    _threading.Thread(target=pump, daemon=True).start()
    _threading.Thread(target=drain, daemon=True).start()
    deadline = _t.monotonic() + timeout

    def send(message: dict) -> None:
        proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def answer_to(msg_id: int) -> dict:
        while True:
            left = deadline - _t.monotonic()
            try:
                raw = lines.get(timeout=max(left, 0.01))
            except _q.Empty:
                raise RuntimeError(f"the server did not answer within "
                                   f"{timeout:g} s")
            if raw is None:
                said = noise[-1] if noise else "it said nothing"
                raise RuntimeError(f"the server stopped: {said}")
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == msg_id:
                if "error" in message:
                    raise RuntimeError(f"the server answered with an "
                                       f"error: {message['error']}")
                got = message.get("result")
                return got if isinstance(got, dict) else {}

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "velaris mcp-verify",
                                        "version": VERSION}}})
        info = answer_to(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools: list = []
        cursor, msg_id = None, 2
        while msg_id < 100:                 # a server paging forever
            send({"jsonrpc": "2.0", "id": msg_id, "method": "tools/list",
                  "params": {"cursor": cursor} if cursor else {}})
            page = answer_to(msg_id)
            tools += [t for t in page.get("tools") or []
                      if isinstance(t, dict)]
            cursor = page.get("nextCursor")
            msg_id += 1
            if not cursor:
                break
        server = info.get("serverInfo")
        return (server if isinstance(server, dict) else {}), tools
    except OSError as e:
        raise RuntimeError(f"the server's pipe closed: {e}")
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
            proc.wait()


def _default_mcp_command() -> list | None:
    """The MCP server beside this compiler, as a client would start it."""
    if getattr(sys, "frozen", False):
        return None                         # a standalone executable
    beside = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "velaris_mcp.py")
    if os.path.exists(beside):
        return [sys.executable, beside]
    return [sys.executable, "-m", "velaris_mcp"]


def _split_server_command(argv: list) -> tuple:
    """(own arguments, the server command after `--`, or the default)."""
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1:]
    return argv, _default_mcp_command()


def _sigstore_verify(artifact: bytes, bundle_path: str,
                     identity: str) -> str | None:
    """None when the sigstore bundle proves `identity` signed these
    exact bytes; otherwise why not."""
    try:
        from sigstore.models import Bundle
        from sigstore.verify import Verifier
        from sigstore.verify.policy import Identity
    except ImportError:
        return ("the sigstore package is not installed, so the signature "
                "cannot be checked: pip install sigstore - or check it with "
                "the sigstore command as SECURITY.md shows and then pass "
                "--skip-signature")
    try:
        with open(bundle_path, "rb") as fh:
            bundle = Bundle.from_json(fh.read())
        Verifier.production().verify_artifact(
            artifact, bundle, Identity(identity=identity, issuer=OIDC_ISSUER))
    except Exception as e:
        return f"the signature does not verify: {type(e).__name__}: {e}"
    return None


def mcp_manifest_main(argv: list) -> int:
    """velaris mcp-manifest [-o FILE] [-- server command...]"""
    own, command = _split_server_command(argv)
    if not command:
        print("mcp-manifest: name the server to ask after --, as: velaris "
              "mcp-manifest -o tools.json -- python -m velaris_mcp",
              file=sys.stderr)
        return 2
    out = None
    if "-o" in own:
        at = own.index("-o")
        if at + 1 >= len(own):
            print("mcp-manifest: -o needs a file", file=sys.stderr)
            return 2
        out = own[at + 1]
    try:
        info, tools = mcp_list_tools(command)
    except RuntimeError as e:
        print(f"mcp-manifest: {e}", file=sys.stderr)
        return 2
    text = json.dumps(mcp_tool_manifest(info, tools), indent=2) + "\n"
    if out is None:
        sys.stdout.write(text)
    else:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"{out}: {len(tools)} tool(s) from {info.get('name')} "
              f"{info.get('version')}", file=sys.stderr)
    return 0


def mcp_verify_main(argv: list) -> int:
    """velaris mcp-verify MANIFEST [--bundle FILE] [--identity URL]
    [--skip-signature] [-- server command...]

    Checks the manifest's signature, starts the server the way a client
    would, and reports every tool whose description or input schema
    differs from the manifest, and every tool added or missing. Exit 0
    when everything matches, 1 when anything differs, 2 when the check
    could not be made."""
    own, command = _split_server_command(argv)
    manifest_path = bundle_path = identity = None
    skip = False
    i = 0
    while i < len(own):
        a = own[i]
        if a in ("--bundle", "--identity"):
            if i + 1 >= len(own):
                print(f"mcp-verify: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--bundle":
                bundle_path = own[i + 1]
            else:
                identity = own[i + 1]
            i += 2
            continue
        if a == "--skip-signature":
            skip = True
        elif a.startswith("-") or manifest_path is not None:
            print("usage: velaris mcp-verify MANIFEST [--bundle FILE] "
                  "[--identity URL] [--skip-signature] [-- server command]",
                  file=sys.stderr)
            return 2
        else:
            manifest_path = a
        i += 1
    if manifest_path is None:
        print("usage: velaris mcp-verify MANIFEST [--bundle FILE] "
              "[--identity URL] [--skip-signature] [-- server command]",
              file=sys.stderr)
        return 2
    if not command:
        print("mcp-verify: name the server to check after --, as: velaris "
              "mcp-verify tools.json -- python -m velaris_mcp",
              file=sys.stderr)
        return 2
    try:
        with open(manifest_path, "rb") as fh:
            raw = fh.read()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        manifest = None
    promised = manifest.get("tools") if isinstance(manifest, dict) else None
    if not (isinstance(manifest, dict)
            and manifest.get("schema") == MCP_TOOLS_SCHEMA
            and manifest.get("hash") == "sha256"
            and isinstance(promised, list)
            and all(isinstance(t, dict) and isinstance(t.get("name"), str)
                    for t in promised)):
        print(f"mcp-verify: {manifest_path} is not a readable "
              f"{MCP_TOOLS_SCHEMA} manifest", file=sys.stderr)
        return 2
    version = (manifest.get("server") or {}).get("version")
    print(f"manifest:  {manifest_path} ({len(promised)} tool(s), "
          f"{(manifest.get('server') or {}).get('name')} {version})")

    if skip:
        print("signature: NOT CHECKED (--skip-signature)")
    else:
        bundle_path = bundle_path or manifest_path + ".sigstore.json"
        identity = identity or release_identity(version)
        if not os.path.exists(bundle_path):
            print(f"mcp-verify: no signature bundle at {bundle_path}; "
                  f"download it from the release beside the manifest, or "
                  f"pass --bundle - or --skip-signature to compare without "
                  f"one", file=sys.stderr)
            return 2
        why = _sigstore_verify(raw, bundle_path, identity)
        if why:
            print(f"mcp-verify: {why}", file=sys.stderr)
            return 2
        print(f"signature: verified, signed by {identity}")

    try:
        info, tools = mcp_list_tools(command)
    except RuntimeError as e:
        print(f"mcp-verify: {e}", file=sys.stderr)
        return 2
    print(f"server:    {' '.join(command)} ({info.get('name')} "
          f"{info.get('version')})")
    if info.get("version") != version:
        print(f"           the manifest is for {version}; the server says "
              f"{info.get('version')}")

    offered: dict = {}
    doubled = set()
    for t in tools:
        h = mcp_tool_hashes(t)
        name = str(h["name"])
        if name in offered:
            doubled.add(name)
        offered[name] = h
    wanted = {t["name"]: t for t in promised}
    same = changed = 0
    for name in sorted(set(wanted) | set(offered)):
        if name not in offered:
            changed += 1
            print(f"  MISSING  {name}: in the manifest, not offered by the "
                  f"server")
            continue
        if name not in wanted:
            changed += 1
            print(f"  NEW      {name}: offered by the server, not in the "
                  f"manifest")
            continue
        parts = [label for key, label in (
            ("description_sha256", "description"),
            ("input_schema_sha256", "input schema"))
            if offered[name][key] != wanted[name].get(key)]
        if name in doubled:
            parts.append("offered more than once")
        if parts:
            changed += 1
            print(f"  CHANGED  {name}: {' and '.join(parts)}")
        else:
            same += 1
            print(f"  ok       {name}")
    print(f"{same} of {len(set(wanted) | set(offered))} tool(s) match the "
          f"manifest" + (f"; {changed} differ" if changed else ""))
    return 1 if changed else 0


# ---------------------------------------------------------------------------
# 17. THE CAPABILITY RATCHET
#
#     A repository declares the capability surface it may have in
#     velaris.capabilities, and `velaris capabilities check` fails a
#     working tree that needs more. The comparison is always with that
#     file, never with the previous commit: capability is binary and
#     cumulative, so a surface assembled over forty small commits is
#     reported in full at every one of them - against what was declared -
#     rather than as forty small steps each measured from the last.
#     `velaris review --against REF` reports the delta from a git ref to
#     the working tree, for a pull request; it informs, the check gates.
#
#     What a program needs is read from its text: its functions' `uses`
#     clauses, the literal paths, hosts and modules its calls name, and a
#     bound on the fs and net operations one run can perform. The effect
#     and type checks run and the prover does not, so the answer is the
#     same with and without z3. velaris-spec SPEC.md section 9 states
#     every rule used here.
# ---------------------------------------------------------------------------

CAPABILITIES_SCHEMA = "velaris.capabilities/1"
CAPABILITIES_FILE = "velaris.capabilities"
CAPABILITIES_CHECK_SCHEMA = "velaris.capabilities-check/1"
REVIEW_SCHEMA = "velaris.review/1"
COUNTED_EFFECTS = ("fs", "net")
_OPERATIONS = (("fs", ("read_file", "read_file_secret", "write_file",
                       "file_exists")),
               ("net", ("fetch", "post", "fetch_status", "request")))
_BOUND_LIMIT = 2 ** 53          # a bound past this is recorded as none
_PLAIN_EFFECTS = ("io", "env", "clock", "rand", "declassify")


# ---- grants as a baseline writes them (velaris-spec 9.2, 9.4) --------------

def _grant_parts(g: str) -> tuple:
    """A baseline grant as a tuple - ("io",), ("ffi", module or None),
    ("fs", direction or None, path or None), ("net", host or None, port
    or None) - or ValueError when it is not one a baseline may hold: no
    count, one module per ffi: grant, no `,` or `@` in a path, hosts
    written as the budget grammar writes them."""
    if not isinstance(g, str) or not g or g != g.strip():
        raise ValueError(f"{g!r} is not a grant")
    if "@" in g:
        raise ValueError(f"'{g}': a baseline grant takes no count; counts "
                         f"go in 'counts'")
    if g in _PLAIN_EFFECTS:
        return (g,)
    if g == "ffi":
        return ("ffi", None)
    if g.startswith("ffi:"):
        m = g[4:]
        if not m or any(ch in m for ch in ",:.") or any(
                ch.isspace() for ch in m):
            raise ValueError(f"'{g}': ffi: names one top-level module")
        return ("ffi", m)
    if g == "fs":
        return ("fs", None, None)
    if g in ("fs:read", "fs:write"):
        return ("fs", g[3:], None)
    if g.startswith("fs:read:") or g.startswith("fs:write:"):
        d, _, p = g[3:].partition(":")
        if not p or "," in p:
            raise ValueError(f"'{g}': a path after fs:{d}: is not empty and "
                             f"holds no ','")
        return ("fs", d, p)
    if g == "net":
        return ("net", None, None)
    if g.startswith("net:"):
        text = g[4:]
        if "," in text:
            raise ValueError(f"'{g}': a host holds no ','")
        try:
            host, port = parse_host_port(text)
        except BudgetError as e:
            raise ValueError(f"'{g}': {e}")
        if host.startswith("*."):
            tail = host[2:]
            if not tail or "*" in tail or "." not in tail or all(
                    lbl.isdigit() for lbl in tail.split(".")):
                raise ValueError(f"'{g}': a wildcard is '*.' and at least "
                                 f"two labels, not over an IP literal")
        elif "*" in host:
            raise ValueError(f"'{g}': only a leading '*.' is a wildcard")
        if any(ch.isspace() for ch in host):
            raise ValueError(f"'{g}': a host holds no space")
        return ("net", _pct_encode(host) if ":" not in host else host, port)
    raise ValueError(f"'{g}' is not a grant; the effects are "
                     f"{', '.join(ALL_EFFECTS)}")


def _norm_path(p: str) -> str:
    """velaris-spec 9.4's N: `/` runs made one, `.` components removed,
    `..` removed with the component before it (never past a leading `/`),
    a trailing `/` removed, nothing made `.`. Text only: nothing is
    resolved against a file system, and `\\` is not a separator."""
    rooted = p.startswith("/")
    out: list = []
    for part in p.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if out and out[-1] != "..":
                out.pop()
                continue
            if rooted and not out:
                continue
        out.append(part)
    text = "/".join(out)
    return "/" + text if rooted else (text or ".")


def _path_covers(q: str, p: str) -> bool:
    """Does a grant for path q cover path p (velaris-spec 9.4)? A path
    holding a `\\` is compared whole: on Windows `data/..\\..\\x` leaves
    `data`, and text that cannot be read the same way everywhere is
    covered only by the same text."""
    nq, np_ = _norm_path(q), _norm_path(p)
    if nq == np_:
        return True
    if "\\" in nq or "\\" in np_:
        return False
    if nq == ".":
        return not (np_.startswith("/") or np_ == ".."
                    or np_.startswith("../"))
    if nq == "/":
        return np_.startswith("/")
    return np_.startswith(nq + "/")


def _covers(b: tuple, c: tuple) -> bool:
    """Does grant b cover grant c (both _grant_parts)? velaris-spec 9.4:
    the budget's covering rule of 5.5, grant by grant, with paths compared
    as text."""
    if b[0] != c[0]:
        return False
    if b[0] in _PLAIN_EFFECTS:
        return True
    if b[0] == "ffi":
        return b[1] is None or b[1] == c[1]
    if b[1] is None:                       # plain fs or net: everything
        return True
    if c[1] is None:                       # c is plain, b is scoped
        return False
    if b[0] == "fs":
        if b[1] != c[1]:
            return False
        if b[2] is None:
            return True
        return c[2] is not None and _path_covers(b[2], c[2])
    # net: a grant with a port does not cover one without
    (host, port), (want, want_port) = (b[1], b[2]), (c[1], c[2])
    if port is not None and port != want_port:
        return False
    if host.startswith("*.") and want.startswith("*."):
        return host == want
    if want.startswith("*."):
        return False
    return _host_matches(host, want)


def _covered(g: str, grants) -> bool:
    """Is grant g covered by any of grants (texts)?"""
    want = _grant_parts(g)
    return any(_covers(_grant_parts(h), want) for h in grants)


def _reduce_grants(grants) -> list:
    """Sorted, without repeats, and without a grant another one covers
    (velaris-spec 9.2 rule 5). Of two grants that cover each other - two
    spellings of one path - the first in code-point order is kept."""
    uniq = sorted(set(grants))
    parts = {g: _grant_parts(g) for g in uniq}
    keep = []
    for g in uniq:
        if not any(h != g and _covers(parts[h], parts[g])
                   and (not _covers(parts[g], parts[h]) or h < g)
                   for h in uniq):
            keep.append(g)
    return keep


def _effect_of(g: str) -> str:
    return g.split(":", 1)[0]


# ---- what a program needs, from its text (velaris-spec 9.3) ----------------

def _call_sites(funcs: list) -> list:
    """(function, Call) for every call in every loaded function's body,
    in source order."""
    import dataclasses as _dc
    found = []

    def visit(node, fn):
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x, fn)
            return
        if not _dc.is_dataclass(node) or isinstance(node, Function):
            return
        if isinstance(node, Call):
            found.append((fn, node))
        for fld in _dc.fields(node):
            visit(getattr(node, fld.name), fn)

    for fn in funcs:
        visit(fn.body, fn)
    return found


def _site(fn, call, literal=None) -> dict:
    return {"file": fn.src_file, "line": call.line, "function": fn.name,
            "call": call.name, "literal": literal}


def _text_value(e, consts: dict):
    """The text an expression always is - a text literal, a variable in
    `consts`, or `+` of two such - or None."""
    if isinstance(e, Str):
        return e.value
    if isinstance(e, Var):
        return consts.get(e.name)
    if isinstance(e, BinOp) and e.op == "+":
        a, b = _text_value(e.left, consts), _text_value(e.right, consts)
        return a + b if a is not None and b is not None else None
    return None


def _text_constants(fn) -> dict:
    """{name: text} for the variables of fn that are bound exactly once,
    by a `let` whose value is text the program fixes (_text_value), and
    never assigned, bound by a check, or a parameter - so that moving a
    literal path, URL or module name into a variable does not read as a
    value built while running (velaris-spec 9.3)."""
    import dataclasses as _dc
    lets: dict = {}
    order: list = []
    other: set = {n for n, _ in fn.params}

    def walk(node):
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not _dc.is_dataclass(node) or isinstance(node, Function):
            return
        if isinstance(node, Let):
            lets[node.name] = lets.get(node.name, 0) + 1
            order.append(node)
        elif isinstance(node, Assign):
            other.add(node.name)
        elif isinstance(node, Check):
            other.update(n for n in (node.ok_name, node.fail_name) if n)
        for fld in _dc.fields(node):
            walk(getattr(node, fld.name))

    walk(fn.body)
    consts: dict = {}
    for node in order:
        if lets[node.name] == 1 and node.name not in other:
            v = _text_value(node.value, consts)
            if v is not None:
                consts[node.name] = v
    return consts


def _literals_named(funcs: list) -> dict:
    """What the calls of every loaded function name: fixed paths by
    direction, hosts, modules - each with the call sites that name it -
    and the sites that name one with a value built while running. Fixed
    means a text literal, or a variable bound once to one
    (_text_constants)."""
    lits: dict = {"read": {}, "write": {}, "read_any": [], "write_any": [],
                  "hosts": {}, "net_any": [], "modules": {}, "ffi_any": []}
    fs_kind = {"read_file": "read", "read_file_secret": "read",
               "file_exists": "read",
               "write_file": "write"}
    url_at = {"fetch": 0, "post": 0, "fetch_status": 0, "request": 1}
    consts_of: dict = {}
    for fn, call in _call_sites(funcs):
        if fn.name not in consts_of:
            consts_of[fn.name] = _text_constants(fn)
        consts = consts_of[fn.name]
        kind = fs_kind.get(call.name)
        if kind and call.args:
            value = _text_value(call.args[0], consts)
            if value is not None:
                lits[kind].setdefault(value, []).append(
                    _site(fn, call, value))
            else:
                lits[kind + "_any"].append(_site(fn, call))
        at = url_at.get(call.name)
        if at is not None and len(call.args) > at:
            value = _text_value(call.args[at], consts)
            entry = _host_entry(value) if value is not None else None
            if entry:
                lits["hosts"].setdefault(entry, []).append(
                    _site(fn, call, value))
            else:
                lits["net_any"].append(_site(fn, call, value))
        if call.name in _FFI_CALLS and call.args:
            value = _text_value(call.args[0], consts)
            if value is not None:
                lits["modules"].setdefault(value.split(".")[0], []) \
                    .append(_site(fn, call, value))
            else:
                lits["ffi_any"].append(_site(fn, call))
    return lits


def _effect_sites(effect: str, funcs: list, own: list) -> list:
    """Where a program comes to need an effect: the calls to a builtin
    that performs it, or - when nothing calls one - the functions of the
    file that declare it without using it."""
    sites = [_site(fn, call) for fn, call in _call_sites(funcs)
             if effect in BUILTINS.get(call.name, {}).get("effects", ())]
    if sites:
        return sites
    return [{"file": f.src_file, "line": f.line, "function": f.name,
             "call": None, "literal": None}
            for f in own if effect in f.effects]


def _needs(effects, lits: dict, funcs: list, own: list) -> dict:
    """{grant: [sites]} - the grants velaris-spec 9.3 derives for a
    program, before reduction, each with the call sites that need it. A
    path, host or module the grammar cannot hold as text, or one built
    while running, makes the grant unscoped: wider, so a scoped baseline
    does not cover it and someone has to look."""
    out: dict = {}
    for e in sorted(effects):
        if e in _PLAIN_EFFECTS:
            out[e] = _effect_sites(e, funcs, own)
        elif e == "ffi":
            mods = lits["modules"]
            if lits["ffi_any"] or not mods or any(
                    not m or any(ch in m for ch in ",@:") or m != m.strip()
                    or any(ch.isspace() for ch in m) for m in mods):
                out["ffi"] = lits["ffi_any"] + [
                    s for ss in mods.values() for s in ss] or \
                    _effect_sites("ffi", funcs, own)
            else:
                for m, sites in mods.items():
                    out[f"ffi:{m}"] = sites
        elif e == "fs":
            made = False
            for d in ("read", "write"):
                paths = lits[d]
                awkward = [p for p in paths
                           if not p or p != p.strip() or "," in p or "@" in p
                           or any(ch in p for ch in "\r\n\t")]
                if lits[d + "_any"] or awkward:
                    out[f"fs:{d}"] = lits[d + "_any"] + [
                        s for p in paths for s in paths[p]]
                    made = True
                elif paths:
                    for p, sites in paths.items():
                        out[f"fs:{d}:{p}"] = sites
                    made = True
            if not made:
                out["fs"] = _effect_sites("fs", funcs, own)
        elif e == "net":
            hosts = lits["hosts"]
            if lits["net_any"] or not hosts or any(
                    "*" in h or "/" in h or (not h.startswith("[")
                                             and h.count(":") > 1)
                    for h in hosts):
                out["net"] = lits["net_any"] + [
                    s for h in hosts for s in hosts[h]] or \
                    _effect_sites("net", funcs, own)
            else:
                for h, sites in hosts.items():
                    out[f"net:{h}"] = sites
    # a grant the baseline grammar cannot hold falls back to its effect
    safe: dict = {}
    for g, sites in out.items():
        try:
            _grant_parts(g)
        except ValueError:
            g = _effect_of(g)
        safe.setdefault(g, []).extend(sites)
    return safe


# ---- how many fs and net operations one run can perform ---------------------

def _const_int(e, known: dict):
    """The whole number an expression always is, from literals and the
    variables `known` holds, or None. `known` maps a variable to a whole
    number, or to ("items", n) for a list literal of n items, whose
    `length` is then known."""
    if isinstance(e, Num) and isinstance(e.value, int) \
            and not isinstance(e.value, bool):
        return e.value
    if isinstance(e, Neg):
        v = _const_int(e.value, known)
        return None if v is None else -v
    if isinstance(e, Var):
        v = known.get(e.name)
        return v if isinstance(v, int) else None
    if isinstance(e, BinOp) and e.op in ("+", "-", "*"):
        a, b = _const_int(e.left, known), _const_int(e.right, known)
        if a is None or b is None:
            return None
        return a + b if e.op == "+" else a - b if e.op == "-" else a * b
    if isinstance(e, Call) and e.name == "length" and len(e.args) == 1:
        arg = e.args[0]
        if isinstance(arg, ListLit):
            return len(arg.items)
        if isinstance(arg, Var) and isinstance(known.get(arg.name), tuple):
            return known[arg.name][1]
    return None


def _turns(loop: While, known: dict):
    """The most times a loop's body can run, or math.inf. A bound exists
    for the one shape the termination rule shows to end (SPEC.md 9.5) -
    a counter moving one step toward its limit on every path - when the
    counter's value on entry and the limit are whole numbers the text
    fixes, the limit read only from variables the body leaves alone.
    Each qualifying conjunct of the condition bounds the loop on its
    own, so the smallest bound is taken."""
    import math
    best = math.inf
    bound = _names_bound_in(loop.body)
    # the limit is read only from literals and from variables the body
    # leaves alone, so a value found for it holds on every turn
    unchanged = {k: v for k, v in known.items() if k not in bound}
    for c in _conjuncts(loop.cond):
        if not isinstance(c, BinOp) or c.op not in FLIP:
            continue
        for side, other, op in ((c.left, c.right, c.op),
                                (c.right, c.left, FLIP[c.op])):
            if not isinstance(side, Var) or side.name not in bound:
                continue
            steps = _steps_along_paths(loop.body, side.name, op)
            if steps is BAD or (steps and steps != {1}):
                continue
            if not steps:                  # every path leaves the loop
                best = min(best, 1)
                continue
            start = known.get(side.name)
            limit = _const_int(other, unchanged)
            if not isinstance(start, int) or limit is None:
                continue
            n = {"<": limit - start, "<=": limit - start + 1,
                 ">": start - limit, ">=": start - limit + 1}[op]
            best = min(best, max(0, n))
    return best


def _operation_bounds(funcs: list) -> tuple:
    """({function: {"fs": n, "net": n}}, {function: {effect: why}}): for
    every loaded function, the most fs and net operations one call to it
    can perform - math.inf when the text sets no bound - and for an
    unbounded one, the first reason. Sums along a path, the larger of two
    branches, a loop's body times its turns (_turns), a callee's bound
    at every call, and no bound through recursion. An operation is a
    call to one of the builtins the runtime counts (_OPERATIONS); a
    function value is pure (SPEC.md 7) and performs none."""
    import math
    INF = math.inf
    table = {f.name: f for f in funcs}
    memo: dict = {}
    why: dict = {}
    biggest: dict = {}           # function -> effect -> (amount, sentence)
    active: list = []

    def zero():
        return {"fs": 0, "net": 0}

    def credit(fn, got, sentence):
        for k, v in got.items():
            if 0 < v < INF and v > biggest.get(fn.name, {}).get(
                    k, (0, ""))[0]:
                biggest.setdefault(fn.name, {})[k] = (v, sentence)

    def add(a, b):
        return {k: a[k] + b[k] for k in a}

    def most(a, b):
        return {k: max(a[k], b[k]) for k in a}

    def times(a, n):
        return {k: (0 if a[k] == 0 else a[k] * n) for k in a}

    def blame(fn, got, reason):
        for k, v in got.items():
            if v == INF:
                why.setdefault(fn.name, {}).setdefault(k, reason)

    def of(name, caller):
        if name in memo:
            return memo[name]
        f = table[name]
        if name in active:                 # recursion: as many as it
            got = {k: (INF if k in f.effects else 0)   # may declare
                   for k in COUNTED_EFFECTS}
            blame(caller, got, f"'{name}' can call itself again, through "
                               f"'{caller.name}'")
            return got
        active.append(name)
        try:
            got = block(f.body, {}, f)
        finally:
            active.pop()
        memo[name] = got
        return got

    def ex(e, known, fn):
        if isinstance(e, Call):
            got = zero()
            for a in e.args:
                got = add(got, ex(a, known, fn))
            for effect, names in _OPERATIONS:
                if e.name in names:
                    got[effect] += 1
            if e.name in table:
                sub = of(e.name, fn)
                if INF in sub.values():
                    blame(fn, sub, f"it calls '{e.name}', which has no "
                                   f"bound: "
                                   + "; ".join(sorted(set(
                                       why.get(e.name, {}).values()))
                                       or ["recursion"]))
                for k, v in sub.items():
                    inner = biggest.get(e.name, {}).get(k)
                    credit(fn, {k: v}, f"it calls '{e.name}'"
                           + (f", where {inner[1]}" if inner else ""))
                got = add(got, sub)
            return got
        if isinstance(e, TryExpr):
            return ex(e.value, known, fn)
        if isinstance(e, BinOp):
            return add(ex(e.left, known, fn), ex(e.right, known, fn))
        if isinstance(e, (Not, Neg)):
            return ex(e.value, known, fn)
        if isinstance(e, FieldGet):
            return ex(e.obj, known, fn)
        if isinstance(e, ListLit):
            got = zero()
            for x in e.items:
                got = add(got, ex(x, known, fn))
            return got
        if isinstance(e, MapLit):
            got = zero()
            for k, v in e.entries:
                got = add(got, add(ex(k, known, fn), ex(v, known, fn)))
            return got
        if isinstance(e, RecordLit):
            got = zero()
            for _name, v in e.fields:
                got = add(got, ex(v, known, fn))
            return got
        return zero()

    def forget(known, names):
        for n in names:
            known.pop(n, None)

    def st(s, known, fn):
        if isinstance(s, (Let, Assign)):
            got = ex(s.value, known, fn)
            v = _const_int(s.value, known)
            if isinstance(s.value, ListLit):
                v = ("items", len(s.value.items))
            if v is None:
                known.pop(s.name, None)
            else:
                known[s.name] = v
            return got
        if isinstance(s, (Return, FailStmt)):
            return zero() if s.value is None else ex(s.value, known, fn)
        if isinstance(s, ExprStmt):
            return ex(s.expr, known, fn)
        if isinstance(s, If):
            got = ex(s.cond, known, fn)
            both = most(block(s.then, known, fn), block(s.other, known, fn))
            forget(known, _names_bound_in(s.then) | _names_bound_in(s.other))
            return add(got, both)
        if isinstance(s, Check):
            got = ex(s.subject, known, fn)
            inner = {k: v for k, v in known.items()
                     if k not in (s.ok_name, s.fail_name)}
            both = most(block(s.ok_body, inner, fn),
                        block(s.fail_body, inner, fn))
            forget(known, _names_bound_in([s]))
            return add(got, both)
        if isinstance(s, While):
            n = _turns(s, known)
            changed = _names_bound_in(s.body)
            inner = {k: v for k, v in known.items() if k not in changed}
            cond, body = ex(s.cond, inner, fn), block(s.body, inner, fn)
            forget(known, changed)
            got = add(times(cond, n + 1), times(body, n))
            where = f"line {s.line} of {os.path.basename(fn.src_file or '?')}"
            if n == INF:
                blame(fn, got, f"the loop at {where} has no fixed number "
                               f"of turns")
            else:
                credit(fn, got, f"the loop at {where} turns at most {n} "
                                f"time(s)")
            return got
        if isinstance(s, Block):
            got = zero()
            for x in s.stmts:
                got = add(got, st(x, known, fn))
            return got
        return zero()

    def block(stmts, known, fn):
        known = dict(known)
        got = zero()
        for s in stmts:
            got = add(got, st(s, known, fn))
        return got

    for f in funcs:
        of(f.name, f)
    for name, per in biggest.items():       # where a finite bound comes
        for k, (_amount, sentence) in per.items():   # from, when no
            why.setdefault(name, {}).setdefault(k, sentence)   # infinite
    return memo, why                                          # one does


def _as_count(n):
    """A bound as a baseline writes it: a whole number, or None for no
    bound (and for one too large to be useful)."""
    import math
    if n == math.inf or n > _BOUND_LIMIT:
        return None
    return int(n)


def _count_exceeds(now, allowed) -> bool:
    """Is `now` more operations than `allowed`? None is no bound."""
    if allowed is None:
        return False
    return now is None or now > allowed


# ---- one program, and a tree of them ----------------------------------------

def _program_capabilities(path: str, rel: str) -> dict:
    """What one .vel file needs (velaris-spec 9.3): its grants, reduced;
    how many fs and net operations one call to any of its functions can
    perform; and each of its functions' declared effects. Keys beginning
    with '_' are for reporting and are not written to a baseline. A file
    that does not parse, load, or pass the effect and type checks cannot
    run, and is marked compiles: False with its problems."""
    out: dict = {"file": rel, "compiles": False, "problems": [],
                 "grants": [], "counts": {}, "functions": {}}
    errors: list = []
    try:
        funcs, records = load_program(path)
        check_main(funcs, errors, running=False)
        check_effects(funcs, errors)
        if not errors:
            check_types(funcs, records, errors)
    except VelarisError as e:
        errors.append(e)
    except Exception as e:                  # a checker that crashed still
        errors.append(VelarisError(         # means: cannot be compared
            "E000", f"{type(e).__name__}: {e}", 0))
    if errors:
        out["problems"] = [{"code": e.code, "line": e.line,
                            "message": e.message} for e in errors[:5]]
        return out
    here = os.path.abspath(path)
    own = [f for f in funcs if not f.name.startswith("fn#")
           and os.path.abspath(f.src_file or path) == here]
    # running this file runs `main`, wherever it is defined: a file that
    # imports its main from outside the checked tree still needs what
    # that main does
    runs = own + [f for f in funcs if f.name == "main" and f not in own]
    effects = sorted({e for f in runs for e in f.effects})
    lits = _literals_named(funcs)
    needs = _needs(effects, lits, funcs, runs)
    grants = _reduce_grants(needs)
    origins = {g: [] for g in grants}
    for g, sites in needs.items():       # a grant reduced away is needed
        into = g if g in origins else next(   # through the one covering it
            h for h in grants if _covers(_grant_parts(h), _grant_parts(g)))
        origins[into].extend(sites)
    bounds, why = _operation_bounds(funcs)
    counts = {}
    for e in COUNTED_EFFECTS:
        if e in effects:
            counts[e] = _as_count(max([bounds[f.name][e] for f in runs]
                                      or [0]))
    out.update(compiles=True, grants=grants, counts=counts,
               functions={f.name: sorted(f.effects) for f in own},
               _funcs=funcs, _own=runs, _origins=origins, _lits=lits,
               _bounds=bounds, _why=why, _path=path)
    return out


def _capability_files(root: str, use_git: bool = True) -> list:
    """Every .vel file under root, as sorted '/'-separated paths relative
    to it - leaving out .git, and files git ignores when root is in a git
    work tree (they are not part of the repository)."""
    import subprocess
    found = []
    for dp, dirs, files in os.walk(root):
        # every directory but git's own: a program committed under
        # .github or .ci is part of the repository like any other
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for f in files:
            if f.endswith(".vel"):
                found.append(os.path.relpath(os.path.join(dp, f), root)
                             .replace(os.sep, "/"))
    found.sort()
    if not found or not use_git:
        return found
    try:
        done = subprocess.run(
            ["git", "-C", root, "check-ignore", "--stdin", "-z"],
            input="\0".join(found).encode("utf-8"), capture_output=True,
            timeout=120)
    except (OSError, subprocess.SubprocessError):
        return found                        # no git: nothing is ignored
    if done.returncode not in (0, 1):
        return found                        # not a work tree
    ignored = {p for p in done.stdout.decode("utf-8", "replace").split("\0")
               if p}
    return [f for f in found if f not in ignored]


def capability_scan(root: str = ".", use_git: bool = True) -> dict:
    """The capability surface of every .vel file under root: {"root",
    "programs": {file: _program_capabilities}, "surface": {"grants",
    "counts"}}. The surface is the union of the grants of the files that
    compile, reduced, and for fs and net the largest count any of them
    has (None - no bound - beats every number)."""
    programs = {rel: _program_capabilities(os.path.join(root, rel), rel)
                for rel in _capability_files(root, use_git)}
    live = [p for p in programs.values() if p["compiles"]]
    grants = _reduce_grants(g for p in live for g in p["grants"])
    counts = {}
    for e in COUNTED_EFFECTS:
        have = [p["counts"][e] for p in live if e in p["counts"]]
        if have:
            counts[e] = None if None in have else max(have)
    return {"root": root, "programs": programs,
            "surface": {"grants": grants, "counts": counts}}


def capabilities_document(scan: dict, date: str | None = None) -> dict:
    """The velaris.capabilities/1 document for a scan: the Velaris that
    wrote it, the date, the surface, and each program's grants, counts
    and functions' effects - or compiles: false."""
    import datetime
    if date is None:
        date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    programs = []
    for rel in sorted(scan["programs"]):
        p = scan["programs"][rel]
        if not p["compiles"]:
            programs.append({"file": rel, "compiles": False})
            continue
        programs.append({"file": rel, "grants": p["grants"],
                         "counts": p["counts"],
                         "functions": dict(sorted(p["functions"].items()))})
    return {"schema": CAPABILITIES_SCHEMA, "velaris_version": VERSION,
            "date": date, "surface": scan["surface"], "programs": programs}


def capabilities_text(doc: dict) -> str:
    """A baseline as text: JSON, one grant per line and one function per
    line, so that accepting a widening is a one-line change in review."""
    dump = json.dumps

    def counts(c):
        return "{" + ", ".join(f"{dump(k)}: {dump(v)}"
                               for k, v in sorted(c.items())) + "}"

    def grant_list(gs, pad):
        if not gs:
            return "[]"
        inner = ",\n".join(f"{pad}  {dump(g)}" for g in gs)
        return "[\n" + inner + f"\n{pad}]"

    lines = ["{",
             f'  "schema": {dump(doc["schema"])},',
             f'  "velaris_version": {dump(doc["velaris_version"])},',
             f'  "date": {dump(doc["date"])},',
             '  "surface": {',
             f'    "grants": {grant_list(doc["surface"]["grants"], "    ")},',
             f'    "counts": {counts(doc["surface"]["counts"])}',
             "  },"]
    entries = []
    for p in doc["programs"]:
        if p.get("compiles") is False:
            entries.append(f'    {{"file": {dump(p["file"])}, '
                           f'"compiles": false}}')
            continue
        fns = ",\n".join(f"        {dump(n)}: {dump(e)}"
                         for n, e in p["functions"].items())
        entries.append(
            "    {\n"
            f'      "file": {dump(p["file"])},\n'
            f'      "grants": {grant_list(p["grants"], "      ")},\n'
            f'      "counts": {counts(p["counts"])},\n'
            '      "functions": ' + ("{}" if not fns else
                                     "{\n" + fns + "\n      }") + "\n"
            "    }")
    lines.append('  "programs": [' + ("" if not entries else "\n"
                                      + ",\n".join(entries) + "\n  ") + "]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def read_capabilities(path: str) -> dict:
    """A velaris.capabilities/1 document, checked; ValueError naming the
    first thing wrong with it. velaris.capabilities/0, the spec's
    provisional form, was never written by Velaris and is refused."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e.strerror or e}")
    except ValueError as e:
        raise ValueError(f"{path} is not JSON: {e}")
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a {CAPABILITIES_SCHEMA} document")
    if doc.get("schema") == "velaris.capabilities/0":
        raise ValueError(f"{path} is velaris.capabilities/0, the "
                         f"provisional form velaris-spec 0.2 described and "
                         f"no Velaris wrote; write a {CAPABILITIES_SCHEMA} "
                         f"one with: velaris capabilities init --force")
    if doc.get("schema") != CAPABILITIES_SCHEMA:
        raise ValueError(f"{path} is not a {CAPABILITIES_SCHEMA} document "
                         f"(its schema is {doc.get('schema')!r})")

    def check_grants(gs, where):
        if not isinstance(gs, list):
            raise ValueError(f"{where}: grants is a list")
        for g in gs:
            try:
                _grant_parts(g)
            except ValueError as e:
                raise ValueError(f"{where}: {e}")

    def check_counts(c, where):
        if not isinstance(c, dict):
            raise ValueError(f"{where}: counts is an object")
        for k, v in c.items():
            if k not in COUNTED_EFFECTS or not (
                    v is None or (isinstance(v, int)
                                  and not isinstance(v, bool) and v >= 0)):
                raise ValueError(f"{where}: counts holds fs and net only, "
                                 f"each a whole number or null")

    surface = doc.get("surface")
    if not isinstance(surface, dict):
        raise ValueError(f"{path}: no surface")
    check_grants(surface.get("grants"), "surface")
    check_counts(surface.get("counts", {}), "surface")
    programs = doc.get("programs")
    if not isinstance(programs, list):
        raise ValueError(f"{path}: programs is a list")
    seen = set()
    for p in programs:
        f = p.get("file") if isinstance(p, dict) else None
        if not isinstance(f, str) or not f or f.startswith("/") \
                or "\\" in f or any(part in ("", ".", "..")
                                    for part in f.split("/")):
            raise ValueError(f"{path}: a program's file is a '/'-separated "
                             f"path under the baseline's directory")
        if f in seen:
            raise ValueError(f"{path}: {f} is listed twice")
        seen.add(f)
        if p.get("compiles") is False:
            continue
        check_grants(p.get("grants"), f)
        check_counts(p.get("counts", {}), f)
        fns = p.get("functions", {})
        if not isinstance(fns, dict) or not all(
                isinstance(v, list) and all(e in ALL_EFFECTS for e in v)
                for v in fns.values()):
            raise ValueError(f"{f}: functions maps each name to its "
                             f"effects")
    return doc


# ---- the ratchet: the tree against the baseline (velaris-spec 9.5) ----------

def _version_tuple(v) -> tuple:
    return tuple(int(x) if x.isdigit() else 0
                 for x in re.split(r"[.+-]", str(v))[:3])


def _chain(table: dict, starts: list, goal: str) -> list:
    """The shortest chain of calls from one of `starts` to `goal`, as
    function names, or []."""
    from collections import deque
    callees: dict = {}

    def of(name):
        if name not in callees:
            fn = table.get(name)
            callees[name] = [] if fn is None else sorted(
                {c.name for _, c in _call_sites([fn]) if c.name in table})
        return callees[name]

    for start in starts:
        seen, todo = {start: None}, deque([start])
        while todo:
            at = todo.popleft()
            if at == goal:
                path = []
                while at is not None:
                    path.append(at)
                    at = seen[at]
                return path[::-1]
            for nxt in of(at):
                if nxt not in seen:
                    seen[nxt] = at
                    todo.append(nxt)
    return []


def _shown_path(file: str, root: str) -> str:
    """A file as a report shows it: relative to the checked root when it
    is under it, else from the standard library, else as it is."""
    full = os.path.abspath(file)
    try:
        rel = os.path.relpath(full, os.path.abspath(root))
    except ValueError:
        rel = None
    if rel is not None and not rel.startswith(".."):
        return rel.replace(os.sep, "/")
    std = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdlib")
    if full.startswith(std + os.sep):
        return "<stdlib>/" + os.path.relpath(full, std).replace(os.sep, "/")
    return full.replace(os.sep, "/")


def _because(fn, effect: str, table: dict) -> list:
    """Why a function needs an effect: the builtins it calls that perform
    it, and the functions it calls that declare it."""
    said = []
    for _, call in _call_sites([fn]):
        if effect in BUILTINS.get(call.name, {}).get("effects", ()):
            said.append(f"calls {call.name} at line {call.line}")
        elif call.name in table and effect in table[call.name].effects:
            said.append(f"calls {call.name} at line {call.line}, which "
                        f"declares {effect}")
    return sorted(set(said), key=said.index) or [
        f"declares {effect} in its uses clause"]


def capabilities_compare(baseline: dict, scan: dict,
                         baseline_file: str = CAPABILITIES_FILE) -> dict:
    """The ratchet (velaris-spec 9.5): the tree in `scan` against the
    declared surface in `baseline` - never against a previous commit.

    Three rules, and a change widens the surface when any of them fails:
      S  every grant a program under the root needs is covered by the
         baseline's surface, and no program performs more fs or net
         operations in a run than the surface's count;
      P  a program the baseline records needs nothing its own entry does
         not give, and no more operations than its entry's count;
      F  a function the baseline records declares no effect it did not
         declare there.
    A program or function the baseline does not record is held to S
    alone: a new program that stays inside the surface the repository
    already declared does not widen it. Narrowing is never a failure;
    it is reported so the baseline can be tightened."""
    root = scan["root"]
    base_surface = baseline["surface"]["grants"]
    base_counts = baseline["surface"].get("counts", {})
    base_effects = {_effect_of(g) for g in base_surface}
    recorded = {p["file"]: p for p in baseline["programs"]
                if p.get("compiles") is not False}
    programs = scan["programs"]
    findings: list = []
    narrowed: list = []
    notes: list = []
    warnings: list = []

    written_by = baseline.get("velaris_version")
    if written_by != VERSION:
        older = _version_tuple(written_by) < _version_tuple(VERSION)
        warnings.append(
            f"{baseline_file} was written by Velaris {written_by}, "
            f"{'an older' if older else 'a different'} version than this "
            f"one ({VERSION}); the comparison uses this version's "
            f"derivation and standard library, so a difference between "
            f"the two can show up as a change. Read any finding with that "
            f"in mind, then record the surface again with: velaris "
            f"capabilities init --force")

    broken_as_recorded = {p["file"] for p in baseline["programs"]
                          if p.get("compiles") is False}
    for rel, p in sorted(programs.items()):
        if not p["compiles"] and rel not in broken_as_recorded:
            notes.append(f"{rel} does not compile, so it cannot run and "
                         f"adds nothing; it was not compared")
    for rel in sorted(set(recorded) - set(programs)):
        notes.append(f"{baseline_file} records {rel}, which is not there "
                     f"now; not a failure")

    # S and P, grant by grant
    by_grant: dict = {}
    for rel, p in sorted(programs.items()):
        if not p["compiles"]:
            continue
        entry = recorded.get(rel)
        table = {f.name: f for f in p["_funcs"]}
        starts = ["main"] if "main" in table else sorted(p["functions"])
        for g in p["grants"]:
            out_surface = not _covered(g, base_surface)
            out_entry = entry is not None and not _covered(
                g, entry["grants"])
            if not (out_surface or out_entry):
                continue
            item = by_grant.setdefault(g, {
                "kind": "grant", "grant": g, "effect": _effect_of(g),
                "new_effect": _effect_of(g) not in base_effects,
                "outside_surface": False, "programs": []})
            item["outside_surface"] |= out_surface
            origins = [dict(s, file=_shown_path(s["file"], root))
                       for s in p["_origins"].get(g, [])]
            reach = []
            if origins and origins[0]["function"] not in starts:
                reach = _chain(table, starts, origins[0]["function"])
            item["programs"].append({
                "file": rel, "recorded": entry is not None,
                "outside_entry": out_entry, "origins": origins[:8],
                "reached_from": reach})
    for g, item in sorted(by_grant.items()):
        accept = []
        if item["outside_surface"]:
            accept.append(f'add "{g}" to surface.grants')
        for q in item["programs"]:
            if q["outside_entry"]:
                accept.append(f'add "{g}" to the grants of {q["file"]}')
        item["accept"] = accept
        item["rules"] = (["W1"] if item["outside_surface"] else []) + (
            ["W3"] if any(q["outside_entry"] for q in item["programs"])
            else [])
        findings.append(item)

    # S and P, counts
    for rel, p in sorted(programs.items()):
        if not p["compiles"]:
            continue
        entry = recorded.get(rel)
        entry_effects = {_effect_of(g) for g in entry["grants"]} \
            if entry else set()
        for e, now in sorted(p["counts"].items()):
            out_surface = e in base_effects and _count_exceeds(
                now, base_counts.get(e))
            out_entry = e in entry_effects and _count_exceeds(
                now, entry.get("counts", {}).get(e))
            if not (out_surface or out_entry):
                continue
            own = p["_own"]
            worst = max(own, key=lambda f: (p["_bounds"][f.name][e],
                                            -f.line))
            reason = p["_why"].get(worst.name, {}).get(e)
            accept = []
            if out_surface:
                accept.append(f"set surface.counts.{e} to "
                              f"{json.dumps(now)}")
            if out_entry:
                accept.append(f"set counts.{e} of {rel} to "
                              f"{json.dumps(now)}")
            findings.append({
                "kind": "count", "effect": e, "file": rel, "current": now,
                "surface_allows": base_counts.get(e),
                "entry_allows": (entry or {}).get("counts", {}).get(e),
                "outside_surface": out_surface, "outside_entry": out_entry,
                "rules": (["W2"] if out_surface else [])
                + (["W4"] if out_entry else []),
                "function": worst.name, "line": worst.line,
                "why": reason, "accept": accept})

    # F, function by function
    for rel, entry in sorted(recorded.items()):
        p = programs.get(rel)
        if not p or not p["compiles"]:
            continue
        table = {f.name: f for f in p["_funcs"]}
        for name, had in sorted(entry.get("functions", {}).items()):
            now = p["functions"].get(name)
            if now is None:
                continue
            gained = sorted(set(now) - set(had))
            if not gained:
                continue
            fn = table[name]
            findings.append({
                "kind": "function", "file": rel, "function": name,
                "line": fn.line, "had": sorted(had), "now": now,
                "gained": gained, "rules": ["W5"],
                "because": [f"{e}: " + "; ".join(_because(fn, e, table))
                            for e in gained],
                "accept": [f"set functions.{name} of {rel} to "
                           f"{json.dumps(now)}"]})

    # what narrowed - never a failure
    needed = [g for p in programs.values() if p["compiles"]
              for g in p["grants"]]
    for b in base_surface:
        bp = _grant_parts(b)
        if not any(_covers(bp, _grant_parts(g)) for g in needed):
            narrowed.append(f'surface: "{b}" is no longer needed')
    now_counts = scan["surface"]["counts"]
    for e, allowed in sorted(base_counts.items()):
        if e in now_counts and allowed is None and now_counts[e] is not None:
            narrowed.append(f"surface: {e} now has a bound, "
                            f"{now_counts[e]}")
        elif e in now_counts and allowed is not None and \
                now_counts[e] is not None and now_counts[e] < allowed:
            narrowed.append(f"surface: {e} count {allowed} -> "
                            f"{now_counts[e]}")
    for rel, entry in sorted(recorded.items()):
        p = programs.get(rel)
        if not p or not p["compiles"]:
            continue
        for name, had in sorted(entry.get("functions", {}).items()):
            now = p["functions"].get(name)
            if now is not None and set(had) - set(now):
                narrowed.append(f"{rel}: {name} no longer declares "
                                f"{', '.join(sorted(set(had) - set(now)))}")

    live = sum(1 for p in programs.values() if p["compiles"])
    still_broken = sum(1 for rel, p in programs.items()
                       if not p["compiles"] and rel in broken_as_recorded)
    if still_broken:
        notes.append(f"{still_broken} file(s) do not compile, as "
                     f"{baseline_file} records")
    return {"schema": CAPABILITIES_CHECK_SCHEMA, "velaris_version": VERSION,
            "root": root,
            "baseline": {"file": baseline_file,
                         "velaris_version": written_by,
                         "date": baseline.get("date")},
            "widened": bool(findings), "findings": findings,
            "narrowed": narrowed, "notes": notes, "warnings": warnings,
            "programs": len(programs), "compared": live}


def _finding_lines(item: dict) -> list:
    """A finding as the report prints it: what widened, where, and the
    edit to the baseline that would accept it."""
    out = []
    if item["kind"] == "grant":
        what = (f"a new effect, {item['effect']}" if item["new_effect"]
                else "not in the surface" if item["outside_surface"]
                else "inside the surface, not in a program's entry")
        out.append(f"WIDENED  {item['grant']} - {what}")
        for q in item["programs"]:
            where = ("its entry does not grant it" if q["outside_entry"]
                     else "not recorded in the baseline" if not q["recorded"]
                     else "its entry grants it")
            out.append(f"    needed by {q['file']} ({where})")
            for s in q["origins"][:4]:
                lit = f'("{s["literal"]}")' if s.get("literal") else ""
                call = f" calls {s['call']}{lit}" if s.get("call") \
                    else " declares it"
                out.append(f"      {s['file']}:{s['line']}  "
                           f"{s['function']}{call}")
            if q["reached_from"]:
                out.append(f"      reached from "
                           f"{' -> '.join(q['reached_from'])}")
    elif item["kind"] == "count":
        now = ("no bound" if item["current"] is None
               else f"at most {item['current']}")
        allows = item["surface_allows"] if item["outside_surface"] \
            else item["entry_allows"]
        out.append(f"WIDENED  {item['effect']} operations in "
                   f"{item['file']}: {now} in a run; the baseline allows "
                   f"{allows}")
        out.append(f"    {item['function']} (line {item['line']})"
                   + (f": {item['why']}" if item.get("why") else ""))
    else:
        out.append(f"WIDENED  {item['file']}: function {item['function']} "
                   f"gained {', '.join(item['gained'])} (it declared "
                   f"{', '.join(item['had']) or 'nothing'})")
        for b in item["because"]:
            effect, _, rest = b.partition(": ")
            out.append(f"    {effect}: {item['function']} {rest}")
    out.append("    if intended: " + "; ".join(item["accept"]))
    return out


def sarif_capabilities(result: dict) -> dict:
    """`velaris capabilities check --sarif`: each widening as an error at
    the line that introduced it - the call that names a new host, the
    function that gained an effect - each narrowing as a note, and the
    check's whole JSON result in the run's property bag."""
    run = _SarifRun("capabilities")
    root = result["root"]

    def at(file):
        return file if os.path.isabs(file) or file.startswith("<") \
            else os.path.join(root, file)

    for item in result["findings"]:
        if item["kind"] == "grant":
            for q in item["programs"]:
                s = (q["origins"] or [{"file": q["file"], "line": None}])[0]
                where, line, via = s["file"], s.get("line"), ""
                if where.startswith("<"):     # the standard library: the
                    via = f", through {where}:{line}"   # program is where
                    where, line = q["file"], None       # it is reached
                gap = ("not in the surface" if item["outside_surface"]
                       else "not in its entry")
                run.add("capability-widened",
                        f"{item['grant']} is needed by {q['file']}{via}, "
                        f"{gap} of {result['baseline']['file']}"
                        + (f" (a new effect, {item['effect']})"
                           if item["new_effect"] else ""),
                        at(where), line,
                        fixes=["if intended: " + "; ".join(item["accept"])])
        elif item["kind"] == "count":
            now = ("no bound" if item["current"] is None
                   else f"at most {item['current']}")
            run.add("capability-widened",
                    f"{item['file']} performs {now} {item['effect']} "
                    f"operations in a run, more than "
                    f"{result['baseline']['file']} allows"
                    + (f": {item['why']}" if item.get("why") else ""),
                    at(item["file"]), item["line"],
                    fixes=["if intended: " + "; ".join(item["accept"])])
        else:
            run.add("capability-effect-gained",
                    f"'{item['function']}' now declares "
                    f"{', '.join(item['gained'])}, which it did not in "
                    f"{result['baseline']['file']}: "
                    + "; ".join(item["because"]),
                    at(item["file"]), item["line"],
                    fixes=["if intended: " + "; ".join(item["accept"])])
    for text in result["narrowed"]:
        run.add("capability-narrowed", text,
                at(result["baseline"]["file"]), None)
    run.properties["capabilities"] = result
    return run.log()


def capabilities_main(argv: list) -> int:
    """velaris capabilities init [path] [--force]
    velaris capabilities check [path] [--json | --sarif]"""
    usage = ("usage: velaris capabilities init [path] [--force]\n"
             "       velaris capabilities check [path] [--json | --sarif]")
    if not argv or argv[0] not in ("init", "check"):
        print(usage, file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    allowed = {"init": {"--force"}, "check": {"--json", "--sarif"}}[sub]
    flags = {a for a in rest if a.startswith("-")}
    places = [a for a in rest if not a.startswith("-")]
    if flags - allowed or len(places) > 1 or flags >= {"--json", "--sarif"}:
        print(usage, file=sys.stderr)
        return 2
    root = places[0] if places else "."
    if not os.path.isdir(root):
        print(f"velaris capabilities: {root} is not a directory",
              file=sys.stderr)
        return 2
    target = os.path.join(root, CAPABILITIES_FILE)

    if sub == "init":
        if os.path.exists(target) and "--force" not in flags:
            print(f"{target} already exists, and it is the surface this "
                  f"repository declared: init does not replace it. To "
                  f"record the surface again, pass --force; the file's "
                  f"diff then shows what changed.", file=sys.stderr)
            return 1
        scan = capability_scan(root)
        doc = capabilities_document(scan)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(capabilities_text(doc))
        broken = [p for p in doc["programs"] if p.get("compiles") is False]
        print(f"wrote {target}: {len(doc['programs'])} program(s), "
              f"Velaris {VERSION}, {doc['date']}")
        print(f"  surface: {', '.join(doc['surface']['grants']) or 'nothing'}")
        for e, n in sorted(doc["surface"]["counts"].items()):
            print(f"  {e} operations in a run: "
                  f"{'no bound' if n is None else f'at most {n}'}")
        if broken:
            print(f"  {len(broken)} file(s) do not compile; recorded as "
                  f"such, and not compared until they do")
        return 0

    if not os.path.exists(target):
        print(f"no {CAPABILITIES_FILE} in {root}: write one with velaris "
              f"capabilities init {root}", file=sys.stderr)
        return 2
    try:
        baseline = read_capabilities(target)
    except ValueError as e:
        print(f"velaris capabilities check: {e}", file=sys.stderr)
        return 2
    result = capabilities_compare(baseline, capability_scan(root),
                                  CAPABILITIES_FILE)
    code = 1 if result["widened"] else 0
    if "--json" in flags:
        print(json.dumps(result, indent=2))
        return code
    if "--sarif" in flags:
        log = sarif_capabilities(result)
        print(json.dumps(log, indent=2))
        print_sarif_summary(log)
        for w in result["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
        return code
    print(f"velaris capabilities check: {result['programs']} program(s) "
          f"under {root}, {result['compared']} compared, against "
          f"{CAPABILITIES_FILE} (Velaris {baseline.get('velaris_version')}, "
          f"{baseline.get('date')})")
    for w in result["warnings"]:
        print(f"warning: {w}")
    for item in result["findings"]:
        print()
        print("\n".join(_finding_lines(item)))
    if result["narrowed"]:
        print()
        print("narrowed (not a failure):")
        for n in result["narrowed"]:
            print(f"  {n}")
    if result["notes"]:
        print()
        for n in result["notes"][:20]:
            print(f"note: {n}")
        if len(result["notes"]) > 20:
            print(f"note: and {len(result['notes']) - 20} more")
    print()
    if result["widened"]:
        print(f"{len(result['findings'])} widening(s): the code needs more "
              f"than {CAPABILITIES_FILE} declares. If it is all intended, "
              f"make the edits above, or record the surface again and "
              f"commit the file so the widening shows in review:\n"
              f"    velaris capabilities init {root} --force")
    else:
        print(f"no widening: every program is inside {CAPABILITIES_FILE}")
    return code


# ---- review: a git ref against the working tree -----------------------------

def _git(args: list, cwd: str, binary: bool = False):
    import subprocess
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          timeout=300)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.decode("utf-8", "replace").strip()
                           or f"git {' '.join(args)} failed")
    return done.stdout if binary else done.stdout.decode("utf-8", "replace")


def _review_side(root: str, use_git: bool = True) -> dict:
    """What review compares on one side: the capability scan, and for
    every file the functions' promise statuses and fallibility, as
    `velaris proofs` counts them."""
    scan = capability_scan(root, use_git)
    proven = runtime = 0
    functions = {}
    for rel in scan["programs"]:
        rep = inspect_source(os.path.join(root, rel))
        here = os.path.abspath(os.path.join(root, rel))
        for f in rep["functions"]:
            if os.path.abspath(f["file"]) != here:
                continue
            functions[(rel, f["name"])] = f
            proven += f["status"] == "proven"
            runtime += f["status"] == "checked at runtime"
    share = round(100.0 * proven / (proven + runtime), 1) \
        if proven + runtime else None
    lits: dict = {"hosts": set(), "read": set(), "write": set(),
                  "modules": set()}
    for p in scan["programs"].values():
        if p["compiles"]:
            for k in lits:
                lits[k] |= set(p["_lits"][k])
    return {"scan": scan, "functions": functions, "proven_share": share,
            "lits": lits}


def review(against: str, root: str = ".") -> dict:
    """The delta from a git ref to the working tree, as facts: whether
    the capability surface changed, the proven share before and after,
    the functions that became fallible, the hosts, paths and modules
    newly named, and a one-word risk computed from those facts alone -
    `high` when the surface widened, `medium` when it did not but a
    program or function the ref had came to need more or the proven
    share fell, `low` otherwise. The ref's files are read with
    `git show REF:PATH` into a scratch directory; nothing is checked
    out. RuntimeError when git cannot answer."""
    import shutil
    import tempfile
    top = _git(["rev-parse", "--show-toplevel"], root).strip()
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{against}^{{commit}}"], root).strip()
    except RuntimeError:
        raise RuntimeError(f"no commit called '{against}' in this "
                           f"repository (a shallow clone may need: git "
                           f"fetch --depth=1 origin {against})")
    # where root sits in the repository, as git itself says - not by
    # comparing paths, which differ when one side is a Windows short
    # name (RUNNER~1) or a link (macOS's /var is /private/var)
    rel_root = _git(["rev-parse", "--show-prefix"], root).strip() \
        .rstrip("/") or "."
    listed = _git(["ls-tree", "-r", "--name-only", "-z", commit], top)
    scratch = tempfile.mkdtemp(prefix="velaris-review-")
    try:
        for name in (n for n in listed.split("\0") if n.endswith(".vel")):
            blob = _git(["show", f"{commit}:{name}"], top, binary=True)
            dest = os.path.join(scratch, *name.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(blob)
        before_root = os.path.join(scratch, *([] if rel_root == "."
                                              else rel_root.split("/")))
        os.makedirs(before_root, exist_ok=True)
        declared_name = CAPABILITIES_FILE if rel_root == "." \
            else f"{rel_root}/{CAPABILITIES_FILE}"
        declared_before = None
        if declared_name in listed.split("\0"):
            declared_before = _git(["show", f"{commit}:{declared_name}"],
                                   top)
        before = _review_side(before_root, use_git=False)
        before_doc = capabilities_document(before["scan"], "")
        after = _review_side(root)
        delta = capabilities_compare(before_doc, after["scan"],
                                     f"{against} ({commit[:7]})")
        backwards = capabilities_compare(
            capabilities_document(after["scan"], ""), before["scan"])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    surface_widened = [f for f in delta["findings"]
                       if f.get("outside_surface")]
    others = [f for f in delta["findings"] if not f.get("outside_surface")]
    narrowed = [f for f in backwards["findings"]
                if f.get("outside_surface")]
    change = ("widened and narrowed" if surface_widened and narrowed
              else "widened" if surface_widened
              else "narrowed" if narrowed else "unchanged")
    b_share, a_share = before["proven_share"], after["proven_share"]
    fell = (b_share is not None and a_share is not None
            and a_share < b_share) or (
        b_share is not None and b_share > 0 and a_share is None)
    new_fallible = sorted(
        ({"file": rel, "function": name, "line": f["line"]}
         for (rel, name), f in after["functions"].items()
         if f["can_fail"] and not before["functions"].get(
             (rel, name), {}).get("can_fail")),
        key=lambda x: (x["file"], x["line"]))
    newly = {k: sorted(after["lits"][k] - before["lits"][k])
             for k in after["lits"]}
    because = []
    for f in surface_widened:
        because.append("the capability surface widened: " + (
            f"{f['grant']}" + (" (a new effect)" if f["new_effect"] else "")
            if f["kind"] == "grant" else
            f"{f['effect']} operations in {f['file']}"))
    for f in others:
        because.append(
            f"{f['file']}: {f['function']} gained "
            f"{', '.join(f['gained'])}" if f["kind"] == "function" else
            f"{', '.join(q['file'] for q in f['programs'])} came to "
            f"need {f['grant']}" if f["kind"] == "grant" else
            f"{f['file']}: more {f['effect']} operations in a run")
    if fell:
        because.append(f"the proven share fell from {b_share}% to "
                       f"{a_share if a_share is not None else 'none'}"
                       + ("%" if a_share is not None else ""))
    declared = _declared_change(declared_before,
                                os.path.join(root, CAPABILITIES_FILE))
    if declared["removed"]:
        because.append(f"{CAPABILITIES_FILE} was removed, which turns "
                       f"the capability ratchet off")
    if declared["widened"]:
        because.append(f"the surface declared in {CAPABILITIES_FILE} "
                       f"widened: " + ", ".join(declared["widened"]))
    risk = ("high" if surface_widened or declared["removed"]
            or declared["widened"] else
            "medium" if others or fell else "low")
    return {"schema": REVIEW_SCHEMA, "velaris_version": VERSION,
            "declared": declared,
            "against": against, "commit": commit, "root": root,
            "prover": bool(HAVE_Z3),
            "surface": {"change": change,
                        "before": before["scan"]["surface"],
                        "after": after["scan"]["surface"],
                        "widened": surface_widened,
                        "narrowed": [f["grant"] if f["kind"] == "grant"
                                     else f"{f['effect']} operations in "
                                          f"{f['file']}"
                                     for f in narrowed]},
            "programs_came_to_need_more": others,
            "proven_share": {"before": b_share, "after": a_share,
                             "fell": fell},
            "new_fallible": new_fallible,
            "new_hosts": newly["hosts"],
            "new_paths": {"read": newly["read"], "write": newly["write"]},
            "new_modules": newly["modules"],
            "does_not_compile": sorted(
                rel for rel, p in after["scan"]["programs"].items()
                if not p["compiles"]
                and before["scan"]["programs"].get(rel, {}).get(
                    "compiles", True)),
            "risk": risk, "risk_because": because}


def _declared_change(before_text, after_path: str) -> dict:
    """How the declared surface - velaris.capabilities - changed between
    the ref (its text, or None) and the working tree: whether it was
    added or removed, and the surface grants and counts it widened or
    narrowed. A baseline widened in a pull request is the acceptance of
    a widening, and a reviewer should see it named."""
    def surface(text):
        try:
            doc = json.loads(text)
            got = doc["surface"]
            for g in got["grants"]:
                _grant_parts(g)
            return got["grants"], got.get("counts", {})
        except (ValueError, KeyError, TypeError):
            return None

    after_text = None
    if os.path.exists(after_path):
        with open(after_path, encoding="utf-8") as fh:
            after_text = fh.read()
    out = {"before": before_text is not None, "after": after_text is not None,
           "removed": before_text is not None and after_text is None,
           "added": before_text is None and after_text is not None,
           "widened": [], "narrowed": []}
    b = surface(before_text) if before_text is not None else None
    a = surface(after_text) if after_text is not None else None
    if b is None or a is None:
        if before_text is not None and after_text is not None:
            out["widened"].append("the file could not be read on one side")
        return out
    (bg, bc), (ag, ac) = b, a
    out["widened"] += [g for g in ag if not _covered(g, bg)]
    out["narrowed"] += [g for g in bg if not _covered(g, ag)]
    for e in COUNTED_EFFECTS:
        if e in ac and e in bc:
            if _count_exceeds(ac[e], bc[e]):
                out["widened"].append(f"{e} count {bc[e]} -> "
                                      f"{'none' if ac[e] is None else ac[e]}")
            elif _count_exceeds(bc[e], ac[e]):
                out["narrowed"].append(f"{e} count {bc[e]} -> {ac[e]}")
    return out


def review_main(argv: list) -> int:
    """velaris review --against REF [path] [--json]"""
    usage = "usage: velaris review --against REF [path] [--json]"
    ref = None
    places, as_json = [], False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--against":
            if i + 1 >= len(argv):
                print(usage, file=sys.stderr)
                return 2
            ref = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            places.append(a)
        i += 1
    if ref is None or len(places) > 1:
        print(usage, file=sys.stderr)
        return 2
    root = places[0] if places else "."
    try:
        got = review(ref, root)
    except (RuntimeError, OSError) as e:
        print(f"velaris review: {e}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(got, indent=2))
        return 0

    def share(v):
        return "no promises" if v is None else f"{v}%"

    print(f"velaris review: {root} against {ref} ({got['commit'][:7]})")
    print(f"  capability surface: {got['surface']['change']}")
    for f in got["surface"]["widened"]:
        print("\n".join("    " + line for line in _finding_lines(f)[:-1]))
    for n in got["surface"]["narrowed"]:
        print(f"    - {n}")
    for f in got["programs_came_to_need_more"]:
        print("\n".join("    " + line for line in _finding_lines(f)[:-1]))
    ps = got["proven_share"]
    print(f"  proven share: {share(ps['before'])} -> {share(ps['after'])}"
          + (" (fell)" if ps["fell"] else "")
          + ("" if got["prover"] else
             "   (no prover here: every promise counts as checked at "
             "runtime, on both sides)"))
    print("  new fallible functions: " + (", ".join(
        f"{x['file']}: {x['function']}" for x in got["new_fallible"])
        or "none"))
    print("  new hosts: " + (", ".join(got["new_hosts"]) or "none"))
    paths = [f"{p} (read)" for p in got["new_paths"]["read"]] + \
        [f"{p} (write)" for p in got["new_paths"]["write"]]
    print("  new paths: " + (", ".join(paths) or "none"))
    print("  new modules: " + (", ".join(got["new_modules"]) or "none"))
    if got["does_not_compile"]:
        print("  no longer compiles, or new and does not: "
              + ", ".join(got["does_not_compile"]))
    d = got["declared"]
    if d["removed"]:
        print(f"  {CAPABILITIES_FILE}: REMOVED - the ratchet is off")
    elif d["added"]:
        print(f"  {CAPABILITIES_FILE}: added")
    elif d["widened"] or d["narrowed"]:
        print(f"  {CAPABILITIES_FILE}: "
              + "; ".join([f"+ {w}" for w in d["widened"]]
                          + [f"- {n}" for n in d["narrowed"]]))
    print(f"risk: {got['risk']}" + (
        " - " + "; ".join(got["risk_because"]) if got["risk_because"]
        else " - nothing widened and the proven share did not fall"))
    return 0


# ---------------------------------------------------------------------------
# 18. CONFORMANCE - velaris-spec's corpus, run against this implementation
#
#     velaris-spec's tests/ directory is a conformance corpus for the
#     capability format: JSON cases an implementation in any language runs
#     its own way (velaris-spec CONFORMANCE.md, tests/README.md). This
#     repository's build_conformance.py writes it from check_sandbox.py,
#     check_library.py and check_ratchet.py. `velaris conformance` reads it
#     back and holds this implementation to it through the doors another
#     implementation would use: the budget parser, the audit, a run under a
#     budget from the command line, and the baseline writer and check. It
#     computes nothing from the case but what the case says, and a case it
#     does not understand fails.
# ---------------------------------------------------------------------------

import shutil
import tempfile

CONFORMANCE_SCHEMA = "velaris.conformance/1"
CORPUS_FORMAT = "velaris.conformance-corpus/1"
# (level, name, the levels a claim at that level needs)
CONFORMANCE_LEVELS = ((1, "Declaration", (1,)), (2, "Enforcement", (1, 2)),
                      (3, "Ratchet", (1, 3)))
_CONF_REFUSAL = re.compile(r"error\[(E\d{3})\]")


class _Skip(Exception):
    """A case that cannot run here: `why`, and whether that is the case's
    own stated requirement (a symbolic link) or a tool this machine lacks
    (jsonschema), which leaves the level unshown."""

    def __init__(self, why: str, required: bool):
        super().__init__(why)
        self.why, self.required = why, required


def _conformance_corpus(given):
    """The corpus directory: --corpus, else $VELARIS_CONFORMANCE_CORPUS,
    else velaris-spec/tests beside the working directory or this file."""
    if given:
        return os.path.abspath(given)
    env = os.environ.get("VELARIS_CONFORMANCE_CORPUS")
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    for where in (os.path.join("velaris-spec", "tests"),
                  os.path.join("..", "velaris-spec", "tests"),
                  os.path.join(here, "..", "velaris-spec", "tests")):
        if os.path.isfile(os.path.join(where, "index.json")):
            return os.path.abspath(where)
    return None


def _conf_files(root: str, files: dict) -> None:
    """Write a case's files under root; None deletes one."""
    for name, text in files.items():
        path = os.path.join(root, *name.split("/"))
        if text is None:
            if os.path.exists(path):
                os.unlink(path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def _conf_validator(schema_path: str):
    """A JSON Schema validator for one of velaris-spec's schemas, or None
    when jsonschema is not installed."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return None
    with open(schema_path, encoding="utf-8") as fh:
        return Draft202012Validator(json.load(fh))


def _conf_invalid(validator, doc, what: str, wrong: list) -> str:
    """The case's verdict: what is wrong, and then whether the document
    fails its schema. With no validator a case that is otherwise right is
    not shown right - it is skipped, and its level left unshown."""
    if wrong:
        return "; ".join(wrong)
    if validator is None:
        raise _Skip(f"jsonschema is not installed, so the {what} was not "
                    f"validated against velaris-spec's schema", False)
    return "; ".join(
        f"{what} fails the schema at "
        f"{'/'.join(str(p) for p in e.absolute_path) or 'the top'}: "
        f"{e.message}" for e in list(validator.iter_errors(doc))[:3])


# ---- level 1 ---------------------------------------------------------------

def _conf_budget_shape(b: "Budget") -> dict:
    out = {"effects": sorted(b.effects)}
    if "ffi" in b.effects:
        out["ffi"] = "any" if b.modules is None else sorted(b.modules)
    if "fs" in b.effects:
        out["fs"] = "any" if b.fs is None else [
            {"direction": d, "path": p} for d, p in b.fs]
    if "net" in b.effects:
        out["net"] = "any" if b.net is None else [
            {"host": h, "port": p} for h, p in b.net]
    out["counts"] = {e: n for e, n in b.limits.items()
                     if n is not None and e in b.effects}
    return out


def _conf_resolved(shape: dict) -> dict:
    """Grants with every path resolved as velaris-spec 5.1 says, and each
    scoped list as a set: the spelling of a path and the order of grants
    are not what a budget means."""
    out = dict(shape)
    if isinstance(out.get("fs"), list):
        out["fs"] = sorted({(g["direction"], None if g["path"] is None else
                             os.path.normcase(os.path.realpath(g["path"])))
                            for g in out["fs"]}, key=repr)
    if isinstance(out.get("net"), list):
        out["net"] = sorted({(g["host"], g["port"]) for g in out["net"]},
                            key=repr)
    return out


def _conf_budget(case: dict, ctx: dict) -> str:
    given, want = case["input"], case["expect"]
    try:
        budget = _budget_from(
            {given["allow"]} if "allow" in given else None,
            {n.strip() for n in given["deny"].split(",")}
            if "deny" in given else None)
    except ValueError as e:
        if want["valid"]:
            return f"refused ({e}); it must parse"
        return ""
    got = _conf_budget_shape(budget)
    if not want["valid"]:
        return f"parsed, to {got}; it must be refused"
    if _conf_resolved(got) != _conf_resolved(want["grants"]):
        return f"parsed to {got}, not {want['grants']}"
    return ""


def _conf_audit(case: dict, ctx: dict) -> str:
    given, want = case["input"], case["expect"]
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        _conf_files(box, given["files"])
        entry = given["entry"]
        doc = audit(given["files"][entry],
                    path=os.path.join(box, *entry.split("/"))).as_dict()
    finally:
        shutil.rmtree(box, ignore_errors=True)
    wrong = []
    if doc.get("schema") != AUDIT_SCHEMA:
        wrong.append(f"schema is {doc.get('schema')!r}")
    if doc["effects"] != sorted(set(doc["effects"])) or not set(
            doc["effects"]) <= set(ALL_EFFECTS):
        wrong.append(f"effects {doc['effects']} is not a sorted subset of "
                     f"{list(ALL_EFFECTS)}")
    try:
        Budget.parse(doc["safe_command"].split("--allow ", 1)[1])
    except (ValueError, IndexError) as e:
        wrong.append(f"safe_command {doc['safe_command']!r} does not "
                     f"parse: {e}")
    if doc["ok"] != want["ok"]:
        wrong.append(f"ok is {doc['ok']}"
                     + (f": {[p['code'] for p in doc['problems']]}"
                        if doc["problems"] else ""))
    elif not want["ok"]:
        codes = {p["code"] for p in doc["problems"]}
        wrong += [f"no {c} among the problems {sorted(codes)}"
                  for c in want["problems_include"] if c not in codes]
    else:
        # `secrets` was added to velaris.audit/1 in 6.0 and is compared
        # only where a case names it, so the cases written before it say
        # nothing about a field that did not exist (velaris-spec 8.6)
        for key in ("effects", "ffi_modules", "ffi_any", "fs_paths",
                    "net_hosts", "safe_command", "secrets"):
            if key in want and doc.get(key) != want[key]:
                wrong.append(f"{key} is {doc.get(key)!r}, not {want[key]!r}")
        fns = [{"name": f["name"], "effects": f["effects"],
                "can_fail": f["can_fail"]} for f in doc["functions"]]
        if fns != want["functions"]:
            wrong.append(f"functions are {fns}, not {want['functions']}")
    return _conf_invalid(ctx["audit_schema"], doc, "audit", wrong)


# ---- level 2 ---------------------------------------------------------------

def _conf_servers() -> tuple:
    """The corpus's two local HTTP servers (tests/README.md): /go on the
    first answers 302 to http://localhost:PORT_B/landed; every other path
    on either answers 200 "hello"."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    ports = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/go"):
                self.send_response(302)
                self.send_header("Location",
                                 f"http://localhost:{ports['b']}/landed")
                self.end_headers()
                return
            body = b"hello"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    servers = (HTTPServer(("127.0.0.1", 0), Handler),
               HTTPServer(("127.0.0.1", 0), Handler))
    ports["a"], ports["b"] = (servers[0].server_address[1],
                              servers[1].server_address[1])
    for srv in servers:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return servers, ports["a"], ports["b"]


def _conf_run(case: dict, ctx: dict) -> str:
    import subprocess
    given, want = case["input"], case["expect"]
    if given.get("fixture") != "sandbox":
        return f"this runner has no fixture {given.get('fixture')!r}"
    root = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        data = os.path.join(root, "box", "data")
        out = os.path.join(root, "box", "out")
        os.makedirs(data)
        os.makedirs(out)
        with open(os.path.join(data, "a.txt"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("inside\n")
        with open(os.path.join(root, "outside.txt"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("outside\n")
        if "symlink" in case["requires"]:
            try:
                os.symlink(os.path.join(root, "outside.txt"),
                           os.path.join(data, "link.txt"))
            except (OSError, NotImplementedError):
                raise _Skip("needs a symbolic link, and this system would "
                            "not make one", True)
        slash = root.replace(os.sep, "/")
        values = (("{ROOT}", slash), ("{DATA}", slash + "/box/data"),
                  ("{OUT}", slash + "/box/out"),
                  ("{OUTSIDE}", slash + "/outside.txt"),
                  ("{PORT_A}", str(ctx["ports"][0])),
                  ("{PORT_B}", str(ctx["ports"][1])))

        def fill(text):
            for key, value in values:
                text = text.replace(key, value)
            return text

        prog = os.path.join(root, "case.vel")
        with open(prog, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(fill(given["source"]))
        cmd = [sys.executable, os.path.abspath(__file__), prog]
        if "allow" in given:
            cmd += ["--allow", fill(given["allow"])]
        if "deny" in given:
            cmd += ["--deny", fill(given["deny"])]
        cmd += [fill(a) for a in given.get("args", [])]
        try:
            done = subprocess.run(cmd, cwd=root, capture_output=True,
                                  text=True, encoding="utf-8",
                                  errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            return "the run did not end in 120 seconds"
        stdout, stderr = done.stdout or "", done.stderr or ""
        found = _CONF_REFUSAL.search(stderr)
        code = found.group(1) if found else None
        wrong = []
        if want["outcome"] == "refused":
            if done.returncode == 0 or code != want["code"]:
                wrong.append(f"expected a refusal with {want['code']}, got "
                             + (f"{code}" if code else
                                f"exit {done.returncode} and no refusal"))
            wrong += [f"it printed {w!r}, so it got past the refusal"
                      for w in want.get("stdout_excludes", [])
                      if fill(w) in stdout]
            wrong += [f"{fill(p)} exists" for p in want.get(
                "must_not_exist", []) if os.path.exists(fill(p))]
        elif want["outcome"] == "completed":
            if done.returncode != 0:
                wrong.append(f"exit {done.returncode}"
                             + (f", refused with {code}" if code else "")
                             + f": {(stderr or stdout).strip()[:160]}")
        else:
            return f"this runner has no outcome {want['outcome']!r}"
        wrong += [f"it did not print {fill(s)!r}"
                  for s in want.get("stdout_includes", [])
                  if fill(s) not in stdout]
        return "; ".join(wrong)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- level 3 ---------------------------------------------------------------

def _conf_edit(doc: dict, edit) -> dict:
    """A baseline as a person edits it (tests/README.md): each key given
    under surface and under a program's entry replaced, and
    velaris_version when given."""
    doc = json.loads(json.dumps(doc))
    if not edit:
        return doc
    if "velaris_version" in edit:
        doc["velaris_version"] = edit["velaris_version"]
    doc["surface"].update(edit.get("surface", {}))
    for file, fields in edit.get("programs", {}).items():
        for p in doc["programs"]:
            if p["file"] == file:
                p.update(fields)
    return doc


def _conf_write_baseline(target: str) -> None:
    doc = capabilities_document(capability_scan(target, use_git=False))
    with open(os.path.join(target, CAPABILITIES_FILE), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(capabilities_text(doc))


def _conf_ratchet(target: str) -> tuple:
    """(verdict, widenings as the corpus writes them) of the check."""
    path = os.path.join(target, CAPABILITIES_FILE)
    if not os.path.exists(path):
        return "cannot-compare", []
    try:
        baseline = read_capabilities(path)
    except ValueError:
        return "cannot-compare", []
    result = capabilities_compare(baseline,
                                  capability_scan(target, use_git=False))
    found = []
    for f in result["findings"]:
        if f["kind"] == "grant":
            found.append({"kind": "grant", "grant": f["grant"],
                          "rules": f["rules"], "programs": sorted(
                              q["file"] for q in f["programs"])})
        elif f["kind"] == "count":
            found.append({"kind": "count", "effect": f["effect"],
                          "program": f["file"], "current": f["current"],
                          "rules": f["rules"]})
        else:
            found.append({"kind": "function", "program": f["file"],
                          "function": f["function"], "gained": f["gained"],
                          "rules": f["rules"]})
    return ("widened" if result["widened"] else "pass"), found


def _conf_verdict_wrong(want: dict, verdict: str, found: list) -> str:
    if verdict != want["verdict"]:
        return (f"{verdict}, not {want['verdict']}"
                + (f": {found}" if found else ""))
    if verdict == "cannot-compare":
        return ""

    def key(x):
        return json.dumps(x, sort_keys=True)
    if sorted(found, key=key) != sorted(want["widenings"], key=key):
        return f"widenings {found}, not {want['widenings']}"
    return ""


def _conf_check(case: dict, ctx: dict) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        base = given["baseline"]
        if base.get("from_tree"):
            doc = capabilities_document(capability_scan(target,
                                                         use_git=False))
            with open(os.path.join(target, CAPABILITIES_FILE), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(capabilities_text(_conf_edit(doc,
                                                      base.get("edit"))))
        elif "text" in base:
            with open(os.path.join(target, CAPABILITIES_FILE), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(base["text"])
        elif not base.get("absent"):
            return f"this runner cannot read the baseline {base}"
        _conf_files(box, given["change"])
        return _conf_verdict_wrong(case["expect"], *_conf_ratchet(target))
    finally:
        shutil.rmtree(box, ignore_errors=True)


def _conf_sequence(case: dict, ctx: dict) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given.get("root", ".").split("/"))
        _conf_write_baseline(target)
        path = os.path.join(target, CAPABILITIES_FILE)
        for n, (st, want) in enumerate(zip(given["steps"],
                                           case["expect"]["steps"]), 1):
            _conf_files(box, st.get("change") or {})
            if st.get("edit"):
                doc = _conf_edit(read_capabilities(path), st["edit"])
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(capabilities_text(doc))
            if st.get("rewrite"):
                _conf_write_baseline(target)
            if st.get("delete_baseline") and os.path.exists(path):
                os.unlink(path)
            wrong = _conf_verdict_wrong(want, *_conf_ratchet(target))
            if wrong:
                return f"step {n} ({st['description']}): {wrong}"
        if len(given["steps"]) != len(case["expect"]["steps"]):
            return "the case has a different number of steps and verdicts"
        return ""
    finally:
        shutil.rmtree(box, ignore_errors=True)


def _conf_derive(case: dict, ctx: dict) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        _conf_write_baseline(target)
        with open(os.path.join(target, CAPABILITIES_FILE),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
    finally:
        shutil.rmtree(box, ignore_errors=True)
    got = {"surface": doc["surface"], "programs": doc["programs"]}
    wrong = [] if got == case["expect"] else [
        f"wrote {json.dumps(got)}"]
    return _conf_invalid(ctx["capabilities_schema"], doc, "baseline", wrong)


def _conf_write_guard(case: dict, ctx: dict) -> str:
    import contextlib
    import io as _io
    if case["expect"] != {"refuses": True, "unchanged": True}:
        return f"this runner knows no write-guard outcome {case['expect']}"
    given = case["input"]
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        quiet = _io.StringIO()
        with contextlib.redirect_stdout(quiet), \
                contextlib.redirect_stderr(quiet):
            first = capabilities_main(["init", target])
            with open(os.path.join(target, CAPABILITIES_FILE),
                      encoding="utf-8") as fh:
                before = fh.read()
            _conf_files(box, given["change"])
            again = capabilities_main(["init", target])
        with open(os.path.join(target, CAPABILITIES_FILE),
                  encoding="utf-8") as fh:
            after = fh.read()
    finally:
        shutil.rmtree(box, ignore_errors=True)
    if first != 0:
        return "the first baseline was not written"
    if again == 0 or after != before:
        return "it replaced the baseline without being asked to"
    return ""


def _conf_covers(case: dict, ctx: dict) -> str:
    try:
        got = _covers(_grant_parts(case["input"]["grant"]),
                      _grant_parts(case["input"]["other"]))
    except ValueError as e:
        return f"not a baseline grant: {e}"
    return "" if got == case["expect"]["covers"] else f"covers is {got}"


def _conf_reduce(case: dict, ctx: dict) -> str:
    got = _reduce_grants(case["input"]["grants"])
    return "" if got == case["expect"]["grants"] else f"reduced to {got}"


def _conf_bound(case: dict, ctx: dict) -> str:
    box = tempfile.mkdtemp(prefix="velaris-conformance-")
    try:
        path = os.path.join(box, "bound.vel")
        _conf_files(box, {"bound.vel": case["input"]["source"]})
        funcs, _ = load_program(path)
        bounds, _ = _operation_bounds(funcs)
    except VelarisError as e:
        return f"does not compile: {e.message}"
    finally:
        shutil.rmtree(box, ignore_errors=True)
    got = {e: _as_count(n) for e, n in
           bounds[case["input"]["function"]].items()}
    return "" if got == case["expect"] else f"bound {got}"


_CONFORMANCE_KINDS = (("budget", _conf_budget), ("audit", _conf_audit),
                      ("run", _conf_run), ("derive", _conf_derive),
                      ("check", _conf_check), ("sequence", _conf_sequence),
                      ("write-guard", _conf_write_guard),
                      ("covers", _conf_covers), ("reduce", _conf_reduce),
                      ("bound", _conf_bound))


def conformance(corpus: str, levels=(1, 2, 3)) -> dict:
    """Run velaris-spec's conformance corpus at `corpus` (its tests/
    directory) against this implementation; the velaris.conformance/1
    report. ValueError when the corpus cannot be read."""
    try:
        with open(os.path.join(corpus, "index.json"), encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read {corpus}/index.json: {e}")
    if index.get("format") != CORPUS_FORMAT:
        raise ValueError(f"{corpus}/index.json is not {CORPUS_FORMAT}")
    schemas = os.path.join(corpus, "..", "schemas")
    ctx = {"audit_schema": _conf_validator(os.path.join(
               schemas, "velaris.audit.1.schema.json")),
           "capabilities_schema": _conf_validator(os.path.join(
               schemas, "velaris.capabilities.1.schema.json"))}
    kinds = dict(_CONFORMANCE_KINDS)
    wanted = sorted({n for lvl, _, needs in CONFORMANCE_LEVELS
                     if lvl in levels for n in needs})
    entries = [e for e in index["cases"] if e["level"] in wanted]
    servers = None
    if 2 in wanted:
        servers, port_a, port_b = _conf_servers()
        ctx["ports"] = (port_a, port_b)
    results = []
    here = os.getcwd()
    scratch = tempfile.mkdtemp(prefix="velaris-conformance-cwd-")
    os.chdir(scratch)            # relative paths in budgets resolve here, and
    try:                         # no proof cache lands where it was run
        for e in entries:
            row = {"id": e["id"], "level": e["level"], "kind": e["kind"],
                   "known_limit": bool(e.get("known_limit"))}
            try:
                with open(os.path.join(corpus, *e["file"].split("/")),
                          encoding="utf-8") as fh:
                    case = json.load(fh)
                if case["id"] != e["id"] or case["kind"] not in kinds:
                    raise ValueError(f"this runner cannot run "
                                     f"{case.get('id')!r} of kind "
                                     f"{case.get('kind')!r}")
                wrong = kinds[case["kind"]](case, ctx)
                row.update(result="fail" if wrong else "pass",
                           detail=wrong)
            except _Skip as s:
                row.update(result="skip", detail=s.why, required=s.required)
            except Exception as x:           # a case that crashes the runner
                row.update(result="fail",    # fails; it never passes
                           detail=f"{type(x).__name__}: {x}")
            results.append(row)
    finally:
        os.chdir(here)
        shutil.rmtree(scratch, ignore_errors=True)
        for srv in servers or ():
            srv.shutdown()
    summary = {}
    for lvl, name, _ in CONFORMANCE_LEVELS:
        if lvl not in wanted:
            continue
        rows = [r for r in results if r["level"] == lvl]
        summary[str(lvl)] = {
            "name": name, "cases": len(rows),
            "passed": sum(r["result"] == "pass" for r in rows),
            "failed": sum(r["result"] == "fail" for r in rows),
            "skipped": sum(r["result"] == "skip" for r in rows),
            "unshown": sum(r["result"] == "skip" and not r.get("required")
                           for r in rows)}
    shown = [lvl for lvl, _, needs in CONFORMANCE_LEVELS if lvl in levels
             and all(summary[str(n)]["failed"] == 0
                     and summary[str(n)]["unshown"] == 0 for n in needs)]
    return {"schema": CONFORMANCE_SCHEMA,
            "implementation": {"name": "velaris-lang", "version": VERSION},
            "corpus": corpus, "levels_run": wanted,
            "levels": summary, "conformant": shown,
            "results": results}


def _conformance_verdict(report: dict, asked) -> str:
    names = dict((lvl, f"L{lvl}") for lvl, _, _ in CONFORMANCE_LEVELS)
    shown = [names[n] for n in report["conformant"]]
    missing = [names[n] for n in asked if n not in report["conformant"]]
    skipped = [r for r in report["results"] if r["result"] == "skip"]
    said = f"Velaris {VERSION} "
    if not missing:
        said += "is conformant at " + " and ".join(
            [", ".join(shown[:-1]), shown[-1]] if len(shown) > 1 else shown)
    else:
        said += "is NOT shown conformant at " + ", ".join(missing) + (
            "; conformant at " + ", ".join(shown) if shown else "")
    if skipped:
        said += (f" ({len(skipped)} case(s) not run here: "
                 + "; ".join(sorted({r['detail'] for r in skipped})) + ")")
    return said


def conformance_main(argv: list) -> int:
    """velaris conformance [--level 1|2|3] [--json] [--corpus DIR]"""
    usage = ("usage: velaris conformance [--level 1|2|3] [--json] "
             "[--corpus DIR]")
    levels, as_json, given = (1, 2, 3), False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--level", "--corpus") and i + 1 < len(argv):
            if a == "--level":
                if argv[i + 1] not in ("1", "2", "3"):
                    print(usage, file=sys.stderr)
                    return 2
                levels = (int(argv[i + 1]),)
            else:
                given = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        else:
            print(usage, file=sys.stderr)
            return 2
        i += 1
    corpus = _conformance_corpus(given)
    if corpus is None or not os.path.isfile(os.path.join(corpus,
                                                         "index.json")):
        print("velaris conformance: no corpus found. It is velaris-spec's "
              "tests/ directory: clone https://github.com/gowrishankar-infra/"
              "velaris-spec beside this directory, or pass --corpus "
              "velaris-spec/tests", file=sys.stderr)
        return 2
    try:
        report = conformance(corpus, levels)
    except ValueError as e:
        print(f"velaris conformance: {e}", file=sys.stderr)
        return 2
    report["verdict"] = _conformance_verdict(report, levels)
    ok = all(n in report["conformant"] for n in levels)
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if ok else 1
    total = sum(v["cases"] for v in report["levels"].values())
    print(f"velaris conformance: velaris-spec corpus at {corpus}, "
          f"{total} case(s) run")
    for lvl, v in sorted(report["levels"].items()):
        extra = (f"  {v['skipped']} skipped" if v["skipped"] else "")
        print(f"  L{lvl} {v['name']:<12} {v['cases']:>4} cases  "
              f"{v['passed']:>4} passed  {v['failed']:>3} failed{extra}")
    for r in report["results"]:
        if r["result"] == "fail":
            print(f"FAIL  {r['id']}: {r['detail'][:400]}")
    for r in report["results"]:
        if r["result"] == "skip":
            print(f"skip  {r['id']}: {r['detail']}")
    print(report["verdict"])
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# 19. ATTESTATION - the audit, bound to the bytes it describes
#
#     `velaris attest` wraps velaris.audit/1 in an in-toto Statement v1 of
#     the predicate type velaris-spec 8.5 defines: the audited file and
#     every file it loads are the subjects, by sha256, and the predicate's
#     audit is audit()'s own output - not a copy recomputed here - so the
#     attestation and the audit cannot disagree, and the attestation says
#     nothing the audit does not. What the audit could not determine it
#     says so in its own fields (ffi_any, read_any, any, a null count, ok
#     false), and the Statement carries them as they are. Nothing here
#     signs: EMBEDDING.md shows how, with cosign or sigstore-python, and
#     the release workflow does it for one example program.
# ---------------------------------------------------------------------------

INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
CAPABILITY_PREDICATE_TYPE = ("https://gowrishankar-infra.github.io/"
                             "velaris-lang/capability/v1")
CAPABILITY_SPEC = "velaris-spec 0.5"


def _attested_at() -> str:
    """When the audit was made, RFC 3339 in UTC to the second - from
    SOURCE_DATE_EPOCH when it is set, so a build that fixes that gets the
    same Statement twice."""
    import datetime
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    when = (datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
            if epoch.isdigit() else
            datetime.datetime.now(datetime.timezone.utc))
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_of(path: str) -> str:
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _subject_name(path: str, entry: str, entry_name: str) -> str:
    """How a Statement names a file the audited program loads: in the
    terms the audited file was named in, or <stdlib>/NAME for the
    standard library this Velaris ships, whose place on disk is this
    machine's business."""
    import posixpath
    full = os.path.abspath(path)
    base = os.path.dirname(os.path.abspath(entry))
    std = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdlib")
    try:
        rel = os.path.relpath(full, base).replace(os.sep, "/")
    except ValueError:                     # another drive, on Windows
        rel = None
    if rel is not None and rel != ".." and not rel.startswith("../"):
        return posixpath.normpath(posixpath.join(
            posixpath.dirname(entry_name), rel))
    if full.startswith(std + os.sep):
        return "<stdlib>/" + os.path.relpath(full, std).replace(os.sep, "/")
    if rel is not None:
        return posixpath.normpath(posixpath.join(
            posixpath.dirname(entry_name), rel))
    return full.replace(os.sep, "/")


def attest_statement(path: str, name: str | None = None) -> dict:
    """The in-toto Statement for one .vel file (velaris-spec 8.5): the
    file first among the subjects, then each file it imports, each by
    the sha256 of its bytes; the predicate, audit() of those bytes.
    ValueError when the file is not UTF-8, or changed while it was being
    attested."""
    import hashlib
    import posixpath
    name = name or posixpath.normpath(path.replace(os.sep, "/"))
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not UTF-8 text")
    entry_digest = hashlib.sha256(raw).hexdigest()

    def imports() -> list:
        read: list = []
        try:
            load_program(path, source, loaded=read)
        except Exception:          # the audit reports why; what could be
            pass                   # read is still what it read
        out, seen = [], {os.path.abspath(path)}
        for p in read:
            if os.path.abspath(p) not in seen:
                seen.add(os.path.abspath(p))
                out.append((p, _sha256_of(p)))
        return out

    before = imports()
    doc = audit(source, path=path).as_dict()
    # the audit read the imported files from disk; if one changed while it
    # did, a digest would name bytes the audit may not have read
    if imports() != before or _sha256_of(path) != entry_digest:
        raise ValueError(f"{path}, or a file it imports, changed while it "
                         f"was being attested; attest it again")
    subjects = [{"name": name, "digest": {"sha256": entry_digest}}]
    subjects += [{"name": _subject_name(p, path, name),
                  "digest": {"sha256": d}} for p, d in before]
    return {"_type": INTOTO_STATEMENT_TYPE,
            "subject": subjects,
            "predicateType": CAPABILITY_PREDICATE_TYPE,
            "predicate": {"producer": {"name": "velaris-lang",
                                       "uri": REPOSITORY},
                          "specification": CAPABILITY_SPEC,
                          "auditedAt": _attested_at(),
                          "audit": doc}}


def attest(path: str) -> list:
    """One in-toto Statement per .vel file: the file itself, or every
    .vel file under a directory, as `velaris capabilities` finds them
    (.git and what git ignores left out). ValueError when there is
    nothing to attest."""
    import posixpath
    if os.path.isdir(path):
        base = posixpath.normpath(path.replace(os.sep, "/"))
        files = _capability_files(path)
        if not files:
            raise ValueError(f"no .vel file under {path}")
        return [attest_statement(os.path.join(path, *rel.split("/")),
                                 rel if base == "." else f"{base}/{rel}")
                for rel in files]
    if not os.path.isfile(path):
        raise ValueError(f"{path}: no such file or directory")
    return [attest_statement(path)]


def attest_main(argv: list) -> int:
    """velaris attest <path> [--output FILE] [--json]"""
    usage = "usage: velaris attest <path> [--output FILE] [--json]"
    places, output, as_json = [], None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--output" and i + 1 < len(argv):
            output = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            places.append(a)
        i += 1
    if len(places) != 1:
        print(usage, file=sys.stderr)
        return 2
    target = places[0]
    try:
        statements = attest(target)
    except (ValueError, OSError) as e:
        print(f"velaris attest: {e}", file=sys.stderr)
        return 2
    # a file gives one Statement; a directory gives one per file, one to a
    # line (JSON Lines; an in-toto Bundle is the same, of signed envelopes)
    if os.path.isdir(target):
        text = "".join(json.dumps(s, ensure_ascii=False,
                                  separators=(",", ":")) + "\n"
                       for s in statements)
    else:
        text = json.dumps(statements[0], indent=2, ensure_ascii=False) + "\n"
    if output:
        with open(output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    if as_json:
        sys.stdout.write(text)
        return 0
    print(f"velaris attest: {len(statements)} in-toto Statement(s) of "
          f"{CAPABILITY_PREDICATE_TYPE}")
    for s in statements:
        a = s["predicate"]["audit"]
        first = s["subject"][0]
        state = ("compiles" if a["ok"] else
                 "does not compile: " + ", ".join(
                     sorted({p["code"] for p in a["problems"]})))
        print(f"  {first['name']}  sha256:{first['digest']['sha256'][:16]}"
              f"  {state}")
        print(f"      effects: {', '.join(a['effects']) or 'none'}"
              + ("; a module named while running (ffi_any)"
                 if a.get("ffi_any") else ""))
        for extra in s["subject"][1:]:
            print(f"      also read: {extra['name']}  "
                  f"sha256:{extra['digest']['sha256'][:16]}")
    print(f"written to {output}" if output else
          "not written: pass --output FILE, or --json to print it")
    return 0


# ---------------------------------------------------------------------------
# 20. WHAT AN UPGRADE GAINED - one dependency, two versions
#
#     `velaris deps-diff <package> <old> <new>` reads both versions of a
#     dependency and reports what the newer one can do that the older one
#     could not. For the .vel files a version holds, that is section 17's
#     comparison with the older version as the baseline: effects, hosts,
#     paths, modules, operation counts and functions, in the shape
#     `capabilities check` reports them. For anything else a version
#     holds it is almost nothing, and the report says so. What Python or
#     JavaScript code can do is not written in its text in any form that
#     can be checked, so no effect is inferred from it; what can be read
#     is read - the install-time scripts a version declares and the
#     dependencies it declares - and the capability surface is reported
#     as unknown.
#
#     `velaris deps-diff --against REF` does the same for every dependency
#     the lockfiles changed since REF upgrade, and `--comment` puts the
#     answer in one pull-request comment that later runs edit.
# ---------------------------------------------------------------------------

DEPS_DIFF_SCHEMA = "velaris.deps-diff/1"
DEPS_LOCKFILES_SCHEMA = "velaris.deps-diff-lockfiles/1"
DEPS_COMMENT_MARKER = "<!-- velaris-deps-diff-comment -->"
DEPS_SOURCES = ("pypi", "npm", "git", "dir")
_DEPS_ARTIFACT_LIMIT = 64 << 20        # bytes read for one archive
_DEPS_TREE_LIMIT = 256 << 20           # bytes unpacked from one version
_DEPS_MAX_UPGRADES = 30                # upgrades compared in one review
_NPM_INSTALL_SCRIPTS = ("preinstall", "install", "postinstall")
_CODE_LANGUAGES = (
    ((".py", ".pyw"), "Python"),
    ((".pyc", ".pyo"), "compiled Python"),
    ((".js", ".mjs", ".cjs", ".jsx"), "JavaScript"),
    ((".ts", ".mts", ".cts", ".tsx"), "TypeScript"),
    ((".so", ".pyd", ".dll", ".dylib", ".node"), "native libraries"),
    ((".wasm",), "WebAssembly"),
    ((".sh", ".bash", ".bat", ".cmd", ".ps1"), "shell scripts"),
    ((".exe",), "executables"),
)
# lockfiles by name: (format, ecosystem). The second set is recognised as
# a lockfile and reported as changed, and nothing in it is read.
_LOCKFILES = {
    "package-lock.json": ("npm-lock", "npm"),
    "npm-shrinkwrap.json": ("npm-lock", "npm"),
    "Pipfile.lock": ("pipfile-lock", "pypi"),
    "poetry.lock": ("toml-packages", "pypi"),
    "uv.lock": ("toml-packages", "pypi"),
    "pdm.lock": ("toml-packages", "pypi"),
    "velaris.lock": ("velaris-lock", "velaris"),
}
_LOCKFILES_NOT_READ = ("yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
                       "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock",
                       "packages.lock.json", "gradle.lockfile",
                       "Package.resolved", "mix.lock", "pubspec.lock")


class DepsError(Exception):
    """A dependency, or a version of it, that could not be read."""


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _ver_key(v: str) -> tuple:
    """A version as something to sort by: numbers as numbers."""
    return tuple((0, int(x)) if x.isdigit() else (1, x)
                 for x in re.split(r"[.+\-_]", str(v)) if x != "")


def _deps_source(package: str) -> tuple:
    """(kind, where) for a package argument: pypi:NAME, npm:NAME, git:URL
    or git:PATH, dir:PATH - and @scope/name, which only npm writes."""
    kind, sep, where = package.partition(":")
    if sep and kind in DEPS_SOURCES and where and not where.startswith("-"):
        return kind, where
    if package.startswith("@") and package.count("/") == 1:
        return "npm", package
    raise DepsError(f"'{package}' does not say where to read it: write "
                    f"pypi:NAME, npm:NAME, git:URL (or a path to a git "
                    f"repository), or dir:PATH, a directory holding one "
                    f"subdirectory per version")


def _deps_get(url: str, limit: int = _DEPS_ARTIFACT_LIMIT,
              accept: str | None = None):
    """The bytes at url, or None when the server says it has nothing
    there (404, 410); DepsError for anything else, and for a body larger
    than limit."""
    import urllib.error
    import urllib.request
    headers = {"User-Agent": f"velaris/{VERSION} (deps-diff)"}
    if accept:
        headers["Accept"] = accept
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        raise DepsError(f"{url}: HTTP {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise DepsError(f"{url}: {getattr(e, 'reason', None) or e}")
    if len(data) > limit:
        raise DepsError(f"{url} is larger than {limit >> 20} MB, which "
                        f"deps-diff does not read")
    return data


_RESERVED_NAMES = frozenset({"con", "prn", "aux", "nul",
                             *(f"com{i}" for i in range(1, 10)),
                             *(f"lpt{i}" for i in range(1, 10))})


def _clean_tree(files: dict, strip_top: bool) -> dict:
    """'/'-separated paths, none climbing out, none absolute; with the one
    top-level directory every path shares removed when strip_top (an
    sdist's name-1.0/, an npm tarball's package/). A part holding ':' is
    left out wherever it is - on Windows `a/C:x` joined under a directory
    is a path on drive C - and so is a device name Windows reserves."""
    out = {}
    for raw, body in files.items():
        text = raw.replace("\\", "/")
        parts = [p for p in text.split("/") if p not in ("", ".")]
        if not parts or text.startswith("/") or ".." in parts or any(
                ":" in p or p.split(".")[0].lower() in _RESERVED_NAMES
                for p in parts):
            continue
        out["/".join(parts)] = body
    if strip_top and out and all("/" in p for p in out) \
            and len({p.split("/", 1)[0] for p in out}) == 1:
        out = {p.split("/", 1)[1]: b for p, b in out.items()}
    return out


def _archive_files(data: bytes, name: str, strip_top: bool = True) -> dict:
    """{path: bytes} for the regular files of a tar (gzip or not), zip or
    wheel archive. Links are not followed and are left out."""
    import io
    import tarfile
    import zipfile
    found: dict = {}
    total = 0
    try:
        if name.lower().endswith((".zip", ".whl")):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    total += info.file_size
                    if total > _DEPS_TREE_LIMIT:
                        raise DepsError(f"{name} unpacks to more than "
                                        f"{_DEPS_TREE_LIMIT >> 20} MB")
                    found[info.filename] = z.read(info)
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as t:
                for m in t.getmembers():
                    if not m.isfile():
                        continue
                    total += m.size
                    if total > _DEPS_TREE_LIMIT:
                        raise DepsError(f"{name} unpacks to more than "
                                        f"{_DEPS_TREE_LIMIT >> 20} MB")
                    fh = t.extractfile(m)
                    if fh is not None:
                        found[m.name] = fh.read()
    except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError,
            ValueError) as e:
        raise DepsError(f"{name} is not an archive deps-diff can read ({e})")
    return _clean_tree(found, strip_top)


def _code_counts(files: dict) -> dict:
    """{language: number of files} for the code a version holds that is
    not Velaris. Type declarations (.d.ts) are not code."""
    out: dict = {}
    for p in files:
        low = p.lower()
        if low.endswith((".d.ts", ".d.mts", ".d.cts")):
            continue
        ext = os.path.splitext(low)[1]
        for suffixes, language in _CODE_LANGUAGES:
            if ext in suffixes:
                out[language] = out.get(language, 0) + 1
    return dict(sorted(out.items()))


def _describe_code(counts: dict) -> str:
    return ", ".join(f"{lang} ({n} file{'' if n == 1 else 's'})"
                     for lang, n in counts.items())


def _toml_value(text: str, table: str, key: str):
    """A string, or a list of strings, written as `key = ...` under
    [table] - the part of TOML pyproject.toml uses for these keys - or
    None. Not a TOML parser; a value in any other form is None."""
    strings = r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\''
    current = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if s.startswith("["):
            current = s.strip("[] \t")
            continue
        if current != table:
            continue
        m = re.match(r'^"?([A-Za-z0-9_.-]+)"?\s*=\s*(.*)$', s)
        if not m or m.group(1) != key:
            continue
        rest = m.group(2)
        if rest.startswith("["):
            buf = rest

            def depth(b):
                bare = re.sub(strings, "", b)
                return bare.count("[") - bare.count("]")
            while depth(buf) > 0 and i < len(lines):
                buf += "\n" + lines[i]
                i += 1
            return [a or b for a, b in re.findall(strings, buf)]
        sm = re.match(strings, rest)
        return (sm.group(1) or sm.group(2)) if sm else None
    return None


def _pep508_name(requirement: str):
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return re.sub(r"[-_.]+", "-", m.group(1)).lower() if m else None


def _requirements_map(reqs) -> dict:
    """{normalised name: the requirement text(s)} for PEP 508 strings."""
    out: dict = {}
    for r in reqs or []:
        if not isinstance(r, str):
            continue
        name = _pep508_name(r)
        if name:
            out.setdefault(name, []).append(r.strip())
    return {n: " | ".join(sorted(v)) for n, v in sorted(out.items())}


def _named_files(command: str, files: dict) -> dict:
    """{path: sha256} for the files of a version an install command names
    - `node setup.js`, `sh ./install.sh` - as node or a shell would find
    them in the package's own directory. What the command does is not
    derived; that the file it runs changed is a fact."""
    out = {}
    for token in re.split(r"[\s;&|()<>`'\"=]+", command):
        t = token[2:] if token.startswith("./") else token
        for cand in (t, t + ".js", t + ".cjs", t + ".mjs"):
            if cand and cand in files:
                out[cand] = _sha256(files[cand])
                break
    return dict(sorted(out.items()))


def _npm_hooks(manifest: dict, files: dict, source: str) -> list:
    """The scripts npm runs when it installs a package from a registry:
    preinstall, install and postinstall - and `node-gyp rebuild`, npm's
    install script for a package with a binding.gyp that names no install
    or preinstall script of its own - each marked with where it was read."""
    scripts = manifest.get("scripts")
    scripts = scripts if isinstance(scripts, dict) else {}
    hooks = []
    for name in _NPM_INSTALL_SCRIPTS:
        cmd = scripts.get(name)
        if isinstance(cmd, str) and cmd.strip():
            hooks.append({"kind": "npm-script", "name": name, "command": cmd,
                          "source": source,
                          "files": _named_files(cmd, files)})
    if "binding.gyp" in files and not any(
            isinstance(scripts.get(n), str) and scripts[n].strip()
            for n in ("install", "preinstall")):
        hooks.append({"kind": "npm-script", "name": "install",
                      "command": "node-gyp rebuild", "implicit": True,
                      "source": source,
                      "files": {"binding.gyp": _sha256(files["binding.gyp"])}})
    return hooks


def _npm_declared(manifest: dict) -> dict:
    out = {}
    for kind in ("dependencies", "optionalDependencies", "peerDependencies"):
        d = manifest.get(kind)
        if isinstance(d, dict):
            out[kind] = {str(k): str(v) for k, v in sorted(d.items())}
    return out


def _python_hooks(files: dict, source: str) -> list:
    """What runs when pip installs a version: setup.py and the build
    backend when it builds from the source distribution, and a .pth file
    with an `import` line at every start of Python once it is installed."""
    hooks = []
    if "setup.py" in files:
        hooks.append({"kind": "setup.py", "name": "setup.py",
                      "source": source,
                      "sha256": _sha256(files["setup.py"])})
    py = files.get("pyproject.toml")
    if py is not None:
        text = py.decode("utf-8", "replace")
        backend = _toml_value(text, "build-system", "build-backend")
        requires = _toml_value(text, "build-system", "requires")
        in_tree = _toml_value(text, "build-system", "backend-path")
        if backend is not None or requires is not None:
            inside = {}
            for d in (in_tree if isinstance(in_tree, list) else []):
                d = d.strip("./") + "/"
                inside.update({p: _sha256(b) for p, b in files.items()
                               if p.startswith(d) and p.endswith(".py")})
            hooks.append({"kind": "build-backend", "source": source,
                          "name": backend if isinstance(backend, str)
                          else "(none named)",
                          "requires": sorted(requires)
                          if isinstance(requires, list) else [],
                          "files": dict(sorted(inside.items()))})
    for p, body in sorted(files.items()):
        top = "/" not in p or re.match(r"^[^/]+\.data/(purelib|platlib)/"
                                       r"[^/]+$", p)
        if p.endswith(".pth") and top and any(
                ln.startswith(("import ", "import\t"))
                for ln in body.decode("utf-8", "replace").splitlines()):
            hooks.append({"kind": "pth", "name": p, "source": source,
                          "sha256": _sha256(body)})
    return hooks


def _tree_declared(files: dict) -> tuple:
    """(hooks, declared dependencies or None, notes) from a version's own
    files, for a source with no registry: package.json, setup.py,
    pyproject.toml."""
    hooks, declared, notes = [], None, []
    pkg = files.get("package.json")
    if pkg is not None:
        try:
            man = json.loads(pkg.decode("utf-8-sig"))
        except ValueError:
            man = None
            notes.append("package.json is not JSON, so its scripts and "
                         "dependencies were not read")
        if isinstance(man, dict):
            hooks += _npm_hooks(man, files, "package.json")
            declared = _npm_declared(man)
    hooks += _python_hooks(files, "files")
    py = files.get("pyproject.toml")
    if py is not None:
        deps = _toml_value(py.decode("utf-8", "replace"), "project",
                           "dependencies")
        if isinstance(deps, list):
            declared = dict(declared or {})
            declared["project.dependencies"] = _requirements_map(deps)
    return hooks, declared, notes


def _missing(what: str, version: str, have: list, why: str = ""):
    have = sorted(have, key=_ver_key)
    listed = (f"; the latest it lists: {', '.join(have[-8:])}" if have
              else "; it lists no versions")
    raise DepsError(f"{what} has no version {version}{listed}{why}")


def _read_pypi(name: str, version: str) -> dict:
    import urllib.parse
    base = os.environ.get("VELARIS_PYPI_URL", "https://pypi.org").rstrip("/")
    q = urllib.parse.quote(name, safe="")
    raw = _deps_get(f"{base}/pypi/{q}/{urllib.parse.quote(version, safe='')}"
                    f"/json", 32 << 20)
    if raw is None:
        whole = _deps_get(f"{base}/pypi/{q}/json", 64 << 20)
        if whole is None:
            raise DepsError(f"PyPI ({base}) has no package '{name}'; for an "
                            f"npm package write npm:{name}")
        _missing(f"pypi:{name}", version,
                 list(json.loads(whole).get("releases") or {}))
    try:
        doc = json.loads(raw)
    except ValueError:
        raise DepsError(f"PyPI's answer for {name} {version} is not JSON")
    info = doc.get("info") or {}
    listed = doc.get("urls") or []
    sdists = [u for u in listed if u.get("packagetype") == "sdist"]
    wheels = sorted((u for u in listed if u.get("packagetype") == "bdist_wheel"),
                    key=lambda u: (not u.get("filename", "").endswith(
                        "-none-any.whl"), u.get("filename", "")))
    read, notes, trees = [], [], {}
    for label, chosen in (("sdist", sdists[:1]), ("wheel", wheels[:1])):
        for u in chosen:
            data = _deps_get(u["url"])
            if data is None:
                raise DepsError(f"{u['url']} is listed by PyPI and not there")
            want = (u.get("digests") or {}).get("sha256")
            if want and _sha256(data) != want:
                raise DepsError(f"{u.get('filename')}: the bytes downloaded "
                                f"are not the ones PyPI lists (sha256)")
            trees[label] = _archive_files(data, u.get("filename", "x.tar.gz"),
                                          strip_top=(label == "sdist"))
            read.append({"artifact": label, "file": u.get("filename"),
                         "url": u["url"], "sha256": _sha256(data)})
    if len(wheels) > 1:
        notes.append(f"{version} has {len(wheels)} wheels; "
                     f"{wheels[0].get('filename')} was read")
    if not listed:
        notes.append(f"PyPI lists no files for {version}, so none was read")
    if doc.get("info", {}).get("yanked") or any(u.get("yanked")
                                                for u in listed):
        why = info.get("yanked_reason")
        notes.append(f"{version} is yanked on PyPI"
                     + (f": {why}" if why else ""))
    # what is installed is the wheel; the sdist is what pip builds when no
    # wheel matches, running setup.py or the build backend as it does
    files = trees.get("wheel") or trees.get("sdist") or {}
    hooks = _python_hooks(trees.get("sdist", {}), "sdist")
    hooks += [h for h in _python_hooks(trees.get("wheel", {}), "wheel")
              if h["kind"] == "pth"]
    return {"version": version, "files": files, "read": read,
            "surface_from": "wheel" if "wheel" in trees else
            "sdist" if "sdist" in trees else None,
            "hooks": hooks,
            "declared": {"requires_dist": _requirements_map(
                info.get("requires_dist"))},
            "notes": notes}


def _read_npm(name: str, version: str) -> dict:
    import base64
    import hashlib
    import urllib.parse
    base = os.environ.get("VELARIS_NPM_REGISTRY",
                          "https://registry.npmjs.org").rstrip("/")
    q = urllib.parse.quote(name, safe="@")
    raw = _deps_get(f"{base}/{q}/{urllib.parse.quote(version, safe='')}",
                    32 << 20)
    if raw is None:
        whole = _deps_get(f"{base}/{q}", 64 << 20,
                          accept="application/vnd.npm.install-v1+json")
        if whole is None:
            raise DepsError(f"npm ({base}) has no package '{name}'; for a "
                            f"Python package write pypi:{name}")
        doc = json.loads(whole)
        gone = (doc.get("time") or {}).get("unpublished")
        why = ""
        if isinstance(gone, dict):
            why = (f" - every version was unpublished on "
                   f"{str(gone.get('time', '?'))[:10]}, and an unpublished "
                   f"version cannot be read")
        _missing(f"npm:{name}", version, list(doc.get("versions") or {}), why)
    try:
        manifest = json.loads(raw)
    except ValueError:
        raise DepsError(f"npm's answer for {name} {version} is not JSON")
    dist = manifest.get("dist") or {}
    files, read, notes = {}, [], []
    tarball = dist.get("tarball")
    if tarball:
        data = _deps_get(tarball)
        if data is None:
            raise DepsError(f"{tarball} is listed by npm and not there")
        integrity = str(dist.get("integrity") or "")
        if integrity.startswith("sha512-"):
            got = base64.b64encode(hashlib.sha512(data).digest()).decode()
            if got != integrity[7:]:
                raise DepsError(f"{tarball}: the bytes downloaded are not "
                                f"the ones npm lists (integrity)")
        elif dist.get("shasum") and hashlib.sha1(data).hexdigest() \
                != dist["shasum"]:
            raise DepsError(f"{tarball}: the bytes downloaded are not the "
                            f"ones npm lists (shasum)")
        files = _archive_files(data, "package.tgz")
        read.append({"artifact": "tarball", "url": tarball,
                     "sha256": _sha256(data)})
    else:
        notes.append(f"npm lists no tarball for {version}, so none was read")
    # The registry's manifest and the package.json inside the tarball are
    # published separately, and nothing checks one against the other. npm
    # builds a fresh tree from the manifest; which copy's install scripts
    # it runs has differed between npm versions, and depends on whether it
    # installs from a lockfile. So the scripts of both are reported, each
    # marked with where it was read, and a difference is said.
    hooks = _npm_hooks(manifest, files, "registry manifest")
    inner = files.get("package.json")
    if inner is not None:
        try:
            packaged = json.loads(inner.decode("utf-8-sig"))
        except ValueError:
            packaged = None
            notes.append(f"the package.json in the tarball of {version} is "
                         f"not JSON, so its scripts were not read")
        if isinstance(packaged, dict):
            in_tarball = _npm_hooks(packaged, files, "tarball package.json")
            if [(h["name"], h["command"]) for h in hooks] \
                    != [(h["name"], h["command"]) for h in in_tarball]:
                notes.append(f"the registry's manifest for {version} and the "
                             f"package.json in its tarball list different "
                             f"install scripts; which one npm runs has "
                             f"differed between npm versions and depends on "
                             f"whether it installs from a lockfile, so both "
                             f"are reported")
            hooks = hooks + in_tarball
            if _npm_declared(packaged) != _npm_declared(manifest):
                notes.append(f"the registry's manifest for {version} and the "
                             f"package.json in its tarball declare different "
                             f"dependencies; npm resolves a fresh install from "
                             f"the manifest, which is what this report shows, "
                             f"and an install from a tree already on disk can "
                             f"read the tarball's")
    elif tarball:
        notes.append(f"the tarball of {version} holds no package.json")
    return {"version": version, "files": files, "read": read,
            "surface_from": "tarball" if tarball else None,
            "hooks": hooks, "declared": _npm_declared(manifest),
            "notes": notes}


def _git_repository(where: str, scratch: str) -> str:
    if os.path.isdir(where):
        return where
    dest = os.path.join(scratch, "repository.git")
    if not os.path.isdir(dest):
        try:
            _git(["clone", "--quiet", "--bare", where, dest], scratch)
        except (RuntimeError, OSError) as e:
            raise DepsError(f"git:{where} could not be cloned: {e}")
    return dest


def _read_git(where: str, version: str, scratch: str) -> dict:
    repo = _git_repository(where, scratch)
    if version.startswith("-"):
        raise DepsError(f"'{version}' is not a version")
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{version}^{{commit}}"], repo).strip()
    except (RuntimeError, OSError):
        try:
            tags = _git(["tag", "--list"], repo).split()
        except (RuntimeError, OSError):
            tags = []
        _missing(f"git:{where}", version, tags,
                 " (no tag, branch or commit of that name)")
    data = _git(["archive", "--format=tar", commit], repo, binary=True)
    files = _archive_files(data, "version.tar", strip_top=False)
    hooks, declared, notes = _tree_declared(files)
    return {"version": version, "files": files,
            "read": [{"artifact": "git", "commit": commit}],
            "surface_from": "git", "hooks": hooks, "declared": declared,
            "notes": notes}


def _read_dir(where: str, version: str) -> dict:
    if not os.path.isdir(where):
        raise DepsError(f"dir:{where}: no such directory")
    here = os.path.join(where, version)
    if version in ("", ".", "..") or "/" in version or "\\" in version \
            or not os.path.isdir(here):
        _missing(f"dir:{where}", version,
                 [d for d in os.listdir(where)
                  if os.path.isdir(os.path.join(where, d))],
                 f" (no directory {here})")
    files, total = {}, 0
    for dp, dirs, names in os.walk(here):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for n in names:
            full = os.path.join(dp, n)
            if os.path.islink(full):
                continue
            total += os.path.getsize(full)
            if total > _DEPS_TREE_LIMIT:
                raise DepsError(f"{here} holds more than "
                                f"{_DEPS_TREE_LIMIT >> 20} MB")
            with open(full, "rb") as fh:
                files[os.path.relpath(full, here).replace(os.sep, "/")] = \
                    fh.read()
    hooks, declared, notes = _tree_declared(files)
    return {"version": version, "files": files,
            "read": [{"artifact": "directory",
                      "path": os.path.abspath(here)}],
            "surface_from": "directory", "hooks": hooks,
            "declared": declared, "notes": notes}


def _deps_scan(files: dict, into: str) -> dict:
    """capability_scan of a version's .vel files, written out under into."""
    os.makedirs(into, exist_ok=True)
    for p, body in files.items():
        if p.endswith(".vel"):
            dest = os.path.join(into, *p.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(body)
    return capability_scan(into, use_git=False)


def _deps_gained(findings: list) -> dict:
    """What the findings add up to, by kind of scope."""
    out: dict = {"effects": [], "grants": [], "hosts": [],
                 "paths": {"read": [], "write": []}, "modules": [],
                 "counts": [], "functions": []}
    for f in findings:
        if f["kind"] == "grant":
            g = f["grant"]
            out["grants"].append(g)
            if f["new_effect"]:
                out["effects"].append(f["effect"])
            parts = _grant_parts(g)
            if parts[0] == "net" and parts[1] is not None:
                out["hosts"].append(g[4:])
            elif parts[0] == "fs" and parts[2] is not None:
                out["paths"][parts[1]].append(parts[2])
            elif parts[0] == "ffi" and parts[1] is not None:
                out["modules"].append(parts[1])
        elif f["kind"] == "count":
            out["counts"].append({
                "effect": f["effect"], "file": f["file"],
                "old": f["surface_allows"] if f["outside_surface"]
                else f["entry_allows"], "new": f["current"]})
        else:
            out["functions"].append({"file": f["file"],
                                     "function": f["function"],
                                     "gained": f["gained"]})
    for k in ("effects", "grants", "hosts", "modules"):
        out[k] = sorted(set(out[k]))
    for d in ("read", "write"):
        out["paths"][d] = sorted(set(out["paths"][d]))
    return out


def _deps_velaris(a: dict, b: dict, scratch: str):
    """Section 17's comparison of the .vel files of two versions, the
    older one as the baseline; None when neither holds one."""
    vel_a = sorted(p for p in a["files"] if p.endswith(".vel"))
    vel_b = sorted(p for p in b["files"] if p.endswith(".vel"))
    if not vel_a and not vel_b:
        return None
    scan_a = _deps_scan(a["files"], os.path.join(scratch, "old"))
    scan_b = _deps_scan(b["files"], os.path.join(scratch, "new"))
    check = capabilities_compare(capabilities_document(scan_a, ""), scan_b,
                                 a["version"])
    # the check's own findings, less the edit to velaris.capabilities that
    # would accept each one - there is no such file here to edit
    findings = [{k: v for k, v in f.items() if k != "accept"}
                for f in check["findings"]]
    return {"files": {"old": vel_a, "new": vel_b},
            "compiles": {"old": sum(1 for p in scan_a["programs"].values()
                                    if p["compiles"]),
                         "new": sum(1 for p in scan_b["programs"].values()
                                    if p["compiles"])},
            "before": scan_a["surface"], "after": scan_b["surface"],
            "widened": bool(findings), "findings": findings,
            "narrowed": check["narrowed"], "notes": check["notes"],
            "gained": _deps_gained(findings)}


def _hook_key(h: dict) -> tuple:
    return (h["kind"], h["name"], h.get("source", ""))


def _hooks_diff(old: list, new: list) -> dict:
    A = {_hook_key(h): h for h in old}
    B = {_hook_key(h): h for h in new}
    changed = []
    for k in sorted(set(A) & set(B)):
        a, b = A[k], B[k]
        what = []
        if a.get("command") != b.get("command"):
            what.append(f"the command was {a.get('command')!r} and is "
                        f"{b.get('command')!r}")
        if a.get("sha256") != b.get("sha256"):
            what.append(f"{a['name']} is not the same file")
        if a.get("requires") != b.get("requires"):
            what.append(f"what it requires was {a.get('requires')} and is "
                        f"{b.get('requires')}")
        fa, fb = a.get("files") or {}, b.get("files") or {}
        for p in sorted(set(fa) | set(fb)):
            if p not in fa:
                what.append(f"it now runs {p}")
            elif p not in fb:
                what.append(f"it no longer names {p}")
            elif fa[p] != fb[p]:
                what.append(f"{p}, which it runs, is not the same file")
        if what:
            changed.append({"kind": b["kind"], "name": b["name"],
                            "source": b.get("source", ""),
                            "old": a, "new": b, "what": what})
    moved = {(c["kind"], c["name"], c["source"]) for c in changed}
    return {"added": [B[k] for k in sorted(set(B) - set(A))],
            "removed": [A[k] for k in sorted(set(A) - set(B))],
            "changed": changed,
            "unchanged": [B[k] for k in sorted(set(A) & set(B))
                          if k not in moved]}


def _grouped(items: list, hook_of) -> list:
    """[(item, [the places it was read])]: an install script that the
    registry's manifest and the tarball both declare, alike, is said
    once."""
    out: dict = {}
    for it in items:
        h = hook_of(it)
        k = json.dumps([h["kind"], h["name"], h.get("command"),
                        h.get("sha256"), h.get("requires"), h.get("files"),
                        it.get("what")], sort_keys=True, default=str)
        out.setdefault(k, (it, []))[1].append(h.get("source") or "")
    return list(out.values())


def _declared_diff(old, new):
    if old is None and new is None:
        return None
    old, new = old or {}, new or {}
    out: dict = {"added": [], "removed": [], "changed": [], "unchanged": 0}
    for kind in sorted(set(old) | set(new)):
        a, b = old.get(kind, {}), new.get(kind, {})
        for n in sorted(set(b) - set(a)):
            out["added"].append({"kind": kind, "name": n, "spec": b[n]})
        for n in sorted(set(a) - set(b)):
            out["removed"].append({"kind": kind, "name": n, "spec": a[n]})
        for n in sorted(set(a) & set(b)):
            if a[n] != b[n]:
                out["changed"].append({"kind": kind, "name": n,
                                       "old": a[n], "new": b[n]})
            else:
                out["unchanged"] += 1
    return out


def _deps_result(package: str, kind: str, where: str, a: dict, b: dict,
                 scratch: str) -> dict:
    code_a, code_b = _code_counts(a["files"]), _code_counts(b["files"])
    vel = _deps_velaris(a, b, scratch)
    capability = ("unknown" if vel is None
                  else "partial" if code_a or code_b else "derived")
    hooks = _hooks_diff(a["hooks"], b["hooks"])
    declared = _declared_diff(a["declared"], b["declared"])
    not_derived = []
    if vel is None:
        held = _describe_code(code_b) or _describe_code(code_a)
        not_derived.append(
            f"Neither {a['version']} nor {b['version']} holds a .vel file, so "
            f"there is no declared capability surface to compare. "
            + (f"What this package holds is {held}, and what that code can "
               f"do when it runs - files, network, processes, the "
               f"environment - is not derived from it: nothing in it states "
               f"that in a form that can be checked. " if held else
               "It holds no code deps-diff recognises either. ")
            + "Nothing here says the upgrade is safe.")
    elif code_a or code_b:
        before = "" if code_a == code_b else (
            f" ({a['version']} held {_describe_code(code_a) or 'none'})")
        not_derived.append(
            f"The surface above is of the .vel files alone. {b['version']} "
            f"also holds {_describe_code(code_b) or 'no other code'}{before}, "
            f"and what that code can do is not derived and is not in it.")
    if hooks["added"] or hooks["changed"] or hooks["unchanged"]:
        not_derived.append("What an install-time script does is not derived: "
                           "the report says that one was added or changed, "
                           "not what it does.")
    gained =bool((vel and vel["findings"]) or hooks["added"]
                  or hooks["changed"])
    exit_code = 1 if gained else 0 if capability == "derived" else 3

    def side(v, code):
        return {"version": v["version"], "read": v["read"],
                "surface_from": v["surface_from"],
                "files": len(v["files"]),
                "velaris_files": sum(1 for p in v["files"]
                                     if p.endswith(".vel")),
                "other_code": code, "notes": v["notes"]}

    return {"schema": DEPS_DIFF_SCHEMA, "velaris_version": VERSION,
            "package": package, "source": kind, "name": where,
            "old": side(a, code_a), "new": side(b, code_b),
            "capability": capability, "velaris": vel,
            "install_time": hooks, "dependencies": declared,
            "not_derived": not_derived, "gained": gained,
            "exit": exit_code}


def deps_diff(package: str, old: str, new: str) -> dict:
    """What version `new` of a dependency can do that `old` could not, as
    a velaris.deps-diff/1 document. DepsError when either version cannot
    be read."""
    import shutil
    import tempfile
    kind, where = _deps_source(package)
    for v in (old, new):
        if not v or v.startswith("-") or any(ch.isspace() for ch in v):
            raise DepsError(f"'{v}' is not a version")
    scratch = tempfile.mkdtemp(prefix="velaris-deps-")
    try:
        if kind == "pypi":
            a, b = _read_pypi(where, old), _read_pypi(where, new)
        elif kind == "npm":
            a, b = _read_npm(where, old), _read_npm(where, new)
        elif kind == "git":
            a = _read_git(where, old, scratch)
            b = _read_git(where, new, scratch)
        else:
            a, b = _read_dir(where, old), _read_dir(where, new)
        return _deps_result(package, kind, where, a, b, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---- saying it ----------------------------------------------------------------

def _deps_finding_lines(item: dict, old: str) -> list:
    """A finding of deps-diff as the report prints it: what the newer
    version gained, where, and through which calls."""
    out = []
    if item["kind"] == "grant":
        what = (f"a new effect, {item['effect']}" if item["new_effect"]
                else f"not in {old}'s surface" if item["outside_surface"]
                else f"in {old}'s surface, not in this file's entry there")
        out.append(f"GAINED  {item['grant']} - {what}")
        for q in item["programs"]:
            out.append(f"    in {q['file']}")
            for s in q["origins"][:4]:
                lit = f'("{s["literal"]}")' if s.get("literal") else ""
                call = f" calls {s['call']}{lit}" if s.get("call") \
                    else " declares it"
                out.append(f"      {s['file']}:{s['line']}  "
                           f"{s['function']}{call}")
            if q["reached_from"]:
                out.append(f"      reached from "
                           f"{' -> '.join(q['reached_from'])}")
    elif item["kind"] == "count":
        now = ("no bound" if item["current"] is None
               else f"at most {item['current']}")
        had = item["surface_allows"] if item["outside_surface"] \
            else item["entry_allows"]
        out.append(f"GAINED  {item['effect']} operations in {item['file']}: "
                   f"{now} in a run; {old} had at most {had}")
        out.append(f"    {item['function']} (line {item['line']})"
                   + (f": {item['why']}" if item.get("why") else ""))
    else:
        out.append(f"GAINED  {item['file']}: {item['function']} now declares "
                   f"{', '.join(item['gained'])} (in {old} it declared "
                   f"{', '.join(item['had']) or 'nothing'})")
        for b in item["because"]:
            effect, _, rest = b.partition(": ")
            out.append(f"    {effect}: {item['function']} {rest}")
    return out


def _hook_text(h: dict, where=None) -> str:
    if h["kind"] == "npm-script":
        return (f"npm {h['name']}: {h['command']}"
                + (" (npm's default for binding.gyp)" if h.get("implicit")
                   else "")
                + (f" [{', '.join(where)}]" if where
                   and where != ["package.json"] else ""))
    if h["kind"] == "setup.py":
        return "setup.py, run when pip builds the sdist"
    if h["kind"] == "build-backend":
        return (f"build backend {h['name']}"
                + (f", requiring {', '.join(h['requires'])}"
                   if h.get("requires") else "")
                + ", run when pip builds the sdist")
    return f"{h['name']}, a .pth file run at every start of Python"


def deps_diff_lines(result: dict) -> list:
    """velaris deps-diff's report, as text."""
    old, new = result["old"]["version"], result["new"]["version"]
    L = [f"velaris deps-diff: {result['package']} {old} -> {new}"]
    for side in (result["old"], result["new"]):
        for r in side["read"]:
            where = r.get("url") or r.get("path") or r.get("commit")
            L.append(f"  read {side['version']}: {r['artifact']} {where}")
    vel = result["velaris"]
    if vel is not None:
        state = ("widened" if vel["widened"] else
                 "narrowed" if vel["narrowed"] else "unchanged")
        L.append(f"  capability surface of the .vel files "
                 f"({len(vel['files']['old'])} in {old}, "
                 f"{len(vel['files']['new'])} in {new}): {state}")
        for f in vel["findings"]:
            L.extend("    " + line for line in _deps_finding_lines(f, old))
        for n in vel["narrowed"]:
            L.append(f"    narrowed: {n}")
        for n in vel["notes"]:
            L.append(f"    note: {n}")
    else:
        L.append("  capability surface: UNKNOWN")
    for text in result["not_derived"]:
        L.append(f"  not derived: {text}")
    hooks = result["install_time"]
    if not any(hooks[k] for k in ("added", "changed", "removed", "unchanged")):
        L.append("  install-time scripts: none in either version")
    else:
        L.append("  install-time scripts:")
        for h, where in _grouped(hooks["added"], lambda x: x):
            L.append(f"    ADDED    {_hook_text(h, where)}")
        for c, where in _grouped(hooks["changed"], lambda x: x["new"]):
            L.append(f"    CHANGED  {_hook_text(c['new'], where)}: "
                     + "; ".join(c["what"]))
        for h, where in _grouped(hooks["removed"], lambda x: x):
            L.append(f"    removed  {_hook_text(h, where)}")
        for h, where in _grouped(hooks["unchanged"], lambda x: x):
            L.append(f"    same     {_hook_text(h, where)}")
    d = result["dependencies"]
    if d is None:
        L.append("  declared dependencies: none read - neither version has "
                 "a manifest that declares them (a Velaris library names "
                 "what it imports in its source)")
    elif not (d["added"] or d["removed"] or d["changed"]):
        L.append(f"  declared dependencies: unchanged ({d['unchanged']})")
    else:
        L.append("  declared dependencies:")
        for x in d["added"]:
            L.append(f"    + {x['name']} {x['spec']} ({x['kind']})")
        for x in d["changed"]:
            L.append(f"    ~ {x['name']} {x['old']} -> {x['new']} "
                     f"({x['kind']})")
        for x in d["removed"]:
            L.append(f"    - {x['name']} ({x['kind']})")
    for side in (result["old"], result["new"]):
        for n in side["notes"]:
            L.append(f"  note: {n}")
    if result["gained"]:
        L.append(f"{new} gained what is marked above.")
    elif result["capability"] == "derived":
        L.append(f"nothing gained: {new} needs nothing {old} did not")
    else:
        L.append(f"nothing gained that could be seen, and the capability "
                 f"surface was not derived: this is not a finding that "
                 f"{new} is safe")
    return L


def _md(text) -> str:
    """Text a pull request controls - a package name, a version, a
    script - for the inside of a code span in a comment, where GitHub
    renders no HTML and links no mention: only a backtick or a line
    break could get out."""
    return str(text).replace("`", "'").replace("\r", " ").replace("\n", " ")


def _md_text(text) -> str:
    """The same, for the prose of a comment: no HTML, no @mention, no
    line break. The mention is broken with an entity for a zero-width
    space rather than the character, so the text stays ASCII: 7.1.0 wrote
    the character, and a console that is not UTF-8 - Windows' cp1252 -
    stopped printing at it."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("@", "@&#8203;")
            .replace("\r", " ").replace("\n", " "))


def _deps_sarif_add(run: "_SarifRun", result: dict, at) -> None:
    """The findings of one deps-diff result, each placed by at(file in the
    package or None, line) -> (path or artifactLocation, line)."""
    pkg = f"{result['package']} {result['old']['version']} -> " \
          f"{result['new']['version']}"
    vel = result["velaris"]
    for f in (vel or {}).get("findings", []):
        if f["kind"] == "grant":
            q = f["programs"][0]
            s = (q["origins"] or [{"file": q["file"], "line": None}])[0]
            where, line = at(s["file"], s.get("line"))
            run.add("dependency-capability-widened",
                    f"{pkg}: {f['grant']} is needed by {q['file']}"
                    + (f" (a new effect, {f['effect']})" if f["new_effect"]
                       else f", not in {result['old']['version']}'s surface"
                       if f["outside_surface"] else ""),
                    where, line)
        elif f["kind"] == "count":
            now = "no bound" if f["current"] is None \
                else f"at most {f['current']}"
            where, line = at(f["file"], f["line"])
            run.add("dependency-capability-widened",
                    f"{pkg}: {f['file']} performs {now} {f['effect']} "
                    f"operations in a run, more than before", where, line)
        else:
            where, line = at(f["file"], f["line"])
            run.add("dependency-effect-gained",
                    f"{pkg}: '{f['function']}' now declares "
                    f"{', '.join(f['gained'])}: " + "; ".join(f["because"]),
                    where, line)
    for n in (vel or {}).get("narrowed", []):
        where, line = at(None, None)
        run.add("dependency-narrowed", f"{pkg}: {n}", where, line)
    hooks = result["install_time"]
    for h, sources in _grouped(hooks["added"], lambda x: x):
        where, line = at("package.json" if h["kind"] == "npm-script"
                         else h["name"] if h["kind"] in ("setup.py", "pth")
                         else "pyproject.toml", None)
        run.add("dependency-install-script",
                f"{pkg}: an install-time script was added: "
                f"{_hook_text(h, sources)}; what it does is not derived",
                where, line)
    for c, sources in _grouped(hooks["changed"], lambda x: x["new"]):
        h = c["new"]
        where, line = at("package.json" if h["kind"] == "npm-script"
                         else h["name"] if h["kind"] in ("setup.py", "pth")
                         else "pyproject.toml", None)
        run.add("dependency-install-script",
                f"{pkg}: an install-time script changed: "
                f"{_hook_text(h, sources)} - " + "; ".join(c["what"])
                + "; what it does is not derived", where, line)
    if result["capability"] != "derived":
        where, line = at(None, None)
        state = "unknown" if result["capability"] == "unknown" \
            else "only partly derived"
        run.add("dependency-surface-unknown",
                f"{pkg}: capability surface {state}. "
                + " ".join(result["not_derived"][:1]), where, line)
    for x in (result["dependencies"] or {}).get("added", []):
        where, line = at(None, None)
        run.add("dependency-added",
                f"{pkg}: now declares {x['name']} {x['spec']} ({x['kind']}); "
                f"its own surface was not examined", where, line)


def _package_base_uri(result: dict) -> str:
    import pathlib
    r = (result["new"]["read"] or [{}])[0]
    if r.get("path"):
        return pathlib.Path(r["path"]).as_uri().rstrip("/") + "/"
    if r.get("url"):
        return r["url"].rstrip("/") + "/"
    if result["source"] == "git" and os.path.isdir(result["name"]):
        return pathlib.Path(os.path.abspath(result["name"])).as_uri() + "/"
    return "urn:velaris-deps-diff:" + re.sub(r"[^A-Za-z0-9._@-]+", "-",
                                             result["package"]) + "/"


def sarif_deps_diff(result: dict) -> dict:
    """`velaris deps-diff PACKAGE OLD NEW --sarif`: each finding at the
    file inside the newer version that holds it, relative to a base URI
    naming that version; the whole result in the run's property bag."""
    run = _SarifRun("deps-diff")
    run.base_ids["DEPENDENCY"] = {
        "uri": _package_base_uri(result),
        "description": {"text": f"{result['package']} "
                                f"{result['new']['version']}"}}

    def at(file, line):
        return ({"uri": file or "", "uriBaseId": "DEPENDENCY"},
                line if file else None)

    _deps_sarif_add(run, result, at)
    run.properties["deps_diff"] = result
    return run.log()


# ---- lockfiles ----------------------------------------------------------------

def _lockfile_format(path: str):
    """(format, ecosystem) for a lockfile's name; ("not-read", None) for
    one recognised and not read; None for a file that is not a lockfile."""
    name = os.path.basename(path)
    if name in _LOCKFILES:
        return _LOCKFILES[name]
    if re.match(r"^requirements[\w.-]*\.txt$", name):
        return ("requirements", "pypi")
    if name in _LOCKFILES_NOT_READ:
        return ("not-read", None)
    return None


def _parse_lockfile(fmt: str, text) -> tuple:
    """({name: {version: ...}}, notes) - the pinned versions a lockfile
    names, from the registry deps-diff reads. An entry from git, a path, a
    link, or another registry or index is left out and said: reading the
    public registry's package of the same name would compare a different
    package."""
    import urllib.parse
    out: dict = {}
    notes: list = []
    if text is None:
        return out, notes
    if fmt == "npm-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        npm_host = urllib.parse.urlsplit(os.environ.get(
            "VELARIS_NPM_REGISTRY", "https://registry.npmjs.org")).netloc.lower()

        def elsewhere(name, e):
            v = str(e.get("version") or "")
            resolved = str(e.get("resolved") or "")
            if e.get("link") or not re.match(r"^\d", v):
                return (f"{name} is not from a registry ({v or 'a link'}); "
                        f"not read")
            if resolved:
                host = urllib.parse.urlsplit(resolved).netloc.lower()
                if not resolved.startswith(("https://", "http://")) \
                        or host != npm_host:
                    return (f"{name} {v} was resolved from "
                            f"{host or resolved.split(':', 1)[0]}, not from "
                            f"the registry deps-diff reads; not read")
            return None

        pkgs = doc.get("packages")
        if isinstance(pkgs, dict):
            for key, e in pkgs.items():
                if not key or "node_modules/" not in key \
                        or not isinstance(e, dict):
                    continue
                name = key.rsplit("node_modules/", 1)[1]
                why = elsewhere(name, e)
                if why:
                    notes.append(why)
                    continue
                out.setdefault(e.get("name") or name, {})[
                    str(e["version"])] = key
        else:
            def walk(deps, trail):
                for name, e in (deps or {}).items():
                    if not isinstance(e, dict):
                        continue
                    why = elsewhere(name, e)
                    if why:
                        notes.append(why)
                    else:
                        out.setdefault(name, {})[str(e["version"])] = \
                            trail + name
                    walk(e.get("dependencies"), trail + name + "/")
            walk(doc.get("dependencies"), "")
    elif fmt == "pipfile-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        pypi = os.environ.get("VELARIS_PYPI_URL", "https://pypi.org").rstrip(
            "/")
        indexes = {s.get("name"): str(s.get("url") or "")
                   for s in (doc.get("_meta") or {}).get("sources") or []
                   if isinstance(s, dict)}
        for section in ("default", "develop"):
            for name, e in (doc.get(section) or {}).items():
                e = e if isinstance(e, dict) else {}
                url = indexes.get(e.get("index"), "")
                if url and not url.startswith(("https://pypi.org/", pypi)):
                    notes.append(f"{name} comes from the index {url}, not "
                                 f"PyPI; not read")
                    continue
                v = str(e.get("version") or "")
                if v.startswith("=="):
                    out.setdefault(_pep508_name(name) or name, {})[v[2:]] = \
                        section
                else:
                    notes.append(f"{name} is not pinned to a version from "
                                 f"an index; not read")
    elif fmt == "toml-packages":
        for block in re.split(r"(?m)^\[\[package\]\]\s*$", text)[1:]:
            head = re.split(r"(?m)^\[", block)[0]
            n = re.search(r'(?m)^name\s*=\s*"([^"]+)"', head)
            v = re.search(r'(?m)^version\s*=\s*"([^"]+)"', head)
            if not n or not v:
                continue
            src = re.search(r"(?m)^source\s*=\s*\{([^}]*)\}", head)
            sub = re.search(r'(?m)^\[package\.source\]\s*\n(?:.*\n)*?'
                            r'type\s*=\s*"([^"]+)"', block)
            name = _pep508_name(n.group(1)) or n.group(1)
            if (src and not re.search(r'registry\s*=\s*"https://pypi\.org/',
                                      src.group(1))) or sub:
                notes.append(f"{name} is not from PyPI; not read")
                continue
            out.setdefault(name, {})[v.group(1)] = "package"
    elif fmt == "requirements":
        lines = [raw.split(" #", 1)[0].strip() for raw in text.splitlines()]
        index = next((ln for ln in lines if re.match(
            r"^(-i|--index-url|--extra-index-url)(\s|=|$)", ln)), None)
        if index:
            # pip takes a pin from whichever index has it, so no pin in
            # this file is known to be PyPI's package. (The option is
            # found outside the f-string: a backslash inside one is a
            # syntax error before Python 3.12, and 7.1.0 shipped that.)
            option = re.split(r"[\s=]", index)[0]
            return out, [f"it sets a package index ({option}), so a pin may "
                         f"not come from PyPI; its pins were not read"]
        for line in lines:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*"
                         r"===?\s*([^\s;\\#]+)", line)
            if m:
                out.setdefault(_pep508_name(m.group(1)), {})[m.group(3)] = \
                    "pin"
    elif fmt == "velaris-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        for e in doc.get("libraries") or []:
            if isinstance(e, dict) and e.get("name") and e.get("sha256"):
                out.setdefault(e["name"], {})[e["sha256"]] = e
    return out, notes


def _lock_line(text: str, fmt: str, name: str, version: str):
    """The line of a lockfile that pins name at version, when it can be
    found; None otherwise."""
    if not text:
        return None
    lines = text.splitlines()
    if fmt == "npm-lock":
        start = [i for i, ln in enumerate(lines)
                 if re.search(r'"(?:[^"]*node_modules/)?' + re.escape(name)
                              + r'"\s*:\s*\{', ln)]
        for i in start:
            for j in range(i, min(i + 12, len(lines))):
                if f'"version": "{version}"' in lines[j]:
                    return j + 1
    elif fmt == "pipfile-lock":
        inside = False                 # within this package's own object
        for i, ln in enumerate(lines):
            key = re.match(r'^\s*"([^"]+)"\s*:\s*\{', ln)
            if key:
                inside = (_pep508_name(key.group(1)) or key.group(1)) == name
            if inside and f'"version": "=={version}"' in ln:
                return i + 1
    elif fmt == "toml-packages":
        for i, ln in enumerate(lines):
            m = re.match(r'^name\s*=\s*"([^"]+)"', ln)
            if m and (_pep508_name(m.group(1)) or m.group(1)) == name \
                    and i + 1 < len(lines) and re.match(
                        r'^version\s*=\s*"' + re.escape(version) + '"',
                        lines[i + 1]):
                return i + 2
    elif fmt == "requirements":
        for i, ln in enumerate(lines):
            m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*"
                         r"===?\s*([^\s;\\#]+)", ln)
            if m and _pep508_name(m.group(1)) == name \
                    and m.group(3) == version:
                return i + 1
    elif fmt == "velaris-lock":
        for i, ln in enumerate(lines):
            if f'"{version}"' in ln:
                return i + 1
    return None


def _lock_changes(base: dict, head: dict) -> tuple:
    """(upgrades as (name, old, new), added as (name, version), removed as
    (name, version)). A name pinned at a version the base did not have is
    compared with the highest version the base had and the head does not,
    or failing that with the highest the base had."""
    upgrades, added, removed = [], [], []
    for name in sorted(set(base) | set(head)):
        old, new = set(base.get(name, {})), set(head.get(name, {}))
        came, gone = new - old, old - new
        pool = gone or old
        for v in sorted(came, key=_ver_key):
            if pool:
                upgrades.append((name, max(pool, key=_ver_key), v))
            else:
                added.append((name, v))
        if not new:
            removed.extend((name, v) for v in sorted(gone, key=_ver_key))
    return upgrades, added, removed


def _vendored_diff(name: str, old_entry: dict, new_entry: dict,
                   old_bytes, new_bytes) -> dict:
    """deps-diff of a library velaris.lock vendors, between the file the
    base commit held and the file the working tree holds."""
    import shutil
    import tempfile
    file = new_entry.get("file") or f"lib/{name}.vel"
    a = {"version": old_entry["sha256"][:12], "read": [{
        "artifact": "vendored", "path": f"{file} at the base"}],
         "files": {} if old_bytes is None else {
             os.path.basename(file): old_bytes},
         "surface_from": "vendored", "hooks": [], "declared": None,
         "notes": [] if old_bytes is not None else [
             f"the base commit does not hold {file}"]}
    b = {"version": new_entry["sha256"][:12], "read": [{
        "artifact": "vendored", "path": f"{file} in the working tree"}],
         "files": {} if new_bytes is None else {
             os.path.basename(file): new_bytes},
         "surface_from": "vendored", "hooks": [], "declared": None,
         "notes": [] if new_bytes is not None else [
             f"the working tree does not hold {file}"]}
    scratch = tempfile.mkdtemp(prefix="velaris-deps-")
    try:
        result = _deps_result(f"velaris.lock:{name}", "vendored", file, a, b,
                              scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    result["not_derived"] = [t for t in result["not_derived"]
                             if not t.startswith("Neither version has a")]
    return result


def deps_review(against: str, root: str = ".",
                limit: int = _DEPS_MAX_UPGRADES) -> dict:
    """Every dependency the lockfiles under root upgrade between the git
    ref `against` and the working tree, each compared with deps_diff, as a
    velaris.deps-diff-lockfiles/1 document. RuntimeError when git cannot
    answer."""
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{against}^{{commit}}"], root).strip()
    except RuntimeError:
        raise RuntimeError(f"no commit called '{against}' in this "
                           f"repository (a shallow clone may need: git "
                           f"fetch --depth=1 origin {against})")
    prefix = _git(["rev-parse", "--show-prefix"], root).strip()
    changed = [p for p in _git(["diff", "--name-only", "--relative", "-z",
                                commit, "--", "."], root).split("\0") if p]
    lockfiles, upgrades, added, removed, skipped = [], [], [], [], []
    budget = limit
    for rel in sorted(p for p in changed if _lockfile_format(p)):
        fmt, eco = _lockfile_format(rel)
        entry = {"file": rel, "format": fmt, "read": fmt != "not-read",
                 "notes": []}
        lockfiles.append(entry)
        if fmt == "not-read":
            entry["notes"].append("velaris deps-diff does not read this "
                                  "lockfile's format, so nothing about its "
                                  "upgrades is reported")
            continue
        try:
            base_text = _git(["show", f"{commit}:{prefix}{rel}"], root)
        except RuntimeError:
            base_text = None
        full = os.path.join(root, *rel.split("/"))
        head_text = None
        if os.path.exists(full):
            with open(full, encoding="utf-8", errors="replace") as fh:
                head_text = fh.read()
        base, _ = _parse_lockfile(fmt, base_text)
        head, notes_h = _parse_lockfile(fmt, head_text)
        said = sorted(set(notes_h))       # what the tree's lockfile left out
        entry["notes"] += said[:20] + ([f"and {len(said) - 20} more left out"]
                                       if len(said) > 20 else [])
        ups, adds, rems = _lock_changes(base, head)
        for name, v in adds:
            added.append({"lockfile": rel, "ecosystem": eco, "name": name,
                          "version": v,
                          "line": _lock_line(head_text, fmt, name, v)})
        for name, v in rems:
            removed.append({"lockfile": rel, "ecosystem": eco, "name": name,
                            "version": v})
        for name, old, new in ups:
            item = {"lockfile": rel, "ecosystem": eco, "name": name,
                    "old": old, "new": new,
                    "line": _lock_line(head_text, fmt, name, new),
                    "result": None, "error": None}
            if budget <= 0:
                skipped.append(item)
                continue
            budget -= 1
            try:
                if eco == "velaris":
                    ob, nb = base[name][old], head[name][new]
                    for e in (ob, nb):           # the lockfile is the pull
                        f = str(e.get("file") or "")   # request's to write
                        if not f.endswith(".vel") or f.startswith("/") \
                                or any(p in ("", ".", "..") or ":" in p
                                       or "\\" in p for p in f.split("/")):
                            raise DepsError(
                                f"velaris.lock names {f!r} for {name}, "
                                f"which is not a .vel file inside the "
                                f"repository; not read")
                    try:
                        old_bytes = _git(["show", f"{commit}:{prefix}"
                                          f"{ob.get('file') or ''}"], root,
                                         binary=True)
                    except RuntimeError:
                        old_bytes = None
                    path = os.path.join(root, *(nb.get("file") or "").split(
                        "/"))
                    new_bytes = None
                    if nb.get("file") and os.path.isfile(path):
                        with open(path, "rb") as fh:
                            new_bytes = fh.read()
                    item["result"] = _vendored_diff(name, ob, nb, old_bytes,
                                                    new_bytes)
                else:
                    item["result"] = deps_diff(f"{eco}:{name}", old, new)
            except DepsError as e:
                item["error"] = str(e)
            upgrades.append(item)
    gained = any(u["result"] and u["result"]["gained"] for u in upgrades)
    unseen = (sum(1 for u in upgrades if u["error"] or (
        u["result"] and u["result"]["capability"] != "derived"))
        + len(skipped) + sum(1 for x in lockfiles if not x["read"]))
    return {"schema": DEPS_LOCKFILES_SCHEMA, "velaris_version": VERSION,
            "against": against, "commit": commit, "root": root,
            "lockfiles": lockfiles, "upgrades": upgrades, "added": added,
            "removed": removed, "not_compared": skipped, "limit": limit,
            "gained": gained, "not_derived": unseen,
            "exit": 1 if gained else 3 if unseen else 0}


def deps_review_lines(review: dict) -> list:
    L = [f"velaris deps-diff: lockfiles changed since {review['against']} "
         f"({review['commit'][:7]}): "
         + (", ".join(x["file"] for x in review["lockfiles"]) or "none")]
    for x in review["lockfiles"]:
        for n in x["notes"]:
            L.append(f"  {x['file']}: {n}")
    for u in review["upgrades"]:
        L.append("")
        L.append(f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']} "
                 f"({u['lockfile']}"
                 + (f" line {u['line']})" if u["line"] else ")"))
        if u["error"]:
            L.append(f"  not compared: {u['error']}")
        else:
            L.extend("  " + ln for ln in deps_diff_lines(u["result"])[1:])
    for u in review["not_compared"]:
        L.append(f"not compared, over the limit of {review['limit']}: "
                 f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']}")
    if review["added"]:
        L.append("")
        L.append("added, with no earlier version to compare: " + ", ".join(
            f"{a['name']} {a['version']}" for a in review["added"][:40])
            + (f" and {len(review['added']) - 40} more"
               if len(review["added"]) > 40 else ""))
    if review["removed"]:
        L.append("removed: " + ", ".join(
            f"{a['name']} {a['version']}" for a in review["removed"][:40]))
    L.append("")
    L.append("gained: yes - see above" if review["gained"] else
             "nothing gained that could be seen; "
             f"{review['not_derived']} dependenc(ies) or lockfile(s) could "
             f"not be derived, which is not a finding that they are safe"
             if review["not_derived"] else "nothing gained")
    return L


def deps_markdown(review: dict) -> str:
    """The pull-request comment: what each upgraded dependency gained,
    with what could not be seen said as plainly as what could."""
    L = [DEPS_COMMENT_MARKER, "## What each upgraded dependency gained", ""]
    if not review["lockfiles"]:
        L.append(f"No lockfile in this pull request changes since the base "
                 f"`{review['commit'][:7]}` any more.")
        L.append("")
        L.append("<sub>Posted by the Velaris action (deps-diff); this "
                 "comment is edited in place on later runs.</sub>")
        return "\n".join(L)
    L.append("Lockfiles changed since the base `"
             + review["commit"][:7] + "`: "
             + ", ".join(f"`{_md(x['file'])}`" for x in review["lockfiles"])
             + ".")
    L.append("")
    L.append("For a Velaris library this compares the capability surface "
             "the two versions declare. For any other package it reads the "
             "install-time scripts and the declared dependencies, and "
             "nothing more: what Python or JavaScript code does cannot be "
             "derived from it, so those rows say **unknown**, and unknown is "
             "not safe. Either way it sees what is declared, not what the "
             "code does when it runs.")
    for u in review["upgrades"]:
        where = f"`{_md(u['lockfile'])}`" + (f" line {u['line']}"
                                              if u["line"] else "")
        L.append("")
        L.append(f"### `{_md(u['ecosystem'])}:{_md(u['name'])}` "
                 f"`{_md(u['old'])}` -> `{_md(u['new'])}` ({where})")
        L.append("")
        if u["error"]:
            L.append(f"**Not compared:** {_md_text(u['error'])}")
            continue
        r = u["result"]
        vel = r["velaris"]
        if vel is not None and vel["findings"]:
            L.append("**Gained:**")
            for f in vel["findings"]:
                if f["kind"] == "grant":
                    q = f["programs"][0]
                    s = (q["origins"] or [{}])[0]
                    L.append(f"- `{_md(f['grant'])}` - "
                             + (f"a new effect, `{f['effect']}`"
                                if f["new_effect"] else "within an effect "
                                "the old version already had")
                             + (f"; `{_md(s['file'])}:{s['line']}` in "
                                f"`{_md(s['function'])}`" if s else ""))
                elif f["kind"] == "count":
                    now = "no bound" if f["current"] is None \
                        else f"at most {f['current']}"
                    L.append(f"- {now} `{f['effect']}` operations in a run "
                             f"in `{_md(f['file'])}`")
                else:
                    L.append(f"- `{_md(f['function'])}` in "
                             f"`{_md(f['file'])}` now declares "
                             + ", ".join(f"`{e}`" for e in f["gained"]))
        elif vel is not None:
            L.append("Capability surface of the `.vel` files: "
                     + ("narrowed." if vel["narrowed"] else "unchanged."))
        if r["capability"] == "unknown":
            L.append(f"**Capability surface: unknown.** "
                     f"{_md_text(r['not_derived'][0])}")
        elif r["capability"] == "partial":
            L.append(f"**Capability surface: partly derived.** "
                     f"{_md_text(r['not_derived'][0])}")
        hooks = r["install_time"]
        bits = ([f"**added** `{_md(_hook_text(h, s))}`"
                 for h, s in _grouped(hooks["added"], lambda x: x)]
                + [f"**changed** `{_md(_hook_text(c['new'], s))}` - `"
                   + _md("; ".join(c["what"])) + "`"
                   for c, s in _grouped(hooks["changed"], lambda x: x["new"])]
                + [f"removed `{_md(_hook_text(h, s))}`"
                   for h, s in _grouped(hooks["removed"], lambda x: x)])
        L.append("")
        L.append("- install-time scripts: " + ("; ".join(bits) if bits else
                                                "unchanged" if
                                                hooks["unchanged"] else
                                                "none in either version"))
        d = r["dependencies"]
        if d is None:
            L.append("- declared dependencies: none read (no manifest "
                     "declares them)")
        else:
            bits = ([f"+ `{_md(x['name'])}` `{_md(x['spec'])}`"
                     for x in d["added"]]
                    + [f"~ `{_md(x['name'])}` `{_md(x['old'])}` -> "
                       f"`{_md(x['new'])}`" for x in d["changed"]]
                    + [f"- `{_md(x['name'])}`" for x in d["removed"]])
            L.append("- declared dependencies: " + ("; ".join(bits[:20])
                                                     if bits else "unchanged"))
    if review["not_compared"]:
        L.append("")
        L.append(f"Not compared, over the limit of {review['limit']}: "
                 + ", ".join(f"`{_md(u['name'])}` `{_md(u['new'])}`"
                             for u in review["not_compared"][:40]) + ".")
    if review["added"]:
        L.append("")
        L.append("Added, with no earlier version to compare: "
                 + ", ".join(f"`{_md(a['name'])}` `{_md(a['version'])}`"
                             for a in review["added"][:40])
                 + (f" and {len(review['added']) - 40} more"
                    if len(review["added"]) > 40 else "") + ".")
    unread = [x for x in review["lockfiles"] if not x["read"]]
    if unread:
        L.append("")
        L.append("Changed and not read, because deps-diff does not read "
                 "their format: " + ", ".join(f"`{_md(x['file'])}`"
                                              for x in unread) + ".")
    L.append("")
    L.append("<sub>Posted by the Velaris action (deps-diff); this comment is "
             "edited in place on later runs.</sub>")
    body = "\n".join(L)
    if len(body) > 60000:                     # GitHub stops at 65536
        body = body[:60000] + ("\n\n... cut here: the comment is too long. "
                               "The job log has all of it.")
    return body


def sarif_deps_review(review: dict) -> dict:
    """`velaris deps-diff --against REF --sarif`: each finding at the line
    of the lockfile that pins the upgraded version."""
    run = _SarifRun("deps-diff")
    root = review["root"]
    for u in review["upgrades"]:
        path = os.path.join(root, *u["lockfile"].split("/"))

        def at(file, line, path=path, u=u):
            return path, u["line"]

        if u["error"]:
            run.add("dependency-surface-unknown",
                    f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']}: "
                    f"not compared: {u['error']}", path, u["line"])
            continue
        _deps_sarif_add(run, u["result"], at)
    for x in review["lockfiles"]:
        if not x["read"]:
            run.add("dependency-surface-unknown",
                    f"{x['file']} changed, and deps-diff does not read its "
                    f"format", os.path.join(root, *x["file"].split("/")),
                    None)
    run.properties["deps_diff"] = review
    return run.log()


def _github(method: str, url: str, token: str, body=None) -> tuple:
    import urllib.error
    import urllib.request
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"velaris/{VERSION} (deps-diff)",
        **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def deps_comment(body: str, pr: str, has_lockfiles: bool = True) -> str:
    """Post the comment, or edit the one an earlier run posted - found by
    its marker - so a pull request holds one. Reads GITHUB_TOKEN,
    GITHUB_REPOSITORY and GITHUB_API_URL. With no lockfile changed and no
    earlier comment, posts nothing. Returns what it did; RuntimeError when
    the API refuses."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com") \
        .rstrip("/")
    if not token or not repo or not str(pr).isdigit():
        raise RuntimeError("--comment needs GITHUB_TOKEN and "
                           "GITHUB_REPOSITORY in the environment and --pr N")
    found = None
    for page in range(1, 11):              # up to 1000 comments back
        status, got = _github(
            "GET", f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100"
                   f"&page={page}", token)
        if status != 200 or not isinstance(got, list):
            raise RuntimeError(f"listing the comments: HTTP {status}")
        found = next((c["id"] for c in got
                      if DEPS_COMMENT_MARKER in (c.get("body") or "")), None)
        if found is not None or len(got) < 100:
            break
    if found is not None:
        status, _ = _github("PATCH",
                            f"{api}/repos/{repo}/issues/comments/{found}",
                            token, {"body": body})
        if status != 200:
            raise RuntimeError(f"editing comment {found}: HTTP {status}")
        return f"edited comment {found}"
    if not has_lockfiles:
        return "no lockfile changed and no earlier comment: nothing posted"
    status, got = _github("POST", f"{api}/repos/{repo}/issues/{pr}/comments",
                          token, {"body": body})
    if status != 201:
        raise RuntimeError(f"posting the comment: HTTP {status}")
    return f"posted comment {(got or {}).get('id')}"


def deps_diff_main(argv: list) -> int:
    """velaris deps-diff <package> <old> <new> [--json | --sarif]
    velaris deps-diff --against REF [path] [--json | --sarif | --markdown]
                      [--comment --pr N] [--max N]
    velaris deps-diff --from FILE [...the same outputs]"""
    usage = ("usage: velaris deps-diff <package> <old-version> <new-version> "
             "[--json | --sarif]\n"
             "       velaris deps-diff --against REF [path] "
             "[--json | --sarif | --markdown] [--comment --pr N] [--max N]\n"
             "       velaris deps-diff --from FILE "
             "[--json | --sarif | --markdown] [--comment --pr N]\n"
             "  <package> is pypi:NAME, npm:NAME, git:URL-or-PATH or "
             "dir:PATH")
    opts: dict = {}
    words: list = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--against", "--pr", "--max", "--from"):
            if i + 1 >= len(argv):
                print(usage, file=sys.stderr)
                return 2
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a in ("--json", "--sarif", "--markdown", "--comment"):
            opts[a] = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            words.append(a)
        i += 1
    formats = [f for f in ("--json", "--sarif", "--markdown") if f in opts]
    lockfile_mode = "--against" in opts or "--from" in opts
    if len(formats) > 1 or ("--comment" in opts) != ("--pr" in opts) or (
            lockfile_mode and len(words) > 1) or (
            not lockfile_mode and (len(words) != 3 or "--comment" in opts
                                   or "--markdown" in opts
                                   or "--max" in opts)) or (
            "--against" in opts and "--from" in opts):
        print(usage, file=sys.stderr)
        return 2

    if not lockfile_mode:
        try:
            result = deps_diff(*words)
        except DepsError as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
        if "--json" in opts:
            print(json.dumps(result, indent=2))
        elif "--sarif" in opts:
            log = sarif_deps_diff(result)
            print(json.dumps(log, indent=2))
            print_sarif_summary(log)
        else:
            print("\n".join(deps_diff_lines(result)))
        return result["exit"]

    if "--from" in opts:
        try:
            with open(opts["--from"], encoding="utf-8") as fh:
                review_doc = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"velaris deps-diff: cannot read {opts['--from']}: {e}",
                  file=sys.stderr)
            return 2
        if review_doc.get("schema") != DEPS_LOCKFILES_SCHEMA:
            print(f"velaris deps-diff: {opts['--from']} is not a "
                  f"{DEPS_LOCKFILES_SCHEMA} document", file=sys.stderr)
            return 2
    else:
        try:
            limit = int(opts.get("--max", _DEPS_MAX_UPGRADES))
        except ValueError:
            print(usage, file=sys.stderr)
            return 2
        root = words[0] if words else "."
        try:
            review_doc = deps_review(opts["--against"], root, limit)
        except (RuntimeError, OSError) as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
    if "--json" in opts:
        print(json.dumps(review_doc, indent=2))
    elif "--sarif" in opts:
        log = sarif_deps_review(review_doc)
        print(json.dumps(log, indent=2))
        print_sarif_summary(log)
    elif "--markdown" in opts:
        print(deps_markdown(review_doc))
    elif "--comment" not in opts:
        print("\n".join(deps_review_lines(review_doc)))
    if "--comment" in opts:
        try:
            said = deps_comment(deps_markdown(review_doc), opts["--pr"],
                                bool(review_doc["lockfiles"]))
        except RuntimeError as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
        print(f"velaris deps-diff: {said}", file=sys.stderr)
    return review_doc["exit"]


def card() -> str:
    """The language, small enough to paste into a model."""
    here = os.path.dirname(os.path.abspath(__file__))
    for where in (os.path.join(here, "LLM.md"),
                  os.path.join(here, "..", "LLM.md")):
        if os.path.exists(where):
            return open(where, encoding="utf-8").read()
    return ""


if __name__ == "__main__":
    sys.exit(main())
