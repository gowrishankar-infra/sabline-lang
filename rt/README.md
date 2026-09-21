# sabline-rt

The Sabline runtime, in Rust. `decisions/0002-runtime-in-rust.md` says why
there is a second runtime and what stays in the Python package;
`plan/9.0.md` is the ladder it climbs and the gate that holds it.

**In 9.0.0-alpha.1 this crate holds a lexer and a parser, and nothing
else.** It does not check types, does not check effects, does not run a
program, does not hold a budget and does not write a receipt. It cannot
tell you whether a program is safe to run. The Python package is what
does that, and where the two disagree the Python package is right and
sabline-rt has a defect - that is what a reference implementation is, and
`plan/9.0.md`'s demotion criteria are the only thing that ever changes it.

What the alpha claims is one thing, and it is checked on every commit:
for every Sabline source this project has, sabline-rt builds the same tree
the Python parser builds, or refuses it with the same code, the same
message, the same fixes and the same line.

    python check_agreement.py ../sabline-spec/tests

    examples: 112 files
    stdlib: 14 files
    benchmark/corpus: 85 files
    tests/error_messages: 84 files
    ../sabline-spec/tests: 216 programs in cases
    the lie corpus: 146 programs
    check_sandbox.py: 58 programs
    check_refusals.py: 24 programs
    truncations of every example: 1680 programs
    the adversarial corpus: 113 programs
    paths that are not files: 2 programs
    agreement gate: 2534 programs, 2534 agreements, 0 differences

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
| `src/json.rs` | the canonical JSON writer |
| `src/dump.rs` | the tree as the canonical document |
| `src/bin/sabline-rt.rs` | `sabline-rt ast` |
| `tests/limits.rs` | the depth caps, and the stack they need |
| `fuzz/` | the `cargo fuzz` targets |
