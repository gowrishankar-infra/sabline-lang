# 0005 - The rest of what 9.0 breaks

Decided for 9.0.0, September 2026. `Untrusted of T` (0004) is the
largest break; this is the list of the others, each with its migration.
Nothing outside this list and 0004 breaks in 9.0. If something has to be
added later it is added here, with its argument, before it is written.

STABILITY.md rule 1 is why this list exists: a break ships only in a
major version, and a major version is how a user learns to read the
CHANGELOG. Rule 4 is why each entry says what a user of 8.x has to
change, item by item - the CHANGELOG entry for 9.0.0 is assembled from
these entries and must not say less.

Three new error codes for 0004 (E570, E571, E572) and one here (E312).
No code is reused (rule 3), and `REMOVED_ERRORS` is still empty.

---

## 1. `fs:delete` is a grant of its own

**Today.** sabline-spec section 5.1: "D MUST be `read` or `write`;
anything else after `fs:` is an error", and "`fs` permits every path in
both". There is no builtin that removes a file, so nothing in the
language deletes - but `sabline/confine.py`'s Landlock plan gives an
unscoped write grant `REMOVE_FILE` and `REMOVE_DIR`, because "every
direction" has to mean something when the budget says `fs`.

**In 9.0.** `delete_file(path)` is a builtin: `uses fs`, fallible, and
permitted only by `fs:delete` or `fs:delete:P`, with P resolved by the
same function R as every other path and counts (`@N`) allowed as on the
other directions. `fs` with no direction grants **read and write, and
not delete**. The Landlock plan drops the two remove rights from
`write_all` and adds them only under a delete grant; the macOS profile
and the Windows token follow.

**Why it is a break, exactly.** Not because a program stops running -
no 8.x program can delete a file. Because STABILITY.md's *budget
grammar* clause says "A budget that parses keeps parsing, and grants the
same thing", and `fs` will parse and grant less. That is the clause,
word for word, and it is a major version.

**Migration.** Nothing to do. No 8.x program needs `fs:delete`, so
`sabline migrate --to 9.0` changes no budget and says so; the CHANGELOG
says `fs` no longer implies removal and `fs:delete:DIR` is how removal
is granted. A budget that named `fs:delete` before was a budget error;
it now parses, which is an addition and not a break.

**Why a direction and not a tenth effect.** A `uses` clause names
effects only and can never name a scope (sabline-spec section 3.2), so
an effect would make every program that touches the file system declare
which directions it uses, in a clause the audit already derives. The
audit's `effects` list stays the closed set; the grant does the work,
as it does for read and write.

---

## 2. `db` is an effect, scoped `db:read` and `db:write`

**Today.** `stdlib/db.vel` is a wrapper over `py_new("sqlite3",
"connect", ...)` and `py_do(conn, "execute", ...)`, so a program that
uses a database declares `uses ffi` and runs under
`ffi:_sqlite3,builtins,sqlite3`. An operator granting that has granted
the whole of three Python modules, in both directions, over every
database file the process can open. `run_tests.py`'s budget for
`examples/database.vel` is exactly that line, and it is the most
generous grant in the table.

**In 9.0.** `db` is the eleventh effect (`trust`, 0004, is the tenth).
Three builtins carry it, and they are builtins because an effect can
only be enforced at one - a `.vel` library over `py_do` can declare no
effect the language does not have:

| Builtin | Effect and direction | Gives |
|---|---|---|
| `db_open(path)` | `db`, read | a `Handle`; fallible |
| `db_query(handle, sql, params)` | `db`, read | `Untrusted of Text`: the rows as JSON; fallible |
| `db_exec(handle, sql, params)` | `db`, write | `Untrusted of Int`: rows affected; fallible |

Grants are `db`, `db:read`, `db:write`, `db:read:P`, `db:write:P` and
`@N` counts, with P a path resolved by R as an `fs:` path is and the
literal `:memory:` reserved for an in-memory database. `db_open` needs
at least a read grant for the path; the first `db_exec` needs the write
grant. A db operation outside the granted direction is **E312**, a code
never given before, in the block that already holds E310, E311, E313 and
E314.

**Why it is a break.** A program that runs today under
`ffi:_sqlite3,builtins,sqlite3` will be refused (E310: `db`) until its
budget names `db`. That is a budget that granted enough and now does
not, and it is the reason this is a major.

**Migration.** `sabline migrate --to 9.0` derives the new budget from
the audit exactly as it derives every other: a program that imports
`db.vel` gets `db:read:PATH` and, if it calls `exec`, `db:write:PATH`,
and the `ffi:` grants for sqlite are dropped from the line it prints.
`--write` rewrites the shell and CI lines it can parse. The `uses ffi`
clauses in the program's own functions become `uses db`, which migrate
rewrites, because that one is mechanical and the compiler checks it.

**What this buys, and it is the point.** An operator can grant a program
read of one database file and nothing else - not write, not another
file, not the rest of `sqlite3`, not the rest of Python. That sentence
could not be written before.

---

## 3. `db.vel` takes parameters and nothing else (CWE-89)

**Today**, in the shipped standard library:

    fn run(conn: Handle, sql: Text) -> Text uses ffi or fail {
        return try py_do(conn, "execute", format("[\"{}\"]", sql))
    }

    fn count(conn: Handle, table: Text) -> Int uses ffi or fail ... {
        let rows = try rows_json(conn, format("select count(*) from {}", table))
        ...
    }

`count` interpolates its `table` argument into SQL. `run` takes whole
SQL text and puts it through `format` into a JSON argument list, so a
value holding a `"` breaks the JSON as well. This is CWE-89 in the file
this project ships, and it has been there since the library was written.

**In 9.0.** `db.vel` is rewritten over the builtins of item 2, and there
is no function anywhere in it that takes a statement a caller assembled:

    fn query(conn: Handle, sql: Text, params: List of Text) -> Untrusted of Text
    fn exec(conn: Handle, sql: Text, params: List of Text) -> Untrusted of Int
    fn count(conn: Handle, table: Text) -> Int          // table held to an identifier rule

`sql` is a statement with `?` placeholders, handed to the driver as a
statement; `params` are bound by the driver and never interpolated.
`count` keeps its convenience and holds `table` to the SQLite identifier
rule - letters, digits and underscore, not starting with a digit - and
fails otherwise, because a table name genuinely cannot be a parameter
and pretending otherwise would be the same defect with a longer name.
`run` and `rows_json` are removed; a caller uses `exec` and `query`.

**Why this is not merely advice.** 0004 makes `sql` a sink and `params`
not one, so an `Untrusted` value in a statement is E570 at compile time
and the only place it can go is the parameter list. The library's shape
and the type rule say the same thing, and the type rule is the one that
cannot be worked around by a program that means well.

**Migration.** `db.run(conn, sql)` becomes `db.exec(conn, sql, [])` or,
where the caller was interpolating, `db.exec(conn, "... ?", [value])`.
`db.rows_json(conn, sql)` becomes `db.query(conn, sql, [])`. `sabline
migrate --to 9.0` finds every call, rewrites the two that are mechanical
(an empty parameter list where the argument is a literal), and prints
every call whose statement is built with `format` or `+` without
rewriting it - the same rule that stops it inserting a `trust`: turning
an interpolation into a parameter list is a change to what the query
means, and a person makes it.

---

## 4. `sabline add` refuses a source the project has not named

**Today.** `sabline add <url>` fetches any `https` URL (8.0 added the
redirect rules) and vendors the bytes into `lib/`, recording name,
source, sha256, file and `added_by` in `sabline.lock`. Nothing says
where a library may come from, so nothing in a review distinguishes a
library from the project's own organisation from one from a URL somebody
pasted.

**In 9.0.** `sabline.toml` gains an `[index]` table holding `sources`, a
list of `https` URL prefixes. `sabline add <url>` fetches only a URL
that begins with one of them at a path-component boundary; otherwise it
refuses, exit 1, and names the flag. A local path (`sabline add
./vendor/x.vel`) is unaffected: it is a file the repository already has.

The override is explicit and recorded. `sabline add <url> --outside-index
--reason "..."` fetches it and writes `outside_index: true` and the
reason into that library's `sabline.lock` entry, within
`sabline.lock/1`, so the fact and its stated reason appear in the diff a
reviewer reads. `sabline deps` lists every outside-index library in its
own section; `sabline review --against REF` and the Action's pull-request
comment name each one added since the ref. An empty or absent `[index]`
means no URL is in the index, so every remote `add` needs the override -
which is the safe direction and makes the flag the thing a project turns
off by writing its index down.

**This is not a package registry.** ROADMAP.md says a registry is not
planned, and this does not add one: `[index]` is a list of prefixes in
the project's own file, checked locally, with nobody running
infrastructure. Vendoring with a recorded hash is unchanged.

**Why it is a break.** A command that fetched a URL now refuses it.
STABILITY.md's *command line* clause covers the commands, their
documented flags and their exit codes, and this changes what exit code
an existing invocation gets.

**Migration.** `sabline migrate --to 9.0` reads `sabline.lock`, and for
a project whose libraries all came from URLs sharing a prefix it prints
the `[index]` table to paste into `sabline.toml`; for the rest it prints
the `--outside-index --reason` line per library, with the reason blank.
It writes neither: which sources a project trusts is the decision the
change exists to make someone state.

---

## 5. Every deprecation in force is removed

STABILITY.md's *Deprecations in force* table has nine rows: seven kept
for one major version by 8.6's rename, and two kept since 8.2. Rule 2
says a deprecation is removed no sooner than the next major version.
This is that version, and all nine go:

| Removed | Since | What it was |
|---|---|---|
| the `velaris` command | 8.6 | a second entry point running `sabline`'s `main()` |
| `import velaris` | 8.6 | the `sabline` module object itself |
| `velaris.VelarisError` | 8.6 | `SablineError` under another name |
| `velaris_mcp`, `velaris_mcp_install`, `velaris_magic` | 8.6 | the `sabline_*` modules |
| `VELARIS_*` environment variables | 8.6 | read where the `SABLINE_*` name was unset |
| `velaris.capabilities`, `velaris.toml`, `velaris.lock` | 8.6 | read when the `sabline.*` file was not beside them |
| a `velaris.*` document schema | 8.6 | read as the `sabline.*` format of that version |
| `--no-cache` | 8.2 | nothing, with a notice |
| `sabline clean` | 8.2 | nothing, exit 0, with a notice |

One line of that table does **not** go, and the difference matters:
**the earlier predicate type names stay accepted for verification,
forever.** `sabline/predicates.py` holds the addresses on
`gowrishankar-infra.github.io` and `velaris-lang.dev` beside the
`sabline.dev` ones, and STABILITY.md says "nothing is ever removed from
that list - a name only ever joins it". Those names were *signed*.
Removing one would stop an attestation made in 2026 from verifying,
which is not a deprecation, it is breaking a signature. A major version
does not license that.

**Migration.** `sabline migrate --to 9.0` finds each removed name in the
shell scripts, CI files and notebooks it can parse, rewrites them - the
rename is a textual substitution and the compiler checks the result -
and lists the environment variables it found set. `check_rename.py`,
which runs each deprecation on every CI leg today, becomes the suite
that asserts each is *gone*: the command absent, the import an
`ImportError`, the `VELARIS_*` variable ignored with a line saying so
for one release. The nine external breaks a blanket substitution made
during 8.6 are the reason that suite is rewritten rather than deleted.

---

## 6. `sabline receipt --as runtime-trace` (an addition, not a break)

in-toto defines
`https://in-toto.io/attestation/runtime-trace/v0.1`, whose predicate has
`monitor`, `monitoredProcess`, `monitorLog` and `metadata`. A Sabline
receipt is a runtime trace by any reading, and a consumer that already
ingests runtime traces should not have to learn a second format to read
one.

`sabline receipt show RECEIPT --as runtime-trace` writes the receipt as
a Statement of that type, over the same subjects:

- `monitor.type` names Sabline and its version; **`monitor.config`
  carries the budget as the trace policy** - the observation scope, in
  the grammar of sabline-spec section 4, which is exactly what a budget
  is and is the field this rendering exists for;
- `monitoredProcess` carries the run's own identity and **no host
  identifier**, because a receipt does not record one and a rendering
  must not invent what the record does not hold;
- `monitorLog` is built from `grants_used`, `effects_used` and
  `refusals` - so its file and network entries are at **grant**
  granularity, `fs:read:/work/data` and `net:api.example.com:443`, never
  the path read or the URL fetched. The rendering says so in the
  statement itself, because a reader of a runtime trace reasonably
  expects paths, and a document that quietly gave grants instead would
  be read as saying less happened than did. sabline-spec section 8.7's
  rule - a receipt holds no value the program handled - has no exception
  here either;
- `metadata` carries `startedAt` and the finish derived from
  `wall_time_ms`.

**It breaks nothing.** `sabline receipt show` without the flag writes
exactly what it writes today; `sabline.receipt/1` is unchanged; nothing
new is written by default. It is listed here because it rides with 9.0
and a reader of this file should find every change 9.0 makes, and
because listing it and then saying it is not a break is how a list like
this stays trustworthy.

---

## 7. The capability predicateType, **only if** in-toto #594 has settled

`sabline attest` writes `predicateType:
https://sabline.dev/capability/v1`. THREAT_MODEL.md's Known open table
says what is wrong with that: "a predicate type is a name on a domain",
and a domain can change hands.

in-toto/attestation issue **#594**, *"Proposal: capability predicate
(what an artifact may touch)"*, is this project's proposal to register
the type upstream; the branch (`gowrishankar-infra/attestation`,
`velaris-capability-predicate`) is pushed and the pull request is not
opened, because in-toto's AI policy asks the submitter to write the
description and sign the DCO themselves. **Checked on 2026-09-21, #594
is open.**

**The decision is conditional and the condition is checked once, when
the release candidate branches.** If #594 has been accepted and the type
has an `in-toto.io` name by then, `sabline attest` writes that name and
the three sabline-held names join the accepted-for-verification list,
where nothing is ever removed. If it has not, nothing changes and the
row stays in the Known open table. No part of 9.0 waits on it, and it
must not become a reason to hold the release.

**Why it would be a break.** STABILITY.md's *library API* clause covers
the in-toto Statements `attest` returns; `predicateType` is a field of
one, and its value would change. 8.6 made the same kind of change in a
minor and argued it on a `compatibility:` line; this one can go in a
major, so it does.

**Migration.** None for a reader - every Sabline verifier accepts all
four names. For a consumer matching the string itself, the CHANGELOG
prints the old and the new, and `sabline verify` keeps accepting both.

---

## 8. Two rows of the Known open table that only a major can close

**A program that stalls a review.** `sabline review` compiles every
program under a directory at a git ref and in the working tree "with
none of the ceiling `check` and `audit` have had since 8.0 and
`capabilities check` has had since 8.2.1", so source written to exhaust
the type checker holds the Action's pull-request comment step until the
job's own timeout. In 9.0 `review` takes the same ceiling, with the same
flags (`--check-timeout`, `--check-memory-mb`, 60 s and 2048 MB) and the
same codes (E613, E614), per program rather than per run. It is a break
because a review of a very large tree that used to finish now stops, and
the migration is the flag. The advice in that row - give the job a
`timeout-minutes` - stays good and is now a second line of defence
rather than the only one.

**A write grant to where the host imports from.** An ejected launcher
already refuses a budget that "lets the program write where Python
imports from - a `PYTHONPATH` entry, a site-packages, the user's site";
a plain run does not, so a program with such a grant can leave code the
next process runs. In 9.0 the budget parser refuses such a grant on
every run, as the ejected launcher does, at parse time and with the
message the launcher gives. It is a break because a budget that parsed
stops parsing - the *budget grammar* clause again - and the migration is
to grant writes to a data directory, which is what THREAT_MODEL.md's
recommendation for that row already says.

**The rest of that table is not closed by a version number**, and 9.0
must not be read as closing it: timing and other side channels; a
granted `ffi` module's full behaviour; native code inside one; what
confinement leaves on each platform (9.0 makes Windows strictly better -
alpha.4 - and does not make it complete); what a receipt shows that is
not a value; an ejected directory keeping the Sabline it was ejected
with; a predicate type being a name on a domain; and the user running
sabline being trusted. Each stays in the table, and 0004 adds one to it:
untrusted content arriving through a granted module.

---

## What was considered and is **not** in 9.0

- **Removing the Python runtime.** plan/9.0.md item 7. 9.0 makes the
  Rust runtime the one that runs; the Python one is still installed and
  is still the reference.
- **Making a granted module's results `Untrusted`.** 0004 says why, and
  it becomes a row of the Known open table instead.
- **A `net:` grant that holds the socket's peer to the granted host**
  rather than to the URL, beyond what 8.0's E317 already does for
  proxies. It belongs with the Rust runtime's own networking, is not
  designed, and a half-made version would claim more than it holds.
- **Removing `--allow all`.** It is loud, recorded and honest, and an
  operator who writes it has waived the gate deliberately. Taking it
  away would move that decision into a longer budget line, not out of
  existence.
- **Anything to do with concurrency.** SPEC.md section 13 and ROADMAP.md
  both say why, and a second runtime does not change the argument: the
  effect system cannot describe a data race.
