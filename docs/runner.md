# Hosting a run that calls tools

The runner's first cut, new in 8.5. A host process - an agent framework, a
service, a script - starts a Velaris program and offers it tools. The
program calls them with `tool(name, arguments)`; the operator's budget says
which may be called and holds arguments to patterns; and the host's manifest
says what each tool takes, what it costs, and the most one run may spend.
There is no adapter for any framework yet: the protocol below is all of it.

`examples/runner/host.py` is a whole host in a hundred lines of Python, and
`examples/runner/digest_outside.vel` a program it refuses.

<!-- illustrative: needs a host on the other end of the pipe -->
```sh
velaris run program.vel --tools tools.json \
    --allow io,tool:search@20,tool:send_email:to=*@corp.com \
    --receipt run.receipt.json
```

**The manifest** (`velaris.tools/1`) is the host's:

```json
{"schema": "velaris.tools/1",
 "tools": {
   "search": {"description": "Look a phrase up.",
              "arguments": {"type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]},
              "cost": 1},
   "vault":  {"arguments": {"type": "object"}, "result": "secret"}},
 "allow": ["tool:search@20"],
 "ceiling": {"calls": 25, "cost": 40, "unit": "credits"}}
```

`arguments` is a JSON Schema, of the keywords Velaris checks and no others
(`type`, `properties`, `required`, `additionalProperties`, `items`, `enum`,
`const`, `minLength`, `maxLength`, `minimum`, `maximum`, `minItems`,
`maxItems`; a manifest that uses another is refused, because a constraint
nobody checks is one somebody believes). An object takes no property its
schema does not name unless `additionalProperties` says so. `result:
"secret"` makes the result a `Secret of Text`, which the program has to ask
for with `tool_secret`. `cost` is what a call spends, in a unit that is
the host's. `allow` is the host's own grants, in the budget's grammar; a
call has to pass them and the operator's `--allow`. `ceiling` is the most
calls and the most cost one run may spend.

**The budget** is the operator's, as for any effect: `tool` (any tool),
`tool:NAME`, `tool:NAME:ARGUMENT=PATTERN`, `tool:NAME@N`, `tool@N`. With no
`tool` grant every call is refused (E310). SPEC.md 7.2 has the pattern
rules, and the section below what they hold against.

**The door** is the run's standard input and output, one JSON object to a
line, UTF-8. From the run:

| Event | Fields |
|---|---|
| `ready` | first: `protocol` (`velaris.tools-door/1`), `velaris`, `budget`, `tools` |
| `output` | `text`: one line the program printed. Its standard error is still standard error |
| `call` | `id`, `tool`, `arguments` (a JSON object, already held to the schema, the grants and the ceilings) |
| `exit` | last, whatever ended the run: `status`, and the ceiling record - `calls`, `cost`, `unit`, `calls_used`, `cost_used`, `manifest_sha256` |

To the run, one line for each `call`, while the run waits:

<!-- illustrative: two replies, one to a line; not one JSON document -->
```text
{"id": 1, "result": "three documents matched"}
{"id": 2, "error": "the index is offline"}
```

`result` is a text, or any JSON value, which the program receives as JSON
text. `error` becomes a failure the program handles with `check`. `cost`,
when given, replaces the manifest's for that call, and must be a number, 0
or more. `"secret": true` marks one result secret. Anything else in a
reply is ignored. One call is open at a time. A reply that is not a line of
JSON, carries another id, holds both or neither of `result` and `error`, or
does not come within `--tool-timeout` seconds (120) stops the run with
E324. The program reads nothing from standard input while it is hosted:
`read_line` gives an empty line.

`velaris skill verify`, given a directory `DIR`, reads a skill before any of it runs: the
programs under `DIR`, and the manifest in `DIR/tools.json` (or `--tools
FILE`). It reports the tools the programs name and whether the manifest
offers each, the budget that covers every program, what they declassify
and which Python modules they call, and the manifest's own grants and
ceiling; it exits 1 when a program does not compile, names a tool the
manifest lacks or one built while running, or would take a secret result
as `Text`. `--json` writes `velaris.skill-verify/1`.

**What is not here yet.** A result is a `Text` like any other; nothing
marks it as the host's words rather than the program's, so what a tool
returns can steer a program anywhere inside its budget, though nowhere
outside it. That mark, `Untrusted`, arrives in 9.0, with the HTTP door for
tools and the first framework adapters. `velaris.tools/1`,
`velaris.tools-door/1` and `velaris.skill-verify/1` are provisional until
then (STABILITY.md).

## Reading a receipt, or an audit, as a page

`velaris receipt show RECEIPT` writes a receipt as a page: what was read,
written and fetched - by grant, with counts, from `grants_used` - which
secrets were declassified and why, each tool call, what was refused and
where, the confinement level, the wall time and the subjects. `velaris audit
program.vel --html` does the same for an audit. Both write to standard
output or `-o FILE`: plain HTML with this site's stylesheet inside it, no
script, nothing fetched, every value escaped, and the same bytes for the
same input on every system. `--text` writes a receipt for a terminal, with
control characters written as escapes. Neither verifies anything; that is
`velaris verify`.

## Who trusts whom

A run started with `--tools` and a manifest lets a program call tools
the process that started it offers (the protocol is above). Who
trusts whom:

- **The host is trusted; the program is not.** The manifest is the host's
  and the budget is the operator's, and a call has to pass both before the
  host hears of it: the tool is one the manifest offers (E320), the budget
  and the manifest's own `allow` grant it and every argument they hold to a
  pattern matches (E321), no `@N`, call ceiling or cost ceiling is passed
  (E322), and the arguments are what the tool's JSON Schema says, with no
  property it does not name (E323). Each is a refusal: it stops the run,
  cannot be caught, and is in the receipt.
- **An argument pattern is a whole-value match.** Every character stands for
  itself and `*` for one or more characters, never the literal that follows
  the star in the pattern (so `*@corp.com` holds exactly one `@`), never
  `, ; < > " ' \`, white space, a control or a format character, and never
  across `..`. Nothing is trimmed, case-folded or normalised first. A list
  matches when every item does; a map, a null, or an argument that is left
  out does not match. `check_runner.py` tries fourteen ways past
  `to=*@corp.com`.
- **A host that lies** about a result cannot be detected, and is not the
  threat: the host is the operator's own process. What a reply can do is
  bounded. It is one line of JSON carrying the open call's id and either a
  result or an error, or the run stops (E324); a cost that is negative, not a
  number or NaN is E324, so a reply cannot win budget back; any other field
  it adds is ignored; and a result is a `Text`, or a `Secret of Text` from
  `tool_secret` - it is never a grant. A reply may mark its result secret,
  which a call through `tool` then refuses (E323); it cannot unmark one the
  manifest marks.
- **A result that steers** is the case this release does not close. A result
  is a `Text` like any other, so a program may use it as a URL, a path or
  another tool's argument, and the budget holds it exactly as it holds any
  value: a host outside `net:` is E314, an address outside `to=*@corp.com`
  is E321. *Inside* the budget, a hostile document that a `search` tool
  returns can still direct what the program does with what it was granted.
  The mark that would let a program, a signature and an audit tell the
  host's words from the program's own is `Untrusted of T`, and it arrives in
  9.0. Until then: grant a program that reads tool results the narrowest
  budget its task needs, and hold the arguments that matter to patterns.
- **What the receipt holds.** Each call site - the tool, the line, how
  often, whether its result was secret - and the grants whose patterns held
  its arguments, as the operator wrote them; the ceiling, what was spent of
  it, and the sha256 of the manifest. Not the arguments and not the results:
  a receipt holds no value the program handled, and that rule has no
  exception here.
