# A platform that lets its customers write Sabline

Your customers want to write their own rules — a discount, a routing
decision, a validation — and run them on your machines. Before one runs
you have to know what it may touch. If it computes money, you also have
to know its arithmetic holds, and no sandbox can answer that.

`app.py` is the whole pattern in one file: audit at submission, refuse a
surface wider than the platform permits, and run what is left on a
`sabline.Pool` whose budget is yours.

## The demo: a rule proven never to return a negative total

A customer writes [`examples/discount.vel`](../discount.vel) — a
percentage off above a threshold, a flat amount as well, and a cap on
the two together. The platform did not write it and does not need to
understand it. It needs two things to be true of it, for every basket
and every rule the types allow:

```
fn discount_for(total: Money of INR, rule: Rule) -> Money of INR
    ensures result >= money(0, "INR")
    ensures total - result >= money(0, "INR")
```

Submitting it returns, among the rest of its declaration:

```json
"proven_share": 100.0,
"prover_ran": true,
"contracts": [
  {"function": "discount_for",
   "ensures": ["result >= money(0, \"INR\")",
               "total - result >= money(0, \"INR\")"],
   "status": "proven"}
]
```

`"status": "proven"` means Z3 settled that promise before anything ran,
for every input the types allow — not that a test passed. That is the
sentence a platform can put in front of a customer before offering to
enable a rule, and the one a sandbox cannot produce.

[`examples/discount_bad.vel`](../discount_bad.vel) is the same rule with
one guard deleted. It never reaches storage:

```json
{"error": "this does not compile, so it cannot be enabled",
 "problems": [{"code": "E700",
   "message": "promise cannot be kept: 'discount_for' ensures total - result >= money(0, \"INR\") - proven without running the program: rule = Rule(percent: 0, above: 0, flat: 2, cap: 1), total = 0 gives result = 1"}]}
```

A basket worth nothing, a flat discount of two paise held down to a cap
of one, and one paisa handed back anyway.

## Running it

From the repository root:

```
pip install fastapi uvicorn
python -m uvicorn app:app --app-dir examples/platform
```

`GET /` prints the platform's policy: the budget every script runs
under, and the time and memory ceilings.

## Submit, inspect, run

```
# 1. submit - the service audits it, stores it, and never runs it
curl -s -X POST 'http://127.0.0.1:8000/scripts?name=discount' \
     --data-binary @examples/discount.vel

# 2. inspect - what this script declares, before anyone enables it
curl -s http://127.0.0.1:8000/scripts/<id>

# 3. run - on the platform's budget, not the script's
curl -s -X POST http://127.0.0.1:8000/scripts/<id>/run
```

The declaration is read off `sabline.audit/1` and holds the effects the
script may perform transitively, the hosts and paths it names, the
Python modules it reaches, the most file and network operations one run
can make, its proven share, its contracts function by function, and the
narrowest budget that would run it:

```json
{"effects": ["io"], "narrowest_budget": "io",
 "hosts": {"hosts": [], "any": false},
 "paths": {"read": [], "write": [], "read_any": false, "write_any": false},
 "modules": [], "most_operations": {"fs": 0, "net": 0},
 "proven_share": 100.0, "prover_ran": true}
```

The run answers with one word for how it ended, plus the output, what
the budget refused, and which limit stopped it:

```json
{"outcome": "ok", "output": "...payable  INR 112.90\n...",
 "refused": [], "stopped_by": null, "effects_used": {"io": 16},
 "ran_under": "io,net:api.example.com@20"}
```

## Refused at submission

This platform grants `io,net:api.example.com@20` — the console and its
own API. A script that reads a file declares more than that, and is
refused before it is stored, with the grants an operator would have to
add:

```json
{"error": "this server does not grant fs",
 "declares": "fs:read,io",
 "platform_allows": "io,net:api.example.com@20",
 "would_need_granting": ["fs:read"]}
```

The audit reads literals. A script that builds its host while running
declares plain `net`, because nothing in the text says which host — so
it is refused too, where the same program with the host written out is
accepted as `net:api.example.com`. Widening is the honest answer when
the text does not fix a value, and the gate acts on it.

## Two guards, and they are not the same guard

The audit is a read of the text and the gate is a policy decision made
from it. The pool is the enforcement: its budget is parsed once when the
pool is made, `pool.run` takes no `allow` argument, each worker installs
the budget before the program is read, and a refusal cannot be caught by
the program. `check_platform.py` puts a script straight into the store,
past the gate entirely, and asserts the run is still refused —

```json
{"outcome": "refused",
 "refused": [{"by": "budget", "code": "E310", "what": "fs"}],
 "output": ""}
```

— which is the property a platform team needs: a bug in your gate is not
a bug in your containment. What the gate cannot see at all is how *much*
a script does, where its text fixes no bound; the pool holds the count,
the clock and the memory regardless.

## What a real platform would add

Storage here is a dict in one process, so scripts vanish on restart and
there is nothing to migrate: a real one persists the source, the audit
it was accepted on and the Sabline version that produced it, so a
compiler upgrade can re-audit what is already enabled rather than
trusting a verdict from an older prover. It authenticates the submitter
and scopes every script to a tenant, since `PLATFORM_ALLOW` here is one
global constant where a real one is per-tenant or per-plan policy —
which means a `sabline.PoolRegistry`, one pool per distinct budget,
rather than the single pool in this file. It would keep a
`sabline.InvocationLog` of every run, rate-limit runs per tenant, pass
input through `pool.run(stdin=, args=)`, and re-run the gate when the
policy tightens, because a script accepted under a wider budget is still
in the store. None of that changes the shape of what is here. This file
is an example; it is not production code.

## Tests

```
python check_platform.py
```

Fifteen assertions covering the whole path: a submission inside the
budget accepted, one outside refused with what would need granting, a
rule whose promise cannot be kept refused with its counterexample, the
discount rule's contracts showing as proven, an effect refused at run
time for a script the gate never saw, and a run stopped by the time
limit. Two of them depend on z3-solver: without it one is skipped and
the other asserts that the declaration says no prover ran, rather than
a proven share that would mean nothing. The suite skips cleanly when
fastapi is not installed — fastapi is a dependency of this example,
never of Sabline.
