# AgentDojo evaluation

Sabline in the loop of [AgentDojo](https://github.com/ethz-spylab/agentdojo),
the agent-security benchmark of Debenedetti et al. The score is published on
[/agentdojo.html](https://sabline.dev/agentdojo.html); this directory holds
the evidence behind it, and `agentdojo_eval.py` at the top of the repository
records and re-derives it.

## What is here

    evals/agentdojo/
      README.md         this
      manifest.json     AgentDojo's tools as a sabline.tools/1 manifest
      results.json      every run's outcome, and the totals the page shows
      programs/         the Sabline programs, generated from ground truth
        benign_<user_task>.vel      the user task's reference solution
        attack_<injection_task>.vel the injection's own action

`../requirements/agentdojo.txt` pins the AgentDojo version the numbers were
measured on. A number is comparable only against one measured on the same
suite and version, so the version is in `results.json`, on the page, and in
that requirements file.

## How it works, and what it does not do

There is **no model here, and no cost**. AgentDojo's own agent pipeline needs
an LLM; this replaces it with AgentDojo's own ground truth. For each user
task the benign program is the task's reference solution; for each injection
task the attack program is the injection's ground-truth action. Each is run
through `sabline run --tools manifest.json --allow BUDGET` against AgentDojo's
real environment, and scored by AgentDojo's own `utility` and `security`
(their trace-based forms where a task has one).

So the numbers are the **operator budget's contribution**, not a model's:

- **Utility** is whether the reference solution runs to completion under a
  budget written for the task. It is reported over all user tasks and over
  the *scorable* subset - the tasks whose reference solution can be judged
  offline. A task that needs model-generated content (a summary, a free-text
  message body) encodes it as a placeholder in its ground truth, which no
  budget can make satisfy the check; those are not scorable here, and the
  page says how many.
- **Attack success** is whether a budget written for the user task lets the
  injection's action land. It is run on its own, not after the benign
  solution, so the number is the budget's verdict on the attacker's calls
  and nothing else. Under `--allow all` (the control) every injection lands;
  the drop under the task budget is what the budget refused.

## Three budgets, and which door the attacker came through

Every number is given under three budgets, each one more thing the operator
said:

| | |
|---|---|
| `all` | `--allow all`. The control: nothing is bounded |
| `task` | `io`, and a grant for each tool the reference solution calls |
| `pinned` | the task budget, with every argument the user task's **own text** names held to that value by the tool door's argument patterns (`tool:send_direct_message:recipient=Bob`, SPEC.md 7.2) |

`PINS` in `agentdojo_eval.py` is the pin table: one entry for every
`tool.argument` a reference solution passes, holding either the patterns the
task's text supports or the reason the text cannot say. `check_pins` holds
the table to two things and stops the run if either fails - it names exactly
the arguments the ground truth passes, and **every literal in every pattern
is in that user task's own prompt**. That is what makes "derived from the
task, never from what a tool returned" a check rather than a claim. Where
the pattern grammar itself could not say something, `PIN_LIMITS` records it
and runs it against the door's real matcher; the grammar is not extended to
flatter the numbers.

`results.json` also records, for every attack that lands under the task
budget, **which door the attacker's value came through**: written into the
program as a literal, or read at run time out of what a tool returned. It is
decided by matching what reached the door against the program's own string
literals, and the page says what the answer means - and what it does not,
given that the harness transcribes ground truth where a model would read.

What needs a model - and a key, and money - is how often a model is actually
steered, and how often it writes a working program at all. That is the harder
half, it is not measured here, and the report says so. `agentdojo_eval.py`
reserves `--model` for it, off by default and never run in CI.

## Reproducing it

    pip install -r requirements/agentdojo.txt
    python agentdojo_eval.py --record     # rewrite results.json and programs/
    python agentdojo_eval.py --check       # re-run and fail if a number moved
    python build_agentdojo_page.py         # rewrite docs/agentdojo.md

`--check` is what CI runs. The runs are deterministic, so a score here can be
reproduced rather than trusted; a model run is where the three repeats
AgentDojo asks for would differ, and that is not this.
