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
