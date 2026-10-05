# AgentDojo evaluation

Sabline in the loop of [AgentDojo](https://github.com/ethz-spylab/agentdojo),
the agent-security benchmark of Debenedetti et al. All four of its suites are
run. The score is published on [/agentdojo.html](https://sabline.dev/agentdojo.html)
with a page per suite; this directory holds the evidence behind it, and
`agentdojo_eval.py` at the top of the repository records and re-derives it.

## What is here

    evals/agentdojo/
      README.md         this
      results.json      the roll-up over the four suites, derived from them
      slack/            one directory per suite
        manifest.json     AgentDojo's tools as a sabline.tools/1 manifest
        results.json      every run's outcome, and the totals the page shows
        programs/         the Sabline programs, generated from ground truth
          benign_<user_task>.vel      the user task's reference solution
          attack_<injection_task>.vel the injection's own action
          probe_<injection_task>.vel  the same action with its payload read
                                      at run time instead of written out
      workspace/        the same, 40 user tasks and 6 injections
      banking/          16 and 9
      travel/           20 and 7

`agentdojo_pins.py` holds the argument pins for all four suites, and nothing
else. `../requirements/agentdojo.txt` pins the AgentDojo version the numbers
were measured on. A number is comparable only against one measured on the
same suite and version, so the version is in every `results.json`, on every
page, and in that requirements file.

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
  budget can make satisfy the check; those are not scorable here, and each
  page says how many. The banking suite has six and the others have none.
- **Attack success** is whether a budget written for the user task lets the
  injection's action land. It is run on its own, not after the benign
  solution, so the number is the budget's verdict on the attacker's calls
  and nothing else. Under `--allow all` (the control) every injection that
  can land does; the drop under the task budget is what the budget refused.

## Three budgets, and which door the attacker came through

Every number is given under three budgets, each one more thing the operator
said:

| | |
|---|---|
| `all` | `--allow all`. The control: nothing is bounded |
| `task` | `io`, and a grant for each tool the reference solution calls |
| `pinned` | the task budget, with every argument the user task's **own text** names held to that value by the tool door's argument patterns (`tool:send_direct_message:recipient=Bob`, SPEC.md 7.2) |

`agentdojo_pins.py` is the pin table: one entry for every `tool.argument` a
reference solution passes, holding either the patterns the task's text
supports or the reason the text cannot say. `check_pins` holds the table to
three things and stops the run if any fails - it names exactly the arguments
the ground truth passes; **every literal in every pattern is in that user
task's own prompt**, or the pattern has a declared `DERIVED` entry that holds
up against that prompt; and no pattern shorter than three characters stands
without one, because a one-character literal is in almost any prompt by
accident (`5` is in `2024-05-20`, and two workspace event ids are exactly
that case). That is what makes "derived from the task, never from what a tool
returned" a check rather than a claim. Where the pattern grammar itself could
not say something, `PIN_LIMITS` and `DOOR_LIMITS` record it and run it
against the door's real matcher and its real grant check; the grammar is not
extended to flatter the numbers.

Each suite's `results.json` records, for every attack that lands under the
task budget, **which door the attacker's value came through** - and it does
it three ways, because they answer three different questions:

- `door_split.counts` is where the value came from **in this run**. Under
  ground-truth transcription that is always the program, *by construction*:
  the harness writes the resolved value out as a literal. On its own this
  number says nothing about AgentDojo.
- `door_split.counts_in_ground_truth` is what **AgentDojo itself** says about
  the same arguments. Its ground truth carries `placeholder_args` beside the
  resolved ones, and a `$code` or `$email.body` there is the benchmark
  marking a value a real agent reads out of the data. That is a fact about
  the corpus.
- `door2_probe` is **door 2, run for real**. For every injection whose ground
  truth marks an argument that way, and which makes a read call there is
  something to launder from, `probe_<injection>.vel` makes the same calls with
  that one argument built at run time out of the text the read returned. Each
  runs under the same three budgets and its verdict is compared, pair by
  pair, with the literal program's. The probe is reported beside the score
  and never inside it: it runs a program AgentDojo's ground truth describes
  but does not contain.

What needs a model - and a key, and money - is how often a model is actually
steered, and how often it writes a working program at all. That is the harder
half, it is not measured here, and the report says so. `agentdojo_eval.py`
reserves a model run for it, off by default and never run in CI.

## Reproducing it

    pip install -r requirements/agentdojo.txt
    python agentdojo_eval.py --record                 rewrite all four
    python agentdojo_eval.py --record --suite slack    rewrite one
    python agentdojo_eval.py --check --suite slack     re-run and hold it
    python agentdojo_eval.py --index                  rebuild results.json
    python build_agentdojo_page.py                    rewrite the five pages

`--check` is what CI runs, one leg per suite. The four together are about an
hour of subprocesses, which is why they are a matrix and not one job. The
runs are deterministic, so a score here can be reproduced rather than
trusted; a model run is where the three repeats AgentDojo asks for would
differ, and that is not this.
