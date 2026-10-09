# sabline-rt

The Sabline runtime, in Rust. `decisions/0002-runtime-in-rust.md` says why
there is a second runtime and what stays in the Python package;
`plan/9.0.md` is the ladder it climbs and the gate that holds it.

**This crate holds a lexer, a parser, from M2 the loader, the checkers
(effects, types with `Secret of T` and `Money of C`, the rules for
`main`, and each loop's termination verdict) and the budget parser, and
from M3 the interpreter**: a program run under a budget, every builtin
spent against it, and the work of every builtin short of the network,
Python and a tool - the pure ones, the console's, a file read, written
and looked for under the budget's grants, counts, read ceiling and
credential rule, the clock and randomness (frozen and seeded as
`--freeze-time` and `--seed` give them), the environment, `declassify`
and the two HMACs. The work of a builtin that reaches the network, calls
Python or a tool is not ported yet: under a budget that does not grant
its effect it is refused before its work would start, exactly as the
reference refuses it. It does not prove, does not hold a budget at the
operating system and does not write a receipt, so it cannot tell you
whether a program is safe to run. The Python package
is what does that, and where the two disagree the Python package is right
and sabline-rt has a defect - that is what a reference implementation is,
and `plan/9.0.md`'s demotion criteria are the only thing that ever changes
it.

What it claims is checked on every commit: for every Sabline source this
project has, sabline-rt builds the same tree the Python parser builds, or
refuses it with the same code, the same message, the same fixes and the
same line; and `sabline check` and sabline-rt find the same problems in it,
stage by stage, in the same order, with the same messages, and give each
loop the same verdict for the same reason; and run under the budget `io`,
with the same input, it prints the same text to each channel, ends with
the same status and stops with the same error - and so does every program
written for a budget, run under its own in a tree of files. And for every budget the
gate holds - sabline-spec's L1 budget cases, what is made from them, and
the edges - both parse it to the same grants and counts, or refuse it with
the same words.

    python check_agreement.py ../sabline-spec/tests

      examples: 122 files
      stdlib: 14 files
      benchmark/corpus: 111 files
      tests/error_messages: 89 files
      ../sabline-spec/tests: 216 programs in cases
      the lie corpus: 146 programs
      check_sandbox.py: 58 programs
      check_refusals.py: 24 programs
      check_termination.py: 64 programs
      truncations of every example: 1830 programs
      the adversarial corpus: 113 programs
      the checkers' corpus: 3785 programs
      the runs' corpus: 222 programs
      paths that are not files: 2 programs
      programs run under their own budgets: 106
      the L1 budget cases: 280 budgets
      their mutations: 2558 budgets
      the budgets' edges: 115 budgets
      paths through a tree: 14 budgets
      the parsers: 6798 compared, 6798 agree, 0 differ
      the checkers: 6798 compared, 6798 agree, 0 differ
      the budget parser: 2967 compared, 2967 agree, 0 differ
      the interpreters: 6798 compared, 6798 agree, 0 differ
      the interpreters, under their budgets: 106 compared, 106 agree, 0 differ
      the builtin tables: 1 compared, 1 agree, 0 differ
    agreement gate: 23468 comparisons, 23468 agreements, 0 differences

## Building it

    cargo build --release --manifest-path rt/Cargo.toml
    cargo test  --manifest-path rt/Cargo.toml
    cargo clippy --manifest-path rt/Cargo.toml --all-targets -- -D warnings
    cargo fmt --manifest-path rt/Cargo.toml --check
    cargo deny --manifest-path rt/Cargo.toml check

The minimum Rust version is **1.82**, stated in `rt/Cargo.toml` as
`rust-version` and held by a CI leg pinned to it. The edition is 2021.

**The crate has no dependencies.** The canonical JSON writer, CPython's
`ascii()` of one character, the float form, the Unicode decimal-digit
table and the command line are all in the crate, because each of them has
to match one particular CPython and a general library is free to spell any
of it differently - and a difference in spelling would read as a
difference between two parsers. `plan/9.0.md` caps the default build at
25 crates and asks for an argument per crate; that argument is easiest to
make when the count is zero, and `rt/deny.toml` is where it stops being
zero quietly. `cargo vet` joins the legs when there is a first dependency
to audit; with none it has nothing to say, and a green run of it would be
a green run of nothing.

## The canonical AST dump

One document, written the same way by both implementations, which is what
the agreement gate compares.

    sabline ast --json <file.vel>       from the Python package
    sabline-rt ast <file.vel>           from this crate

It is **not a stable interface** and is not in `tests/api/golden.json`. It
is a comparison surface, and STABILITY.md's "anything else in the package"
clause covers it. Nothing but `check_agreement.py` reads it. The Python
side is `sabline/ast_dump.py`; this side is `src/dump.rs` and `src/json.rs`.

### The document

```json
{"dump":1,"ok":true,"program":{"funcs":[...],"imports":[...],"records":[...]}}
```

or, for a program the lexer or the parser refused:

```json
{"dump":1,"error":{"code":"E101","fixes":[...],"line":3,"message":"..."},"ok":false}
```

`dump` is the format's version, carried so that a change to the format is
never read as a difference between two parsers. One document covers both
outcomes, so one comparison covers the tree and the refusal.

A node is an object with `kind` and that node's own fields, named as
`sabline/nodes.py` names them. `for` is already desugared to `while` and
function values are already lifted into top-level functions, because the
parser does both and nothing after it knows about them.

### How it is written

* **Keys sorted** by code point, and **no whitespace at all**: `,`
  between items, `:` after a key, `[]` and `{}` for an empty container.
  What CPython's `json.dumps(..., sort_keys=True, separators=(",", ":"))`
  writes. The absence of indentation is a decision, not a default: two
  spaces a level makes a document O(depth squared), and the dump of the
  deepest program the parser accepts - 40 KB of source, which the
  adversarial corpus holds on purpose - was 352 MB of mostly spaces,
  written twice on every leg of CI. Compact it is 316 KB. Nothing reads
  the dump by eye: the gate reports a difference as a path through the
  tree.
* **ASCII only.** Every character outside `\x20` to `\x7e` is escaped:
  `\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t` by name, everything else as
  `\uxxxx` in lowercase hex, a character past the basic plane as the two
  `\uxxxx` of its surrogate pair. That is `ensure_ascii=True`.
* **Bytes, not text.** Both write the document and one `\n` as bytes, so
  that a Windows text stream's `\r\n` cannot be mistaken for a difference.
* **A whole number is decimal text**, leading zeros gone. The reference's
  integer literals are arbitrary precision - `let x = ` followed by 4,300
  digits is a `Num`, and 4,301 is E407 - so no machine word holds one.
* **A float is `d[.ddd]eE`**: the shortest decimal that reads back as the
  same double, with one digit before the point. `1.0` is `1e0`, `0.00001`
  is `1e-5`, `100.0` is `1e2`. Neither language's default printing is the
  other's - CPython writes `1.0` and `1e+16`, Rust writes `1` and
  `10000000000000000` - so the dump uses a third form both can write, and
  it is the form Rust's `{:e}` already writes.
* **`effects` is sorted.** The Python parser holds them in a `set`, which
  has no order to compare.
* **A line is a number, and there is no column.** The reference's tokens
  carry a line and nothing else, so neither implementation can offer one.
* **There are no spans and no memory addresses**, because there is nothing
  in the reference tree that holds either.

### Two files at a time

`--list <paths-file>` takes a file of one path per line and writes a
framed stream, because the gate compares some thousands of files on every
commit in every leg and a process per file would make it the slowest thing
in CI:

```text
sabline.ast-batch/1
--- <bytes> <path>
<that many bytes of canonical document>
--- <bytes> <path>
...
```

A length rather than a separator, so a record's bytes **are** the
document's bytes and a reader never has to parse one to find the next. The
gate compares those bytes; it reads a document only to say where two of
them first differ.

## The canonical check document

The second comparison surface (9.0, M2): what `sabline check` finds in one
program, without the prover, which sabline-rt does not have.

    sabline check-dump <file.vel>                          from the Python package
    sabline-rt check --install-dir <dir> <file.vel>        from this crate

`--install-dir` is where the host keeps the shipped standard library, as
`<dir>/stdlib/`: an import that a program's own directory does not have is
looked for there by its base name, as the Python package looks beside
itself. The gate gives both the same place - its own checkout, which is
where the Python package it runs keeps its library.

```json
{"check":1,"errors":[...],"loops":[...],
 "stages":{"load":null,"main":[],"main_run":[],"effects":[],"types":[]}}
```

`stages` is the reference's pipeline, stage by stage and in its order:
`load` (the one refusal that stopped the loader, or null), `main` as
`sabline check` asks about it and `main_run` as a run does (where a
missing `main` is E400), `effects`, and `types` - null when an earlier
stage found something, because the type checker then does not run. Each
problem is `code`, `file`, `fixes`, `line` and `message`. `errors` is every
problem once, in order, which is what `sabline check --json` prints less
the `reference` line every error carries; `loops` is every loop of every
function, lifted ones included, with `function`, `file`, `line`,
`verdict` and `why`. It is written the way the AST dump is, and framed
the same way under `--list`, with the header `sabline.check-batch/1`.

`sabline-rt tables` and `sabline check-dump --tables` write the builtin
tables both checkers read, so that a builtin added to one runtime and not
the other is a difference whether or not any program calls it.

## The budget document

The third comparison surface (9.0, M2): what a budget parses to.

    sabline check-dump --budgets <file>      from the Python package
    sabline-rt budget --list <file>          from this crate

Each line of `<file>` is one budget case as JSON, `[allow, deny]`, each a
string or `null`, exactly as a sabline-spec `budget` case gives them:
`allow` is the budget's text (`null` is the default, `io`) and `deny` is a
comma-separated list of effects to take away. JSON, so that a tab, a comma
or a character past ASCII reaches both runtimes unchanged. Each answer is
what the library's `_budget_from` makes of the case:

```json
{"valid":true,"shape":{"effects":[...],"fs":[...],"net":[...],"counts":{...}},
 "spec":"...","tools":{...},"tool_limits":{...}}
```

or `{"valid":false,"refused":"..."}` with the refusal word for word.
`shape` is what a conformance case compares; `spec` is the budget written
back as the command line writes it, and `tools` and `tool_limits` are the
tool grants, which no conformance case reads yet. The stream is framed as
the others are, with the header `sabline.budget-batch/1`, each record named
by its line's number.

**A path is resolved when the budget is parsed** (sabline-spec 5.1's
resolution R): `normcase(realpath(path))` against the working directory.
So the gate runs both runtimes in one scratch directory, holding a small
tree - a directory, a file, a link to the directory, a link to nothing,
and on Windows a junction - that `agreement_budgets.py`'s paths walk
through.

`sabline conformance --runtime rust` asks the same question for L1's 280
budget cases through this binary, and labels every other case as answered
by the Python package (`check_conformance_rust.py` holds it to that).

## The run document

The fourth comparison surface (9.0, M3): what a run of one program did.

    sabline run-dump --list <paths-file>                   from the Python package
    sabline-rt run --install-dir <dir> --list <paths-file> from this crate

Each program is run as `sabline <file>` runs it - the checkers as the
command line runs them, then `main` - with five things fixed so that the
same program gives the same document on every machine and in both
runtimes, and three left out because sabline-rt does not have them in
9.0:

| Fixed | As |
|---|---|
| the budget | `io`, what a run with no `--allow` gets, unless the list's line gives one |
| the input | `1\n2\nthree\n`, read as the library's `stdin=` is read |
| the arguments | `["first", "2"]` |
| a step limit | 20,000 calls and loop turns, after which the run is stopped where it is |
| a size limit | 4,194,304 of what the run makes, counted as below, after which the run is stopped at the operation that passed it |

| Left out | Because |
|---|---|
| the prover | decisions/0002 keeps it in Python; a run here leaves every promise to be checked while running, which is the lie corpus's point |
| native code | `fuzz_native.py` holds the Python runtime's two engines to each other |
| the operating system's confinement | M4 |

The step limit is the gate's and nothing else's. A wall-clock limit would
stop a program that does not end wherever each runtime's own speed had
taken it; a count of calls and loop turns stops it at the same one in
both, so its output up to there is compared too. In the Python package
it is `state._STEP_LIMIT`, `None` everywhere but `run-dump`.

**The size limit** is its partner, for a program that grows without end:
a text doubled forty times exhausts memory long before it makes 20,000
calls, and how far each runtime gets before its machine stops it is the
machine's. So both count what a run makes, the same way, and stop at the
operation that takes the count past the limit - never by wall-clock time
and never by real memory, whose cap stays the operating system's (E611,
M4). What makes a value, and so is counted: a `+` that makes a text or a
list; a list or a map written in the program; the answer of every builtin
but `get`, `get_or` and `declassify`, which hand back a value the program
already holds (and `to_text` of a text, which is itself); and the text
`print` and `log` write and `ask` asks with, before it is written. A text
counts its UTF-8 bytes, a lone surrogate three; a list or a map its items;
anything else nothing. Every program the gate holds that ends makes less
than a fortieth of the limit. In the Python package it is
`state._SIZE_LIMIT` and `runtime.size_of`, `None` - nothing counted -
everywhere but `run-dump`.

**A line of the list** is a program's path, run as above; or a JSON object
naming one with what a command line could add: `allow` and `deny` (the
budget), `seed`, `freeze_time` (epoch seconds), `max_read` (the read
ceiling, in bytes) and `environ` (variables set for the run over the
process's environment, which is how the gate gives both runtimes the same
`~`). The document does not repeat them; the gate gives both the same line.

```json
{"run":2,"refused":null,"error":null,"exit":0,
 "stdout":"...","stderr":"...","stopped":null,"stopped_by":null,
 "raised":null}
```

`refused` is the problems the check found, one each in file and line
order, when it found any; `error` the error the run stopped with, its
message quoting what the program held; `exit` the status, `null` when a
limit stopped it; `stdout` and `stderr` the text written to each,
compared as text - code points, a lone surrogate included - rather than
as whatever bytes a console would have made of it; `stopped` the line a
limit stopped it at and `stopped_by` which, `"steps"` or `"size"`; and
`raised` the name of a Python exception that escaped the reference, which
is a defect there and a difference here. The stream is framed as the
others are, with the header `sabline.run-batch/1`.

`check_agreement.py` runs every program it holds, and would print the
ones it does not: `RUN_EXCLUDED`, each with its reason, which is empty.
Its one program until the size limit - a text doubled forty times, to be
stopped by the memory cap it tests - is stopped by the size limit now, at
the same operation in both. And it runs every program written for a
budget under that budget - the runs' corpus's own table, check_sandbox.py's
rows and sabline-spec's L2 cases, each of the last two whose budget grants
only effects whose work is ported - in a tree of files made afresh for each
runtime, with `~` the tree's home.

## What had to be written down to be copied

Four things in the reference are decided somewhere other than the lexer
and the parser, and each would have been got wrong by reading those two
files alone.

**`open(path, encoding="utf-8")`** in `sabline/loader.py` decides three of
them at once (`src/source.rs`): UTF-8 strictly, so bytes that are not UTF-8
are E512 - with the loader's wording, which says "cannot import" even
about a file nobody imported; **universal newlines**, so `\r\n` and a lone
`\r` are both `\n` before the lexer sees one, and the lexer's own
`[ \t\r]+` never sees a `\r` from a file; and **the byte-order mark
stays**, because `utf-8` is not `utf-8-sig`, so a file that begins with one
begins with U+FEFF and is E000 on line 1.

**`\d` is every Unicode decimal digit.** The NUMBER and FLOAT patterns are
`\d+` and `\d+\.\d+`, and `\d` in a `str` pattern is category Nd, not the
ten ASCII digits - so `let x = ١٢` is `Num(12)`, because `int()` reads each
character by its decimal value. `src/unicode_nd.rs` carries that set, and
`scripts/gen_unicode_nd.py` writes it from CPython's own `\d`.
`[A-Za-z_]` is ASCII, though, so a non-ASCII letter is E000 and not an
identifier: the two rules in one regular expression disagree about what a
character is, and both are copied rather than reconciled.

**The set of characters that is Nd follows the Unicode version of the
CPython that generated the table**, which is written into the file's
header. Two CPythons this project supports can disagree about whether a
recently assigned code point is a digit, so the reference disagrees with
itself there. No program in any corpus is affected; it is written down
because it is true rather than because it bites.

**`Parser.lambda_n` is a class attribute the parser never resets**, so
`fn#N` and `for#N` depend on how many function values the *process* has
parsed before. `sabline ast --json` sets it to zero for each file, so a
dump of one file is a function of that file. This crate's counter belongs
to the parser, which is the same thing one file at a time.

**The checkers are a transliteration, and three of their properties are
copied because each changes what a check reports** (`src/checker.rs`
says more):

* `infer` runs again wherever the reference runs it again - three times on
  a map's first value, twice on a key it puts in a message - because
  inferring a function value checks that function, and the check appends
  what it finds to the one list of problems. A cache would be faster and
  would report a different list.
* **The counter that names a lifted function value runs across every file
  one load parses**, in the order the loader parses them, because
  `Parser.lambda_n` is a class attribute; `fn#N` in a message is that
  sequence's `N`. The check document sets it to zero per program, as the
  AST dump does.
* **A file's name is spelled the way CPython's `os.path` spells it**:
  `os.path.join(os.path.dirname(importer), path)`, unnormalised, which is
  what an error's `file` and an E512 or E513 message say. `src/pypath.rs`
  is `ntpath` and `posixpath`, both compiled and tested everywhere.

Two smaller ones: CPython's `str.strip()` strips U+001C to U+001F, which
Unicode does not call white space (`pyrepr::py_isspace`), and `expr_str`
writes a float as CPython's `repr` does, `1e-05` and `1e+16` included
(`pyrepr::py_float_repr`).

**The budget parser copies four more** (`src/budget.rs` says more):

* **`os.path.realpath` is CPython's walk, not `std::fs::canonicalize`.**
  Canonicalize fails on a path that does not exist; CPython resolves as
  much as exists - following links and, on Windows, junctions - and joins
  the rest on. `src/pypath.rs` copies `ntpath.realpath` (with
  `_getfinalpathname` as the system's final-path call, and its walk up
  through the parts that are not there) and posixpath's link-by-link walk,
  each over a small trait so both are tested everywhere against answers
  CPython gave over the same fake disk.
* **`ntpath.normcase` is `LCMapStringEx`** from CPython 3.13 on Windows:
  one character for one, no final sigma, `İ` left alone. Safe Rust cannot
  call it, so the port lowers one character for one with Unicode's table,
  and about four hundred letters that Windows' older table does not lower
  (`ẞ`, Cherokee, some Greek) would differ. No budget in the gate holds
  one.
* **`str.isdigit()` is more than the decimal digits**: superscripts and
  circled digits count, so `net:*.1.²` is a wildcard over an IP literal.
  `src/unicode_digit.rs` carries them, written by
  `scripts/gen_unicode_digit.py`.
* **A count is any size, up to 4,300 digits**: `int()` has no upper
  bound, and from CPython 3.10.7 refuses to read more than 4,300 digits,
  leading zeros included, with a message of its own that becomes the
  budget's refusal. `budget::Count` holds the digits. That message is
  the one place the supported CPythons disagree with each other: 3.10
  says "Exceeds the limit (4300) for ...", 3.12 and later "(4300
  digits)". The crate writes the later, and the gate holds no count that
  long, because no single answer would match every leg.

**The interpreter copies more than any stage before it**, because what a
running program sees is CPython's object model (`src/value.rs`,
`src/text.rs`, `src/interp.rs` say more):

* **A Text is code points** (`text::Text`), not UTF-8: `length` counts
  them, `code_at` gives one, and a lone surrogate - which a program meets
  the moment it reads `"\ud800"` out of a JSON document - is a value like
  any other. `upper`, `lower` and the characters `repr` leaves alone come
  from tables generated from CPython (`src/unicode_text.rs`,
  `scripts/gen_unicode_text.py`), with `lower`'s one rule that depends on
  context - a capital sigma at the end of a word - copied from CPython's
  `handle_capital_sigma`.
* **`to_text` and `str` are different functions**, and both are needed:
  `print` writes `true` and `[a, b]`, and a broken promise's message names
  its values as an f-string writes them, `True` and `['a', 'b']`, with
  `repr()`'s choice of quotes and escapes.
* **A whole number is a Python `int`.** Arithmetic is checked on its
  result, so a literal past 64 bits is a value (`print(99999999999999999999)`
  prints it), and so is `%` of one; `src/bigint.rs` holds such a value.
  Division floors and a remainder takes the divisor's sign; a float's
  floor division and remainder are CPython's `float_divmod`; `round` is
  half to even; an `int` and a `float` compare exactly.
* **A container compares its items by identity first**, as CPython's
  `PyObject_RichCompareBool` does, so a record holding a NaN equals
  itself and a NaN does not. Every NaN a run makes carries an identity of
  its own (`value::fresh_float`).
* **A map is a `dict`**: insertion order, a key already there keeping its
  place and the key first given for it, and `1`, `1.0` and `true` one key.
* **The JSON builtins are `json.loads` and `json.dumps`** (`src/pyjson.rs`,
  a transliteration of `_json.c`'s scanner): which texts parse, the value
  each gives, and every message, with its line, column and character. The
  messages are CPython 3.10's to 3.12's; 3.13 says "Illegal trailing comma
  before end of object" where they say "Expecting property name enclosed
  in double quotes", so the gate holds no document with such a comma.
  `int()` and `float()` of a text, which `json_int` and `json_float` use,
  are copied with their Unicode digits, white space and underscores.
* **`base64_decode` is `b64decode(..., validate=True)`**, which from
  CPython 3.11 is `a2b_base64`'s strict mode: 3.10 decodes padding at the
  start of a quad (`"YWJj=="`) that 3.11 and later refuse. The crate is
  3.11's and later; the gate holds no such text.
* **What a run reaches of the machine is CPython's** (`src/host.rs`):
  `env()` reads `os.environ`, which on Windows upper-cases every name -
  `env("path", "")` finds `Path` - and leaves out the C runtime's hidden
  `=C:` variables, and elsewhere decodes bytes as `os.fsdecode` does; `~`
  is `os.path.expanduser`'s, `USERPROFILE` before `HOMEDRIVE` and
  `HOMEPATH`; `random(n)` under a seed is `random.Random(seed).randrange`
  - the Mersenne Twister seeded by `init_by_array` from the seed's
  absolute value in 32-bit words, and `_randbelow`'s rejection loop over
  `getrandbits`; a file is read as `open(path, encoding="utf-8")` reads
  it, strictly, with universal newlines (`\r\n` and `\r` alone are `\n`)
  and a byte-order mark kept; written as `open(path, "w")` writes it, each
  `\n` this system's line end and the file emptied before a text that
  cannot be encoded is refused; and an operating system's refusal to open
  one is `OSError.strerror`'s words - the C library's `strerror`, or on
  Windows the C runtime's text for the `errno` its `_dosmaperr` gives the
  system's error.
* **A file builtin is guarded as `budget.allow_path` guards it**:
  `normcase(realpath(path))` against each grant's, the credential rule
  (E318) before the ordinary one - the documented locations under `~`,
  and any `.env`, `*.pem` or `*.key`, matched as `fnmatch` matches on this
  system - then E313 with the directory to grant; the count (E315) spent
  after the grant and before the work, so a failed read spends one; and
  the read ceiling (E316) asked of `os.path.getsize` before the read.

**Defects in the reference found by comparing runs** were fixed in the
reference, as M1 fixed E000's message: a broken promise naming a record
printed the record's memory address, so the same promise gave a different
message on every run (`RecordValue` now has a `repr`); a function value
printed or named in a message was written as Python writes the object, an
address included, and prints as `fn` and its name now (SPEC.md 12a); and
`all_of` and `any_of` were Python's `all()` over a generator, so a function
value reaching them again nested C calls and, from CPython 3.12, met the C
recursion limit before the depth limit - the same program gave E609's
"nested too deeply to print" at line 0 there and the depth limit's E609 on
3.10. They loop now, and the depth limit fires on every CPython.

## No `unsafe`

The workspace sets `unsafe_code = "forbid"`, so there is none in this
crate and none can be added without changing that line.

A later alpha has to: Landlock, seccomp-bpf, `sandbox_init`, the Windows
AppContainer and every C ABI entry point are `unsafe` and cannot be
otherwise. `plan/9.0.md`'s rule applies from the first block, and it is
not "as few as possible" - a count is not a property:

* `#![forbid(unsafe_code)]` stays on every module that does not need it,
  which is the whole of the lexer, parser, checkers and interpreter.
* `unsafe_op_in_unsafe_fn` is denied, so an `unsafe fn` does not silently
  make its body unsafe.
* **Every `unsafe` block carries a `// SAFETY:` comment saying which
  invariant makes it sound, and names a test that would fail if that
  invariant were broken.** A lint job greps every block for the comment
  and fails without one; a second scan requires each comment to name a
  test by name, and requires that test to exist.
* `cargo miri test` runs on the parts Miri can run, on the Linux leg.

## A panic is never an answer

No input is allowed to make sabline-rt panic, abort, overflow its stack or
hang. Every malformed input is a coded error. Three things hold that:

* **`cargo fuzz`** (`crates/sabline-rt/fuzz`, outside the workspace
  because it needs a nightly toolchain): `parse` runs arbitrary bytes
  through `decode` and the parser, `dump` runs them all the way to the
  canonical document. Briefly on every push, longer in `monthly.yml`.

      cargo +nightly fuzz run parse -- -max_total_time=30

* **The differential fuzzer**, `fuzz_parsers.py --target agreement`: the
  same generated input to both parsers, which must answer the same tree or
  the same code, message, fixes and line. Coverage-guided, as the rest of
  that file is, and seeded from the corpora and from
  `agreement_edges.py`.

* **`agreement_edges.py`**, which the gate carries on every commit: the
  standing adversarial pass written down as a table rather than done once
  - deep nesting on each side of each cap, literals of 4,299, 4,300 and
  4,301 digits, bytes that are not UTF-8, byte-order marks, CRLF, lone
  CR, NUL, Arabic-Indic and Devanagari and fullwidth digits, combining
  marks, a right-to-left override, an astral character, a line of a
  hundred thousand characters, and the shapes of the grammar nothing else
  reaches.

**The stack.** The parser is recursive and its caps let a program nest
4,000 blocks and 1,000 expressions deep before E102 - deeper than a
default thread stack carries. A stack overflow is not a panic; it is the
process going away with no message, which is worse than any refusal. So
the library publishes `PARSE_STACK` and `on_parse_stack`, every entry
point that parses runs the parse there, and `tests/limits.rs` holds the
deepest program the parser accepts against that number. The reference does
the same thing for the same reason: `load_program` raises CPython's
recursion limit to 20,000 before it parses.

## What is here

| File | Holds |
|---|---|
| `src/lib.rs` | the crate, `PARSE_STACK` and `on_parse_stack` |
| `src/errors.rs` | `SablineError`: a code, a message, a line, the fixes |
| `src/source.rs` | a file's bytes to the text the lexer sees |
| `src/lexer.rs` | text to tokens, the `re` alternation written out |
| `src/unicode_nd.rs` | every Unicode decimal digit (generated) |
| `src/nodes.rs` | the tree, field order for field order with Python's |
| `src/parser.rs` | tokens to the tree, and the free-variable walk |
| `src/pyrepr.rs` | CPython's `ascii()` of a character, and the float form |
| `src/json.rs` | the canonical JSON writer, and a reader for the budgets the gate sends |
| `src/dump.rs` | the tree as the canonical document |
| `src/pypath.rs` | CPython's `os.path`, Windows and POSIX, `realpath` included |
| `src/tables.rs` | the builtins, the effects and the currencies every checker reads |
| `src/types.rs` | types as text: `fn_sig_parts`, `type_mentions`, `Money of C` and `Secret of T` |
| `src/show.rs` | `expr_str` and `nice_name`, an expression as a message quotes it |
| `src/loader.rs` | a file and everything it imports, as one program |
| `src/effects.rs` | the effect checker, and E204 |
| `src/checker.rs` | `check_main` and the type checker |
| `src/termination.rs` | which loops are shown to end |
| `src/check_dump.rs` | what `sabline check` finds, as the canonical check document |
| `src/budget.rs` | the budget parser, and the budget document |
| `src/unicode_digit.rs` | every digit `str.isdigit()` accepts that is not decimal (generated) |
| `src/text.rs` | a Text as code points, and CPython's `str` algorithms over them |
| `src/unicode_text.rs` | CPython's `upper`, `lower` and `isprintable` (generated) |
| `src/bigint.rs` | a whole number of any size, for the values of a run past 64 bits |
| `src/value.rs` | a running program's values, compared, hashed and written as CPython does |
| `src/pyjson.rs` | `json.loads`, `json.dumps`, and `int()` and `float()` of a text |
| `src/digest.rs` | SHA-256, HMAC-SHA-256, hexadecimal, base64 and `url_encode` |
| `src/host.rs` | what a run reaches of the machine, as CPython reaches it: `os.environ`, `~`, `random.Random`, a file's text, `OSError.strerror` |
| `src/interp.rs` | the interpreter, every builtin's spending against the budget, the file grants, counts and ceiling, and the size limit |
| `src/run_dump.rs` | what a run did, as the canonical run document |
| `src/bin/sabline-rt.rs` | `sabline-rt ast`, `check`, `tables`, `budget` and `run` |
| `tests/limits.rs` | the depth caps, and the stack they need |
| `tests/runs.rs` | a library's function value under a name, how a function value prints, the size limit, a file grant |
| `fuzz/` | the `cargo fuzz` targets |
