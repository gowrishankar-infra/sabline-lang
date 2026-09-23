---
slug: package-hallucination
title: Hallucinated packages, and squatting on them
date: 2024-03-28
lane: agent
verdict: PARTIAL
budget_line: import "lib/..."
verified: false
---

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

## Sources

- [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations) - Bar Lanyado's own write-up, 28 March 2024: the `huggingface-cli` test, the more than 30,000 downloads in three months, and the Alibaba README.
- [We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) - USENIX Security 2025: the rates, the sample size, and the 205,474 names.
- [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination) - the paper's published code and data.

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
