## Add Sabline tools: sandboxed execution of agent-written code

### The problem

When an agent writes code, the crew has to run it somewhere. Today the
choices are a subprocess with the crew's full permissions, or a
container. Neither tells you *what the code will do* before it runs,
and neither lets the crew's author say "this agent may print and
nothing else."

### What this adds

Two tools (plus a third that returns the language reference):

- `SablineAuditTool` — reports what a program can touch (io, fs, net,
  clock, rand, ffi, declassify), whether it holds a secret and whether
  it ever lets one out, what each function promises, and whether those
  promises were proven before running. Returns versioned JSON.
- `SablineRunTool(allow=["io"])` — runs the program with an effect
  budget the crew's author sets. Effects outside it are refused while
  the program runs, whatever the source claims, and a refusal cannot
  be caught by the program.

Sabline is a small language built for this: a function's signature
declares its effects and its promises, and a theorem prover checks the
promises before execution. A model learns it from a ~4,600-word card
(the third tool returns it), so an agent can write it without prior
training.

### Tests

Five tests, all runnable in CI with `pip install sabline-lang`:
the audit names effects, the run refuses `fs` when only `io` is
allowed, permits it when granted, returns output, and defaults to
`io`-only.

### Honest limits

Not a security boundary. `allow=["ffi"]` grants everything Python can
do, and nothing here limits memory or time. It is a guard for the
ordinary case of running a script a model wrote. The tool's docstring
and README say so.

### Links

- Language: https://github.com/gowrishankar-infra/sabline-lang
- The library these tools wrap, and its test suite proving the budget
  holds through the API: `EMBEDDING.md` and `check_library.py` there
