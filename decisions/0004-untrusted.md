# 0004 - `Untrusted of T`

Decided for 9.0.0, September 2026. The design; the spec repository
carries it as a draft appendix marked "9.0, not yet normative", and
nothing is normative until 9.0 ships it in both runtimes.

## What is open

docs/runner.md says it, under "What is not here yet":

> A result is a `Text` like any other; nothing marks it as the host's
> words rather than the program's, so what a tool returns can steer a
> program anywhere inside its budget, though nowhere outside it.

THREAT_MODEL.md says the larger version of the same thing, in the Known
open table, under *Secrets arriving another way*: a value read through
`read_line`, passed in through `args()`, fetched over `net` or returned
by a tool is an ordinary `Text` with no protection.

`Secret of T` bounds where a value may **go**. Nothing bounds what a
value may **name**. Those are different problems and the second one is
the one an agent runtime has: the budget says `fs:read:./data` and
`tool:search@20`, and inside that a document a search tool returned can
choose which file under `./data` is read, which of the granted hosts is
reached, and what the next tool call's arguments say. Every one of those
is inside the budget. The budget was never going to catch it: a budget
bounds the set of resources, and this is a choice within the set.

**The case found in 8.5**, which `check_runner.py` records and this
decision closes:

    fn summarise(topic: Text) -> Text uses tool, fs or fail {
        let found = try tool("search", json_of({"query": topic}))
        let name = try json_get(found, "attachment")   // the host's words
        return try read_file("./data/" + name)          // inside fs:read:./data
    }

Run under `--allow io,fs:read:./data,tool:search@20`, every operation
here is granted. A `search` result that says `attachment:
"../../.ssh/id_rsa"` is refused - E313, because the budget resolves
paths - but one that says `attachment: "payroll.csv"` is not, and the
program reads and returns a file the topic never named. The same shape
sends the file to whichever granted host the document picks, and puts
whatever the document says into the next `tool` call's arguments. 8.5
shipped with this written down and the advice "grant the narrowest
budget its task needs"; that advice is right and is not a mechanism.

## What was decided

**`Untrusted of T` is `Secret of T`'s machinery, with a different set of
sinks and no rule about branching.** One mark implementation, two
instantiations - this is the central decision, and everything below
follows from it.

That means the rules of SPEC.md section 3.1 hold verbatim for
`Untrusted of T`, with `Untrusted` substituted for `Secret`: what
carries one (a value that is one, or holds one anywhere inside - a list,
a map's values, a record's field, a record with a field of such a
record); what keeps one (**every pure operation on a value that carries
the mark gives an `Untrusted` of its result type**, comparisons
included); what does not (a container's own shape - `length` of a `List
of Untrusted of Text`, `keys` of a map of them, `has`); that there is no
`Untrusted of Untrusted of T`; and that **no type variable is bound to a
type that carries one**, for the reason the Secret rule gives, which
applies unchanged: a generic body checked with `T` standing for nothing
in particular will hand `to_text(x)` back as a plain `Text`, and that is
laundering. The way to write a generic function over untrusted values is
to say so in the signature - `fn first(xs: Untrusted of List of T) ->
Untrusted of T for any T`.

### Where one comes from

| Builtin | Gives | Why |
|---|---|---|
| `fetch(url)`, `post(url, body)`, `request(m, url, body, headers)` | `Untrusted of Text` | a remote host chose the bytes |
| `fetch_status(url)` | `Untrusted of Int` | a remote host chose the number |
| `read_file(path)` | `Untrusted of Text` | the budget named the directory; nothing named the content |
| `read_line()`, `ask(prompt)` | `Untrusted of Text` | whoever is on the other end of standard input chose it |
| `args()` | `Untrusted of List of Text` | in an agent setting the command line is assembled by a model |
| `tool(name, arguments)` | `Untrusted of Text` | the case above |
| `db_query(handle, sql, params)` (new in 9.0, 0005) | `Untrusted of Text` | rows are what somebody else put in the table |

And nothing else. In particular:

- **`env()` is not one, and `read_file_secret` and `tool_secret` are not
  ones.** Each already returns a `Secret of T`, and a `Secret` reaches no
  sink at all without `declassify` - which needs the effect, the
  operator's grant and a reason written as text in the call, and is
  named in the audit. That is exactly what `trust` needs and does. A
  value gets one gate on the way to a sink, not two; two would be two
  written reasons for one decision, and an audit carrying both would say
  less, not more. `args()` and `read_line()` have no such gate, which is
  why they need this one.

  The counter-case is real and is answered elsewhere: an environment
  assembled by something that is not the operator. THREAT_MODEL.md
  already says "Do not start Sabline with an environment someone else
  controls - which was already true of `PATH` and `PYTHONPATH`", and the
  answer there is to withhold the `env` grant, not to mark the value. A
  program that knows its environment is assembled by something it does
  not trust writes `env_untrusted(name, fallback)`, new in 9.0, which
  gives `Secret of Untrusted of Text` - the same relation
  `read_file_secret` has to `read_file`.

- **A granted Python module's results are not ones.** `py`, `py_json`,
  `py_field` and `py_do` give ordinary values. THREAT_MODEL.md's rule
  for `ffi` is that the grant *is* the trust: "The allow-list narrows
  which module a call reaches, not what it does... treat the grant as
  trust in those modules." Marking every FFI result untrusted would put
  a `trust` call in every use of `csv.vel`, `dates.vel` and `db.vel`,
  and a mark that appears in every program stops being read. This leaves
  a real gap - `ffi:requests` fetches the network and hands back a body
  that is not marked - and it goes in THREAT_MODEL.md's Known open
  table as *Untrusted content through a granted module*, with the
  recommendation that a program that must mark such a value passes it
  through the library function that does, not through its own.

### Where one cannot go

An `Untrusted` value given to anything on this list is **E570**, which
names the value, the sink, and where the mark came from - the shape
E560 already uses.

| Sink | The argument that refuses one |
|---|---|
| `fetch`, `fetch_status`, `post` | the URL |
| `request` | the URL (its second argument) |
| `read_file`, `read_file_secret`, `write_file`, `file_exists` | the path |
| `py`, `py_int`, `py_float`, `py_json`, `py_new` | the module name, and every name in the attribute chain |
| `py_do`, `py_field` | the method or field name |
| `tool`, `tool_secret` | the tool's name, **and** its arguments text |
| `db_open`, `db_query`, `db_exec` (new in 9.0, 0005) | the path, and the `sql` text - **never** the `params` list |
| `import` | the path |

Three of those need saying out loud.

- **A tool's arguments are a sink, and a tool's result is a source.**
  That pair is what closes the case above: a document a `search` tool
  returned cannot become the argument of a `send_email` call. 8.5 holds
  tool arguments to the operator's patterns (E321); 9.0 adds that they
  may not be the host's own words.
- **A query's `sql` is a sink and its `params` are not.** That is the
  whole of the CWE-89 argument in 0005, stated as a type rule: an
  untrusted value cannot be part of the statement, and putting it in the
  parameter list - the only thing left to do with it - is the thing that
  was always correct. The fix is not advice; it is the only shape that
  compiles.
- **`import` is a sink and, in the reference, a vacuous one.** An import
  path is a literal read at compile time, so no runtime value can reach
  it and the rule refuses nothing today. It is stated and enforced
  anyway, so that a later dynamic import cannot open the hole by
  omission.

And what is **not** a sink, which matters as much:

- **Nothing that only emits.** `print`, `log`, `write_file`'s *content*,
  `post`'s *body*, `fail`'s reason, `exit_with`'s status. `Untrusted`
  bounds what a value may **name**, not where it may go; bounding where
  it may go is `Secret`'s job and doing both with one mark would make
  neither legible. A program may print what a tool said, and should.
- **No `if` or `while` rule.** There is no twin of E563, and this is the
  one place the two marks genuinely differ. Branching on a secret is an
  oracle; branching on untrusted data is **validation**, which is the
  thing a program ought to do with it. Refusing it would refuse the fix.

### The way out, and the better way out

`trust(value, reason)` takes an `Untrusted of T` and gives back the `T`.
It says so three times, as `declassify` does:

- the function doing it declares `uses trust`, checked across the whole
  call graph like any other effect (E300);
- `reason` is written as text in the call, not built while running, so
  `sabline audit` can report it without running the program (**E571**,
  which is also what a `trust` of something that is not `Untrusted`
  gets, and what an empty reason gets);
- the operator's budget grants `trust`, or the call is refused at the
  moment it is reached (E310), like any other effect.

`trust` is the tenth effect. It reaches nothing outside the program, for
the reason sabline-spec section 3.1 already gives about `declassify`:
it is an effect because it is the only operation that removes a mark the
type system put on, and because an operator who withholds it gets a
program that cannot launder anything.

**The better way out is not to call it.** The pattern that needs no
`trust` and no effect is to branch on the untrusted value and use the
program's own literal:

    let name = try json_get(found, "attachment")      // Untrusted of Text
    if name == "payroll.csv" {
        return try read_file("./data/payroll.csv")    // the program's word
    }
    fail "that attachment is not one this program reads"

That compiles with no `trust`, no grant and no audit entry, because
nothing untrusted reaches the sink: the comparison is allowed, the
literal is the program's. Every migration note, every error message and
the documentation say this before they mention `trust`.

### Both marks at once

A value carries both when two values are combined: `env("USER", "") ==
get(args(), 0)` is a `Secret of Untrusted of Bool`; a record with a secret
field and an untrusted field carries both, and so does `json_of` of it;
`hmac_sha256(key, body)` where `body` came off the network gives
`Untrusted of Text`, which is right - a MAC of attacker-influenced input
is attacker-influenced - and is still what the audit records as a
declassification.

- **The spelling is `Secret of Untrusted of T`**, always, with `Secret`
  outermost. `Untrusted of Secret of T` is **E572**, whose message gives
  the canonical spelling; so is a doubled mark of either kind, which is
  what E562 says today for `Secret of Secret of T` and what E572 says for
  `Untrusted of Untrusted of T`. One spelling, so that a signature, an
  error message and a golden all agree.
- **The two ways out are independent and neither implies the other.**
  `declassify` removes `Secret` and leaves `Untrusted`; `trust` removes
  `Untrusted` and leaves `Secret`. A value that is both needs both
  calls, both effects, both grants and two written reasons - which is
  correct, because they are two different statements, and it is also why
  neither of the three builtins that already return a `Secret` is
  additionally a source.
- **Sinks compose the obvious way.** A `Secret of Untrusted of Text` at
  a path argument is refused; the code given is E560, because a `Secret`
  reaches no effectful builtin at all and that is the stronger and
  earlier rule. E570 is given when the value carries `Untrusted` and not
  `Secret`.

### What a reader of documents sees

- **`sabline.audit/1` gains `untrusted`**, an object beside `secrets`
  and shaped like it, added within version 1 so a consumer that does not
  know it ignores it (sabline-spec section 8.1): `sources`, the sorted
  names of the source builtins the program as loaded reaches; `trusts`,
  true when it contains at least one `trust` call; and `trustings`, one
  object per call with `reason`, `function` and `line`, sorted. An
  implementation with no such type writes empty values, as it does for
  `secrets`. The whole field is null when the program could not be
  loaded.
- **A receipt gains `trustings`**, one object per distinct call with
  `reason`, `line` and `times` - `declassifications` exactly - and
  `effects_used` may hold `trust`. The rule that a receipt holds no
  value the program handled has no exception here: a reason is the text
  written in the program, never the value trusted.
- **SARIF gains the rule `value-trusted`**, at warning level, beside
  `secret-declassified`, with `--allow-trust-reasons` as the twin of
  `--allow-declassify-reasons`: a reviewed reason passes, a new one
  appears in the pull request. Under `--strict` it is an error unless
  listed. The compile-time codes E570, E571 and E572 become SARIF rules
  the way every code does, from `ERROR_TABLE`.
- **The capability predicate and the ratchet need no new rule at all.**
  `trust` is an effect, so it is in `effects`, in `safe_command` and in
  `sabline.capabilities/1` like any other, and a program that gains its
  first `trust` call widens its surface and fails `sabline capabilities
  check` until the baseline is changed in review - which is exactly what
  6.0's `declassify` did, and is the behaviour to want. sabline-spec
  section 9 changes only by the effect list growing.

## The compatibility story

**This is a break, and it is the largest one 9.0 makes.** Three shapes
of 8.x program stop compiling, and they are the same three shapes 6.0's
`env()` change stopped, for the same reason.

1. **A signature that says it returns `Text` and returns a source's
   result** - E503. `fn get(url: Text) -> Text uses net or fail { return
   try fetch(url) }` is `stdlib/http.vel` line 6.
2. **A `Text` variable, field or parameter holding one** - E501. `record
   Answer { status: Int, body: Text, raw: Text }` is `stdlib/http.vel`,
   and `RestAnswer` is `stdlib/rest.vel`.
3. **A source's result reaching a sink** - E570. This is the one the
   release is for, and the only one of the three that is a finding
   rather than a signature to widen.

Measured against this tree, at 8.6.0: **13 of 104 `examples/`, 6 of 14
`stdlib/` files and 47 of 85 `benchmark/corpus/` programs** call at
least one of the source builtins, and are the upper bound on what needs
attention. The shipped standard library changes in the same release:
`http.vel`'s `get`, `send`, `get_json` and `call`, `rest.vel`'s `call`,
and the four batteries built on them - `github.vel`, `k8s.vel`,
`aws.vel`, `azure.vel` - return `Untrusted` values, and `Answer` and
`RestAnswer` hold them. `http.status`'s `ensures result >= 0` becomes an
`Untrusted of Bool`, which is allowed: a promise is not a branch, and
sabline-spec's rule for a `Secret of Bool` promise covers it unchanged.

Touching a source is not the same as breaking, and the difference is
where most of the 66 programs above land. `examples/tools.vel` calls
`args()`, reads it with `get`, measures it with `length`, branches on
that length and prints every item through `format` - and compiles
unchanged, because printing is not a sink and branching is not refused.
What breaks is a program that annotates the value `Text`, returns it as
a `Text`, or hands it to something that names a resource. The migration
report separates the two, and the release note leads with the second.

**What `sabline migrate --to 9.0` does.** It reads a program or a tree
and reports, per file and per line: every value that becomes
`Untrusted`, where the mark came from, and which of the three shapes
above refuses it. `--write` changes only what is mechanical and
reversible - a `Text` annotation on a local, a field, a parameter or a
return type widened to `Untrusted of Text` where the checker can trace
the value to a source - and it re-checks the file afterwards, putting
back what it wrote if the file stopped compiling.

**`--write` never inserts a `trust` call.** Deciding that a particular
untrusted value may name a resource is the security decision this
release exists to surface; a tool that made it, and wrote a reason for
it, would be a tool that turns the release into a no-op. For every place
where only a `trust` or a validation will do, migrate prints the line,
the sink, the source, and both ways out - the comparison against a
literal first, `trust(value, "...")` second with the reason left blank
for a person to write. `sabline migrate --to 9.0 --json` gives the same
as `sabline.migrate/1`, so a repository can count what is left.

## What was rejected

- **Tainting only tool results**, which is the case 8.5 recorded. A mark
  that catches a `search` result steering a path and not a `read_file`
  result steering a URL is a mark whose boundary is an implementation
  detail of where the value came from, not a property a reader can
  state. The rule has to be "from outside the program".
- **A `Trusted of T` marking the safe values instead**, so that nothing
  existing breaks. It defaults the wrong way: every value a program has
  not thought about would be safe, and the interesting programs are the
  ones nobody thought about. The default has to refuse, for the reason
  5.0 changed the default budget to `io`.
- **A branch rule, the twin of E563.** Refusing `if name ==
  "payroll.csv"` would refuse validation, which is the fix.
- **Making `trust` pure**, with no effect and no grant. Then an operator
  could not run a program with the laundering switched off, and a
  program's audit could not be read for whether it launders at all. The
  effect is most of the value.
- **A second, weaker mark for values a program has validated**, so that
  the checker could tell a validated value from a trusted one. It is a
  dataflow claim the type system cannot check without dependent types,
  and a mark the compiler cannot check is a decoration. The comparison
  pattern above gets the same result with no new type: a program that
  validates ends up using its own literal.
