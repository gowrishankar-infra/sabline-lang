# velaris-lang

Run code you did not write.

```
npx velaris-lang script.vel
```

That program cannot read a file, reach the network or call Python -
whatever its source says about itself - and a refusal cannot be caught
and carried past. A run with no `--allow` gets `io` (5.0), so that is
the default rather than something you have to remember; widen it by
naming what the program needs, and `--allow all` grants every effect
and says so on stderr.

```javascript
import { audit, run } from "velaris-lang";

const report = await audit(source);
console.log(report.effects);        // ['fs', 'net']
console.log(report.proven_share);   // 66.7

const result = await run(source, { allow: ["io"] });
console.log(result.ok, result.output, result.refusedEffect);
```

Velaris is a language where a function's signature declares its types,
the effects it may perform, whether it can fail, and promises a theorem
prover checks before the program runs. This package is a thin wrapper
around that compiler.

Not a security boundary - allowing `ffi` grants everything Python can
do. It is a real guard for running a script a model wrote.

## The compiler

The compiler itself is a Python package. This wrapper calls it, so
install it once:

```
pip install velaris-lang
```

Two optional pieces are worth having:

```
pip install "velaris-lang[full]"
```

That adds `z3-solver`, which proves a function's promises before the
program runs instead of leaving them to be checked as it goes, and
`llvmlite`, which compiles pure integer and float code to native code
instead of interpreting it. Neither is required. Without them Velaris
runs fully interpreted and checks promises while running - it prints
`note: llvmlite is not installed - running fully interpreted` and
carries on, refusing effects outside the budget exactly the same way.

### Which Python it uses

The wrapper tries `py`, `python` and `python3` on Windows, `python3`
then `python` elsewhere, asks each one which Velaris it has, and uses
the newest. If the newest it finds is older than this npm package it
still uses it, but says so first, on stderr, naming both versions and
the interpreter - so a stale install left on PATH is visible rather
than mysterious. If you ask for a subcommand that version does not
have, it says which command and which version introduced it instead of
handing it over. `pip install -U velaris-lang` upgrades the compiler.

[Documentation](https://velaris-lang.dev/) ·
[Playground](https://velaris-lang.dev/playground.html) ·
[Source](https://github.com/gowrishankar-infra/velaris-lang)
