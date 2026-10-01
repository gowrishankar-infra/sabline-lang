# Slopsquatting, replayed in Sabline

<!-- description: PARTIAL: On 28 March 2024 Bar Lanyado published a test of what he had named "AI package hallucination": models recommended installing a Python package ... -->

**Hallucinated packages, and squatting on them**, 2024-03-28. Also called package hallucination, hallucinated packages. ([The name in use](https://news.ycombinator.com/item?id=44810695).) Verdict: **`PARTIAL`** - part of the shape is refused and part is not; both halves are recorded.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

On 28 March 2024 Bar Lanyado published a test of what he had named "AI
package hallucination": models recommended installing a Python package
called `huggingface-cli`, which did not exist. He registered the
name and uploaded an empty package under it, and reports that "in three
months the fake and empty package got more than 30k authentic downloads",
and that "instructions for installing this package can be found in the
README of a repository dedicated to research conducted by Alibaba". The
USENIX Security 2025 paper by Spracklen and colleagues measured the
phenomenon across 576,000 generated code samples from 16 models, finding at
least 5.2% hallucinated package references from commercial models and 21.7%
from open-source ones, across 205,474 distinct invented names.

## The shape, in Sabline

A model writes a dependency that does not exist, and somebody is waiting at
that name. The half of this that Sabline answers is structural rather than
clever: a Sabline import is a path to a file in the project, not a name
resolved over a network. `import "lib/huggingface_cli.vel"` does not reach
somebody else's package - it does not reach anything, and the compiler says
so before the program runs (E512). There is no registry to squat on because
there is no registry.

The half it does not answer is the one that matters on a real machine.
`via_python.vel` calls `py("huggingface_cli", "whoami", ...)`, and a budget
that names that module - `ffi:huggingface_cli`, exactly what an operator
following the model's own instructions would write - loads whatever is
installed under that name from the Python environment. Here nothing is
installed, so the call fails rather than refuses, and the entry records
that plainly: the message is `cannot import 'huggingface_cli'`, which is a
failure the program handles, not a refusal. Had the package been there, it
would have run.

## The one line that does the work

import "lib/huggingface_cli.vel"

The import line itself. A Sabline dependency is vendored as source into
`lib/` with `sabline add`, which records its sha256 in `sabline.lock`; a
name that was never vendored resolves to nothing at all.

## What this does not cover

`ffi:NAME` names a Python module in the environment Sabline was started in,
and Sabline neither installs it nor checks where it came from - a
hallucinated name that somebody has registered on PyPI and the operator has
installed is reached by exactly the grant the model asked for. Nothing here
tells an operator that a module name was invented.

### hallucinated.vel

```vel
// The model wrote the dependency the way it writes them for every other
// language: a name it expects somebody else to have published.

import "lib/huggingface_cli.vel" as hf

fn main() uses io {
    print(hf.whoami())
}
```

### via_python.vel

```vel
// The same invented name, reached the way a Sabline program actually can
// reach the Python environment: by asking for it, with the operator
// granting exactly the module the model named.

fn main() uses io, ffi {
    check py("huggingface_cli", "whoami", ["--token"]) {
        ok who {
            print(who)
        }
        fail why {
            print("the call failed: " + why)
        }
    }
}
```

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the invented dependency resolves to nothing, not to somebody else's package
$ sabline hallucinated.vel --allow io --receipt receipt.json
error[E512] cannot find imported file 'lib/huggingface_cli.vel'
  --> hallucinated.vel, line 4
  how to fix (pick one):
    1. check the path in the import line
    2. paths are relative to the importing file
  reference: https://sabline.dev/llms.txt
exit 1

# the same name reached through Python, with no ffi grant
$ sabline via_python.vel --allow io
error[E310] 'py' needs the 'ffi' effect, which this run does not allow (it allows: io)
  --> via_python.vel, line 6
  how to fix (pick one):
    1. allow it: sabline <file> --allow io,ffi
    2. a run with no --allow gets io (5.0); --allow all grants every effect
    3. or use a program that does not need it
  reference: https://sabline.dev/llms.txt
exit 1

# and with the grant the model's own instructions would ask for
$ sabline via_python.vel --allow io,ffi:huggingface_cli
the call failed: cannot import 'huggingface_cli'
sabline: ffi:huggingface_cli is not in the confinement table, so the operating system layer is off for this run: the budget is the only boundary
exit 0
```

## Sources

- [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations) - Bar Lanyado's own write-up, 28 March 2024: the `huggingface-cli` test, the more than 30,000 downloads in three months, and the Alibaba README.
- [We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) - USENIX Security 2025: the rates, the sample size, and the 205,474 names.
- [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination) - the paper's published code and data.

The entry, its program and its recorded run are in [incidents/package-hallucination/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/package-hallucination/). Every incident, with its verdict, is in [the catalogue](incidents.md).
